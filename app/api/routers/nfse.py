from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, insert, func, update, text, or_, case, and_
from typing import List, Optional
from app.core.database import SessionLocal, get_db
from app.schemas.nfse import NFSEDownloadRequest, NFSEDownloadResponse, NFSEDownloadStatus, BatchDownloadRequest
from app.models.download_job import DownloadJob
from app.models.company import Company
from app.models.documento_fiscal import DocumentoFiscal, TipoDocumento
from app.models.nfse import Nfse
from app.schemas.common import PaginatedResponse
from app.schemas.nfse_detail import (
    NfseSalvarRequest,
    NfseOut,
    NotaResumoOut,
    NotaDetalheOut,
    DashboardResumoOut,
    DashboardSerieItem,
    DashboardEmpresaItem,
    AnaliseAtividadeItem,
    AnaliseClienteItem,
    AnaliseEmpresaOut,
    AnaliseMatrizItem,
)
from app.services.adn_api import (
    fetch_distribuicao,
    extrair_campos_nfse,
    parse_xml_role_and_competence,
    EVENTO_CANCELAMENTO,
    situacao_para_evento,
)
from app.services.nfse_xlsx import gerar_xlsx_nfse_download
from app.services.danfse import gerar_danfse
from app.core.api_key import verify_api_key, api_key_dep
import uuid
import os
import tempfile
import zipfile
import asyncio
import io
from datetime import datetime

batch_status = {}
router = APIRouter(prefix="/nfse", tags=["nfse"])

def _para_ym(data: str | None) -> str | None:
    """Converte DD/MM/YYYY -> YYYY-MM (ou None)."""
    if not data:
        return None
    try:
        partes = data.split("/")
        if len(partes) == 3:
            return f"{partes[2]}-{partes[1]}"
    except Exception:
        return None
    return None


def _periodo_valido(
    competencia: str | None,
    datainicio: str | None,
    datafim: str | None,
) -> bool:
    """Verifica se a competencia (YYYY-MM) está dentro do período [datainicio, datafim]."""
    if not competencia:
        return False
    if not datainicio and not datafim:
        return True
    ini = _para_ym(datainicio)
    fim = _para_ym(datafim)
    if ini and competencia < ini:
        return False
    if fim and competencia > fim:
        return False
    return True


async def _process_single_company_async(
    company_id: int,
    batch_id: str,
    batch_status: dict,
    download_type: str = "xml",
    datainicio: str | None = None,
    datafim: str | None = None,
    force_update: bool = False,
):
    """Processa download ADN para uma única empresa."""
    db = SessionLocal()
    try:
        company = db.execute(select(Company).where(Company.id == company_id)).scalar_one()
        cnpj = company.cnpj
        nome = company.nome
        id_dominio = company.id_dominio or 0

        # Se force_update, busca notas existentes no banco para re-extrair
        if force_update:
            cid = str(company_id)
            batch_status[batch_id]["companies"][cid]["mensagem"] = "Consultando banco..."
            from app.models.documento_fiscal import DocumentoFiscal, TipoDocumento
            from app.models.nfse import Nfse
            
            notas_db = db.execute(
                select(Nfse)
                .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
                .where(
                    DocumentoFiscal.empresa_id == company_id,
                    DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                    Nfse.xml_original.isnot(None),
                )
            ).scalars().all()
            
            batch_status[batch_id][cid]["mensagem"] = f"Encontradas {len(notas_db)} notas, preparando..."
            
            xmls = []
            for n in notas_db:
                xmls.append({
                    "nsu": n.nsu,
                    "tipo": n.tipo_documento_api,
                    "chave": n.chave_acesso,
                    "xml": n.xml_original,
                    "role": n.role,
                    "competencia": n.competencia,
                })
            
            if not xmls:
                batch_status[batch_id][cid]["status"] = "success"
                batch_status[batch_id][cid]["mensagem"] = "Nenhuma nota para atualizar"
                return (company_id, None, None, cnpj, nome, id_dominio, [])
            
            batch_status[batch_id][cid]["mensagem"] = f"Re-extraindo {len(xmls)} notas..."
            return (company_id, None, None, cnpj, nome, id_dominio, xmls)

        result = await fetch_distribuicao(
            company_id=company_id,
            ult_nsu=0,
            ambiente="producao",
        )

        xmls = result.get("xmls", [])

        if datainicio or datafim:
            xmls_filtrados = []
            for x in xmls:
                campos = extrair_campos_nfse(x["xml"])
                if _periodo_valido(campos.get("competencia"), datainicio, datafim):
                    xmls_filtrados.append(x)
            xmls = xmls_filtrados

        cid = str(company_id)

        if result["error"]:
            batch_status[batch_id]["companies"][cid]["status"] = "failed"
            batch_status[batch_id]["companies"][cid]["error"] = result["error"]
            batch_status[batch_id]["companies"][cid]["mensagem"] = f"Erro: {result['error']}"
            return (company_id, None, result["error"], cnpj, nome, id_dominio, xmls)
        elif xmls:
            batch_status[batch_id]["companies"][cid]["status"] = "success"
            return (company_id, None, None, cnpj, nome, id_dominio, xmls)
        else:
            batch_status[batch_id]["companies"][cid]["status"] = "success"
            batch_status[batch_id]["companies"][cid]["notas_done"] = 0
            batch_status[batch_id]["companies"][cid]["mensagem"] = "Nenhuma nota encontrada"
            return (company_id, None, None, cnpj, nome, id_dominio, [])

    except Exception as e:
        batch_status[batch_id]["companies"][cid]["mensagem"] = f"Erro: {str(e)}"
        return (company_id, None, str(e), "", "", 0, [])
    finally:
        db.close()


def _role_to_folder(role: str) -> str:
    """Mapeia role para nome da pasta principal."""
    mapping = {
        "prestado": "Prestados",
        "tomado": "Tomados",
        "intermediario": "Intermediarios",
        "autor_evento": "AutorEvento",
        "desconhecido": "Desconhecidos",
    }
    return mapping.get(role.lower(), "Outros")


def _organizar_xmls_por_competencia_role(xmls: list) -> dict:
    """Organiza XMLs na estrutura: {ano: {mes: {role: [xml_data]}}}"""
    organizados = {}
    for xml in xmls:
        tipo = xml.get("tipo", "DESCONHECIDO")
        role = xml.get("role", "desconhecido")
        comp = xml.get("competencia", "0000-00")

        pasta_role = _role_to_folder(role)

        try:
            ano, mes = comp.split("-")
        except:
            ano, mes = "0000", "00"

        if ano not in organizados:
            organizados[ano] = {}
        if mes not in organizados[ano]:
            organizados[ano][mes] = {}
        if pasta_role not in organizados[ano][mes]:
            organizados[ano][mes][pasta_role] = []
        organizados[ano][mes][pasta_role].append(xml)
    return organizados


def _get_empresa_folder_name(id_dominio: int, nome: str) -> str:
    """Gera nome da pasta da empresa: <Código da Dominio>-<Empresa>"""
    return f"{id_dominio}-{nome}"


def _marcar_notas_canceladas(db: Session, empresa_id: int, eventos: list[dict]) -> int:
    """Marca a NFS-e original como cancelada para cada evento coletado neste lote.

    O evento referencia a nota pela mesma chave (chNFSe == chave_acesso da nota).
    Não cria documento nem nota: apenas atualiza situacao/observacao no DocumentoFiscal
    e tipo_evento/descricao_evento/data_evento no nfse.
    """
    marcados = 0
    for ev in eventos:
        chave_ref = ev.get("chave_ref")
        tipo_evento = ev.get("tipo_evento")
        if not chave_ref or not tipo_evento:
            continue
        if situacao_para_evento(tipo_evento) == "normal":
            continue
        descricao = ev.get("descricao")
        data_evento = ev.get("data_evento")
        doc = db.execute(
            select(DocumentoFiscal).where(
                DocumentoFiscal.empresa_id == empresa_id,
                DocumentoFiscal.chave_acesso == chave_ref,
                DocumentoFiscal.ativo == True,
            )
        ).scalars().first()
        if not doc:
            print(f"[ADN] Evento {tipo_evento} sem nota original para a chave {chave_ref} (empresa {empresa_id})")
            continue
        doc.situacao = situacao_para_evento(tipo_evento)
        doc.observacao = descricao
        nfse_row = db.execute(
            select(Nfse).where(Nfse.documento_fiscal_id == doc.id)
        ).scalars().first()
        if nfse_row:
            nfse_row.tipo_evento = tipo_evento
            nfse_row.descricao_evento = descricao
            nfse_row.data_evento = data_evento
        marcados += 1
    db.commit()
    return marcados


def _parse_data_evento(valor) -> "datetime | None":
    """Converte dhEvento/dhRegEvento (ISO) para datetime. Retorna None se inválido/ausente."""
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except Exception:
        return None


def _reconciliar_eventos_cancelamento(db: Session, empresa_id: int) -> int:
    """Marca a nota original como cancelada para cada EVENTO conhecido no banco.

    Um evento referencia a NFSe cancelada via <chNFSe>. Este passo:
    1. Re-extrai metadados de EVENTOS antigos salvos antes das correções (que ficaram
       sem tipo_evento/chNFSe), usando o xml_original;
    2. Atualiza o próprio documento do EVENTO (situacao 'cancelada');
    3. Atualiza a nota original referenciada (situacao/observacao no DocumentoFiscal e
       tipo_evento/descricao_evento/data_evento no nfse), para que os relatórios a contem
       como cancelada.

    Retorna o número de notas originais marcadas.
    """
    eventos = db.execute(
        select(Nfse.id, Nfse.tipo_evento, Nfse.descricao_evento, Nfse.data_evento,
               Nfse.chave_nfe_referenciada, Nfse.xml_original)
        .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
        .where(
            DocumentoFiscal.empresa_id == empresa_id,
            Nfse.tipo_documento_api == "EVENTO",
        )
    ).all()
    if not eventos:
        return 0

    marcados = 0
    for ev in eventos:
        chave_ref = ev.chave_nfe_referenciada
        tipo_evento = ev.tipo_evento
        descricao = ev.descricao_evento
        data_evento = ev.data_evento

        # Re-extrair do XML eventos salvos antes das correções (sem metadados persistidos)
        if (not tipo_evento or not chave_ref) and ev.xml_original:
            info = parse_xml_role_and_competence(ev.xml_original, "")
            tipo_evento = tipo_evento or info.get("evento_tipo")
            descricao = descricao or info.get("evento_descricao")
            chave_ref = chave_ref or info.get("chave_referenciada")
            data_evento = data_evento or _parse_data_evento(info.get("data_evento"))
            if tipo_evento:
                situacao_evento = situacao_para_evento(tipo_evento)
                db.execute(
                    update(Nfse).where(Nfse.id == ev.id).values(
                        tipo_evento=tipo_evento,
                        descricao_evento=descricao,
                        data_evento=data_evento,
                        chave_nfe_referenciada=chave_ref,
                    )
                )
                doc_evento_id = db.execute(
                    select(Nfse.documento_fiscal_id).where(Nfse.id == ev.id)
                ).scalar_one_or_none()
                if doc_evento_id:
                    db.execute(
                        update(DocumentoFiscal)
                        .where(DocumentoFiscal.id == doc_evento_id)
                        .values(situacao=situacao_evento, observacao=descricao)
                    )

        if not chave_ref or not tipo_evento:
            continue
        if situacao_para_evento(tipo_evento) == "normal":
            continue

        doc = db.execute(
            select(DocumentoFiscal).where(
                DocumentoFiscal.empresa_id == empresa_id,
                DocumentoFiscal.chave_acesso == chave_ref,
                DocumentoFiscal.ativo == True,
            )
        ).scalars().first()
        if not doc:
            continue
        doc.situacao = situacao_para_evento(tipo_evento)
        if descricao:
            doc.observacao = descricao
        nfse_row = db.execute(
            select(Nfse).where(Nfse.documento_fiscal_id == doc.id)
        ).scalars().first()
        if nfse_row:
            nfse_row.tipo_evento = tipo_evento
            nfse_row.descricao_evento = descricao
            nfse_row.data_evento = data_evento
        marcados += 1

    db.commit()
    return marcados


def _salvar_notas_empresa(db: Session, empresa_id: int, xmls: list, force_update: bool = False, batch_status: dict = None, batch_id: str = None) -> int:
    """Salva XMLs de uma empresa no banco com UPSERT + delta detection.
    
    Estratégia:
    - Calcula hash do XML para detectar mudanças
    - Usa UPSERT (ON CONFLICT) para insert/update atômico
    - Processa em lotes para não travar o banco
    - force_update=True re-processa tudo (útil para correção de bugs)
    """
    from app.models.documento_fiscal import DocumentoFiscal, TipoDocumento
    from app.models.nfse import Nfse
    from sqlalchemy import update
    import hashlib

    # A ADN dá ao evento de cancelamento a MESMA chave da NFS-e (chNFSe == chave_acesso).
    # Eventos NÃO são notas: devem sair do upsert e apenas marcar a nota original como cancelada.
    # Enquanto os eventos compartilham a chave da nota, um upsert com ambos colidiria no mesmo
    # (empresa_id, chave_acesso, tipo_documento) no mesmo comando (CardinalityViolation).
    eventos_coletados: list[dict] = []
    xmls_unicos: list[dict] = []
    vistos: set[str] = set()
    for x in xmls:
        evento_tipo = x.get("evento_tipo")
        if evento_tipo:
            eventos_coletados.append({
                "chave_ref": x.get("chave_referenciada"),
                "tipo_evento": evento_tipo,
                "descricao": x.get("evento_descricao"),
                "data_evento": _parse_data_evento(x.get("data_evento")),
            })
            continue
        chave = x.get("chave") or x.get("chave_acesso")
        if chave and chave in vistos:
            print(f"[ADN] XML duplicado da chave {chave} (NSU {x.get('nsu')}) — ignorado")
            continue
        if chave:
            vistos.add(chave)
        xmls_unicos.append(x)
    xmls = xmls_unicos

    def _atualiza_msg(msg: str):
        if batch_status and batch_id and batch_id in batch_status:
            cid = str(empresa_id)
            if cid in batch_status[batch_id].get("companies", {}):
                batch_status[batch_id]["companies"][cid]["mensagem"] = msg

    def _xml_hash(xml_str: str) -> str:
        """Calcula SHA256 do XML normalizado (sem espaços extras)."""
        normalized = ' '.join(xml_str.split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]

    # Buscar chaves existentes + hash atual no banco (uma query só), escopada à empresa.
    # A mesma nota (mesma chave) pode ser distribuída a várias empresas tomadoras:
    # cada empresa precisa do seu próprio registro nfse apontando para o seu documento.
    _atualiza_msg("Verificando notas existentes...")
    chaves_xml = [x.get("chave") or x.get("chave_acesso") for x in xmls if x.get("chave") or x.get("chave_acesso")]
    existentes = db.execute(
        select(Nfse.chave_acesso, Nfse.xml_hash)
        .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
        .where(
            DocumentoFiscal.empresa_id == empresa_id,
            Nfse.chave_acesso.in_(chaves_xml),
        )
    ).all()
    
    # Mapa: chave -> hash_atual_no_banco
    hash_no_banco = {chave: xml_hash for chave, xml_hash in existentes}
    
    # Preparar dados para UPSERT em lote
    doc_dicts: list[dict] = []
    nfse_dicts: list[dict] = []
    salvos = 0
    atualizados = 0
    ignorados = 0
    
    BATCH_SIZE = 100  # Processa em lotes de 100
    
    for i in range(0, len(xmls), BATCH_SIZE):
        lote = xmls[i:i + BATCH_SIZE]
        _atualiza_msg(f"Processando lote {i//BATCH_SIZE + 1}/{(len(xmls)-1)//BATCH_SIZE + 1}...")
        
        lote_doc_dicts = []
        lote_nfse_dicts = []
        
        for xml_data in lote:
            campos = extrair_campos_nfse(xml_data["xml"])
            chave = campos.get("chave_acesso") or xml_data.get("chave")

            evento_tipo = xml_data.get("evento_tipo")
            evento_descricao = xml_data.get("evento_descricao")

            if not chave:
                print(f"[ADN] XML sem chave de acesso (NSU {xml_data.get('nsu')}, tipo {xml_data.get('tipo')}) — ignorado")
                continue

            # Calcular hash do XML novo
            xml_str = xml_data["xml"]
            xml_hash = _xml_hash(xml_str)

            # Verificar se precisa atualizar
            hash_antigo = hash_no_banco.get(chave)

            if hash_antigo == xml_hash and not force_update:
                # XML idêntico ao salvo - pular
                ignorados += 1
                continue

            # Precisa inserir ou atualizar
            periodo = campos.get("competencia") or xml_data.get("competencia") or "0000-00"
            valor_servico = campos.get("valor_servico")

            if evento_tipo:
                situacao = situacao_para_evento(evento_tipo)
                observacao = evento_descricao
            else:
                situacao = campos.get("tipo_evento") or "normal"
                observacao = campos.get("descricao_evento")

            lote_doc_dicts.append({
                "empresa_id": empresa_id,
                "tipo_documento": TipoDocumento.NFSE,
                "periodo": periodo,
                "chave_acesso": chave,
                "numero_documento": campos.get("numero_nfse"),
                "valor_total": valor_servico,
                "situacao": situacao,
                "observacao": observacao,
                "arquivo_fonte": campos.get("arquivo_fonte"),
                "data_emissao": campos.get("data_emissao"),
                "ativo": True,
            })

            data_evento = _parse_data_evento(xml_data.get("data_evento"))

            nfse_data = {
                "chave_acesso": chave,
                "nsu": xml_data.get("nsu"),
                "tipo_documento_api": xml_data.get("tipo"),
                "role": xml_data.get("role"),
                "competencia": periodo,
                "xml_original": xml_str,
                "xml_hash": xml_hash,  # NOVO: armazenar hash para delta detection
                "tipo_evento": evento_tipo or campos.get("tipo_evento"),
                "descricao_evento": evento_descricao or campos.get("descricao_evento"),
                "data_evento": data_evento or campos.get("data_evento"),
                "chave_nfe_referenciada": xml_data.get("chave_referenciada") or campos.get("chave_nfe_referenciada"),
            }
            for campo in [
                "identificador_nfse", "numero_nfse", "codigo_verificacao", "versao_leiaute",
                "data_emissao", "municipio_emissor_codigo", "municipio_emissor_descricao",
                "cnpj_prestador", "cpf_prestador", "razao_social_prestador",
                "inscricao_municipal_prestador", "caepf_prestador", "nif_prestador", "cnao_nif_prestador",
                "cnpj_tomador", "cpf_tomador", "razao_social_tomador",
                "inscricao_municipal_tomador", "caepf_tomador", "nif_tomador", "cnao_nif_tomador",
                "codigo_servico", "descricao_servico", "informacoes_complementares", "numero_pedido",
                "valor_servico", "valor_recebido", "valor_desconto_condicionado",
                "valor_desconto_incondicionado", "valor_liquido", "base_calculo_iss",
                "aliquota_iss", "valor_iss", "iss_retido", "valor_iss_retido",
                "valor_retido_cp", "valor_retido_irrf", "valor_retido_csll",
                "valor_retido_pis", "valor_retido_cofins",
                "chave_nfe_referenciada", "tipo_evento", "descricao_evento", "data_evento",
                "arquivo_fonte",
            ]:
                if campo in campos:
                    nfse_data[campo] = campos[campo]

            lote_nfse_dicts.append(nfse_data)

            if hash_antigo is None:
                salvos += 1
            else:
                atualizados += 1
        
        # UPSERT do lote
        if lote_doc_dicts:
            # 1. UPSERT DocumentoFiscal
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            
            stmt = pg_insert(DocumentoFiscal).values(lote_doc_dicts)
            stmt = stmt.on_conflict_do_update(
                index_elements=["empresa_id", "chave_acesso", "tipo_documento"],
                set_={
                    "periodo": stmt.excluded.periodo,
                    "numero_documento": stmt.excluded.numero_documento,
                    "valor_total": stmt.excluded.valor_total,
                    "situacao": stmt.excluded.situacao,
                    "observacao": stmt.excluded.observacao,
                    "arquivo_fonte": stmt.excluded.arquivo_fonte,
                    "data_emissao": stmt.excluded.data_emissao,
                    "ativo": stmt.excluded.ativo,
                }
            )
            result = db.execute(stmt.returning(DocumentoFiscal.id, DocumentoFiscal.chave_acesso))
            id_map = {chave: doc_id for doc_id, chave in result.fetchall()}
            
            # 2. UPSERT Nfse - usar SQL raw para evitar problemas com None
            for item in lote_nfse_dicts:
                item["documento_fiscal_id"] = id_map[item["chave_acesso"]]
            
            # Construir UPSERT raw para cada item
            for item in lote_nfse_dicts:
                chave = item["chave_acesso"]
                is_new = chave not in hash_no_banco
                
                if is_new:
                    # INSERT - incluir apenas campos não-None
                    fields = [k for k, v in item.items() if v is not None]
                    placeholders = ", ".join([f":{k}" for k in fields])
                    columns = ", ".join(fields)
                    sql = f"INSERT INTO nfse ({columns}) VALUES ({placeholders})"
                    params = {k: v for k, v in item.items() if v is not None}
                    db.execute(text(sql), params)
                else:
                    # UPDATE - apenas campos não-None
                    update_data = {k: v for k, v in item.items() if v is not None and k not in ("chave_acesso", "documento_fiscal_id")}
                    if update_data:
                        set_clause = ", ".join([f"{k} = :{k}" for k in update_data.keys()])
                        params = {**update_data, "chave_acesso": item["chave_acesso"]}
                        db.execute(text(f"UPDATE nfse SET {set_clause} WHERE chave_acesso = :chave_acesso"), params)
            
            db.commit()
    
    # Marcar as notas originais cujos eventos de cancelamento chegaram neste lote
    try:
        marcados = _marcar_notas_canceladas(db, empresa_id, eventos_coletados)
        if marcados:
            print(f"[ADN] {marcados} notas marcadas como canceladas (empresa {empresa_id})")
    except Exception as e:
        print(f"[ADN] Erro ao marcar notas canceladas (empresa {empresa_id}): {e}")

    # Reconciliar eventos de cancelamento com as notas originais desta empresa
    try:
        reconciliados = _reconciliar_eventos_cancelamento(db, empresa_id)
        if reconciliados:
            _atualiza_msg(f"{reconciliados} notas marcadas como canceladas")
    except Exception as e:
        print(f"[ADN] Erro ao reconciliar eventos de cancelamento (empresa {empresa_id}): {e}")

    _atualiza_msg(f"Concluído: {salvos} novas, {atualizados} atualizadas, {ignorados} inalteradas")
    return salvos + atualizados


def _notas_base_query():
    return (
        select(Nfse, DocumentoFiscal, Company)
        .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
        .join(Company, DocumentoFiscal.empresa_id == Company.id)
        .where(
            DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
            DocumentoFiscal.ativo == True,
        )
    )


def _notas_join_query():
    return (
        select(Nfse)
        .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
        .join(Company, DocumentoFiscal.empresa_id == Company.id)
        .where(
            DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
            DocumentoFiscal.ativo == True,
        )
    )


def _apply_nota_filters(
    query,
    empresa_id: Optional[int] = None,
    competencia_inicio: Optional[str] = None,
    competencia_fim: Optional[str] = None,
    role: Optional[str] = None,
    tipo_evento: Optional[str] = None,
    situacao: Optional[str] = None,
    iss_retido: Optional[str] = None,
    search: Optional[str] = None,
    valor_min: Optional[float] = None,
    valor_max: Optional[float] = None,
    so_canceladas: Optional[bool] = None,
    so_sem_xml: Optional[bool] = None,
    so_sem_competencia: Optional[bool] = None,
    iss_sem_aliquota: Optional[bool] = None,
):
    if empresa_id is not None:
        query = query.where(DocumentoFiscal.empresa_id == empresa_id)
    if competencia_inicio:
        query = query.where(Nfse.competencia >= competencia_inicio)
    if competencia_fim:
        query = query.where(Nfse.competencia <= competencia_fim)
    if role:
        query = query.where(func.lower(Nfse.role) == role.lower())
    if tipo_evento:
        query = query.where(Nfse.tipo_evento == tipo_evento)
    if situacao:
        query = query.where(DocumentoFiscal.situacao == situacao)
    if iss_retido is not None:
        query = query.where(Nfse.iss_retido == iss_retido)
    if so_canceladas:
        query = query.where(Nfse.tipo_evento.is_not(None))
    if so_sem_xml:
        query = query.where(or_(Nfse.xml_original.is_(None), Nfse.xml_original == ""))
    if so_sem_competencia:
        query = query.where(or_(Nfse.competencia.is_(None), Nfse.competencia == ""))
    if iss_sem_aliquota:
        query = query.where(and_(func.coalesce(Nfse.valor_iss, 0) > 0, func.coalesce(Nfse.aliquota_iss, 0) == 0))
    if valor_min is not None:
        query = query.where(Nfse.valor_servico >= valor_min)
    if valor_max is not None:
        query = query.where(Nfse.valor_servico <= valor_max)
    if search:
        s = search.strip()
        digits = "".join(ch for ch in s if ch.isdigit())
        conds = [
            Nfse.chave_acesso.ilike(f"%{s}%"),
            Nfse.numero_nfse.ilike(f"%{s}%"),
            Nfse.razao_social_prestador.ilike(f"%{s}%"),
            Nfse.razao_social_tomador.ilike(f"%{s}%"),
        ]
        if digits:
            conds += [
                Nfse.cnpj_prestador.ilike(f"%{digits}%"),
                Nfse.cnpj_tomador.ilike(f"%{digits}%"),
                Nfse.cpf_prestador.ilike(f"%{digits}%"),
                Nfse.cpf_tomador.ilike(f"%{digits}%"),
            ]
        query = query.where(or_(*conds))
    return query


def _nota_resumo_dict(n: Nfse, doc: DocumentoFiscal, emp: Company) -> dict:
    return {
        "id": n.id,
        "documento_fiscal_id": n.documento_fiscal_id,
        "empresa_id": doc.empresa_id,
        "empresa_nome": emp.nome if emp else None,
        "empresa_cnpj": emp.cnpj if emp else None,
        "competencia": n.competencia or doc.periodo,
        "data_emissao": n.data_emissao or doc.data_emissao,
        "numero_nfse": n.numero_nfse or doc.numero_documento,
        "chave_acesso": n.chave_acesso or doc.chave_acesso,
        "role": n.role,
        "tipo_documento_api": n.tipo_documento_api,
        "tipo_evento": n.tipo_evento,
        "situacao": doc.situacao,
        "cnpj_prestador": n.cnpj_prestador,
        "razao_social_prestador": n.razao_social_prestador,
        "cnpj_tomador": n.cnpj_tomador,
        "razao_social_tomador": n.razao_social_tomador,
        "codigo_servico": n.codigo_servico,
        "descricao_servico": n.descricao_servico,
        "valor_servico": n.valor_servico,
        "valor_liquido": n.valor_liquido,
        "base_calculo_iss": n.base_calculo_iss,
        "aliquota_iss": n.aliquota_iss,
        "valor_iss": n.valor_iss,
        "iss_retido": n.iss_retido,
        "valor_iss_retido": n.valor_iss_retido,
        "valor_total": doc.valor_total,
        "ativo": doc.ativo,
        "atualizado_em": n.atualizado_em,
    }


@router.get("/notas/dashboard/resumo", response_model=DashboardResumoOut)
async def notas_dashboard_resumo(
    empresa_id: Optional[int] = Query(None),
    competencia_inicio: Optional[str] = Query(None, description="Competência inicial YYYY-MM"),
    competencia_fim: Optional[str] = Query(None, description="Competência final YYYY-MM"),
    role: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    agg = _apply_nota_filters(
        select(
            func.count(Nfse.id).label("total_notas"),
            func.coalesce(func.sum(Nfse.valor_servico), 0).label("total_valor_servico"),
            func.coalesce(func.sum(Nfse.valor_iss), 0).label("total_iss"),
            # tpRetISSQN=2 (ISS retido pelo tomador). Não usamos valor_iss_retido:
            # o ADN jamais preenche vRetISSQN; a retenção, quando existe, é o vISSQN da própria nota.
            func.coalesce(func.sum(case((Nfse.iss_retido == "2", Nfse.valor_iss), else_=0)), 0).label("total_iss_retido"),
            func.coalesce(func.sum(case((func.lower(Nfse.role) == "prestado", Nfse.valor_servico), else_=0)), 0).label("total_valor_prestado"),
            func.coalesce(func.sum(case((func.lower(Nfse.role) == "tomado", Nfse.valor_servico), else_=0)), 0).label("total_valor_tomado"),
        )
        .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
        .join(Company, DocumentoFiscal.empresa_id == Company.id)
        .where(
            DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
            DocumentoFiscal.ativo == True,
        ),
        empresa_id=empresa_id,
        competencia_inicio=competencia_inicio,
        competencia_fim=competencia_fim,
        role=role,
    )
    row = db.execute(agg).first()

    def _count(extra=None, role_value: Optional[str] = None):
        q = _apply_nota_filters(
            select(func.count(Nfse.id))
            .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
            .join(Company, DocumentoFiscal.empresa_id == Company.id)
            .where(
                DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                DocumentoFiscal.ativo == True,
            ),
            empresa_id=empresa_id,
            competencia_inicio=competencia_inicio,
            competencia_fim=competencia_fim,
            role=role,
        )
        if role_value is not None:
            q = q.where(func.lower(Nfse.role) == role_value)
        if extra is not None:
            q = q.where(extra)
        return db.execute(q).scalar() or 0

    # Camada de verificação (cálculo automático, sem marcação manual)
    from datetime import datetime, timedelta, timezone

    ultima_sync = db.execute(
        select(func.max(DocumentoFiscal.data_extracao))
        .where(
            DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
            DocumentoFiscal.ativo == True,
        )
    ).scalar()
    novas_desde_ontem = db.execute(
        select(func.count(DocumentoFiscal.id))
        .where(
            DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
            DocumentoFiscal.ativo == True,
            DocumentoFiscal.data_extracao >= datetime.now(timezone.utc) - timedelta(days=1),
        )
    ).scalar() or 0
    saude = "ok" if (
        (_count(extra=or_(Nfse.xml_original.is_(None), Nfse.xml_original == "")) == 0)
        and (_count(extra=or_(Nfse.competencia.is_(None), Nfse.competencia == "")) == 0)
    ) else "atencao"

    return DashboardResumoOut(
        total_notas=row.total_notas or 0,
        total_valor_servico=float(row.total_valor_servico or 0),
        total_iss=float(row.total_iss or 0),
        total_iss_retido=float(row.total_iss_retido or 0),
        valor_prestado=float(row.total_valor_prestado or 0),
        valor_tomado=float(row.total_valor_tomado or 0),
        notas_prestadas=_count(role_value="prestado"),
        notas_tomadas=_count(role_value="tomado"),
        notas_outras=_count(extra=or_(Nfse.role.is_(None), func.lower(Nfse.role).notin_(["prestado", "tomado"]))),
        notas_canceladas=_count(extra=Nfse.tipo_evento.is_not(None)),
        empresas_com_notas=db.execute(
            _apply_nota_filters(
                select(func.count(func.distinct(DocumentoFiscal.empresa_id)))
                .select_from(Nfse)
                .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
                .join(Company, DocumentoFiscal.empresa_id == Company.id)
                .where(
                    DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                    DocumentoFiscal.ativo == True,
                ),
                empresa_id=empresa_id,
                competencia_inicio=competencia_inicio,
                competencia_fim=competencia_fim,
                role=role,
            )
        ).scalar() or 0,
        notas_sem_competencia=_count(extra=or_(Nfse.competencia.is_(None), Nfse.competencia == "")),
        notas_sem_xml=_count(extra=or_(Nfse.xml_original.is_(None), Nfse.xml_original == "")),
        ultima_sincronizacao=ultima_sync,
        notas_novas_desde_ontem=novas_desde_ontem,
        saude_conferencia=saude,
    )


@router.get("/notas/dashboard/series", response_model=List[DashboardSerieItem])
async def notas_dashboard_series(
    empresa_id: Optional[int] = Query(None),
    competencia_inicio: Optional[str] = Query(None),
    competencia_fim: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    totals = db.execute(
        _apply_nota_filters(
            select(
                Nfse.competencia.label("competencia"),
                func.count(Nfse.id).label("total_notas"),
                func.coalesce(func.sum(Nfse.valor_servico), 0).label("valor_servico"),
                func.coalesce(func.sum(Nfse.valor_iss), 0).label("valor_iss"),
            )
            .select_from(Nfse)
            .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
            .join(Company, DocumentoFiscal.empresa_id == Company.id)
            .where(
                DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                DocumentoFiscal.ativo == True,
            )
            .group_by(Nfse.competencia)
            .order_by(Nfse.competencia),
            empresa_id=empresa_id,
            competencia_inicio=competencia_inicio,
            competencia_fim=competencia_fim,
            role=role,
        )
    ).all()

    roles = db.execute(
        _apply_nota_filters(
            select(
                Nfse.competencia.label("competencia"),
                func.lower(Nfse.role).label("role"),
                func.count(Nfse.id).label("total"),
                func.coalesce(func.sum(Nfse.valor_servico), 0).label("valor"),
            )
            .select_from(Nfse)
            .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
            .join(Company, DocumentoFiscal.empresa_id == Company.id)
            .where(
                DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                DocumentoFiscal.ativo == True,
            )
            .group_by(Nfse.competencia, func.lower(Nfse.role)),
            empresa_id=empresa_id,
            competencia_inicio=competencia_inicio,
            competencia_fim=competencia_fim,
            role=role,
        )
    ).all()

    role_by_comp = {}
    valor_by_comp = {}
    for r in roles:
        role_by_comp.setdefault(r.competencia, {})[r.role] = r.total
        valor_by_comp.setdefault(r.competencia, {})[r.role] = float(r.valor or 0)

    return [
        DashboardSerieItem(
            competencia=r.competencia,
            total_notas=r.total_notas or 0,
            notas_prestadas=role_by_comp.get(r.competencia, {}).get("prestado", 0),
            notas_tomadas=role_by_comp.get(r.competencia, {}).get("tomado", 0),
            valor_servico=float(r.valor_servico or 0),
            valor_iss=float(r.valor_iss or 0),
            valor_prestado=valor_by_comp.get(r.competencia, {}).get("prestado", 0.0),
            valor_tomado=valor_by_comp.get(r.competencia, {}).get("tomado", 0.0),
        )
        for r in totals
    ]


@router.get("/notas/dashboard/empresas", response_model=List[DashboardEmpresaItem])
async def notas_dashboard_empresas(
    empresa_id: Optional[int] = Query(None),
    competencia_inicio: Optional[str] = Query(None),
    competencia_fim: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    rows = db.execute(
        _apply_nota_filters(
            select(
                Company.id.label("empresa_id"),
                Company.nome.label("nome"),
                Company.cnpj.label("cnpj"),
                func.count(Nfse.id).label("total_notas"),
                func.coalesce(func.sum(Nfse.valor_servico), 0).label("valor_servico"),
                func.coalesce(func.sum(Nfse.valor_iss), 0).label("valor_iss"),
                func.coalesce(func.sum(case((func.lower(Nfse.role) == "prestado", Nfse.valor_servico), else_=0)), 0).label("valor_prestado"),
                func.coalesce(func.sum(case((func.lower(Nfse.role) == "tomado", Nfse.valor_servico), else_=0)), 0).label("valor_tomado"),
            )
            .select_from(Nfse)
            .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
            .join(Company, DocumentoFiscal.empresa_id == Company.id)
            .where(
                DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                DocumentoFiscal.ativo == True,
            )
            .group_by(Company.id, Company.nome, Company.cnpj)
            .order_by(func.coalesce(func.sum(Nfse.valor_servico), 0).desc())
            .limit(limit),
            empresa_id=empresa_id,
            competencia_inicio=competencia_inicio,
            competencia_fim=competencia_fim,
            role=role,
        )
    ).all()

    return [
        DashboardEmpresaItem(
            empresa_id=r.empresa_id,
            nome=r.nome,
            cnpj=r.cnpj,
            total_notas=r.total_notas or 0,
            valor_servico=float(r.valor_servico or 0),
            valor_iss=float(r.valor_iss or 0),
            valor_prestado=float(r.valor_prestado or 0),
            valor_tomado=float(r.valor_tomado or 0),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Análise por empresa (endpoint único para a tela de estudo)
# ---------------------------------------------------------------------------


def _shift_ym(ym: str, delta: int) -> str:
    """Desloca YYYY-MM em delta meses (delta negativo = passado)."""
    ano, mes = int(ym[:4]), int(ym[5:7])
    total = ano * 12 + (mes - 1) + delta
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def _months_between(inicio: str, fim: str) -> List[str]:
    months: List[str] = []
    cur = inicio
    while cur <= fim:
        months.append(cur)
        cur = _shift_ym(cur, 1)
    return months


@router.get("/analise/empresa", response_model=AnaliseEmpresaOut)
async def analise_empresa(
    empresa_id: int = Query(..., description="ID da empresa a analisar"),
    role: Optional[str] = Query(None, pattern="^(prestado|tomado)$"),
    competencia_inicio: Optional[str] = Query(None, description="Competência inicial YYYY-MM"),
    competencia_fim: Optional[str] = Query(None, description="Competência final YYYY-MM"),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    empresa = db.execute(select(Company).where(Company.id == empresa_id)).scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    # Contrapartes da análise ABC: papel-aware (prestado → tomador; tomado → prestador).
    # Sob papel=Todos, conta uma par por (contraparte × papel).
    cliente_par_cnpj = case(
        (func.lower(Nfse.role) == "prestado", func.coalesce(Nfse.cnpj_tomador, Nfse.razao_social_tomador)),
        else_=func.coalesce(Nfse.cnpj_prestador, Nfse.razao_social_prestador),
    )
    cliente_par_nome = case(
        (func.lower(Nfse.role) == "prestado", Nfse.razao_social_tomador),
        else_=Nfse.razao_social_prestador,
    )
    cliente_key = func.coalesce(func.nullif(cliente_par_cnpj, ""), cliente_par_nome)

    def apply_filters(query):
        return _apply_nota_filters(
            query,
            empresa_id=empresa_id,
            competencia_inicio=competencia_inicio,
            competencia_fim=competencia_fim,
            role=role,
        )

    def base_join(query):
        return (
            query
            .select_from(Nfse)
            .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
            .join(Company, DocumentoFiscal.empresa_id == Company.id)
            .where(
                DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                DocumentoFiscal.ativo == True,
            )
        )

    def scalar(query):
        return db.execute(apply_filters(base_join(query))).scalar() or 0

    # ── 1) KPIs + únicos ───────────────────────────────────────────
    kpi_row = db.execute(
        apply_filters(
            base_join(
                select(
                    func.count(Nfse.id).label("total_notas"),
                    func.coalesce(func.sum(case((func.lower(Nfse.role) == "prestado", Nfse.valor_servico), else_=0)), 0).label("valor_prestado"),
                    func.coalesce(func.sum(case((func.lower(Nfse.role) == "tomado", Nfse.valor_servico), else_=0)), 0).label("valor_tomado"),
                    func.count(case((func.lower(Nfse.role) == "prestado", 1))).label("notas_prestadas"),
                    func.count(case((func.lower(Nfse.role) == "tomado", 1))).label("notas_tomadas"),
                    func.coalesce(func.sum(Nfse.valor_retido_cp), 0).label("valor_retido_cp"),
                    func.coalesce(func.sum(Nfse.valor_retido_irrf), 0).label("valor_retido_irrf"),
                    # Mesma regra do dashboard: valor_iss_retido vem de vISSQN das notas
                    # tpRetISSQN=2 (retenção pelo tomador); vRetISSQN chega zerado no XML.
                    func.coalesce(func.sum(case((Nfse.iss_retido == "2", Nfse.valor_iss), else_=0)), 0).label("valor_iss_retido"),
                    func.count(case((Nfse.iss_retido == "2", 1))).label("notas_iss_retido"),
                    func.count(
                        case((and_(func.coalesce(Nfse.valor_iss, 0) > 0, func.coalesce(Nfse.aliquota_iss, 0) == 0), 1))
                    ).label("iss_sem_aliquota"),
                )
            )
        )
    ).first()

    total_notas = kpi_row.total_notas or 0
    valor_prestado = float(kpi_row.valor_prestado or 0)
    valor_tomado = float(kpi_row.valor_tomado or 0)
    total_servicos = valor_prestado + valor_tomado
    ticket_medio = total_servicos / total_notas if total_notas else 0.0
    valor_retido_cp = float(kpi_row.valor_retido_cp or 0)
    valor_retido_irrf = float(kpi_row.valor_retido_irrf or 0)
    valor_iss_retido = float(kpi_row.valor_iss_retido or 0)
    notas_iss_retido = int(kpi_row.notas_iss_retido or 0)
    iss_sem_aliquota = int(kpi_row.iss_sem_aliquota or 0)
    pct_retido_cp_irrf = ((valor_retido_cp + valor_retido_irrf) / total_servicos * 100) if total_servicos else None

    def contar(extra=None):
        q = apply_filters(base_join(select(func.count(Nfse.id))))
        if extra is not None:
            q = q.where(extra)
        return db.execute(q).scalar() or 0

    canceladas = contar(Nfse.tipo_evento.is_not(None))
    sem_xml = contar(or_(Nfse.xml_original.is_(None), Nfse.xml_original == ""))
    sem_competencia = contar(or_(Nfse.competencia.is_(None), Nfse.competencia == ""))
    sem_papel = contar(or_(Nfse.role.is_(None), func.lower(Nfse.role).not_in(("prestado", "tomado"))))

    # Contrapartes únicas pelo mesmo papel das seções de ABC (modo "todas" = clientes)
    clientes_unicos = db.execute(
        _apply_nota_filters(
            base_join(
                select(
                    func.count(
                        func.distinct(func.concat_ws('|', cliente_key, func.lower(Nfse.role)))
                    )
                ).where(cliente_key.isnot(None))
            ),
            empresa_id=empresa_id,
            competencia_inicio=competencia_inicio,
            competencia_fim=competencia_fim,
            role=role,
        )
    ).scalar() or 0

    # ── 2) Variação vs período anterior igual ────────────────────────
    periodo_anterior = ""
    var_prestado = None
    var_tomado = None
    if competencia_inicio and competencia_fim:
        months = _months_between(competencia_inicio, competencia_fim)
        n = len(months)
        if n > 0:
            prev_fim = _shift_ym(competencia_inicio, -1)
            prev_ini = _shift_ym(prev_fim, -(n - 1))
            periodo_anterior = f"{prev_ini} a {prev_fim} (período anterior igual)"
            prev_row = db.execute(
                _apply_nota_filters(
                    base_join(
                        select(
                            func.coalesce(func.sum(case((func.lower(Nfse.role) == "prestado", Nfse.valor_servico), else_=0)), 0).label("valor_prestado"),
                            func.coalesce(func.sum(case((func.lower(Nfse.role) == "tomado", Nfse.valor_servico), else_=0)), 0).label("valor_tomado"),
                        )
                    ),
                    empresa_id=empresa_id,
                    competencia_inicio=prev_ini,
                    competencia_fim=prev_fim,
                    role=role,
                )
            ).first()
            prev_prest = float(prev_row.valor_prestado or 0) if prev_row else 0.0
            prev_tom = float(prev_row.valor_tomado or 0) if prev_row else 0.0
            var_prestado = (valor_prestado - prev_prest) / prev_prest if prev_prest > 0 else None
            var_tomado = (valor_tomado - prev_tom) / prev_tom if prev_tom > 0 else None
    else:
        # Sem janela explícita: compara últimos 12 meses de dados vs 12 anteriores (TTM)
        last = db.execute(
            apply_filters(base_join(select(func.max(Nfse.competencia))))
        ).scalar()
        if last:
            fim_ttm = last
            ini_ttm = _shift_ym(fim_ttm, -11)
            prev_fim = _shift_ym(ini_ttm, -1)
            prev_ini = _shift_ym(prev_fim, -11)
            periodo_anterior = f"últimos 12m vs 12m anteriores ({prev_ini} a {prev_fim})"
            curr_row = db.execute(
                _apply_nota_filters(
                    base_join(
                        select(
                            func.coalesce(func.sum(case((func.lower(Nfse.role) == "prestado", Nfse.valor_servico), else_=0)), 0).label("valor_prestado"),
                            func.coalesce(func.sum(case((func.lower(Nfse.role) == "tomado", Nfse.valor_servico), else_=0)), 0).label("valor_tomado"),
                        )
                    ),
                    empresa_id=empresa_id,
                    competencia_inicio=ini_ttm,
                    competencia_fim=fim_ttm,
                    role=role,
                )
            ).first()
            prev_row = db.execute(
                _apply_nota_filters(
                    base_join(
                        select(
                            func.coalesce(func.sum(case((func.lower(Nfse.role) == "prestado", Nfse.valor_servico), else_=0)), 0).label("valor_prestado"),
                            func.coalesce(func.sum(case((func.lower(Nfse.role) == "tomado", Nfse.valor_servico), else_=0)), 0).label("valor_tomado"),
                        )
                    ),
                    empresa_id=empresa_id,
                    competencia_inicio=prev_ini,
                    competencia_fim=prev_fim,
                    role=role,
                )
            ).first()
            curr_prest = float(curr_row.valor_prestado or 0) if curr_row else 0.0
            curr_tom = float(curr_row.valor_tomado or 0) if curr_row else 0.0
            prev_prest = float(prev_row.valor_prestado or 0) if prev_row else 0.0
            prev_tom = float(prev_row.valor_tomado or 0) if prev_row else 0.0
            var_prestado = (curr_prest - prev_prest) / prev_prest if prev_prest > 0 else None
            var_tomado = (curr_tom - prev_tom) / prev_tom if prev_tom > 0 else None

    # ── 3) Série mensal (mesma forma da dashboard de notas) ───────────
    totals = db.execute(
        apply_filters(
            base_join(
                select(
                    Nfse.competencia.label("competencia"),
                    func.count(Nfse.id).label("total_notas"),
                    func.coalesce(func.sum(Nfse.valor_servico), 0).label("valor_servico"),
                    func.coalesce(func.sum(Nfse.valor_iss), 0).label("valor_iss"),
                )
            )
            .group_by(Nfse.competencia)
            .order_by(Nfse.competencia)
        )
    ).all()

    roles = db.execute(
        apply_filters(
            base_join(
                select(
                    Nfse.competencia.label("competencia"),
                    func.lower(Nfse.role).label("role"),
                    func.count(Nfse.id).label("total"),
                    func.coalesce(func.sum(Nfse.valor_servico), 0).label("valor"),
                )
            )
            .group_by(Nfse.competencia, func.lower(Nfse.role))
        )
    ).all()

    role_by_comp: dict = {}
    valor_by_comp: dict = {}
    for r in roles:
        role_by_comp.setdefault(r.competencia, {})[r.role] = r.total
        valor_by_comp.setdefault(r.competencia, {})[r.role] = float(r.valor or 0)

    serie = [
        DashboardSerieItem(
            competencia=r.competencia,
            total_notas=r.total_notas or 0,
            notas_prestadas=role_by_comp.get(r.competencia, {}).get("prestado", 0),
            notas_tomadas=role_by_comp.get(r.competencia, {}).get("tomado", 0),
            valor_servico=float(r.valor_servico or 0),
            valor_iss=float(r.valor_iss or 0),
            valor_prestado=valor_by_comp.get(r.competencia, {}).get("prestado", 0.0),
            valor_tomado=valor_by_comp.get(r.competencia, {}).get("tomado", 0.0),
        )
        for r in totals
    ]

    # ── 4) Mix de atividades: grupo por código tributário (chave estável) ──
    total_valor = db.execute(
        apply_filters(base_join(select(func.coalesce(func.sum(Nfse.valor_servico), 0))))
    ).scalar() or 0

    def atividade_label(key, desc, trib):
        key = (key or "").strip()
        desc = (desc or "").strip()
        trib = (trib or "").strip()
        for sep in (" - Conforme Lei", ", Conforme Lei", " Conforme Lei"):
            idx = desc.find(sep)
            if idx > 0:
                desc = desc[:idx].rstrip(" -,")
                break
        if key.isdigit():
            return f"{key} — {trib}" if trib else (f"{key} — {desc[:60]}" if desc else key)
        return (desc or key or "Sem descrição")[:110]

    key_expr = func.coalesce(func.nullif(Nfse.codigo_servico, ""), func.nullif(Nfse.descricao_servico, ""))

    def base_actividadades():
        papel = func.lower(Nfse.role)
        return base_join(
            select(
                key_expr.label("atividade_key"),
                papel.label("papel"),
                func.max(func.nullif(Nfse.tributo_nacional, "")).label("tributo_nacional"),
                func.max(func.nullif(Nfse.descricao_servico, "")).label("descricao"),
                func.count(Nfse.id).label("notas"),
                func.count(case((papel == "prestado", 1))).label("notas_prestadas"),
                func.count(case((papel == "tomado", 1))).label("notas_tomadas"),
                func.coalesce(func.sum(Nfse.valor_servico), 0).label("valor"),
                func.coalesce(func.sum(case((papel == "prestado", Nfse.valor_servico), else_=0)), 0).label("valor_prestado"),
                func.coalesce(func.sum(case((papel == "tomado", Nfse.valor_servico), else_=0)), 0).label("valor_tomado"),
            ).where(key_expr.isnot(None), papel.in_(["prestado", "tomado"]))
        ).group_by("atividade_key", papel)

    mix_rows = db.execute(
        apply_filters(
            base_actividadades()
        )
        .order_by(func.sum(Nfse.valor_servico).desc())
        .limit(20 if not role else 10)
    ).all()

    valor_prestado_total = float(valor_prestado or 0)
    valor_tomado_total = float(valor_tomado or 0)
    mix = []
    for r in mix_rows:
        key = (r.atividade_key or "").strip()
        label = atividade_label(key, r.descricao, r.tributo_nacional)
        if not label:
            continue
        papel_row = (r.papel or "").strip()
        row_valor = float(r.valor or 0)
        papel_total = valor_prestado_total if papel_row == "prestado" else valor_tomado_total
        mix.append(
            AnaliseAtividadeItem(
                atividade=label,
                papel=papel_row or None,
                notas=r.notas or 0,
                valor=row_valor,
                pct=(row_valor / papel_total * 100) if papel_total else 0.0,
                notas_prestadas=r.notas_prestadas or 0,
                valor_prestado=float(r.valor_prestado or 0),
                notas_tomadas=r.notas_tomadas or 0,
                valor_tomado=float(r.valor_tomado or 0),
            )
        )

    atividade_dominante = mix[0].atividade if mix else None
    atividade_dominante_pct = mix[0].pct if mix else None

    # ── 5) Top contrapartes (ABC por R$), separado por papel ───────────
    cliente_rows = db.execute(
        _apply_nota_filters(
            base_join(
                select(
                    cliente_key.label("cnpj"),
                    func.max(cliente_par_nome).label("nome"),
                    func.lower(Nfse.role).label("papel"),
                    func.count(Nfse.id).label("notas"),
                    func.coalesce(func.sum(Nfse.valor_servico), 0).label("valor"),
                ).where(cliente_key.isnot(None))
            ),
            empresa_id=empresa_id,
            competencia_inicio=competencia_inicio,
            competencia_fim=competencia_fim,
            role=role,
        )
        .group_by(cliente_key, func.lower(Nfse.role))
        .order_by(func.sum(Nfse.valor_servico).desc())
    ).all()

    # Curva A: quantos clientes concentram os primeiros 80% do faturamento
    clientes_curva_a = 0
    _acum80 = 0.0
    total_val_80 = float(total_valor or 0)
    for r in cliente_rows:
        _acum80 += float(r.valor or 0)
        clientes_curva_a += 1
        if total_val_80 and _acum80 >= 0.8 * total_val_80:
            break
    clientes_curva_a_pct_base = (clientes_curva_a / len(cliente_rows) * 100) if cliente_rows else None

    acumulado = 0.0
    clientes: List[AnaliseClienteItem] = []
    for r in cliente_rows[:10]:
        valor = float(r.valor or 0)
        acumulado += valor
        clientes.append(
            AnaliseClienteItem(
                cliente=r.nome,
                cnpj=r.cnpj,
                papel=(r.papel or None),
                notas=r.notas or 0,
                valor=valor,
                pct=(valor / float(total_valor) * 100) if total_valor else 0.0,
                pct_acum=(acumulado / float(total_valor) * 100) if total_valor else 0.0,
            )
        )

    # Mesma lente, ordenada por VOLUME de notas (respostas idênticas na lente fornecedor)
    qtd_papel = sum(int(r.notas or 0) for r in cliente_rows)  # total de notas do papel atual
    qtd_rows = sorted(cliente_rows, key=lambda r: (r.notas or 0), reverse=True)[:10]
    acumulado_n = 0.0
    clientes_por_notas: List[AnaliseClienteItem] = []
    for r in qtd_rows:
        n = int(r.notas or 0)
        acumulado_n += n
        valor = float(r.valor or 0)
        clientes_por_notas.append(
            AnaliseClienteItem(
                cliente=r.nome,
                cnpj=r.cnpj,
                papel=(r.papel or None),
                notas=n,
                valor=valor,
                pct=(valor / float(total_valor) * 100) if total_valor else 0.0,
                pct_acum=0.0,
                pct_notas_acum=(acumulado_n / qtd_papel * 100) if qtd_papel else None,
            )
        )

    def build_matriz(papel: str, base_total: float, limite: int = 10) -> List[AnaliseMatrizItem]:
        if papel == "prestado":
            contra_cnpj, contra_nome = Nfse.cnpj_tomador, Nfse.razao_social_tomador
        else:
            contra_cnpj, contra_nome = Nfse.cnpj_prestador, Nfse.razao_social_prestador

        rows = db.execute(
            _apply_nota_filters(
                base_join(
                    select(
                        key_expr.label("atividade_key"),
                        func.max(func.nullif(Nfse.tributo_nacional, "")).label("tributo_nacional"),
                        func.max(func.nullif(Nfse.descricao_servico, "")).label("descricao"),
                        func.coalesce(func.nullif(contra_cnpj, ""), contra_nome).label("cnpj"),
                        func.max(contra_nome).label("nome"),
                        func.count(Nfse.id).label("notas"),
                        func.coalesce(func.sum(Nfse.valor_servico), 0).label("valor"),
                    )
                    .where(and_(func.coalesce(func.nullif(contra_cnpj, ""), contra_nome).isnot(None), key_expr.isnot(None)))
                ),
                empresa_id=empresa_id,
                competencia_inicio=competencia_inicio,
                competencia_fim=competencia_fim,
                role=papel,
            )
            .group_by("atividade_key", func.coalesce(func.nullif(contra_cnpj, ""), contra_nome))
            .order_by(func.sum(Nfse.valor_servico).desc())
            .limit(limite)
        ).all()

        items: List[AnaliseMatrizItem] = []
        for r in rows:
            key = (r.atividade_key or "").strip()
            label = atividade_label(key, r.descricao, r.tributo_nacional)
            if not label:
                continue
            valor = float(r.valor or 0)
            items.append(
                AnaliseMatrizItem(
                    atividade=label,
                    cliente=r.nome,
                    cnpj=r.cnpj,
                    papel=papel,
                    notas=r.notas or 0,
                    valor=valor,
                    pct=(valor / base_total * 100) if base_total else 0.0,
                )
            )
        return items

    matriz_prestadas = build_matriz("prestado", float(valor_prestado or 0))
    matriz_tomadas = build_matriz("tomado", float(valor_tomado or 0))

    return AnaliseEmpresaOut(
        empresa_nome=empresa.nome,
        empresa_cnpj=empresa.cnpj,
        role=role,
        competencia_inicio=competencia_inicio,
        competencia_fim=competencia_fim,
        periodo_anterior=periodo_anterior,
        total_notas=total_notas,
        notas_prestadas=kpi_row.notas_prestadas or 0,
        notas_tomadas=kpi_row.notas_tomadas or 0,
        valor_prestado=valor_prestado,
        valor_tomado=valor_tomado,
        clientes_unicos=clientes_unicos,
        ticket_medio=ticket_medio,
        var_prestado_anterior=var_prestado,
        var_tomado_anterior=var_tomado,
        canceladas=canceladas,
        sem_xml=sem_xml,
        sem_competencia=sem_competencia,
        sem_papel=sem_papel,
        valor_retido_cp=valor_retido_cp,
        valor_retido_irrf=valor_retido_irrf,
        pct_retido_cp_irrf=pct_retido_cp_irrf,
        valor_iss_retido=valor_iss_retido,
        notas_iss_retido=notas_iss_retido,
        iss_sem_aliquota=iss_sem_aliquota,
        clientes_curva_a=clientes_curva_a,
        clientes_curva_a_pct_base=clientes_curva_a_pct_base,
        atividade_dominante=atividade_dominante,
        atividade_dominante_pct=atividade_dominante_pct,
        serie=serie,
        mix=mix,
        clientes=clientes,
        clientes_por_notas=clientes_por_notas,
        matriz_prestadas=matriz_prestadas,
        matriz_tomadas=matriz_tomadas,
    )


@router.get("/notas", response_model=PaginatedResponse[NotaResumoOut])
async def list_notas(
    empresa_id: Optional[int] = Query(None),
    competencia_inicio: Optional[str] = Query(None),
    competencia_fim: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    tipo_evento: Optional[str] = Query(None),
    situacao: Optional[str] = Query(None),
    iss_retido: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    valor_min: Optional[float] = Query(None),
    valor_max: Optional[float] = Query(None),
    so_canceladas: bool = Query(False),
    so_sem_xml: bool = Query(False),
    so_sem_competencia: bool = Query(False),
    iss_sem_aliquota: bool = Query(False),
    sort: str = Query("competencia"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    base = _apply_nota_filters(
        _notas_base_query(),
        empresa_id=empresa_id,
        competencia_inicio=competencia_inicio,
        competencia_fim=competencia_fim,
        role=role,
        tipo_evento=tipo_evento,
        situacao=situacao,
        iss_retido=iss_retido,
        search=search,
        valor_min=valor_min,
        valor_max=valor_max,
        so_canceladas=so_canceladas,
        so_sem_xml=so_sem_xml,
        so_sem_competencia=so_sem_competencia,
        iss_sem_aliquota=iss_sem_aliquota,
    )
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar() or 0

    sort_map = {
        "competencia": Nfse.competencia,
        "data_emissao": Nfse.data_emissao,
        "valor_servico": Nfse.valor_servico,
        "valor_iss": Nfse.valor_iss,
        "atualizado_em": Nfse.atualizado_em,
        "numero_nfse": Nfse.numero_nfse,
        "empresa": Company.nome,
        "role": Nfse.role,
    }
    sort_col = sort_map.get(sort, Nfse.competencia)
    order_col = sort_col.asc().nullslast() if order.lower() == "asc" else sort_col.desc().nullslast()
    offset = (page - 1) * page_size
    rows = db.execute(base.order_by(order_col, Nfse.id.desc()).offset(offset).limit(page_size)).all()
    items = [_nota_resumo_dict(n, doc, emp) for n, doc, emp in rows]
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse[NotaResumoOut](items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get("/notas/{nota_id}", response_model=NotaDetalheOut)
async def get_nota(nota_id: int, db: Session = Depends(get_db), api_key: str = Depends(api_key_dep)):
    row = db.execute(
        _notas_base_query().where(Nfse.id == nota_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Nota não encontrada")
    n, doc, emp = row
    data = NfseOut.model_validate(n).model_dump()
    data.update(
        {
            "empresa_id": doc.empresa_id,
            "empresa_nome": emp.nome if emp else None,
            "empresa_cnpj": emp.cnpj if emp else None,
            "situacao": doc.situacao,
            "valor_total": doc.valor_total,
            "tem_xml": bool(n.xml_original),
            "xml_original": None,
        }
    )
    return NotaDetalheOut(**data)


@router.get("/notas/{nota_id}/xml")
async def get_nota_xml(nota_id: int, db: Session = Depends(get_db), api_key: str = Depends(api_key_dep)):
    n = db.execute(select(Nfse).where(Nfse.id == nota_id)).scalar_one_or_none()
    if not n or not n.xml_original:
        raise HTTPException(status_code=404, detail="XML não encontrado")
    filename = f"NFSe_{n.chave_acesso or n.numero_nfse or nota_id}.xml"
    return Response(
        content=n.xml_original,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/notas/{nota_id}/danfse")
async def get_nota_danfse(nota_id: int, db: Session = Depends(get_db), api_key: str = Depends(api_key_dep)):
    n = db.execute(select(Nfse).where(Nfse.id == nota_id)).scalar_one_or_none()
    if not n or not n.xml_original:
        raise HTTPException(status_code=404, detail="XML não encontrado")
    doc = db.execute(select(DocumentoFiscal).where(DocumentoFiscal.id == n.documento_fiscal_id)).scalar_one_or_none()
    situacao = (doc.situacao if doc else "normal") or "normal"
    # tpRetISSQN/eventos espelhados no doc.situacao: cancelada→2, substituida→1, válida→0
    stc = 2 if situacao == "cancelada" else (1 if situacao == "substituida" else 0)
    try:
        pdf = await gerar_danfse(n.xml_original, stc=stc)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    filename = f"DANFSe_{n.chave_acesso or n.numero_nfse or nota_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/relatorio/xlsx")
async def download_relatorio_nfse_xlsx(
    periodo: Optional[str] = Query(None, description="Competência exata no formato YYYY-MM (opcional se datainicio/datafim informados)"),
    datainicio: Optional[str] = Query(None, description="Data inicial DD/MM/YYYY (filtro por competência, inclusivo)"),
    datafim: Optional[str] = Query(None, description="Data final DD/MM/YYYY (filtro por competência, inclusivo)"),
    company_ids: Optional[str] = Query(None, description="IDs das empresas separados por vírgula (opcional)"),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    """Gera planilha XLSX com notas fiscais baixadas (NFSe).

    Filtro por competência (dCompet extraído do XML), nunca por data de emissão.
    - Se `periodo` informado: competência exata.
    - Se `datainicio`/`datafim` informados (DD/MM/YYYY): filtro por range de competência (mesma regra do batch/ZIP).
    - Caso contrário: 422 (informe ao menos um dos dois).

    Aba 1 - RESUMO: Totais por empresa + totais por tipo (Prestado/Tomado/Cancelado) + valores
    Aba 2 - DETALHAMENTO: Todas as notas com detalhes completos
    """
    if not periodo and not datainicio and not datafim:
        raise HTTPException(status_code=422, detail="Informe 'periodo' (YYYY-MM) ou 'datainicio'/'datafim' (DD/MM/YYYY)")

    periodo_inicio = _para_ym(datainicio) if datainicio else periodo
    periodo_fim = _para_ym(datafim) if datafim else periodo

    if periodo_inicio and periodo_fim and periodo_inicio != periodo_fim:
        periodo_label = f"{periodo_inicio} a {periodo_fim}"
    else:
        periodo_label = periodo_inicio or periodo_fim or ""

    # Parse company_ids se fornecido
    company_id_list = None
    if company_ids:
        try:
            company_id_list = [int(x.strip()) for x in company_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="company_ids deve ser lista de inteiros separados por vírgula")

    # Buscar empresas
    empresas_query = select(Company).order_by(Company.id)
    if company_id_list:
        empresas_query = empresas_query.where(Company.id.in_(company_id_list))
    empresas_db = db.execute(empresas_query).scalars().all()

    if not empresas_db:
        raise HTTPException(status_code=404, detail="Nenhuma empresa encontrada")

    empresas_data = []
    for emp in empresas_db:
        # Buscar notas da competência para esta empresa
        notas_query = (
            select(Nfse)
            .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
            .where(
                DocumentoFiscal.empresa_id == emp.id,
                DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                DocumentoFiscal.ativo == True,
            )
            .order_by(Nfse.data_emissao)
        )
        if periodo_inicio:
            notas_query = notas_query.where(Nfse.competencia >= periodo_inicio)
        if periodo_fim:
            notas_query = notas_query.where(Nfse.competencia <= periodo_fim)
        notas_db = db.execute(notas_query).scalars().all()

        # Calcular totais por role (eventos de cancelamento não são notas — apenas marcam a nota original)
        notas_prestado = 0
        notas_tomado = 0
        notas_cancelado = 0
        valor_servico_total = 0.0
        valor_iss_total = 0.0

        notas_list = []
        for n in notas_db:
            if (n.tipo_documento_api or "").upper() == "EVENTO":
                # Evento de cancelamento não entra nos totais nem no DETALHAMENTO
                continue
            role = (n.role or "").lower()
            evento_cancelamento = bool(n.tipo_evento) and n.tipo_evento in EVENTO_CANCELAMENTO
            evento_cancelamento = evento_cancelamento or (bool(n.tipo_evento) and situacao_para_evento(n.tipo_evento) == "cancelada")
            if evento_cancelamento:
                notas_cancelado += 1
            elif role == "tomado":
                notas_tomado += 1
            elif role == "prestado":
                notas_prestado += 1
            else:
                # Se não tem role nem tipo_evento, assume prestado
                notas_prestado += 1

            vs = float(n.valor_servico or 0)
            if vs == 0:
                vs = float(n.valor_liquido_calculado or 0)
            valor_servico_total += vs
            valor_iss_total += float(n.valor_iss or 0)

            notas_list.append({
                "chave_acesso": n.chave_acesso,
                "numero_nfse": n.numero_nfse,
                "competencia": n.competencia,
                "data_emissao": n.data_emissao.strftime("%d/%m/%Y") if n.data_emissao else "-",
                "role": n.role,
                "cnpj_prestador": n.cnpj_prestador,
                "razao_social_prestador": n.razao_social_prestador,
                "cnpj_tomador": n.cnpj_tomador,
                "razao_social_tomador": n.razao_social_tomador,
                "codigo_servico": n.codigo_servico,
                "descricao_servico": n.descricao_servico,
                "valor_servico": vs,
                "base_calculo_iss": float(n.base_calculo_iss or 0),
                "aliquota_iss": float(n.aliquota_iss or 0),
                "valor_iss": float(n.valor_iss or 0),
                "valor_desconto_condicionado": float(n.valor_desconto_condicionado or 0),
                "valor_desconto_incondicionado": float(n.valor_desconto_incondicionado or 0),
                "iss_retido": n.iss_retido,
                "tipo_evento": n.tipo_evento,
                "descricao_evento": n.descricao_evento,
                "situacao": "Cancelada" if evento_cancelamento else ("Evento" if n.tipo_evento else "Normal"),
            })

        total_notas = notas_prestado + notas_tomado + notas_cancelado

        empresas_data.append({
            "id": emp.id,
            "razao_social": emp.nome,
            "cnpj": emp.cnpj,
            "total_notas": total_notas,
            "notas_prestado": notas_prestado,
            "notas_tomado": notas_tomado,
            "notas_cancelado": notas_cancelado,
            "valor_servico_total": valor_servico_total,
            "valor_iss_total": valor_iss_total,
            "notas": notas_list,
        })

    xlsx_bytes = gerar_xlsx_nfse_download(periodo_label, empresas_data)

    filename = f"nfse_download_{periodo_label.replace('-', '').replace(' ', '')}.xlsx"
    return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@router.post("/batch-download", response_model=NFSEDownloadResponse)
async def start_batch_download(
    request: BatchDownloadRequest,
    background_tasks: BackgroundTasks,
    _api_key: str = Depends(verify_api_key),
):
    """Inicia download em lote de NFSe para múltiplas empresas."""
    batch_id = str(uuid.uuid4())

    # Inicializa status do batch
    batch_status[batch_id] = {
        "total": len(request.company_ids),
        "done": 0,
        "status": "queued",
        "datainicio": request.datainicio,
        "datafim": request.datafim,
        "download_type": request.download_type,
        "created_at": datetime.now().isoformat(),
        "companies": {},
    }

    for cid in request.company_ids:
        cid_str = str(cid)
        batch_status[batch_id]["companies"][cid_str] = {
            "status": "queued",
            "notas_done": 0,
            "notas_salvas": 0,
            "valorServico": 0,
            "valorIss": 0,
            "notasPrestadas": 0,
            "notasTomadas": 0,
            "notasCanceladas": 0,
            "notasOutros": 0,
            "valorPrestado": 0,
            "valorTomado": 0,
            "valorCancelado": 0,
            "valorOutros": 0,
            "notasPrestadasComRetencao": 0,
            "notasPrestadasSemRetencao": 0,
            "valorPrestadoComRetencao": 0.0,
            "valorPrestadoSemRetencao": 0.0,
            "carregando_notas": False,
            "cnpj": "",
            "nome": "",
            "empresa_id": cid,
            "mensagem": "",
        }

    # Adiciona task em background
    background_tasks.add_task(
        _process_batch_background,
        batch_id,
        request.company_ids,
        request.datainicio,
        request.datafim,
        request.download_type,
        request.force_update,
    )

    return NFSEDownloadResponse(batch_id=batch_id, status="queued")


async def _process_batch_background(
    batch_id: str,
    company_ids: List[int],
    datainicio: str | None,
    datafim: str | None,
    download_type: str,
    force_update: bool = False,
):
    """Processa o batch em background."""
    batch_status[batch_id]["status"] = "processing"

    # Pre-popula cnpj/nome para todas as empresas ANTES de processar
    db = SessionLocal()
    try:
        companies = db.execute(
            select(Company).where(Company.id.in_(company_ids))
        ).scalars().all()
        for company in companies:
            cid = str(company.id)
            batch_status[batch_id]["companies"][cid]["cnpj"] = company.cnpj
            batch_status[batch_id]["companies"][cid]["nome"] = company.nome
            batch_status[batch_id]["companies"][cid]["id_dominio"] = company.id_dominio or 0
    finally:
        db.close()

    for company_id in company_ids:
        cid = str(company_id)
        batch_status[batch_id]["companies"][cid]["status"] = "processing"
        batch_status[batch_id]["companies"][cid]["carregando_notas"] = True

        result = await _process_single_company_async(
            company_id=company_id,
            batch_id=batch_id,
            batch_status=batch_status,
            download_type=download_type,
            datainicio=datainicio,
            datafim=datafim,
            force_update=force_update,
        )

        company_id_res, _, error, cnpj, nome, id_dominio, xmls = result
        cid_res = str(company_id_res)

        batch_status[batch_id]["companies"][cid_res]["carregando_notas"] = False

        if error:
            batch_status[batch_id]["companies"][cid_res]["status"] = "failed"
            batch_status[batch_id]["companies"][cid_res]["error"] = error
        else:
            # Salva no banco
            db = SessionLocal()
            try:
                salvos = _salvar_notas_empresa(db, company_id_res, xmls, force_update, batch_status, batch_id)
                batch_status[batch_id]["companies"][cid_res]["notas_salvas"] = salvos
                batch_status[batch_id]["companies"][cid_res]["notas_done"] = len(xmls)
            
                # Calcula valores
                valor_servico = 0.0
                valor_iss = 0.0
                notas_prestadas = 0
                notas_tomadas = 0
                notas_canceladas = 0
                notas_outros = 0
                valor_prestado = 0.0
                valor_tomado = 0.0
                valor_cancelado = 0.0
                valor_outros = 0.0
                notas_prestadas_com_retencao = 0
                notas_prestadas_sem_retencao = 0
                valor_prestado_com_retencao = 0.0
                valor_prestado_sem_retencao = 0.0
            
                for xml_data in xmls:
                    tipo_api = (xml_data.get("tipo") or "").upper()
                    evento_tipo = xml_data.get("evento_tipo")

                    if tipo_api == "EVENTO":
                        # Evento de cancelamento não entra nos totais de notas
                        if evento_tipo and evento_tipo in EVENTO_CANCELAMENTO:
                            notas_canceladas += 1
                        continue

                    campos = extrair_campos_nfse(xml_data["xml"])
                    vs = float(campos.get("valor_servico") or 0)
                    if vs == 0:
                        vs = float(campos.get("valor_liquido_calculado") or 0)
                    valor_servico += vs
                    valor_iss += float(campos.get("valor_iss") or 0)
                
                    role = (xml_data.get("role") or "").lower()
                    evento_tipo = evento_tipo or campos.get("tipo_evento")
                    if evento_tipo in EVENTO_CANCELAMENTO:
                        notas_canceladas += 1
                        valor_cancelado += vs
                    elif role == "prestado":
                        notas_prestadas += 1
                        valor_prestado += vs
                        if (campos.get("iss_retido") or "") == "2":
                            notas_prestadas_com_retencao += 1
                            valor_prestado_com_retencao += vs
                        else:
                            notas_prestadas_sem_retencao += 1
                            valor_prestado_sem_retencao += vs
                    elif role == "tomado":
                        notas_tomadas += 1
                        valor_tomado += vs
                    else:
                        notas_outros += 1
                        valor_outros += vs
            
                batch_status[batch_id]["companies"][cid_res]["valorServico"] = valor_servico
                batch_status[batch_id]["companies"][cid_res]["valorIss"] = valor_iss
                batch_status[batch_id]["companies"][cid_res]["notasPrestadas"] = notas_prestadas
                batch_status[batch_id]["companies"][cid_res]["notasTomadas"] = notas_tomadas
                batch_status[batch_id]["companies"][cid_res]["notasCanceladas"] = notas_canceladas
                batch_status[batch_id]["companies"][cid_res]["notasOutros"] = notas_outros
                batch_status[batch_id]["companies"][cid_res]["valorPrestado"] = valor_prestado
                batch_status[batch_id]["companies"][cid_res]["valorTomado"] = valor_tomado
                batch_status[batch_id]["companies"][cid_res]["valorCancelado"] = valor_cancelado
                batch_status[batch_id]["companies"][cid_res]["valorOutros"] = valor_outros
                batch_status[batch_id]["companies"][cid_res]["notasPrestadasComRetencao"] = notas_prestadas_com_retencao
                batch_status[batch_id]["companies"][cid_res]["notasPrestadasSemRetencao"] = notas_prestadas_sem_retencao
                batch_status[batch_id]["companies"][cid_res]["valorPrestadoComRetencao"] = valor_prestado_com_retencao
                batch_status[batch_id]["companies"][cid_res]["valorPrestadoSemRetencao"] = valor_prestado_sem_retencao

                batch_status[batch_id]["companies"][cid_res]["status"] = "success"
                batch_status[batch_id]["companies"][cid_res]["mensagem"] = "Concluído com sucesso"
            except Exception as e:
                batch_status[batch_id]["companies"][cid_res]["status"] = "failed"
                batch_status[batch_id]["companies"][cid_res]["error"] = str(e)
                batch_status[batch_id]["companies"][cid_res]["mensagem"] = f"Erro: {str(e)}"
            finally:
                db.close()
    
        batch_status[batch_id]["done"] += 1

    # Gera ZIP com XMLs + XLSX
    _gerar_zip_batch(batch_id, datainicio, datafim)

    batch_status[batch_id]["status"] = "success"


def _gerar_zip_batch(batch_id: str, datainicio: str | None, datafim: str | None):
    """Gera arquivo ZIP com XMLs organizados + relatório XLSX."""
    import tempfile
    import zipfile

    if batch_id not in batch_status:
        return

    companies_data = batch_status[batch_id]["companies"]

    # Cria arquivo temporário para o ZIP
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"nfse_batch_{batch_id}.zip")

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Adiciona XMLs organizados por empresa/competência/role
        for company_id, company_info in companies_data.items():
            if company_info["status"] != "success":
                continue
        
            cnpj = company_info.get("cnpj", "")
            nome = company_info.get("nome", "")
            id_dominio = company_info.get("id_dominio", 0)
        
            # Busca XMLs salvos no banco para esta empresa
            db = SessionLocal()
            try:
                from app.models.documento_fiscal import DocumentoFiscal, TipoDocumento
                from app.models.nfse import Nfse
            
                notas_query = (
                    select(Nfse)
                    .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
                    .where(
                        DocumentoFiscal.empresa_id == company_id,
                        DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                        DocumentoFiscal.ativo == True,
                    )
                )
            
                # Filtro de período se fornecido
                if datainicio or datafim:
                    ini = _para_ym(datainicio)
                    fim = _para_ym(datafim)
                    if ini:
                        notas_query = notas_query.where(Nfse.competencia >= ini)
                    if fim:
                        notas_query = notas_query.where(Nfse.competencia <= fim)
            
                notas_db = db.execute(notas_query).scalars().all()
            
                # Organiza por competência e role
                organizados = _organizar_xmls_por_competencia_role([
                    {
                        "xml": n.xml_original,
                        "tipo": n.tipo_documento_api,
                        "role": n.role,
                        "competencia": n.competencia,
                    }
                    for n in notas_db
                ])
            
                empresa_folder = _get_empresa_folder_name(id_dominio, nome)

                for ano, meses in organizados.items():
                    for mes, roles in meses.items():
                        for role, xmls in roles.items():
                            for i, xml_data in enumerate(xmls):
                                xml_content = xml_data["xml"]
                                # Nova estrutura: <Role>/<Cod.> - <Apelido>/mmaaaa/
                                mmaaaa = f"{mes}{ano}"
                                filename = f"{role}/{empresa_folder}/{mmaaaa}/NFSe_{xml_data.get('chave', f'{ano}{mes}{i}')}.xml"
                                zipf.writestr(filename, xml_content)
            finally:
                db.close()
    
        # Gera e adiciona relatório XLSX
        try:
            # Prepara dados para o XLSX
            empresas_xlsx = []
            for company_id, company_info in companies_data.items():
                if company_info["status"] != "success":
                    continue
            
                db = SessionLocal()
                try:
                    from app.models.documento_fiscal import DocumentoFiscal, TipoDocumento
                    from app.models.nfse import Nfse
                
                    notas_query = (
                        select(Nfse)
                        .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
                        .where(
                            DocumentoFiscal.empresa_id == company_id,
                            DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                            DocumentoFiscal.ativo == True,
                        )
                    )
                    periodo_inicio = _para_ym(datainicio) if datainicio else None
                    periodo_fim = _para_ym(datafim) if datafim else None
                    
                    # CORRECAO: usar range periodo inicio a fim (nao so primeiro mes)
                    if periodo_inicio:
                        notas_query = notas_query.where(Nfse.competencia >= periodo_inicio)
                    if periodo_fim:
                        notas_query = notas_query.where(Nfse.competencia <= periodo_fim)
                
                    notas_db = db.execute(notas_query).scalars().all()
                
                
                    # Mesmo processamento do relatório:
                    # eventos de cancelamento não são notas — marcam a nota original
                    notas_prestado = 0
                    notas_tomado = 0
                    notas_cancelado = 0
                    valor_servico_total = 0.0
                    valor_iss_total = 0.0
                    notas_list = []
                
                    for n in notas_db:
                        if (n.tipo_documento_api or "").upper() == "EVENTO":
                            continue
                        role = (n.role or "").lower()
                        evento_cancelamento = bool(n.tipo_evento) and situacao_para_evento(n.tipo_evento) == "cancelada"
                        if evento_cancelamento:
                            notas_cancelado += 1
                        elif role == "tomado":
                            notas_tomado += 1
                        elif role == "prestado":
                            notas_prestado += 1
                        else:
                            notas_prestado += 1
                    
                        vs = float(n.valor_servico or 0)
                        if vs == 0:
                            vs = float(n.valor_liquido_calculado or 0)
                        valor_servico_total += vs
                        valor_iss_total += float(n.valor_iss or 0)
                    
                        notas_list.append({
                            "chave_acesso": n.chave_acesso,
                            "numero_nfse": n.numero_nfse,
                            "competencia": n.competencia,
                            "data_emissao": n.data_emissao.strftime("%d/%m/%Y") if n.data_emissao else "-",
                            "role": n.role,
                            "cnpj_prestador": n.cnpj_prestador,
                            "razao_social_prestador": n.razao_social_prestador,
                            "cnpj_tomador": n.cnpj_tomador,
                            "razao_social_tomador": n.razao_social_tomador,
                            "codigo_servico": n.codigo_servico,
                            "descricao_servico": n.descricao_servico,
                            "valor_servico": vs,
                            "base_calculo_iss": float(n.base_calculo_iss or 0),
                            "aliquota_iss": float(n.aliquota_iss or 0),
                            "valor_iss": float(n.valor_iss or 0),
                            "valor_desconto_condicionado": float(n.valor_desconto_condicionado or 0),
                            "valor_desconto_incondicionado": float(n.valor_desconto_incondicionado or 0),
                            "iss_retido": n.iss_retido,
                            "tipo_evento": n.tipo_evento,
                            "descricao_evento": n.descricao_evento,
                            "situacao": "Cancelada" if evento_cancelamento else ("Evento" if n.tipo_evento else "Normal"),
                        })

                    total_notas = notas_prestado + notas_tomado + notas_cancelado
                
                    empresas_xlsx.append({
                        "id": company_id,
                        "razao_social": company_info.get("nome", ""),
                        "cnpj": company_info.get("cnpj", ""),
                        "total_notas": total_notas,
                        "notas_prestado": notas_prestado,
                        "notas_tomado": notas_tomado,
                        "notas_cancelado": notas_cancelado,
                        "valor_servico_total": valor_servico_total,
                        "valor_iss_total": valor_iss_total,
                        "notas": notas_list,
                    })
                finally:
                    db.close()
        
            # Gera XLSX se tem dados
            if empresas_xlsx:
                if datainicio and datafim and _para_ym(datainicio) != _para_ym(datafim):
                    periodo_str = f"{_para_ym(datainicio)}_a_{_para_ym(datafim)}"
                else:
                    periodo_str = _para_ym(datainicio) if datainicio else datetime.now().strftime("%Y-%m")
                xlsx_bytes = gerar_xlsx_nfse_download(periodo_str, empresas_xlsx)
                zipf.writestr(f"RELATORIO_NFSE_{periodo_str.replace('-', '')}.xlsx", xlsx_bytes)
        except Exception as e:
            print(f"Erro ao gerar XLSX para ZIP: {e}")

    # Salva caminho do ZIP no status
    batch_status[batch_id]["zip_path"] = zip_path


@router.get("/batch-download/{batch_id}/debug")
async def get_batch_status_debug(
    batch_id: str,
    _api_key: str = Depends(verify_api_key),
):
    """Debug endpoint to check raw batch_status."""
    if batch_id not in batch_status:
        return {"error": "Batch não encontrado", "available_batches": list(batch_status.keys())}
    return batch_status[batch_id]


@router.get("/batch-download/debug/list")
async def list_batches(
    _api_key: str = Depends(verify_api_key),
):
    """List all batch IDs in memory."""
    return {"batches": list(batch_status.keys())}


@router.get("/batch-download/active")
async def list_active_batches(
    _api_key: str = Depends(verify_api_key),
):
    """Lista todos os batches ativos."""
    return batch_status


@router.get("/batch-download/{batch_id}")
async def get_batch_status(
    batch_id: str,
    _api_key: str = Depends(verify_api_key),
):
    """Retorna status do batch download."""
    if batch_id not in batch_status:
        raise HTTPException(status_code=404, detail="Batch não encontrado")

    s = batch_status[batch_id]
    return NFSEDownloadStatus(
            batch_id=batch_id,
            status=s["status"],
            file_url=f"/nfse/batch-download/{batch_id}/file" if s.get("zip_path") else None,
            error_message=s.get("companies", {}).get(list(s.get("companies", {}).keys())[0], {}).get("error") if s["status"] == "failed" else None,
            started_at=datetime.fromisoformat(s["created_at"]) if s.get("created_at") else None,
            finished_at=datetime.now() if s["status"] in ("success", "failed", "cancelled") else None,
            created_at=datetime.fromisoformat(s["created_at"]) if s.get("created_at") else None,
            datainicio=s.get("datainicio"),
            datafim=s.get("datafim"),
            download_type=s.get("download_type"),
            total=s.get("total", 0),
            done=s.get("done", 0),
            companies=s.get("companies", {}),
        )


@router.patch("/batch-download/{batch_id}/cancel")
async def cancel_batch(
    batch_id: str,
    _api_key: str = Depends(verify_api_key),
):
    """Cancela um batch em andamento."""
    if batch_id not in batch_status:
        raise HTTPException(status_code=404, detail="Batch não encontrado")

    if batch_status[batch_id]["status"] in ("success", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail="Batch já finalizado")

    batch_status[batch_id]["status"] = "cancelling"
    return {"status": "cancelling"}


@router.get("/batch-download/{batch_id}/file")
async def download_batch_file(
    batch_id: str,
    _api_key: str = Depends(verify_api_key),
):
    """Download do arquivo ZIP do batch."""
    if batch_id not in batch_status:
        raise HTTPException(status_code=404, detail="Batch não encontrado")

    zip_path = batch_status[batch_id].get("zip_path")
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Arquivo ZIP não encontrado ou ainda não gerado")

    filename = os.path.basename(zip_path)
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
    )

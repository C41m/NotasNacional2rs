from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse, StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import select, insert, func, update
from typing import List, Optional
from app.core.database import SessionLocal, get_db
from app.schemas.nfse import NFSEDownloadRequest, NFSEDownloadResponse, NFSEDownloadStatus, BatchDownloadRequest
from app.models.download_job import DownloadJob
from app.models.company import Company
from app.models.documento_fiscal import DocumentoFiscal, TipoDocumento
from app.models.nfse import Nfse
from app.schemas.nfse_detail import NfseSalvarRequest, NfseOut
from app.services.adn_api import fetch_distribuicao, extrair_campos_nfse
from app.services.nfse_xlsx import gerar_xlsx_nfse_download
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


def _organizar_xmls_por_competencia_role(xmls: list) -> dict:
    """Organiza XMLs na estrutura: {ano: {mes: {role: [xml_data]}}}"""
    organizados = {}
    for xml in xmls:
        tipo = xml.get("tipo", "DESCONHECIDO")
        role = xml.get("role", "desconhecido")
        comp = xml.get("competencia", "0000-00")
        
        if role == "prestado":
            pasta_role = "Prestados"
        elif role == "tomado":
            pasta_role = "Tomados"
        else:
            pasta_role = "Outros"
        
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
    nome_clean = nome.replace("/", "_").replace("\\", "_").replace(" ", "_")
    return f"{id_dominio}-{nome_clean}"


def _salvar_notas_empresa(db: Session, empresa_id: int, xmls: list, force_update: bool = False, batch_status: dict = None, batch_id: str = None) -> int:
    """Salva XMLs de uma empresa no banco com bulk insert + dedup em memória.
    Se force_update=True, atualiza registros existentes re-extraindo do XML armazenado.
    """
    from app.models.documento_fiscal import DocumentoFiscal, TipoDocumento
    from app.models.nfse import Nfse
    from sqlalchemy import update

    def _atualiza_msg(msg: str):
        if batch_status and batch_id and batch_id in batch_status:
            cid = str(empresa_id)
            if cid in batch_status[batch_id].get("companies", {}):
                batch_status[batch_id]["companies"][cid]["mensagem"] = msg

    existentes = db.execute(
        select(DocumentoFiscal.chave_acesso).where(
            DocumentoFiscal.empresa_id == empresa_id,
            DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
            DocumentoFiscal.chave_acesso.isnot(None),
        )
    ).scalars().all()
    chaves_existentes = set(existentes)

    doc_dicts: list[dict] = []
    nfse_items: list[dict] = []
    salvos = 0
    atualizados = 0

    # Se force_update, busca Nfse existentes com xml_original para re-extrair
    if force_update and chaves_existentes:
        _atualiza_msg("Buscando notas no banco...")
        nfse_existentes = db.execute(
            select(Nfse).where(
                Nfse.chave_acesso.in_(chaves_existentes),
                Nfse.xml_original.isnot(None),
            )
        ).scalars().all()
        nfse_por_chave = {n.chave_acesso: n for n in nfse_existentes}

        _atualiza_msg(f"Atualizando {len(nfse_por_chave)} notas...")

        # No force_update, itera diretamente sobre as chaves do banco para garantir atualização de todas
        for i, chave_temp in enumerate(chaves_existentes, 1):
            if chave_temp not in nfse_por_chave:
                continue
            if i % 50 == 0:
                _atualiza_msg(f"Atualizando {i}/{len(nfse_por_chave)} notas...")
            xml_para_extrair = nfse_por_chave[chave_temp].xml_original
            campos = extrair_campos_nfse(xml_para_extrair)
            chave = campos.get("chave_acesso") or chave_temp

            if chave not in chaves_existentes:
                continue

            periodo = campos.get("competencia") or "0000-00"
            valor_servico = campos.get("valor_servico")

            # Atualiza DocumentoFiscal
            db.execute(
                update(DocumentoFiscal)
                .where(
                    DocumentoFiscal.empresa_id == empresa_id,
                    DocumentoFiscal.chave_acesso == chave,
                )
                .values(
                    periodo=periodo,
                    numero_documento=campos.get("numero_nfse"),
                    valor_total=valor_servico,
                    situacao=campos.get("tipo_evento") or "normal",
                    observacao=campos.get("descricao_evento"),
                    arquivo_fonte=campos.get("arquivo_fonte"),
                    data_emissao=campos.get("data_emissao"),
                )
            )
            # Atualiza Nfse
            nfse_update_data = {"xml_original": xml_para_extrair}
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
                    nfse_update_data[campo] = campos[campo]

            db.execute(
                update(Nfse)
                .where(Nfse.chave_acesso == chave)
                .values(**nfse_update_data)
            )
            atualizados += 1

    _atualiza_msg("Finalizando...")

    if force_update:
        # No force_update, não processa xmls da ADN - já atualizou tudo acima
        if not doc_dicts and atualizados == 0:
            return 0
        # Commit e retorna
        if nfse_items:
            for item in nfse_items:
                item["documento_fiscal_id"] = id_map[item["chave_acesso"]]
            db.bulk_save_objects(nfse_items)
        db.commit()
        return salvos + atualizados

    for xml_data in xmls:
        _atualiza_msg("Preparando novas notas...")
        campos = extrair_campos_nfse(xml_data["xml"])
        chave = campos.get("chave_acesso") or xml_data.get("chave")

        if not chave:
            continue

        periodo = campos.get("competencia") or xml_data.get("competencia") or "0000-00"
        valor_servico = campos.get("valor_servico")

        if chave in chaves_existentes:
            continue

        doc_dicts.append({
            "empresa_id": empresa_id,
            "tipo_documento": TipoDocumento.NFSE,
            "periodo": periodo,
            "chave_acesso": chave,
            "numero_documento": campos.get("numero_nfse"),
            "valor_total": valor_servico,
            "situacao": campos.get("tipo_evento") or "normal",
            "observacao": campos.get("descricao_evento"),
            "arquivo_fonte": campos.get("arquivo_fonte"),
            "data_emissao": campos.get("data_emissao"),
            "ativo": True,
        })

        nfse_data = {
            "chave_acesso": chave,
            "nsu": xml_data.get("nsu"),
            "tipo_documento_api": xml_data.get("tipo"),
            "role": xml_data.get("role"),
            "competencia": periodo,
            "xml_original": xml_data["xml"],
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

        nfse_items.append(nfse_data)
        chaves_existentes.add(chave)
        salvos += 1

    if not doc_dicts and atualizados == 0:
        return 0

    result = db.execute(
        insert(DocumentoFiscal)
        .returning(DocumentoFiscal.id, DocumentoFiscal.chave_acesso),
        doc_dicts,
    )
    id_map = {chave: doc_id for doc_id, chave in result.fetchall()}

    nfse_instances = []
    for item in nfse_items:
        item["documento_fiscal_id"] = id_map[item["chave_acesso"]]
        nfse_instances.append(Nfse(**item))

    db.bulk_save_objects(nfse_instances)
    db.commit()
    return salvos + atualizados


@router.get("/relatorio/xlsx")
async def download_relatorio_nfse_xlsx(
    periodo: str = Query(..., description="Competência no formato YYYY-MM"),
    company_ids: Optional[str] = Query(None, description="IDs das empresas separados por vírgula (opcional)"),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    """Gera planilha XLSX com notas fiscais baixadas (NFSe) para a competência.
    
    Aba 1 - RESUMO: Totais por empresa + totais por tipo (Prestado/Tomado/Cancelado) + valores
    Aba 2 - DETALHAMENTO: Todas as notas com detalhes completos
    """
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
                Nfse.competencia == periodo,
                DocumentoFiscal.ativo == True,
            )
            .order_by(Nfse.data_emissao)
        )
        notas_db = db.execute(notas_query).scalars().all()

        # Calcular totais por role
        notas_prestado = 0
        notas_tomado = 0
        notas_cancelado = 0
        valor_servico_total = 0.0
        valor_iss_total = 0.0

        notas_list = []
        for n in notas_db:
            role = (n.role or "").lower()
            if role == "prestado":
                notas_prestado += 1
            elif role == "tomado":
                notas_tomado += 1
            elif n.tipo_evento:
                notas_cancelado += 1
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
                "iss_retido": n.iss_retido,
            })

        empresas_data.append({
            "id": emp.id,
            "razao_social": emp.nome,
            "cnpj": emp.cnpj,
            "total_notas": len(notas_db),
            "notas_prestado": notas_prestado,
            "notas_tomado": notas_tomado,
            "notas_cancelado": notas_cancelado,
            "valor_servico_total": valor_servico_total,
            "valor_iss_total": valor_iss_total,
            "notas": notas_list,
        })

    xlsx_bytes = gerar_xlsx_nfse_download(periodo, empresas_data)

    filename = f"nfse_download_{periodo.replace('-', '')}.xlsx"
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
            "valorPrestado": 0,
            "valorTomado": 0,
            "valorCancelado": 0,
            "carregando_notas": False,
            "cnpj": "",
            "nome": "",
            "empresa_id": cid,
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
                valor_prestado = 0.0
                valor_tomado = 0.0
                valor_cancelado = 0.0
            
                for xml_data in xmls:
                    campos = extrair_campos_nfse(xml_data["xml"])
                    vs = float(campos.get("valor_servico") or 0)
                    if vs == 0:
                        vs = float(campos.get("valor_liquido_calculado") or 0)
                    valor_servico += vs
                    valor_iss += float(campos.get("valor_iss") or 0)
                
                    role = (xml_data.get("role") or "").lower()
                    if role == "prestado":
                        notas_prestadas += 1
                        valor_prestado += vs
                    elif role == "tomado":
                        notas_tomadas += 1
                        valor_tomado += vs
                    elif campos.get("tipo_evento"):
                        notas_canceladas += 1
                        valor_cancelado += vs
                    else:
                        notas_prestadas += 1
                        valor_prestado += vs
            
                batch_status[batch_id]["companies"][cid_res]["valorServico"] = valor_servico
                batch_status[batch_id]["companies"][cid_res]["valorIss"] = valor_iss
                batch_status[batch_id]["companies"][cid_res]["notasPrestadas"] = notas_prestadas
                batch_status[batch_id]["companies"][cid_res]["notasTomadas"] = notas_tomadas
                batch_status[batch_id]["companies"][cid_res]["notasCanceladas"] = notas_canceladas
                batch_status[batch_id]["companies"][cid_res]["valorPrestado"] = valor_prestado
                batch_status[batch_id]["companies"][cid_res]["valorTomado"] = valor_tomado
                batch_status[batch_id]["companies"][cid_res]["valorCancelado"] = valor_cancelado

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
                                filename = f"{empresa_folder}/{ano}/{mes}/{role}/NFSe_{xml_data.get('chave', f'{ano}{mes}{i}')}.xml"
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
                
                    periodo_inicio = _para_ym(datainicio) if datainicio else None
                    periodo_fim = _para_ym(datafim) if datafim else None
                
                    # Se tem período, usa o primeiro; senão busca todas
                    competencia_filtro = periodo_inicio if periodo_inicio else None
                
                    notas_query = (
                        select(Nfse)
                        .join(DocumentoFiscal, Nfse.documento_fiscal_id == DocumentoFiscal.id)
                        .where(
                            DocumentoFiscal.empresa_id == company_id,
                            DocumentoFiscal.tipo_documento == TipoDocumento.NFSE,
                            DocumentoFiscal.ativo == True,
                        )
                    )
                
                    if competencia_filtro:
                        notas_query = notas_query.where(Nfse.competencia == competencia_filtro)
                
                    notas_db = db.execute(notas_query).scalars().all()
                
                    # Mesmo processamento do relatório
                    notas_prestado = 0
                    notas_tomado = 0
                    notas_cancelado = 0
                    valor_servico_total = 0.0
                    valor_iss_total = 0.0
                    notas_list = []
                
                    for n in notas_db:
                        role = (n.role or "").lower()
                        if role == "prestado":
                            notas_prestado += 1
                        elif role == "tomado":
                            notas_tomado += 1
                        elif n.tipo_evento:
                            notas_cancelado += 1
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
                            "iss_retido": n.iss_retido,
                        })
                
                    empresas_xlsx.append({
                        "id": company_id,
                        "razao_social": company_info.get("nome", ""),
                        "cnpj": company_info.get("cnpj", ""),
                        "total_notas": len(notas_db),
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
                periodo_str = datainicio.replace("/", "-")[:7] if datainicio else datetime.now().strftime("%Y-%m")
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

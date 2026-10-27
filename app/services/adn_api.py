import asyncio
import base64
import gzip
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

import httpx
from app.core.database import SessionLocal
from app.models.company import Company
from app.services.certificate_service import get_certificate_pem
from sqlalchemy import select

# Endpoints da API ADN
ADN_BASE_URLS = {
    "producaorestrita": "https://adn.producaorestrita.nfse.gov.br/contribuintes",
    "producao": "https://adn.nfse.gov.br/contribuintes",
}

# Namespace padrão NFS-e Nacional
NFSE_NS = "http://www.sped.fazenda.gov.br/nfse"

# Mapeamento de eventos NFS-e Nacional (código → descrição)
# Fonte: Anexo II - SEFIN ADN (gov.br) - código de 6 dígitos
MAPEVENTOS = {
    # Eventos de Cancelamento
    "101101": "CANCELAMENTO",  # Cancelamento de NFS-e
    "105102": "CANCELAMENTO_POR_SUBSTITUICAO",  # Cancelamento de NFS-e por Substituição
    "105104": "CANCELAMENTO_DEFERIDO_ANALISE_FISCAL",  # Cancelamento Deferido por Análise Fiscal
    "105105": "CANCELAMENTO_INDEFERIDO_ANALISE_FISCAL",  # Cancelamento Indeferido por Análise Fiscal
    "305101": "CANCELAMENTO_POR_OFICIO",  # Cancelamento de NFS-e por Ofício (município)
    # Eventos de Manifestação (Tomador / Prestador / Intermediário)
    "101102": "MANIFESTACAO_REJEICAO",  # Manifestação de Rejeição
    "101103": "MANIFESTACAO_DESCONHECIMENTO",  # Manifestação de Desconhecimento
    "101104": "MANIFESTACAO_NAO_REALIZADA",  # Manifestação Não Realizada
}


class ADNError(Exception):
    """Erro na comunicação com a API ADN."""
    pass


def parse_xml_role_and_competence(xml_str: str, cnpj_interessado: str) -> dict:
    """
    Analisa o XML e identifica:
    - tipo_documento: 'NFSE' | 'EVENTO' | 'DPS' | 'CREDITO' | 'DEBITO' | 'APURACAO'
    - role: 'prestado' | 'tomado' | 'intermediario' | 'desconhecido'
    - competencia: 'YYYY-MM'
    - evento_tipo: código do evento (se aplicável)
    - evento_descricao: descrição legível do evento (se aplicável)
    """
    try:
        root = ET.fromstring(xml_str)
        ns = {'nfse': NFSE_NS}
        
        # Verificar se é DPS (Declaração de Prestação de Serviço)
        inf_dps = root.find('.//nfse:infDPS', ns)
        if inf_dps is not None:
            competencia = _extrair_competencia(inf_dps, ns)
            role = _detectar_role(inf_dps, cnpj_interessado, ns)
            return {
                'tipo_documento': 'DPS',
                'role': role,
                'competencia': competencia,
                'evento_tipo': None,
                'evento_descricao': None,
            }
        
        # Verificar se é Evento (pedRegEvento)
        inf_ped_reg = root.find('.//nfse:pedRegEvento/nfse:infPedReg', ns)
        if inf_ped_reg is not None:
            evento_tipo = None
            evento_desc = None
            
            # Extrair código do evento
            tp_evento_elem = inf_ped_reg.find('.//nfse:tpEvento', ns)
            if tp_evento_elem is not None and tp_evento_elem.text:
                evento_tipo = tp_evento_elem.text.strip()
                evento_desc = MAPEVENTOS.get(evento_tipo, f"EVENTO_{evento_tipo}")
            
            competencia = _extrair_competacao_evento(root, ns)
            role = _detectar_role_evento(inf_ped_reg, cnpj_interessado, ns)
            
            return {
                'tipo_documento': 'EVENTO',
                'role': role,
                'competencia': competencia,
                'evento_tipo': evento_tipo,
                'evento_descricao': evento_desc,
            }
        
        # Verificar se é NFS-e
        inf_nfse = root.find('.//nfse:infNFSe', ns)
        if inf_nfse is not None:
            competencia = _extrair_competencia(inf_nfse, ns)
            role = _detectar_role(inf_nfse, cnpj_interessado, ns)
            return {
                'tipo_documento': 'NFSE',
                'role': role,
                'competencia': competencia,
                'evento_tipo': None,
                'evento_descricao': None,
            }
        
        # Estrutura não reconhecida
        return {
            'tipo_documento': None,
            'role': None,
            'competencia': None,
            'evento_tipo': None,
            'evento_descricao': None,
        }
        
    except Exception:
        return {
            'tipo_documento': None,
            'role': None,
            'competencia': None,
            'evento_tipo': None,
            'evento_descricao': None,
        }


def _extrair_competencia(elem, ns) -> Optional[str]:
    """Extrai competência de um elemento infNFSe ou infDPS."""
    for tag in ['nfse:dhEmi', 'nfse:dhProc', 'nfse:dCompet']:
        found = elem.find(f'.//{tag}', ns)
        if found is not None and found.text:
            try:
                dt = datetime.fromisoformat(found.text.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m')
            except:
                pass
    return None


def _extrair_competacao_evento(root, ns) -> Optional[str]:
    """Extrai competência de um XML de evento (pedRegEvento)."""
    # Eventos referenciam uma NFS-e pela chave, então a competência
    # pode ser inferida da data do evento
    for tag in ['nfse:dhEvento', 'nfse:dhRegEvento']:
        found = root.find(f'.//{tag}', ns)
        if found is not None and found.text:
            try:
                dt = datetime.fromisoformat(found.text.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m')
            except:
                pass
    return None


def _detectar_role(elem, cnpj_interessado: str, ns) -> str:
    """Detecta o papel do CNPJ interessado em uma NFS-e ou DPS."""
    cnpj_clean = cnpj_interessado.replace('.', '').replace('/', '').replace('-', '')
    
    # Verificar prestador/emitente
    for path in ['.//nfse:emit/nfse:CNPJ', './/nfse:prest/nfse:CNPJ']:
        el = elem.find(path, ns)
        if el is not None and el.text == cnpj_clean:
            return 'prestado'
    
    # Verificar tomador
    toma = elem.find('.//nfse:toma/nfse:CNPJ', ns)
    if toma is not None and toma.text == cnpj_clean:
        return 'tomado'
    
    # Verificar intermediário
    interm = elem.find('.//nfse:inter/nfse:CNPJ', ns)
    if interm is not None and interm.text == cnpj_clean:
        return 'intermediario'
    
    return 'desconhecido'


def _detectar_role_evento(inf_ped_reg, cnpj_interessado: str, ns) -> str:
    """Detecta o papel do CNPJ interessado em um evento."""
    cnpj_clean = cnpj_interessado.replace(".", "").replace("/", "").replace("-", "")

    # Eventos podem ter CNPJ do autor (cnpjAutor ou CPFAutor)
    for path in ['.//nfse:cnpjAutor', './/nfse:CPFAutor']:
        el = inf_ped_reg.find(path, ns)
        if el is not None and el.text == cnpj_clean:
            return 'autor_evento'

    return 'desconhecido'


# ---------------------------------------------------------------------------
# Extração de campos de negócio da NFS-e Nacional (leiaute SPED)
# Mapeia apenas tags reais do XML namespace http://www.sped.fazenda.gov.br/nfse
# ---------------------------------------------------------------------------

def _texto(elem, path: str, ns) -> Optional[str]:
    """Retorna o texto de um elemento ou None."""
    el = elem.find(path, ns)
    if el is not None and el.text:
        return el.text.strip()
    return None


def _numero(valor: Optional[str]) -> Optional[float]:
    """Converte string monetária para float. Retorna None se inválido.

    Suporta:
    - ponto decimal (XSD): "1500.00" -> 1500.0
    - vírgula decimal (BR): "1.500,00" -> 1500.0 ; "1500,00" -> 1500.0
    """
    if valor is None:
        return None
    try:
        v = valor.strip()
        if ',' in v:
            v = v.replace('.', '').replace(',', '.')
        return float(v)
    except (ValueError, AttributeError):
        return None


def extrair_campos_nfse(xml_str: str) -> dict:
    """
    Extrai campos de negócio de um XML de NFS-e Nacional (infNFSe).
    Retorna dict com chaves alinhadas ao modelo Nfse / tabela nfse.
    Não inventa campos: só extrai tags presentes no leiaute SPED.
    """
    try:
        root = ET.fromstring(xml_str)
        ns = {'nfse': NFSE_NS}

        inf_nfse = root.find('.//nfse:infNFSe', ns)
        if inf_nfse is None:
            return {}

        campos: dict = {}

        # Identificação
        campos['identificador_nfse'] = inf_nfse.get('id')
        campos['numero_nfse'] = _texto(inf_nfse, './/nfse:nNFSe', ns)
        campos['versao_leiaute'] = root.get('versao') or inf_nfse.get('versao')

        # Data / competência
        dh_emi = _texto(inf_nfse, './/nfse:dhEmi', ns)
        if dh_emi:
            try:
                campos['data_emissao'] = datetime.fromisoformat(dh_emi.replace('Z', '+00:00'))
                campos['competencia'] = dh_emi[:7]  # YYYY-MM
            except Exception:
                pass
        d_compet = _texto(inf_nfse, './/nfse:dCompet', ns)
        if d_compet and not campos.get('competencia'):
            try:
                campos['competencia'] = datetime.strptime(d_compet, '%Y-%m').strftime('%Y-%m')
            except Exception:
                campos['competencia'] = d_compet[:7] if len(d_compet) >= 7 else None

        # Município emissor
        campos['municipio_emissor_codigo'] = _texto(inf_nfse, './/nfse:cLocEmi', ns) or _texto(inf_nfse, './/nfse:cMun', ns)
        campos['municipio_emissor_descricao'] = _texto(inf_nfse, './/nfse:xLocEmi', ns)

        # Local de prestação e incidência
        campos['local_prestacao'] = _texto(inf_nfse, './/nfse:xLocPrestacao', ns)
        campos['local_incidencia_codigo'] = _texto(inf_nfse, './/nfse:cLocIncid', ns)
        campos['local_incidencia_descricao'] = _texto(inf_nfse, './/nfse:xLocIncid', ns)

        # Tributos
        campos['tributo_nacional'] = _texto(inf_nfse, './/nfse:xTribNac', ns)
        campos['tributo_municipal'] = _texto(inf_nfse, './/nfse:xTribMun', ns)
        campos['codigo_nbs'] = _texto(inf_nfse, './/nfse:xNBS', ns)

        # Identificação administrativa
        campos['versao_aplicacao'] = _texto(inf_nfse, './/nfse:verAplic', ns)
        campos['ambiente_gerador'] = _texto(inf_nfse, './/nfse:ambGer', ns)
        campos['tipo_emissao'] = _texto(inf_nfse, './/nfse:tpEmis', ns)
        campos['processo_emissao'] = _texto(inf_nfse, './/nfse:procEmi', ns)
        campos['codigo_status'] = _texto(inf_nfse, './/nfse:cStat', ns)
        campos['numero_dfse'] = _texto(inf_nfse, './/nfse:nDFSe', ns)

        # Data de processamento
        dh_proc = _texto(inf_nfse, './/nfse:dhProc', ns)
        if dh_proc:
            try:
                campos['data_processamento'] = datetime.fromisoformat(dh_proc.replace('Z', '+00:00'))
            except Exception:
                pass

        # Prestador (emit / prest)
        prest = inf_nfse.find('.//nfse:emit', ns) or inf_nfse.find('.//nfse:prest', ns)
        if prest is not None:
            campos['cnpj_prestador'] = _texto(prest, './/nfse:CNPJ', ns)
            campos['cpf_prestador'] = _texto(prest, './/nfse:CPF', ns)
            campos['razao_social_prestador'] = _texto(prest, './/nfse:xNome', ns)
            campos['inscricao_municipal_prestador'] = _texto(prest, './/nfse:IM', ns)
            campos['caepf_prestador'] = _texto(prest, './/nfse:CAEPF', ns)
            campos['nif_prestador'] = _texto(prest, './/nfse:NIF', ns)
            campos['cnao_nif_prestador'] = _texto(prest, './/nfse:cNaoNIF', ns)

            # Endereço do prestador (enderNac)
            ender = prest.find('.//nfse:enderNac', ns)
            if ender is not None:
                campos['prest_logradouro'] = _texto(ender, './/nfse:xLgr', ns)
                campos['prest_numero'] = _texto(ender, './/nfse:nro', ns)
                campos['prest_bairro'] = _texto(ender, './/nfse:xBairro', ns)
                campos['prest_codigo_municipio'] = _texto(ender, './/nfse:cMun', ns)
                campos['prest_uf'] = _texto(ender, './/nfse:UF', ns)
                campos['prest_cep'] = _texto(ender, './/nfse:CEP', ns)
                campos['prest_telefone'] = _texto(prest, './/nfse:fone', ns)
                campos['prest_email'] = _texto(prest, './/nfse:email', ns)

        # Tomador
        toma = inf_nfse.find('.//nfse:toma', ns)
        if toma is not None:
            campos['cnpj_tomador'] = _texto(toma, './/nfse:CNPJ', ns)
            campos['cpf_tomador'] = _texto(toma, './/nfse:CPF', ns)
            campos['razao_social_tomador'] = _texto(toma, './/nfse:xNome', ns)
            campos['inscricao_municipal_tomador'] = _texto(toma, './/nfse:IM', ns)
            campos['caepf_tomador'] = _texto(toma, './/nfse:CAEPF', ns)
            campos['nif_tomador'] = _texto(toma, './/nfse:NIF', ns)
            campos['cnao_nif_tomador'] = _texto(toma, './/nfse:cNaoNIF', ns)

        # Serviço
        serv = inf_nfse.find('.//nfse:serv', ns)
        if serv is not None:
            campos['codigo_servico'] = _texto(serv, './/nfse:cServ', ns)
            info_compl = serv.find('.//nfse:infoCompl', ns)
            if info_compl is not None:
                campos['informacoes_complementares'] = _texto(info_compl, './/nfse:xInfComp', ns)
                campos['numero_pedido'] = _texto(info_compl, './/nfse:xPed', ns)

        # Valores
        valores = inf_nfse.find('.//nfse:valores', ns)
        
        # Função auxiliar para extrair valores de um bloco valores
        def extrair_valores(valores_elem):
            if valores_elem is None:
                return {}
            v = {}
            v_serv_prest = valores_elem.find('.//nfse:vServPrest', ns)
            if v_serv_prest is not None:
                v['valor_servico'] = _numero(_texto(v_serv_prest, './/nfse:vServ', ns))
                v['valor_recebido'] = _numero(_texto(v_serv_prest, './/nfse:vReceb', ns))
            v_desc = valores_elem.find('.//nfse:vDescCondIncond', ns)
            if v_desc is not None:
                v['valor_desconto_condicionado'] = _numero(_texto(v_desc, './/nfse:vDescCond', ns))
                v['valor_desconto_incondicionado'] = _numero(_texto(v_desc, './/nfse:vDescIncond', ns))
            # Valores diretos do bloco valores/ (conforme leiaute SPED)
            v['valor_servico'] = _numero(_texto(valores_elem, './/nfse:vServPrest/nfse:vServ', ns)) or v.get('valor_servico')
            v['valor_recebido'] = _numero(_texto(valores_elem, './/nfse:vServPrest/nfse:vReceb', ns)) or v.get('valor_recebido')
            v['base_calculo_iss'] = _numero(_texto(valores_elem, './/nfse:vBC', ns))
            v['aliquota_iss'] = _numero(_texto(valores_elem, './/nfse:pAliqAplic', ns))
            v['valor_iss'] = _numero(_texto(valores_elem, './/nfse:vISSQN', ns))
            v['valor_total_retencoes'] = _numero(_texto(valores_elem, './/nfse:vTotalRet', ns))
            v['valor_liquido_calculado'] = _numero(_texto(valores_elem, './/nfse:vLiq', ns))
            # Descontos
            v['valor_desconto_condicionado'] = _numero(_texto(valores_elem, './/nfse:vDescCondIncond/nfse:vDescCond', ns)) or v.get('valor_desconto_condicionado')
            v['valor_desconto_incondicionado'] = _numero(_texto(valores_elem, './/nfse:vDescCondIncond/nfse:vDescIncond', ns)) or v.get('valor_desconto_incondicionado')
            # ISS municipal (tribMun) - apenas campos de retenção/tipo
            trib_mun = valores_elem.find('.//nfse:tribMun', ns)
            if trib_mun is not None:
                v['iss_retido'] = _texto(trib_mun, './/nfse:tpRetISSQN', ns)
                # vRetISSQN pode vir aqui
                v['valor_iss_retido'] = _numero(_texto(trib_mun, './/nfse:vRetISSQN', ns))
                # pAliq dentro de tribMun é a alíquota municipal (diferente de pAliqAplic)
                aliq_trib = _texto(trib_mun, './/nfse:pAliq', ns)
                if aliq_trib and not v.get('aliquota_iss'):
                    v['aliquota_iss'] = _numero(aliq_trib)
            # Retenções federais (tribFed)
            trib_fed = valores_elem.find('.//nfse:tribFed', ns)
            if trib_fed is not None:
                v['valor_retido_cp'] = _numero(_texto(trib_fed, './/nfse:vRetCP', ns))
                v['valor_retido_irrf'] = _numero(_texto(trib_fed, './/nfse:vRetIRRF', ns))
                v['valor_retido_csll'] = _numero(_texto(trib_fed, './/nfse:vRetCSLL', ns))
                v['valor_retido_pis'] = _numero(_texto(trib_fed, './/nfse:vRetPIS', ns))
                v['valor_retido_cofins'] = _numero(_texto(trib_fed, './/nfse:vRetCOFINS', ns))
            return v

        # Primeiro tenta valores direto em infNFSe
        valores_dict = extrair_valores(valores)
        campos.update(valores_dict)
        
        # Se não encontrou valores principais, tenta no DPS/infDPS/valores (para notas tomadas)
        if not campos.get('valor_servico') or not campos.get('base_calculo_iss'):
            dps_inf = inf_nfse.find('.//nfse:DPS/nfse:infDPS', ns)
            if dps_inf is not None:
                valores_dps = dps_inf.find('.//nfse:valores', ns)
                if valores_dps is not None:
                    valores_dps_dict = extrair_valores(valores_dps)
                    # Só atualiza campos que ainda não têm valor
                    for k, v in valores_dps_dict.items():
                        if v is not None and not campos.get(k):
                            campos[k] = v

        # Chaves de referência
        # Tenta chNFSe, chaveAcesso, e o Id do infNFSe (formato NFS...)
        chave_id = inf_nfse.get('id') or inf_nfse.get('Id')
        if chave_id and chave_id.startswith('NFS'):
            # Remove prefixo NFS para compatibilidade com dados existentes no banco
            campos['chave_acesso'] = chave_id[3:]
        else:
            campos['chave_acesso'] = _texto(inf_nfse, './/nfse:chNFSe', ns) or _texto(inf_nfse, './/nfse:chaveAcesso', ns)
        campos['chave_nfe_referenciada'] = _texto(inf_nfse, './/nfse:chaveDFe', ns) or _texto(inf_nfse, './/nfse:chNFe', ns)

        # Valor líquido (cálculo se não vier direto)
        vs = campos.get('valor_servico')
        vd_cond = campos.get('valor_desconto_condicionado') or 0
        vd_incond = campos.get('valor_desconto_incondicionado') or 0
        if vs is not None:
            campos['valor_liquido'] = round(vs - vd_cond - vd_incond, 2)
        else:
            # Fallback: se não há vServ, usar vLiq como valor_servico para totais
            v_liq = _texto(valores, './/nfse:vLiq', ns) if valores is not None else None
            if v_liq:
                campos['valor_servico'] = _numero(v_liq)
                campos['valor_liquido'] = _numero(v_liq)

        # XML original
        campos['xml_original'] = xml_str

        # Remove chaves None para não sobrescrever com None no upsert
        return {k: v for k, v in campos.items() if v is not None}

    except Exception:
        return {}


async def fetch_distribuicao(
    company_id: int,
    ult_nsu: int = 0,
    ambiente: str = "producaorestrita",
    batch_status: Optional[dict] = None,
    batch_id: Optional[str] = None,
    progress_callback=None,
) -> dict:
    """
    Busca documentos fiscais com análise de XML.
    Retorna XMLs com: tipo_documento, role, competencia, evento_tipo, evento_descricao.
    """
    db = SessionLocal()
    temp_dir = None
    cert_path = None
    key_path = None

    try:
        company = db.execute(select(Company).where(Company.id == company_id)).scalar_one()
        cnpj = company.cnpj.replace(".", "").replace("/", "").replace("-", "")

        cert_pem, key_pem, password = get_certificate_pem(db, company_id)

        temp_dir = Path(tempfile.mkdtemp(prefix="adn_"))
        cert_path = temp_dir / "cert.pem"
        key_path = temp_dir / "key.pem"
        cert_path.write_bytes(cert_pem)
        key_path.write_bytes(key_pem)

        base_url = ADN_BASE_URLS.get(ambiente, ADN_BASE_URLS["producaorestrita"])

        client = httpx.AsyncClient(
            cert=(str(cert_path), str(key_path)),
            timeout=60.0,
            verify=True,
        )

        xmls = []
        notas_processadas = 0
        ult_nsu_atual = ult_nsu

        try:
            while True:
                if batch_status and batch_id:
                    batch = batch_status.get(batch_id, {})
                    if batch.get("cancelled"):
                        return {"xmls": xmls, "notas_processadas": notas_processadas, "error": "Cancelado"}

                url = f"{base_url}/DFe/{ult_nsu_atual}"
                response = await client.get(url)

                if response.status_code == 404:
                    break

                if response.status_code != 200:
                    raise ADNError(f"Erro API ADN: {response.status_code} - {response.text[:200]}")

                data = response.json()
                if data.get("StatusProcessamento") == "NENHUM_DOCUMENTO_LOCALIZADO":
                    break

                lote = data.get("LoteDFe", [])
                if not lote:
                    break

                for doc in lote:
                    nsu = doc.get("NSU", "unknown")
                    xml_b64 = doc.get("ArquivoXml", "")
                    tipo_doc_api = doc.get("TipoDocumento", "")

                    if not xml_b64:
                        continue

                    try:
                        xml_zip = base64.b64decode(xml_b64)
                        xml_bytes = gzip.decompress(xml_zip)
                        xml_str = xml_bytes.decode("utf-8")

                        # Analisar XML
                        info = parse_xml_role_and_competence(xml_str, cnpj)

                        # Se o parser não identificou tipo, usar o da API ADN
                        tipo_documento = info.get('tipo_documento') or tipo_doc_api or 'DESCONHECIDO'

                        xmls.append({
                            "nsu": nsu,
                            "tipo": tipo_documento,
                            "chave": doc.get("ChaveAcesso", ""),
                            "xml": xml_str,
                            "role": info.get("role") or "desconhecido",
                            "competencia": info.get("competencia") or "0000-00",
                            "evento_tipo": info.get("evento_tipo"),
                            "evento_descricao": info.get("evento_descricao"),
                        })
                        notas_processadas += 1

                        if progress_callback is not None:
                            await progress_callback(company_id, notas_processadas, notas_processadas)

                    except Exception as e:
                        print(f"[ADN] Erro NSU {nsu}: {e}")

                if len(lote) < 50:
                    break

                ult_nsu_atual = max(doc.get("NSU", 0) for doc in lote) + 1

        finally:
            await client.aclose()

        return {"xmls": xmls, "notas_processadas": notas_processadas, "error": None}

    except Exception as e:
        return {"xmls": [], "notas_processadas": 0, "error": str(e)}
    finally:
        if cert_path and os.path.exists(cert_path):
            os.unlink(cert_path)
        if key_path and os.path.exists(key_path):
            os.unlink(key_path)
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        db.close()

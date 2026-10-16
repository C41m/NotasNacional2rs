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
MAPEVENTOS = {
    # Eventos de Cancelamento
    "110110": "SOLICITACAO_CANCELAMENTO",
    "110111": "CANCELAMENTO",
    "110112": "CANCELAMENTO_POR_SUBSTITUICAO",
    "110115": "SUBSTITUICAO",
    "110116": "ANALISE_FISCAL_CANCELAMENTO",
    "110117": "ANULACAO_REJEICAO",
    "110118": "ANALISE_FISCAL_CANCELAMENTO_2",
    "110119": "CANCELAMENTO_INDEFERIDO",
    # Eventos de Bloqueio/Desbloqueio
    "110120": "BLOQUEIO_POR_OFICIO",
    "110121": "DESBLOQUEIO_POR_OFICIO",
    "110122": "CANCELAMENTO_POR_OFICIO",
    "110123": "ANULACAO_CANCELAMENTO_SUBSTITUICAO",
    # Eventos de Manifestação (Tomador)
    "101101": "MANIFESTACAO_CONFIRMACAO",
    "101102": "MANIFESTACAO_REJEICAO",
    "101103": "MANIFESTACAO_DESCONHECIMENTO",
    "101104": "MANIFESTACAO_NAO_REALIZADA",
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
    cnpj_clean = cnpj_interessado.replace('.', '').replace('/', '').replace('-', '')
    
    # Eventos podem ter CNPJ do autor (cnpjAutor ou CPFAutor)
    for path in ['.//nfse:cnpjAutor', './/nfse:CPFAutor']:
        el = inf_ped_reg.find(path, ns)
        if el is not None and el.text == cnpj_clean:
            return 'autor_evento'
    
    return 'desconhecido'


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

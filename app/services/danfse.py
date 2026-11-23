# app/services/danfse.py
"""Proxy para o serviço externo de geração de DANFSe (PDF).

Wrapper fino do `calculadora-rtc-gerador-danfse` (Go) para o backend:
- recebe o XML armazenado (string) e a situação da nota;
- chama o serviço por HTTP;
- devolve os bytes do PDF.
"""
import httpx

from app.core.config import settings


async def gerar_danfse(xml_original: str, stc: int = 0) -> bytes:
    """Gera o DANFSe em PDF no serviço externo.

    xml_original: conteúdo do XML (tal como armazenado no banco).
    stc: situação da nota — 0 válida, 1 substituída, 2 cancelada.
    """
    if not xml_original:
        raise ValueError("XML não encontrado")
    xml_bytes = xml_original.encode("utf-8") if isinstance(xml_original, str) else xml_original
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            settings.DANFSE_SERVICE_URL,
            content=xml_bytes,
            headers={"Content-Type": "application/xml"},
            params={"stc": str(stc)},
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Serviço DANFSe respondeu {resp.status_code}")
    return resp.content

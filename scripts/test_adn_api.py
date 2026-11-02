#!/usr/bin/env python3
"""
Script de teste - Consulta API ADN (Ambiente de Dados Nacional) NFS-e

Faz consulta na API de distribuição de documentos fiscais para contribuintes.
Usa certificado digital A1/A3 armazenado no banco (tabela certificates).

Uso:
    python scripts/test_adn_api.py [--company-id 11] [--nsu 0] [--ambiente producao]

Docs oficiais:
    https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/apis-prod-restrita-e-producao
    Swagger prod: https://adn.nfse.gov.br/contribuintes/docs/index.html
"""
import asyncio
import base64
import gzip
import json
import shutil
import sys
import tempfile
from pathlib import Path

import httpx

# Caminhos do projeto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import SessionLocal
from app.services.certificate_service import get_certificate_pem


def decrypt_and_save_cert(company_id: int):
    """Decripta certificado do banco e salva PEMs temporários."""
    db = SessionLocal()
    try:
        cert_pem, key_pem, password = get_certificate_pem(db, company_id)
    finally:
        db.close()

    temp_dir = Path(tempfile.mkdtemp(prefix="adn_cert_"))
    cert_path = temp_dir / "cert.pem"
    key_path = temp_dir / "key.pem"

    cert_path.write_bytes(cert_pem)
    key_path.write_bytes(key_pem)

    return cert_path, key_path, password, temp_dir


async def test_adn_consulta(company_id: int, ult_nsu: int = 0, ambiente: str = "producao"):
    """
    Testa a API ADN de distribuição de DFe para contribuinte.
    """
    base_url = (
        "https://adn.producaorestrita.nfse.gov.br/contribuintes"
        if ambiente == "producaorestrita"
        else "https://adn.nfse.gov.br/contribuintes"
    )

    # CNPJ da empresa (necessário na nova versão da API ADN)
    from app.models.company import Company
    from sqlalchemy import select
    _db = SessionLocal()
    _company = _db.execute(select(Company).where(Company.id == company_id)).scalar_one()
    cnpj_empresa = _company.cnpj.replace(".", "").replace("/", "").replace("-", "")
    _db.close()

    output_dir = PROJECT_ROOT / "scripts" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Decriptar certificado
    print(f"🔐 Decriptando certificado da empresa ID={company_id}...")
    cert_path, key_path, password, temp_dir = decrypt_and_save_cert(company_id)
    print(f"   Certificado salvo em: {temp_dir}")

    try:
        client = httpx.AsyncClient(
            cert=(str(cert_path), str(key_path)),
            timeout=60.0,
            verify=True,
        )

        # === Teste 1: Consulta por NSU (distribuição incremental) ===
        print(f"\n📡 Teste 1: GET /DFe/{ult_nsu} (distribuição incremental)")
        url = f"{base_url}/DFe/{ult_nsu}?lote=true&cnpjConsulta={cnpj_empresa}"
        print(f"   URL: {url}")

        response = await client.get(url)
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")

        if response.status_code == 200:
            try:
                data = response.json()
            except json.JSONDecodeError:
                print(f"   Resposta não-JSON: {response.text[:500]}")
                data = {}

            cStat = data.get("StatusProcessamento", "")
            xMotivo = ""
            for erro in data.get("Erros", []):
                xMotivo += erro.get("Descricao", "") + "; "

            print(f"\n   📋 Resposta JSON:")
            print(f"      Status: {cStat}")
            if xMotivo:
                print(f"      Motivo: {xMotivo}")

            # Extrair documentos do lote
            lote = data.get("LoteDFe", [])
            print(f"      Documentos no lote: {len(lote)}")

            sucessos = 0
            erros = 0
            for doc in lote:
                nsu = doc.get("NSU", "unknown")
                schema = doc.get("TipoDocumento", "")
                zip_b64 = doc.get("ArquivoXml", "")  # Campo correto da API ADN

                if not zip_b64:
                    print(f"  ⚠️  NSU {nsu}: sem dados XML")
                    erros += 1
                    continue

                try:
                    zip_bytes = base64.b64decode(zip_b64)
                    xml_bytes = gzip.decompress(zip_bytes)
                    xml_str = xml_bytes.decode("utf-8")

                    # Salvar XML
                    xml_file = output_dir / f"dfe_{company_id}_{nsu}.xml"
                    xml_file.write_text(xml_str, encoding="utf-8")
                    print(f"  💾 NSU {nsu} ({schema}): {len(xml_str)} bytes → {xml_file.name}")
                    sucessos += 1

                except Exception as e:
                    print(f"  ⚠️  Erro ao descompactar NSU {nsu}: {e}")
                    erros += 1

            print(f"\n   📊 Resumo: {sucessos} sucessos, {erros} erros")

            # Salvar resposta completa
            resp_file = output_dir / f"response_{company_id}_{ult_nsu}.json"
            resp_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"      💾 Resposta salva: {resp_file}")

        elif response.status_code == 404:
            print(f"   📋 Nenhum documento localizado para esta empresa no ADN")
            try:
                data = response.json()
                for erro in data.get("Erros", []):
                    print(f"      Erro: {erro.get('Descricao')}")
            except Exception:
                print(f"      Resposta: {response.text[:300]}")
        else:
            print(f"   ❌ Erro {response.status_code}: {response.text[:500]}")

        # === Teste 2: Consulta eventos por chave (exemplo com chave fake) ===
        print(f"\n📡 Teste 2: GET /NFSe/{{chave}}/Eventos (exemplo)")
        chave_exemplo = "00000000000000000000000000000000000000000000"
        url2 = f"{base_url}/NFSe/{chave_exemplo}/Eventos"
        response2 = await client.get(url2)
        print(f"   Status: {response2.status_code}")
        if response2.status_code == 200:
            try:
                data2 = response2.json()
                print(f"   Eventos encontrados: {len(data2.get('eventos', []))}")
            except Exception:
                print(f"   Resposta: {response2.text[:200]}")

        await client.aclose()

    finally:
        # Limpar certificados temporários
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"\n🧹 Certificados temporários removidos")
        except Exception:
            pass

    print("\n✅ Teste concluído!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Teste API ADN NFS-e")
    parser.add_argument("--company-id", type=int, default=11, help="ID da empresa no banco (default: 11)")
    parser.add_argument("--nsu", type=int, default=0, help="Último NSU conhecido (default: 0)")
    parser.add_argument("--ambiente", choices=["producao_restrita", "producao"], default="producaorestrita")
    args = parser.parse_args()

    asyncio.run(test_adn_consulta(args.company_id, args.nsu, args.ambiente))

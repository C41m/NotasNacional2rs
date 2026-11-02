#!/usr/bin/env python3
"""
PoC: Consultar Declaracoes Transmitidas do Simples Nacional (PGDAS-D)
via API oficial SERPRO Integra Contador — SEM browser, so httpx + mTLS.

Servico: PGDASD / CONSDECLARACAO13
Docs: https://apicenter.estaleiro.serpro.gov.br/documentacao/api-integra-contador/pt/quick_start/
Demo:  https://gateway.apiserpro.serpro.gov.br/integra-contador-trial/v1/Consultar

A API trial usa um Bearer de demonstracao e nao exige certificado — serve
para validar o formato do payload e da resposta. Producao exige
Consumer Key/Secret (contrato SERPRO) + e-CNPJ via mTLS.

Uso:
  python scripts/poc_consultar_declaracoes.py --ano 2026
  python scripts/poc_consultar_declaracoes.py --producao --company-id 11 --ano 2026
"""
import argparse
import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

TRIAL_URL = "https://gateway.apiserpro.serpro.gov.br/integra-contador-trial/v1/Consultar"
PROD_URL = "https://gateway.apiserpro.serpro.gov.br/integra-contador/v1/Consultar"
AUTH_URL = "https://autenticacao.sapi.serpro.gov.br/authenticate"
# Bearer de demonstracao publicado na documentacao oficial de cenarios
TRIAL_BEARER = "06aef429-a981-3ec5-a1f8-71d38d86481e"


def build_payload(cnpj: str, ano: str, pa: str | None = None):
    """CONSDECLARACAO13 — ano-calendario (ou periodo de apuracao)."""
    dados = {"anoCalendario": ano} if not pa else {"periodoApuracao": pa}
    return {
        "contratante": {"numero": cnpj, "tipo": 2},
        "autorPedidoDados": {"numero": cnpj, "tipo": 2},
        "contribuinte": {"numero": cnpj, "tipo": 2},
        "pedidoDados": {
            "idSistema": "PGDASD",
            "idServico": "CONSDECLARACAO13",
            "versaoSistema": "1.0",
            "dados": json.dumps(dados),
        },
    }


async def trial(ano: str, pa: str | None):
    payload = build_payload("00000000000000", ano, pa)
    print(f"=== TRIAL — PGDASD/CONSDECLARACAO13 (ano={ano}, pa={pa}) ===")
    print("Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    async with httpx.AsyncClient(timeout=90.0) as c:
        r = await c.post(
            TRIAL_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {TRIAL_BEARER}",
                "Content-Type": "application/json",
                "accept": "application/json",
            },
        )
    print(f"\nHTTP {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type')}")
    try:
        data = r.json()
        print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
        return data
    except Exception:
        print(r.text[:3000])
        return None


async def producao(cnpj: str, ano: str, pa: str | None, consumer_key: str, consumer_secret: str,
                   cert_path: Path, key_path: Path):
    import base64

    basic = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
    print(f"=== PRODUCAO — autenticando (CNPJ {cnpj}) ===")
    async with httpx.AsyncClient(
        cert=(str(cert_path), str(key_path)),
        verify=True,
        timeout=90.0,
    ) as c:
        r = await c.post(
            AUTH_URL,
            data={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {basic}",
                "role-type": "TERCEIROS",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
    print(f"authenticate -> HTTP {r.status_code}")
    if r.status_code != 200:
        print(r.text[:1500])
        print("\nSem token valido. Verifique Consumer Key/Secret e o certificado e-CNPJ "
              "(o certificado da contratacao deve ser o mesmo usado no SERPRO).")
        return None

    tok = r.json()
    print(f"expires_in={tok.get('expires_in')} token_type={tok.get('token_type')}")

    payload = build_payload(cnpj, ano, pa)
    async with httpx.AsyncClient(timeout=90.0) as c:
        r = await c.post(
            PROD_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {tok['access_token']}",
                "jwt_token": tok.get("jwt_token", ""),
                "Content-Type": "application/json",
                "accept": "application/json",
            },
        )
    print(f"\nConsultar -> HTTP {r.status_code}")
    try:
        data = r.json()
        print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
        return data
    except Exception:
        print(r.text[:2000])
        return None


def parse_declaracoes(data) -> None:
    """'dados' volta como string JSON dentro da resposta do gateway."""
    if not isinstance(data, dict):
        return
    raw = data.get("dados")
    if not raw:
        print("\n(sem campo 'dados')")
        return
    try:
        inner = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        print(f"\ndados (nao-JSON): {str(raw)[:800]}")
        return

    print("\n=== Declaracoes encontradas ===")
    if isinstance(inner, dict):
        for k, v in inner.items():
            if isinstance(v, list):
                print(f"{k}: {len(v)} item(ns)")
                for it in v[:14]:
                    print("   ", json.dumps(it, ensure_ascii=False)[:220])
            else:
                print(f"{k}: {json.dumps(v, ensure_ascii=False)[:200]}")
    elif isinstance(inner, list):
        print(f"{len(inner)} item(ns)")
        for it in inner[:14]:
            print("   ", json.dumps(it, ensure_ascii=False)[:240])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", default="2026")
    ap.add_argument("--pa", default=None, help="periodo de apuracao YYYYMM")
    ap.add_argument("--producao", action="store_true")
    ap.add_argument("--company-id", type=int, default=11)
    ap.add_argument("--consumer-key", default="")
    ap.add_argument("--consumer-secret", default="")
    a = ap.parse_args()

    if not a.producao:
        data = await trial(a.ano, a.pa)
        parse_declaracoes(data)
        return

    from app.core.database import SessionLocal
    from app.models.company import Company
    from app.services.certificate_service import get_certificate_pem
    from sqlalchemy import select

    db = SessionLocal()
    try:
        comp = db.execute(select(Company).where(Company.id == a.company_id)).scalar_one_or_none()
        cert_pem, key_pem, _pw = get_certificate_pem(db, a.company_id)
    finally:
        db.close()

    cnpj = comp.cnpj if comp else ""
    print(f"empresa={comp.nome if comp else '?'} cnpj={cnpj}")

    tmp = Path(tempfile.mkdtemp(prefix="serpro_"))
    try:
        cp, kp = tmp / "cert.pem", tmp / "key.pem"
        cp.write_bytes(cert_pem)
        kp.write_bytes(key_pem)
        data = await producao(cnpj, a.ano, a.pa, a.consumer_key, a.consumer_secret, cp, kp)
        parse_declaracoes(data)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
#!/usr/bin/env python3
"""
Existe caminho para consultar/transmitir PGDAS-D SEM a API do SERPRO?

O unico host confirmado que exige certificado de cliente no handshake e
'certificado.sso.acesso.gov.br' (gov.br). Este script tenta completar o
fluxo de autenticacao por certificado e usar a sessao resultante no e-CAC.

Passos:
  1. Handshake mTLS real no host do SSO de certificado
  2. Varre endpoints de autenticacao por certificado
  3. Verifica se algum devolve token/sessao (e nao tela de login)
  4. Tenta reutilizar a sessao no portal do Simples / e-CAC
"""
import shutil
import socket
import ssl
import sys
import tempfile
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# endpoints candidatos de autenticacao por certificado no SSO
SSO_ENDPOINTS = [
    ("cert_root", "https://certificado.sso.acesso.gov.br/"),
    ("cert_auth", "https://certificado.sso.acesso.gov.br/autenticar"),
    ("cert_login", "https://certificado.sso.acesso.gov.br/login"),
    ("cert_x509", "https://certificado.sso.acesso.gov.br/x509"),
    ("sso_cert", "https://sso.acesso.gov.br/autenticacao/certificado"),
    ("sso_cert2", "https://sso.acesso.gov.br/certificado"),
    ("sso_x509", "https://sso.acesso.gov.br/autenticacao/x509"),
    ("sso_acesso", "https://servicos.acesso.gov.br/"),
    ("sso_select", "https://sso.acesso.gov.br/autenticacao/select-login"),
    ("sso_index", "https://sso.acesso.gov.br/"),
]

# alvos onde a sessao seria reaproveitada
REUSE = [
    ("simples_www8", "https://www8.receita.fazenda.gov.br/SimplesNacional/Default.aspx"),
    ("cav_login", "https://cav.receita.fazenda.gov.br/autenticacao/login"),
]


def mtls_handshake(host: str, cp: Path, kp: Path) -> str:
    """Handshake exigindo client cert (verifica se a CA realmente exige)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.load_cert_chain(certfile=str(cp), keyfile=str(kp))
    try:
        with socket.create_connection((host, 443), timeout=30) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as s:
                # did we actually present a cert? peer sees it, but we can
                # check if the handshake negotiated a client cert slot
                return f"OK {s.version()} {s.cipher()[0]}"
    except ssl.SSLError as e:
        return f"SSLError: {e}"
    except Exception as e:
        return f"{type(e).__name__}: {str(e)[:100]}"


def main():
    from app.core.database import SessionLocal
    from app.services.certificate_service import get_certificate_pem
    db = SessionLocal()
    try:
        cert_pem, key_pem, _pw = get_certificate_pem(db, 11)
    finally:
        db.close()

    tmp = Path(tempfile.mkdtemp(prefix="sso_"))
    cp, kp = tmp / "cert.pem", tmp / "key.pem"
    cp.write_bytes(cert_pem)
    kp.write_bytes(key_pem)

    try:
        # --- 1) handshake mTLS ---
        print("=== 1) handshake mTLS em certificado.sso.acesso.gov.br ===")
        print(f"  {mtls_handshake('certificado.sso.acesso.gov.br', cp, kp)}")

        # --- 2) varredura de endpoints ---
        print("\n=== 2) endpoints de autenticacao por certificado ===")
        melhor = None
        with httpx.Client(cert=(str(cp), str(kp)), verify=True, timeout=40.0,
                          follow_redirects=False,
                          headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"}) as c:
            for nome, url in SSO_ENDPOINTS:
                try:
                    r = c.get(url)
                except Exception as e:
                    print(f"  {nome:<14} ERRO {type(e).__name__}: {str(e)[:80]}")
                    continue
                loc = r.headers.get("location", "")
                body = r.text
                low = body.lower()
                # token/sessao = sinal de autenticacao bem-sucedida
                tem_token = any(k in low for k in
                                ("id_token", "access_token", "jwt", "authorization_code",
                                 "saml", "\"token\""))
                tem_login = any(k in low for k in
                                ("entrar", "login", "cpf", "senha", "captcha"))
                print(f"  {nome:<14} {r.status_code} len={len(r.content)} "
                      f"{'TOKEN!' if tem_token else ('login' if tem_login else '')}"
                      f"{' -> ' + loc[:60] if loc else ''}")
                for ck in r.headers.get_list("set-cookie")[:4]:
                    print(f"       cookie: {ck[:100]}")
                if tem_token:
                    melhor = (nome, url, body)

        if melhor:
            print(f"\n  >>> candidato com token: {melhor[0]} {melhor[1]}")
            print(f"  body: {' '.join(melhor[2].split())[:500]}")
        else:
            print("\n  >>> Nenhum endpoint devolveu token/sessao.")

        # --- 3) tentar reutilizar sessao no portal do Simples ---
        print("\n=== 3) reutilizar sessao (cookie jar) no portal do Simples / e-CAC ===")
        with httpx.Client(cert=(str(cp), str(kp)), verify=False, timeout=45.0,
                          follow_redirects=True,
                          headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9"}) as c:
            # popula o jar percorrendo o SSO
            for _nome, url in SSO_ENDPOINTS[:4]:
                try:
                    c.get(url)
                except Exception:
                    pass
            print(f"  cookies coletados: {list(c.cookies.keys())}")

            for nome, url in REUSE:
                try:
                    r = c.get(url)
                except Exception as e:
                    print(f"  {nome:<14} ERRO {type(e).__name__}: {str(e)[:90]}")
                    continue
                low = r.text.lower()
                print(f"  {nome:<14} {r.status_code} len={len(r.content)} final={str(r.url)[:80]}")
                marks = sorted({m for m in ("nao autenticado", "não autenticado",
                                            "acesso negado", "captcha", "hcaptcha",
                                            "sessao expirada", "cnpj", "pgdas",
                                            "declaracao", "menu", "sair")
                                if m in low})
                print(f"      markers: {marks}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
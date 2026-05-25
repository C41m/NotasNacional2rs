import asyncio

from playwright.async_api import async_playwright, Browser
from typing import Optional, Tuple, Dict, Any
import tempfile
import os


# Configurações do Chromium — headless para economizar CPU/memória no servidor
CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-setuid-sandbox",
]

CHROMIUM_KWARGS = dict(
    headless=True,
    args=CHROMIUM_ARGS,
)

# Máximo de browsers simultâneos (~150MB cada, 2 = ~300MB total — seguro no Render free)
MAX_CONCURRENT_BROWSERS = 2


async def launch_dedicated_browser() -> Tuple[async_playwright, Browser]:
    """
    Inicia um processo Chromium dedicado para uma task.
    Retorna (playwright, browser) — o chamador é responsável por fechar ambos.
    """
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(**CHROMIUM_KWARGS)
    return pw, browser


async def create_mtls_context(
    browser: Browser,
    cert_pem: bytes,
    key_pem: bytes,
    password: Optional[str] = None,
) -> Tuple:
    """
    Cria um BrowserContext isolado com certificado mTLS no browser indicado.
    """
    cert_fd, cert_path = tempfile.mkstemp(suffix=".pem")
    key_fd, key_path = tempfile.mkstemp(suffix=".pem")

    try:
        with os.fdopen(cert_fd, "wb") as f:
            f.write(cert_pem)
        with os.fdopen(key_fd, "wb") as f:
            f.write(key_pem)

        context = await browser.new_context(
            client_certificates=[{
                "origin": "https://www.nfse.gov.br",
                "certPath": cert_path,
                "keyPath": key_path,
                **({"passphrase": password} if password else {})
            }],
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            ignore_https_errors=False,
            java_script_enabled=True
        )

        return context, cert_path, key_path
    except Exception:
        # Limpa arquivos temporários em caso de erro
        if os.path.exists(cert_path):
            os.unlink(cert_path)
        if os.path.exists(key_path):
            os.unlink(key_path)
        raise


async def close_browser(pw: async_playwright, browser: Browser):
    """Fecha o browser e o playwright de forma segura."""
    if browser and browser.is_connected():
        await browser.close()
    if pw:
        await pw.stop()
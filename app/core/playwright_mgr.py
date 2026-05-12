import asyncio

from playwright.async_api import async_playwright, Browser
from typing import Optional, Tuple
import tempfile
import os


# Configurações do Chromium — usadas tanto para browser singleton quanto para contexts
CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-setuid-sandbox",
]

CHROMIUM_KWARGS = dict(
    headless=False,
    args=CHROMIUM_ARGS,
)


async def get_shared_browser() -> Browser:
    """
    Retorna um browser singleton compartilhado (um único processo Chromium).
    Cria o browser se ainda não existir no event loop atual.
    """
    loop = asyncio.get_running_loop()
    key = "_shared_browser"

    if not hasattr(loop, key):
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(**CHROMIUM_KWARGS)
        # Armazena browser e playwright para cleanup posterior
        setattr(loop, key, browser)
        setattr(loop, "_shared_playwright", playwright)

    return getattr(loop, key)


async def close_shared_browser():
    """Fecha o browser singleton do event loop atual."""
    loop = asyncio.get_running_loop()
    browser = getattr(loop, "_shared_browser", None)
    playwright = getattr(loop, "_shared_playwright", None)

    if browser and browser.is_connected():
        await browser.close()
    if playwright:
        await playwright.stop()

    for attr in ("_shared_browser", "_shared_playwright"):
        if hasattr(loop, attr):
            delattr(loop, attr)


async def create_mtls_context_from_browser(
    browser: Browser,
    cert_pem: bytes,
    key_pem: bytes,
    password: Optional[str] = None,
) -> Tuple:
    """
    Cria um BrowserContext isolado com certificado mTLS.
    Muito mais leve que criar um novo browser — compartilha o mesmo processo Chromium.
    """
    cert_fd, cert_path = tempfile.mkstemp(suffix=".pem")
    key_fd, key_path = tempfile.mkstemp(suffix=".pem")

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
    )

    return context, cert_path, key_path


async def create_mtls_context(cert_pem: bytes, key_pem: bytes, password: Optional[str] = None) -> Tuple:
    """
    API backward-compatible: cria contexto mTLS a partir do browser singleton.
    """
    browser = await get_shared_browser()
    return await create_mtls_context_from_browser(browser, cert_pem, key_pem, password)
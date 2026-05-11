import sys
import asyncio

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright, Browser, BrowserContext
from typing import Optional, Tuple
import tempfile
import os

_browser: Optional[Browser] = None

async def get_browser() -> Browser:
    """Singleton headless Chromium instance."""
    global _browser
    if _browser is None or not _browser.is_connected():
        loop = asyncio.get_event_loop()
        if sys.platform.startswith("win") and not isinstance(loop, asyncio.ProactorEventLoop):
            loop.close()
            asyncio.set_event_loop(asyncio.ProactorEventLoop())
            loop = asyncio.get_event_loop()
        playwright = await async_playwright().start()
        _browser = await playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
    return _browser

async def create_mtls_context(cert_pem: bytes, key_pem: bytes, password: Optional[str] = None) -> Tuple[BrowserContext, str, str]:
    """Create browser context with mTLS client certificate."""
    browser = await get_browser()

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
        timezone_id="America/Sao_Paulo"
    )

    return context, cert_path, key_path

async def close_browser():
    """Cleanup browser on shutdown."""
    global _browser
    if _browser:
        await _browser.close()
        _browser = None

import sys
import asyncio
import threading

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright, Browser, BrowserContext
from typing import Optional, Tuple
import tempfile
import os

# Thread-local storage for browser instances
_thread_local = threading.local()

async def _get_browser() -> Browser:
    """Get or create browser instance for current thread."""
    thread_id = threading.current_thread().ident
    if not hasattr(_thread_local, 'browsers'):
        _thread_local.browsers = {}

    browser_key = f"browser_{thread_id}"
    browser = _thread_local.browsers.get(browser_key)

    if browser is None or not browser.is_connected():
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
            ]
        )
        _thread_local.browsers[browser_key] = browser

        # Store playwright for cleanup
        _thread_local.browsers[f"playwright_{thread_id}"] = playwright

    return browser

async def create_mtls_context(cert_pem: bytes, key_pem: bytes, password: Optional[str] = None) -> Tuple[BrowserContext, str, str]:
    """Create browser context with mTLS client certificate."""
    browser = await _get_browser()

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
    """Cleanup browser for current thread."""
    thread_id = threading.current_thread().ident
    if hasattr(_thread_local, 'browsers'):
        browser = _thread_local.browsers.pop(f"browser_{thread_id}", None)
        playwright = _thread_local.browsers.pop(f"playwright_{thread_id}", None)

        if browser and browser.is_connected():
            await browser.close()
        if playwright:
            await playwright.stop()
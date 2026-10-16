import re
import asyncio
from playwright.async_api import BrowserContext, Download, Browser, TimeoutError as PlaywrightTimeoutError
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.playwright_mgr import create_mtls_context
from app.models.download_job import DownloadJob
from app.models.company import Company
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
import tempfile, os, zipfile, shutil
from datetime import datetime


async def handle_captcha_if_present(page, timeout: int = 60) -> bool:
    """Detecta e tenta resolver CAPTCHA 'Sou humano' se presente.
    Retorna True se resolveu, False se não havia CAPTCHA."""
    
    # Verifica se há alerta de CAPTCHA
    alert = await page.query_selector("div.alert-info")
    if not alert:
        return False
    
    text = await alert.inner_text() or ""
    if "Sou humano" not in text and "desafio" not in text.lower() and "recaptcha" not in text.lower():
        return False
    
    print("[CAPTCHA] Detectado! Tentando resolver...")
    
    # Tenta clicar no "Sou humano" (checkbox)
    human_btn = await page.query_selector("div.alert-info input[type=checkbox], div.alert-info button, div.alert-info a")
    if human_btn:
        tag = await human_btn.evaluate("el => el.tagName")
        # Verifica se é o botão de "Sou humano"
        btn_text = (await human_btn.inner_text() or "").lower()
        if "sou humano" in btn_text or "humano" in btn_text or tag == "BUTTON":
            await human_btn.click()
            print("[CAPTCHA] Clicou em 'Sou humano'")
            await page.wait_for_timeout(2000)
    
    # Aguarda o alerta desaparecer (resolvido)
    start = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start) < timeout:
        try:
            await page.wait_for_selector("div.alert-info", state="hidden", timeout=1000)
            print("[CAPTCHA] Resolvido!")
            return True
        except:
            # Ainda está visível, continua aguardando
            # Clica novamente no botão se aparecer novo
            new_btn = await page.query_selector("div.alert-info button:not([disabled]), div.alert-info a")
            if new_btn:
                await new_btn.click()
                print("[CAPTCHA] Clicou em botão dentro do alerta")
            await page.wait_for_timeout(1000)
    
    # Timeout - salva screenshot
    screenshot_path = os.path.join(tempfile.gettempdir(), f"nfse_captcha_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
    await page.screenshot(path=screenshot_path, full_page=True)
    print(f"[CAPTCHA] Timeout ao resolver. Screenshot salvo em: {screenshot_path}")
    return False


class NFSeBotError(Exception):
    pass


async def run_nfse_download_async(
    company_id: int,
    job_id: str,
    db: Session,
    cert_pem: bytes,
    key_pem: bytes,
    cert_password: str,
    browser: Browser,
    batch_status: dict | None = None,
    batch_id: str | None = None,
    datainicio: str = "01/04/2026",
    datafim: str = "30/04/2026",
    download_type: str = "xml",
    progress_callback=None,
):
    """Execute NFSe download com mTLS e retry logic, usando o browser dedicado recebido."""
    context = None
    temp_dir = None
    zip_path = None
    cert_path = None
    key_path = None

    try:
        # Update job to processing
        job = db.execute(select(DownloadJob).where(DownloadJob.id == job_id)).scalar_one()
        job.status = "processing"
        job.started_at = datetime.utcnow()
        job.download_type = download_type
        db.commit()

        # Fetch company CNPJ for isolated temp directory
        company = db.execute(select(Company).where(Company.id == company_id)).scalar_one()
        cnpj = company.cnpj.replace(".", "").replace("/", "").replace("-", "")

        # Definir caminho do ZIP com CNPJ e datas
        jobs_dir = os.path.join(tempfile.gettempdir(), "jobs")
        os.makedirs(jobs_dir, exist_ok=True)
        zip_path = os.path.join(
            jobs_dir,
            f"NFSe_{cnpj}_{datainicio.replace('/', '-')}_{datafim.replace('/', '-')}.zip"
        )
        if os.path.exists(zip_path):
            os.remove(zip_path)

        temp_dir = os.path.join(tempfile.gettempdir(), "nfse_downloads", cnpj, job_id)
        os.makedirs(temp_dir, exist_ok=True)

        # Cria contexto mTLS no browser dedicado (sem contenção com outras tasks)
        context, cert_path, key_path = await create_mtls_context(
            browser, cert_pem, key_pem, cert_password,
            origins=[
                "https://www.nfse.gov.br",
                "https://certificado.nfse.gov.br",
            ]
        )
        page = await context.new_page()

        await page.goto("https://www.nfse.gov.br/EmissorNacional/", timeout=30000)
        await page.wait_for_selector("a.img-certificado", timeout=30000)
        await page.click("a.img-certificado")
        await page.wait_for_load_state("networkidle", timeout=15000)
        
        # Verifica se há CAPTCHA após clicar no certificado
        captcha_ok = await handle_captcha_if_present(page, timeout=120)
        if not captcha_ok:
            print("[CAPTCHA] Não resolvido, tentando continuar mesmo assim...")
        
        await page.goto("https://www.nfse.gov.br/EmissorNacional/Notas/Emitidas", timeout=30000)
        
        # Segunda verificação de CAPTCHA (pode aparecer na página de notas também)
        captcha_ok2 = await handle_captcha_if_present(page, timeout=120)
        if not captcha_ok2:
            print("[CAPTCHA] CAPTCHA persistiu na página de notas")

        await page.wait_for_selector("#datainicio", timeout=15000)
        await page.wait_for_selector("#datafim", timeout=15000)
        await page.fill("#datainicio", datainicio)
        await page.fill("#datafim", datafim)
        await page.click("#searchbar > form > div:nth-child(3) > div:nth-child(2) > div:nth-child(2) > button")

        total_registros = 0
        try:
            await page.wait_for_selector("div.paginacao div.descricao", timeout=5000)
            paginacao_text = await page.locator("div.paginacao div.descricao").inner_text()
            print(f"[DEBUG] Paginação text: {paginacao_text}")
            match = re.search(r'Total de (\d+) registros', paginacao_text)
            if match:
                total_registros = int(match.group(1))
                job.total_registros = total_registros
            else:
                print(f"[WARN] Pattern não encontrado no texto de paginação")
        except Exception as e:
            print(f"[WARN] Erro ao buscar total de registros: {e}")
        local_count = 0
        try:
            pagina_atual = 1
            while True:
                # Verifica se o batch foi cancelado
                if batch_status and batch_status.get(batch_id, {}).get("cancelled"):
                    print(f"[Batch {batch_id}] Cancelamento solicitado, encerrando...")
                    batch_status[batch_id]["status"] = "cancelled"
                    batch_status[batch_id]["error"] = "Cancelado pelo usuário"
                    job.status = "cancelled"
                    job.error_message = "Cancelado pelo usuário"
                    job.finished_at = datetime.utcnow()
                    db.commit()
                    return None

                await page.wait_for_selector("div.container.container-fluid-xl.container-body table tbody tr", timeout=5000)

                rows = await page.locator("div.container.container-fluid-xl.container-body table tbody tr").all()
                num_rows = len(rows)

                for i in range(num_rows):
                    await page.evaluate("document.querySelectorAll('.popover').forEach(e => e.remove())")
                    row = page.locator("div.container.container-fluid-xl.container-body table tbody tr").nth(i)
                    options_btn = row.locator("a.icone-trigger").first
                    if await options_btn.count() == 0:
                        options_btn = row.locator("td.td-opcoes a").first
                    if await options_btn.count() == 0:
                        continue
                    await options_btn.click()
                    try:
                        # Determina o tipo de download
                        is_xml = download_type in ("xml", "both")
                        is_pdf = download_type in ("pdf", "both")

                        # Obtém número da nota
                        xml_link = page.locator("div.popover:visible a:has-text('Download XML')").first
                        href = None
                        nf_num = "unknown"
                        if await xml_link.count() > 0:
                            href = await xml_link.get_attribute("href")
                        else:
                            # Para PDF pode haver só DANFS-e
                            pdf_link = page.locator("div.popover:visible a:has-text('Download DANFS-e')").first
                            if await pdf_link.count() == 0:
                                continue
                            await pdf_link.wait_for(state="visible", timeout=3000)

                        if href:
                            match = re.search(r'/NFSe/(\d+)', href)
                            if match:
                                nf_num = match.group(1)

                        # Download XML (se solicitado)
                        if is_xml:
                            download = None
                            dest_path = None
                            initial_pages = len(page.context.pages)

                            try:
                                async with page.expect_download() as download_info:
                                    await xml_link.click()
                                download = await download_info.value
                            except Exception:
                                print("Download XML falhou, tentando via popup")
                                await xml_link.click()
                                try:
                                    await page.wait_for_selector("div.popover:visible", timeout=2000)
                                except Exception:
                                    pass

                            if download is None and len(page.context.pages) > initial_pages:
                                popup = page.context.pages[-1]
                                try:
                                    await popup.wait_for_load_state("networkidle", timeout=3000)
                                    content = await popup.content()
                                    dest_path = os.path.join(temp_dir, f"NFSe_{nf_num}.xml")
                                    with open(dest_path, "w", encoding="utf-8") as f:
                                        f.write(content)
                                    await popup.close()
                                except Exception:
                                    pass

                            if download and dest_path is None:
                                dest_path = os.path.join(temp_dir, f"NFSe_{nf_num}.xml")
                                try:
                                    await download.save_as(dest_path)
                                except Exception:
                                    dest_path = None

                        # Download PDF/DANFS-e (se solicitado)
                        if is_pdf:
                            # Reabre o popover pois pode ter fechado após o download do XML
                            await options_btn.click()
                            await page.wait_for_selector("div.popover:visible", timeout=3000)

                            pdf_link = page.locator("div.popover:visible a:has-text('Download DANFS-e')").first
                            if await pdf_link.count() > 0:
                                try:
                                    await pdf_link.wait_for(state="visible", timeout=3000)
                                    pdf_download = None
                                    initial_pages = len(page.context.pages)
                                    try:
                                        async with page.expect_download() as download_info:
                                            await pdf_link.click()
                                        pdf_download = await download_info.value
                                    except Exception:
                                        print("Download PDF falhou, tentando via popup")
                                        await pdf_link.click()

                                    if pdf_download:
                                        pdf_path = os.path.join(temp_dir, f"NFSe_{nf_num}.pdf")
                                        try:
                                            await pdf_download.save_as(pdf_path)
                                        except Exception:
                                            pass

                                except Exception as pdf_err:
                                    print(f"Erro no download PDF: {pdf_err}")

                        if is_xml or is_pdf:
                            local_count += 1
                            # Fecha o popover antes da próxima iteração
                            await page.evaluate("document.querySelectorAll('.popover').forEach(e => e.remove())")
                            if progress_callback:
                                await progress_callback(company_id, local_count, total_registros or 0)
                    except Exception as e:
                        print(f"Erro no download XML: {e}")

                next_li = page.locator("div.paginacao div.indice ul li").nth(-2)
                if await next_li.count() > 0:
                    classes = await next_li.get_attribute("class") or ""
                    if "disabled" not in classes:
                        next_btn = next_li.locator("a").first
                        await next_btn.click()
                        await page.wait_for_load_state("networkidle", timeout=5000)
                        pagina_atual += 1
                    else:
                        break
                else:
                    break

        except Exception as e:
            print(f"Erro ao processar registros: {e}")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    path = os.path.join(root, file)
                    zipf.write(path, os.path.relpath(path, temp_dir))

        job.status = "success"
        job.file_url = zip_path
        job.notas_processed = local_count
        job.datainicio = datainicio
        job.datafim = datafim
        job.finished_at = datetime.utcnow()
        db.commit()

        return zip_path

    except Exception as e:
        job = db.execute(select(DownloadJob).where(DownloadJob.id == job_id)).scalar_one_or_none()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        if context:
            await context.close()
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        if 'cert_path' in locals() and os.path.exists(cert_path):
            os.unlink(cert_path)
        if 'key_path' in locals() and os.path.exists(key_path):
            os.unlink(key_path)
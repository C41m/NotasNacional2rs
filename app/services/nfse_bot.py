import re
import asyncio
from playwright.async_api import BrowserContext, Download
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.playwright_mgr import create_mtls_context
from app.models.download_job import DownloadJob
from app.models.company import Company
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
import tempfile, os, zipfile, shutil
from datetime import datetime

class NFSeBotError(Exception):
    pass

async def run_nfse_download_async(company_id: int, job_id: str, db: Session, cert_pem: bytes, key_pem: bytes, cert_password: str, datainicio: str = "01/04/2026", datafim: str = "30/04/2026", progress_callback=None):
    """Execute NFSe download with mTLS and retry logic."""
    context = None
    temp_dir = None
    zip_path = None

    try:
        # Update job to processing
        job = db.execute(select(DownloadJob).where(DownloadJob.id == job_id)).scalar_one()
        job.status = "processing"
        job.started_at = datetime.utcnow()
        db.commit()

        # Fetch company CNPJ for isolated temp directory
        company = db.execute(select(Company).where(Company.id == company_id)).scalar_one()
        cnpj = company.cnpj.replace(".", "").replace("/", "").replace("-", "")

        # Definir caminho do ZIP com CNPJ e datas
        zip_path = os.path.join(
            tempfile.gettempdir(), "jobs",
            f"NFSe_{cnpj}_{datainicio.replace('/', '-')}_{datafim.replace('/', '-')}.zip"
        )
        if os.path.exists(zip_path):
            os.remove(zip_path)

        temp_dir = os.path.join(tempfile.gettempdir(), "nfse_downloads", cnpj, job_id)
        os.makedirs(temp_dir, exist_ok=True)

        context, cert_path, key_path = await create_mtls_context(cert_pem, key_pem, cert_password)
        page = await context.new_page()

        await page.goto("https://www.nfse.gov.br/EmissorNacional/Login?ReturnUrl=%2fEmissorNacional", timeout=30000)
        await page.wait_for_selector("a.img-certificado", timeout=15000)
        await page.click("a.img-certificado")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.goto("https://www.nfse.gov.br/EmissorNacional/Notas/Emitidas", timeout=30000)

        await page.wait_for_selector("#datainicio", timeout=15000)
        await page.wait_for_selector("#datafim", timeout=15000)
        await page.fill("#datainicio", datainicio)
        await page.fill("#datafim", datafim)
        await page.click("#searchbar > form > div:nth-child(3) > div:nth-child(2) > div:nth-child(2) > button")

        try:
            await page.wait_for_selector("div.paginacao div.descricao", timeout=10000)
            paginacao_text = await page.locator("div.paginacao div.descricao").inner_text()
            match = re.search(r'Total de (\d+) registros', paginacao_text)
            if match:
                total_registros = int(match.group(1))
                job.total_registros = total_registros
                db.commit()
        except Exception:
            pass

        total_registros = getattr(job, 'total_registros', 0) or 0
        try:
            pagina_atual = 1
            while True:
                await page.wait_for_selector("div.container.container-fluid-xl.container-body table tbody tr", timeout=15000)
                await page.wait_for_timeout(1000)

                rows = await page.locator("div.container.container-fluid-xl.container-body table tbody tr").all()
                num_rows = len(rows)

                for i in range(num_rows):
                    await page.evaluate("document.querySelectorAll('.popover').forEach(e => e.remove())")
                    await page.wait_for_timeout(200)
                    row = page.locator("div.container.container-fluid-xl.container-body table tbody tr").nth(i)
                    options_btn = row.locator("a.icone-trigger").first
                    if await options_btn.count() == 0:
                        options_btn = row.locator("td.td-opcoes a").first
                    if await options_btn.count() == 0:
                        continue
                    await options_btn.click()
                    await page.wait_for_timeout(300)
                    try:
                        xml_link = page.locator("div.popover:visible a:has-text('Download XML')").first
                        await xml_link.wait_for(state="visible", timeout=3000)
                        href = await xml_link.get_attribute("href")
                        nf_num = "unknown"
                        if href:
                            match = re.search(r'/NFSe/(\d+)', href)
                            if match:
                                nf_num = match.group(1)
                        async with page.expect_download(timeout=10000) as download_info:
                            await xml_link.click()
                        download = await download_info.value
                        suggested_name = download.suggested_filename or f"NFSe_{nf_num}.xml"
                        if not suggested_name.lower().endswith('.xml'):
                            suggested_name = f"NFSe_{nf_num}.xml"
                        dest_path = os.path.join(temp_dir, suggested_name)
                        await download.save_as(dest_path)
                        if os.path.exists(dest_path):
                            job.notas_processed = (job.notas_processed or 0) + 1
                            db.commit()
                            if progress_callback:
                                await progress_callback(company_id, job.notas_processed, total_registros or 0)
                    except Exception as e:
                        print(f"Erro no download XML: {e}")

                next_li = page.locator("div.paginacao div.indice ul li").nth(-2)
                if await next_li.count() > 0:
                    classes = await next_li.get_attribute("class") or ""
                    if "disabled" not in classes:
                        next_btn = next_li.locator("a").first
                        await next_btn.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)
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

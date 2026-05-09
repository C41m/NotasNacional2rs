import re
from playwright.async_api import BrowserContext, Download
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.playwright_mgr import create_mtls_context
from app.models.download_job import DownloadJob
from app.models.company import Company
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import tempfile, os, zipfile, shutil
from datetime import datetime

class NFSeBotError(Exception):
    pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=4, max=10), reraise=True)
async def run_nfse_download(company_id: int, job_id: str, db: AsyncSession, cert_pem: bytes, key_pem: bytes, cert_password: str, datainicio: str = "01/04/2026", datafim: str = "30/04/2026", progress_callback=None):
    """Execute NFSe download with mTLS and retry logic."""
    context = None
    temp_dir = None
    zip_path = None

    try:
        # Update job to processing
        result = await db.execute(select(DownloadJob).where(DownloadJob.id == job_id))
        job = result.scalar_one()
        job.status = "processing"
        job.started_at = datetime.utcnow()
        await db.commit()

        # Fetch company CNPJ for isolated temp directory
        company_result = await db.execute(select(Company).where(Company.id == company_id))
        company = company_result.scalar_one()
        cnpj = company.cnpj.replace(".", "").replace("/", "").replace("-", "")

        # Definir caminho do ZIP com CNPJ e datas
        zip_path = os.path.join(
            tempfile.gettempdir(), "jobs",
            f"NFSe_{cnpj}_{datainicio.replace('/', '-')}_{datafim.replace('/', '-')}.zip"
        )
        # Remover ZIP anterior se existir (substituir)
        if os.path.exists(zip_path):
            os.remove(zip_path)

        # Pasta isolada por empresa e job (evita conflito entre instâncias)
        temp_dir = os.path.join(tempfile.gettempdir(), "nfse_downloads", cnpj, job_id)
        os.makedirs(temp_dir, exist_ok=True)

        # Create mTLS browser context
        context, cert_path, key_path = await create_mtls_context(cert_pem, key_pem, cert_password)
        page = await context.new_page()

        # Não usar event listener - downloads são via navegação direta
        # Usar page.expect_download() no momento do clique

        # Navigate to login (mTLS auto-authenticates)
        await page.goto("https://www.nfse.gov.br/EmissorNacional/Login?ReturnUrl=%2fEmissorNacional", timeout=30000)
        
        # Wait for and click on certificate link
        await page.wait_for_selector("a.img-certificado", timeout=15000)
        await page.click("a.img-certificado")

        # Wait for navigation or content load after click
        await page.wait_for_load_state("networkidle", timeout=15000)
        
        # Navegar para tela de emitidas
        await page.goto("https://www.nfse.gov.br/EmissorNacional/Notas/Emitidas", timeout=30000)

        # Preencher dados de data
        await page.wait_for_selector("#datainicio", timeout=15000)
        await page.wait_for_selector("#datafim", timeout=15000)

        await page.fill("#datainicio", datainicio)
        await page.fill("#datafim", datafim)
        
        await page.click("#searchbar > form > div:nth-child(3) > div:nth-child(2) > div:nth-child(2) > button")

        # Extrair total de registros da paginação
        try:
            await page.wait_for_selector("div.paginacao div.descricao", timeout=10000)
            paginacao_text = await page.locator("div.paginacao div.descricao").inner_text()
            match = re.search(r'Total de (\d+) registros', paginacao_text)
            if match:
                total_registros = int(match.group(1))
                job.total_registros = total_registros
                await db.commit()
        except Exception:
            pass  # Não bloqueia se não encontrar

        # Iterar sobre cada registro e baixar XML
        try:
            pagina_atual = 1
            while True:
                # Aguardar carregamento da tabela
                await page.wait_for_selector("div.container.container-fluid-xl.container-body table tbody tr", timeout=15000)
                await page.wait_for_timeout(1000)  # Garantir renderização

                # Obter todas as linhas da tabela na página atual
                rows = await page.locator("div.container.container-fluid-xl.container-body table tbody tr").all()
                num_rows = len(rows)

                for i in range(num_rows):
                    # Fechar qualquer popover aberto da iteração anterior
                    await page.evaluate("document.querySelectorAll('.popover').forEach(e => e.remove())")
                    await page.wait_for_timeout(200)

                    # Re-obter a linha por índice para evitar stale element
                    row = page.locator("div.container.container-fluid-xl.container-body table tbody tr").nth(i)

                    # Localizar botão de opções (três pontos verticais)
                    # Usar seletor específico para o trigger do popover
                    options_btn = row.locator("a.icone-trigger").first
                    if await options_btn.count() == 0:
                        options_btn = row.locator("td.td-opcoes a").first
                    if await options_btn.count() == 0:
                        continue

                    # Abrir popover de opções
                    await options_btn.click()
                    await page.wait_for_timeout(300)

                    # Clicar em "Download XML" pelo texto (independente da ordem)
                    try:
                        xml_link = page.locator("div.popover:visible a:has-text('Download XML')").first
                        await xml_link.wait_for(state="visible", timeout=3000)

                        # Extrair número da NFSe da URL do link
                        href = await xml_link.get_attribute("href")
                        nf_num = "unknown"
                        if href:
                            match = re.search(r'/NFSe/(\d+)', href)
                            if match:
                                nf_num = match.group(1)

                        # Clicar no link e capturar o download (NÃO fechar popover antes)
                        async with page.expect_download(timeout=10000) as download_info:
                            await xml_link.click()
                        download = await download_info.value

                        # Garanta nome e extensão corretos
                        suggested_name = download.suggested_filename or f"NFSe_{nf_num}.xml"
                        if not suggested_name.lower().endswith('.xml'):
                            suggested_name = f"NFSe_{nf_num}.xml"

                        dest_path = os.path.join(temp_dir, suggested_name)
                        await download.save_as(dest_path)

                        # Validação pós-download (debug)
                        if os.path.exists(dest_path):
                            file_size = os.path.getsize(dest_path)
                            print(f"✓ Download salvo: {dest_path} ({file_size} bytes)")
                            if file_size == 0:
                                print(f"⚠️ Arquivo vazio! URL do download: {download.url}")

                            # Atualizar contador de notas processadas no job
                            job.notas_processed = (job.notas_processed or 0) + 1
                            await db.commit()

                            # Chamar callback de progresso (se fornecido)
                            if progress_callback:
                                await progress_callback(company_id, job.notas_processed, total_registros or 0)
                        else:
                            print(f"❌ Arquivo não foi salvo em: {dest_path}")
                            
                    except Exception as e:
                        print(f"Erro no download XML: {e}")

                # Verificar se há próxima página
                # Penúltimo li = "Próxima", último li = "Última"
                # Se penúltimo li tiver class="disabled", paramos
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
            # Não interromper o job se houver erro em uma linha
            print(f"Erro ao processar registros: {e}")

        # Create ZIP
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    path = os.path.join(root, file)
                    zipf.write(path, os.path.relpath(path, temp_dir))

        # Update job success
        job.status = "success"
        job.file_url = zip_path
        job.datainicio = datainicio
        job.datafim = datafim
        job.finished_at = datetime.utcnow()
        await db.commit()

        return zip_path

    except Exception as e:
        result = await db.execute(select(DownloadJob).where(DownloadJob.id == job_id))
        job = result.scalar_one_or_none()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            await db.commit()
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

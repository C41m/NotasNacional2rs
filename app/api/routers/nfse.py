from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import SessionLocal, get_db
from app.schemas.nfse import NFSEDownloadRequest, NFSEDownloadResponse, NFSEDownloadStatus, BatchDownloadRequest
from app.models.download_job import DownloadJob
from app.models.company import Company
from app.services.certificate_service import get_certificate_pem
from app.services.nfse_bot import run_nfse_download_async as run_nfse_download
from app.core.playwright_mgr import (
    launch_dedicated_browser,
    close_browser,
    MAX_CONCURRENT_BROWSERS,
)
import uuid
import os
import tempfile
import zipfile
import asyncio
from datetime import datetime


# Dicionário global para acompanhar batches
batch_status = {}

router = APIRouter(prefix="/nfse", tags=["nfse"])


async def _process_single_company_async(
    company_id: int,
    datainicio: str,
    datafim: str,
    batch_id: str,
    batch_status: dict,
    semaphore: asyncio.Semaphore,
):
    """
    Processa download para uma única empresa de forma assíncrona.
    - Usa semáforo para limitar concorrência de browsers dedicados
    - Cada chamada cria seu próprio processo Chromium (dedicado, sem contenção)
    - Retorna (company_id, zip_path | None, error | None, cnpj, nome)
    """
    async with semaphore:
        db = SessionLocal()
        playwright = None
        browser = None
        try:
            # Buscar dados da empresa para exibir CNPJ e nome no frontend
            company = db.execute(select(Company).where(Company.id == company_id)).scalar_one()
            cnpj = company.cnpj
            nome = company.nome

            cert_pem, key_pem, password = get_certificate_pem(db, company_id)

            # Lançar browser dedicado para esta task — sem contenção
            playwright, browser = await launch_dedicated_browser()

            job_id = str(uuid.uuid4())
            job = DownloadJob(
                id=job_id,
                company_id=company_id,
                data_inicio=datainicio,
                data_fim=datafim,
            )
            db.add(job)
            db.commit()

            def progress_callback(cid, notas_done, notas_total):
                if batch_id in batch_status:
                    companies = batch_status[batch_id].setdefault("companies", {})
                    if cid not in companies:
                        companies[cid] = {}
                    companies[cid]["notas_done"] = notas_done
                    companies[cid]["notas_total"] = notas_total
                    companies[cid]["status"] = job.status
                    companies[cid]["cnpj"] = cnpj
                    companies[cid]["nome"] = nome

            zip_path = await run_nfse_download(
                company_id, job_id, db, cert_pem, key_pem, password,
                browser=browser,
                datainicio=datainicio,
                datafim=datafim,
                batch_status=batch_status,
                batch_id=batch_id,
                progress_callback=progress_callback,
            )

            if zip_path and os.path.exists(zip_path):
                return (company_id, zip_path, None, cnpj, nome)
            return (company_id, None, "ZIP não gerado", cnpj, nome)

        except Exception as e:
            return (company_id, None, str(e), "", "")
        finally:
            # Fechar browser dedicado em qualquer cenário
            if playwright is not None or browser is not None:
                await close_browser(playwright, browser)
            db.close()


def process_batch(batch_id: str, company_ids: list, datainicio: str, datafim: str):
    """
    Processa download para múltiplas empresas.
    - Cada empresa roda em seu próprio processo Chromium dedicado
    - Semáforo limita a MAX_CONCURRENT_BROWSERS para controlar memória
    - Progresso atualizado em tempo real via lock
    """
    try:
        batch_status[batch_id] = {
            "total": len(company_ids),
            "done": 0,
            "status": "processing",
            "zip_path": None,
            "companies": {},
            "datainicio": datainicio,
            "datafim": datafim,
            "created_at": datetime.utcnow().isoformat(),
        }
        print(
            f"[Batch {batch_id}] Iniciando processamento de "
            f"{len(company_ids)} empresas (max {MAX_CONCURRENT_BROWSERS} "
            f"browsers simultâneos)..."
        )

        for cid in company_ids:
            batch_status[batch_id]["companies"][cid] = {
                "status": "queued",
                "notas_done": 0,
                "notas_total": 0,
                "cnpj": "",
                "nome": "",
            }

        zip_paths = []
        errors = []
        done_count = 0

        async def _run_all():
            """Executa todos os downloads em um único event loop."""
            nonlocal done_count, zip_paths, errors

            # Lock para atualizar batch_status de forma segura entre tasks
            lock = asyncio.Lock()

            # Semáforo: no máximo MAX_CONCURRENT_BROWSERS browsers ao mesmo tempo
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_BROWSERS)

            async def _process_and_track(cid):
                """Processa uma empresa e atualiza progresso em tempo real."""
                nonlocal done_count
                result = await _process_single_company_async(
                    cid, datainicio, datafim, batch_id, batch_status, semaphore
                )

                async with lock:
                    done_count += 1
                    batch_status[batch_id]["done"] = done_count

                    if isinstance(result, Exception):
                        errors.append(str(result))
                        print(f"[Batch {batch_id}] Erro inesperado na empresa {cid}: {result}")
                        batch_status[batch_id]["companies"][cid]["status"] = "failed"
                        return

                    cid_result, zp, err, cnpj, nome = result

                    # Atualiza CNPJ e nome da empresa
                    batch_status[batch_id]["companies"][cid]["cnpj"] = cnpj
                    batch_status[batch_id]["companies"][cid]["nome"] = nome

                    if err:
                        errors.append(err)
                        print(f"[Batch {batch_id}] Erro na empresa {cid}: {err}")
                        batch_status[batch_id]["companies"][cid]["status"] = "failed"
                    elif zp:
                        zip_paths.append(zp)
                        batch_status[batch_id]["companies"][cid]["status"] = "success"
                        print(
                            f"[Batch {batch_id}] Empresa {cid} ({cnpj}) concluída! "
                            f"({done_count}/{len(company_ids)})"
                        )
                    else:
                        batch_status[batch_id]["companies"][cid]["status"] = "failed"

            tasks = [
                asyncio.create_task(_process_and_track(cid))
                for cid in company_ids
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Uma única chamada asyncio.run() — tudo no mesmo event loop
        asyncio.run(_run_all())

        if zip_paths:
            final_zip = os.path.join(
                tempfile.gettempdir(), "jobs", f"NFSe_Batch_{batch_id}.zip"
            )
            os.makedirs(os.path.dirname(final_zip), exist_ok=True)
            print(
                f"[Batch {batch_id}] Combinando {len(zip_paths)} ZIPs em "
                f"{final_zip}..."
            )

            with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as final_zipf:
                for zp in zip_paths:
                    arcname = os.path.basename(zp)
                    with open(zp, "rb") as f:
                        final_zipf.writestr(arcname, f.read())

            batch_status[batch_id]["status"] = "success"
            batch_status[batch_id]["zip_path"] = final_zip

            for zp in zip_paths:
                if os.path.exists(zp):
                    os.remove(zp)

            print(
                f"[Batch {batch_id}] Concluído com sucesso! "
                f"ZIP final: {final_zip}"
            )
        else:
            batch_status[batch_id]["status"] = "failed"
            batch_status[batch_id]["error"] = "Nenhum ZIP gerado"
            print(f"[Batch {batch_id}] Falhou: nenhum ZIP gerado. Erros: {errors}")

    except Exception as e:
        batch_status[batch_id]["status"] = "failed"
        batch_status[batch_id]["error"] = str(e)
        print(f"[Batch {batch_id}] Erro fatal: {e}")


@router.post("/batch-download")
def start_batch_download(
    request: BatchDownloadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    for cid in request.company_ids:
        if not db.execute(
            select(Company).where(Company.id == cid)
        ).scalar_one_or_none():
            raise HTTPException(404, f"Company {cid} not found")

    batch_id = str(uuid.uuid4())
    background_tasks.add_task(
        process_batch, batch_id, request.company_ids, request.datainicio, request.datafim,
    )
    return {"batch_id": batch_id, "status": "queued"}


@router.get("/batch-download/active")
def list_active_batches(db: Session = Depends(get_db)):
    """Lista todos os batches que ainda estão em memória (processing, queued, cancelling, success, failed)."""
    result = {}
    for bid, bdata in batch_status.items():
        companies_info = {}
        for cid, cdata in bdata.get("companies", {}).items():
            company = db.execute(
                select(Company).where(Company.id == int(cid))
            ).scalar_one_or_none()
            companies_info[cid] = {
                **cdata,
                "nome": company.nome if company else cdata.get("nome", "Desconhecida"),
                "cnpj": company.cnpj if company else cdata.get("cnpj", ""),
            }
        result[bid] = {
            **bdata,
            "companies": companies_info,
        }
    return result


@router.get("/batch-download/{batch_id}")
def get_batch_status(batch_id: str):
    if batch_id not in batch_status:
        raise HTTPException(404, "Batch not found")
    return batch_status[batch_id]


@router.patch("/batch-download/{batch_id}/cancel")
def cancel_batch(batch_id: str):
    if batch_id not in batch_status:
        raise HTTPException(404, "Batch not found")
    batch = batch_status[batch_id]
    if batch["status"] not in ("queued", "processing"):
        raise HTTPException(400, f"Batch está '{batch['status']}', não pode ser cancelado")
    batch["cancelled"] = True
    batch["status"] = "cancelling"
    return {"message": "Cancelamento solicitado com sucesso"}


@router.get("/batch-download/{batch_id}/file")
def download_batch_file(batch_id: str, background_tasks: BackgroundTasks):
    if batch_id not in batch_status:
        raise HTTPException(404, "Batch not found")
    batch = batch_status[batch_id]
    if batch["status"] != "success" or not batch.get("zip_path"):
        raise HTTPException(400, "File not ready")
    if not os.path.exists(batch["zip_path"]):
        raise HTTPException(404, "File not found")

    zip_path = batch["zip_path"]
    filename = os.path.basename(zip_path)

    def cleanup_after_download():
        import time

        # Aguarda 5 minutos após o download antes de limpar
        time.sleep(300)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if batch_id in batch_status:
            del batch_status[batch_id]

    background_tasks.add_task(cleanup_after_download)

    return FileResponse(
        path=zip_path,
        filename=filename,
        media_type="application/zip",
    )


def _run_single_sync(job_id: str, company_id: int):
    """Wrapper síncrono para download único — roda em thread de background."""

    async def _run():
        db = SessionLocal()
        playwright = None
        browser = None
        try:
            playwright, browser = await launch_dedicated_browser()
            cert_pem, key_pem, password = get_certificate_pem(db, company_id)
            await run_nfse_download(
                company_id, job_id, db, cert_pem, key_pem, password,
                browser=browser,
            )
        except Exception as e:
            db2 = SessionLocal()
            try:
                job = (
                    db2.execute(
                        select(DownloadJob).where(DownloadJob.id == job_id)
                    )
                    .scalar_one_or_none()
                )
                if job:
                    job.status = "failed"
                    job.error_message = str(e)
                    job.finished_at = datetime.utcnow()
                    db2.commit()
            finally:
                db2.close()
        finally:
            # Fecha browser dedicado em qualquer cenário (sucesso ou erro)
            try:
                await close_browser(playwright, browser)
            except Exception:
                pass
            db.close()

    asyncio.run(_run())


@router.post("/download", response_model=NFSEDownloadResponse)
def start_download(
    request: NFSEDownloadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if not db.execute(
        select(Company).where(Company.id == request.company_id)
    ).scalar_one_or_none():
        raise HTTPException(404, "Company not found")

    job_id = str(uuid.uuid4())
    job = DownloadJob(id=job_id, company_id=request.company_id)
    db.add(job)
    db.commit()

    background_tasks.add_task(_run_single_sync, job_id, request.company_id)
    return NFSEDownloadResponse(job_id=job_id, status="queued")


@router.get("/download/{job_id}", response_model=NFSEDownloadStatus)
def get_download_status(job_id: str, db: Session = Depends(get_db)):
    job = db.execute(select(DownloadJob).where(DownloadJob.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/download/{job_id}/file")
def download_file(job_id: str, db: Session = Depends(get_db)):
    job = db.execute(select(DownloadJob).where(DownloadJob.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "success" or not job.file_url:
        raise HTTPException(400, "File not ready")
    if not os.path.exists(job.file_url):
        raise HTTPException(404, "File not found")
    return FileResponse(
        path=job.file_url,
        filename=os.path.basename(job.file_url),
        media_type="application/zip",
    )
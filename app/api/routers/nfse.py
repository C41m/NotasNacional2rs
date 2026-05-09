from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db, async_session_factory
from app.schemas.nfse import NFSEDownloadRequest, NFSEDownloadResponse, NFSEDownloadStatus, BatchDownloadRequest
from app.models.download_job import DownloadJob
from app.models.company import Company
from app.services.certificate_service import get_certificate_pem
from app.services.nfse_bot import run_nfse_download
import uuid
import os, tempfile, zipfile
import asyncio

# Dicionário global para acompanhar batches (em produção, usar Redis ou DB)
# Estrutura: { batch_id: { "total": N, "done": N, "status": "...", "zip_path": "...", "companies": { company_id: { "status": "...", "notas_done": N, "notas_total": N } } } }
batch_status = {}

router = APIRouter(prefix="/nfse", tags=["nfse"])


async def process_single_company(company_id: int, datainicio: str, datafim: str, batch_id: str = None):
    """Processa download para uma única empresa. Retorna (company_id, zip_path or None, error or None)."""
    try:
        async with async_session_factory() as db:
            # Buscar certificado da empresa
            cert_pem, key_pem, password = await get_certificate_pem(db, company_id)

            # Criar job individual
            job_id = str(uuid.uuid4())
            job = DownloadJob(id=job_id, company_id=company_id, data_inicio=datainicio, data_fim=datafim)
            db.add(job)
            await db.commit()

            # Progress callback para atualizar batch_status
            async def progress_callback(cid, notas_done, notas_total):
                if batch_id and batch_id in batch_status:
                    if cid not in batch_status[batch_id].get("companies", {}):
                        batch_status[batch_id].setdefault("companies", {})[cid] = {}
                    batch_status[batch_id]["companies"][cid]["notas_done"] = notas_done
                    batch_status[batch_id]["companies"][cid]["notas_total"] = notas_total
                    batch_status[batch_id]["companies"][cid]["status"] = job.status

            # Executar download (dentro da mesma sessão)
            zip_path = await run_nfse_download(company_id, job_id, db, cert_pem, key_pem, password, datainicio, datafim, progress_callback=progress_callback)
            if zip_path and os.path.exists(zip_path):
                return (company_id, zip_path, None)
            return (company_id, None, "ZIP não gerado")

    except Exception as e:
        return (company_id, None, str(e))


async def process_batch(batch_id: str, company_ids: list, datainicio: str, datafim: str):
    """Processa download para múltiplas empresas em paralelo e gera ZIP único."""
    try:
        batch_status[batch_id] = {"total": len(company_ids), "done": 0, "status": "processing", "zip_path": None, "companies": {}}
        print(f"[Batch {batch_id}] Iniciando processamento de {len(company_ids)} empresas...")

        # Inicializar empresas no batch_status
        for cid in company_ids:
            batch_status[batch_id]["companies"][cid] = {"status": "queued", "notas_done": 0, "notas_total": 0}

        # Criar tasks para cada empresa
        tasks = [asyncio.create_task(process_single_company(cid, datainicio, datafim, batch_id)) for cid in company_ids]

        # Processar conforme cada empresa termina (atualiza progresso incrementalmente)
        zip_paths = []
        done_count = 0
        for future in asyncio.as_completed(tasks):
            try:
                cid, zp, err = await future
                done_count += 1
                batch_status[batch_id]["done"] = done_count

                if err:
                    print(f"[Batch {batch_id}] Erro na empresa {cid}: {err}")
                    batch_status[batch_id]["companies"][cid]["status"] = "failed"
                elif zp:
                    zip_paths.append(zp)
                    batch_status[batch_id]["companies"][cid]["status"] = "success"
                    print(f"[Batch {batch_id}] Empresa {cid} concluída! ({done_count}/{len(company_ids)})")
            except Exception as e:
                done_count += 1
                batch_status[batch_id]["done"] = done_count
                print(f"[Batch {batch_id}] Erro fatal processando empresa: {e}")

        # Combinar todos os ZIPs em um único
        if zip_paths:
            final_zip = os.path.join(tempfile.gettempdir(), "jobs", f"NFSe_Batch_{batch_id}.zip")
            os.makedirs(os.path.dirname(final_zip), exist_ok=True)
            print(f"[Batch {batch_id}] Combinando {len(zip_paths)} ZIPs em {final_zip}...")

            with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as final_zipf:
                for zp in zip_paths:
                    arcname = os.path.basename(zp)
                    with open(zp, "rb") as f:
                        final_zipf.writestr(arcname, f.read())

            batch_status[batch_id]["status"] = "success"
            batch_status[batch_id]["zip_path"] = final_zip

            # Limpar ZIPs individuais
            for zp in zip_paths:
                if os.path.exists(zp):
                    os.remove(zp)

            print(f"[Batch {batch_id}] Concluído com sucesso! ZIP final: {final_zip}")
        else:
            batch_status[batch_id]["status"] = "failed"
            print(f"[Batch {batch_id}] Falhou: nenhum ZIP gerado")

    except Exception as e:
        batch_status[batch_id]["status"] = "failed"
        batch_status[batch_id]["error"] = str(e)
        print(f"[Batch {batch_id}] Erro fatal: {e}")


@router.post("/batch-download")
async def start_batch_download(request: BatchDownloadRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    # Validar empresas
    for cid in request.company_ids:
        if not await db.execute(select(Company).where(Company.id == cid)):
            raise HTTPException(404, f"Company {cid} not found")

    batch_id = str(uuid.uuid4())
    background_tasks.add_task(
        process_batch, batch_id, request.company_ids, request.datainicio, request.datafim
    )
    return {"batch_id": batch_id, "status": "queued"}


@router.get("/batch-download/{batch_id}")
async def get_batch_status(batch_id: str):
    if batch_id not in batch_status:
        raise HTTPException(404, "Batch not found")
    return batch_status[batch_id]


@router.get("/batch-download/{batch_id}/file")
async def download_batch_file(batch_id: str, background_tasks: BackgroundTasks):
    if batch_id not in batch_status:
        raise HTTPException(404, "Batch not found")
    batch = batch_status[batch_id]
    if batch["status"] != "success" or not batch.get("zip_path"):
        raise HTTPException(400, "File not ready")
    if not os.path.exists(batch["zip_path"]):
        raise HTTPException(404, "File not found")

    zip_path = batch["zip_path"]
    filename = os.path.basename(zip_path)

    # Agendar deleção do arquivo e limpeza do status após 1 minuto
    async def cleanup():
        await asyncio.sleep(60)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if batch_id in batch_status:
            del batch_status[batch_id]
    background_tasks.add_task(cleanup)

    return FileResponse(
        path=zip_path,
        filename=filename,
        media_type="application/zip"
    )


async def process_download(job_id: str, company_id: int, db: AsyncSession):
    try:
        cert_pem, key_pem, password = await get_certificate_pem(db, company_id)
        await run_nfse_download(company_id, job_id, db, cert_pem, key_pem, password)
    except Exception as e:
        job = await db.execute(select(DownloadJob).where(DownloadJob.id == job_id))
        job = job.scalar_one_or_none()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.utcnow()
            await db.commit()


@router.post("/download", response_model=NFSEDownloadResponse)
async def start_download(request: NFSEDownloadRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    if not await db.execute(select(Company).where(Company.id == request.company_id)):
        raise HTTPException(404, "Company not found")

    job_id = str(uuid.uuid4())
    job = DownloadJob(id=job_id, company_id=request.company_id)
    db.add(job)
    await db.commit()

    background_tasks.add_task(process_download, job_id, request.company_id, db)
    return NFSEDownloadResponse(job_id=job_id, status="queued")


@router.get("/download/{job_id}", response_model=NFSEDownloadStatus)
async def get_download_status(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.execute(select(DownloadJob).where(DownloadJob.id == job_id))
    job = job.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/download/{job_id}/file")
async def download_file(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.execute(select(DownloadJob).where(DownloadJob.id == job_id))
    job = job.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status != "success" or not job.file_url:
        raise HTTPException(400, "File not ready")
    if not os.path.exists(job.file_url):
        raise HTTPException(404, "File not found")
    return FileResponse(
        path=job.file_url,
        filename=os.path.basename(job.file_url),
        media_type="application/zip"
    )

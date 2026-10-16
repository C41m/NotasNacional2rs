from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.core.database import SessionLocal, get_db
from app.schemas.nfse import NFSEDownloadRequest, NFSEDownloadResponse, NFSEDownloadStatus, BatchDownloadRequest
from app.models.download_job import DownloadJob
from app.models.company import Company
from app.services.adn_api import fetch_distribuicao
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
    batch_id: str,
    batch_status: dict,
    download_type: str = "xml",
):
    """
    Processa download ADN para uma única empresa.
    Usa API ADN ao invés de Playwright/scraping.
    """
    db = SessionLocal()
    try:
        company = db.execute(select(Company).where(Company.id == company_id)).scalar_one()
        cnpj = company.cnpj
        nome = company.nome

        progress_callback = None

        result = await fetch_distribuicao(
            company_id=company_id,
            ult_nsu=0,
            ambiente="producao",
        )

        xmls = result.get("xmls", [])

        # Atualizar status
        if result["error"]:
            batch_status[batch_id]["companies"][company_id]["status"] = "failed"
            batch_status[batch_id]["companies"][company_id]["error"] = result["error"]
            return (company_id, None, result["error"], cnpj, nome, [])
        elif xmls:
            batch_status[batch_id]["companies"][company_id]["status"] = "success"
            return (company_id, None, None, cnpj, nome, xmls)
        else:
            # Sem documentos
            batch_status[batch_id]["companies"][company_id]["status"] = "success"
            batch_status[batch_id]["companies"][company_id]["notas_done"] = 0
            return (company_id, None, None, cnpj, nome, [])

    except Exception as e:
        return (company_id, None, str(e), "", "", [])
    finally:
        db.close()


def _organizar_xmls(xmls: list) -> dict:
    """
    Organiza XMLs em estrutura: {tipo_documento: {role: {competencia: [xml_data]}}}
    tipo_documento: 'NFSE', 'EVENTO', 'DPS', 'CREDITO', 'DEBITO', 'APURACAO'
    role: 'prestado', 'tomado', 'intermediario', 'autor_evento', 'desconhecido'
    competencia: 'YYYY-MM'
    """
    organizados = {}
    for xml in xmls:
        tipo = xml.get("tipo", "DESCONHECIDO")
        role = xml.get("role", "desconhecido")
        comp = xml.get("competencia", "0000-00")
        
        # Para eventos, adicionar subtipo
        if tipo == "EVENTO":
            evento_desc = xml.get("evento_descricao") or "EVENTO_OUTROS"
            role = f"evento_{evento_desc.lower()}"
        
        if tipo not in organizados:
            organizados[tipo] = {}
        if role not in organizados[tipo]:
            organizados[tipo][role] = {}
        if comp not in organizados[tipo][role]:
            organizados[tipo][role][comp] = []
        organizados[tipo][role][comp].append(xml)
    return organizados


async def process_batch(batch_id: str, company_ids: list, download_type: str = "xml"):
    """
    Processa download ADN - gera ZIP com pastas organizadas.
    Estrutura: NOMEEMPRESA/TIPO_DOC/role/YYYY-MM/
    """
    batch_status[batch_id] = {
        "total": len(company_ids),
        "done": 0,
        "status": "processing",
        "zip_path": None,
        "companies": {},
        "created_at": datetime.utcnow().isoformat(),
    }

    for cid in company_ids:
        batch_status[batch_id]["companies"][cid] = {
            "status": "queued",
            "notas_done": 0,
            "notas_total": 0,
            "cnpj": "",
            "nome": "",
            "zip_path": None,
        }

    async def _run_all():
        errors = []
        all_company_xmls = []  # [(nome, xml_data)]

        # ponytail: loop simples sequencial. Concorrência com create_task/gather
        # fazia os documentos se perderem entre _process_single_company_async
        # e o ZIP consolidado. Uma empresa por vez é mais que suficiente.
        for cid in company_ids:
            if batch_status[batch_id].get("cancelled"):
                break

            try:
                result = await _process_single_company_async(
                    cid, batch_id, batch_status, download_type
                )
            except Exception as e:
                errors.append(str(e))
                batch_status[batch_id]["companies"][cid]["status"] = "failed"
                batch_status[batch_id]["companies"][cid]["error"] = str(e)
                continue

            batch_status[batch_id]["done"] += 1
            cid_result, zp, err, cnpj, nome, xmls = result
            batch_status[batch_id]["companies"][cid]["cnpj"] = cnpj
            batch_status[batch_id]["companies"][cid]["nome"] = nome

            if err:
                errors.append(err)
                batch_status[batch_id]["companies"][cid]["status"] = "failed"
                batch_status[batch_id]["companies"][cid]["error"] = err
            elif xmls:
                jobs_dir = os.path.join(tempfile.gettempdir(), "jobs", batch_id)
                os.makedirs(jobs_dir, exist_ok=True)
                nome_clean = nome.replace("/", "_").replace("\\", "_").replace(" ", "_")
                zip_path = os.path.join(jobs_dir, f"{nome_clean}.zip")

                organizados = _organizar_xmls(xmls)
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for tipo, roles in organizados.items():
                        for role, competencias in roles.items():
                            for comp, xmls_list in competencias.items():
                                for xml_data in xmls_list:
                                    nsu = xml_data["nsu"]
                                    chave = xml_data["chave"]
                                    xml_str = xml_data["xml"]
                                    evento_desc = xml_data.get("evento_descricao") or ""
                                    if evento_desc:
                                        filename = f"{tipo}/{role}/{comp}/{evento_desc}_NSU{nsu}_{chave}.xml"
                                    elif chave:
                                        filename = f"{tipo}/{role}/{comp}/NSU{nsu}_{chave}.xml"
                                    else:
                                        filename = f"{tipo}/{role}/{comp}/NSU{nsu}.xml"
                                    zipf.writestr(filename, xml_str.encode("utf-8"))

                batch_status[batch_id]["companies"][cid]["status"] = "success"
                batch_status[batch_id]["companies"][cid]["notas_done"] = len(xmls)
                batch_status[batch_id]["companies"][cid]["zip_path"] = zip_path

                for xml_data in xmls:
                    all_company_xmls.append((nome, xml_data))

                print(f"[Batch {batch_id}] {cid} ({nome}): {len(xmls)} documentos")
            else:
                batch_status[batch_id]["companies"][cid]["status"] = "success"

        # ZIP consolidado: NOMEEMPRESA/TIPO_DOCUMENTO/role/competencia/arquivo.xml
        if all_company_xmls:
            jobs_dir = os.path.join(tempfile.gettempdir(), "jobs")
            final_zip = os.path.join(jobs_dir, f"NFSe_ADN_Batch_{batch_id}.zip")
            
            with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
                for nome, xml_data in all_company_xmls:
                    nsu = xml_data["nsu"]
                    tipo = xml_data.get("tipo", "DESCONHECIDO")
                    chave = xml_data["chave"]
                    xml_str = xml_data["xml"]
                    role = xml_data.get("role", "desconhecido")
                    comp = xml_data.get("competencia", "0000-00")
                    evento_desc = xml_data.get("evento_descricao") or ""
                    nome_clean = nome.replace("/", "_").replace("\\", "_").replace(" ", "_")
                    
                    if evento_desc:
                        filename = f"{nome_clean}/{tipo}/{role}/{comp}/{evento_desc}_NSU{nsu}_{chave}.xml"
                    elif chave:
                        filename = f"{nome_clean}/{tipo}/{role}/{comp}/NSU{nsu}_{chave}.xml"
                    else:
                        filename = f"{nome_clean}/{tipo}/{role}/{comp}/NSU{nsu}.xml"
                    zipf.writestr(filename, xml_str.encode("utf-8"))
            
            batch_status[batch_id]["zip_path"] = final_zip
            batch_status[batch_id]["status"] = "success"
            print(f"[Batch {batch_id}] ZIP consolidado: {len(all_company_xmls)} XMLs → {final_zip}")
        else:
            # Sem documentos: cria ZIP vazio para o download funcionar e o
            # usuário receber um arquivo (resultado correto: nada encontrado).
            jobs_dir = os.path.join(tempfile.gettempdir(), "jobs")
            os.makedirs(jobs_dir, exist_ok=True)
            final_zip = os.path.join(jobs_dir, f"NFSe_ADN_Batch_{batch_id}.zip")
            with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED):
                pass
            batch_status[batch_id]["zip_path"] = final_zip
            batch_status[batch_id]["status"] = "success"
            batch_status[batch_id]["error"] = "Nenhum documento encontrado" if not errors else "; ".join(errors)
            print(f"[Batch {batch_id}] Nenhum documento encontrado → ZIP vazio")

    try:
        # ponytail: asyncio.run() não pode ser chamado dentro de um loop já ativo.
        # O FastAPI BackgroundTasks já roda no loop do Uvicorn — usar await direto.
        await _run_all()
    except Exception as e:
        import traceback
        traceback.print_exc()
        batch_status[batch_id]["status"] = "failed"
        batch_status[batch_id]["error"] = str(e)
        print(f"[Batch {batch_id}] Erro fatal: {e}")


@router.post("/batch-download")
def start_batch_download(
    request: BatchDownloadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Inicia download de NFSe via API ADN para múltiplas empresas."""
    for cid in request.company_ids:
        if not db.execute(
            select(Company).where(Company.id == cid)
        ).scalar_one_or_none():
            raise HTTPException(404, f"Company {cid} not found")

    batch_id = str(uuid.uuid4())
    background_tasks.add_task(
        process_batch, batch_id, request.company_ids, request.download_type,
    )
    return {"batch_id": batch_id, "status": "queued"}


@router.get("/batch-download/active")
def list_active_batches(db: Session = Depends(get_db)):
    """Lista todos os batches em memória."""
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
    """Retorna status de um batch específico."""
    if batch_id not in batch_status:
        raise HTTPException(404, "Batch not found")
    return batch_status[batch_id]


@router.patch("/batch-download/{batch_id}/cancel")
def cancel_batch(batch_id: str):
    """Cancela um batch em processamento."""
    if batch_id not in batch_status:
        raise HTTPException(404, "Batch not found")
    batch = batch_status[batch_id]
    if batch["status"] not in ("queued", "processing"):
        raise HTTPException(400, f"Batch está '{batch['status']}', não pode ser cancelado")
    batch["cancelled"] = True
    batch["status"] = "cancelling"
    return {"message": "Cancelamento solicitado com sucesso"}


@router.get("/batch-download/{batch_id}/file/{company_id}")
def download_company_file(batch_id: str, company_id: int, db: Session = Depends(get_db)):
    """Baixa o ZIP de uma empresa específica, com nome da empresa."""
    if batch_id not in batch_status:
        raise HTTPException(404, "Batch not found")
    batch = batch_status[batch_id]
    companies = batch.get("companies", {})
    
    if str(company_id) not in companies:
        raise HTTPException(404, f"Company {company_id} not found in batch")
    
    company = companies[str(company_id)]
    zip_path = company.get("zip_path")
    nome = company.get("nome", f"empresa_{company_id}")
    
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(404, "File not found or company has no documents")
    
    # Nome do ZIP: NOMEEMPRESA.zip
    nome_clean = nome.replace("/", "_").replace("\\", "_").replace(" ", "_")
    filename = f"{nome_clean}.zip"
    
    return FileResponse(
        path=zip_path,
        filename=filename,
        media_type="application/zip",
    )


@router.get("/batch-download/{batch_id}/file")
def download_batch_file(batch_id: str, background_tasks: BackgroundTasks):
    """Retorna o ZIP consolidado (todos os XMLs com nome da empresa)."""
    if batch_id not in batch_status:
        raise HTTPException(404, "Batch not found")
    batch = batch_status[batch_id]
    if batch["status"] != "success" or not batch.get("zip_path"):
        raise HTTPException(400, "File not ready")
    if not os.path.exists(batch["zip_path"]):
        raise HTTPException(404, "File not found")

    zip_path = batch["zip_path"]
    companies = batch.get("companies", {})
    
    # Se só teve uma empresa, usa o nome dela no ZIP
    if len(companies) == 1:
        company = list(companies.values())[0]
        nome = company.get("nome", "NFSe")
        nome_clean = nome.replace("/", "_").replace("\\", "_").replace(" ", "_")
        filename = f"{nome_clean}.zip"
    else:
        filename = os.path.basename(zip_path)

    def cleanup_after_download():
        import time
        time.sleep(3600)  # 1 hora antes de limpar
        if os.path.exists(zip_path):
            os.remove(zip_path)
        batch_dir = os.path.join(tempfile.gettempdir(), "jobs", batch_id)
        if os.path.exists(batch_dir):
            import shutil
            shutil.rmtree(batch_dir, ignore_errors=True)
        if batch_id in batch_status:
            del batch_status[batch_id]

    background_tasks.add_task(cleanup_after_download)

    return FileResponse(
        path=zip_path,
        filename=filename,
        media_type="application/zip",
    )


# Endpoints legados (mantidos para compatibilidade)
def _run_single_sync(job_id: str, company_id: int):
    """Wrapper síncrono para download único via API ADN."""
    async def _run():
        db = SessionLocal()
        try:
            result = await fetch_distribuicao(
                company_id=company_id,
                ult_nsu=0,
                ambiente="producao",
            )

            xmls = result.get("xmls", [])

            # Gerar ZIP
            zip_path = None
            if xmls:
                company = db.execute(select(Company).where(Company.id == company_id)).scalar_one()
                cnpj = company.cnpj.replace(".", "").replace("/", "").replace("-", "")

                jobs_dir = os.path.join(tempfile.gettempdir(), "jobs")
                os.makedirs(jobs_dir, exist_ok=True)
                zip_path = os.path.join(
                    jobs_dir,
                    f"NFSe_ADN_{cnpj}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                )

                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for xml_data in xmls:
                        nsu = xml_data["nsu"]
                        tipo = xml_data.get("tipo", "DESCONHECIDO")
                        chave = xml_data["chave"]
                        xml_str = xml_data["xml"]
                        role = xml_data.get("role", "desconhecido")
                        comp = xml_data.get("competencia", "0000-00")
                        evento_desc = xml_data.get("evento_descricao") or ""
                        
                        if evento_desc:
                            filename = f"{tipo}/{role}/{comp}/{evento_desc}_NSU{nsu}_{chave}.xml"
                        elif chave:
                            filename = f"{tipo}/{role}/{comp}/NSU{nsu}_{chave}.xml"
                        else:
                            filename = f"{tipo}/{role}/{comp}/NSU{nsu}.xml"
                        zipf.writestr(filename, xml_str.encode("utf-8"))

            job = db.execute(select(DownloadJob).where(DownloadJob.id == job_id)).scalar_one_or_none()
            if job:
                if result["error"]:
                    job.status = "failed"
                    job.error_message = result["error"]
                elif zip_path:
                    job.status = "success"
                    job.file_url = zip_path
                    job.notas_processed = len(xmls)
                else:
                    job.status = "success"
                    job.notas_processed = 0
                job.finished_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()

    asyncio.run(_run())


@router.post("/download", response_model=NFSEDownloadResponse)
def start_download(
    request: NFSEDownloadRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Inicia download de NFSe via API ADN para uma empresa."""
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
    """Retorna status de um job de download."""
    job = db.execute(select(DownloadJob).where(DownloadJob.id == job_id)).scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/download/{job_id}/file")
def download_file(job_id: str, db: Session = Depends(get_db)):
    """Retorna o ZIP do job para download."""
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
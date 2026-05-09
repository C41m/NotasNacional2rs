from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.services.certificate_service import save_certificate
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyOut
from app.models.company import Company
from app.models.certificate import Certificate
from typing import List

router = APIRouter(prefix="/companies", tags=["companies"])

@router.post("/", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(company: CompanyCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Company).where(Company.cnpj == company.cnpj))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "CNPJ already registered")

    db_company = Company(nome=company.nome, cnpj=company.cnpj)
    db.add(db_company)
    await db.commit()
    await db.refresh(db_company)

    try:
        cert = await save_certificate(db, db_company.id, company.pfx_base64, company.password)
    except Exception as e:
        await db.rollback()
        raise HTTPException(400, f"Certificate error: {str(e)}")

    return CompanyOut(**company.model_dump(), id=db_company.id, created_at=db_company.created_at, updated_at=db_company.updated_at, validade_cert=cert.validade)

@router.get("/", response_model=List[CompanyOut])
async def list_companies(page: int = 1, limit: int = 20, search: str = "", db: AsyncSession = Depends(get_db)):
    query = select(Company).options(selectinload(Company.certificate))
    if search:
        query = query.where(Company.nome.icontains(search) | Company.cnpj.icontains(search))
    result = await db.execute(query.offset((page-1)*limit).limit(limit))
    companies = result.scalars().all()
    return [CompanyOut(**c.__dict__, validade_cert=c.certificate.validade if c.certificate else None) for c in companies]

@router.get("/{company_id}", response_model=CompanyOut)
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).options(selectinload(Company.certificate)).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    return CompanyOut(**company.__dict__, validade_cert=company.certificate.validade if company.certificate else None)

@router.patch("/{company_id}", response_model=CompanyOut)
async def update_company(company_id: int, update: CompanyUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).options(selectinload(Company.certificate)).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")

    if update.nome:
        company.nome = update.nome

    if update.pfx_base64 or update.password:
        if not update.pfx_base64 or not update.password:
            raise HTTPException(400, "Both PFX and password required for certificate update")
        if company.certificate:
            await db.delete(company.certificate)
        await save_certificate(db, company.id, update.pfx_base64, update.password)

    await db.commit()
    await db.refresh(company)
    return CompanyOut(**company.__dict__, validade_cert=company.certificate.validade if company.certificate else None)

@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    await db.delete(company)
    await db.commit()

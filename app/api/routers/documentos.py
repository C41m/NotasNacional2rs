from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db
from app.core.api_key import verify_api_key, api_key_dep
from app.models.documento_fiscal import DocumentoFiscal, TipoDocumento
from app.schemas.documento_fiscal import (
    DocumentoFiscalCreate,
    DocumentoFiscalUpdate,
    DocumentoFiscalOut,
    DocumentoFiscalResumoOut,
)
from app.schemas.common import PaginatedResponse

router = APIRouter(prefix="/documentos", tags=["documentos"])


@router.post("/", response_model=DocumentoFiscalOut, status_code=status.HTTP_201_CREATED)
async def create_documento(
    payload: DocumentoFiscalCreate,
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """Cria um novo documento fiscal."""
    documento = DocumentoFiscal(**payload.model_dump())
    db.add(documento)
    db.commit()
    db.refresh(documento)
    return documento


@router.get("/", response_model=PaginatedResponse[DocumentoFiscalResumoOut])
async def list_documentos(
    empresa_id: Optional[int] = Query(None, description="Filtrar por empresa"),
    tipo_documento: Optional[TipoDocumento] = Query(None, description="Filtrar por tipo"),
    periodo: Optional[str] = Query(None, description="Filtrar por período (YYYY-MM)"),
    ano_calendario: Optional[int] = Query(None, description="Filtrar por ano calendário"),
    situacao: Optional[str] = Query(None, description="Filtrar por situação"),
    ativo: Optional[bool] = Query(True, description="Filtrar por status ativo"),
    data_emissao_inicio: Optional[datetime] = Query(None, description="Data emissão início"),
    data_emissao_fim: Optional[datetime] = Query(None, description="Data emissão fim"),
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    """Lista documentos fiscais com filtros e paginação."""
    query = select(DocumentoFiscal)
    count_query = select(func.count(DocumentoFiscal.id))

    # Aplicar filtros
    filters = []
    if empresa_id is not None:
        filters.append(DocumentoFiscal.empresa_id == empresa_id)
    if tipo_documento is not None:
        filters.append(DocumentoFiscal.tipo_documento == tipo_documento)
    if periodo is not None:
        filters.append(DocumentoFiscal.periodo == periodo)
    if ano_calendario is not None:
        filters.append(DocumentoFiscal.ano_calendario == ano_calendario)
    if situacao is not None:
        filters.append(DocumentoFiscal.situacao == situacao)
    if ativo is not None:
        filters.append(DocumentoFiscal.ativo == ativo)
    if data_emissao_inicio is not None:
        filters.append(DocumentoFiscal.data_emissao >= data_emissao_inicio)
    if data_emissao_fim is not None:
        filters.append(DocumentoFiscal.data_emissao <= data_emissao_fim)

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    # Contagem total
    total = db.execute(count_query).scalar() or 0

    # Paginação
    offset = (page - 1) * page_size
    query = query.order_by(DocumentoFiscal.id.desc()).offset(offset).limit(page_size)

    documentos = db.execute(query).scalars().all()

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse[DocumentoFiscalResumoOut](
        items=[DocumentoFiscalResumoOut.model_validate(d) for d in documentos],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{documento_id}", response_model=DocumentoFiscalOut)
async def get_documento(
    documento_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    """Obtém um documento fiscal pelo ID."""
    result = db.execute(
        select(DocumentoFiscal).where(DocumentoFiscal.id == documento_id)
    )
    documento = result.scalar_one_or_none()

    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento fiscal não encontrado",
        )

    return documento


@router.put("/{documento_id}", response_model=DocumentoFiscalOut)
async def update_documento(
    documento_id: int,
    payload: DocumentoFiscalUpdate,
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """Atualiza um documento fiscal."""
    result = db.execute(
        select(DocumentoFiscal).where(DocumentoFiscal.id == documento_id)
    )
    documento = result.scalar_one_or_none()

    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento fiscal não encontrado",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(documento, field, value)

    db.commit()
    db.refresh(documento)
    return documento


@router.delete("/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_documento(
    documento_id: int,
    _api_key: str = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """Remove um documento fiscal."""
    result = db.execute(
        select(DocumentoFiscal).where(DocumentoFiscal.id == documento_id)
    )
    documento = result.scalar_one_or_none()

    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento fiscal não encontrado",
        )

    db.delete(documento)
    db.commit()
    return None


@router.get("/empresa/{empresa_id}", response_model=List[DocumentoFiscalResumoOut])
async def list_documentos_by_empresa(
    empresa_id: int,
    tipo_documento: Optional[TipoDocumento] = Query(None),
    periodo: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    """Lista todos os documentos de uma empresa."""
    query = select(DocumentoFiscal).where(DocumentoFiscal.empresa_id == empresa_id)

    if tipo_documento is not None:
        query = query.where(DocumentoFiscal.tipo_documento == tipo_documento)
    if periodo is not None:
        query = query.where(DocumentoFiscal.periodo == periodo)

    query = query.order_by(DocumentoFiscal.periodo.desc(), DocumentoFiscal.id.desc())
    documentos = db.execute(query).scalars().all()

    return [DocumentoFiscalResumoOut.model_validate(d) for d in documentos]


@router.get("/tipos/", response_model=List[str])
async def list_tipos_documento(
    db: Session = Depends(get_db),
    api_key: str = Depends(api_key_dep),
):
    """Lista os tipos de documento disponíveis."""
    return [t.value for t in TipoDocumento]

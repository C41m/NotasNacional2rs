from pydantic import BaseModel, Field, ConfigDict
from app.utils.cnpj import CNPJ
from datetime import datetime

class CompanyBase(BaseModel):
    nome: str = Field(..., max_length=255)
    cnpj: CNPJ

class CompanyCreate(CompanyBase):
    pfx_base64: str = Field(..., description="PFX certificate in base64")
    password: str = Field(..., min_length=1)

class CompanyUpdate(BaseModel):
    nome: str | None = Field(None, max_length=255)
    pfx_base64: str | None = None
    password: str | None = Field(None, min_length=1)

class CompanyOut(CompanyBase):
    id: int
    created_at: datetime
    updated_at: datetime
    validade_cert: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

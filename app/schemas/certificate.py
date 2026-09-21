from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class CertificateBase(BaseModel):
    company_id: int = Field(..., gt=0)
    certificado_enc: str = Field(..., description="Certificado digital em base64")
    senha_enc: str = Field(..., description="Senha do certificado criptografada")
    validade: datetime | None = None


class CertificateCreate(CertificateBase):
    pass


class CertificateUpdate(BaseModel):
    certificado_enc: str | None = None
    senha_enc: str | None = None
    validade: datetime | None = None


class CertificateOut(BaseModel):
    id: int
    company_id: int
    validade: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

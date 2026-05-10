from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
from datetime import datetime, timezone
from app.core.security import encrypt_bytes, decrypt_bytes
from app.models.certificate import Certificate
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Tuple
import base64

class CertificateError(Exception):
    pass

def validate_pfx(pfx_base64: str, password: str) -> Tuple[datetime, bytes, bytes]:
    """Validate PFX and return (expiration, cert_pem, key_pem)."""
    try:
        pfx_data = base64.b64decode(pfx_base64)
        private_key, certificate, _ = pkcs12.load_key_and_certificates(pfx_data, password.encode())
        if not private_key or not certificate:
            raise CertificateError("Invalid PFX: missing key or certificate")

        not_after = certificate.not_valid_after_utc
        if not_after < datetime.now(timezone.utc):
            raise CertificateError("Certificate is expired")

        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        cert_pem = certificate.public_bytes(serialization.Encoding.PEM)

        return not_after, cert_pem, key_pem
    except Exception as e:
        raise CertificateError(f"PFX validation failed: {str(e)}") from e

def save_certificate(db: Session, company_id: int, pfx_base64: str, password: str) -> Certificate:
    """Validate and save encrypted certificate."""
    not_after, _, _ = validate_pfx(pfx_base64, password)
    pfx_data = base64.b64decode(pfx_base64)

    cert = Certificate(
        company_id=company_id,
        certificado_enc=encrypt_bytes(pfx_data),
        senha_enc=encrypt_bytes(password.encode()),
        validade=not_after
    )
    db.add(cert)
    db.commit()
    db.refresh(cert)
    return cert

def get_certificate_pem(db: Session, company_id: int) -> Tuple[bytes, bytes, str]:
    """Retrieve and convert certificate to PEM for Playwright."""
    result = db.execute(select(Certificate).where(Certificate.company_id == company_id))
    cert = result.scalar_one_or_none()
    if not cert:
        raise CertificateError("Certificate not found")

    password = decrypt_bytes(cert.senha_enc).decode()
    pfx_data = decrypt_bytes(cert.certificado_enc)
    pfx_base64 = base64.b64encode(pfx_data).decode()
    _, cert_pem, key_pem = validate_pfx(pfx_base64, password)

    return cert_pem, key_pem, password

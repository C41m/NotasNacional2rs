from cryptography.fernet import Fernet, InvalidToken
from cryptography.exceptions import InvalidKey
from app.core.config import settings
from typing import Optional

_fernet = Fernet(settings.CERT_KEY.encode())

def encrypt_bytes(data: bytes) -> str:
    """Encrypt bytes and return base64-encoded string."""
    return _fernet.encrypt(data).decode()

def decrypt_bytes(encrypted_str: str) -> bytes:
    """Decrypt base64-encoded string to bytes."""
    try:
        return _fernet.decrypt(encrypted_str.encode())
    except (InvalidToken, InvalidKey) as e:
        raise ValueError("Invalid encryption key or corrupted data") from e

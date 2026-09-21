from fastapi import Depends, HTTPException, status, Header
from app.core.config import settings


async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """Verify X-API-Key header matches DEEPSEEK_API_KEY setting."""
    if not x_api_key or x_api_key != settings.DEEPSEEK_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key"
        )
    return x_api_key


def get_api_key_dependency():
    """Returns a FastAPI Depends that validates X-API-Key header."""
    return verify_api_key


# This is the actual dependency used in routers
api_key_dep = verify_api_key

# Re-export for use in routers
__all__ = ['verify_api_key', 'api_key_dep', 'get_api_key_dependency']
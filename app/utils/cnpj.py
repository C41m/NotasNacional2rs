from pydantic import BeforeValidator
from typing import Annotated
import re

def validate_cnpj(cnpj: str) -> str:
    """Validate CNPJ format and check digits."""
    cleaned = re.sub(r'[^0-9]', '', cnpj)
    if len(cleaned) != 14:
        raise ValueError("CNPJ must be 14 digits long")

    # First check digit
    weights1 = [5,4,3,2,9,8,7,6,5,4,3,2]
    total = sum(int(cleaned[i]) * weights1[i] for i in range(12))
    remainder = total % 11
    digit1 = 0 if remainder < 2 else 11 - remainder
    if digit1 != int(cleaned[12]):
        raise ValueError("Invalid CNPJ first check digit")

    # Second check digit
    weights2 = [6,5,4,3,2,9,8,7,6,5,4,3,2]
    total = sum(int(cleaned[i]) * weights2[i] for i in range(13))
    remainder = total % 11
    digit2 = 0 if remainder < 2 else 11 - remainder
    if digit2 != int(cleaned[13]):
        raise ValueError("Invalid CNPJ second check digit")

    return cleaned

CNPJ = Annotated[str, BeforeValidator(lambda v: validate_cnpj(v))]

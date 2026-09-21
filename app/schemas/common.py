from pydantic import BaseModel, ConfigDict
from typing import TypeVar, Generic, List

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    detail: str
    status_code: int

    model_config = ConfigDict(from_attributes=True)


class SuccessResponse(BaseModel):
    message: str
    data: dict | None = None

    model_config = ConfigDict(from_attributes=True)

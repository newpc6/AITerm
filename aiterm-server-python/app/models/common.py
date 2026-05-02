from pydantic import BaseModel
from typing import Optional, Generic, TypeVar, List, Any

T = TypeVar('T')


class Response(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: Optional[T] = None


class SSEEvent(BaseModel):
    event: str
    data: dict


class LLMPublicInfo(BaseModel):
    model: str
    configured: bool


class PaginationRequest(BaseModel):
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int):
        total_pages = (total + page_size -
                       1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

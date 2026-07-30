from typing import Any, Optional

from pydantic import BaseModel, Field


class NounResponse(BaseModel):
    id: str
    name: str
    type: str = "entity"  # person, concept, technology, event
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: Optional[str] = None


class NounSearchResponse(BaseModel):
    results: list[NounResponse] = []
    query: str
    total: int = 0

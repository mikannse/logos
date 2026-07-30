from typing import Optional

from pydantic import BaseModel, Field


class Milestone(BaseModel):
    year: int
    title: str = Field(max_length=20)
    description: str
    source_url: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class TimelineResponse(BaseModel):
    noun_id: str
    milestones: list[Milestone] = []
    total: int = 0

from typing import Optional

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    type: str = "entity"  # person, entity, event
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: Optional[str] = None
    image_url: Optional[str] = None
    year: Optional[int] = None


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_url: str = ""
    evidence: Optional[str] = None


class GraphResponse(BaseModel):
    center: str
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    depth: int = 1
    has_more: bool = False

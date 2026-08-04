from typing import Optional

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    type: str = "entity"  # person/entity/event/concept/technology/organization/category
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance: float = Field(default=0.0, ge=0.0, le=1.0, description="与中心实体的相关度（≠confidence 数据可靠度）")
    summary: Optional[str] = None
    image_url: Optional[str] = None
    year: Optional[int] = None
    year_end: Optional[int] = None
    hop: Optional[int] = None  # 距中心跳数（多跳构建用；depth=1 时缺省）


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    relevance: float = Field(default=0.0, ge=0.0, le=1.0, description="与中心实体的相关度（≠confidence 数据可靠度）")
    source_url: str = ""
    evidence: Optional[str] = None
    hop: Optional[int] = None  # 这条边所属跳数（多跳构建用）


class GraphResponse(BaseModel):
    center: str
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    depth: int = 1
    has_more: bool = False

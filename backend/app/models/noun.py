from typing import Optional

from pydantic import BaseModel, Field


class NounResponse(BaseModel):
    id: str
    name: str
    type: str = "entity"  # person, concept, technology, event
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: Optional[str] = None


class DisambiguationGroup(BaseModel):
    """消歧分组项 — 同名实体的区别信息"""
    id: str
    label: str
    label_en: str = ""           # 英文名（帮助跨语言识别）
    type_label: str = ""         # 类型标签，如 "水果/食品"、"技术公司"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""


class NounSearchResponse(BaseModel):
    results: list[NounResponse] = []
    query: str
    total: int = 0
    needs_disambiguation: bool = False
    disambiguation_groups: list[DisambiguationGroup] = []

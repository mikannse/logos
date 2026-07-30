from typing import Optional

from pydantic import BaseModel, Field


class RelationModel(BaseModel):
    """Edge 模型 — 每条关系必有 source / confidence / evidence 三字段"""

    source: str  # 数据源名称
    target: str
    type: str  # 关系类型 label
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_url: str = ""  # 数据来源链接
    evidence: Optional[str] = None  # 证据摘要

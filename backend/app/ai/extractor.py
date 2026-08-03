"""实体/关系提取器 — 从非结构化文本中提取结构化知识

使用 Instructor 驱动的 LLM 提取，支持 Anthropic / OpenAI 切换。
输出符合 Logos 数据模型（Node + Edge 格式）。
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.ai.llm_client import LLMClient


# 结构化提取 Schema
class ExtractedEntity(BaseModel):
    """从文本中提取的实体"""
    name: str = Field(description="实体名称")
    type: str = Field(description="实体类型: person/concept/technology/event/organization")
    description: str = Field(description="单句描述（<=50字）")
    relevance: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="与焦点实体的相关度：核心直接关联 >0.7，间接/弱相关 0.3-0.5，无关不提取",
    )
    aliases: list[str] = Field(default_factory=list, description="别名/其他写法")


class ExtractedRelation(BaseModel):
    """实体间关系"""
    source: str = Field(description="源实体名称")
    target: str = Field(description="目标实体名称")
    relation_type: str = Field(description="关系类型: influence/affiliation/creation/competition/collaboration/other")
    description: str = Field(description="关系描述（<=30字）")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="置信度")


class EntityExtractionResult(BaseModel):
    """实体/关系提取结果"""
    entities: list[ExtractedEntity] = Field(description="提取的实体列表（3-10个）")
    relations: list[ExtractedRelation] = Field(description="实体间关系列表")
    focus_entity_type: Optional[str] = Field(
        default=None,
        description="焦点实体的类型判定（person/concept/technology/event/organization）；规则推断为 entity 时用于 AI 兜底覆盖",
    )


class EntityExtractor:
    """从非结构化文本中提取实体和关系"""

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()

    async def extract_from_text(
        self, text: str, focus_entity: Optional[str] = None
    ) -> Optional[EntityExtractionResult]:
        """从文本中提取实体和关系

        Args:
            text: 非结构化文本
            focus_entity: 焦点实体（中心名词）。提供时只提取与其直接关联的实体，
                并为每个实体给出与焦点的相关度打分（relevance）。
        """
        system_prompt = """你是一个知识图谱构建专家。从给定文本中提取核心实体和它们之间的关系。

规则：
1. 实体类型: person(人物), concept(概念), technology(技术), event(事件), organization(组织)
2. 关系类型: influence(影响), affiliation(隶属), creation(创作), competition(竞争), collaboration(合作), other(其他)
3. 只提取文本中有明确依据的实体和关系
4. 输出 3-10 个核心实体，以及它们之间的主要关系
5. 描述要简洁（实体<=50字，关系<=30字）
6. 低可信度的关系使用较低的 confidence 值"""

        if focus_entity:
            system_prompt += f"""
7. 以「{focus_entity}」为核心焦点，只提取与它直接关联的实体，不要提取仅与文本主题沾边的无关实体
8. 为每个实体给出 relevance（与「{focus_entity}」的相关度）：核心直接关联 >0.7，间接/弱相关 0.3-0.5；相关度 <0.3 的实体不要提取
9. 在 focus_entity_type 字段给出「{focus_entity}」的类型判定（person/concept/technology/event/organization 之一）"""
        else:
            system_prompt += """
7. 为每个实体给出 relevance（与文本主题的相关度）：核心 >0.7，次要 0.3-0.5"""

        result = await self.llm.structured_extract(
            text=text,
            response_model=EntityExtractionResult,
            system_prompt=system_prompt,
        )

        return result

    async def extract_simple(self, text: str) -> dict:
        """简化提取（不需要 LLM 时的规则基元）

        适用于 LLM 不可用时，返回空结构。
        """
        return {"entities": [], "relations": []}

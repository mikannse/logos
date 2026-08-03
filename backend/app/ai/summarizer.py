"""知识点摘要生成器

为图谱中的实体生成简明摘要，提取关键事实。
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.ai.llm_client import LLMClient


class ExtractedMilestone(BaseModel):
    """带年份的关键里程碑"""
    year: int = Field(description="事件年份")
    title: str = Field(description="里程碑标题（<=20字）")
    description: str = Field(description="简要说明（<=40字）")


class MilestoneExtractionResult(BaseModel):
    """里程碑结构化提取结果"""
    milestones: list[ExtractedMilestone] = Field(description="按年份排列的关键里程碑（5-10个）")


class Summarizer:
    """知识点摘要生成

    为实体生成中英文摘要，提取关键事实列表。
    """

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()

    async def generate_summary(self, entity_data: dict) -> str:
        """生成实体摘要

        Args:
            entity_data: {id, name, type, summary(optional), wiki_url, ...}

        Returns:
            生成的摘要文本
        """
        name = entity_data.get("name", "")
        entity_type = entity_data.get("type", "entity")
        existing_summary = entity_data.get("summary", "")

        # If we already have a Wikidata description, possibly enhance it
        if existing_summary:
            return existing_summary

        # Otherwise, try to generate one via LLM
        prompt = f"""请用一句话（<=50字）介绍「{name}」（{entity_type}）。
要求：简明扼要，说清楚它是什么。"""

        summary = await self.llm.generate_summary(prompt, max_length=100)
        return summary or ""

    async def extract_milestones(
        self, focus_entity: str, text: str
    ) -> list[ExtractedMilestone]:
        """从文本中结构化提取带年份的演化里程碑

        Args:
            focus_entity: 焦点实体（中心名词）
            text: 非结构化文本（如 Web 搜索摘要）

        Returns:
            按年份排列的里程碑列表（LLM 未配置/失败时为空）
        """
        system_prompt = f"""你是一个历史演化分析专家。从给定文本中提取「{focus_entity}」的关键里程碑事件。

规则：
1. 只提取有明确年份依据的事件（若年份缺失但描述明显，可给出合理近似年份）
2. 按年份从早到晚输出 5-10 个里程碑
3. title <=20字（如"发布 iPhone"），description <=40字（如"智能手机革命性产品"）
4. 只保留对该实体演化真正重要的转折点，不要罗列无关琐事"""

        result = await self.llm.structured_extract(
            text=text,
            response_model=MilestoneExtractionResult,
            system_prompt=system_prompt,
        )

        if result is None:
            return []
        return result.milestones

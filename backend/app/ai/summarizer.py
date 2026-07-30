"""知识点摘要生成器

为图谱中的实体生成简明摘要，提取关键事实。
"""

from typing import Optional

from app.ai.llm_client import LLMClient


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

    async def extract_key_facts(self, text: str, max_facts: int = 5) -> list[dict]:
        """从文本中提取关键事实

        Returns:
            [{"fact": str, "confidence": float}, ...]
        """
        # TODO: 实现结构化事实提取
        return []

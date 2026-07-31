"""图谱构建服务 — AI 数据管道编排

冷启动构建策略：
1. Wikidata 获取结构化数据（即时，已实现）
2. LLM 实体/关系提取（非结构化 → 结构化）
3. AI Web Search 补充（最新信息）
4. 统一写入 Neo4j 并标注置信度
5. 通过 SSE 推送增量更新
"""

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

from app.ai.llm_client import LLMClient
from app.ai.extractor import EntityExtractor
from app.ai.web_search import WebSearch
from app.ai.summarizer import Summarizer
from app.repositories.wikidata_repo import WikidataRepository
from app.repositories.neo4j_repo import Neo4jRepository
from app.core.cache import CacheService
from app.services.search_service import SearchService


class GraphBuilder:
    """图谱构建器 — 协调 AI 数据管道"""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        extractor: Optional[EntityExtractor] = None,
        web_search: Optional[WebSearch] = None,
        summarizer: Optional[Summarizer] = None,
        wikidata: Optional[WikidataRepository] = None,
        neo4j: Optional[Neo4jRepository] = None,
        cache: Optional[CacheService] = None,
        search_service: Optional[SearchService] = None,
    ):
        self.llm = llm or LLMClient()
        self.extractor = extractor or EntityExtractor(self.llm)
        self.web_search = web_search or WebSearch(self.llm)
        self.summarizer = summarizer or Summarizer(self.llm)
        self.wikidata = wikidata or WikidataRepository()
        self.neo4j = neo4j or Neo4jRepository()
        self.cache = cache or CacheService()
        self.search_service = search_service or SearchService(
            wikidata_repo=self.wikidata,
            neo4j_repo=self.neo4j,
            cache=self.cache,
        )

        # SSE event storage: noun_id → list of events
        self._building_tasks: dict[str, asyncio.Task] = {}
        self._sse_events: dict[str, list[dict]] = {}

    async def build_graph(self, query: str, language: str = "zh"):
        """冷启动构建主体流程

        1. Wikidata 结构化数据 → Neo4j
        2. AI Web Search（异步并行）
        3. LLM 实体/关系提取
        4. 写入 Neo4j
        5. 推送 SSE 增量
        """
        noun_id = f"cold-{query.lower().replace(' ', '_')}"

        self._add_sse_event(noun_id, {
            "type": "build_started",
            "message": f"开始构建「{query}」的知识图谱",
            "progress": 0,
        })

        try:
            # Phase 1: Wikidata (0-30%)
            self._add_sse_event(noun_id, {
                "type": "progress",
                "message": "正在查询 Wikidata 结构化数据...",
                "progress": 10,
            })

            wikidata_entities = await self.wikidata.search(query, language=language)
            if not wikidata_entities and language == "zh":
                wikidata_entities = await self.wikidata.search(query, language="en")

            self._add_sse_event(noun_id, {
                "type": "progress",
                "message": f"已获取 {len(wikidata_entities)} 个 Wikidata 实体",
                "progress": 30,
            })

            # Write Wikidata entities to Neo4j
            for entity in wikidata_entities:
                entity_dict = self.search_service._entity_to_dict(entity)
                await self.neo4j.upsert_entity(entity_dict)

            # Phase 2: AI Web Search + Entity Extraction (30-80%)
            self._add_sse_event(noun_id, {
                "type": "progress",
                "message": "正在通过 AI 搜索补充信息...",
                "progress": 40,
            })

            # Search and extract
            search_result = await self.web_search.search_and_extract(query)

            if search_result and search_result.get("summary"):
                # Try LLM entity/relation extraction
                llm_extraction = await self.extractor.extract_from_text(
                    search_result["summary"]
                )

                if llm_extraction:
                    # Write extracted entities to Neo4j
                    for entity in llm_extraction.entities:
                        await self.neo4j.upsert_entity({
                            "id": f"llm_{entity.name.lower().replace(' ', '_')}",
                            "name": entity.name,
                            "type": entity.type,
                            "confidence": 0.5,  # LLM-extracted, medium confidence
                            "summary": entity.description,
                        })

                    # Write extracted relations to Neo4j（实体名 → llm_* ID 解析）
                    for rel in llm_extraction.relations:
                        await self.neo4j.upsert_relation(
                            source_id=f"llm_{rel.source.lower().replace(' ', '_')}",
                            target_id=f"llm_{rel.target.lower().replace(' ', '_')}",
                            rel_type=rel.relation_type.upper(),
                            confidence=rel.confidence,
                            source_url="",
                            evidence=rel.description,
                        )

                    self._add_sse_event(noun_id, {
                        "type": "nodes_added",
                        "message": f"AI 提取了 {len(llm_extraction.entities)} 个实体和 {len(llm_extraction.relations)} 个关系",
                        "entities": [e.model_dump() for e in llm_extraction.entities],
                        "relations": [r.model_dump() for r in llm_extraction.relations],
                        "progress": 70,
                    })

            # Phase 3: Generate summaries (80-100%)
            self._add_sse_event(noun_id, {
                "type": "progress",
                "message": "正在生成摘要...",
                "progress": 90,
            })

            self._add_sse_event(noun_id, {
                "type": "build_completed",
                "message": f"「{query}」的知识图谱构建完成",
                "progress": 100,
            })

        except Exception as e:
            logger.exception("图谱构建失败: query=%r", query)
            self._add_sse_event(noun_id, {
                "type": "build_error",
                "message": f"构建过程中出现错误: {str(e)}",
                "progress": -1,
            })

    def start_build(self, query: str, language: str = "zh"):
        """异步启动冷启动构建（同一 query 去重，已在构建中则跳过）"""
        noun_id = f"cold-{query.lower().replace(' ', '_')}"

        # 已存在进行中的构建则直接返回，避免重复触发付费 LLM 管道
        existing = self._building_tasks.get(noun_id)
        if existing is not None and not existing.done():
            return noun_id

        # Initialize SSE events for this noun
        if noun_id not in self._sse_events:
            self._sse_events[noun_id] = []

        # Start background task，完成时清理引用
        task = asyncio.create_task(self.build_graph(query, language))
        self._building_tasks[noun_id] = task
        task.add_done_callback(lambda t: self._building_tasks.pop(noun_id, None))

        return noun_id

    def get_sse_events(self, noun_id: str, since_index: int = 0) -> list[dict]:
        """获取 SSE 事件（用于 SSE 推送）"""
        events = self._sse_events.get(noun_id, [])
        return events[since_index:]

    def _add_sse_event(self, noun_id: str, event: dict):
        if noun_id not in self._sse_events:
            self._sse_events[noun_id] = []
        events = self._sse_events[noun_id]
        events.append(event)
        # 每个名词最多保留最近 200 条事件，防止无界累积
        if len(events) > 200:
            del events[: len(events) - 200]


_default_builder: Optional[GraphBuilder] = None


def get_default_builder() -> GraphBuilder:
    """全局共享的 GraphBuilder 单例（nouns / sse 共用，确保 SSE 事件可达）"""
    global _default_builder
    if _default_builder is None:
        _default_builder = GraphBuilder()
    return _default_builder

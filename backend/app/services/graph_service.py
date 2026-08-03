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
from app.ai.extractor import EntityExtractor, EntityExtractionResult
from app.ai.web_search import WebSearch
from app.ai.summarizer import Summarizer
from app.repositories.wikidata_repo import WikidataRepository
from app.repositories.neo4j_repo import Neo4jRepository
from app.core.cache import CacheService
from app.services.search_service import SearchService


# ---- LLM 提取结果 → 图谱合并（P3：相关性过滤 + llm_* ID 统一解析） ----

# LLM 实体相关度过滤阈值：低于该值不入图谱（无关噪声）
RELEVANCE_FILTER_THRESHOLD = 0.5
# 无法解析为 Wikidata QID 的 llm_* 实体，相关度封顶（标低相关，弱化展示）
MAX_UNRESOLVED_RELEVANCE = 0.5
# 关系类型白名单（LLM 输出可能不合法，落库前归一）
_SEMANTIC_REL_TYPES = {
    "influence", "affiliation", "creation", "competition", "collaboration", "other",
}
# 合法节点类型（P7/P10：7 种）；未知类型归一为 entity
_VALID_NODE_TYPES = {
    "person", "entity", "event", "concept", "technology", "organization", "category",
}


def llm_entity_id(name: str) -> str:
    """llm_* 前缀的实体 ID（名称 slug 化）"""
    return f"llm_{name.lower().replace(' ', '_')}"


async def resolve_qid(
    name: str,
    wikidata: WikidataRepository,
    cache: Optional[CacheService] = None,
) -> str:
    """将实体名称解析为统一 ID

    Wikidata wbsearchentities label/alias 精确命中 → QID；否则保留 llm_* ID。
    仅精确匹配才解析（避免错配），无法解析保留 llm_* 前缀并标低相关度。
    解析结果缓存 1h，避免重复打 Wikidata。
    """
    cache_key = f"qid_resolve:{name}"
    if cache is not None:
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

    target = name.casefold()
    qid = llm_entity_id(name)
    try:
        hits = await wikidata.search_raw(name, language="zh", limit=5)
        for hit in hits:
            label = hit.get("label", "")
            if label and label.casefold() == target:
                qid = hit["id"]
                break
            for alias in hit.get("aliases", []):
                if alias.casefold() == target:
                    qid = hit["id"]
                    break
            if qid.startswith("Q"):
                break
    except Exception:
        pass  # 解析失败保留 llm_* ID

    if cache is not None:
        try:
            await cache.set(cache_key, qid, ttl=3600)
        except Exception:
            pass
    return qid


async def merge_llm_entities(
    extraction: EntityExtractionResult,
    center_id: str,
    center_names: list[str],
    wikidata: WikidataRepository,
    neo4j: Neo4jRepository,
    cache: Optional[CacheService] = None,
    center_entity_type: Optional[str] = None,
    existing_node_ids: Optional[set] = None,
    existing_edge_keys: Optional[set] = None,
    existing_relevance: Optional[dict] = None,
) -> dict:
    """将 LLM 提取结果合并写入图谱（P2/P3/P7 规则）

    - 实体按 relevance >= 0.5 过滤（无关噪声不写入）
    - 名称优先解析为 Wikidata QID（消除两套 ID 体系造成的重复节点）
    - 无法解析的保留 llm_* 前缀，relevance 封顶 0.5（低相关弱化）
    - 中心实体/中心别名不重复写入
    - 关系仅当两端实体都解析成功才写入（丢弃悬空关系）
    - 节点类型归一为 7 种合法类型（P7）
    - AI 兜底类型（P7 Part B）：中心规则类型为 entity 且 LLM 给出 focus_entity_type
      时，用 LLM 判定覆盖并写回（仅在规则推断失守时启用）
    - existing_node_ids / existing_edge_keys：基础图谱（Wikidata 优先）已有的
      节点/边不覆盖写库，保证「同 ID 节点 Wikidata 优先」契约（P5 丰富合并）

    Returns:
        {"nodes": [...新增节点 dict], "edges": [...新增边 dict],
         "focus_entity_type": Optional[str] 覆盖后的中心类型}
    """
    threshold = RELEVANCE_FILTER_THRESHOLD
    entities = [e for e in extraction.entities if e.relevance >= threshold]

    existing_nodes = existing_node_ids or set()
    existing_edges = existing_edge_keys or set()

    # 解析 ID（并发）；name → (id, relevance)
    resolved = await asyncio.gather(
        *[resolve_qid(e.name, wikidata, cache=cache) for e in entities],
        return_exceptions=True,
    )

    center_ids = set(center_names) | ({center_id} if center_id else set())
    name_to_id: dict[str, str] = {}
    id_relevance: dict[str, float] = {}
    new_nodes: list[dict] = []
    seen_ids: set[str] = set()
    # 中心实体相关度恒为 1.0（语义：与焦点最相关），参与触及中心的边计算，
    # 避免 min(兜底0.5, 节点relevance) 把强关联边错误压低到 0.5
    if center_id:
        id_relevance[center_id] = 1.0
    # 基础图谱已有节点（Wikidata 优先）也并入相关度，供触及它们的边计算真实值
    if existing_relevance:
        id_relevance.update(existing_relevance)

    # 中心类型 AI 兜底：仅当规则推断为 entity 且 LLM 给出合法类型时覆盖
    focus_entity_type: Optional[str] = None
    llm_type = (extraction.focus_entity_type or "").strip().lower()
    if center_entity_type in (None, "entity") and llm_type in _VALID_NODE_TYPES:
        focus_entity_type = llm_type

    for entity, entity_id in zip(entities, resolved):
        if not isinstance(entity_id, str):
            entity_id = llm_entity_id(entity.name)
        # 中心实体/中心别名不重复写入，名称映射到中心 ID（关系落边用）
        if entity_id in center_ids or entity.name in center_names:
            name_to_id[entity.name] = center_id or entity_id
            continue
        name_to_id[entity.name] = entity_id
        if entity_id in seen_ids:
            # 同名实体解析到同一 ID（如多语言别名）→ 不重复写节点
            continue
        seen_ids.add(entity_id)
        # Wikidata 基础图谱已有该节点 → 不覆盖（Wikidata 优先契约）
        if entity_id in existing_nodes:
            continue
        # 无法解析为 QID → 低相关度弱化
        relevance = entity.relevance
        if entity_id.startswith("llm_"):
            relevance = min(relevance, MAX_UNRESOLVED_RELEVANCE)
        id_relevance[entity_id] = relevance
        node_type = entity.type if entity.type in _VALID_NODE_TYPES else "entity"
        node = {
            "id": entity_id,
            "name": entity.name,
            "type": node_type,
            "confidence": 0.5,  # LLM 提取，中等置信度
            "relevance": relevance,
            "summary": entity.description,
        }
        new_nodes.append(node)
        await neo4j.upsert_entity(node)

    # 中心名称 → 中心 ID 映射（关系落边需要）
    for cn in center_names:
        name_to_id.setdefault(cn, center_id or cn)

    # 关系：两端都解析成功才写入
    new_edges: list[dict] = []
    seen_edges: set[tuple] = set()
    for rel in extraction.relations:
        src_id = name_to_id.get(rel.source)
        tgt_id = name_to_id.get(rel.target)
        if not src_id or not tgt_id or src_id == tgt_id:
            continue
        rel_type = rel.relation_type.lower()
        if rel_type not in _SEMANTIC_REL_TYPES:
            rel_type = "other"
        key = (src_id, tgt_id, rel_type)
        if key in seen_edges or key in existing_edges:
            continue
        seen_edges.add(key)
        edge_relevance = min(
            id_relevance.get(src_id, 0.5),
            id_relevance.get(tgt_id, 0.5),
        )
        await neo4j.upsert_relation(
            source_id=src_id,
            target_id=tgt_id,
            rel_type=rel_type.upper(),
            confidence=rel.confidence,
            evidence=rel.description,
            relevance=edge_relevance,
        )
        new_edges.append({
            "source": src_id,
            "target": tgt_id,
            "type": rel_type,
            "confidence": rel.confidence,
            "relevance": edge_relevance,
            "evidence": rel.description,
        })

    return {"nodes": new_nodes, "edges": new_edges, "focus_entity_type": focus_entity_type}


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

            # Search and extract（按实体类型路由兜底源）
            search_result = await self.web_search.search_and_extract(
                query,
                entity_type=wikidata_entities[0].type if wikidata_entities else None,
            )

            if search_result and search_result.get("summary"):
                # Try LLM entity/relation extraction（焦点锚定 query）
                llm_extraction = await self.extractor.extract_from_text(
                    search_result["summary"],
                    focus_entity=query,
                )

                if llm_extraction:
                    # 按 P2/P3 规则过滤（relevance>=0.5）+ 统一 ID 解析后写入 Neo4j
                    center_id = wikidata_entities[0].id if wikidata_entities else noun_id
                    center_names = [query]
                    if wikidata_entities:
                        center_names.append(wikidata_entities[0].label)
                    await merge_llm_entities(
                        llm_extraction,
                        center_id,
                        center_names,
                        self.wikidata,
                        self.neo4j,
                        cache=self.cache,
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

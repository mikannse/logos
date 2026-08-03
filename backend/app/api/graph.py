import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Query

from app.models.graph import GraphResponse, GraphNode, GraphEdge
from app.repositories.neo4j_repo import Neo4jRepository
from app.repositories.wikidata_repo import WikidataRepository, WikidataEntity
from app.core.cache import CacheService
from app.core.neo4j_client import Neo4jClient
from app.ai.web_search import WebSearch
from app.ai.extractor import EntityExtractor
from app.services.graph_service import merge_llm_entities

router = APIRouter(tags=["graph"])

_neo4j_repo: Neo4jRepository | None = None
_wikidata_repo: WikidataRepository | None = None
_cache: CacheService | None = None

# ---- Wikidata 关系属性白名单（P4：收敛去噪 + P8：可映射属性） ----

# 强关联属性（P4 收敛白名单 + 人物核心关系扩展）——不含 P31/P279 分类属性。
# 新增 P1327（合作者）/ P69（教育）/ P108（雇主）/ P102（政党）等人物常见属性，
# 否则马克思的恩格斯（P1327）、柏林大学（P69）等核心关联会被白名单过滤掉。
_STRONG_RELATION_PROPS = [
    "P800", "P1416", "P106", "P463", "P910", "P127", "P355", "P1830",
    "P1327", "P69", "P108", "P102",
]
# P8 扩展可映射属性（追加，提供更多语义关系；含家庭/地理/研究领域等中性关联）
_EXTRA_RELATION_PROPS = [
    "P50", "P144", "P2860", "P737", "P361",
    "P26", "P19", "P20", "P937", "P101",
]
# 分类属性：P31（instance of）/ P279（subclass of）目标降级为 category 节点
_CATEGORY_PROPS = ["P31", "P279"]

# P8: Wikidata 属性 → Logos 语义关系类型映射
_RELATION_TYPE_MAP = {
    "P800": "creation", "P50": "creation", "P144": "creation",        # 创作/作品关联
    "P106": "affiliation", "P1416": "affiliation", "P463": "affiliation",  # 隶属
    "P127": "affiliation", "P355": "affiliation", "P361": "affiliation",
    "P69": "affiliation", "P108": "affiliation", "P102": "affiliation",  # 教育/雇主/政党
    "P1327": "collaboration",                                         # 合作者
    "P2860": "influence", "P737": "influence",                        # 影响
    "P910": "other", "P1830": "other", "P279": "other",               # 其他/分类
    "P26": "other", "P19": "other", "P20": "other",                   # 配偶/出生地/死亡地
    "P937": "other", "P101": "other",                                 # 工作地/研究领域
}

# 提取顺序：语义类型优先的属性在前（去重时先到先得），分类属性垫底
_RELATION_PROPS = [
    "P800", "P50", "P144",
    "P1327",                                   # 合作者（collaboration）
    "P737", "P2860",                            # 影响
    "P106", "P1416", "P463", "P127", "P355", "P361",
    "P69", "P108", "P102",                      # 教育/雇主/政党（affiliation）
    "P910", "P1830", "P26", "P19", "P20", "P937", "P101",
    "P31", "P279",
]

_RELATED_LIMIT = 15

# P4: 节点类型优先级（越小越优先）——截断时低优先级类型被挤出
_NODE_TYPE_PRIORITY = {
    "person": 0,
    "event": 1,
    "technology": 2,
    "organization": 3,
    "concept": 4,
    "entity": 5,
    "category": 6,
}

# 中心/强关联/分类节点 relevance 约定
_CENTER_RELEVANCE = 1.0
_STRONG_RELEVANCE = 0.7
_CATEGORY_RELEVANCE = 0.2

# P5: 正常搜索触发 Web 丰富的强相关节点下限（<6 时触发）
_ENRICH_TRIGGER_THRESHOLD = 6
# Web 丰富结果缓存 TTL（1h）
_ENRICH_CACHE_TTL = 3600
# 触发丰富判定的强相关阈值
_STRONG_RELEVANCE_THRESHOLD = 0.6


def _edge_type_for_prop(prop: str) -> str:
    """Wikidata 属性 → 语义关系类型（未知/未映射 → other）"""
    return _RELATION_TYPE_MAP.get(prop, "other")


def get_neo4j_repo() -> Neo4jRepository:
    global _neo4j_repo
    if _neo4j_repo is None:
        client = Neo4jClient()
        _neo4j_repo = Neo4jRepository(client)
    return _neo4j_repo


def get_wikidata_repo() -> WikidataRepository:
    global _wikidata_repo
    if _wikidata_repo is None:
        _wikidata_repo = WikidataRepository()
    return _wikidata_repo


def get_cache() -> CacheService:
    global _cache
    if _cache is None:
        _cache = CacheService()
    return _cache


def _entity_to_node(entity_id: str | None, label: str | None, entity_type: str | None,
                     description: str | None, has_sitelink: bool,
                     relevance: float = 0.0) -> dict:
    """将 Wikidata 实体转为 Neo4j upsert dict（统一 shape，复用 search_service 契约）"""
    name = label or entity_id or ""
    return {
        "id": entity_id,
        "name": name,
        "label": name,  # GraphNode 使用 label 字段
        "type": entity_type or "entity",
        "confidence": 0.9 if has_sitelink else 0.6,
        "relevance": relevance,
        "summary": description or "",
    }


def _extract_related_qids(claims: dict, exclude_id: str) -> list[tuple[str, str]]:
    """从 claims 中提取 wikibase-item 类型的相关 QID，返回 [(qid, prop)]

    去重但保序：同一 qid 首次出现的属性优先（_RELATION_PROPS 语义类型在前）。
    """
    seen: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for prop_id in _RELATION_PROPS:
        for claim in claims.get(prop_id, []):
            mainsnak = claim.get("mainsnak", {})
            if mainsnak.get("datatype") != "wikibase-item":
                continue
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            if not isinstance(value, dict):
                continue
            qid = value.get("id", "")
            if qid and qid != exclude_id and qid not in seen:
                seen.add(qid)
                pairs.append((qid, prop_id))
    return pairs


def _type_priority_sort_key(node: dict) -> tuple:
    """节点类型优先级排序键：类型优先级优先，其次是否有站点链接（sitelink 优先）"""
    priority = _NODE_TYPE_PRIORITY.get(node.get("type"), 5)  # 未知类型按 entity 档
    has_sitelink = node.get("confidence", 0) >= 0.9
    return (priority, 0 if has_sitelink else 1)


def _edge_relevance_for_prop(prop: str) -> float:
    """边 relevance：分类属性弱关联，强关联属性 0.7"""
    if prop in _CATEGORY_PROPS:
        return _CATEGORY_RELEVANCE
    return _STRONG_RELEVANCE


# ---- P5: 正常搜索触发 Web 内容丰富（同步合并） ----

_web_search_instance: WebSearch | None = None
_extractor_instance: EntityExtractor | None = None


def get_web_search() -> WebSearch:
    global _web_search_instance
    if _web_search_instance is None:
        _web_search_instance = WebSearch()
    return _web_search_instance


def get_extractor() -> EntityExtractor:
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = EntityExtractor()
    return _extractor_instance


def _should_enrich(nodes: list[dict], edges: list[dict], center_id: str) -> bool:
    """Web 丰富触发判定：语义多样性不足时触发（替代旧"强相关节点数 <6"）

    旧规则只对"图谱薄"的实体触发，对 Wikidata 数据丰富的实体（人物/组织等）
    反而关闭了 Web 丰富通道——而这类实体的关键信息恰好在非结构化文本里
    （合作者、史实、所属运动等），导致图谱丰富度不足（如马克思缺核心关联）。

    新规则任一命中即触发：
    - 关联节点过少（< _ENRICH_TRIGGER_THRESHOLD）→ 图谱薄
    - 关联节点类型单一（< 3 种）→ 内容单调（如全 entity）
    - 语义边类型 ≤ 1 种 → 关系单调（如全 related_to）

    成本控制：丰富结果缓存 web_enrich:{qid} 1h，同一实体每小时至多一次 LLM 调用。
    """
    related = [
        n for n in nodes
        if n.get("id") != center_id and n.get("type") != "category"
    ]
    if len(related) < _ENRICH_TRIGGER_THRESHOLD:
        return True
    distinct_types = len({n.get("type", "entity") for n in related})
    if distinct_types < 3:
        return True
    distinct_edge_types = len({e.get("type", "other") for e in edges})
    if distinct_edge_types <= 1:
        return True
    return False


async def _enrich_from_web(
    center_id: str,
    center_entity,
    wikidata: WikidataRepository,
    neo4j: Neo4jRepository,
    web_search: WebSearch,
    extractor: EntityExtractor,
    cache: Optional[CacheService] = None,
    existing_node_ids: Optional[set] = None,
    existing_edge_keys: Optional[set] = None,
    existing_relevance: Optional[dict] = None,
) -> dict:
    """Web Search + LLM 丰富图谱（同步合并）

    1. 命中 web_enrich:{qid} 缓存（1h）直接返回
    2. web_search.search_and_extract(中心名, entity_type=中心实体类型) → 无摘要则返回空
    3. extractor.extract_from_text(summary, focus_entity=中心名)
    4. merge_llm_entities：relevance>=0.5 过滤 + QID 统一解析合并
    5. 缓存丰富结果 1h

    existing_node_ids / existing_edge_keys：基础图谱（Wikidata 优先）已有
    的节点/边，合并时跳过写库，保证「同 ID 节点 Wikidata 优先」契约。
    existing_relevance：基础图谱节点相关度，供触及它们的边计算真实值。

    LLM 未配置 / 任意一步失败 → 静默退化，返回空丰富（基础图谱不受影响）。
    """
    cache_key = f"web_enrich:{center_id}"
    if cache is not None:
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

    center_name = center_entity.label or center_id
    empty = {"nodes": [], "edges": []}
    try:
        search_result = await web_search.search_and_extract(
            center_name, entity_type=center_entity.type
        )
        if not search_result or not search_result.get("summary"):
            return empty

        extraction = await extractor.extract_from_text(
            search_result["summary"],
            focus_entity=center_name,
        )
        if extraction is None:
            return empty

        center_names = [center_name]
        if center_entity.label_en:
            center_names.append(center_entity.label_en)

        merged = await merge_llm_entities(
            extraction,
            center_id,
            center_names,
            wikidata,
            neo4j,
            cache=cache,
            center_entity_type=center_entity.type,
            existing_node_ids=existing_node_ids,
            existing_edge_keys=existing_edge_keys,
            existing_relevance=existing_relevance,
        )
    except Exception:
        # 丰富是增强通道：任何失败都不得拖垮基础图谱
        return empty

    # P7 Part B：中心规则类型为 entity 且 LLM 判定出类型 → 覆盖并写回 Neo4j
    focus_type = merged.get("focus_entity_type")
    if focus_type is not None:
        try:
            await neo4j.upsert_entity({
                "id": center_id,
                "name": center_entity.label,
                "type": focus_type,
                "confidence": 0.9 if (center_entity.sitelink_zh or center_entity.sitelink_en) else 0.6,
                "summary": center_entity.description,
            })
        except Exception:
            pass
        merged["center_type"] = focus_type

    if cache is not None:
        try:
            await cache.set(cache_key, merged, ttl=_ENRICH_CACHE_TTL)
        except Exception:
            pass
    return merged


def _build_response(center: str, data: dict, depth: int) -> GraphResponse:
    """统一的 GraphResponse 构造"""
    nodes = []
    for n in data.get("nodes", []):
        n = dict(n)
        # 兼容旧缓存：旧格式只有 name 键，无 label
        if "label" not in n:
            n["label"] = n.pop("name", n.get("id", ""))
        nodes.append(GraphNode(**n))
    return GraphResponse(
        center=center,
        nodes=nodes,
        edges=[GraphEdge(**e) for e in data.get("edges", [])],
        depth=depth,
        has_more=data.get("has_more", False),
    )


@router.get("/nouns/{noun_id}/graph")
async def get_graph(
    noun_id: str,
    depth: int = Query(default=1, ge=1, le=3, description="图谱深度（跳数）"),
):
    """关系图谱（分层加载）

    优先从 Neo4j 读取缓存，未命中则从 Wikidata 查询并缓存。
    """
    repo = get_neo4j_repo()
    cache = get_cache()
    cache_key = f"graph:{noun_id}:depth{depth}"

    # Try cache — 注意区分 "未命中" 与 "缓存了空结果"
    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            # 即使 nodes 为空也视为有效缓存（避免重复查询不存在 / 无关系的实体）
            return _build_response(noun_id, cached, depth)
    except Exception:
        pass  # 缓存不可用时降级 — 不影响主逻辑

    # Try Neo4j
    try:
        result = await repo.get_graph(noun_id, depth)
        nodes = result.get("nodes", [])
        if nodes:
            edges = result.get("edges", [])
            data = {"nodes": nodes, "edges": edges, "has_more": result.get("has_more", False)}
            await cache.set(cache_key, data, ttl=600)
            return _build_response(noun_id, data, depth)
    except Exception:
        pass

    # Fallback: build from Wikidata（可能含 Web 丰富）
    wikidata = get_wikidata_repo()
    try:
        graph_data = await build_graph_from_wikidata(noun_id, wikidata, repo, depth)
        # 缓存结果 — 即使空也缓存（短期 TTL 避免刷 Wikidata）；
        # 非空（可能含 Web 丰富）缓存 1h，避免重复触发付费 LLM 管道
        ttl = 60 if not graph_data.get("nodes") else _ENRICH_CACHE_TTL
        await cache.set(cache_key, graph_data, ttl=ttl)
        return _build_response(noun_id, graph_data, depth)
    except Exception:
        return GraphResponse(center=noun_id, depth=depth, has_more=False)


async def build_graph_from_wikidata(
    entity_id: str,
    wikidata: WikidataRepository,
    neo4j: Neo4jRepository,
    depth: int = 1,
    web_search: Optional[WebSearch] = None,
    extractor: Optional[EntityExtractor] = None,
    cache: Optional[CacheService] = None,
) -> dict:
    """从 Wikidata 构建基础图谱 + 可选 Web 丰富

    目前仅支持 depth=1（单跳）；多跳留待后续实现。

    去噪与排序（P4）：
    - P31/P279 分类目标保留但降级为 type:"category" + relevance:0.2
    - 关联节点按类型优先级排序后截断 _RELATED_LIMIT

    Web 丰富（P5）：
    - 基础图谱强相关节点（relevance>=0.6，不含中心）<6 时，同步触发
      Web Search + LLM 提取合并（结果缓存 1h）
    - 否则仅 Wikidata 基础图谱（省成本，NFR-6）
    """
    nodes = []
    edges = []
    center_entity = await wikidata.get_entity_by_qid(entity_id)

    if not center_entity:
        return {"nodes": [], "edges": [], "has_more": False}

    has_sitelink = bool(center_entity.sitelink_zh or center_entity.sitelink_en)

    # Center node（复用统一 shape，使用 'name' 键匹配 neo4j upsert 契约）
    center_node = _entity_to_node(
        entity_id, center_entity.label, center_entity.type,
        center_entity.description, has_sitelink,
        relevance=_CENTER_RELEVANCE,
    )
    nodes.append(center_node)
    await neo4j.upsert_entity(center_node)

    # Fetch related entities
    if depth < 1:
        return {"nodes": nodes, "edges": edges, "has_more": False}

    claims = center_entity.claims
    related_pairs = _extract_related_qids(claims, entity_id)

    truncated = len(related_pairs) > _RELATED_LIMIT
    # 多取 2x 候选再排序，保证高优先级类型（person 等）不被低优先级淹没后截断
    fetch_pairs = related_pairs[:_RELATED_LIMIT * 2]

    # 并发拉取关联实体详情，减少串行 N+1 延迟
    related_entities = await asyncio.gather(
        *[wikidata.get_entity_by_qid(qid) for qid, _ in fetch_pairs],
        return_exceptions=True,
    )

    related_nodes = []
    for (qid, prop), related in zip(fetch_pairs, related_entities):
        # gather(return_exceptions=True) 时元素可能是异常对象，需 isinstance 判断
        if not isinstance(related, WikidataEntity):
            continue
        is_category = prop in _CATEGORY_PROPS
        node_type = "category" if is_category else (related.type or "entity")
        node_relevance = _CATEGORY_RELEVANCE if is_category else _STRONG_RELEVANCE

        node = _entity_to_node(
            qid, related.label, node_type,
            related.description,
            bool(related.sitelink_zh or related.sitelink_en),
            relevance=node_relevance,
        )
        related_nodes.append((node, qid, prop, related))

    # 按类型优先级排序后截断（person > event > technology > organization > ... > category）
    related_nodes.sort(key=lambda item: _type_priority_sort_key(item[0]))
    related_nodes = related_nodes[:_RELATED_LIMIT]

    for node, qid, prop, related in related_nodes:
        nodes.append(node)
        await neo4j.upsert_entity(node)

        edge_relevance = _edge_relevance_for_prop(prop)
        edge_type = _edge_type_for_prop(prop)
        edge = {
            "source": entity_id,
            "target": qid,
            "type": edge_type,
            "confidence": 0.7,
            "relevance": edge_relevance,
            "source_url": center_entity.sitelink_zh or center_entity.sitelink_en or "",
            "evidence": center_entity.description or "",
        }
        edges.append(edge)

        # write edge to Neo4j（UPPER_SNAKE 存储，读取时归一小写语义类型）
        await neo4j.upsert_relation(
            source_id=entity_id,
            target_id=qid,
            rel_type=edge_type.upper(),
            confidence=0.7,
            source_url=edge["source_url"],
            evidence=edge["evidence"],
            relevance=edge_relevance,
        )

    # P5: 语义多样性不足时触发 Web Search + LLM 丰富（同步合并）
    # （替代旧"强相关节点 <6"：旧规则对数据丰富的实体反而关闭丰富通道，
    #   导致图谱单调。新规则按节点/边语义多样性判定，见 _should_enrich。）
    if depth >= 1 and _should_enrich(nodes, edges, entity_id):
        web = web_search or get_web_search()
        ext = extractor or get_extractor()
        enrich_cache = cache if cache is not None else get_cache()
        # Wikidata 优先契约：基础图谱已有节点/边不覆盖写库
        base_node_ids = {n["id"] for n in nodes}
        base_edge_keys = {(e["source"], e["target"], e["type"]) for e in edges}
        base_relevance = {n["id"]: n.get("relevance", 0.0) for n in nodes}
        enrich = await _enrich_from_web(
            entity_id, center_entity, wikidata, neo4j, web, ext, enrich_cache,
            existing_node_ids=base_node_ids,
            existing_edge_keys=base_edge_keys,
            existing_relevance=base_relevance,
        )
        if enrich:
            # 合并丰富节点/边（去重：同 ID 节点 Wikidata 优先）
            enrich_node_ids = {n["id"] for n in nodes}
            center_type_override = enrich.get("center_type")
            if center_type_override:
                for n in nodes:
                    if n["id"] == entity_id:
                        n["type"] = center_type_override
            for n in enrich.get("nodes", []):
                if n["id"] not in enrich_node_ids:
                    nodes.append(n)
                    enrich_node_ids.add(n["id"])
            seen_edges = {(e["source"], e["target"], e["type"]) for e in edges}
            for e in enrich.get("edges", []):
                key = (e["source"], e["target"], e["type"])
                if key not in seen_edges:
                    edges.append(e)
                    seen_edges.add(key)

    return {"nodes": nodes, "edges": edges, "has_more": truncated}

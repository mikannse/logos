from fastapi import APIRouter, Query

from app.models.graph import GraphResponse, GraphNode, GraphEdge
from app.repositories.neo4j_repo import Neo4jRepository
from app.repositories.wikidata_repo import WikidataRepository
from app.core.cache import CacheService
from app.core.neo4j_client import Neo4jClient

router = APIRouter(tags=["graph"])

_neo4j_repo: Neo4jRepository | None = None
_wikidata_repo: WikidataRepository | None = None
_cache: CacheService | None = None

# Wikidata 关键关系属性
_RELATION_PROPS = ["P31", "P279", "P361", "P101", "P800", "P106", "P1416", "P463"]
_RELATED_LIMIT = 15


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
                     description: str | None, has_sitelink: bool) -> dict:
    """将 Wikidata 实体转为 Neo4j upsert dict（统一 shape，复用 search_service 契约）"""
    name = label or entity_id or ""
    return {
        "id": entity_id,
        "name": name,
        "label": name,  # GraphNode 使用 label 字段
        "type": entity_type or "entity",
        "confidence": 0.9 if has_sitelink else 0.6,
        "summary": description or "",
    }


def _extract_related_qids(claims: dict, exclude_id: str) -> list[str]:
    """从 claims 中提取 wikibase-item 类型的相关 QID"""
    qids = []
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
            if qid and qid != exclude_id:
                qids.append(qid)
    # 去重但保序
    seen = set()
    unique = []
    for qid in qids:
        if qid not in seen:
            seen.add(qid)
            unique.append(qid)
    return unique


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

    # Fallback: build from Wikidata
    wikidata = get_wikidata_repo()
    try:
        graph_data = await build_graph_from_wikidata(noun_id, wikidata, repo, depth)
        # 缓存结果 — 即使空也缓存（短期 TTL 避免刷 Wikidata）
        ttl = 60 if not graph_data.get("nodes") else 600
        await cache.set(cache_key, graph_data, ttl=ttl)
        return _build_response(noun_id, graph_data, depth)
    except Exception:
        return GraphResponse(center=noun_id, depth=depth, has_more=False)


async def build_graph_from_wikidata(
    entity_id: str,
    wikidata: WikidataRepository,
    neo4j: Neo4jRepository,
    depth: int = 1,
) -> dict:
    """从 Wikidata 构建基础图谱

    目前仅支持 depth=1（单跳）；多跳留待后续实现。
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
    )
    nodes.append(center_node)
    await neo4j.upsert_entity(center_node)

    # Fetch related entities
    if depth < 1:
        return {"nodes": nodes, "edges": edges, "has_more": False}

    claims = center_entity.claims
    related_qids = _extract_related_qids(claims, entity_id)

    truncated = len(related_qids) > _RELATED_LIMIT
    fetch_qids = related_qids[:_RELATED_LIMIT]

    for qid in fetch_qids:
        related = await wikidata.get_entity_by_qid(qid)
        if not related:
            continue

        node = _entity_to_node(
            qid, related.label, related.type,
            related.description,
            bool(related.sitelink_zh or related.sitelink_en),
        )
        nodes.append(node)
        await neo4j.upsert_entity(node)

        edge = {
            "source": entity_id,
            "target": qid,
            "type": "related_to",
            "confidence": 0.7,
            "source_url": center_entity.sitelink_zh or center_entity.sitelink_en or "",
            "evidence": center_entity.description or "",
        }
        edges.append(edge)

        # write edge to Neo4j
        await neo4j.upsert_relation(
            source_id=entity_id,
            target_id=qid,
            rel_type="RELATED_TO",
            confidence=0.7,
            source_url=edge["source_url"],
            evidence=edge["evidence"],
        )

    return {"nodes": nodes, "edges": edges, "has_more": truncated}

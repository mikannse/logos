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

    # Try cache
    cached = await cache.get(cache_key)
    if cached and cached.get("nodes"):
        return GraphResponse(
            center=noun_id,
            nodes=[GraphNode(**n) for n in cached["nodes"]],
            edges=[GraphEdge(**e) for e in cached["edges"]],
            depth=depth,
            has_more=cached.get("has_more", False),
        )

    # Try Neo4j
    try:
        result = await repo.get_graph(noun_id, depth)
        nodes = result.get("nodes", [])
        if nodes:
            edges = result.get("edges", [])
            await cache.set(cache_key, result, ttl=600)
            return GraphResponse(
                center=noun_id,
                nodes=[GraphNode(**n) for n in nodes],
                edges=[GraphEdge(**e) for e in edges],
                depth=depth,
                has_more=result.get("has_more", False),
            )
    except Exception:
        pass

    # Fallback: build from Wikidata
    wikidata = get_wikidata_repo()
    try:
        graph_data = await build_graph_from_wikidata(noun_id, wikidata, repo, depth)
        await cache.set(cache_key, graph_data, ttl=600)
        return GraphResponse(
            center=noun_id,
            nodes=[GraphNode(**n) for n in graph_data["nodes"]],
            edges=[GraphEdge(**e) for e in graph_data["edges"]],
            depth=depth,
            has_more=graph_data.get("has_more", False),
        )
    except Exception:
        return GraphResponse(center=noun_id, depth=depth, has_more=False)


async def build_graph_from_wikidata(
    entity_id: str,
    wikidata: WikidataRepository,
    neo4j: Neo4jRepository,
    depth: int = 1,
) -> dict:
    """从 Wikidata 构建基础图谱

    1. 获取目标实体详情
    2. 获取重要关联实体（属性、子类、所属）
    3. 写入 Neo4j 缓存
    """
    nodes = []
    edges = []
    seen_ids = set()
    center_entity = await wikidata.get_entity_by_qid(entity_id)

    if not center_entity:
        return {"nodes": [], "edges": [], "has_more": False}

    seen_ids.add(entity_id)

    # Center node
    center_node = {
        "id": entity_id,
        "label": center_entity.label or entity_id,
        "type": center_entity.type or "entity",
        "confidence": 0.9 if center_entity.sitelink_zh or center_entity.sitelink_en else 0.6,
        "summary": center_entity.description or "",
    }
    nodes.append(center_node)
    await neo4j.upsert_entity(center_node)

    # Fetch related entities via Wikidata claims
    claims = center_entity.claims
    related_qids = set()

    # Extract key relation properties
    for prop_id in ["P31", "P279", "P361", "P101", "P800", "P106", "P1416", "P463"]:
        for claim in claims.get(prop_id, []):
            mainsnak = claim.get("mainsnak", {})
            if mainsnak.get("datatype") == "wikibase-item":
                datavalue = mainsnak.get("datavalue", {})
                value = datavalue.get("value", {})
                if isinstance(value, dict):
                    qid = value.get("id", "")
                    if qid and qid not in seen_ids:
                        related_qids.add(qid)

    # Fetch related entity details
    for qid in list(related_qids)[:15]:
        related = await wikidata.get_entity_by_qid(qid)
        if related:
            seen_ids.add(qid)
            node = {
                "id": qid,
                "label": related.label or qid,
                "type": related.type or "entity",
                "confidence": 0.9 if related.sitelink_zh or related.sitelink_en else 0.6,
                "summary": related.description or "",
            }
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

    return {"nodes": nodes, "edges": edges, "has_more": False}

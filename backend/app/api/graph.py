from fastapi import APIRouter, Query

from app.models.graph import GraphResponse, GraphNode, GraphEdge
from app.repositories.neo4j_repo import Neo4jRepository
from app.core.neo4j_client import Neo4jClient

router = APIRouter(tags=["graph"])

_neo4j_repo: Neo4jRepository | None = None


def get_neo4j_repo() -> Neo4jRepository:
    global _neo4j_repo
    if _neo4j_repo is None:
        client = Neo4jClient()
        _neo4j_repo = Neo4jRepository(client)
    return _neo4j_repo


@router.get("/nouns/{noun_id}/graph")
async def get_graph(
    noun_id: str,
    depth: int = Query(default=1, ge=1, le=3, description="图谱深度（跳数）"),
):
    """关系图谱（分层加载）

    返回该节点指定跳数范围内的所有关联。
    默认 depth=1，最多 depth=3，每跳 ≤ 50 节点。
    当 Neo4j 未连接时返回空图谱。
    """
    repo = get_neo4j_repo()
    try:
        result = await repo.get_graph(noun_id, depth)
        nodes = [GraphNode(**n) for n in result.get("nodes", [])]
        edges = [GraphEdge(**e) for e in result.get("edges", [])]
        return GraphResponse(
            center=noun_id,
            nodes=nodes,
            edges=edges,
            depth=depth,
            has_more=result.get("has_more", False),
        )
    except Exception:
        # Graceful fallback when Neo4j is unavailable
        return GraphResponse(center=noun_id, depth=depth, has_more=False)

from fastapi import APIRouter, Query

from app.models.graph import GraphResponse

router = APIRouter(tags=["graph"])


@router.get("/nouns/{noun_id}/graph")
async def get_graph(
    noun_id: str,
    depth: int = Query(default=1, ge=1, le=3, description="图谱深度（跳数）"),
):
    """关系图谱（分层加载）

    返回该节点指定跳数范围内的所有关联。
    默认 depth=1，最多 depth=3，每跳 ≤ 50 节点。
    """
    return GraphResponse(center=noun_id, depth=depth, has_more=False)

from fastapi import APIRouter

from app.models.timeline import TimelineResponse

router = APIRouter(tags=["timeline"])


@router.get("/nouns/{noun_id}/timeline")
async def get_timeline(noun_id: str):
    """演化时间轴

    返回 5-10 个关键里程碑，按时间排序。
    """
    return TimelineResponse(noun_id=noun_id)

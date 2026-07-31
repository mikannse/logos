from fastapi import APIRouter

from app.models.timeline import TimelineResponse
from app.services.timeline_service import TimelineService

router = APIRouter(tags=["timeline"])

_timeline_service: TimelineService | None = None


def get_timeline_service() -> TimelineService:
    global _timeline_service
    if _timeline_service is None:
        _timeline_service = TimelineService()
    return _timeline_service


@router.get("/nouns/{noun_id}/timeline")
async def get_timeline(noun_id: str):
    """演化时间轴

    从 Wikidata 带时间信息的声明提取关键里程碑，按时间排序，
    返回最多 10 个里程碑（含缓存）。
    """
    service = get_timeline_service()
    result = await service.get_timeline(noun_id)
    return TimelineResponse(**result)

from typing import Optional

from fastapi import APIRouter, Body
from pydantic import BaseModel

from app.services.history_service import SnapshotService

router = APIRouter(tags=["history"])

_history_service: SnapshotService | None = None


def get_history_service() -> SnapshotService:
    global _history_service
    if _history_service is None:
        _history_service = SnapshotService()
    return _history_service


class SnapshotRequest(BaseModel):
    """前端在搜索解析出实体并加载图谱/时间轴后，将完整快照 POST 到后端存储"""

    noun_id: str
    query: str
    entity: dict
    graph: dict
    timeline: list
    saved_at: Optional[str] = None


@router.post("/history")
async def save_history(req: SnapshotRequest):
    """保存 / 更新搜索快照（同一名词重复搜索时覆盖更新）"""
    svc = get_history_service()
    record = svc.save_snapshot(req.noun_id, req.model_dump())
    return {"ok": True, "noun_id": req.noun_id, "saved_at": record["saved_at"]}


@router.get("/history")
async def list_history():
    """历史摘要列表（按保存时间倒序）"""
    svc = get_history_service()
    items = svc.list_snapshots()
    return {"items": items, "total": len(items)}


@router.get("/history/{noun_id}")
async def get_history(noun_id: str):
    """获取单个名词的完整快照；不存在时返回 exists=False（避免 404 增加前端分支）"""
    svc = get_history_service()
    snap = svc.get_snapshot(noun_id)
    if snap is None:
        return {"exists": False, "noun_id": noun_id}
    return {"exists": True, **snap}


@router.delete("/history/{noun_id}")
async def delete_history(noun_id: str):
    """删除单个名词的快照（隐私可删除）"""
    svc = get_history_service()
    deleted = svc.delete_snapshot(noun_id)
    return {"ok": True, "noun_id": noun_id, "deleted": deleted}

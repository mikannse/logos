from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.history_service import SnapshotService

router = APIRouter(tags=["history"])

_history_service: SnapshotService | None = None

# V3c: 快照防御上限——防异常/未来多跳累积导致单文件无限膨胀
_MAX_GRAPH_NODES = 200
_MAX_GRAPH_EDGES = 200
_MAX_PAYLOAD_BYTES = 1024 * 1024  # 1MB


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


def _validate_snapshot_graph(graph: dict) -> dict:
    """V3c: 防御性校验——节点/边数量上限 + 边端点引用校验

    返回清洗后的 graph（丢弃悬空边）；超限抛 HTTPException。
    """
    graph = graph or {}
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []

    if len(nodes) > _MAX_GRAPH_NODES:
        raise HTTPException(
            status_code=400,
            detail=f"图谱节点数 {len(nodes)} 超过上限 {_MAX_GRAPH_NODES}",
        )
    if len(edges) > _MAX_GRAPH_EDGES:
        raise HTTPException(
            status_code=400,
            detail=f"图谱边数 {len(edges)} 超过上限 {_MAX_GRAPH_EDGES}",
        )

    # 校验边端点均在节点集合内，丢弃悬空边（防异常数据写入）
    node_ids = {n.get("id") for n in nodes if isinstance(n, dict)}
    valid_edges = [
        e for e in edges
        if isinstance(e, dict) and e.get("source") in node_ids and e.get("target") in node_ids
    ]
    if len(valid_edges) != len(edges):
        graph = dict(graph)
        graph["edges"] = valid_edges

    return graph


@router.post("/history")
async def save_history(req: SnapshotRequest):
    """保存 / 更新搜索快照（同一名词重复搜索时覆盖更新）"""
    svc = get_history_service()

    # V3c: 防御上限——payload 总字节限制
    import json as _json
    try:
        payload_bytes = len(_json.dumps(req.model_dump(), ensure_ascii=False).encode("utf-8"))
        if payload_bytes > _MAX_PAYLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"快照体积 {payload_bytes} 字节超过上限 {_MAX_PAYLOAD_BYTES}",
            )
    except HTTPException:
        raise
    except Exception:
        pass  # 序列化异常由下游兜底

    # V3c: 清洗 graph（数量上限 + 悬空边过滤）
    req = req.model_copy(update={"graph": _validate_snapshot_graph(req.graph)})

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

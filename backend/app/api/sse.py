"""SSE (Server-Sent Events) 端点

用于图谱增量更新推送。
前端订阅后，后端在冷启动构建完成时推送新增节点和边。
"""

import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.services.graph_service import GraphBuilder, get_default_builder

router = APIRouter(tags=["events"])


def get_graph_builder() -> GraphBuilder:
    # 与 nouns 路由共用同一全局单例，确保冷启动构建的 SSE 事件可被读取
    return get_default_builder()


@router.get("/events/graph-updates")
async def graph_updates(
    noun_id: str = Query(..., description="名词 ID"),
    since_index: int = Query(default=0, description="起始事件索引"),
):
    """SSE 图谱增量更新推送

    前端订阅此端点后，后端在冷启动构建过程中
    逐步推送新增节点和边。

    事件类型:
    - build_started: 构建开始
    - nodes_added: 新增节点和边
    - progress: 进度更新
    - build_completed: 构建完成
    - build_error: 构建出错
    """
    builder = get_graph_builder()

    async def event_generator():
        current_index = since_index
        timeout_count = 0
        max_timeout = 60  # 60 heartbeats = 300 seconds max

        while timeout_count < max_timeout:
            events = builder.get_sse_events(noun_id, current_index)
            if events:
                for event in events:
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    current_index += 1
                    if event.get("type") in ("build_completed", "build_error"):
                        return
                timeout_count = 0
            else:
                timeout_count += 1
                # Send heartbeat
                yield f": heartbeat {timeout_count}\n\n"
                await asyncio.sleep(5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

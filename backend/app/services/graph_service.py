"""图谱服务 - Graph Service"""


class GraphService:
    """图谱业务逻辑"""

    async def get_graph(self, noun_id: str, depth: int = 1):
        """获取指定节点的关联图谱"""
        # TODO: 实现图谱查询逻辑
        return {"center": noun_id, "nodes": [], "edges": [], "depth": depth, "has_more": False}

    async def get_incremental_updates(self, noun_id: str):
        """获取增量节点/边（SSE 推送用）"""
        # TODO: 实现增量更新
        return {"nodes": [], "edges": []}

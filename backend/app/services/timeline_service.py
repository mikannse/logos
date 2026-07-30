"""时间轴服务 - Timeline Service"""


class TimelineService:
    """演化时间轴业务逻辑"""

    async def get_timeline(self, noun_id: str):
        """获取指定名词的演化时间轴"""
        # TODO: 实现时间轴查询逻辑
        return {"noun_id": noun_id, "milestones": [], "total": 0}

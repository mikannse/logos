import pytest


class TestGraphService:
    """GraphService 测试"""

    @pytest.mark.asyncio
    async def test_get_graph_default_depth(self):
        from app.services.graph_service import GraphService
        service = GraphService()
        result = await service.get_graph("test_entity")
        assert result["center"] == "test_entity"
        assert result["depth"] == 1

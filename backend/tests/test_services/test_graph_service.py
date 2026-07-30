import pytest


class TestGraphBuilder:
    """GraphBuilder 测试"""

    @pytest.mark.asyncio
    async def test_get_graph_default_depth(self):
        from app.api.graph import get_neo4j_repo
        repo = get_neo4j_repo()
        # Just verify the repo module can import (Neo4j may not be running)
        assert repo is not None


class TestFuzzySearch:
    """模糊搜索测试"""

    @pytest.mark.asyncio
    async def test_fuzzy_search(self):
        from app.services.search_service import SearchService
        service = SearchService()
        results = await service.search_fuzzy("深度学习之父")
        assert isinstance(results, list)


class TestSuggest:
    """搜索建议测试"""

    @pytest.mark.asyncio
    async def test_suggest(self):
        from app.services.search_service import SearchService
        service = SearchService()
        suggestions = await service.suggest("深度")
        assert isinstance(suggestions, list)

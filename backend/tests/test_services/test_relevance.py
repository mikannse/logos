"""P1: GraphNode/GraphEdge relevance 字段 + Neo4j relevance 持久化读写"""

import pytest
from pydantic import ValidationError

from app.models.graph import GraphNode, GraphEdge
from app.repositories.neo4j_repo import Neo4jRepository


# ---------- Neo4j 驱动 Fake  plumbing ----------

class FakeNode:
    def __init__(self, props: dict):
        self._props = props

    def items(self):
        return self._props.items()


class FakeRel:
    def __init__(self, rel_type: str, props: dict, start: FakeNode, end: FakeNode):
        self.type = rel_type
        self._props = props
        self.start_node = start
        self.end_node = end

    def items(self):
        return self._props.items()

    def get(self, key, default=None):
        return self._props.get(key, default)


class FakePath:
    def __init__(self, nodes, relationships):
        self.nodes = nodes
        self.relationships = relationships


class FakeResult:
    def __init__(self, records=None, single_record=None):
        self._records = records or []
        self._single = single_record

    async def fetch(self, n):
        return self._records[:n]

    async def single(self):
        return self._single


class FakeSession:
    def __init__(self, driver):
        self._driver = driver

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def run(self, query, **params):
        self._driver.calls.append((query, params))
        if self._driver.run_handler:
            return self._driver.run_handler(query, params)
        return FakeResult(single_record={"found": 1})


class FakeDriver:
    def __init__(self, run_handler=None):
        self.calls: list[tuple[str, dict]] = []
        self.run_handler = run_handler

    def session(self):
        return FakeSession(self)


class FakeClient:
    """模拟 Neo4jClient 的延迟 driver 属性"""

    def __init__(self, driver: FakeDriver):
        self._driver = driver

    @property
    async def driver(self):
        return self._driver


def make_repo(driver: FakeDriver) -> Neo4jRepository:
    return Neo4jRepository(client=FakeClient(driver))


# ---------- 模型字段 ----------

class TestModelRelevance:
    def test_node_relevance_default_zero(self):
        node = GraphNode(id="Q1", label="x")
        assert node.relevance == 0.0

    def test_edge_relevance_default_zero(self):
        edge = GraphEdge(source="Q1", target="Q2", type="other")
        assert edge.relevance == 0.0

    def test_relevance_bounds_enforced(self):
        with pytest.raises(ValidationError):
            GraphNode(id="Q1", label="x", relevance=1.5)
        with pytest.raises(ValidationError):
            GraphNode(id="Q1", label="x", relevance=-0.1)
        with pytest.raises(ValidationError):
            GraphEdge(source="Q1", target="Q2", type="other", relevance=2.0)

    def test_relevance_semantics_distinct_from_confidence(self):
        node = GraphNode(id="Q1", label="x", confidence=0.9, relevance=0.2)
        assert node.confidence == 0.9
        assert node.relevance == 0.2


# ---------- Neo4j 写入 ----------

class TestNeo4jRelevanceWrite:
    @pytest.mark.asyncio
    async def test_upsert_entity_writes_relevance(self):
        driver = FakeDriver()
        repo = make_repo(driver)
        ok = await repo.upsert_entity({
            "id": "Q1", "name": "苹果公司", "type": "organization",
            "confidence": 0.9, "summary": "", "relevance": 0.7,
        })
        assert ok is True
        query, params = driver.calls[-1]
        assert "relevance" in query
        assert params["relevance"] == 0.7

    @pytest.mark.asyncio
    async def test_upsert_entity_without_relevance_preserves_existing(self):
        """未提供 relevance 时用 coalesce 保留库中已有值（不覆盖为 0）"""
        driver = FakeDriver()
        repo = make_repo(driver)
        ok = await repo.upsert_entity({
            "id": "Q1", "name": "x", "type": "entity",
            "confidence": 0.6, "summary": "",
        })
        assert ok is True
        query, params = driver.calls[-1]
        assert params["relevance"] is None
        assert "coalesce" in query.lower()

    @pytest.mark.asyncio
    async def test_upsert_relation_writes_relevance(self):
        driver = FakeDriver()
        repo = make_repo(driver)
        ok = await repo.upsert_relation(
            source_id="Q1", target_id="Q2", rel_type="CREATION",
            confidence=0.8, relevance=0.9,
        )
        assert ok is True
        _, params = driver.calls[-1]
        assert params["relevance"] == 0.9


# ---------- Neo4j 读取 ----------

def _make_graph_handler():
    """构造一条 center→related 路径，节点/边均带 relevance 属性"""
    center = FakeNode({
        "entityId": "Q1", "entityName": "中心", "entityType": "organization",
        "confidence": 0.9, "summary": "", "relevance": 1.0,
    })
    related = FakeNode({
        "entityId": "Q2", "entityName": "关联", "entityType": "person",
        "confidence": 0.8, "summary": "", "relevance": 0.7,
    })
    rel = FakeRel("CREATION", {
        "confidence": 0.8, "source": "", "evidence": "", "relevance": 0.9,
    }, center, related)
    path = FakePath([center, related], [rel])

    def handler(query, params):
        return FakeResult(records=[{"path": path}])

    return handler


class TestNeo4jRelevanceRead:
    @pytest.mark.asyncio
    async def test_get_graph_reads_node_and_edge_relevance(self):
        driver = FakeDriver(run_handler=_make_graph_handler())
        repo = make_repo(driver)
        result = await repo.get_graph("Q1", depth=1)

        nodes = {n["id"]: n for n in result["nodes"]}
        assert nodes["Q1"]["relevance"] == 1.0
        assert nodes["Q2"]["relevance"] == 0.7
        assert result["edges"][0]["relevance"] == 0.9

    @pytest.mark.asyncio
    async def test_get_graph_defaults_for_legacy_data_without_relevance(self):
        """旧数据无 relevance 属性：中心 1.0 / 连通节点 0.5 / 孤立节点 0.1"""
        center = FakeNode({
            "entityId": "Q1", "entityName": "中心", "entityType": "entity",
            "confidence": 0.9, "summary": "",
        })
        related = FakeNode({
            "entityId": "Q2", "entityName": "关联", "entityType": "entity",
            "confidence": 0.8, "summary": "",
        })
        rel = FakeRel("RELATED_TO", {"confidence": 0.7}, center, related)
        path = FakePath([center, related], [rel])

        def handler(query, params):
            return FakeResult(records=[{"path": path}])

        driver = FakeDriver(run_handler=handler)
        repo = make_repo(driver)
        result = await repo.get_graph("Q1", depth=1)

        nodes = {n["id"]: n for n in result["nodes"]}
        assert nodes["Q1"]["relevance"] == 1.0
        assert nodes["Q2"]["relevance"] == 0.5
        assert result["edges"][0]["relevance"] == 0.0


# ---------- API 层节点构造 ----------

class TestEntityToNode:
    def test_entity_to_node_includes_relevance(self):
        from app.api.graph import _entity_to_node
        node = _entity_to_node("Q1", "苹果公司", "organization", "科技公司", True, relevance=0.7)
        assert node["relevance"] == 0.7

    def test_entity_to_node_relevance_default(self):
        from app.api.graph import _entity_to_node
        node = _entity_to_node("Q1", "x", "entity", "", False)
        assert node["relevance"] == 0.0

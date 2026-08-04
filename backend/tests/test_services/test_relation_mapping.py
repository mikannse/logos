"""P8: 关系类型映射 + Neo4j 边规范化

- Wikidata 属性 → 6 种语义关系类型（创作/隶属/影响/竞争/合作/其他）
- build_graph_from_wikidata 写边用 UPPER_SNAKE（语义类型大写）
- get_graph 读回归一为小写语义类型；未知 / related to → other（前端 6 色板命中）
- upsert_relation 归一 UPPER_SNAKE
"""

import pytest

from app.api.graph import (
    _RELATION_TYPE_MAP,
    _edge_type_for_prop,
    _extract_related_qids,
    build_graph_from_wikidata,
)
from app.repositories.neo4j_repo import Neo4jRepository
from app.repositories.wikidata_repo import WikidataEntity
from tests.test_services.test_relevance import (
    FakeDriver,
    FakeClient,
    FakeNode,
    FakeRel,
    FakePath,
    FakeResult,
)


def item_claim(qid: str) -> dict:
    return {
        "mainsnak": {"datatype": "wikibase-item", "datavalue": {"value": {"id": qid}}}
    }


class TestRelationTypeMap:
    def test_creation_mappings(self):
        assert _RELATION_TYPE_MAP["P800"] == "creation"
        assert _RELATION_TYPE_MAP["P50"] == "creation"
        assert _RELATION_TYPE_MAP["P144"] == "creation"

    def test_affiliation_mappings(self):
        for p in ("P106", "P1416", "P463", "P127", "P355", "P361"):
            assert _RELATION_TYPE_MAP[p] == "affiliation"

    def test_influence_mappings(self):
        assert _RELATION_TYPE_MAP["P2860"] == "influence"
        assert _RELATION_TYPE_MAP["P737"] == "influence"

    def test_collaboration_mapping(self):
        assert _RELATION_TYPE_MAP["P1327"] == "collaboration"

    def test_education_employer_party_mappings(self):
        """教育/雇主/政党 → affiliation（人物核心关联，马克思的恩格斯/柏林大学）"""
        assert _RELATION_TYPE_MAP["P69"] == "affiliation"
        assert _RELATION_TYPE_MAP["P108"] == "affiliation"
        assert _RELATION_TYPE_MAP["P102"] == "affiliation"

    def test_family_place_mappings(self):
        """配偶/出生地/死亡地/工作地 → other（中性关联，展示但非语义色）"""
        assert _RELATION_TYPE_MAP["P26"] == "other"
        assert _RELATION_TYPE_MAP["P19"] == "other"
        assert _RELATION_TYPE_MAP["P20"] == "other"
        assert _RELATION_TYPE_MAP["P937"] == "other"

    def test_other_mappings(self):
        assert _RELATION_TYPE_MAP["P910"] == "other"
        assert _RELATION_TYPE_MAP["P1830"] == "other"
        assert _RELATION_TYPE_MAP["P279"] == "other"

    def test_unknown_prop_defaults_other(self):
        assert _edge_type_for_prop("P999") == "other"
        assert _edge_type_for_prop("P31") == "other"


class TestExtractRelatedQidsPairs:
    def test_returns_qid_prop_pairs(self):
        claims = {"P800": [item_claim("Q100")], "P1416": [item_claim("Q200")]}
        pairs = _extract_related_qids(claims, exclude_id="Q0")
        assert ("Q100", "P800") in pairs
        assert ("Q200", "P1416") in pairs

    def test_dedup_keeps_first_prop(self):
        claims = {"P800": [item_claim("Q100")], "P1416": [item_claim("Q100")]}
        pairs = _extract_related_qids(claims, exclude_id="Q0")
        assert pairs == [("Q100", "P800")]  # 语义类型优先属性先到

    def test_collaborator_and_education_include_in_whitelist(self):
        """P1327 合作者 / P69 教育在白名单中 → 恩格斯、柏林大学不被过滤"""
        claims = {
            "P1327": [item_claim("Q34787")],  # 恩格斯
            "P69": [item_claim("Q152087")],   # 柏林大学
        }
        pairs = _extract_related_qids(claims, exclude_id="Q0")
        assert ("Q34787", "P1327") in pairs
        assert ("Q152087", "P69") in pairs


class TestBuildGraphEdgeTypes:
    def make_entity(self, qid, label, claims):
        return WikidataEntity(
            id=qid, label=label, label_en=label, description="",
            type="entity", aliases=[], sitelink_zh="", sitelink_en="", claims=claims,
        )

    class FakeWD:
        def __init__(self, entities):
            self._entities = entities

        async def get_entity_by_qid(self, qid):
            return self._entities.get(qid)

        async def get_entities_by_qids(self, qids):
            return {q: self._entities.get(q) for q in qids if q in self._entities}

    class FakeN4j:
        def __init__(self):
            self.relations = []
            self.entities = []

        async def upsert_entity(self, d):
            self.entities.append(d)
            return True

        async def upsert_relation(self, **kw):
            self.relations.append(kw)
            return True

        async def delete_outgoing_relations(self, entity_id):
            return True

        async def delete_subgraph_edges(self, entity_ids):
            return True

        async def mark_graph_built(self, entity_id, depth=1):
            return True

    @pytest.mark.asyncio
    async def test_edge_type_mapped_and_stored_upper_snake(self):
        """P800 创作 → edge.type='creation'，Neo4j 存 'CREATION'"""
        center = self.make_entity("Q1", "苹果公司", {"P800": [item_claim("Q100")]})
        product = self.make_entity("Q100", "iPhone", {})
        wd = self.FakeWD({"Q1": center, "Q100": product})
        n4j = self.FakeN4j()

        result = await build_graph_from_wikidata("Q1", wd, n4j, depth=1)

        edge = result["edges"][0]
        assert edge["type"] == "creation"
        # 写库类型为大写语义类型
        stored = n4j.relations[0]
        assert stored["rel_type"] == "CREATION"

    @pytest.mark.asyncio
    async def test_no_related_to_edges(self):
        """图谱边不再出现笼统的 related_to"""
        center = self.make_entity("Q1", "苹果公司", {
            "P800": [item_claim("Q100")],
            "P31": [item_claim("Q500")],
        })
        wd = self.FakeWD({"Q1": center, "Q100": self.make_entity("Q100", "iPhone", {})})
        n4j = self.FakeN4j()

        result = await build_graph_from_wikidata("Q1", wd, n4j, depth=1)
        assert all(e["type"] != "related_to" for e in result["edges"])


class TestNeo4jEdgeNormalization:
    @pytest.mark.asyncio
    async def test_get_graph_normalizes_upper_snake_to_semantic(self):
        center = FakeNode({
            "entityId": "Q1", "entityName": "中心", "entityType": "organization",
            "confidence": 0.9, "summary": "", "relevance": 1.0,
        })
        related = FakeNode({
            "entityId": "Q2", "entityName": "关联", "entityType": "entity",
            "confidence": 0.8, "summary": "", "relevance": 0.7,
        })
        rel = FakeRel("CREATION", {"confidence": 0.8, "relevance": 0.7}, center, related)

        def handler(query, params):
            # V3a: get_graph 拆为节点/边两条查询，按查询内容分发
            if "RETURN n" in query:
                return FakeResult(records=[{"n": center}, {"n": related}])
            return FakeResult(records=[{"rel": rel, "a": center, "b": related}])

        driver = FakeDriver(run_handler=handler)
        repo = Neo4jRepository(client=FakeClient(driver))
        result = await repo.get_graph("Q1", depth=1)

        assert result["edges"][0]["type"] == "creation"

    @pytest.mark.asyncio
    async def test_get_graph_related_to_normalized_to_other(self):
        """旧数据 RELATED_TO → 读回为 other（前端 6 色板）"""
        center = FakeNode({
            "entityId": "Q1", "entityName": "中心", "entityType": "entity",
            "confidence": 0.9, "summary": "", "relevance": 1.0,
        })
        related = FakeNode({
            "entityId": "Q2", "entityName": "关联", "entityType": "entity",
            "confidence": 0.8, "summary": "", "relevance": 0.5,
        })
        rel = FakeRel("RELATED_TO", {"confidence": 0.7, "relevance": 0.5}, center, related)

        def handler(query, params):
            if "RETURN n" in query:
                return FakeResult(records=[{"n": center}, {"n": related}])
            return FakeResult(records=[{"rel": rel, "a": center, "b": related}])

        driver = FakeDriver(run_handler=handler)
        repo = Neo4jRepository(client=FakeClient(driver))
        result = await repo.get_graph("Q1", depth=1)

        assert result["edges"][0]["type"] == "other"

    @pytest.mark.asyncio
    async def test_get_graph_unknown_type_normalized_to_other(self):
        center = FakeNode({"entityId": "Q1", "entityName": "c", "entityType": "entity",
                           "confidence": 0.9, "summary": "", "relevance": 1.0})
        rel = FakeRel("MYSTERY_REL", {"confidence": 0.7, "relevance": 0.5},
                      center,
                      FakeNode({"entityId": "Q2", "entityName": "r", "entityType": "entity",
                                "confidence": 0.8, "summary": "", "relevance": 0.5}))

        def handler(query, params):
            if "RETURN n" in query:
                return FakeResult(records=[{"n": center}, {"n": rel.end_node}])
            return FakeResult(records=[{"rel": rel, "a": rel.start_node, "b": rel.end_node}])

        driver = FakeDriver(run_handler=handler)
        repo = Neo4jRepository(client=FakeClient(driver))
        result = await repo.get_graph("Q1", depth=1)

        assert result["edges"][0]["type"] == "other"

    @pytest.mark.asyncio
    async def test_upsert_relation_normalizes_lowercase_input(self):
        """小写输入 'creation' → 存储为 UPPER_SNAKE 'CREATION'"""
        driver = FakeDriver()
        repo = Neo4jRepository(client=FakeClient(driver))
        ok = await repo.upsert_relation("Q1", "Q2", "creation", confidence=0.8)
        assert ok is True
        _, params = driver.calls[-1]
        query = driver.calls[-1][0]
        assert "r:CREATION" in query

    @pytest.mark.asyncio
    async def test_upsert_relation_rejects_invalid_type(self):
        driver = FakeDriver()
        repo = Neo4jRepository(client=FakeClient(driver))
        ok = await repo.upsert_relation("Q1", "Q2", "INVALID TYPE!", confidence=0.8)
        assert ok is False
        assert driver.calls == []  # 未发查询

"""P4: Wikidata 去噪 + 类型优先级排序

- 强关联属性白名单收敛（无 P31/P279 混入）
- P31/P279 分类节点保留但标 type:"category" + relevance:0.2（方案 B，不剔除）
- 按类型优先级 person > event > technology > organization > concept > entity > category
  排序后截断 _RELATED_LIMIT
- 强关联节点 relevance:0.7，中心节点 relevance:1.0
"""

import pytest

from app.api.graph import (
    build_graph_from_wikidata,
    _RELATION_PROPS,
    _CATEGORY_PROPS,
    _STRONG_RELATION_PROPS,
    _RELATED_LIMIT,
    _NODE_TYPE_PRIORITY,
)
from app.repositories.wikidata_repo import WikidataEntity


def make_entity(qid: str, label: str, claims: dict) -> WikidataEntity:
    return WikidataEntity(
        id=qid, label=label, label_en=label, description="",
        type="entity", aliases=[], sitelink_zh="", sitelink_en="", claims=claims,
    )


def item_claim(qid: str) -> dict:
    return {
        "mainsnak": {
            "datatype": "wikibase-item",
            "datavalue": {"value": {"id": qid}},
        }
    }


class FakeWikidata:
    def __init__(self, entities: dict[str, WikidataEntity]):
        self._entities = entities

    async def get_entity_by_qid(self, qid):
        return self._entities.get(qid)


class FakeNeo4j:
    def __init__(self):
        self.entities: list[dict] = []
        self.relations: list[dict] = []

    async def upsert_entity(self, entity_data: dict):
        self.entities.append(entity_data)
        return True

    async def upsert_relation(self, **kwargs):
        self.relations.append(kwargs)
        return True


def build_apple_graph():
    """中心 Q312 苹果公司：
    - P31 公司分类 → category
    - P279 智能手机子类 → category
    - P800 产品 iPhone → 强关联
    - P355 子公司 Beats → 强关联
    - P106 无（公司无职业）
    """
    center_claims = {
        "P31": [item_claim("Q4830453")],
        "P279": [item_claim("Q1972862")],
        "P800": [item_claim("Q1416")],  # iPhone
        "P355": [item_claim("Q813689")],  # Beats
    }
    entities = {
        "Q312": make_entity("Q312", "苹果公司", center_claims),
        "Q4830453": make_entity("Q4830453", "公司", {}),
        "Q1972862": make_entity("Q1972862", "智能手机", {}),
        "Q1416": make_entity("Q1416", "iPhone", {}),
        "Q813689": make_entity("Q813689", "Beats Electronics", {}),
    }
    return entities


class TestRelationPropsWhitelist:
    def test_strong_whitelist_excludes_p31_p279(self):
        assert "P31" not in _STRONG_RELATION_PROPS
        assert "P279" not in _STRONG_RELATION_PROPS
        # P4 收敛白名单 + 人物核心关系扩展（合作者/教育/雇主/政党）
        assert _STRONG_RELATION_PROPS == [
            "P800", "P1416", "P106", "P463", "P910", "P127", "P355", "P1830",
            "P1327", "P69", "P108", "P102",
        ]

    def test_category_props_present(self):
        assert set(_CATEGORY_PROPS) == {"P31", "P279"}


class TestBuildGraphDenoise:
    @pytest.mark.asyncio
    async def test_category_nodes_marked_and_low_relevance(self):
        wikidata = FakeWikidata(build_apple_graph())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q312", wikidata, neo4j, depth=1)

        nodes = {n["id"]: n for n in result["nodes"]}
        assert nodes["Q4830453"]["type"] == "category"  # 公司分类
        assert nodes["Q4830453"]["relevance"] == 0.2
        assert nodes["Q1972862"]["type"] == "category"  # 智能手机分类
        assert nodes["Q1972862"]["relevance"] == 0.2

    @pytest.mark.asyncio
    async def test_strong_related_nodes_relevance(self):
        wikidata = FakeWikidata(build_apple_graph())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q312", wikidata, neo4j, depth=1)

        nodes = {n["id"]: n for n in result["nodes"]}
        assert nodes["Q1416"]["type"] == "entity"  # iPhone 无类别 → 未降级
        assert nodes["Q1416"]["relevance"] == 0.7
        assert nodes["Q813689"]["relevance"] == 0.7

    @pytest.mark.asyncio
    async def test_center_node_relevance_one(self):
        wikidata = FakeWikidata(build_apple_graph())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q312", wikidata, neo4j, depth=1)

        center = next(n for n in result["nodes"] if n["id"] == "Q312")
        assert center["relevance"] == 1.0

    @pytest.mark.asyncio
    async def test_category_edges_preserved_but_weak(self):
        wikidata = FakeWikidata(build_apple_graph())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q312", wikidata, neo4j, depth=1)

        cat_edges = [e for e in result["edges"] if e["target"] == "Q4830453"]
        assert len(cat_edges) == 1
        assert cat_edges[0]["relevance"] == 0.2  # 分类边弱相关但保留

    @pytest.mark.asyncio
    async def test_nodes_upserted_to_neo4j_with_relevance(self):
        wikidata = FakeWikidata(build_apple_graph())
        neo4j = FakeNeo4j()
        await build_graph_from_wikidata("Q312", wikidata, neo4j, depth=1)

        assert len(neo4j.entities) == 5
        by_id = {e["id"]: e for e in neo4j.entities}
        assert by_id["Q4830453"]["type"] == "category"
        assert by_id["Q4830453"]["relevance"] == 0.2
        assert by_id["Q1416"]["relevance"] == 0.7


class TestTypePriorityOrdering:
    @pytest.mark.asyncio
    async def test_type_priority_rankings(self):
        assert _NODE_TYPE_PRIORITY["person"] < _NODE_TYPE_PRIORITY["event"]
        assert _NODE_TYPE_PRIORITY["event"] < _NODE_TYPE_PRIORITY["technology"]
        assert _NODE_TYPE_PRIORITY["technology"] < _NODE_TYPE_PRIORITY["organization"]
        assert _NODE_TYPE_PRIORITY["organization"] < _NODE_TYPE_PRIORITY["entity"]
        assert _NODE_TYPE_PRIORITY["entity"] < _NODE_TYPE_PRIORITY["category"]

    @pytest.mark.asyncio
    async def test_person_outranks_category_when_truncated(self):
        """类型优先级排序后截断：person 进入结果，更低优先级的 category 被挤出"""
        # 中心有 1 个 person（P800 乔布斯）+ 1 个 category（P31 公司），limit=1
        center_claims = {
            "P800": [item_claim("Q19837")],  # 史蒂夫·乔布斯
            "P31": [item_claim("Q4830453")],  # 公司分类
        }
        entities = {
            "Q1": make_entity("Q1", "中心", center_claims),
            "Q19837": make_entity("Q19837", "史蒂夫·乔布斯", {"P31": [item_claim("Q5")]}),
            "Q4830453": make_entity("Q4830453", "公司", {}),
        }
        # 真实 wikidata_repo 会通过 P31=Q5 推断出 person；fake 需等价反映
        entities["Q19837"].type = "person"
        import app.api.graph as graph_mod
        orig = graph_mod._RELATED_LIMIT
        graph_mod._RELATED_LIMIT = 1
        try:
            wikidata = FakeWikidata(entities)
            neo4j = FakeNeo4j()
            result = await build_graph_from_wikidata("Q1", wikidata, neo4j, depth=1)
        finally:
            graph_mod._RELATED_LIMIT = orig

        related = [n for n in result["nodes"] if n["id"] != "Q1"]
        assert related, "应有至少一个关联节点"
        # 截断后保留的是最高优先级的节点（person），category 被挤出
        assert related[0]["id"] == "Q19837"
        assert related[0]["type"] == "person"
        assert all(n["id"] != "Q4830453" for n in result["nodes"])

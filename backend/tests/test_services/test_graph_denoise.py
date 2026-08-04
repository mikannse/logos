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
    _edge_evidence,
    _edge_confidence,
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

    async def delete_outgoing_relations(self, entity_id):
        return True

    async def mark_graph_built(self, entity_id):
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
        # P4 收敛白名单 + 人物核心关系扩展（合作者/教育/雇主/政党）；
        # 修复 4b：P106（职业）已移除——"革命家/政治人物"等职业概念值
        # 作为图谱边信息量≈0，且目标易被误判为 person/event 实例
        assert "P106" not in _STRONG_RELATION_PROPS
        assert _STRONG_RELATION_PROPS == [
            "P800", "P1416", "P463", "P910", "P127", "P355", "P1830",
            "P1327", "P69", "P108", "P102",
        ]

    def test_relation_props_excludes_p106(self):
        """修复 4b：P106 职业不在提取属性列表中（职业概念不进图谱）"""
        assert "P106" not in _RELATION_PROPS

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


class TestEdgeEvidenceAndRebuild:
    """修复 1：边 evidence/confidence 关系级真实值；修复 3：重建清理旧边 + 标记构建时间"""

    @pytest.mark.asyncio
    async def test_edge_evidence_is_relation_level_not_center_description(self):
        """边 evidence 应为关系语义描述（"著名作品：iPhone"），而非中心实体描述占位符"""
        wikidata = FakeWikidata(build_apple_graph())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q312", wikidata, neo4j, depth=1)

        edge = next(e for e in result["edges"] if e["target"] == "Q1416")
        assert edge["evidence"] == "著名作品：iPhone"
        assert edge["evidence"] != "苹果公司"  # 不再是中心描述

    @pytest.mark.asyncio
    async def test_edge_confidence_graded_by_sitelink_and_category(self):
        """边 confidence 分级：无站点链接 0.6，分类属性 0.5（替代旧硬编码 0.7）"""
        # 构造：强关联 target 有 sitelink（0.85）、无 sitelink（0.6）、分类（0.5）
        center_claims = {
            "P800": [item_claim("Q100")],     # 强关联，无 sitelink → 0.6
            "P355": [item_claim("Q200")],     # 强关联，有 sitelink → 0.85
            "P31": [item_claim("Q300")],      # 分类 → 0.5
        }
        entities = {
            "Q1": make_entity("Q1", "中心", center_claims),
            "Q100": make_entity("Q100", "作品A", {}),
            "Q200": make_entity("Q200", "子公司B", {}),
            "Q300": make_entity("Q300", "类别C", {}),
        }
        entities["Q200"].sitelink_en = "https://en.wikipedia.org/wiki/B"
        wikidata = FakeWikidata(entities)
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q1", wikidata, neo4j, depth=1)

        conf = {e["target"]: e["confidence"] for e in result["edges"]}
        assert conf["Q100"] == 0.6
        assert conf["Q200"] == 0.85
        assert conf["Q300"] == 0.5
        # 写库的 confidence 与响应一致
        stored = {r["target_id"]: r["confidence"] for r in neo4j.relations}
        assert stored["Q100"] == 0.6 and stored["Q200"] == 0.85 and stored["Q300"] == 0.5

    @pytest.mark.asyncio
    async def test_rebuild_clears_stale_edges_and_marks_built(self):
        """修复 3：重建前清理旧出边；构建完成后标记 graphBuiltAt"""
        class TrackingNeo4j(FakeNeo4j):
            def __init__(self):
                super().__init__()
                self.deleted = []
                self.marked = []

            async def delete_outgoing_relations(self, entity_id):
                self.deleted.append(entity_id)
                return True

            async def mark_graph_built(self, entity_id):
                self.marked.append(entity_id)
                return True

        wikidata = FakeWikidata(build_apple_graph())
        neo4j = TrackingNeo4j()
        result = await build_graph_from_wikidata("Q312", wikidata, neo4j, depth=1)

        # 中心构建前清旧边，构建完成后标记时间
        assert neo4j.deleted == ["Q312"]
        assert neo4j.marked == ["Q312"]
        assert result["edges"], "重建后应有边"

    def test_edge_evidence_helper_produces_prop_label(self):
        """_edge_evidence 使用属性中文标签（未知属性回退"关联"）"""
        target = make_entity("Q1", "恩格斯", {})
        assert _edge_evidence("P1327", target) == "合作者：恩格斯"
        assert _edge_evidence("P999", target) == "关联：恩格斯"

    def test_edge_confidence_helper_grades(self):
        """_edge_confidence 三档：分类 0.5 / 有 sitelink 0.85 / 无 0.6"""
        target = make_entity("Q1", "X", {})
        assert _edge_confidence("P31", target) == 0.5
        assert _edge_confidence("P800", target) == 0.6
        target.sitelink_en = "https://en.wikipedia.org/wiki/X"
        assert _edge_confidence("P800", target) == 0.85

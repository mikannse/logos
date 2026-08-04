"""V3a/V2c: 多跳图谱构建 + 节点年段提取

V3a 多跳构建：
- depth 1→3 递归展开，hop≥2 仅展开强关系属性（决策②，防分类/地理/家庭噪音）
- 已访问集合防环（hop-2 指向已访问 hop-1/中心节点被跳过）
- 每跳 ≤ _RELATED_LIMIT 截断；relevance 随跳衰减（hop-1 保留 prop 制，hop≥2 乘衰减）
- has_more：本跳候选被截断时置位
- 写库：hop 标注、mark_graph_built 带 depth

V2c 年段提取：
- _extract_node_year 从 claims 提取 (year, year_end)：P569/571/577/585 锚点年，
  P570/576/8556 结束年
- 节点/边 year/year_end/hop 字段透传至结果与写库
"""

import pytest

from app.api.graph import (
    build_graph_from_wikidata,
    _extract_node_year,
    _RELATED_LIMIT,
    _STRONG_RELATION_PROPS,
    _HOP_STRONG_RELATION_PROPS,
    _HOP_RELEVANCE_DECAY,
)
from app.repositories.wikidata_repo import WikidataEntity


def make_entity(qid: str, label: str, claims: dict, type_: str = "entity") -> WikidataEntity:
    return WikidataEntity(
        id=qid, label=label, label_en=label, description="",
        type=type_, aliases=[], sitelink_zh="", sitelink_en="", claims=claims,
    )


def item_claim(qid: str) -> dict:
    return {
        "mainsnak": {
            "datatype": "wikibase-item",
            "datavalue": {"value": {"id": qid}},
        }
    }


def time_claim(time: str) -> dict:
    return {
        "mainsnak": {
            "datatype": "time",
            "datavalue": {"value": {"time": time}},
        }
    }


class FakeWikidata:
    def __init__(self, entities: dict[str, WikidataEntity]):
        self._entities = entities
        self.batch_calls = 0
        self.single_calls = 0

    async def get_entity_by_qid(self, qid):
        self.single_calls += 1
        return self._entities.get(qid)

    async def get_entities_by_qids(self, qids):
        self.batch_calls += 1
        return {q: self._entities.get(q) for q in qids if q in self._entities}


class FakeNeo4j:
    def __init__(self):
        self.entities: list[dict] = []
        self.relations: list[dict] = []
        self.deleted_outgoing: list[str] = []
        self.built: list[tuple] = []

    async def upsert_entity(self, entity_data):
        self.entities.append(entity_data)
        return True

    async def upsert_relation(self, **kwargs):
        self.relations.append(kwargs)
        return True

    async def delete_outgoing_relations(self, entity_id):
        self.deleted_outgoing.append(entity_id)
        return True

    async def delete_subgraph_edges(self, entity_ids):
        return True

    async def mark_graph_built(self, entity_id, depth=1):
        self.built.append((entity_id, depth))
        return True


# ---- 多跳构建测试数据：马克思（Q937）→ 恩格斯（Q34787）→ 恩格斯著作/关系 ----

def build_marx_two_hop():
    """Q937 马克思 → P1327 恩格斯（Q34787）→ P800 作品（Q278760）
    验证 hop-2 展开：恩格斯 claims 的 P800 作品被拉入图谱
    """
    entities = {
        "Q937": make_entity("Q937", "卡尔·马克思", {
            "P1327": [item_claim("Q34787")],  # 合作者 恩格斯
        }, type_="person"),
        "Q34787": make_entity("Q34787", "弗里德里希·恩格斯", {
            "P800": [item_claim("Q278760")],  # 作品 共产党宣言
            "P1327": [item_claim("Q937")],    # 环：回指马克思 → 防环测试
        }, type_="person"),
        "Q278760": make_entity("Q278760", "共产党宣言", {}, type_="concept"),
    }
    return entities


def build_noisy_two_hop():
    """中心有强关联（P800）与分类（P31）；hop-2 候选含分类（P31）与地理（P19）
    验证 hop≥2 白名单收敛：分类/地理被丢弃
    """
    entities = {
        "Q1": make_entity("Q1", "中心", {
            "P800": [item_claim("Q2")],
            "P31": [item_claim("QCAT1")],
        }, type_="entity"),
        "Q2": make_entity("Q2", "作品", {
            "P31": [item_claim("QCAT2")],    # hop-2 分类 → 应被丢弃
            "P19": [item_claim("QPLACE")],   # hop-2 出生地 → 应被丢弃
            "P800": [item_claim("Q3")],      # hop-2 强关联 → 应保留
        }, type_="concept"),
        "QCAT2": make_entity("QCAT2", "分类2", {}, type_="category"),
        "QPLACE": make_entity("QPLACE", "地点", {}, type_="entity"),
        "Q3": make_entity("Q3", "延伸作品", {}, type_="concept"),
        "QCAT1": make_entity("QCAT1", "分类1", {}, type_="category"),
    }
    return entities


class TestMultiHopBuild:
    @pytest.mark.asyncio
    async def test_hop2_expands_strong_relations(self):
        wikidata = FakeWikidata(build_marx_two_hop())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q937", wikidata, neo4j, depth=2)

        ids = {n["id"] for n in result["nodes"]}
        assert "Q34787" in ids  # hop-1 恩格斯
        assert "Q278760" in ids  # hop-2 共产党宣言（通过 P800 展开）
        # hop 标注正确
        hop_map = {n["id"]: n.get("hop") for n in result["nodes"]}
        assert hop_map["Q937"] == 0
        assert hop_map["Q34787"] == 1
        assert hop_map["Q278760"] == 2

    @pytest.mark.asyncio
    async def test_cycle_prevented_visited_skipped(self):
        """防环：恩格斯 P1327 回指马克思 → 马克思不重复加入"""
        wikidata = FakeWikidata(build_marx_two_hop())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q937", wikidata, neo4j, depth=2)

        ids = [n["id"] for n in result["nodes"]]
        assert ids.count("Q937") == 1
        assert ids.count("Q34787") == 1

    @pytest.mark.asyncio
    async def test_hop2_whitelist_converges_to_strong(self):
        """决策②：hop≥2 仅展开强关系属性，分类/地理被丢弃"""
        wikidata = FakeWikidata(build_noisy_two_hop())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q1", wikidata, neo4j, depth=2)

        ids = {n["id"] for n in result["nodes"]}
        assert "Q2" in ids       # hop-1 作品
        assert "Q3" in ids       # hop-2 强关联保留
        assert "QCAT2" not in ids  # hop-2 分类被丢弃
        assert "QPLACE" not in ids  # hop-2 地理被丢弃

    @pytest.mark.asyncio
    async def test_hop2_relevance_decay(self):
        wikidata = FakeWikidata(build_marx_two_hop())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q937", wikidata, neo4j, depth=2)

        hop_map = {n["id"]: n for n in result["nodes"]}
        # hop-1 恩格斯：P1327 合作者 → 强关联 0.7
        assert hop_map["Q34787"]["relevance"] == 0.7
        # hop-2 共产党宣言：P800 创作 0.7 × 0.5 衰减 = 0.35
        assert hop_map["Q278760"]["relevance"] == pytest.approx(0.7 * _HOP_RELEVANCE_DECAY[2], abs=0.001)

    @pytest.mark.asyncio
    async def test_hop1_relevance_keeps_prop_based(self):
        """hop-1 保留 prop 制：分类 0.2 不变，不因多跳逻辑升到 0.7"""
        wikidata = FakeWikidata(build_noisy_two_hop())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q1", wikidata, neo4j, depth=1)

        cat = next(n for n in result["nodes"] if n["id"] == "QCAT1")
        assert cat["relevance"] == 0.2

    @pytest.mark.asyncio
    async def test_mark_graph_built_with_depth(self):
        wikidata = FakeWikidata(build_marx_two_hop())
        neo4j = FakeNeo4j()
        await build_graph_from_wikidata("Q937", wikidata, neo4j, depth=2)

        assert neo4j.built == [("Q937", 2)]

    @pytest.mark.asyncio
    async def test_upserted_entities_have_hop(self):
        wikidata = FakeWikidata(build_marx_two_hop())
        neo4j = FakeNeo4j()
        await build_graph_from_wikidata("Q937", wikidata, neo4j, depth=2)

        stored = {e["id"]: e.get("hop") for e in neo4j.entities}
        assert stored["Q937"] == 0
        assert stored["Q34787"] == 1
        assert stored["Q278760"] == 2

    @pytest.mark.asyncio
    async def test_upserted_relations_have_hop(self):
        wikidata = FakeWikidata(build_marx_two_hop())
        neo4j = FakeNeo4j()
        await build_graph_from_wikidata("Q937", wikidata, neo4j, depth=2)

        hop_map = {(r["source_id"], r["target_id"]): r.get("hop") for r in neo4j.relations}
        assert hop_map[("Q937", "Q34787")] == 1
        assert hop_map[("Q34787", "Q278760")] == 2

    @pytest.mark.asyncio
    async def test_stale_out_edges_cleaned_on_rebuild(self):
        """B1: 重建时每个非中心源节点写边前清理陈旧出边——
        hop1→hop2 内部边（恩格斯出边）被清，避免前次更深度构建残留累积"""
        wikidata = FakeWikidata(build_marx_two_hop())
        neo4j = FakeNeo4j()
        await build_graph_from_wikidata("Q937", wikidata, neo4j, depth=2)

        # 中心出边 + hop-1 源节点（恩格斯）出边都应被清理
        assert neo4j.deleted_outgoing, "应调用 delete_outgoing_relations 清理陈旧边"
        assert "Q937" in neo4j.deleted_outgoing
        assert "Q34787" in neo4j.deleted_outgoing  # 恩格斯出边（hop1→hop2）被清

    @pytest.mark.asyncio
    async def test_batch_fetch_used(self):
        """hop≥2 走批量拉取 get_entities_by_qids，避免逐 QID 串行放大"""
        wikidata = FakeWikidata(build_marx_two_hop())
        neo4j = FakeNeo4j()
        await build_graph_from_wikidata("Q937", wikidata, neo4j, depth=2)

        assert wikidata.batch_calls >= 1


class TestHopWhitelistConstant:
    def test_hop_strong_props_is_subset_of_relation_props(self):
        """hop≥2 白名单 ⊂ 全量关系属性（决策② 收敛）"""
        from app.api.graph import _RELATION_PROPS
        assert set(_HOP_STRONG_RELATION_PROPS).issubset(set(_RELATION_PROPS))

    def test_hop_strong_excludes_categories_and_geography(self):
        """hop≥2 不展开分类（P31/P279）与地理/家庭（P19/P20/P26/P937/P101）"""
        assert "P31" not in _HOP_STRONG_RELATION_PROPS
        assert "P279" not in _HOP_STRONG_RELATION_PROPS
        assert "P19" not in _HOP_STRONG_RELATION_PROPS
        assert "P20" not in _HOP_STRONG_RELATION_PROPS
        assert "P26" not in _HOP_STRONG_RELATION_PROPS
        assert "P937" not in _HOP_STRONG_RELATION_PROPS

    def test_hop_strong_equals_strong_relation_props(self):
        assert _HOP_STRONG_RELATION_PROPS == list(_STRONG_RELATION_PROPS)


class TestExtractNodeYear:
    def test_person_lifespan(self):
        """人物：P569 出生 → year，P570 逝世 → year_end"""
        claims = {
            "P569": [time_claim("+1818-05-05T00:00:00Z")],
            "P570": [time_claim("+1883-03-14T00:00:00Z")],
        }
        year, year_end = _extract_node_year(claims)
        assert year == 1818
        assert year_end == 1883

    def test_organization_founded(self):
        claims = {"P571": [time_claim("+1976-04-01T00:00:00Z")]}
        year, year_end = _extract_node_year(claims)
        assert year == 1976
        assert year_end is None

    def test_work_published(self):
        claims = {"P577": [time_claim("+1848-02-21T00:00:00Z")]}
        year, year_end = _extract_node_year(claims)
        assert year == 1848

    def test_no_time_claims(self):
        year, year_end = _extract_node_year({})
        assert year is None
        assert year_end is None

    def test_none_claims(self):
        year, year_end = _extract_node_year(None)
        assert year is None
        assert year_end is None

    def test_bce_year(self):
        """公元前：-0445 → -445"""
        claims = {"P569": [time_claim("-0445-03-14T00:00:00Z")]}
        year, _ = _extract_node_year(claims)
        assert year == -445


class TestNodeYearPopulatedInBuild:
    @pytest.mark.asyncio
    async def test_center_and_related_nodes_have_year(self):
        """V2c：构建时节点年段透传（马克思 1818-1883，恩格斯 1820-1895）"""
        entities = {
            "Q937": make_entity("Q937", "卡尔·马克思", {
                "P569": [time_claim("+1818-05-05T00:00:00Z")],
                "P570": [time_claim("+1883-03-14T00:00:00Z")],
                "P1327": [item_claim("Q34787")],
            }, type_="person"),
            "Q34787": make_entity("Q34787", "弗里德里希·恩格斯", {
                "P569": [time_claim("+1820-11-28T00:00:00Z")],
                "P570": [time_claim("+1895-08-05T00:00:00Z")],
            }, type_="person"),
        }
        wikidata = FakeWikidata(entities)
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q937", wikidata, neo4j, depth=1)

        node_map = {n["id"]: n for n in result["nodes"]}
        assert node_map["Q937"]["year"] == 1818
        assert node_map["Q937"]["year_end"] == 1883
        assert node_map["Q34787"]["year"] == 1820
        assert node_map["Q34787"]["year_end"] == 1895

        # 写库也带年段
        stored = {e["id"]: e for e in neo4j.entities}
        assert stored["Q937"]["year"] == 1818
        assert stored["Q937"]["year_end"] == 1883

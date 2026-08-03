"""P5: 正常搜索触发 Web 丰富（同步合并）

- 语义多样性不足时触发 Web Search + LLM 丰富：
  - 关联节点过少（<6）
  - 关联节点类型单一（<3 种）
  - 语义边类型 <=1 种
- 多样性充足（节点多、类型多、边类型多）时不触发（省成本，NFR-6）
- 丰富结果缓存 1h（web_enrich:{qid}）
- 丰富失败/LLM 未配置 → 静默退化为基础图谱，不抛异常
"""

import pytest

from app.api.graph import (
    build_graph_from_wikidata,
    _ENRICH_TRIGGER_THRESHOLD,
    _should_enrich,
)
from app.ai.extractor import (
    EntityExtractionResult,
    ExtractedEntity,
    ExtractedRelation,
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


class FakeWikidata:
    def __init__(self, entities: dict[str, WikidataEntity]):
        self._entities = entities
        self.calls = []

    async def get_entity_by_qid(self, qid):
        return self._entities.get(qid)

    async def search_raw(self, query, language="zh", limit=5):
        self.calls.append(query)
        return []


class FakeNeo4j:
    def __init__(self):
        self.entities = []
        self.relations = []

    async def upsert_entity(self, entity_data):
        self.entities.append(entity_data)
        return True

    async def upsert_relation(self, **kwargs):
        self.relations.append(kwargs)
        return True


class FakeCache:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ttl=0):
        self.data[key] = value


class FakeWebSearch:
    def __init__(self, summary: str = ""):
        self.summary = summary
        self.calls = []

    async def search_and_extract(self, query, entity_type=None):
        self.calls.append(query)
        if not self.summary:
            return None
        return {"query": query, "summary": self.summary, "entities": [], "relations": []}


class FakeExtractor:
    def __init__(self, result=None):
        self.result = result
        self.calls = []

    async def extract_from_text(self, text, focus_entity=None):
        self.calls.append(focus_entity)
        return self.result


def make_extraction():
    return EntityExtractionResult(
        entities=[
            ExtractedEntity(name="史蒂夫·乔布斯", type="person", description="苹果联合创始人", relevance=0.9),
            ExtractedEntity(name="蒂姆·库克", type="person", description="CEO", relevance=0.6),
        ],
        relations=[
            ExtractedRelation(source="苹果公司", target="史蒂夫·乔布斯", relation_type="affiliation",
                              description="创始人", confidence=0.8),
        ],
    )


def sparse_center() -> dict:
    """只有 2 个强相关节点（<6）→ 触发丰富"""
    entities = {
        "Q312": make_entity("Q312", "苹果公司", {
            "P800": [item_claim("Q1416")],
            "P800_dup_placeholder": [],
        }),
        "Q1416": make_entity("Q1416", "iPhone", {}),
    }
    return entities


def rich_center() -> dict:
    """多样性充足的图谱（节点 6+、类型 ≥3 种、边类型 ≥2 种）→ 不触发丰富"""
    # 中心实体：organization，关联 6 个不同类型节点，混合边类型
    center_claims = {
        "P800": [item_claim("Q1001"), item_claim("Q1002")],  # creation 产品
        "P106": [item_claim("Q1003")],                        # affiliation 职业
        "P1416": [item_claim("Q1004")],                       # affiliation 关联机构
        "P1327": [item_claim("Q1005")],                       # collaboration 合作者
        "P737": [item_claim("Q1006")],                        # influence 影响
    }
    entities = {
        "Q312": make_entity("Q312", "苹果公司", center_claims, type_="organization"),
        "Q1001": make_entity("Q1001", "产品1", {}, type_="technology"),
        "Q1002": make_entity("Q1002", "产品2", {}, type_="technology"),
        "Q1003": make_entity("Q1003", "员工", {}, type_="person"),
        "Q1004": make_entity("Q1004", "机构", {}, type_="organization"),
        "Q1005": make_entity("Q1005", "合作者", {}, type_="person"),
        "Q1006": make_entity("Q1006", "创始人", {}, type_="person"),
    }
    return entities


class TestEnrichTrigger:
    def test_threshold_constant(self):
        assert _ENRICH_TRIGGER_THRESHOLD == 6

    def test_should_enrich_too_few_related(self):
        """关联节点过少（<6）→ 触发"""
        nodes = [
            {"id": "Q1", "type": "person"},
            {"id": "Q2", "type": "entity"},
        ]
        assert _should_enrich(nodes, [{"type": "other"}], "Q0") is True

    def test_should_enrich_monotone_types(self):
        """关联节点类型单一（<3 种）→ 触发（旧"全 entity"图谱）"""
        nodes = [{"id": f"Q{i}", "type": "entity"} for i in range(1, 8)]
        edges = [{"type": "affiliation"}] * 6
        assert _should_enrich(nodes, edges, "Q0") is True

    def test_should_enrich_monotone_edges(self):
        """语义边类型 <=1 种 → 触发"""
        nodes = [
            {"id": f"Q{i}", "type": "person" if i % 2 else "concept"}
            for i in range(1, 9)
        ]
        edges = [{"type": "affiliation"}] * 7
        assert _should_enrich(nodes, edges, "Q0") is True

    def test_should_enrich_diverse_graph_skips(self):
        """多样性充足（节点 6+、类型 3+、边类型 2+）→ 不触发"""
        nodes = [
            {"id": f"Q{i}", "type": ["technology", "person", "organization"][i % 3]}
            for i in range(1, 8)
        ]
        edges = [{"type": "creation"}, {"type": "affiliation"}] * 4
        assert _should_enrich(nodes, edges, "Q0") is False

    def test_should_enrich_center_and_category_excluded(self):
        """中心节点与 category 节点不计入多样性判定"""
        nodes = [
            {"id": "Q0", "type": "person"},  # 中心
            {"id": "Q1", "type": "category"},  # 分类
            {"id": "Q2", "type": "entity"},
            {"id": "Q3", "type": "entity"},
            {"id": "Q4", "type": "entity"},
            {"id": "Q5", "type": "entity"},
            {"id": "Q6", "type": "entity"},
        ]
        edges = [{"type": "affiliation"}] * 6
        # 排除中心与 category 后仅 5 个 entity → 类型单一 → 触发
        assert _should_enrich(nodes, edges, "Q0") is True

    @pytest.mark.asyncio
    async def test_sparse_graph_triggers_enrichment(self):
        wikidata = FakeWikidata(sparse_center())
        neo4j = FakeNeo4j()
        web_search = FakeWebSearch("苹果公司是一家科技公司，由史蒂夫·乔布斯创立。")
        extractor = FakeExtractor(make_extraction())
        cache = FakeCache()

        result = await build_graph_from_wikidata(
            "Q312", wikidata, neo4j, depth=1,
            web_search=web_search, extractor=extractor, cache=cache,
        )

        assert web_search.calls == ["苹果公司"]  # 以中心名搜索
        assert extractor.calls == ["苹果公司"]  # 焦点锚定中心
        names = {n["name"] for n in result["nodes"]}
        assert "史蒂夫·乔布斯" in names
        assert "蒂姆·库克" in names

    @pytest.mark.asyncio
    async def test_rich_graph_skips_enrichment(self):
        wikidata = FakeWikidata(rich_center())
        neo4j = FakeNeo4j()
        web_search = FakeWebSearch("...")
        extractor = FakeExtractor(make_extraction())

        result = await build_graph_from_wikidata(
            "Q312", wikidata, neo4j, depth=1,
            web_search=web_search, extractor=extractor, cache=FakeCache(),
        )

        assert web_search.calls == []  # 强相关 >=6 → 不触发
        assert extractor.calls == []
        assert len(result["nodes"]) == 7  # 中心 + 6 强相关

    @pytest.mark.asyncio
    async def test_enrichment_result_cached_one_hour(self):
        wikidata = FakeWikidata(sparse_center())
        neo4j = FakeNeo4j()
        web_search = FakeWebSearch("文本")
        extractor = FakeExtractor(make_extraction())
        cache = FakeCache()

        await build_graph_from_wikidata(
            "Q312", wikidata, neo4j, depth=1,
            web_search=web_search, extractor=extractor, cache=cache,
        )

        assert "web_enrich:Q312" in cache.data
        cached = cache.data["web_enrich:Q312"]
        assert isinstance(cached, dict)
        assert len(cached["nodes"]) >= 2

        # 第二次调用命中缓存，不再重复调用 LLM 管道
        web_search.calls.clear()
        extractor.calls.clear()
        await build_graph_from_wikidata(
            "Q312", wikidata, neo4j, depth=1,
            web_search=web_search, extractor=extractor, cache=cache,
        )
        assert web_search.calls == []
        assert extractor.calls == []

    @pytest.mark.asyncio
    async def test_extraction_failure_degrades_gracefully(self):
        """LLM 未配置/提取失败 → 基础图谱正常返回，不抛异常"""
        wikidata = FakeWikidata(sparse_center())
        neo4j = FakeNeo4j()
        web_search = FakeWebSearch("有摘要但 LLM 提取失败")
        extractor = FakeExtractor(None)  # extract_from_text → None

        result = await build_graph_from_wikidata(
            "Q312", wikidata, neo4j, depth=1,
            web_search=web_search, extractor=extractor, cache=FakeCache(),
        )

        assert extractor.calls == ["苹果公司"]
        # 基础图谱（中心 + iPhone）仍返回
        assert len(result["nodes"]) == 2

    @pytest.mark.asyncio
    async def test_no_summary_no_enrichment(self):
        wikidata = FakeWikidata(sparse_center())
        neo4j = FakeNeo4j()
        web_search = FakeWebSearch("")  # 无摘要
        extractor = FakeExtractor(make_extraction())

        result = await build_graph_from_wikidata(
            "Q312", wikidata, neo4j, depth=1,
            web_search=web_search, extractor=extractor, cache=FakeCache(),
        )

        assert extractor.calls == []
        assert len(result["nodes"]) == 2

    @pytest.mark.asyncio
    async def test_no_dependencies_no_enrichment(self):
        """不传 web_search/extractor（旧调用方）→ 仅基础图谱，向后兼容"""
        wikidata = FakeWikidata(sparse_center())
        neo4j = FakeNeo4j()
        result = await build_graph_from_wikidata("Q312", wikidata, neo4j, depth=1)
        assert len(result["nodes"]) == 2

    @pytest.mark.asyncio
    async def test_duplicate_center_entity_not_added(self):
        """丰富提取出中心自身时，中心节点不重复"""
        wikidata = FakeWikidata(sparse_center())
        neo4j = FakeNeo4j()
        extraction = EntityExtractionResult(
            entities=[
                ExtractedEntity(name="苹果公司", type="organization", description="中心", relevance=1.0),
                ExtractedEntity(name="史蒂夫·乔布斯", type="person", description="创始人", relevance=0.9),
            ],
            relations=[],
        )
        web_search = FakeWebSearch("文本")
        extractor = FakeExtractor(extraction)

        result = await build_graph_from_wikidata(
            "Q312", wikidata, neo4j, depth=1,
            web_search=web_search, extractor=extractor, cache=FakeCache(),
        )

        ids = [n["id"] for n in result["nodes"]]
        assert ids.count("Q312") == 1

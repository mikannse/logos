"""P7: 通用实体类型推断（规则表 + P279 继承 + 描述关键词 + AI 兜底）"""

import pytest

from app.repositories.wikidata_repo import (
    WikidataRepository,
    _map_wikidata_type,
    _type_from_description,
    _ENTITY_TYPE_MAP,
)
from app.ai.extractor import EntityExtractionResult
from app.services.graph_service import merge_llm_entities, _VALID_NODE_TYPES


class TestEntityTypeMap:
    def test_direct_mapping_core_types(self):
        assert _ENTITY_TYPE_MAP["Q5"] == "person"
        assert _ENTITY_TYPE_MAP["Q4830453"] == "organization"   # 企业
        assert _ENTITY_TYPE_MAP["Q43229"] == "organization"     # 组织
        assert _ENTITY_TYPE_MAP["Q7397"] == "technology"        # 软件
        assert _ENTITY_TYPE_MAP["Q9143"] == "technology"        # 编程语言
        assert _ENTITY_TYPE_MAP["Q11424"] == "concept"          # 电影（修复）
        assert _ENTITY_TYPE_MAP["Q7725634"] == "concept"        # 文学作品

    def test_video_game_not_person(self):
        """Q7889 电子游戏误映射 person 的 bug 修复 → technology"""
        assert _ENTITY_TYPE_MAP.get("Q7889") is not None
        assert _ENTITY_TYPE_MAP["Q7889"] != "person"
        assert _ENTITY_TYPE_MAP["Q7889"] == "technology"

    def test_year_not_technology(self):
        """Q577 是"年"不是编程语言 → 不应映射为 technology"""
        assert _ENTITY_TYPE_MAP.get("Q577") != "technology"

    def test_event_mapping(self):
        assert _ENTITY_TYPE_MAP["Q198"] == "event"        # 战争
        assert _ENTITY_TYPE_MAP["Q1190554"] == "event"    # 事件
        assert _ENTITY_TYPE_MAP["Q1656682"] == "event"    # 计划活动

    def test_map_direct_layer(self):
        assert _map_wikidata_type("Q937", ["Q5"], description="物理学家") == "person"

    def test_map_p279_inheritance_layer(self):
        """P31 未命中 → P279 父类命中"""
        assert _map_wikidata_type("Qx", ["Q999_unknown_class"], subclass_of=["Q43229"]) == "organization"

    def test_map_description_keyword_layer(self):
        assert _map_wikidata_type("Qx", [], description="这是一家科技公司") == "organization"
        assert _map_wikidata_type("Qx", [], description="美国物理学家") == "person"
        assert _map_wikidata_type("Qx", [], description="") == "entity"


class TestDescriptionKeywords:
    def test_person(self):
        assert _type_from_description("著名物理学家") == "person"
        assert _type_from_description("a famous physicist") == "person"

    def test_organization(self):
        assert _type_from_description("大型科技公司") == "organization"
        assert _type_from_description("international corporation") == "organization"

    def test_technology(self):
        assert _type_from_description("开源编程语言") == "technology"
        assert _type_from_description("一款操作系统") == "technology"

    def test_event(self):
        assert _type_from_description("第二次世界大战") == "event"
        assert _type_from_description("annual conference") == "event"

    def test_concept(self):
        assert _type_from_description("一种哲学理论") == "concept"
        assert _type_from_description("a novel") == "concept"

    def test_unknown_returns_entity(self):
        assert _type_from_description("zzz qqq") == "entity"

    def test_profession_class_qid_maps_to_concept(self):
        """修复 4a：职业/专业类 P31 直映射 concept（革命家 P31=Q12737077、政治人物 P31=Q28640）"""
        assert _map_wikidata_type("Q3242115", ["Q12737077"], description="参与革命的人") == "concept"
        assert _map_wikidata_type("Q82955", ["Q28640"], description="參與政治的人物、政府官員") == "concept"
        assert _map_wikidata_type("Qx", ["Q4167410"]) == "concept"  # 消歧义页


# ---------- _get_entity_detail 集成（fake HTTP） ----------

class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def wd_entity(qid, label, claims=None, description=""):
    return {
        "labels": {"zh": {"value": label}, "en": {"value": label}},
        "descriptions": {"zh": {"value": description}, "en": {"value": description}},
        "aliases": {},
        "claims": claims or {},
        "sitelinks": {},
    }


def item_claim(qid):
    return [{"mainsnak": {"datatype": "wikibase-item", "datavalue": {"value": {"id": qid}}}}]


class FakeHttpClient:
    def __init__(self, entities: dict):
        self._entities = entities
        self.calls: list[tuple] = []

    async def get(self, url, params):
        self.calls.append((url, params))
        ids = params["ids"].split("|")
        ents = {qid: self._entities[qid] for qid in ids if qid in self._entities}
        return FakeResponse({"entities": ents})


class TestGetEntityDetailInheritance:
    def _make_repo(self, entities):
        repo = WikidataRepository.__new__(WikidataRepository)
        repo._client = FakeHttpClient(entities)
        return repo

    @pytest.mark.asyncio
    async def test_direct_p31_hit_no_extra_call(self):
        entities = {"Q937": wd_entity("Q937", "阿尔伯特·爱因斯坦", {"P31": item_claim("Q5")})}
        repo = self._make_repo(entities)
        entity = await repo._get_entity_detail("Q937")
        assert entity.type == "person"
        # 直接命中 → 不触发 P279 父类查询
        assert len(repo._client.calls) == 1

    @pytest.mark.asyncio
    async def test_p279_inheritance_via_class_parent(self):
        """P31 目标类未映射 → 拉取该类 P279 父类 → Q43229 组织"""
        class_qid = "Q999_unknown_class"
        entities = {
            "Q500": wd_entity("Q500", "某研究机构", {"P31": item_claim(class_qid)}),
            class_qid: wd_entity(class_qid, "科研单位", {"P279": item_claim("Q43229")}),
        }
        repo = self._make_repo(entities)
        entity = await repo._get_entity_detail("Q500")
        assert entity.type == "organization"
        # 初始详情 + P279 父类查询 = 2 次
        assert len(repo._client.calls) == 2

    @pytest.mark.asyncio
    async def test_description_fallback_when_all_layers_miss(self):
        entities = {"Q500": wd_entity("Q500", "某某", {}, description="一家科技公司")}
        repo = self._make_repo(entities)
        entity = await repo._get_entity_detail("Q500")
        assert entity.type == "organization"

    @pytest.mark.asyncio
    async def test_entity_own_p279_claims_counted(self):
        """实体自身 P279 声明（类实体）直接参与继承推断"""
        entities = {"Q700": wd_entity("Q700", "某个类", {"P279": item_claim("Q11424")})}
        repo = self._make_repo(entities)
        entity = await repo._get_entity_detail("Q700")
        assert entity.type == "concept"


# ---------- AI 兜底：focus_entity_type ----------

class TestFocusEntityType:
    def test_focus_entity_type_field(self):
        result = EntityExtractionResult(
            entities=[], relations=[], focus_entity_type="organization"
        )
        assert result.focus_entity_type == "organization"

    def test_default_none(self):
        result = EntityExtractionResult(entities=[], relations=[])
        assert result.focus_entity_type is None

    @pytest.mark.asyncio
    async def test_center_rule_type_entity_uses_llm_override(self):
        """中心规则类型为 entity 且 LLM 给出类型 → 覆盖为 LLM 判定"""
        extraction = EntityExtractionResult(
            entities=[],
            relations=[],
            focus_entity_type="organization",
        )
        # 空 entities 时无节点写入；仅验证 override 透出
        from app.repositories.wikidata_repo import WikidataRepository

        class FakeWD:
            async def search_raw(self, *a, **k):
                return []

        class FakeN4j:
            async def upsert_entity(self, d):
                return True

            async def upsert_relation(self, **k):
                return True

        result = await merge_llm_entities(
            extraction, "Q312", ["苹果公司"], FakeWD(), FakeN4j(),
            center_entity_type="entity",
        )
        assert result["focus_entity_type"] == "organization"

    @pytest.mark.asyncio
    async def test_center_non_entity_no_override(self):
        """中心规则类型非 entity（如 organization）→ 不覆盖"""
        extraction = EntityExtractionResult(entities=[], relations=[], focus_entity_type="person")

        class FakeWD:
            async def search_raw(self, *a, **k):
                return []

        class FakeN4j:
            async def upsert_entity(self, d):
                return True

            async def upsert_relation(self, **k):
                return True

        result = await merge_llm_entities(
            extraction, "Q312", ["苹果公司"], FakeWD(), FakeN4j(),
            center_entity_type="organization",
        )
        assert result["focus_entity_type"] is None

    @pytest.mark.asyncio
    async def test_center_entity_no_llm_type_keeps_entity(self):
        extraction = EntityExtractionResult(entities=[], relations=[])

        class FakeWD:
            async def search_raw(self, *a, **k):
                return []

        class FakeN4j:
            async def upsert_entity(self, d):
                return True

            async def upsert_relation(self, **k):
                return True

        result = await merge_llm_entities(
            extraction, "Q312", ["苹果公司"], FakeWD(), FakeN4j(),
            center_entity_type="entity",
        )
        assert result["focus_entity_type"] is None


class TestValidNodeTypes:
    def test_valid_node_types(self):
        assert "category" in _VALID_NODE_TYPES
        assert "organization" in _VALID_NODE_TYPES
        assert "technology" in _VALID_NODE_TYPES

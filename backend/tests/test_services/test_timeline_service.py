"""演化时间轴服务单元测试（不依赖网络，使用 mock Wikidata）"""

import pytest

from app.services.timeline_service import TimelineService
from app.repositories.wikidata_repo import WikidataEntity


def make_time_claim(time: str = "+1879-03-14T00:00:00Z"):
    return {
        "mainsnak": {
            "datatype": "time",
            "datavalue": {"value": {"time": time}},
        }
    }


def make_qualifier_time(time: str) -> dict:
    """Wikidata 限定符是扁平结构：datatype/datavalue 直接放（无 mainsnak）"""
    return {
        "datatype": "time",
        "datavalue": {"value": {"time": time}},
    }


def make_item_claim(qid: str, year: str = ""):
    claim = {
        "mainsnak": {
            "datatype": "wikibase-item",
            "datavalue": {"value": {"id": qid}},
        }
    }
    if year:
        claim["qualifiers"] = {"P585": [make_qualifier_time(year)]}
    return claim


def make_entity(claims: dict) -> WikidataEntity:
    return WikidataEntity(
        id="Q937",
        label="阿尔伯特·爱因斯坦",
        label_en="Albert Einstein",
        description="物理学家",
        type="person",
        aliases=[],
        sitelink_zh="",
        sitelink_en="",
        claims=claims,
    )


class FakeWikidata:
    def __init__(self, entity, labels: dict[str, str]):
        self._entity = entity
        self._labels = labels

    async def get_entity_by_qid(self, qid):
        return self._entity

    async def get_entity_labels(self, qids, language="zh"):
        return {q: self._labels.get(q, "") for q in qids}


class NoEntity:
    async def get_entity_by_qid(self, qid):
        return None

    async def get_entity_labels(self, qids, language="zh"):
        return {}


class FakeCache:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ttl=0):
        self.data[key] = value


@pytest.mark.asyncio
async def test_timeline_keeps_lifecycle_events():
    """生命周期事件（出生/逝世）必须保留，即使被教育/任职记录包围"""
    claims = {
        "P569": [make_time_claim("+1879-03-14T00:00:00Z")],  # 出生
        "P570": [make_time_claim("+1955-04-18T00:00:00Z")],  # 逝世
        "P69": [make_item_claim("Q1", "+1896-01-01T00:00:00Z")],   # 学校
        "P108": [make_item_claim("Q2", "+1902-01-01T00:00:00Z")],  # 雇主
    }
    wikidata = FakeWikidata(make_entity(claims), {"Q1": "苏黎世联邦理工", "Q2": "专利局"})
    service = TimelineService(wikidata=wikidata, cache=FakeCache())

    result = await service.get_timeline("Q937")

    years = [m["year"] for m in result["milestones"]]
    titles = [m["title"] for m in result["milestones"]]

    # 出生与逝世必须都在
    assert 1879 in years
    assert 1955 in years
    assert "出生" in titles
    assert "逝世" in titles
    # 按年份升序
    assert years == sorted(years)
    # 不超过上限
    assert result["total"] <= 10
    # 无内部标记字段泄漏
    assert all("_lifecycle" not in m for m in result["milestones"])


@pytest.mark.asyncio
async def test_timeline_extracts_entity_qualifier_milestones():
    """教育/任职等带时间限定符的实体里程碑应被提取"""
    claims = {
        "P166": [make_item_claim("Q3", "+1921-01-01T00:00:00Z")],  # 获奖
    }
    wikidata = FakeWikidata(make_entity(claims), {"Q3": "诺贝尔物理学奖"})
    service = TimelineService(wikidata=wikidata, cache=FakeCache())

    result = await service.get_timeline("Q937")

    assert result["total"] >= 1
    assert result["milestones"][0]["year"] == 1921
    assert result["milestones"][0]["title"] == "诺贝尔物理学奖"


@pytest.mark.asyncio
async def test_timeline_empty_for_missing_entity():
    service = TimelineService(wikidata=NoEntity(), cache=FakeCache())
    result = await service.get_timeline("Q999")
    assert result["milestones"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_timeline_uses_cache():
    claims = {
        "P569": [make_time_claim("+1879-03-14T00:00:00Z")],
        "P570": [make_time_claim("+1955-04-18T00:00:00Z")],
    }
    cache = FakeCache()
    service = TimelineService(wikidata=FakeWikidata(make_entity(claims), {}), cache=cache)
    first = await service.get_timeline("Q937")
    second = await service.get_timeline("Q937")
    assert first == second
    assert "timeline:Q937" in cache.data

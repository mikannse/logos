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
        # 作品出版年表（qid -> year）；默认空 = 作品无出版年
        self.work_years: dict[str, int] = {}

    async def get_entity_by_qid(self, qid):
        return self._entity

    async def get_entity_labels(self, qids, language="zh"):
        return {q: self._labels.get(q, "") for q in qids}

    async def get_claim_time_years(self, qids, prop):
        return {q: y for q, y in self.work_years.items() if q in qids}


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


@pytest.mark.asyncio
async def test_timeline_includes_notable_work_publication_years():
    """修复 2：P800 著名作品 → 作品条目 P577 出版年进入时间轴"""
    claims = {
        "P569": [make_time_claim("+1818-05-05T00:00:00Z")],
        "P570": [make_time_claim("+1883-03-14T00:00:00Z")],
        "P800": [make_item_claim("Q58784"), make_item_claim("Q4701")],  # 资本论、共产党宣言
        "P551": [make_item_claim("Q84", "+1837-01-01T00:00:00Z")],  # 居住地柏林（低优先级）
    }
    wikidata = FakeWikidata(make_entity(claims), {"Q58784": "资本论", "Q4701": "共产党宣言", "Q84": "柏林"})
    wikidata.work_years = {"Q58784": 1867, "Q4701": 1848}
    service = TimelineService(wikidata=wikidata, cache=FakeCache())

    result = await service.get_timeline("Q937")

    titles = {m["year"]: m["title"] for m in result["milestones"]}
    # 作品出版里程碑必须存在（出版年在作品条目，非中心声明）
    assert titles.get(1848) == "共产党宣言"
    assert titles.get(1867) == "资本论"


@pytest.mark.asyncio
async def test_timeline_work_publication_outranks_residence_when_truncated():
    """修复 2：代表作（tier 1）优先于居住地（tier 4）填充上限名额"""
    # 10 个名额：2 生命周期 + 3 作品 + 2 重要事件 + 3 教育 = 10 已满；
    # 居住地（更晚年份）即使时间更近也不得挤占 tier 更高的名额。
    claims = {
        "P569": [make_time_claim("+1800-01-01T00:00:00Z")],
        "P570": [make_time_claim("+1870-01-01T00:00:00Z")],
        "P800": [make_item_claim("Q10"), make_item_claim("Q11"), make_item_claim("Q12")],
        "P793": [make_item_claim("Q20", "+1848-01-01T00:00:00Z")],
        "P166": [make_item_claim("Q21", "+1850-01-01T00:00:00Z")],
        "P69": [make_item_claim("Q30", "+1820-01-01T00:00:00Z"),
                make_item_claim("Q31", "+1830-01-01T00:00:00Z"),
                make_item_claim("Q32", "+1840-01-01T00:00:00Z")],
        "P551": [make_item_claim("Q40", "+1860-01-01T00:00:00Z")],  # 居住地 1860，tier 4 应被挤出
    }
    labels = {"Q10": "作品一", "Q11": "作品二", "Q12": "作品三",
              "Q20": "重大事件", "Q21": "某奖项",
              "Q30": "学校一", "Q31": "学校二", "Q32": "学校三", "Q40": "某地"}
    wikidata = FakeWikidata(make_entity(claims), labels)
    wikidata.work_years = {"Q10": 1825, "Q11": 1835, "Q12": 1845}
    service = TimelineService(wikidata=wikidata, cache=FakeCache())

    result = await service.get_timeline("Q937")

    titles = [m["title"] for m in result["milestones"]]
    assert result["total"] <= 10
    # 10 个名额被 2 生命周期 + 3 作品 + 2 事件/获奖 + 3 教育占满
    assert "某地" not in titles, "低优先级居住地不应挤占作品/事件名额"
    assert "作品一" in titles and "作品三" in titles
    assert "重大事件" in titles and "某奖项" in titles
    assert "学校一" in titles and "学校三" in titles


@pytest.mark.asyncio
async def test_timeline_works_without_publication_year_are_skipped():
    """修复 2：作品条目无 P577（无出版年）→ 静默跳过，不产生空里程碑"""
    claims = {
        "P569": [make_time_claim("+1818-05-05T00:00:00Z")],
        "P800": [make_item_claim("Q999")],  # 无出版年的作品
    }
    wikidata = FakeWikidata(make_entity(claims), {"Q999": "未出版手稿"})
    # work_years 默认空 → get_claim_time_years 返回 {} → 跳过
    service = TimelineService(wikidata=wikidata, cache=FakeCache())

    result = await service.get_timeline("Q937")

    titles = [m["title"] for m in result["milestones"]]
    assert "未出版手稿" not in titles
    assert result["total"] == 1  # 仅出生

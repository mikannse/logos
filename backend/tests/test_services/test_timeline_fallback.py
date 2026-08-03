"""P6: 时间轴 AI 兜底丰富 + Summarizer.extract_milestones"""

import pytest

from app.ai.summarizer import Summarizer, ExtractedMilestone, MilestoneExtractionResult
from app.services.timeline_service import TimelineService, _MAX_MILESTONES
from app.repositories.wikidata_repo import WikidataEntity


# ---------- Summarizer.extract_milestones ----------

class FakeLLM:
    def __init__(self, milestones=None):
        self._milestones = milestones
        self.calls = []

    async def structured_extract(self, text, response_model, system_prompt="", model=None):
        self.calls.append({"text": text, "system_prompt": system_prompt})
        return MilestoneExtractionResult(milestones=self._milestones or [])

    async def generate_summary(self, *args, **kwargs):
        return ""


class TestExtractMilestones:
    @pytest.mark.asyncio
    async def test_returns_structured_milestones(self):
        llm = FakeLLM(milestones=[
            ExtractedMilestone(year=1976, title="苹果公司成立", description="车库创立"),
            ExtractedMilestone(year=2007, title="发布 iPhone", description="智能手机革命"),
        ])
        summarizer = Summarizer(llm=llm)

        result = await summarizer.extract_milestones("苹果公司", "苹果公司成立于1976年...")

        assert isinstance(result, list)
        assert result[0].year == 1976
        assert result[0].title == "苹果公司成立"
        assert result[1].description == "智能手机革命"

    @pytest.mark.asyncio
    async def test_focus_entity_in_prompt(self):
        llm = FakeLLM()
        summarizer = Summarizer(llm=llm)
        await summarizer.extract_milestones("苹果公司", "文本")
        assert "苹果公司" in llm.calls[0]["system_prompt"]

    @pytest.mark.asyncio
    async def test_empty_when_llm_unconfigured(self):
        llm = FakeLLM(milestones=[])
        summarizer = Summarizer(llm=llm)
        result = await summarizer.extract_milestones("X", "文本")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_key_facts_removed(self):
        """extract_key_facts 的 TODO 占位应被 extract_milestones 取代"""
        assert not hasattr(Summarizer, "extract_key_facts")


# ---------- TimelineService AI 兜底 ----------

def make_time_claim(time: str = "+1879-03-14T00:00:00Z"):
    return {"mainsnak": {"datatype": "time", "datavalue": {"value": {"time": time}}}}


def make_entity(claims: dict, label: str = "苹果公司") -> WikidataEntity:
    return WikidataEntity(
        id="Q312", label=label, label_en="Apple Inc.", description="",
        type="organization", aliases=[], sitelink_zh="https://zh.wikipedia.org/wiki/苹果公司",
        sitelink_en="", claims=claims,
    )


class FakeWikidata:
    def __init__(self, entity):
        self._entity = entity

    async def get_entity_by_qid(self, qid):
        return self._entity

    async def get_entity_labels(self, qids, language="zh"):
        return {}


class FakeWebSearch:
    def __init__(self, summary=""):
        self.summary = summary
        self.calls = []

    async def search_and_extract(self, query, entity_type=None):
        self.calls.append(query)
        if not self.summary:
            return None
        return {"query": query, "summary": self.summary}


class FakeSummarizer:
    def __init__(self, milestones=None):
        self.milestones = milestones or []
        self.calls = []

    async def extract_milestones(self, focus_entity, text):
        self.calls.append(focus_entity)
        return self.milestones


class FakeCache:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ttl=0):
        self.data[key] = value


def ai_milestones():
    return [
        ExtractedMilestone(year=1984, title="发布 Macintosh", description="个人电脑"),
        ExtractedMilestone(year=2001, title="发布 iPod", description="数字音乐"),
        ExtractedMilestone(year=1976, title="苹果公司成立", description="车库创立"),
    ]


class TestTimelineAiFallback:
    @pytest.mark.asyncio
    async def test_sparse_timeline_triggers_ai_fallback(self):
        """Wikidata 仅 2 个里程碑（<5）→ 触发 Web Search + 里程碑提取合并"""
        claims = {
            "P571": [make_time_claim("+1976-04-01T00:00:00Z")],  # 成立
            "P576": [make_time_claim("+1997-01-01T00:00:00Z")],  # 解散（示例数据）
        }
        wikidata = FakeWikidata(make_entity(claims))
        web_search = FakeWebSearch("苹果公司发展历史...")
        summarizer = FakeSummarizer(ai_milestones())

        service = TimelineService(
            wikidata=wikidata, cache=FakeCache(),
            web_search=web_search, summarizer=summarizer,
        )
        result = await service.get_timeline("Q312")

        assert web_search.calls == ["苹果公司"]
        assert summarizer.calls == ["苹果公司"]
        assert result["total"] >= 4  # 2 Wikidata + ≥2 AI（去重后）

    @pytest.mark.asyncio
    async def test_dedup_year_title_wikidata_priority(self):
        """(year,title) 去重；AI 与 Wikidata 同条目不重复添加"""
        claims = {"P571": [make_time_claim("+1976-04-01T00:00:00Z")]}
        wikidata = FakeWikidata(make_entity(claims))
        summarizer = FakeSummarizer([
            ExtractedMilestone(year=1976, title="成立", description="AI 版本"),
        ])
        service = TimelineService(
            wikidata=wikidata, cache=FakeCache(),
            web_search=FakeWebSearch("文本"), summarizer=summarizer,
        )
        result = await service.get_timeline("Q312")

        titles = [m["title"] for m in result["milestones"]]
        # 同 (1976, 成立)：Wikidata 版本保留（描述含实体名），AI 版本不重复
        assert titles.count("成立") == 1

    @pytest.mark.asyncio
    async def test_ai_milestones_sorted_by_year_capped(self):
        """AI 合并后按年份升序，封顶 10"""
        claims = {"P571": [make_time_claim("+1976-04-01T00:00:00Z")]}
        wikidata = FakeWikidata(make_entity(claims))
        many_ai = [ExtractedMilestone(year=1980 + i, title=f"事件{i}", description="x") for i in range(15)]
        service = TimelineService(
            wikidata=wikidata, cache=FakeCache(),
            web_search=FakeWebSearch("文本"), summarizer=FakeSummarizer(many_ai),
        )
        result = await service.get_timeline("Q312")

        years = [m["year"] for m in result["milestones"]]
        assert years == sorted(years)
        assert result["total"] <= _MAX_MILESTONES

    @pytest.mark.asyncio
    async def test_ai_milestone_confidence_marked(self):
        """AI 提取里程碑标注低置信度（0.5）"""
        claims = {"P571": [make_time_claim("+1976-04-01T00:00:00Z")]}
        wikidata = FakeWikidata(make_entity(claims))
        service = TimelineService(
            wikidata=wikidata, cache=FakeCache(),
            web_search=FakeWebSearch("文本"), summarizer=FakeSummarizer(ai_milestones()),
        )
        result = await service.get_timeline("Q312")

        ai_titles = {"发布 Macintosh", "发布 iPod"}
        ai_items = [m for m in result["milestones"] if m["title"] in ai_titles]
        assert ai_items
        assert all(m["confidence"] == 0.5 for m in ai_items)
        # AI 里程碑带描述与来源链接
        assert all(m["description"] for m in ai_items)
        assert all(m["source_url"] for m in ai_items)

    @pytest.mark.asyncio
    async def test_rich_timeline_skips_ai(self):
        """Wikidata 里程碑 >=5 → 不触发 AI（省成本）"""
        claims = {"P793": {}}
        # 6 个直接时间属性里程碑
        claims = {
            "P569": [make_time_claim(f"+{1900 + i}-01-01T00:00:00Z") for i in range(6)]
        }
        wikidata = FakeWikidata(make_entity(claims))
        web_search = FakeWebSearch("文本")
        summarizer = FakeSummarizer(ai_milestones())
        service = TimelineService(
            wikidata=wikidata, cache=FakeCache(),
            web_search=web_search, summarizer=summarizer,
        )
        result = await service.get_timeline("Q312")

        assert web_search.calls == []
        assert summarizer.calls == []
        assert result["total"] >= 5

    @pytest.mark.asyncio
    async def test_llm_unconfigured_degrades_to_wikidata(self):
        """LLM 未配置（摘要为空 → AI 里程碑为空）→ 仅 Wikidata 时间轴"""
        claims = {"P571": [make_time_claim("+1976-04-01T00:00:00Z")]}
        wikidata = FakeWikidata(make_entity(claims))
        web_search = FakeWebSearch("")  # 无摘要
        service = TimelineService(
            wikidata=wikidata, cache=FakeCache(),
            web_search=web_search, summarizer=FakeSummarizer([]),
        )
        result = await service.get_timeline("Q312")
        assert result["total"] == 1
        assert result["milestones"][0]["confidence"] == 0.8  # Wikidata 置信度

    @pytest.mark.asyncio
    async def test_wikidata_milestones_have_source_link(self):
        """Wikidata 里程碑也附带来源链接（实体 Wikipedia 页）"""
        claims = {"P571": [make_time_claim("+1976-04-01T00:00:00Z")]}
        wikidata = FakeWikidata(make_entity(claims))
        service = TimelineService(
            wikidata=wikidata, cache=FakeCache(),
            web_search=FakeWebSearch(""), summarizer=FakeSummarizer([]),
        )
        result = await service.get_timeline("Q312")
        assert result["milestones"][0]["source_url"].startswith("http")

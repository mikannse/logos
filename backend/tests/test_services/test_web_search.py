"""AI Web Search 三层数据源测试（sprint-change-proposal-2026-08-01-web-search）

T1 未配置 Tavily Key → 短路 Tavily、进入兜底池、兜底也无内容时 LLM 记忆退化
T2 Tavily 成功 → LLM 综合真实内容，不进兜底池，sources 含 URL
T3 Tavily 失败 → 降级领域感知权威兜底池
T4 Tavily + 兜底池全失败 → LLM 记忆退化（不抛异常）
T5 Tavily 请求参数（max_results / search_depth / include_answer / api_key）
T6 DNS-pinning 复用（resolve_endpoint(api.tavily.com)，不裸 httpx 直连）
T7 实体类型路由 + 单源失败隔离
全部 Mock 外部，零真实网络请求。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.web_search import (
    TAVILY_API,
    SourceResult,
    WebSearch,
    _parse_arxiv,
    _route_for,
)
from app.services.config_service import LLMConfig


# ---------- 测试替身 ----------

class FakeConfigService:
    """模拟运行时配置（含/不含 Tavily Key）"""

    def __init__(self, tavily_key: str = ""):
        self._key = tavily_key

    async def get_llm_config(self):
        return LLMConfig(tavily_api_key=self._key)


class FakeLLM:
    def __init__(self, summary: str = "记忆摘要"):
        self._summary = summary
        self.prompts: list[str] = []

    async def generate_summary(self, text, max_length=200):
        self.prompts.append(text)
        return self._summary


def _make_ws(tavily_key: str = "", summary: str = "记忆摘要"):
    return WebSearch(
        llm=FakeLLM(summary),
        config_service=FakeConfigService(tavily_key),
    )


# ---------- T1：未配置 Tavily Key ----------

class TestNoTavilyKey:
    @pytest.mark.asyncio
    async def test_no_key_shortcircuits_tavily_and_degrades(self):
        ws = _make_ws(tavily_key="", summary="记忆摘要")
        with patch.object(WebSearch, "_post_json", new=AsyncMock(return_value=None)) as mock_post, \
             patch.object(WebSearch, "_call_source", new=AsyncMock(return_value=[])) as mock_src:
            result = await ws.search_and_extract("某个冷门名词")

        mock_post.assert_not_called()          # 无 Key：Tavily 直接短路，不发起外部调用
        assert mock_src.called                 # 无 Key：进入权威兜底池
        assert result["summary"] == "记忆摘要"  # 兜底池也无内容 → LLM 记忆退化
        assert result["sources"] == []


# ---------- T2：Tavily 成功 ----------

class TestTavilySuccess:
    @pytest.mark.asyncio
    async def test_synthesizes_real_content(self):
        fake_llm = FakeLLM("综合摘要")
        ws = WebSearch(llm=fake_llm, config_service=FakeConfigService("tvly-key"))
        tavily_resp = {
            "answer": "苹果公司是一家美国跨国科技公司，由史蒂夫·乔布斯、史蒂夫·沃兹尼亚克与罗纳德·韦恩于1976年4月1日在加州库比蒂诺创立，总部位于Apple Park。",
            "results": [
                {"url": "https://example.com/a",
                 "content": "苹果公司最初以 Apple I 个人电脑起家，1984年推出革命性的 Macintosh 图形界面电脑。"
                           "1997年乔布斯回归后推出 iMac，2001年发布 iPod 定义数字音乐时代。"},
                {"url": "https://example.com/b",
                 "content": "2007年发布的 iPhone 重新定义了智能手机行业，"
                           "2010年 iPad 开创平板电脑品类，2020年推出自研 Apple Silicon M1 芯片。"},
                {"url": "https://example.com/c",
                 "content": "苹果的主要产品线包括 iPhone、Mac、iPad、Apple Watch、AirPods、"
                           "Apple Vision Pro 以及服务业务如 App Store、Apple Music、iCloud。"},
            ],
        }
        with patch.object(WebSearch, "_post_json", new=AsyncMock(return_value=tavily_resp)), \
             patch.object(WebSearch, "_call_source", new=AsyncMock(return_value=[])) as mock_src:
            result = await ws.search_and_extract("苹果公司", entity_type="organization")

        mock_src.assert_not_called()               # Tavily 内容充足 → 不进入兜底池
        assert result["summary"] == "综合摘要"
        assert fake_llm.prompts, "LLM 应被调用以综合真实内容"
        assert "1976" in fake_llm.prompts[0]       # 综合的是搜索到的真实内容
        assert "【Tavily】" in fake_llm.prompts[0]
        urls = [s["url"] for s in result["sources"]]
        assert "https://example.com/a" in urls


# ---------- T3：Tavily 失败 → 权威兜底池 ----------

class TestTavilyFailureFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_authoritative_pool(self):
        ws = _make_ws(tavily_key="tvly-key", summary="兜底摘要")
        wiki = [SourceResult("Wikipedia", "https://zh.wikipedia.org/wiki/X", "X 是一家……" * 30)]

        async def fake_call_source(source, query):
            return wiki if source == "wikipedia" else []

        with patch.object(WebSearch, "_post_json", new=AsyncMock(return_value=None)), \
             patch.object(WebSearch, "_call_source", new=AsyncMock(side_effect=fake_call_source)):
            result = await ws.search_and_extract("X", entity_type="concept")

        assert result["summary"] == "兜底摘要"
        assert any(s["name"] == "Wikipedia" for s in result["sources"])


# ---------- T4：全部失败 → LLM 记忆退化 ----------

class TestAllSourcesFail:
    @pytest.mark.asyncio
    async def test_degrades_to_llm_memory_without_exception(self):
        ws = _make_ws(tavily_key="tvly-key", summary="记忆摘要")
        with patch.object(WebSearch, "_post_json", new=AsyncMock(return_value=None)), \
             patch.object(WebSearch, "_call_source", new=AsyncMock(return_value=[])):
            result = await ws.search_and_extract("无人知晓的词条")

        assert result["summary"] == "记忆摘要"
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_llm_unconfigured_returns_empty_summary(self):
        """LLM 未配置（generate_summary 返回空）→ 空 summary，调用方静默跳过，不抛异常"""

        class DeadLLM:
            async def generate_summary(self, *a, **k):
                return ""

        ws = WebSearch(llm=DeadLLM(), config_service=FakeConfigService(""))
        with patch.object(WebSearch, "_call_source", new=AsyncMock(return_value=[])):
            result = await ws.search_and_extract("X")

        assert result["summary"] == ""


# ---------- T5/T6：Tavily 请求参数 + DNS-pinning ----------

class TestTavilyRequestWiring:
    @pytest.mark.asyncio
    async def test_params_and_dns_pinning(self):
        ws = _make_ws(tavily_key="tvly-key-123")

        captured = {}
        fake_resp = MagicMock(status_code=200)
        fake_resp.json.return_value = {"answer": "", "results": []}

        def fake_post(url, **kwargs):
            captured["url"] = url
            captured["payload"] = kwargs.get("json")
            return fake_resp

        fake_client = MagicMock()
        fake_client.post = MagicMock(side_effect=fake_post)
        fake_resolved = MagicMock()
        fake_resolved.make_http_client.return_value = fake_client

        with patch("app.ai.web_search.resolve_endpoint", return_value=fake_resolved) as mock_resolve:
            await ws._tavily_search("量子计算")

        # T6：DNS-pinning 复用（对 api.tavily.com 走 resolve_endpoint）
        mock_resolve.assert_called_once_with(TAVILY_API)
        fake_resolved.make_http_client.assert_called_once()

        # T5：请求参数
        payload = captured["payload"]
        assert captured["url"] == f"{TAVILY_API}/search"
        assert payload["api_key"] == "tvly-key-123"
        assert payload["query"] == "量子计算"
        assert payload["max_results"] == 5
        assert payload["search_depth"] == "advanced"
        assert payload["include_answer"] is True


# ---------- T7：实体类型路由 + 单源失败隔离 ----------

class TestTypeRouting:
    def test_route_table(self):
        assert _route_for("person") == ["wikipedia", "openalex", "github", "musicbrainz"]
        assert _route_for("organization") == ["wikipedia", "openalex", "github"]
        assert _route_for("technology") == ["wikipedia", "github", "hackernews", "arxiv"]
        assert _route_for("concept") == ["wikipedia", "wiktionary", "openalex", "arxiv"]
        assert _route_for("event") == ["wikipedia", "hackernews"]
        assert _route_for("book") == ["wikipedia", "openlibrary"]
        assert _route_for("music") == ["wikipedia", "musicbrainz"]
        assert _route_for("place") == ["wikipedia", "nominatim"]
        assert _route_for(None) == ["wikipedia", "openalex", "hackernews"]
        assert _route_for("unknown") == ["wikipedia", "openalex", "hackernews"]

    @pytest.mark.asyncio
    async def test_person_route_with_failure_isolation(self):
        ws = _make_ws(tavily_key="", summary="路由摘要")
        calls: list[str] = []

        def make_src(name, fail=False):
            async def _src(query):
                calls.append(name)
                if fail:
                    raise RuntimeError("boom")
                return [SourceResult(name, f"https://{name}.example/x", f"{name} 内容 " * 20)]
            return _src

        for src in ["wikipedia", "openalex", "github", "musicbrainz",
                    "hackernews", "arxiv", "wiktionary", "openlibrary", "nominatim"]:
            setattr(ws, f"_src_{src}", make_src(src, fail=(src == "musicbrainz")))

        # person 路由；musicbrainz 失败被隔离，其余源照常
        result = await ws.search_and_extract("爱因斯坦", entity_type="person")
        assert set(calls) == {"wikipedia", "openalex", "github", "musicbrainz"}
        assert result["summary"] == "路由摘要"
        names = {s["name"] for s in result["sources"]}
        assert names == {"wikipedia", "openalex", "github"}  # 失败源被剔除

        calls.clear()
        await ws.search_and_extract("React", entity_type="technology")
        assert set(calls) == {"wikipedia", "github", "hackernews", "arxiv"}


# ---------- arXiv XML 解析（defusedxml 安全） ----------

class TestArxivParsing:
    def test_parse_arxiv_xml(self):
        xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Attention Is All You Need</title>
            <summary>Transformer architecture...</summary>
            <published>2017-06-12T00:00:00Z</published>
            <link rel="alternate" href="https://arxiv.org/abs/1706.03762"/>
          </entry>
        </feed>"""
        results = _parse_arxiv(xml)
        assert len(results) == 1
        assert "Attention Is All You Need" in results[0].text
        assert "2017" in results[0].text
        assert results[0].url == "https://arxiv.org/abs/1706.03762"

    def test_malicious_dtd_silently_dropped(self):
        """billion-laughs / DTD 注入 → defusedxml 拒绝，静默返回空（不抛异常）"""
        xml = """<?xml version="1.0"?>
        <!DOCTYPE lolz [
          <!ENTITY lol "lol">
          <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
        ]>
        <feed xmlns="http://www.w3.org/2005/Atom"><entry><title>&lol2;</title></entry></feed>"""
        assert _parse_arxiv(xml) == []

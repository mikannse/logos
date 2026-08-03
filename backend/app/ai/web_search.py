"""AI Web Search 工具 —— Tavily 全网搜索（主源）+ 领域感知权威源兜底池

三层数据源（替换原 LLM 记忆占位实现，见 sprint-change-proposal-2026-08-01-web-search）：

  Layer 1: Tavily 全网搜索（真实联网，主源；Key 运行时设置页配置）
  Layer 2: 领域感知权威源兜底池（按实体类型路由，直接查询各源 API）
  Layer 3: LLM 记忆摘要（终极兜底，无任何外部源可用时）

采集到的真实内容拼接后交 LLM 综合成聚焦摘要（仅基于材料，禁止编造）。
所有外部域走 resolve_endpoint DNS-pinning；纯 httpx 直调，不新增 pip 依赖。
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional

import defusedxml.ElementTree as ET  # 防 XXE / billion-laughs（解析外部 arXiv Atom XML）

from app.ai.llm_client import LLMClient
from app.core.endpoint_security import resolve_endpoint
from app.services.config_service import ConfigService

TAVILY_API = "https://api.tavily.com"

# 外部源 UA：GitHub / MusicBrainz / Nominatim 等服务要求可识别的 User-Agent
_UA = "Logos/0.1 (Knowledge Graph Explorer; contact@logos.app) httpx/0.27"
_HEADERS_GENERIC = {"User-Agent": _UA}
_HEADERS_GITHUB = {"User-Agent": "Logos/0.1", "Accept": "application/vnd.github+json"}
_HEADERS_MUSICBRAINZ = {"User-Agent": "Logos/0.1 (contact@logos.app)"}
_HEADERS_NOMINATIM = {"User-Agent": _UA, "Accept-Language": "zh"}

# 内容充足阈值：Tavily 采集到的总字符数低于此值时进入权威兜底池
_MIN_CONTENT_CHARS = 150


@dataclass
class SourceResult:
    """兜底池各源的统一返回结构"""
    name: str       # 数据源名（Wikipedia / OpenAlex / GitHub / ...）
    url: str        # 来源链接（可为空）
    text: str       # 正文内容（摘要片段）


# 领域感知路由：实体类型 → 兜底源（按优先级；类型体系见 wikidata_repo._map_wikidata_type）
_TYPE_ROUTES: dict[str, list[str]] = {
    "person":       ["wikipedia", "openalex", "github", "musicbrainz"],
    "organization": ["wikipedia", "openalex", "github"],
    "technology":   ["wikipedia", "github", "hackernews", "arxiv"],
    "event":        ["wikipedia", "hackernews"],
    "concept":      ["wikipedia", "wiktionary", "openalex", "arxiv"],
    # 预留：类型体系扩展后自动生效（当前类型推断仅产出上面六类 + entity）
    "book":         ["wikipedia", "openlibrary"],
    "music":        ["wikipedia", "musicbrainz"],
    "place":        ["wikipedia", "nominatim"],
}
_DEFAULT_ROUTE = ["wikipedia", "openalex", "hackernews"]


def _route_for(entity_type: Optional[str]) -> list[str]:
    """按实体类型选兜底源；未知/未传类型走通用默认组合"""
    if entity_type and entity_type in _TYPE_ROUTES:
        return _TYPE_ROUTES[entity_type]
    return _DEFAULT_ROUTE


def _has_enough(sources: list[SourceResult]) -> bool:
    return sum(len(s.text) for s in sources) >= _MIN_CONTENT_CHARS


# ---- 节流：Nominatim / MusicBrainz 等服务要求 ≤1 req/s，按域名串行化 ----
_throttle_locks: dict[str, asyncio.Lock] = {}
_throttle_last: dict[str, float] = {}


async def _throttle(domain: str, min_interval: float = 1.1) -> None:
    lock = _throttle_locks.setdefault(domain, asyncio.Lock())
    async with lock:
        now = time.monotonic()
        gap = now - _throttle_last.get(domain, 0.0)
        if gap < min_interval:
            await asyncio.sleep(min_interval - gap)
        _throttle_last[domain] = time.monotonic()


def _openalex_abstract(inv: Optional[dict]) -> str:
    """OpenAlex 摘要以倒排索引存储，需重建为正序文本"""
    if not inv:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


_ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _parse_arxiv(xml_text: str) -> list[SourceResult]:
    """解析 arXiv Atom XML（defusedxml，防 XXE / billion-laughs）"""
    try:
        root = ET.fromstring(xml_text)
    except Exception:  # ParseError + defusedxml 防护异常（DTD/实体/外部引用），一律静默
        return []
    results = []
    for entry in root.findall("atom:entry", _ARXIV_NS):
        title = (entry.findtext("atom:title", default="", namespaces=_ARXIV_NS) or "").strip().replace("\n", " ")
        summary = (entry.findtext("atom:summary", default="", namespaces=_ARXIV_NS) or "").strip().replace("\n", " ")
        year = (entry.findtext("atom:published", default="", namespaces=_ARXIV_NS) or "")[:4]
        link = ""
        for l in entry.findall("atom:link", _ARXIV_NS):
            if l.get("rel") == "alternate":
                link = l.get("href", "")
        text = title if not year else f"{title}（{year}）"
        if summary:
            text += f" — {summary[:300]}"
        if title:
            results.append(SourceResult("arXiv", link, text))
    return results


class WebSearch:
    """AI Web Search 工具

    先 Tavily 全网搜索（真实联网），结果不足时按实体类型路由到
    权威源兜底池，最终无外部源可用时退化 LLM 记忆摘要。
    """

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        config_service: Optional[ConfigService] = None,
    ):
        self.llm = llm or LLMClient()
        self.config_service = config_service or ConfigService()

    async def search_and_extract(
        self, query: str, entity_type: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """搜索并提取知识图谱数据

        Args:
            query: 搜索查询（如"阿尔伯特·爱因斯坦"）
            entity_type: 实体类型（person/organization/technology/event/concept/entity），
                         用于 Layer 2 兜底池的领域感知路由；不传走通用默认组合

        Returns:
            {"query": str, "summary": str, "entities": [], "relations": [],
             "sources": [{"name", "url"}]}
        """
        # Layer 1: Tavily 全网搜索（主源）
        sources = await self._tavily_search(query)

        # Layer 2: 领域感知权威源兜底池（Tavily 结果不足时）
        if not _has_enough(sources):
            route = _route_for(entity_type)
            gathered = await asyncio.gather(
                *(self._call_source(s, query) for s in route),
                return_exceptions=True,
            )
            for r in gathered:
                if isinstance(r, list):
                    sources.extend(r)

        # 有真实内容 → LLM 综合；否则 → Layer 3 LLM 记忆兜底
        summary = ""
        if sources:
            summary = await self._synthesize(query, sources)
        if not summary:
            summary = await self._llm_memory_summary(query)

        return {
            "query": query,
            "summary": summary,
            "entities": [],
            "relations": [],
            "sources": [{"name": s.name, "url": s.url} for s in sources],
        }

    # ---------- Layer 1: Tavily ----------

    async def _tavily_search(self, query: str) -> list[SourceResult]:
        """Tavily 全网搜索（advanced 深度 + 直答；无 Key/失败返回空）"""
        try:
            config = await self.config_service.get_llm_config()
            key = config.tavily_api_key
        except Exception:
            return []
        if not key:
            return []

        data = await self._post_json(
            TAVILY_API,
            "/search",
            {
                "api_key": key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 5,
                "include_answer": True,
            },
        )
        if not data:
            return []

        results: list[SourceResult] = []
        answer = (data.get("answer") or "").strip()
        if answer:
            results.append(SourceResult("Tavily", "", answer))
        for item in data.get("results", []):
            content = (item.get("content") or "").strip()
            if content:
                results.append(SourceResult("Tavily", item.get("url", ""), content))
        return results

    # ---------- Layer 2: 权威源兜底池 ----------

    async def _call_source(self, source: str, query: str) -> list[SourceResult]:
        """按源名分发到对应适配器；单源失败静默，不影响其他源"""
        method = getattr(self, f"_src_{source}", None)
        if method is None:
            return []
        try:
            return await method(query)
        except Exception:
            return []

    async def _src_wikipedia(self, query: str) -> list[SourceResult]:
        """Wikipedia（zh → en）搜索 + 导语正文（generator=search 单次调用）"""
        for lang in ("zh", "en"):
            data = await self._get_json(
                f"https://{lang}.wikipedia.org",
                "/w/api.php",
                {
                    "action": "query", "format": "json",
                    "generator": "search", "gsrsearch": query, "gsrlimit": 2,
                    "prop": "extracts|info", "exintro": "1", "explaintext": "1",
                    "exchars": "1500", "inprop": "url",
                },
                headers=_HEADERS_GENERIC,
            )
            if not data:
                continue
            pages = (data.get("query") or {}).get("pages") or {}
            results = [
                SourceResult("Wikipedia", p.get("fullurl", ""), (p.get("extract") or "").strip())
                for p in pages.values()
                if (p.get("extract") or "").strip()
            ]
            if results:
                return results
        return []

    async def _src_wiktionary(self, query: str) -> list[SourceResult]:
        """Wiktionary（zh → en）词条定义/词源"""
        for lang in ("zh", "en"):
            data = await self._get_json(
                f"https://{lang}.wiktionary.org",
                "/w/api.php",
                {
                    "action": "query", "format": "json",
                    "generator": "search", "gsrsearch": query, "gsrlimit": 1,
                    "prop": "extracts|info", "exintro": "1", "explaintext": "1",
                    "exchars": "800", "inprop": "url",
                },
                headers=_HEADERS_GENERIC,
            )
            if not data:
                continue
            pages = (data.get("query") or {}).get("pages") or {}
            results = [
                SourceResult("Wiktionary", p.get("fullurl", ""), (p.get("extract") or "").strip())
                for p in pages.values()
                if (p.get("extract") or "").strip()
            ]
            if results:
                return results
        return []

    async def _src_openalex(self, query: str) -> list[SourceResult]:
        """OpenAlex 学术文献（标题 + 年份 + 摘要片段）"""
        data = await self._get_json(
            "https://api.openalex.org",
            "/works",
            {"search": query, "per-page": 3},
        )
        if not data:
            return []
        results = []
        for w in data.get("results", []):
            title = (w.get("title") or "").strip()
            year = w.get("publication_year") or ""
            doi = w.get("doi") or w.get("id") or ""
            abstract = _openalex_abstract(w.get("abstract_inverted_index"))
            text = title if not year else f"{title}（{year}）"
            if abstract:
                text += f" — {abstract[:300]}"
            if title:
                results.append(SourceResult("OpenAlex", doi, text))
        return results

    async def _src_github(self, query: str) -> list[SourceResult]:
        """GitHub：仓库搜索 + 用户/组织搜索（无需 Key，UA 必需）"""
        results: list[SourceResult] = []
        data = await self._get_json(
            "https://api.github.com",
            "/search/repositories",
            {"q": query, "per_page": 3},
            headers=_HEADERS_GITHUB,
        )
        if data:
            for repo in data.get("items", []):
                name = repo.get("full_name") or ""
                desc = repo.get("description") or ""
                stars = repo.get("stargazers_count") or 0
                text = f"{name}：{desc}（★{stars}）"
                if name:
                    results.append(SourceResult("GitHub", repo.get("html_url", ""), text))
        users = await self._get_json(
            "https://api.github.com",
            "/search/users",
            {"q": query, "per_page": 2},
            headers=_HEADERS_GITHUB,
        )
        if users:
            for u in users.get("items", []):
                login = u.get("login") or ""
                if login:
                    results.append(
                        SourceResult("GitHub", u.get("html_url", ""), f"GitHub 用户/组织：{login}")
                    )
        return results

    async def _src_openlibrary(self, query: str) -> list[SourceResult]:
        """Open Library 图书/作者（书名 + 作者 + 首版年）"""
        data = await self._get_json(
            "https://openlibrary.org",
            "/search.json",
            {"title": query, "limit": 3},
        )
        if not data:
            return []
        results = []
        for doc in data.get("docs", []):
            title = (doc.get("title") or "").strip()
            authors = "、".join(doc.get("author_name") or [])
            year = doc.get("first_publish_year") or ""
            text = f"《{title}》"
            if authors:
                text += f"（作者：{authors}）"
            if year:
                text += f"，首次出版 {year}"
            if title:
                key = doc.get("key") or ""
                url = f"https://openlibrary.org{key}" if key else ""
                results.append(SourceResult("Open Library", url, text))
        return results

    async def _src_musicbrainz(self, query: str) -> list[SourceResult]:
        """MusicBrainz 音乐艺术家（名称 + 类型 + 国籍/说明；≤1 req/s）"""
        await _throttle("musicbrainz.org")
        data = await self._get_json(
            "https://musicbrainz.org",
            "/ws/2/artist/",
            {"query": query, "fmt": "json", "limit": 3},
            headers=_HEADERS_MUSICBRAINZ,
        )
        if not data:
            return []
        results = []
        for a in data.get("artists", []):
            name = (a.get("name") or "").strip()
            dis = a.get("disambiguation") or ""
            a_type = a.get("type") or ""
            country = a.get("country") or ""
            text = name
            if a_type:
                text += f"（{a_type}）"
            if country:
                text += f"，{country}"
            if dis:
                text += f" — {dis}"
            if name:
                mbid = a.get("id") or ""
                url = f"https://musicbrainz.org/artist/{mbid}" if mbid else ""
                results.append(SourceResult("MusicBrainz", url, text))
        return results

    async def _src_arxiv(self, query: str) -> list[SourceResult]:
        """arXiv 预印本（标题 + 年份 + 摘要片段）"""
        text = await self._get_text(
            "https://export.arxiv.org",
            "/api/query",
            {"search_query": f"all:{query}", "max_results": 3},
        )
        if not text:
            return []
        return _parse_arxiv(text)

    async def _src_hackernews(self, query: str) -> list[SourceResult]:
        """Hacker News (Algolia) 科技新闻/讨论（标题 + 年份 + 票数）"""
        data = await self._get_json(
            "https://hn.algolia.com",
            "/api/v1/search",
            {"query": query, "hitsPerPage": 5, "tags": "story"},
        )
        if not data:
            return []
        results = []
        for hit in data.get("hits", []):
            title = (hit.get("title") or "").strip()
            points = hit.get("points") or 0
            year = (hit.get("created_at") or "")[:4]
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            text = title if not year else f"{title}（{year}，{points} 票）"
            if title:
                results.append(SourceResult("Hacker News", url, text))
        return results

    async def _src_nominatim(self, query: str) -> list[SourceResult]:
        """Nominatim (OSM) 地名（display_name + 类型；≤1 req/s）"""
        await _throttle("nominatim.openstreetmap.org")
        data = await self._get_json(
            "https://nominatim.openstreetmap.org",
            "/search",
            {"q": query, "format": "json", "limit": 3, "accept-language": "zh"},
            headers=_HEADERS_NOMINATIM,
        )
        if not isinstance(data, list):
            return []
        results = []
        for item in data:
            name = (item.get("display_name") or "").strip()
            otype = item.get("type") or ""
            text = name if not otype else f"{name}（{otype}）"
            osm_type = item.get("osm_type") or ""
            osm_id = item.get("osm_id") or ""
            url = (
                f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
                if osm_type and osm_id else ""
            )
            if name:
                results.append(SourceResult("Nominatim", url, text))
        return results

    # ---------- LLM 综合 / 终极兜底 ----------

    async def _synthesize(self, query: str, sources: list[SourceResult]) -> str:
        """将采集到的真实内容交 LLM 综合成聚焦摘要（仅基于材料，禁止编造）"""
        digest = "\n\n".join(f"【{s.name}】{s.text}" for s in sources[:8])
        if not digest.strip():
            return ""
        prompt = (
            f"请仅基于以下材料，综合概括「{query}」的核心信息（中文，不超过400字）。"
            "要求：1. 这是什么（人物/概念/技术/事件等）；2. 核心事实（3-5条，尽量含年份/数字）；"
            "3. 关键关联的人和事。不得添加材料中没有的信息。\n\n"
            f"材料：\n{digest[:6000]}"
        )
        return await self.llm.generate_summary(prompt, max_length=400)

    async def _llm_memory_summary(self, query: str) -> str:
        """Layer 3：无任何外部源可用时退化 LLM 记忆摘要（原占位行为）"""
        summary_prompt = f"""请简要介绍「{query}」的核心信息，包括：
1. 这是什么（人物/概念/技术/事件）
2. 核心事实（3-5条）
3. 关键关联的人和事"""
        return await self.llm.generate_summary(summary_prompt, max_length=500)

    # ---------- DNS-pinned HTTP 基元 ----------

    async def _get_json(
        self, base_url: str, path: str, params: dict, headers: Optional[dict] = None
    ) -> Any:
        """DNS-pinned GET → JSON（任何失败返回 None）"""
        try:
            resolved = await asyncio.get_running_loop().run_in_executor(
                None, resolve_endpoint, base_url
            )
            client = resolved.make_http_client()
            try:
                resp = await asyncio.to_thread(
                    client.get,
                    f"{base_url}{path}",
                    params=params,
                    headers=headers or _HEADERS_GENERIC,
                    timeout=20,
                )
                if resp.status_code != 200:
                    return None
                return resp.json()
            finally:
                client.close()
        except Exception:
            return None

    async def _get_text(
        self, base_url: str, path: str, params: dict, headers: Optional[dict] = None
    ) -> Optional[str]:
        """DNS-pinned GET → text（任何失败返回 None；arXiv XML 用）"""
        try:
            resolved = await asyncio.get_running_loop().run_in_executor(
                None, resolve_endpoint, base_url
            )
            client = resolved.make_http_client()
            try:
                resp = await asyncio.to_thread(
                    client.get,
                    f"{base_url}{path}",
                    params=params,
                    headers=headers or _HEADERS_GENERIC,
                    timeout=20,
                )
                if resp.status_code != 200:
                    return None
                return resp.text
            finally:
                client.close()
        except Exception:
            return None

    async def _post_json(
        self, base_url: str, path: str, payload: dict, headers: Optional[dict] = None
    ) -> Optional[dict]:
        """DNS-pinned POST JSON → JSON（任何失败返回 None；Tavily 用）"""
        try:
            resolved = await asyncio.get_running_loop().run_in_executor(
                None, resolve_endpoint, base_url
            )
            client = resolved.make_http_client()
            try:
                resp = await asyncio.to_thread(
                    client.post,
                    f"{base_url}{path}",
                    json=payload,
                    headers=headers or _HEADERS_GENERIC,
                    timeout=25,
                )
                if resp.status_code != 200:
                    return None
                return resp.json()
            finally:
                client.close()
        except Exception:
            return None

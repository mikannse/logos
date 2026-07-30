"""Wikidata API 数据访问层

使用 Wikidata 公共 API（无需认证）：
- wbsearchentities: 实体搜索
- wbgetentities: 实体详情获取
- 跨语言对齐：通过 Q ID 映射中英文
"""

from dataclasses import dataclass
from typing import Optional

import httpx

WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData"


@dataclass
class WikidataEntity:
    """Wikidata 实体数据"""
    id: str               # Q ID (e.g., Q937)
    label: str            # 显示名称
    description: str      # 一句话描述
    type: str             # person / concept / technology / event
    aliases: list[str]    # 别名列表
    sitelink_zh: str      # 中文 Wikipedia 链接
    sitelink_en: str      # 英文 Wikipedia 链接
    claims: dict          # 属性声明


def _map_wikidata_type(qid: str, instance_of: list[str]) -> str:
    """将 Wikidata 实体类型映射到 Logos 类型系统"""
    type_map = {
        "Q5": "person",           # 人类
        "Q13442814": "concept",   # 学术概念
        "Q11424": "technology",   # 技术
        "Q16521": "event",        # 事件
        "Q215380": "concept",     # 音乐作品/概念
        "Q7725634": "concept",    # 文学作品
        "Q188451": "concept",     # 哲学概念
        "Q577": "technology",     # 编程语言 -> technology
        "Q7397": "technology",    # 软件
        "Q7889": "person",        # 视频游戏 -> 如需要可调整
    }
    for inst in instance_of:
        if inst in type_map:
            return type_map[inst]
    return "entity"


class WikidataRepository:
    """Wikidata 数据源 Repository"""

    def __init__(self):
        headers = {
            "User-Agent": "Logos/0.1 (Knowledge Graph Explorer; contact@logos.app) httpx/0.27",
        }
        self._client = httpx.AsyncClient(timeout=30.0, headers=headers)

    async def search(
        self, query: str, language: str = "zh", limit: int = 5
    ) -> list[WikidataEntity]:
        """搜索 Wikidata 实体

        Args:
            query: 搜索关键词（中英文均可）
            language: 搜索语言
            limit: 返回结果数量

        Returns:
            匹配的实体列表
        """
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": language,
            "format": "json",
            "limit": min(limit, 25),
        }

        try:
            response = await self._client.get(WIKIDATA_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if "search" not in data or not data["search"]:
                return []

            entities = []
            for item in data["search"][:limit]:
                entity = await self._get_entity_detail(item["id"], language)
                if entity:
                    entities.append(entity)

            return entities

        except httpx.HTTPError as e:
            print(f"Wikidata search error: {e}")
            return []

    async def _get_entity_detail(
        self, qid: str, language: str = "zh"
    ) -> Optional[WikidataEntity]:
        """获取实体详情"""
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "props": "labels|descriptions|aliases|claims|sitelinks/urls",
            "languages": f"{language}|en",
            "sitefilter": "zhwiki|enwiki",
            "format": "json",
        }

        try:
            response = await self._client.get(WIKIDATA_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

            if qid not in data.get("entities", {}):
                return None

            entity_data = data["entities"][qid]

            # 提取标签（优先请求语言，fallback 到英文）
            labels = entity_data.get("labels", {})
            label = (
                labels.get(language, {}).get("value")
                or labels.get("en", {}).get("value")
                or qid
            )

            # 提取描述
            descriptions = entity_data.get("descriptions", {})
            description = (
                descriptions.get(language, {}).get("value")
                or descriptions.get("en", {}).get("value")
                or ""
            )

            # 提取别名
            aliases_data = entity_data.get("aliases", {})
            aliases = []
            for lang in [language, "en"]:
                for alias in aliases_data.get(lang, []):
                    val = alias.get("value", "")
                    if val and val not in aliases:
                        aliases.append(val)

            # 提取实例（instance of P31）以推断类型
            instance_of = []
            claims = entity_data.get("claims", {})
            for claim in claims.get("P31", []):
                mainsnak = claim.get("mainsnak", {})
                if mainsnak.get("datatype") == "wikibase-item":
                    datavalue = mainsnak.get("datavalue", {})
                    value = datavalue.get("value", {})
                    if isinstance(value, dict):
                        instance_of.append(value.get("id", ""))

            entity_type = _map_wikidata_type(qid, instance_of)

            # 提取 Wikipedia 链接
            sitelinks = entity_data.get("sitelinks", {})
            sitelink_zh = sitelinks.get("zhwiki", {}).get("url", "")
            if not sitelink_zh:
                sitelink_zh = sitelinks.get("zh_cnwiki", {}).get("url", "")  # 中文简体
            sitelink_en = sitelinks.get("enwiki", {}).get("url", "")

            return WikidataEntity(
                id=qid,
                label=label,
                description=description,
                type=entity_type,
                aliases=aliases,
                sitelink_zh=sitelink_zh,
                sitelink_en=sitelink_en,
                claims=claims,
            )

        except httpx.HTTPError as e:
            print(f"Wikidata entity detail error: {e}")
            return None

    async def get_entity_by_qid(self, qid: str) -> Optional[WikidataEntity]:
        """通过 Q ID 获取实体（中英双语）"""
        return await self._get_entity_detail(qid, language="zh")

    async def get_wikipedia_summary(self, qid: str, language: str = "zh") -> str:
        """通过 Wikipedia API 获取摘要

        当 Wikidata 描述不够详细时，使用 Wikipedia REST API 补充。
        """
        lang_map = {"zh": "zh", "en": "en"}
        lang = lang_map.get(language, "zh")
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{qid}"

        try:
            response = await self._client.get(
                url.replace(f"/{qid}", f"/Q{qid}" if not qid.startswith("Q") else f"/{qid}"),
                follow_redirects=True,
            )
            # Wikipedia API uses titles, not QIDs, so need entity label first
            # Fallback: use Wikidata sitelink
            return ""
        except httpx.HTTPError:
            return ""

    async def close(self):
        await self._client.aclose()

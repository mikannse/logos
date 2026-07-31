"""Wikidata API 数据访问层

使用 Wikidata 公共 API（无需认证）：
- wbsearchentities: 实体搜索
- wbgetentities: 实体详情获取
- 跨语言对齐：通过 Q ID 映射中英文
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

import httpx

WIKIDATA_SEARCH_URL = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData"


@dataclass
class WikidataEntity:
    """Wikidata 实体数据"""
    id: str               # Q ID (e.g., Q937)
    label: str            # 显示名称（请求语言优先，fallback 英文）
    label_en: str         # 英文显示名称（独立提取，避免别名启发式误判）
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

    def __init__(self, proxy: Optional[str] = None):
        headers = {
            "User-Agent": "Logos/0.1 (Knowledge Graph Explorer; contact@logos.app) httpx/0.27",
        }
        # 显式代理支持：优先传入参数，其次读取配置（HTTPS_PROXY/HTTP_PROXY）
        # httpx 默认也信任环境变量（trust_env），此处显式注入让 .env 配置生效
        if proxy is None:
            from app.config import settings

            proxy = settings.https_proxy or settings.http_proxy or None
        self._client = httpx.AsyncClient(timeout=30.0, headers=headers, proxy=proxy)

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

            # 并发获取详情，避免 N+1 顺序请求导致搜索延迟被放大
            results = await asyncio.gather(
                *[
                    self._get_entity_detail(item["id"], language)
                    for item in data["search"][:limit]
                ],
                return_exceptions=True,
            )
            return [r for r in results if isinstance(r, WikidataEntity)]

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
            # 英文标签独立提取——用于消歧展示等场景，避免从别名猜测英文名
            label_en = labels.get("en", {}).get("value", "")

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
                label_en=label_en,
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

    async def get_entity_labels(self, qids: list[str], language: str = "zh") -> dict[str, str]:
        """批量获取实体标签（轻量，仅 labels，避免拉全量 claims）

        Args:
            qids: Q ID 列表
            language: 优先语言

        Returns:
            {qid: label} 映射（缺失的实体不在结果中）
        """
        if not qids:
            return {}
        params = {
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "props": "labels",
            "languages": f"{language}|en",
            "format": "json",
        }
        try:
            response = await self._client.get(WIKIDATA_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()
            result = {}
            for qid, entity_data in data.get("entities", {}).items():
                labels = entity_data.get("labels", {})
                label = (
                    labels.get(language, {}).get("value")
                    or labels.get("en", {}).get("value")
                    or ""
                )
                if label:
                    result[qid] = label
            return result
        except httpx.HTTPError as e:
            print(f"Wikidata label batch error: {e}")
            return {}

    async def close(self):
        await self._client.aclose()

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


def _map_wikidata_type(qid: str, instance_of: list[str],
                       subclass_of: Optional[list[str]] = None,
                       description: str = "") -> str:
    """将 Wikidata 实体映射到 Logos 类型系统（P7 三层推断）

    ① P31 直映射（instance_of）
    ② P279 子类继承（subclass_of：实体自身 P279 + P31 目标类的父类）
    ③ 描述关键词兜底

    QID 语义均经 Wikidata API 校验（2026-08）：
    - Q11424=电影（旧映射误标 technology）、Q577=年（旧映射误标编程语言）、
      Q16521=生物分类单元（旧映射误标 event）、Q7889=电子游戏（旧映射误标 person）
    """
    # ① P31 直映射
    for inst in instance_of:
        if inst in _ENTITY_TYPE_MAP:
            return _ENTITY_TYPE_MAP[inst]
    # ② P279 子类继承（父类映射）
    for parent in (subclass_of or []):
        if parent in _ENTITY_TYPE_MAP:
            return _ENTITY_TYPE_MAP[parent]
    # ③ 描述关键词兜底
    if description:
        inferred = _type_from_description(description)
        if inferred != "entity":
            return inferred
    return "entity"


def _type_from_description(description: str) -> str:
    """描述关键词 → 类型（兜底层；无命中返回 entity）"""
    text = description or ""
    # 按优先级检查：person > organization > technology > event > concept
    if any(k in text for k in (
        "学家", "作家", "演员", "歌手", "运动员", "政治家", "企业家",
        "科学家", "创始人", "人物", "physicist", "scientist", "writer",
        "actor", "singer", "athlete", "politician", "founder", "human",
        "author", "musician", "artist", "professor",
    )):
        return "person"
    if any(k in text for k in (
        "公司", "企业", "组织", "机构", "大学", "学院", "政府", "政府机构",
        "研究所", "研究院", "乐队", "研究机构", "非营利组织",
        "company", "corporation", "organization", "university", "institute",
        "government", "research", "school",
    )):
        return "organization"
    if any(k in text for k in (
        "软件", "编程语言", "操作系统", "应用", "网站", "平台", "游戏",
        "数据库", "框架", "协议", "硬件",
        "software", "programming language", "operating system", "app",
        "website", "platform", "video game", "framework", "protocol",
    )):
        return "technology"
    if any(k in text for k in (
        "战争", "二战", "大战", "战役", "革命", "运动", "会议", "比赛", "节日", "事件",
        "war", "revolution", "battle", "conference", "competition",
        "festival", "event", "attack", "campaign",
    )):
        return "event"
    if any(k in text for k in (
        "概念", "理论", "主义", "学说", "思想", "学派", "学科", "哲学",
        "作品", "小说", "电影", "专辑", "歌曲",
        "concept", "theory", "ideology", "doctrine", "discipline",
        "philosophy", "novel", "film", "album", "song", "book", "genre",
    )):
        return "concept"
    return "entity"


# 实体类型映射表（P7 通用类型推断——QID 均经 Wikidata API 校验）
# person / organization / technology / event / concept / entity
_ENTITY_TYPE_MAP = {
    # person
    "Q5": "person",                     # 人类
    # organization
    "Q4830453": "organization",         # 企业
    "Q43229": "organization",           # 组织
    "Q3918": "organization",            # 大学
    "Q31855": "organization",           # 研究机构
    "Q215380": "organization",          # 乐队（音乐团体）
    # technology
    "Q7397": "technology",              # 软件
    "Q9143": "technology",              # 编程语言
    "Q9135": "technology",              # 操作系统
    "Q7889": "technology",              # 电子游戏（修复旧映射误判 person）
    "Q35127": "technology",             # 网站
    "Q620615": "technology",            # 移动应用
    # event
    "Q1656682": "event",                # 计划活动
    "Q1190554": "event",                # 事件（occurrence）
    "Q198": "event",                    # 战争
    # concept（学术概念 / 作品）
    "Q13442814": "concept",             # 学术文章
    "Q11424": "concept",                # 电影（修复旧映射误标 technology）
    "Q7725634": "concept",              # 文学作品
    "Q571": "concept",                  # 图书
    "Q2188189": "concept",              # 音乐作品
    "Q482994": "concept",               # 音乐专辑
    "Q134556": "concept",               # 单曲
    "Q188451": "concept",               # 音乐流派
    "Q15416": "concept",                # 电视节目
    "Q5398426": "concept",              # 电视系列节目
    "Q25118": "concept",                # 印刷品（百科文章）
    # 说明：Q16970（教堂建筑）/ Q11755880（居住建筑物）这类场所属性未纳入映射表，
    # 走描述关键词 / entity 兜底，避免误标组织。
}


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
        raw = await self.search_raw(query, language=language, limit=limit)
        if not raw:
            return []
        # 并发获取详情，避免 N+1 顺序请求导致搜索延迟被放大
        results = await asyncio.gather(
            *[
                self._get_entity_detail(item["id"], language)
                for item in raw
            ],
            return_exceptions=True,
        )
        return [r for r in results if isinstance(r, WikidataEntity)]

    async def search_raw(
        self, query: str, language: str = "zh", limit: int = 5
    ) -> list[dict]:
        """轻量搜索（仅 wbsearchentities，不拉详情）

        用于 QID 解析等只需要 id/label/aliases 的场景（单次 HTTP 调用）。
        返回 [{"id": QID, "label": str, "aliases": [str]}]
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
            return [
                {
                    "id": item["id"],
                    "label": item.get("label", ""),
                    "aliases": item.get("aliases", []),
                }
                for item in data.get("search", [])
            ]
        except httpx.HTTPError as e:
            print(f"Wikidata raw search error: {e}")
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

            # 提取实例（instance of P31）与子类（subclass of P279）以推断类型
            instance_of = []
            subclass_of = []
            claims = entity_data.get("claims", {})
            for claim in claims.get("P31", []):
                mainsnak = claim.get("mainsnak", {})
                if mainsnak.get("datatype") == "wikibase-item":
                    datavalue = mainsnak.get("datavalue", {})
                    value = datavalue.get("value", {})
                    if isinstance(value, dict):
                        instance_of.append(value.get("id", ""))
            for claim in claims.get("P279", []):
                mainsnak = claim.get("mainsnak", {})
                if mainsnak.get("datatype") == "wikibase-item":
                    datavalue = mainsnak.get("datavalue", {})
                    value = datavalue.get("value", {})
                    if isinstance(value, dict):
                        subclass_of.append(value.get("id", ""))

            # P7 三层类型推断：P31 直映射 → P279 继承 → 描述关键词
            # ① P31 直映射
            entity_type = _map_wikidata_type(qid, instance_of)
            # ② P279 继承（实体自身 P279 + P31 目标类的父类，一跳）
            if entity_type == "entity" and (instance_of or subclass_of):
                parents = list(subclass_of)
                if instance_of:
                    parents.extend(await self._get_subclass_of(instance_of[:10]))
                entity_type = _map_wikidata_type(qid, instance_of, subclass_of=parents)
            # ③ 描述关键词兜底
            if entity_type == "entity":
                entity_type = _map_wikidata_type(qid, instance_of, description=description)

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

    async def _get_subclass_of(self, class_qids: list[str]) -> list[str]:
        """批量获取类别 QID 的 P279 父类（P7 P279 继承推断用）

        仅拉取 claims，一次 HTTP 调用；仅返回可映射的父类 QID 列表。
        """
        if not class_qids:
            return []
        params = {
            "action": "wbgetentities",
            "ids": "|".join(class_qids[:50]),
            "props": "claims",
            "format": "json",
        }
        try:
            response = await self._client.get(WIKIDATA_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()
            parents: list[str] = []
            for entity_data in data.get("entities", {}).values():
                for claim in entity_data.get("claims", {}).get("P279", []):
                    mainsnak = claim.get("mainsnak", {})
                    if mainsnak.get("datatype") != "wikibase-item":
                        continue
                    value = mainsnak.get("datavalue", {}).get("value", {})
                    if isinstance(value, dict) and value.get("id"):
                        parents.append(value["id"])
            return parents
        except httpx.HTTPError as e:
            print(f"Wikidata subclass fetch error: {e}")
            return []

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

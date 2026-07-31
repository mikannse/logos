"""演化时间轴服务 - Timeline Service

从 Wikidata 带时间信息的声明构建演化时间轴：
- P569 出生 / P570 逝世（人物）
- P571 成立 / P577 出版 / P576 解散（组织、作品、事件）
- P793 重要事件（通过 P585 时间限定符提取年份）

结果按年份排序、去重，最多返回 10 个里程碑，并写入 Redis 缓存。
"""

import re
from typing import Optional

from app.repositories.wikidata_repo import WikidataRepository
from app.core.cache import CacheService

# 时间值解析：ISO 8601 格式 "+1879-03-14T00:00:00Z" / "-0445-03-14T00:00:00Z"
_TIME_RE = re.compile(r"^[+-]?(\d{4,})")

# 时间相关属性 → 里程碑标题（mainsnak 直接为时间值）
_TIME_PROP_TITLES = {
    "P569": "出生",
    "P570": "逝世",
    "P571": "成立",
    "P577": "出版",
    "P576": "解散",
    "P8556": "消亡",
}

# 实体型属性 + 时间限定符 → 里程碑（title 用实体标签）
# 限定符优先 P585（时间点），其次 P580（开始时间）、P582（结束时间）
_ENTITY_QUALIFIER_PROPS = {
    "P793": "P585",   # 重要事件 + 时间点
    "P166": "P585",   # 获得奖项 + 获奖时间
    "P69": "P580",    # 就读学校 + 开始时间
    "P108": "P580",   # 雇主 + 开始时间
    "P551": "P580",   # 居住地 + 开始时间
}

# 限定符候选：优先 P585，其次 P580，最后 P582
_QUALIFIER_CANDIDATES = ("P585", "P580", "P582")

# 里程碑上限
_MAX_MILESTONES = 10


def _extract_time_year(value: object) -> Optional[int]:
    """从时间 datavalue 提取年份（支持 dict 或 time 字符串）"""
    if isinstance(value, dict):
        value = value.get("time", "")
    if not isinstance(value, str):
        return None
    m = _TIME_RE.match(value)
    if not m:
        return None
    return int(m.group(1))


def _extract_mainsnak_year(claim: dict) -> Optional[int]:
    """从 claim 的 mainsnak（time 类型）提取年份"""
    mainsnak = claim.get("mainsnak", {})
    if mainsnak.get("datatype") != "time":
        return None
    return _extract_time_year(mainsnak.get("datavalue", {}).get("value", ""))


def _extract_qualifier_year(claim: dict, qualifier_prop: str) -> Optional[int]:
    """从 claim 的限定符中提取某属性的时间年份（如 P793 的 P585）"""
    for q in claim.get("qualifiers", {}).get(qualifier_prop, []):
        if q.get("datatype") != "time":
            continue
        year = _extract_time_year(q.get("datavalue", {}).get("value", ""))
        if year is not None:
            return year
    return None


def _extract_any_qualifier_year(claim: dict) -> Optional[int]:
    """按优先级从 P585 / P580 / P582 限定符中提取年份"""
    for prop in _QUALIFIER_CANDIDATES:
        year = _extract_qualifier_year(claim, prop)
        if year is not None:
            return year
    return None


def _extract_entity_target(claim: dict) -> Optional[str]:
    """从 claim 的 mainsnak 提取 wikibase-item 目标 QID"""
    mainsnak = claim.get("mainsnak", {})
    if mainsnak.get("datatype") != "wikibase-item":
        return None
    value = mainsnak.get("datavalue", {}).get("value", {})
    if not isinstance(value, dict):
        return None
    return value.get("id", "") or None


def _make_milestone(
    year: int,
    title: str,
    name: str,
    confidence: float = 0.8,
    lifecycle: bool = False,
) -> dict:
    """构造里程碑 dict

    lifecycle 标记是否属生命周期事件（出生/逝世/成立等），
    用于保证关键节点不被教育/任职等记录挤出上限。
    """
    return {
        "year": year,
        "title": title[:50],
        "description": f"{name} · {title}",
        "source_url": "",
        "confidence": confidence,
        "_lifecycle": lifecycle,
    }


class TimelineService:
    """演化时间轴业务逻辑"""

    def __init__(
        self,
        wikidata: Optional[WikidataRepository] = None,
        cache: Optional[CacheService] = None,
    ):
        self.wikidata = wikidata or WikidataRepository()
        self.cache = cache or CacheService()

    async def get_timeline(self, noun_id: str) -> dict:
        """获取指定名词的演化时间轴

        从 Wikidata 声明提取带日期的事实，按年份排序，
        返回最多 10 个关键里程碑。
        """
        cache_key = f"timeline:{noun_id}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached

        entity = await self.wikidata.get_entity_by_qid(noun_id)
        if not entity:
            result = {"noun_id": noun_id, "milestones": [], "total": 0}
            await self.cache.set(cache_key, result, ttl=3600)
            return result

        claims = entity.claims or {}
        name = entity.label or noun_id
        milestones: list[dict] = []

        # 直接时间属性（出生/逝世/成立/出版/解散等）—— 生命周期事件
        for prop, title in _TIME_PROP_TITLES.items():
            for claim in claims.get(prop, []):
                year = _extract_mainsnak_year(claim)
                if year is not None:
                    milestones.append(_make_milestone(year, title, name, lifecycle=True))

        # 实体型属性 + 时间限定符（重要事件/获奖/教育/任职等）
        entity_qids: list[str] = []
        entity_years: dict[str, int] = {}
        for prop in _ENTITY_QUALIFIER_PROPS:
            for claim in claims.get(prop, []):
                qid = _extract_entity_target(claim)
                if not qid:
                    continue
                year = _extract_any_qualifier_year(claim)
                if year is not None and qid not in entity_years:
                    entity_qids.append(qid)
                    entity_years[qid] = year

        if entity_qids:
            labels = await self.wikidata.get_entity_labels(entity_qids)
            for qid in entity_qids:
                label = labels.get(qid, "")
                if not label:
                    continue
                milestones.append(_make_milestone(entity_years[qid], label, name))

        # 优先级：生命周期事件（出生/逝世/成立/解散等）全保留，
        # 实体里程碑（教育/任职/获奖）按年份补足剩余名额。
        # 避免 "1955 逝世" 这类关键节点被大量教育记录挤出时间轴。
        lifecycle = [m for m in milestones if m["_lifecycle"]]
        entity_m = [m for m in milestones if not m["_lifecycle"]]
        remaining = _MAX_MILESTONES - len(lifecycle)
        if remaining < 0:
            remaining = 0

        seen: set[tuple] = set()
        selected: list[dict] = []

        def _dedup_add(item: dict) -> None:
            key = (item["year"], item["title"])
            if key not in seen:
                seen.add(key)
                selected.append(item)

        # 先加生命周期，再加实体（实体按年份排序，取最早的补位）
        for m in sorted(lifecycle, key=lambda x: x["year"]):
            _dedup_add(m)
        for m in sorted(entity_m, key=lambda x: x["year"])[:remaining]:
            _dedup_add(m)

        # 最终按年份排序，剥离内部标记字段
        selected.sort(key=lambda x: x["year"])
        selected = [{k: v for k, v in m.items() if not k.startswith("_")} for m in selected]

        result = {"noun_id": noun_id, "milestones": selected, "total": len(selected)}
        await self.cache.set(cache_key, result, ttl=3600)
        return result

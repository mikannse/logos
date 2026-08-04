import asyncio
import re
from typing import Any, Optional

from fastapi import APIRouter, Query

from app.models.graph import GraphResponse, GraphNode, GraphEdge
from app.repositories.neo4j_repo import Neo4jRepository
from app.repositories.wikidata_repo import WikidataRepository, WikidataEntity
from app.core.cache import CacheService
from app.core.neo4j_client import Neo4jClient
from app.ai.web_search import WebSearch
from app.ai.extractor import EntityExtractor
from app.services.graph_service import merge_llm_entities

router = APIRouter(tags=["graph"])

_neo4j_repo: Neo4jRepository | None = None
_wikidata_repo: WikidataRepository | None = None
_cache: CacheService | None = None

# ---- Wikidata 关系属性白名单（P4：收敛去噪 + P8：可映射属性） ----

# 强关联属性（P4 收敛白名单 + 人物核心关系扩展）——不含 P31/P279 分类属性，
# 也不含 P106（职业）：职业是"分类/概念"性质的值（如"革命家""政治人物"），
# 作为图谱边信息量≈0，且目标易被误判为 person/event 实例（修复 4b 移除）。
# 新增 P1327（合作者）/ P69（教育）/ P108（雇主）/ P102（政党）等人物常见属性，
# 否则马克思的恩格斯（P1327）、柏林大学（P69）等核心关联会被白名单过滤掉。
_STRONG_RELATION_PROPS = [
    "P800", "P1416", "P463", "P910", "P127", "P355", "P1830",
    "P1327", "P69", "P108", "P102",
]
# P8 扩展可映射属性（追加，提供更多语义关系；含家庭/地理/研究领域等中性关联）
_EXTRA_RELATION_PROPS = [
    "P50", "P144", "P2860", "P737", "P361",
    "P26", "P19", "P20", "P937", "P101",
]
# 分类属性：P31（instance of）/ P279（subclass of）目标降级为 category 节点
_CATEGORY_PROPS = ["P31", "P279"]

# P8: Wikidata 属性 → Logos 语义关系类型映射
_RELATION_TYPE_MAP = {
    "P800": "creation", "P50": "creation", "P144": "creation",        # 创作/作品关联
    "P106": "affiliation", "P1416": "affiliation", "P463": "affiliation",  # 隶属
    "P127": "affiliation", "P355": "affiliation", "P361": "affiliation",
    "P69": "affiliation", "P108": "affiliation", "P102": "affiliation",  # 教育/雇主/政党
    "P1327": "collaboration",                                         # 合作者
    "P2860": "influence", "P737": "influence",                        # 影响
    "P910": "other", "P1830": "other", "P279": "other",               # 其他/分类
    "P26": "other", "P19": "other", "P20": "other",                   # 配偶/出生地/死亡地
    "P937": "other", "P101": "other",                                 # 工作地/研究领域
}

# Wikidata 属性 → 中文标签（边 evidence 的关系语义描述，如"合作者：恩格斯"）
_PROP_LABEL_ZH = {
    "P800": "著名作品", "P50": "作者", "P144": "改编自",
    "P1327": "合作者", "P737": "受影响于", "P2860": "引用",
    "P106": "职业", "P1416": "隶属", "P463": "成员",
    "P127": "拥有者", "P355": "子公司", "P361": "所属部分",
    "P69": "就读学校", "P108": "雇主", "P102": "政党",
    "P910": "主分类", "P1830": "拥有物",
    "P26": "配偶", "P19": "出生地", "P20": "逝世地",
    "P937": "工作地", "P101": "研究领域",
    "P31": "实例", "P279": "子类",
}

# 提取顺序：语义类型优先的属性在前（去重时先到先得），分类属性垫底
# （不含 P106 职业：低信息量的概念值，见 _STRONG_RELATION_PROPS 注释）
_RELATION_PROPS = [
    "P800", "P50", "P144",
    "P1327",                                   # 合作者（collaboration）
    "P737", "P2860",                            # 影响
    "P1416", "P463", "P127", "P355", "P361",
    "P69", "P108", "P102",                      # 教育/雇主/政党（affiliation）
    "P910", "P1830", "P26", "P19", "P20", "P937", "P101",
    "P31", "P279",
]

_RELATED_LIMIT = 15

# P4: 节点类型优先级（越小越优先）——截断时低优先级类型被挤出
_NODE_TYPE_PRIORITY = {
    "person": 0,
    "event": 1,
    "technology": 2,
    "organization": 3,
    "concept": 4,
    "entity": 5,
    "category": 6,
}

# 中心/强关联/分类节点 relevance 约定
_CENTER_RELEVANCE = 1.0
_STRONG_RELEVANCE = 0.7
_CATEGORY_RELEVANCE = 0.2

# V3a: 多跳 relevance 跳衰减（hop≥2 的边 relevance = 衰减基数 × 属性制基数）
# hop-1 保留 prop 制（强 0.7 / 分类 0.2，见 _edge_relevance_for_prop）；
# hop≥2 在 prop 制基础上按跳衰减，避免分类边在 hop≥2 升到 0.7。
_HOP_RELEVANCE_DECAY = {2: 0.5, 3: 0.3}
# V3a: hop≥2 仅展开强关系属性（决策②）——丢弃 P31/P279 分类与 P19/P20/P26/P937/P101
# 地理/家庭/领域弱属性，防止 hop-2/3 堆满 category 噪音节点
_HOP_STRONG_RELATION_PROPS = list(_STRONG_RELATION_PROPS)

# P5: 正常搜索触发 Web 丰富的强相关节点下限（<6 时触发）
_ENRICH_TRIGGER_THRESHOLD = 6
# Web 丰富结果缓存 TTL（1h）
_ENRICH_CACHE_TTL = 3600

# Neo4j 图谱缓存有效期（7 天）：过期后视为未命中，从 Wikidata 重建。
# 修复 3：此前 Neo4j 图谱无失效机制——类型映射/白名单等逻辑改进
# 及 Wikidata 上游更新对已缓存实体永久不生效，且部分写入的残缺图谱
# 会被无限命中。重建前删除中心实体的旧出边（见 build_graph_from_wikidata）。
_GRAPH_NEO4J_TTL_MS = 7 * 24 * 3600 * 1000


def _edge_type_for_prop(prop: str) -> str:
    """Wikidata 属性 → 语义关系类型（未知/未映射 → other）"""
    return _RELATION_TYPE_MAP.get(prop, "other")


def get_neo4j_repo() -> Neo4jRepository:
    global _neo4j_repo
    if _neo4j_repo is None:
        client = Neo4jClient()
        _neo4j_repo = Neo4jRepository(client)
    return _neo4j_repo


def get_wikidata_repo() -> WikidataRepository:
    global _wikidata_repo
    if _wikidata_repo is None:
        _wikidata_repo = WikidataRepository()
    return _wikidata_repo


def get_cache() -> CacheService:
    global _cache
    if _cache is None:
        _cache = CacheService()
    return _cache


def _entity_to_node(entity_id: str | None, label: str | None, entity_type: str | None,
                     description: str | None, has_sitelink: bool,
                     relevance: float = 0.0) -> dict:
    """将 Wikidata 实体转为 Neo4j upsert dict（统一 shape，复用 search_service 契约）"""
    name = label or entity_id or ""
    return {
        "id": entity_id,
        "name": name,
        "label": name,  # GraphNode 使用 label 字段
        "type": entity_type or "entity",
        "confidence": 0.9 if has_sitelink else 0.6,
        "relevance": relevance,
        "summary": description or "",
    }


def _extract_related_qids(claims: dict, exclude_id: str,
                          props: Optional[list[str]] = None) -> list[tuple[str, str]]:
    """从 claims 中提取 wikibase-item 类型的相关 QID，返回 [(qid, prop)]

    去重但保序：同一 qid 首次出现的属性优先（_RELATION_PROPS 语义类型在前）。

    V3a: props 参数用于 hop≥2 收敛白名单（_HOP_STRONG_RELATION_PROPS），
    丢弃分类/地理/家庭弱属性，防多跳堆满噪音。
    """
    prop_order = props if props is not None else _RELATION_PROPS
    seen: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for prop_id in prop_order:
        for claim in claims.get(prop_id, []):
            mainsnak = claim.get("mainsnak", {})
            if mainsnak.get("datatype") != "wikibase-item":
                continue
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            if not isinstance(value, dict):
                continue
            qid = value.get("id", "")
            if qid and qid != exclude_id and qid not in seen:
                seen.add(qid)
                pairs.append((qid, prop_id))
    return pairs


def _type_priority_sort_key(node: dict) -> tuple:
    """节点类型优先级排序键：类型优先级优先，其次是否有站点链接（sitelink 优先）"""
    priority = _NODE_TYPE_PRIORITY.get(node.get("type"), 5)  # 未知类型按 entity 档
    has_sitelink = node.get("confidence", 0) >= 0.9
    return (priority, 0 if has_sitelink else 1)


def _edge_relevance_for_prop(prop: str) -> float:
    """边 relevance：分类属性弱关联，强关联属性 0.7"""
    if prop in _CATEGORY_PROPS:
        return _CATEGORY_RELEVANCE
    return _STRONG_RELEVANCE


def _edge_confidence(prop: str, target: WikidataEntity) -> float:
    """边置信度分级（替代旧的 0.7 硬编码）

    分类属性（P31/P279）证据弱 → 0.5；
    目标实体有 Wikipedia 站点链接（声明可交叉验证）→ 0.85；
    无站点链接 → 0.6。
    """
    if prop in _CATEGORY_PROPS:
        return 0.5
    return 0.85 if (target.sitelink_zh or target.sitelink_en) else 0.6


def _edge_evidence(prop: str, target: WikidataEntity) -> str:
    """边证据：关系级真实描述（替代旧的中心实体描述占位符）

    如 "合作者：弗里德里希·恩格斯"——声明来自 Wikidata 中心实体页面的该属性，
    evidence 需让用户理解这条边为何存在，而非重复中心实体简介。
    """
    prop_label = _PROP_LABEL_ZH.get(prop, "关联")
    return f"{prop_label}：{target.label or target.id}"


# ---- V2c: 节点年份提取（时间轴-图谱联动的数据基础） ----

# 时间值解析：ISO 8601 "+1879-03-14T00:00:00Z" / "-0445-03-14T00:00:00Z"
# 捕获符号 + 年份（公元前用负年，如 -0445 → -445）
_TIME_YEAR_RE = re.compile(r"^([+-])(\d{1,6})")
# 锚点年属性（起始/存在）与结束年属性（逝世/解散/消亡）
_ANCHOR_YEAR_PROPS = ("P569", "P571", "P577", "P585")
_END_YEAR_PROPS = ("P570", "P576", "P8556")


def _extract_claim_year(claim: dict) -> Optional[int]:
    """从单条 claim 的 mainsnak（time 类型）提取年份"""
    mainsnak = claim.get("mainsnak", {})
    if mainsnak.get("datatype") != "time":
        return None
    value = mainsnak.get("datavalue", {}).get("value", "")
    # 兼容两种 shape：time 字符串 或 {"time": ...}（Wikidata raw 结构）
    if isinstance(value, dict):
        value = value.get("time", "")
    if not isinstance(value, str):
        return None
    m = _TIME_YEAR_RE.match(value)
    if not m:
        return None
    sign = -1 if m.group(1) == "-" else 1
    return sign * int(m.group(2))


def _extract_node_year(claims: dict) -> tuple[Optional[int], Optional[int]]:
    """从实体 claims 提取 (year, year_end) 年段

    V2c：时间轴-图谱联动需要每个节点"活跃于某年"的判定。
    - 锚点年：P569 出生 / P571 成立 / P577 出版 / P585 事件时间点（取最早）
    - 结束年：P570 逝世 / P576 解散 / P8556 消亡（取最早）

    Returns:
        (year, year_end)；无时间属性的返回 (None, None)
    """
    year: Optional[int] = None
    year_end: Optional[int] = None
    if not claims:
        return year, year_end
    for prop in _ANCHOR_YEAR_PROPS:
        for claim in claims.get(prop, []):
            y = _extract_claim_year(claim)
            if y is not None and (year is None or y < year):
                year = y
    for prop in _END_YEAR_PROPS:
        for claim in claims.get(prop, []):
            y = _extract_claim_year(claim)
            if y is not None and (year_end is None or y < year_end):
                year_end = y
    return year, year_end


# ---- P5: 正常搜索触发 Web 内容丰富（同步合并） ----

_web_search_instance: WebSearch | None = None
_extractor_instance: EntityExtractor | None = None


def get_web_search() -> WebSearch:
    global _web_search_instance
    if _web_search_instance is None:
        _web_search_instance = WebSearch()
    return _web_search_instance


def get_extractor() -> EntityExtractor:
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = EntityExtractor()
    return _extractor_instance


def _should_enrich(nodes: list[dict], edges: list[dict], center_id: str,
                   depth: int = 1) -> bool:
    """Web 丰富触发判定：语义多样性不足时触发（替代旧"强相关节点数 <6"）

    旧规则只对"图谱薄"的实体触发，对 Wikidata 数据丰富的实体（人物/组织等）
    反而关闭了 Web 丰富通道——而这类实体的关键信息恰好在非结构化文本里
    （合作者、史实、所属运动等），导致图谱丰富度不足（如马克思缺核心关联）。

    新规则任一命中即触发：
    - 关联节点过少（< _ENRICH_TRIGGER_THRESHOLD）→ 图谱薄
    - 关联节点类型单一（< 3 种）→ 内容单调（如全 entity）
    - 语义边类型 ≤ 1 种 → 关系单调（如全 related_to）

    V3a：只统计 hop-1 子图（hop 缺省视为 1，兼容单跳调用）——多跳后 related
    节点数必然 ≥6，若统计全量会恒不触发，Web 丰富通道在多跳图上静默关闭。

    成本控制：丰富结果缓存 web_enrich:{qid} 1h，同一实体每小时至多一次 LLM 调用。
    """
    related = [
        n for n in nodes
        if n.get("id") != center_id
        and n.get("type") != "category"
        and (n.get("hop", 1) == 1)  # 仅 hop-1 参与判定（V3a）
    ]
    if len(related) < _ENRICH_TRIGGER_THRESHOLD:
        return True
    distinct_types = len({n.get("type", "entity") for n in related})
    if distinct_types < 3:
        return True
    hop1_edges = [e for e in edges if e.get("hop", 1) == 1]
    distinct_edge_types = len({e.get("type", "other") for e in hop1_edges})
    if distinct_edge_types <= 1:
        return True
    return False


async def _enrich_from_web(
    center_id: str,
    center_entity,
    wikidata: WikidataRepository,
    neo4j: Neo4jRepository,
    web_search: WebSearch,
    extractor: EntityExtractor,
    cache: Optional[CacheService] = None,
    existing_node_ids: Optional[set] = None,
    existing_edge_keys: Optional[set] = None,
    existing_relevance: Optional[dict] = None,
) -> dict:
    """Web Search + LLM 丰富图谱（同步合并）

    1. 命中 web_enrich:{qid} 缓存（1h）直接返回
    2. web_search.search_and_extract(中心名, entity_type=中心实体类型) → 无摘要则返回空
    3. extractor.extract_from_text(summary, focus_entity=中心名)
    4. merge_llm_entities：relevance>=0.5 过滤 + QID 统一解析合并
    5. 缓存丰富结果 1h

    existing_node_ids / existing_edge_keys：基础图谱（Wikidata 优先）已有
    的节点/边，合并时跳过写库，保证「同 ID 节点 Wikidata 优先」契约。
    existing_relevance：基础图谱节点相关度，供触及它们的边计算真实值。

    LLM 未配置 / 任意一步失败 → 静默退化，返回空丰富（基础图谱不受影响）。
    """
    cache_key = f"web_enrich:{center_id}"
    if cache is not None:
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

    center_name = center_entity.label or center_id
    empty = {"nodes": [], "edges": []}
    try:
        search_result = await web_search.search_and_extract(
            center_name, entity_type=center_entity.type
        )
        if not search_result or not search_result.get("summary"):
            return empty

        extraction = await extractor.extract_from_text(
            search_result["summary"],
            focus_entity=center_name,
        )
        if extraction is None:
            return empty

        center_names = [center_name]
        if center_entity.label_en:
            center_names.append(center_entity.label_en)

        merged = await merge_llm_entities(
            extraction,
            center_id,
            center_names,
            wikidata,
            neo4j,
            cache=cache,
            center_entity_type=center_entity.type,
            existing_node_ids=existing_node_ids,
            existing_edge_keys=existing_edge_keys,
            existing_relevance=existing_relevance,
        )
    except Exception:
        # 丰富是增强通道：任何失败都不得拖垮基础图谱
        return empty

    # P7 Part B：中心规则类型为 entity 且 LLM 判定出类型 → 覆盖并写回 Neo4j
    focus_type = merged.get("focus_entity_type")
    if focus_type is not None:
        try:
            await neo4j.upsert_entity({
                "id": center_id,
                "name": center_entity.label,
                "type": focus_type,
                "confidence": 0.9 if (center_entity.sitelink_zh or center_entity.sitelink_en) else 0.6,
                "summary": center_entity.description,
            })
        except Exception:
            pass
        merged["center_type"] = focus_type

    if cache is not None:
        try:
            await cache.set(cache_key, merged, ttl=_ENRICH_CACHE_TTL)
        except Exception:
            pass
    return merged


def _build_response(center: str, data: dict, depth: int) -> GraphResponse:
    """统一的 GraphResponse 构造"""
    nodes = []
    for n in data.get("nodes", []):
        n = dict(n)
        # 兼容旧缓存：旧格式只有 name 键，无 label
        if "label" not in n:
            n["label"] = n.pop("name", n.get("id", ""))
        nodes.append(GraphNode(**n))
    return GraphResponse(
        center=center,
        nodes=nodes,
        edges=[GraphEdge(**e) for e in data.get("edges", [])],
        depth=depth,
        has_more=data.get("has_more", False),
    )


@router.get("/nouns/{noun_id}/graph")
async def get_graph(
    noun_id: str,
    depth: int = Query(default=1, ge=1, le=3, description="图谱深度（跳数）"),
):
    """关系图谱（分层加载）

    优先从 Neo4j 读取缓存，未命中则从 Wikidata 查询并缓存。
    """
    repo = get_neo4j_repo()
    cache = get_cache()
    # V2c: 缓存键升级 v2——旧缓存无 year/year_end/hop 字段，发布时间一次性失效
    # 避免"有的实体联动正常、有的完全无反应"（旧 Redis 缓存无年段数据）
    cache_key = f"graph:{noun_id}:depth{depth}:v2"

    # Try cache — 注意区分 "未命中" 与 "缓存了空结果"
    try:
        cached = await cache.get(cache_key)
        if cached is not None:
            # 即使 nodes 为空也视为有效缓存（避免重复查询不存在 / 无关系的实体）
            return _build_response(noun_id, cached, depth)
    except Exception:
        pass  # 缓存不可用时降级 — 不影响主逻辑

    # Try Neo4j — 含新鲜度检查：无 graphBuiltAt（旧数据）或超期 → 视为未命中，
    # 走 Wikidata 重建，避免陈旧图谱永久冻结（修复 3）
    try:
        result = await repo.get_graph(noun_id, depth, max_age_ms=_GRAPH_NEO4J_TTL_MS)
        nodes = result.get("nodes", [])
        if nodes:
            edges = result.get("edges", [])
            data = {"nodes": nodes, "edges": edges, "has_more": result.get("has_more", False)}
            await cache.set(cache_key, data, ttl=600)
            return _build_response(noun_id, data, depth)
    except Exception:
        pass

    # Fallback: build from Wikidata（可能含 Web 丰富）
    wikidata = get_wikidata_repo()
    try:
        graph_data = await build_graph_from_wikidata(noun_id, wikidata, repo, depth)
        # 缓存结果 — 即使空也缓存（短期 TTL 避免刷 Wikidata）；
        # 非空（可能含 Web 丰富）缓存 1h，避免重复触发付费 LLM 管道
        ttl = 60 if not graph_data.get("nodes") else _ENRICH_CACHE_TTL
        await cache.set(cache_key, graph_data, ttl=ttl)
        return _build_response(noun_id, graph_data, depth)
    except Exception:
        return GraphResponse(center=noun_id, depth=depth, has_more=False)


async def build_graph_from_wikidata(
    entity_id: str,
    wikidata: WikidataRepository,
    neo4j: Neo4jRepository,
    depth: int = 1,
    web_search: Optional[WebSearch] = None,
    extractor: Optional[EntityExtractor] = None,
    cache: Optional[CacheService] = None,
) -> dict:
    """从 Wikidata 构建基础图谱（多跳）+ 可选 Web 丰富

    V3a：由单跳扩展为递归 depth 1→3 多跳构建。
    - hop-1 展开 _RELATION_PROPS（含分类），hop≥2 仅展开 _HOP_STRONG_RELATION_PROPS
      （决策②：丢弃分类/地理/家庭弱属性，防多跳堆满噪音）
    - 每跳 ≤ _RELATED_LIMIT 节点，已访问集合防环
    - relevance 随跳衰减：hop-1 保留 prop 制（强 0.7 / 分类 0.2），hop≥2 乘衰减系数
    - 节点/边写库（hop 标注），重建前清理子图内部陈旧边

    去噪与排序（P4）：
    - P31/P279 分类目标保留但降级为 type:"category" + relevance:0.2
    - 关联节点按类型优先级排序后截断 _RELATED_LIMIT

    Web 丰富（P5，仅 hop-1 判定）：
    - hop-1 子图语义多样性不足时，同步触发 Web Search + LLM 提取合并（缓存 1h）
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_ids: set[str] = set()  # 防环
    seen_edge_keys: set[tuple] = set()

    center_entity = await wikidata.get_entity_by_qid(entity_id)

    if not center_entity:
        return {"nodes": [], "edges": [], "has_more": False}

    # 重建前清理中心陈旧出边（修复 3）：删除上次构建残留的旧关系，
    # 避免旧逻辑数据（占位符 evidence、过期类型/白名单）与新构建累积混淆，
    # 同时让"部分写入中断"的图谱在下次触发重建时自愈。
    # V3a: 多跳内部边（hop1→hop2、hop2→hop3）由下方遍历时的逐节点清理处理
    #（每次为该节点写边前先 delete_outgoing_relations，保证陈旧边清干净）。
    await neo4j.delete_outgoing_relations(entity_id)

    has_sitelink = bool(center_entity.sitelink_zh or center_entity.sitelink_en)
    center_year, center_year_end = _extract_node_year(center_entity.claims)

    # Center node（复用统一 shape，使用 'name' 键匹配 neo4j upsert 契约）
    center_node = _entity_to_node(
        entity_id, center_entity.label, center_entity.type,
        center_entity.description, has_sitelink,
        relevance=_CENTER_RELEVANCE,
    )
    center_node["year"] = center_year
    center_node["year_end"] = center_year_end
    center_node["hop"] = 0
    nodes.append(center_node)
    seen_ids.add(entity_id)
    await neo4j.upsert_entity(center_node)

    # ---- 递归多跳构建 ----
    # frontier: 当前跳的候选 (source_id, qid, prop, source_node, source_relevance)
    frontier: list[tuple] = []
    related_pairs = _extract_related_qids(center_entity.claims, entity_id)
    frontier = [(entity_id, qid, prop) for qid, prop in related_pairs]
    has_more = False
    # V3a: 已清理过出边的源节点集合——每次为该节点写边前先删陈旧出边，
    # 保证前次更深度构建写入的 hopN→hopN+1 内部边被清干净（B1 修复）。
    # 中心出边已在构建前清理，故只需处理 hop≥2 的非中心源节点。
    stale_cleaned: set[str] = set()

    for hop in range(1, depth + 1):
        if not frontier:
            break
        # 本跳属性白名单：hop-1 全量，hop≥2 收敛为强关系属性（决策②）
        props = _RELATION_PROPS if hop == 1 else _HOP_STRONG_RELATION_PROPS
        # 过滤：本跳候选若已在 seen 跳过；hop≥2 重筛属性
        hop_candidates: list[tuple[str, str, str]] = []
        for src_id, qid, prop in frontier:
            if qid in seen_ids:
                continue
            if hop >= 2 and prop not in props:
                continue
            hop_candidates.append((src_id, qid, prop))

        if not hop_candidates:
            frontier = []
            continue

        truncated = len(hop_candidates) > _RELATED_LIMIT
        # 多取 2x 候选再排序（类型优先级），保证 person 等不被低优先级淹没后截断
        fetch_candidates = hop_candidates[:_RELATED_LIMIT * 2]

        # 批量拉取本跳候选实体详情（并发，Semaphore 限流）
        qids_to_fetch = list(dict.fromkeys(qid for _, qid, _ in fetch_candidates))
        batch = await wikidata.get_entities_by_qids(qids_to_fetch)
        # 批量接口失败/不支持时降级为逐个拉取（向后兼容 Fake/旧实现）
        if not batch and len(qids_to_fetch) > 1:
            fetched = await asyncio.gather(
                *[wikidata.get_entity_by_qid(qid) for qid in qids_to_fetch],
                return_exceptions=True,
            )
            batch = {
                qid: ent for qid, ent in zip(qids_to_fetch, fetched)
                if isinstance(ent, WikidataEntity)
            }

        # 组装本跳节点（类型优先级排序后截断）
        hop_nodes: list[tuple[dict, str, str, WikidataEntity]] = []
        for src_id, qid, prop in fetch_candidates:
            related = batch.get(qid)
            if not isinstance(related, WikidataEntity):
                continue
            is_category = prop in _CATEGORY_PROPS
            node_type = "category" if is_category else (related.type or "entity")
            node_relevance = _CATEGORY_RELEVANCE if is_category else _STRONG_RELEVANCE
            if hop >= 2:
                node_relevance = node_relevance * _HOP_RELEVANCE_DECAY.get(hop, 0.3)

            node = _entity_to_node(
                qid, related.label, node_type,
                related.description,
                bool(related.sitelink_zh or related.sitelink_en),
                relevance=node_relevance,
            )
            year, year_end = _extract_node_year(related.claims)
            node["year"] = year
            node["year_end"] = year_end
            node["hop"] = hop
            hop_nodes.append((node, src_id, qid, prop, related))

        # 按类型优先级排序后截断（person > event > ... > category）
        hop_nodes.sort(key=lambda item: _type_priority_sort_key(item[0]))
        hop_nodes = hop_nodes[:_RELATED_LIMIT]

        next_frontier: list[tuple] = []
        for node, src_id, qid, prop, related in hop_nodes:
            if qid in seen_ids:
                continue
            if src_id != entity_id and src_id not in stale_cleaned:
                await neo4j.delete_outgoing_relations(src_id)
                stale_cleaned.add(src_id)
            nodes.append(node)
            seen_ids.add(qid)
            await neo4j.upsert_entity(node)

            edge_relevance = _edge_relevance_for_prop(prop)
            if hop >= 2:
                edge_relevance = edge_relevance * _HOP_RELEVANCE_DECAY.get(hop, 0.3)
            edge_type = _edge_type_for_prop(prop)
            edge_confidence = _edge_confidence(prop, related)
            edge_key = (src_id, qid, edge_type)
            if edge_key not in seen_edge_keys:
                seen_edge_keys.add(edge_key)
                edge = {
                    "source": src_id,
                    "target": qid,
                    "type": edge_type,
                    "confidence": edge_confidence,
                    "relevance": edge_relevance,
                    # 来源指向目标实体的 Wikipedia 页面（用户可验证该端点），中心页面兜底
                    "source_url": (
                        related.sitelink_zh or related.sitelink_en
                        or center_entity.sitelink_zh or center_entity.sitelink_en or ""
                    ),
                    "evidence": _edge_evidence(prop, related),
                    "hop": hop,
                }
                edges.append(edge)
                # write edge to Neo4j（UPPER_SNAKE 存储，读取时归一小写语义类型）
                await neo4j.upsert_relation(
                    source_id=src_id,
                    target_id=qid,
                    rel_type=edge_type.upper(),
                    confidence=edge_confidence,
                    source_url=edge["source_url"],
                    evidence=edge["evidence"],
                    relevance=edge_relevance,
                    hop=hop,
                )

            # 下一跳候选：hop<depth 时从本跳节点的 claims 收集（仅强关系属性）
            if hop < depth:
                for next_qid, next_prop in _extract_related_qids(
                    related.claims, qid, props=_HOP_STRONG_RELATION_PROPS
                ):
                    next_frontier.append((qid, next_qid, next_prop))

        frontier = next_frontier

        # 本跳有截断 → has_more 置位（还有更多候选未展开）
        if truncated and depth > hop:
            has_more = True

    # P5: 语义多样性不足时触发 Web Search + LLM 丰富（同步合并，仅 hop-1 判定）
    if depth >= 1 and _should_enrich(nodes, edges, entity_id, depth=depth):
        web = web_search or get_web_search()
        ext = extractor or get_extractor()
        enrich_cache = cache if cache is not None else get_cache()
        # Wikidata 优先契约：基础图谱已有节点/边不覆盖写库
        base_node_ids = {n["id"] for n in nodes}
        base_edge_keys = {(e["source"], e["target"], e["type"]) for e in edges}
        base_relevance = {n["id"]: n.get("relevance", 0.0) for n in nodes}
        enrich = await _enrich_from_web(
            entity_id, center_entity, wikidata, neo4j, web, ext, enrich_cache,
            existing_node_ids=base_node_ids,
            existing_edge_keys=base_edge_keys,
            existing_relevance=base_relevance,
        )
        if enrich:
            # 合并丰富节点/边（去重：同 ID 节点 Wikidata 优先）
            enrich_node_ids = {n["id"] for n in nodes}
            center_type_override = enrich.get("center_type")
            if center_type_override:
                for n in nodes:
                    if n["id"] == entity_id:
                        n["type"] = center_type_override
            for n in enrich.get("nodes", []):
                if n["id"] not in enrich_node_ids:
                    n.setdefault("hop", 1)
                    nodes.append(n)
                    enrich_node_ids.add(n["id"])
            seen_edges = {(e["source"], e["target"], e["type"]) for e in edges}
            for e in enrich.get("edges", []):
                key = (e["source"], e["target"], e["type"])
                if key not in seen_edges:
                    e.setdefault("hop", 1)
                    edges.append(e)
                    seen_edges.add(key)

    # 全部 upsert 成功后再标记构建完成时间与深度（修复 3 + V3a 深度感知新鲜度）；
    # 构建中途异常则不标记，get_graph 下次视为未命中并重新构建。
    await neo4j.mark_graph_built(entity_id, depth=depth)
    return {"nodes": nodes, "edges": edges, "has_more": has_more}

"""搜索服务 - Search Service

搜索策略：
1. 精确匹配 Neo4j 缓存
2. 未命中 → Wikidata API 搜索
3. 结果写入 Neo4j + Redis 缓存
4. 跨语言对齐：同一 Wikidata Q ID 合并不同语言标签
5. 消歧判断：如果返回多个不同实体，标记 needs_disambiguation=True
"""

from typing import Optional

from app.repositories.wikidata_repo import WikidataRepository, WikidataEntity
from app.repositories.neo4j_repo import Neo4jRepository
from app.core.cache import CacheService

# Wikidata 实体实例类型标签映射（P31 → 可读类型）
TYPE_LABEL_MAP = {
    "Q5": "人物·人类",
    "Q13442814": "学术概念",
    "Q11424": "技术/产品",
    "Q16521": "事件",
    "Q7725634": "文学作品",
    "Q188451": "哲学概念",
    "Q577": "编程语言",
    "Q7397": "软件",
    "Q4830453": "企业/公司",
    "Q6256": "国家",
    "Q515": "城市",
    "Q43229": "组织",
    "Q101352": "编程语言家族",
    "Q21199": "计算机程序",
    "Q7889": "电子游戏",
}


def _get_type_label(entity: WikidataEntity) -> str:
    """从 P31 claims 推断可读类型标签"""
    claims = entity.claims
    for claim in claims.get("P31", []):
        mainsnak = claim.get("mainsnak", {})
        if mainsnak.get("datatype") == "wikibase-item":
            datavalue = mainsnak.get("datavalue", {})
            value = datavalue.get("value", {})
            if isinstance(value, dict):
                qid = value.get("id", "")
                if qid in TYPE_LABEL_MAP:
                    return TYPE_LABEL_MAP[qid]

    # fallback: 通过 entity.type 推断
    type_labels = {
        "person": "人物",
        "concept": "概念",
        "technology": "技术/产品",
        "event": "事件",
    }
    return type_labels.get(entity.type, "实体")


def _has_same_identity(e1: WikidataEntity, e2: WikidataEntity) -> bool:
    """判断两个实体是否指向同一事物（消歧辅助）

    如果两个实体共享 Wikipedia 页面或 Wikidata 描述相似度过高，
    则视为同一事物（不做消歧）。
    """
    # 同一 Q ID → 相同实体
    if e1.id == e2.id:
        return True
    # 共享 Wikipedia 页面（同一事物的多语言页面）
    if e1.sitelink_en and e2.sitelink_en and e1.sitelink_en == e2.sitelink_en:
        return True
    if e1.sitelink_zh and e2.sitelink_zh and e1.sitelink_zh == e2.sitelink_zh:
        return True
    return False


class SearchService:
    """名词搜索业务逻辑"""

    def __init__(
        self,
        wikidata_repo: Optional[WikidataRepository] = None,
        neo4j_repo: Optional[Neo4jRepository] = None,
        cache: Optional[CacheService] = None,
    ):
        self.wikidata = wikidata_repo or WikidataRepository()
        self.neo4j = neo4j_repo or Neo4jRepository()
        self.cache = cache or CacheService()
        self._neo4j_initialized = neo4j_repo is not None

    async def search(
        self, query: str, language: str = "zh"
    ) -> dict:
        """执行搜索，返回含消歧信息的完整结果

        Returns:
            dict with keys:
              - results: list[dict] — 搜索结果列表
              - needs_disambiguation: bool
              - disambiguation_groups: list[dict]
        """
        cache_key = f"search:{language}:{query.lower()}"

        # 1) Try cache
        cached = await self.cache.get(cache_key)
        if cached is not None:
            cached.setdefault("needs_disambiguation", False)
            cached.setdefault("disambiguation_groups", [])
            return cached

        # 2) Try Neo4j cache
        neo4j_results = await self.neo4j.search_entity(query)
        if neo4j_results:
            response = {
                "results": neo4j_results,
                "needs_disambiguation": False,
                "disambiguation_groups": [],
            }
            await self.cache.set(cache_key, response, ttl=300)
            return response

        # 3) Query Wikidata
        raw_entities = await self.wikidata.search(query, language=language)

        # Cross-language fallback
        if not raw_entities and language == "zh":
            raw_entities = await self.wikidata.search(query, language="en")

        if not raw_entities and len(query) <= 3 and language == "zh":
            raw_entities = await self.wikidata.search(query, language="en")

        if not raw_entities:
            return {
                "results": [],
                "needs_disambiguation": False,
                "disambiguation_groups": [],
            }

        # 4) Dedup by identity (merge entities describing the same thing)
        seen_ids: set[str] = set()
        unique_entities: list[WikidataEntity] = []
        for entity in raw_entities:
            if entity.id in seen_ids:
                continue
            # Check if it shares identity with an already-selected entity
            is_duplicate = False
            for existing in unique_entities:
                if _has_same_identity(entity, existing):
                    is_duplicate = True
                    break
            if not is_duplicate:
                seen_ids.add(entity.id)
                unique_entities.append(entity)

        # 5) Transform to API format
        results = []
        for entity in unique_entities:
            result = self._entity_to_dict(entity)
            results.append(result)

            # Upsert to Neo4j (fire-and-forget)
            if self._neo4j_initialized:
                try:
                    await self.neo4j.upsert_entity(result)
                except Exception:
                    pass

        # 6) Determine if disambiguation needed
        needs_disambiguation = len(results) > 1
        disambiguation_groups = []
        if needs_disambiguation:
            for entity in unique_entities:
                disambiguation_groups.append({
                    "id": entity.id,
                    "label": entity.label,
                    "label_en": self._get_en_label(entity),
                    "type_label": _get_type_label(entity),
                    "confidence": 0.9 if entity.sitelink_zh or entity.sitelink_en else 0.6,
                    "summary": entity.description,
                })

        response = {
            "results": results,
            "needs_disambiguation": needs_disambiguation,
            "disambiguation_groups": disambiguation_groups,
        }

        # 7) Cache
        await self.cache.set(cache_key, response, ttl=300)
        return response

    def _get_en_label(self, entity: WikidataEntity) -> str:
        """从 Wikidata 响应中提取英文标签"""
        # We store aliases which may include English names
        for alias in entity.aliases:
            # Simple heuristic: if alias contains only ASCII, likely English
            if alias and all(ord(c) < 128 for c in alias):
                return alias
        return ""

    def _entity_to_dict(self, entity: WikidataEntity) -> dict:
        """将 WikidataEntity 转换为 API 响应格式"""
        return {
            "id": entity.id,
            "name": entity.label,
            "type": entity.type,
            "confidence": 0.9 if entity.sitelink_zh or entity.sitelink_en else 0.6,
            "summary": entity.description,
            "aliases": entity.aliases[:5] if entity.aliases else [],
            "wiki_url_zh": entity.sitelink_zh,
            "wiki_url_en": entity.sitelink_en,
        }

    async def get_detail(self, noun_id: str) -> Optional[dict]:
        """获取名词详情"""
        cache_key = f"detail:{noun_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        entity = await self.wikidata.get_entity_by_qid(noun_id)
        if entity:
            result = self._entity_to_dict(entity)
            await self.cache.set(cache_key, result, ttl=3600)
            return result

        return None

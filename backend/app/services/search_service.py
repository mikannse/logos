"""搜索服务 - Search Service

搜索策略：
1. 精确匹配 Neo4j 缓存
2. 未命中 → Wikidata API 搜索
3. 结果写入 Neo4j + Redis 缓存
4. 异步触发 AI 数据管道（冷启动构建）
"""

from typing import Optional

from app.repositories.wikidata_repo import WikidataRepository, WikidataEntity
from app.repositories.neo4j_repo import Neo4jRepository
from app.core.cache import CacheService


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
        self._wikidata_initialized = wikidata_repo is not None
        self._neo4j_initialized = neo4j_repo is not None

    async def search(
        self, query: str, language: str = "zh"
    ) -> list[dict]:
        """执行搜索

        Strategy:
        1. Check Redis cache
        2. If cached, return immediately
        3. Search Wikidata
        4. Upsert to Neo4j
        5. Cache in Redis
        """
        # Try cache first
        cache_key = f"search:{language}:{query.lower()}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Try Neo4j cache
        neo4j_results = await self.neo4j.search_entity(query)
        if neo4j_results:
            await self.cache.set(cache_key, neo4j_results, ttl=300)
            return neo4j_results

        # Query Wikidata
        wikidata_results = await self.wikidata.search(query, language=language)

        # If no results, try English (cross-language fallback)
        if not wikidata_results and language == "zh":
            wikidata_results = await self.wikidata.search(query, language="en")

        if not wikidata_results:
            # Also try to find by Chinese pinyin or transliteration
            # For short queries, try both languages
            if len(query) <= 3 and language == "zh":
                wikidata_results = await self.wikidata.search(query, language="en")

        # Transform to API response format
        results = []
        for entity in wikidata_results:
            result = self._entity_to_dict(entity)
            results.append(result)

            # Upsert to Neo4j (async, fire-and-forget)
            if self._neo4j_initialized:
                try:
                    await self.neo4j.upsert_entity(result)
                except Exception:
                    pass

        # Cache in Redis (short TTL for fresh search results)
        if results:
            await self.cache.set(cache_key, results, ttl=300)

        return results

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
        # Try cache
        cache_key = f"detail:{noun_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        # Try Wikidata
        entity = await self.wikidata.get_entity_by_qid(noun_id)
        if entity:
            result = self._entity_to_dict(entity)
            await self.cache.set(cache_key, result, ttl=3600)
            return result

        return None

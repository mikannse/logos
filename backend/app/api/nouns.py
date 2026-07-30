from fastapi import APIRouter, Query

from app.models.noun import NounSearchResponse, NounResponse
from app.services.search_service import SearchService

router = APIRouter(tags=["nouns"])

_search_service: SearchService | None = None


def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


@router.get("/nouns", response_model=NounSearchResponse)
async def search_nouns(
    q: str = Query(..., min_length=2, max_length=200, description="搜索名词"),
    lang: str = Query(default="zh", description="语言 (zh/en)"),
):
    """名词搜索

    搜索流程：
    1. 精确匹配 Neo4j 缓存
    2. 未命中 → Wikidata API 查询（跨语言对齐）
    3. 结果写入 Neo4j + Redis 缓存
    4. 返回结构化结果
    """
    service = get_search_service()
    results = await service.search(q, language=lang)

    return NounSearchResponse(
        results=[
            NounResponse(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                confidence=r.get("confidence", 0.5),
                summary=r.get("summary", ""),
            )
            for r in results
        ],
        query=q,
        total=len(results),
    )


@router.get("/nouns/{noun_id}")
async def get_noun(noun_id: str):
    """获取名词详情"""
    service = get_search_service()
    result = await service.get_detail(noun_id)
    if result is None:
        return {"id": noun_id, "message": "Not found"}, 404
    return result

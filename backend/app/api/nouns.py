import asyncio

from fastapi import APIRouter, Query

from app.models.noun import (
    NounSearchResponse,
    NounResponse,
    DisambiguationGroup,
)
from app.services.search_service import SearchService
from app.services.graph_service import GraphBuilder

router = APIRouter(tags=["nouns"])

_search_service: SearchService | None = None
_graph_builder: GraphBuilder | None = None


def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


def get_graph_builder() -> GraphBuilder:
    global _graph_builder
    if _graph_builder is None:
        _graph_builder = GraphBuilder()
    return _graph_builder


@router.get("/nouns", response_model=NounSearchResponse)
async def search_nouns(
    q: str = Query(..., min_length=2, max_length=200, description="搜索名词"),
    lang: str = Query(default="zh", description="语言 (zh/en)"),
    build: bool = Query(default=False, description="无结果时是否触发冷启动构建"),
):
    """名词搜索（含消歧 + 冷启动）

    搜索流程：
    1. 精确匹配 Neo4j 缓存
    2. 未命中 → Wikidata API 查询（跨语言对齐，实体去重）
    3. 设置 ?build=true 时无结果自动触发后台冷启动构建
    4. 多义检测：如果返回多个不同实体，标记 needs_disambiguation=True
    """
    service = get_search_service()
    result = await service.search(q, language=lang)

    # Trigger cold-start build if no results and build flag is set
    if build and len(result.get("results", [])) == 0:
        builder = get_graph_builder()
        asyncio.create_task(builder.build_graph(q, lang))

    return NounSearchResponse(
        results=[
            NounResponse(
                id=r["id"],
                name=r["name"],
                type=r["type"],
                confidence=r.get("confidence", 0.5),
                summary=r.get("summary", ""),
            )
            for r in result.get("results", [])
        ],
        query=q,
        total=len(result.get("results", [])),
        needs_disambiguation=result.get("needs_disambiguation", False),
        disambiguation_groups=[
            DisambiguationGroup(**g)
            for g in result.get("disambiguation_groups", [])
        ],
    )


@router.get("/nouns/suggest")
async def suggest_nouns(
    q: str = Query(..., min_length=2, max_length=100, description="搜索提示"),
    lang: str = Query(default="zh", description="语言 (zh/en)"),
):
    """搜索建议（autocomplete）

    轻量级接口，为搜索框输入提供即时补全建议。
    查询 Wikidata 返回匹配项，含缓存。
    """
    service = get_search_service()
    suggestions = await service.suggest(q, language=lang)
    return {"suggestions": suggestions}


@router.get("/nouns/fuzzy")
async def fuzzy_search_nouns(
    q: str = Query(..., min_length=2, max_length=200, description="模糊搜索名词"),
    lang: str = Query(default="zh", description="语言 (zh/en)"),
):
    """模糊语义搜索

    当精确搜索未命中时降级到模糊匹配。
    返回带相似度分数的结果。
    """
    service = get_search_service()
    results = await service.search_fuzzy(q, language=lang)
    return {"query": q, "results": results, "total": len(results)}


@router.get("/nouns/{noun_id}")
async def get_noun(noun_id: str):
    """获取名词详情"""
    service = get_search_service()
    result = await service.get_detail(noun_id)
    if result is None:
        return {"id": noun_id, "message": "Not found"}, 404
    return result

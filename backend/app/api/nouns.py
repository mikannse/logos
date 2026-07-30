from fastapi import APIRouter, Query

from app.models.noun import NounSearchResponse

router = APIRouter(tags=["nouns"])


@router.get("/nouns")
async def search_nouns(q: str = Query(..., min_length=2, max_length=200, description="搜索名词")):
    """名词搜索（含消歧）

    搜索流程：
    1. 精确匹配 Neo4j 缓存
    2. 未命中 → Wikidata API 查询
    3. 异步触发 AI 数据管道
    """
    return NounSearchResponse(results=[], query=q, total=0)


@router.get("/nouns/{noun_id}")
async def get_noun(noun_id: str):
    """获取名词详情"""
    return {"id": noun_id, "message": "Not implemented yet"}

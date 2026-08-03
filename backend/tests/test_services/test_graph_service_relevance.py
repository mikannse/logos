"""P3: 图谱构建相关性过滤 + llm_* ID 统一解析

- LLM 实体按 relevance >= 0.5 过滤
- 名称优先解析为 Wikidata QID（label/alias 精确命中），否则保留 llm_* ID
- unresolved 实体标低相关度（cap 0.5）
- upsert 使用解析后的 ID 与 relevance
"""

import pytest

from app.ai.extractor import (
    EntityExtractionResult,
    ExtractedEntity,
    ExtractedRelation,
)
from app.services.graph_service import (
    RELEVANCE_FILTER_THRESHOLD,
    llm_entity_id,
    resolve_qid,
    merge_llm_entities,
)


# ---------- Fakes ----------

class FakeWikidata:
    def __init__(self, hits: dict[str, list[dict]]):
        self._hits = hits
        self.calls: list[str] = []

    async def search_raw(self, query, language="zh", limit=5):
        self.calls.append(query)
        return self._hits.get(query, [])[:limit]


class FakeNeo4j:
    def __init__(self):
        self.entities: list[dict] = []
        self.relations: list[dict] = []

    async def upsert_entity(self, entity_data: dict):
        self.entities.append(entity_data)
        return True

    async def upsert_relation(self, source_id, target_id, rel_type, confidence=0.5,
                              source_url="", evidence="", relevance=None):
        self.relations.append({
            "source_id": source_id, "target_id": target_id, "rel_type": rel_type,
            "confidence": confidence, "evidence": evidence, "relevance": relevance,
        })
        return True


class FakeCache:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ttl=0):
        self.data[key] = value


def make_extraction():
    entities = [
        ExtractedEntity(name="史蒂夫·乔布斯", type="person", description="苹果联合创始人", relevance=0.9),
        ExtractedEntity(name="苹果公司", type="organization", description="科技公司", relevance=1.0),
        ExtractedEntity(name="随口感叹", type="entity", description="无关内容", relevance=0.2),
        ExtractedEntity(name="Apple Inc.", type="organization", description="同名", relevance=0.7),
        ExtractedEntity(name="蒂姆·库克", type="person", description="CEO", relevance=0.6),
    ]
    relations = [
        ExtractedRelation(source="苹果公司", target="史蒂夫·乔布斯", relation_type="affiliation",
                          description="创始人", confidence=0.8),
        ExtractedRelation(source="苹果公司", target="不存在的人", relation_type="other",
                          description="无解析目标", confidence=0.5),
    ]
    return EntityExtractionResult(entities=entities, relations=relations)


# ---------- llm_entity_id / resolve_qid ----------

class TestLlmEntityId:
    def test_slug(self):
        assert llm_entity_id("史蒂夫·乔布斯") == "llm_史蒂夫·乔布斯"
        assert llm_entity_id("Steve Jobs") == "llm_steve_jobs"


class TestResolveQid:
    @pytest.mark.asyncio
    async def test_exact_label_match_resolves_to_qid(self):
        wikidata = FakeWikidata({
            "史蒂夫·乔布斯": [{"id": "Q19837", "label": "史蒂夫·乔布斯", "aliases": []}],
        })
        qid = await resolve_qid("史蒂夫·乔布斯", wikidata)
        assert qid == "Q19837"

    @pytest.mark.asyncio
    async def test_alias_exact_match_resolves(self):
        wikidata = FakeWikidata({
            "Apple Inc.": [{"id": "Q312", "label": "苹果公司", "aliases": ["Apple Inc.", "苹果"]}],
        })
        qid = await resolve_qid("Apple Inc.", wikidata)
        assert qid == "Q312"

    @pytest.mark.asyncio
    async def test_no_match_keeps_llm_id(self):
        wikidata = FakeWikidata({"神秘实体": []})
        qid = await resolve_qid("神秘实体", wikidata)
        assert qid == llm_entity_id("神秘实体")
        assert qid.startswith("llm_")

    @pytest.mark.asyncio
    async def test_case_insensitive_match(self):
        """查询 'Apple' 应精确命中 label 'Apple'（大小写归一后相等）"""
        wikidata = FakeWikidata({
            "Apple": [{"id": "Q312", "label": "Apple", "aliases": []}],
        })
        qid = await resolve_qid("Apple", wikidata)
        assert qid == "Q312"

    @pytest.mark.asyncio
    async def test_cached_resolution(self):
        cache = FakeCache()
        wikidata = FakeWikidata({"苹果公司": [{"id": "Q312", "label": "苹果公司", "aliases": []}]})
        first = await resolve_qid("苹果公司", wikidata, cache=cache)
        second = await resolve_qid("苹果公司", wikidata, cache=cache)
        assert first == "Q312"
        assert second == "Q312"
        assert len(wikidata.calls) == 1  # 第二次走缓存


# ---------- merge_llm_entities ----------

class TestMergeLlmEntities:
    @pytest.mark.asyncio
    async def test_filters_relevance_below_threshold(self):
        wikidata = FakeWikidata({})
        neo4j = FakeNeo4j()
        result = await merge_llm_entities(make_extraction(), "Q312", ["苹果公司"], wikidata, neo4j)

        names = [n["name"] for n in neo4j.entities]
        assert "随口感叹" not in names  # relevance 0.2 < 0.5 被过滤
        assert "史蒂夫·乔布斯" in names
        assert "蒂姆·库克" in names

    @pytest.mark.asyncio
    async def test_upsert_uses_resolved_qid_and_relevance(self):
        wikidata = FakeWikidata({
            "史蒂夫·乔布斯": [{"id": "Q19837", "label": "史蒂夫·乔布斯", "aliases": []}],
        })
        neo4j = FakeNeo4j()
        await merge_llm_entities(make_extraction(), "Q312", ["苹果公司"], wikidata, neo4j)

        jobs = next(e for e in neo4j.entities if e["name"] == "史蒂夫·乔布斯")
        assert jobs["id"] == "Q19837"  # 解析为 Wikidata QID
        assert jobs["relevance"] == 0.9

    @pytest.mark.asyncio
    async def test_unresolved_entity_keeps_llm_id_capped_relevance(self):
        wikidata = FakeWikidata({})  # 所有解析失败
        neo4j = FakeNeo4j()
        await merge_llm_entities(make_extraction(), "Q312", ["苹果公司"], wikidata, neo4j)

        cook = next(e for e in neo4j.entities if e["name"] == "蒂姆·库克")
        assert cook["id"].startswith("llm_")
        assert cook["relevance"] == 0.5  # unresolved 标低相关度（cap 0.5）

    @pytest.mark.asyncio
    async def test_center_duplicate_entity_skipped(self):
        """实体名与中心同名时不重复写入中心节点"""
        wikidata = FakeWikidata({
            "苹果公司": [{"id": "Q312", "label": "苹果公司", "aliases": []}],
        })
        neo4j = FakeNeo4j()
        await merge_llm_entities(make_extraction(), "Q312", ["苹果公司"], wikidata, neo4j)

        ids = [e["id"] for e in neo4j.entities]
        assert ids.count("Q312") == 0  # 中心节点不重复写入

    @pytest.mark.asyncio
    async def test_relations_only_when_both_endpoints_resolve(self):
        wikidata = FakeWikidata({
            "史蒂夫·乔布斯": [{"id": "Q19837", "label": "史蒂夫·乔布斯", "aliases": []}],
        })
        neo4j = FakeNeo4j()
        result = await merge_llm_entities(make_extraction(), "Q312", ["苹果公司"], wikidata, neo4j)

        rel_sources = [(r["source_id"], r["target_id"]) for r in neo4j.relations]
        assert ("Q312", "Q19837") in rel_sources  # 两端都解析成功 → 写入
        # "不存在的人" 解析失败 → 该关系不写入
        assert not any("不存在的人" in str(r) for r in neo4j.relations)

    @pytest.mark.asyncio
    async def test_returns_new_nodes_and_edges(self):
        wikidata = FakeWikidata({})
        neo4j = FakeNeo4j()
        result = await merge_llm_entities(make_extraction(), "Q312", ["苹果公司"], wikidata, neo4j)
        assert isinstance(result["nodes"], list)
        assert isinstance(result["edges"], list)

    @pytest.mark.asyncio
    async def test_threshold_constant(self):
        assert RELEVANCE_FILTER_THRESHOLD == 0.5

    @pytest.mark.asyncio
    async def test_center_edge_relevance_not_capped_at_0_5(self):
        """触及中心的边 relevance 取 min(中心1.0, 节点relevance)，不再被兜底 0.5 截断"""
        wikidata = FakeWikidata({
            "史蒂夫·乔布斯": [{"id": "Q19837", "label": "史蒂夫·乔布斯", "aliases": []}],
        })
        neo4j = FakeNeo4j()
        await merge_llm_entities(make_extraction(), "Q312", ["苹果公司"], wikidata, neo4j)

        center_edge = next(
            r for r in neo4j.relations
            if r["source_id"] == "Q312" or r["target_id"] == "Q312"
        )
        # 中心 Q312 relevance=1.0，乔布斯 0.9 → 边应为 0.9 而非 0.5
        assert center_edge.get("relevance") == 0.9

    @pytest.mark.asyncio
    async def test_existing_base_node_not_overwritten(self):
        """Wikidata 基础图谱已有节点（existing_node_ids）→ LLM 不覆盖写库（Wikidata 优先）"""
        wikidata = FakeWikidata({
            "史蒂夫·乔布斯": [{"id": "Q19837", "label": "史蒂夫·乔布斯", "aliases": []}],
        })
        neo4j = FakeNeo4j()
        existing_ids = {"Q19837"}  # 基础图谱已有乔布斯
        result = await merge_llm_entities(
            make_extraction(), "Q312", ["苹果公司"], wikidata, neo4j,
            existing_node_ids=existing_ids,
            existing_relevance={"Q19837": 0.7},
        )

        # 乔布斯已在基础图谱 → 不重复写库
        assert not any(e["id"] == "Q19837" for e in neo4j.entities)
        # 边仍以基础 relevance 计算（0.7）
        center_edge = next(
            r for r in neo4j.relations
            if r["source_id"] == "Q312" and r["target_id"] == "Q19837"
        )
        assert center_edge.get("relevance") == 0.7

    @pytest.mark.asyncio
    async def test_existing_edge_not_duplicated(self):
        """基础图谱已有 (source,target,type) 边 → LLM 不重复写入"""
        wikidata = FakeWikidata({
            "史蒂夫·乔布斯": [{"id": "Q19837", "label": "史蒂夫·乔布斯", "aliases": []}],
        })
        neo4j = FakeNeo4j()
        existing_edges = {("Q312", "Q19837", "affiliation")}
        result = await merge_llm_entities(
            make_extraction(), "Q312", ["苹果公司"], wikidata, neo4j,
            existing_edge_keys=existing_edges,
        )

        assert all(
            not (r["source_id"] == "Q312" and r["target_id"] == "Q19837")
            for r in neo4j.relations
        )

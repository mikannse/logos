"""搜索服务单元测试（label_en / type_label 修复，不依赖网络）"""

import pytest

from app.services.search_service import SearchService, _get_type_label
from app.repositories.wikidata_repo import WikidataEntity


def make_entity(
    label: str,
    label_en: str = "",
    aliases: list[str] | None = None,
    claims: dict | None = None,
    id: str = "Q-test",
) -> WikidataEntity:
    return WikidataEntity(
        id=id,
        label=label,
        label_en=label_en,
        description="",
        type="entity",
        aliases=aliases or [],
        sitelink_zh="",
        sitelink_en="",
        claims=claims or {},
    )


def make_p31_claim(qid: str) -> dict:
    return {
        "mainsnak": {
            "datatype": "wikibase-item",
            "datavalue": {"value": {"id": qid}},
        }
    }


def test_get_en_label_prefers_real_label():
    """英文标签应优先使用 Wikidata 正式 label，而非别名启发式"""
    svc = SearchService()
    entity = make_entity(
        label="阿尔伯特·爱因斯坦",
        label_en="Albert Einstein",
        aliases=["A. Einsten", "爱因斯坦"],
    )
    assert svc._get_en_label(entity) == "Albert Einstein"


def test_get_en_label_falls_back_to_alias():
    """无英文 label 时降级到全 ASCII 别名"""
    svc = SearchService()
    entity = make_entity(label="虫洞", aliases=["wormhole", "Wormholes"])
    assert svc._get_en_label(entity) == "wormhole"


def test_get_en_label_empty():
    svc = SearchService()
    entity = make_entity(label="测试", aliases=["测试别名"])
    assert svc._get_en_label(entity) == ""


def test_type_label_surname():
    """Q101352（姓氏）应映射为「姓氏」，而非「编程语言家族」"""
    entity = make_entity(
        label="愛因斯坦",
        claims={"P31": [make_p31_claim("Q101352")]},
    )
    assert _get_type_label(entity) == "姓氏"


def test_type_label_human():
    entity = make_entity(
        label="阿尔伯特·爱因斯坦",
        claims={"P31": [make_p31_claim("Q5")]},
    )
    assert _get_type_label(entity) == "人物·人类"


def test_entity_to_dict_includes_label_en():
    svc = SearchService()
    entity = make_entity(label="虫洞", label_en="wormhole")
    d = svc._entity_to_dict(entity)
    assert d["label_en"] == "wormhole"


# ---------- 消歧判定（阈值化，避免每词必弹） ----------


def test_disambiguation_when_multiple_results_match_query():
    """查询词精确命中多个同名实体（苹果 → 水果/植物/电影）→ 需要消歧"""
    svc = SearchService()
    entities = [
        make_entity(id="Q89", label="苹果"),
        make_entity(id="Q158657", label="苹果"),
        make_entity(id="Q595660", label="苹果"),
    ]
    needs, groups = svc._compute_disambiguation(entities, "苹果")
    assert needs is True
    assert len(groups) == 3


def test_disambiguation_two_companies_same_name():
    """同名但不同实体（Apple Inc vs Apple Corps）→ 需要消歧"""
    svc = SearchService()
    entities = [
        make_entity(id="Q312", label="蘋果公司"),
        make_entity(id="Q621231", label="苹果公司"),
    ]
    needs, groups = svc._compute_disambiguation(entities, "苹果公司")
    assert needs is True
    assert len(groups) == 2


def test_disambiguation_ignores_subtopic_results():
    """精确查询的附属词条（总部/历史）不计入歧义 → 不弹窗"""
    svc = SearchService()
    entities = [
        make_entity(id="Q312", label="蘋果公司"),
        make_entity(id="Q3150741", label="苹果公司总部"),
        make_entity(id="Q1048090", label="苹果公司历史"),
    ]
    needs, groups = svc._compute_disambiguation(entities, "苹果公司")
    assert needs is False
    assert groups == []


def test_disambiguation_suppressed_when_only_one_named_match():
    """查询词只精确命中一个实体，其余为无关伴生结果 → 不消歧"""
    svc = SearchService()
    entities = [
        make_entity(id="Q944", label="量子力学"),
        make_entity(id="Q20665653", label="理论物理学"),
        make_entity(id="Q123456", label="随机文章"),
    ]
    needs, _ = svc._compute_disambiguation(entities, "量子力学")
    assert needs is False


def test_disambiguation_single_result_never_ambiguous():
    svc = SearchService()
    entities = [make_entity(id="Q89", label="苹果")]
    needs, groups = svc._compute_disambiguation(entities, "苹果")
    assert needs is False
    assert groups == []

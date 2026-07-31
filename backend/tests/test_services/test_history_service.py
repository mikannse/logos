"""快照存储服务单元测试（JSON 文件存储，不依赖网络/Redis/Neo4j）"""

import pytest

from app.services.history_service import SnapshotService


def make_snapshot(noun_id="Q937", query="爱因斯坦", entity_name="阿尔伯特·爱因斯坦", saved_at="2026-07-31T10:00:00"):
    return {
        "noun_id": noun_id,
        "query": query,
        "entity": {"id": noun_id, "name": entity_name},
        "graph": {"nodes": [{"id": noun_id, "label": entity_name}], "edges": []},
        "timeline": [{"year": 1955, "title": "逝世"}],
        "saved_at": saved_at,
    }


def test_save_and_get(tmp_path):
    svc = SnapshotService(data_dir=str(tmp_path))
    svc.save_snapshot("Q937", make_snapshot())
    snap = svc.get_snapshot("Q937")
    assert snap is not None
    assert snap["noun_id"] == "Q937"
    assert snap["entity"]["name"] == "阿尔伯特·爱因斯坦"
    assert snap["graph"]["nodes"][0]["label"] == "阿尔伯特·爱因斯坦"


def test_upsert_overwrites_same_noun(tmp_path):
    svc = SnapshotService(data_dir=str(tmp_path))
    svc.save_snapshot("Q937", make_snapshot(query="爱因斯坦"))
    svc.save_snapshot("Q937", make_snapshot(query="爱因斯坦重新搜索"))
    items = svc.list_snapshots()
    # 同一名词只保留一条记录，且为最新
    assert len(items) == 1
    assert items[0]["query"] == "爱因斯坦重新搜索"
    # 旧数据被覆盖，无重复文件
    assert svc.get_snapshot("Q937")["query"] == "爱因斯坦重新搜索"


def test_get_missing_returns_none(tmp_path):
    svc = SnapshotService(data_dir=str(tmp_path))
    assert svc.get_snapshot("Q999999") is None


def test_list_sorted_by_saved_at_desc(tmp_path):
    svc = SnapshotService(data_dir=str(tmp_path))
    svc.save_snapshot("Q89", make_snapshot("Q89", "苹果", "苹果", saved_at="2026-07-30T08:00:00"))
    svc.save_snapshot("Q937", make_snapshot(saved_at="2026-07-31T12:00:00"))
    svc.save_snapshot("Q312", make_snapshot("Q312", "苹果公司", "蘋果公司", saved_at="2026-07-31T09:00:00"))
    items = svc.list_snapshots()
    assert [i["noun_id"] for i in items] == ["Q937", "Q312", "Q89"]
    # 摘要字段完整
    assert items[0]["entity_name"] == "阿尔伯特·爱因斯坦"


def test_delete(tmp_path):
    svc = SnapshotService(data_dir=str(tmp_path))
    svc.save_snapshot("Q937", make_snapshot())
    assert svc.delete_snapshot("Q937") is True
    assert svc.get_snapshot("Q937") is None
    assert svc.list_snapshots() == []
    # 删除不存在的返回 False
    assert svc.delete_snapshot("Q937") is False


def test_saved_at_defaulted_when_missing(tmp_path):
    svc = SnapshotService(data_dir=str(tmp_path))
    snap = make_snapshot()
    del snap["saved_at"]
    svc.save_snapshot("Q937", snap)
    assert svc.get_snapshot("Q937")["saved_at"]

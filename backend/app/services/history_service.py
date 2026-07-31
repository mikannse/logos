"""匿名搜索历史快照服务 - History Service

以 JSON 文件形式持久化搜索结果的完整快照（查询词 + 实体 + 图谱 + 时间轴），
无需登录、匿名、可导出可删除。数据独立于 Redis 缓存 / Neo4j 持久化，
面向"回顾"场景，与实时展示解耦。

存储布局（ADR-005）：
    data/history/
        index.json          # 索引：{noun_id: {noun_id, query, entity_name, saved_at}}
        {noun_id}.json      # 单名词完整快照
"""

import json
import os
import re
from typing import Optional

from app.config import settings

# 文件名安全化：仅保留字母数字与 -_（entityId 一般形如 Q312 / llm_xxx / cold_xxx）
_SAFE_FILE = re.compile(r"[^A-Za-z0-9_-]")


class SnapshotService:
    """搜索快照的保存 / 读取 / 列表 / 删除"""

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or settings.history_dir
        os.makedirs(self.data_dir, exist_ok=True)

    # ---------- 内部工具 ----------

    def _index_path(self) -> str:
        return os.path.join(self.data_dir, "index.json")

    def _snapshot_path(self, noun_id: str) -> str:
        safe = _SAFE_FILE.sub("_", noun_id or "") or "unknown"
        return os.path.join(self.data_dir, f"{safe}.json")

    def _load_index(self) -> dict:
        try:
            with open(self._index_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_index(self, index: dict) -> None:
        self._atomic_write(self._index_path(), index)

    def _atomic_write(self, path: str, data: dict) -> None:
        """原子写：先写临时文件再改名，避免并发读看到半截 JSON"""
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    # ---------- 业务操作 ----------

    def save_snapshot(self, noun_id: str, snapshot: dict) -> dict:
        """保存 / 更新快照并维护索引（同一名词重复搜索时覆盖更新）"""
        record = dict(snapshot or {})
        record["noun_id"] = noun_id
        if not record.get("saved_at"):
            record["saved_at"] = self._now()

        self._atomic_write(self._snapshot_path(noun_id), record)

        index = self._load_index()
        index[noun_id] = {
            "noun_id": noun_id,
            "query": record.get("query", ""),
            "entity_name": (record.get("entity") or {}).get("name", ""),
            "saved_at": record["saved_at"],
        }
        self._save_index(index)
        return record

    def get_snapshot(self, noun_id: str) -> Optional[dict]:
        """读取单个名词的完整快照；不存在返回 None"""
        try:
            with open(self._snapshot_path(noun_id), "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def list_snapshots(self) -> list[dict]:
        """返回历史摘要列表（按保存时间倒序）"""
        items = list(self._load_index().values())
        items.sort(key=lambda i: i.get("saved_at", ""), reverse=True)
        return items

    def delete_snapshot(self, noun_id: str) -> bool:
        """删除单个名词的快照；返回是否存在"""
        path = self._snapshot_path(noun_id)
        existed = os.path.exists(path)
        if existed:
            os.remove(path)
        index = self._load_index()
        if noun_id in index:
            del index[noun_id]
            self._save_index(index)
        return existed

    @staticmethod
    def _now() -> str:
        from datetime import datetime

        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

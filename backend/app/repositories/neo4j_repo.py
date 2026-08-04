"""Neo4j 数据访问层

命名规范：
- Node Label: PascalCase (`:Person`, `:Entity`, `:Event`)
- Relationship Type: UPPER_SNAKE_CASE 存储（`:RELATES_TO` / `:CREATION`），
  读取时经 _EDGE_TYPE_READ_MAP 归一为小写语义类型（creation/affiliation/...）
- 属性: camelCase (`entityName`)
"""

import re
from typing import Any, Optional

from app.core.neo4j_client import Neo4jClient

# 关系类型会直接拼入 Cypher（关系类型无法参数化），严格白名单校验
_VALID_REL_TYPE = re.compile(r"^[A-Z_]{1,64}$")

# P8: 读取时归一化为小写语义类型（前端 6 色板）；未知/related to → other
_EDGE_TYPE_READ_MAP = {
    "CREATION": "creation",
    "AFFILIATION": "affiliation",
    "INFLUENCE": "influence",
    "COMPETITION": "competition",
    "COLLABORATION": "collaboration",
    "OTHER": "other",
}


def _normalize_edge_type(rel_type: str) -> str:
    """Neo4j UPPER_SNAKE 关系类型 → 小写语义类型；未知/related to → other"""
    return _EDGE_TYPE_READ_MAP.get((rel_type or "").upper(), "other")


class Neo4jRepository:
    """Neo4j 图数据库 Repository"""

    def __init__(self, client: Optional[Neo4jClient] = None):
        self._client = client

    @property
    async def _driver(self):
        if self._client is None:
            self._client = Neo4jClient()
            await self._client.connect()
        return await self._client.driver

    async def search_entity(self, query: str) -> list[dict]:
        """模糊搜索实体（按 label 模糊匹配）"""
        try:
            driver = await self._driver
            async with driver.session() as session:
                result = await session.run(
                    """
                    MATCH (e:Entity)
                    WHERE e.entityName CONTAINS $query
                       OR e.entityId CONTAINS $query
                    RETURN e.entityName AS name,
                           e.entityId AS id,
                           e.entityType AS type,
                           e.confidence AS confidence,
                           e.summary AS summary
                    LIMIT 10
                    """,
                    query=query,
                )
                records = await result.fetch(10)
                return [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "type": r.get("type", "entity"),
                        "confidence": r.get("confidence", 0.0),
                        "summary": r.get("summary", ""),
                    }
                    for r in records
                ]
        except Exception:
            return []

    async def get_graph(
        self, entity_id: str, depth: int = 1, max_age_ms: Optional[int] = None
    ) -> dict[str, Any]:
        """获取实体关联图谱

        从中心实体出发遍历 1..depth 跳路径，汇总路径上的全部节点与边。
        节点按 entityId 去重，边按 (source, target, type) 去重。

        Args:
            entity_id: 实体 ID
            depth: 关联深度（1-3）
            max_age_ms: 图谱新鲜度上限（毫秒）。仅返回 graphBuiltAt 之后
                构建的图谱；None 表示不过期。无 graphBuiltAt 属性（旧数据）
                或已过期 → 返回空，由调用方触发 Wikidata 重建（避免陈旧图
                谱永久冻结，修复 3）。

        Returns:
            {nodes: [...], edges: [...], has_more: bool}
        """
        # depth 直接拼入 Cypher（`-[r*1..{depth}]-`），本地强校验防注入/越界
        depth = int(depth) if isinstance(depth, (int, float, str)) and str(depth).lstrip("-").isdigit() else 1
        depth = min(max(depth, 1), 3)
        try:
            driver = await self._driver
            async with driver.session() as session:
                query = f"""
                MATCH (center:Entity {{entityId: $entity_id}})
                WHERE center.graphBuiltAt IS NOT NULL
                  AND ($max_age_ms IS NULL OR center.graphBuiltAt > timestamp() - $max_age_ms)
                MATCH path = (center)-[r*1..{depth}]-(related)
                RETURN path
                LIMIT 200
                """
                result = await session.run(query, entity_id=entity_id, max_age_ms=max_age_ms)
                records = await result.fetch(200)

                node_map: dict[str, dict] = {}
                seen_edges: set[tuple] = set()
                edges: list[dict] = []

                for rec in records:
                    path = rec["path"]
                    for node in path.nodes:
                        props = dict(node.items())
                        eid = props.get("entityId")
                        if not eid:
                            continue
                        if eid not in node_map:
                            relevance = props.get("relevance")
                            node_map[eid] = {
                                "id": eid,
                                "label": props.get("entityName", "") or "",
                                "type": props.get("entityType", "entity") or "entity",
                                "confidence": props.get("confidence", 0.0),
                                # None 标记旧数据（无 relevance 属性），汇总后统一补默认值
                                "relevance": relevance if relevance is not None else None,
                                "summary": props.get("summary", "") or "",
                            }
                    for rel in path.relationships:
                        start = dict(rel.start_node.items())
                        end = dict(rel.end_node.items())
                        src = start.get("entityId", "")
                        dst = end.get("entityId", "")
                        if not src or not dst:
                            continue
                        # P8: UPPER_SNAKE 读回归一为小写语义类型（未知/related to → other）
                        rel_type = _normalize_edge_type(rel.type or "")
                        key = (src, dst, rel_type)
                        if key in seen_edges:
                            continue
                        seen_edges.add(key)
                        edges.append({
                            "source": src,
                            "target": dst,
                            "type": rel_type,
                            "confidence": rel.get("confidence", 0.0),
                            "relevance": rel.get("relevance", 0.0) or 0.0,
                            "source_url": rel.get("source", "") or "",
                            "evidence": rel.get("evidence", "") or "",
                        })

                # 旧数据 relevance 缺省值：中心 1.0 / 连通节点 0.5 / 孤立节点 0.1
                connected: set[str] = set()
                for e in edges:
                    connected.add(e["source"])
                    connected.add(e["target"])
                for n in node_map.values():
                    if n["relevance"] is not None:
                        continue
                    if n["id"] == entity_id:
                        n["relevance"] = 1.0
                    elif n["id"] not in connected:
                        n["relevance"] = 0.1
                    else:
                        n["relevance"] = 0.5

                return {
                    "nodes": list(node_map.values()),
                    "edges": edges,
                    "has_more": len(records) >= 200,
                }
        except Exception:
            return {"nodes": [], "edges": [], "has_more": False}

    async def get_timeline(self, entity_id: str) -> list[dict]:
        """获取实体演化时间轴

        时间轴数据走 Redis 缓存（TimelineService 构建，见 timeline_service.py），
        不落 Neo4j —— 此处保持空实现。
        """
        return []

    async def upsert_entity(self, entity_data: dict) -> bool:
        """创建或更新实体（MERGE）

        Args:
            entity_data: {id, name, type, confidence, summary, relevance(可选), ...}

        Returns:
            是否成功
        """
        params = {
            "id": entity_data.get("id"),
            "name": entity_data.get("name") or entity_data.get("label") or entity_data.get("id"),
            "type": entity_data.get("type", "entity"),
            "confidence": entity_data.get("confidence", 0.0),
            "summary": entity_data.get("summary", ""),
            # None → coalesce 保留库中已有值（未感知 relevance 的旧调用方不会将其冲掉）
            "relevance": entity_data.get("relevance"),
        }
        try:
            driver = await self._driver
            async with driver.session() as session:
                await session.run(
                    """
                    MERGE (e:Entity {entityId: $id})
                    SET e.entityName = $name,
                        e.entityType = $type,
                        e.confidence = $confidence,
                        e.summary = $summary,
                        e.relevance = coalesce($relevance, e.relevance),
                        e.updatedAt = timestamp()
                    """,
                    **params,
                )
                return True
        except Exception:
            return False

    async def upsert_relation(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        confidence: float = 0.5,
        source_url: str = "",
        evidence: str = "",
        relevance: Optional[float] = None,
    ) -> bool:
        """创建或更新关系

        Args:
            source_id: 源实体 ID
            target_id: 目标实体 ID
            rel_type: 关系类型（写入前归一为 UPPER_SNAKE；未知语义类型原样存储，
                读取时归一为 other）
            confidence: 置信度
            source_url: 数据来源
            evidence: 证据
            relevance: 与中心实体的相关度（None 时保留已有值）
        """
        # P8: 关系类型归一 UPPER_SNAKE 后白名单校验（非法直接拒绝，避免 Cypher 注入）
        rel_type = (rel_type or "").strip().upper().replace(" ", "_")
        if not _VALID_REL_TYPE.match(rel_type):
            return False

        try:
            driver = await self._driver
            async with driver.session() as session:
                result = await session.run(
                    f"""
                    MATCH (a:Entity {{entityId: $source_id}})
                    MATCH (b:Entity {{entityId: $target_id}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r.confidence = $confidence,
                        r.source = $source_url,
                        r.evidence = $evidence,
                        r.relevance = coalesce($relevance, r.relevance),
                        r.updatedAt = timestamp()
                    RETURN count(a) AS found
                    """,
                    source_id=source_id,
                    target_id=target_id,
                    confidence=confidence,
                    source_url=source_url,
                    evidence=evidence,
                    relevance=relevance,
                )
                # 端点实体不存在时 MATCH 无行，MERGE 为 no-op —— 返回真实结果而非假成功
                record = await result.single()
                return bool(record and record["found"] > 0)
        except Exception:
            return False

    async def mark_graph_built(self, entity_id: str) -> bool:
        """标记实体图谱构建完成时间（get_graph 新鲜度判定基准）

        在 build_graph_from_wikidata 全部 upsert 成功后调用；
        未标记（构建中途失败）时 get_graph 视为未命中，下次自动重建。
        """
        try:
            driver = await self._driver
            async with driver.session() as session:
                await session.run(
                    """
                    MATCH (e:Entity {entityId: $id})
                    SET e.graphBuiltAt = timestamp()
                    """,
                    id=entity_id,
                )
                return True
        except Exception:
            return False

    async def delete_outgoing_relations(self, entity_id: str) -> bool:
        """删除实体的全部出边（过期重建前清理陈旧图谱）

        本系统图谱构建的边恒以中心实体为 source（Wikidata 白名单边与
        Web 丰富边均是如此），故重建前删除出边即可清掉陈旧关系，
        避免与旧逻辑残留的边（如占位符 evidence、过期类型映射）累积混淆。
        其他实体指向本实体的入边属于对方图谱，不删除。
        """
        try:
            driver = await self._driver
            async with driver.session() as session:
                await session.run(
                    """
                    MATCH (e:Entity {entityId: $id})-[r]->()
                    DELETE r
                    """,
                    id=entity_id,
                )
                return True
        except Exception:
            return False

    async def get_entity_aliases(self, entity_id: str) -> list[str]:
        """获取实体的别名/译名列表"""
        # TODO: 实现别名查询
        return []

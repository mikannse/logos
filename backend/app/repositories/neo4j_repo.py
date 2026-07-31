"""Neo4j 数据访问层

命名规范：
- Node Label: PascalCase (`:Person`, `:Entity`, `:Event`)
- Relationship Type: UPPER_SNAKE_CASE (`:RELATES_TO`)
- 属性: camelCase (`entityName`)
"""

import re
from typing import Any, Optional

from app.core.neo4j_client import Neo4jClient

# 关系类型会直接拼入 Cypher（关系类型无法参数化），严格白名单校验
_VALID_REL_TYPE = re.compile(r"^[A-Z_]{1,64}$")


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
        self, entity_id: str, depth: int = 1
    ) -> dict[str, Any]:
        """获取实体关联图谱

        从中心实体出发遍历 1..depth 跳路径，汇总路径上的全部节点与边。
        节点按 entityId 去重，边按 (source, target, type) 去重。

        Args:
            entity_id: 实体 ID
            depth: 关联深度（1-3）

        Returns:
            {nodes: [...], edges: [...], has_more: bool}
        """
        try:
            driver = await self._driver
            async with driver.session() as session:
                query = f"""
                MATCH path = (center:Entity {{entityId: $entity_id}})
                -[r*1..{depth}]-(related)
                RETURN path
                LIMIT 200
                """
                result = await session.run(query, entity_id=entity_id)
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
                            node_map[eid] = {
                                "id": eid,
                                "label": props.get("entityName", "") or "",
                                "type": props.get("entityType", "entity") or "entity",
                                "confidence": props.get("confidence", 0.0),
                                "summary": props.get("summary", "") or "",
                            }
                    for rel in path.relationships:
                        start = dict(rel.start_node.items())
                        end = dict(rel.end_node.items())
                        src = start.get("entityId", "")
                        dst = end.get("entityId", "")
                        if not src or not dst:
                            continue
                        rel_type = (rel.type or "RELATED").lower().replace("_", " ")
                        key = (src, dst, rel_type)
                        if key in seen_edges:
                            continue
                        seen_edges.add(key)
                        edges.append({
                            "source": src,
                            "target": dst,
                            "type": rel_type,
                            "confidence": rel.get("confidence", 0.0),
                            "source_url": rel.get("source", "") or "",
                            "evidence": rel.get("evidence", "") or "",
                        })

                return {
                    "nodes": list(node_map.values()),
                    "edges": edges,
                    "has_more": len(records) >= 200,
                }
        except Exception:
            return {"nodes": [], "edges": [], "has_more": False}

    async def get_timeline(self, entity_id: str) -> list[dict]:
        """获取实体演化时间轴"""
        # TODO: 实现时间轴查询
        return []

    async def upsert_entity(self, entity_data: dict) -> bool:
        """创建或更新实体（MERGE）

        Args:
            entity_data: {id, name, type, confidence, summary, ...}

        Returns:
            是否成功
        """
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
                        e.updatedAt = timestamp()
                    """,
                    **entity_data,
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
    ) -> bool:
        """创建或更新关系

        Args:
            source_id: 源实体 ID
            target_id: 目标实体 ID
            rel_type: 关系类型
            confidence: 置信度
            source_url: 数据来源
            evidence: 证据
        """
        # 白名单校验：非法关系类型直接拒绝，避免 Cypher 注入
        if not _VALID_REL_TYPE.match(rel_type or ""):
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
                        r.updatedAt = timestamp()
                    RETURN count(a) AS found
                    """,
                    source_id=source_id,
                    target_id=target_id,
                    confidence=confidence,
                    source_url=source_url,
                    evidence=evidence,
                )
                # 端点实体不存在时 MATCH 无行，MERGE 为 no-op —— 返回真实结果而非假成功
                record = await result.single()
                return bool(record and record["found"] > 0)
        except Exception:
            return False

    async def get_entity_aliases(self, entity_id: str) -> list[str]:
        """获取实体的别名/译名列表"""
        # TODO: 实现别名查询
        return []

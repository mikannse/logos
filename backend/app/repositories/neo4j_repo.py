"""Neo4j 数据访问层

命名规范：
- Node Label: PascalCase (`:Person`, `:Entity`, `:Event`)
- Relationship Type: UPPER_SNAKE_CASE (`:RELATES_TO`)
- 属性: camelCase (`entityName`)
"""

from typing import Any, Optional

from app.core.neo4j_client import Neo4jClient


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

        Args:
            entity_id: 实体 ID
            depth: 关联深度（1-3）

        Returns:
            {nodes: [...], edges: [...]}
        """
        try:
            driver = await self._driver
            async with driver.session() as session:
                query = f"""
                MATCH path = (center:Entity {{entityId: $entity_id}})
                -[r*1..{depth}]-(related)
                RETURN center, related, r
                LIMIT 200
                """
                result = await session.run(query, entity_id=entity_id)
                # TODO: Implement proper result parsing
                return {"nodes": [], "edges": []}
        except Exception:
            return {"nodes": [], "edges": []}

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
        try:
            driver = await self._driver
            async with driver.session() as session:
                await session.run(
                    f"""
                    MATCH (a:Entity {{entityId: $source_id}})
                    MATCH (b:Entity {{entityId: $target_id}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r.confidence = $confidence,
                        r.source = $source_url,
                        r.evidence = $evidence,
                        r.updatedAt = timestamp()
                    """,
                    source_id=source_id,
                    target_id=target_id,
                    confidence=confidence,
                    source_url=source_url,
                    evidence=evidence,
                )
                return True
        except Exception:
            return False

    async def get_entity_aliases(self, entity_id: str) -> list[str]:
        """获取实体的别名/译名列表"""
        # TODO: 实现别名查询
        return []

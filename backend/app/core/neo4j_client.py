"""Neo4j 客户端（延迟加载单例）"""

from neo4j import AsyncGraphDatabase, AsyncDriver

from app.core.net_utils import normalize_localhost


class Neo4jClient:
    """Neo4j 驱动封装 — 延迟加载，首次使用才建立连接"""

    _instance: "Neo4jClient | None" = None
    _driver: AsyncDriver | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, uri: str = "", user: str = "", password: str = ""):
        if not hasattr(self, "_initialized"):
            # 未显式传参时回退到配置（读取 NEO4J_URI 等环境变量 / .env）
            from app.config import settings

            # Windows 下 localhost 优先解析为 ::1 导致连接超时，统一换成 127.0.0.1
            self._uri = normalize_localhost(uri or settings.neo4j_uri)
            self._user = user or settings.neo4j_user
            self._password = password or settings.neo4j_password
            self._initialized = False

    async def connect(self):
        """建立连接"""
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self._uri,
                auth=(self._user, self._password),
            )

    @property
    async def driver(self) -> AsyncDriver:
        """获取驱动实例（延迟连接）"""
        if self._driver is None:
            await self.connect()
        return self._driver

    async def close(self):
        """关闭连接"""
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def verify_connectivity(self):
        """验证连接"""
        driver = await self.driver
        return await driver.verify_connectivity()

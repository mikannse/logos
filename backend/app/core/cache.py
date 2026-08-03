"""Redis 缓存封装（三层缓存策略）

缓存层级：
1. 浏览器缓存（Next.js force-cache）
2. Redis 缓存（本模块）
3. Neo4j 持久化
"""

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.net_utils import normalize_localhost


class CacheService:
    """Redis 缓存服务"""

    def __init__(self, redis_url: Optional[str] = None):
        # 未显式传参时回退到配置（读取 REDIS_URL 环境变量 / .env），
        # 否则 docker 容器内缓存会错误地指向容器自身的 localhost。
        if redis_url is None:
            from app.config import settings

            redis_url = settings.redis_url
        # Windows 下 localhost 优先解析为 ::1 导致连接超时，统一换成 127.0.0.1
        self.redis_url = normalize_localhost(redis_url) if redis_url else redis_url
        self._client: Optional[aioredis.Redis] = None

    async def get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            client = await self.get_client()
            value = await client.get(key)
            if value is not None:
                return json.loads(value)
            return None
        except Exception:
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """设置缓存"""
        try:
            client = await self.get_client()
            await client.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
        except Exception:
            pass

    async def delete(self, key: str):
        """删除缓存"""
        try:
            client = await self.get_client()
            await client.delete(key)
        except Exception:
            pass

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        try:
            client = await self.get_client()
            return bool(await client.exists(key))
        except Exception:
            return False

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None

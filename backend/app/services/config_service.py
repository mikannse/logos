"""LLM 配置管理

将 LLM 配置存储在 Redis 中（比 .env 更灵活）。
配置可在运行期间通过 API 修改，前端实时生效。
"""

from typing import Optional

import json

from pydantic import BaseModel, Field

from app.core.cache import CacheService


class LLMConfig(BaseModel):
    """LLM 连接配置"""
    endpoint: str = Field(default="https://api.openai.com/v1", description="LLM API 端点")
    api_key: str = Field(default="", description="API Key")
    model: str = Field(default="gpt-4o-mini", description="模型名称")
    provider: str = Field(default="openai", description="提供商标识（用于显示）")
    tavily_api_key: str = Field(default="", description="Tavily 全网搜索 API Key")


class ConfigService:
    """配置服务

    从 Redis 读取/写入运行时配置。
    如果没有配置，回退到 .env 文件的环境变量。
    """

    def __init__(self, cache: Optional[CacheService] = None):
        self.cache = cache or CacheService()
        self._config_key = "config:llm"

    async def get_llm_config(self) -> LLMConfig:
        """获取 LLM 配置"""
        raw = await self.cache.get(self._config_key)
        if raw:
            if isinstance(raw, dict):
                return LLMConfig(**raw)
            try:
                data = json.loads(raw)
                return LLMConfig(**data)
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: use environment defaults
        from app.config import settings
        if settings.anthropic_api_key:
            return LLMConfig(
                endpoint="https://api.anthropic.com/v1",
                api_key=settings.anthropic_api_key,
                model="claude-sonnet-4-20250514",
                provider="anthropic",
            )
        if settings.openai_api_key:
            return LLMConfig(
                endpoint="https://api.openai.com/v1",
                api_key=settings.openai_api_key,
                model="gpt-4o-mini",
                provider="openai",
            )

        # No config at all
        return LLMConfig()

    async def set_llm_config(self, config: LLMConfig) -> None:
        """保存 LLM 配置到 Redis"""
        await self.cache.set(self._config_key, config.model_dump(), ttl=86400 * 365)

    async def has_config(self) -> bool:
        """检查是否已有 LLM 配置"""
        config = await self.get_llm_config()
        return bool(config.api_key)

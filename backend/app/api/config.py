"""LLM 配置 API 端点

提供前端配置页面对接的 REST 接口。
配置存储在 Redis 中，运行时生效。
"""

from urllib.parse import urlparse

from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Request

from app.services.config_service import ConfigService, LLMConfig

router = APIRouter(tags=["config"])

_config_service: ConfigService | None = None

# 禁止作为 LLM 端点的内网/保留地址段
BLOCKED_HOSTS = [
    "127.0.0.1", "127.0.0.0", "localhost", "::1",
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.", "169.254.",
    "0.0.0.0", "metadata.google.internal",
]


def validate_endpoint(url: str) -> str:
    """验证 LLM 端点 URL 安全性和格式"""
    parsed = urlparse(url)

    if not parsed.scheme:
        raise HTTPException(status_code=400, detail="端点地址缺少协议头 (https://)")

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="不支持的协议，仅支持 http/https")

    host = parsed.hostname or parsed.netloc
    for blocked in BLOCKED_HOSTS:
        if host.startswith(blocked):
            raise HTTPException(
                status_code=400,
                detail=f"不允许的端点地址: {url}（内网地址已被拦截）",
            )

    return url


def get_config_service() -> ConfigService:
    global _config_service
    if _config_service is None:
        _config_service = ConfigService()
    return _config_service


@router.get("/config")
async def get_config():
    """获取系统配置状态"""
    service = get_config_service()
    config = await service.get_llm_config()
    has_config = await service.has_config()
    return {
        "llm_configured": has_config,
        "llm": {
            "endpoint": config.endpoint,
            "model": config.model,
            "provider": config.provider,
            "has_api_key": bool(config.api_key),
        },
    }


@router.get("/config/llm")
async def get_llm_config():
    """获取 LLM 配置（不含 API Key）"""
    service = get_config_service()
    config = await service.get_llm_config()
    return {
        "endpoint": config.endpoint,
        "model": config.model,
        "provider": config.provider,
        "has_api_key": bool(config.api_key),
    }


class LLMConfigUpdate(BaseModel):
    endpoint: str
    api_key: str = ""
    model: str
    provider: str = ""


@router.put("/config/llm")
async def update_llm_config(body: LLMConfigUpdate, request: Request):
    """更新 LLM 配置"""
    # Validate endpoint security
    validate_endpoint(body.endpoint)

    service = get_config_service()
    config = LLMConfig(
        endpoint=body.endpoint,
        api_key=body.api_key,
        model=body.model,
        provider=body.provider or "custom",
    )
    await service.set_llm_config(config)
    return {"status": "ok", "message": "LLM 配置已更新"}


@router.post("/config/llm/test")
async def test_llm_connection(body: LLMConfigUpdate, request: Request):
    """测试 LLM 连接

    用提供的配置发一条简单的模型请求检查连通性。
    """
    from openai import OpenAI

    # Validate endpoint security before making request
    validate_endpoint(body.endpoint)

    try:
        client = OpenAI(
            api_key=body.api_key,
            base_url=body.endpoint,
        )
        response = client.chat.completions.create(
            model=body.model,
            messages=[{"role": "user", "content": "Reply with just: ok"}],
            max_tokens=10,
            timeout=15,
        )
        reply = response.choices[0].message.content or ""
        return {
            "status": "ok",
            "message": f"连接成功！响应: {reply}",
            "model": body.model,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")

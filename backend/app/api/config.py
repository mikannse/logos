"""LLM 配置 API 端点

提供前端配置页面对接的 REST 接口。
配置存储在 Redis 中，运行时生效。
"""

import ipaddress
import socket
from urllib.parse import urlparse

from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Request

from app.services.config_service import ConfigService, LLMConfig

router = APIRouter(tags=["config"])

_config_service: ConfigService | None = None


def validate_endpoint(url: str) -> str:
    """通过 DNS 解析验证 LLM 端点安全性"""
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="仅支持 http/https 协议")

    host = parsed.hostname or parsed.netloc
    if not host:
        raise HTTPException(status_code=400, detail="端点地址缺少主机名")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"无法解析主机: {host}")

    for _, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise HTTPException(
                status_code=400,
                detail=f"不允许的端点地址（内网地址已被拦截）",
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
    import httpx
    from openai import OpenAI

    # Validate endpoint security before making request
    validate_endpoint(body.endpoint)

    try:
        client = OpenAI(
            api_key=body.api_key,
            base_url=body.endpoint,
            http_client=httpx.Client(follow_redirects=False),
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

"""LLM 配置 API 端点

提供前端配置页面对接的 REST 接口。
配置存储在 Redis 中，运行时生效。
"""

import asyncio

from pydantic import BaseModel

from fastapi import APIRouter, HTTPException

from app.core.endpoint_security import (
    ResolvedEndpoint,
    resolve_endpoint,
    EndpointValidationError,
)
from app.services.config_service import ConfigService, LLMConfig

router = APIRouter(tags=["config"])

_config_service: ConfigService | None = None


def _resolve_and_raise(url: str) -> ResolvedEndpoint:
    """线程池中解析端点，将 EndpointValidationError 转为 HTTP 400"""
    try:
        return resolve_endpoint(url)
    except EndpointValidationError as e:
        raise HTTPException(status_code=e.http_status, detail=str(e))


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
async def update_llm_config(body: LLMConfigUpdate):
    """更新 LLM 配置"""
    await asyncio.get_running_loop().run_in_executor(
        None, _resolve_and_raise, body.endpoint
    )

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
async def test_llm_connection(body: LLMConfigUpdate):
    """测试 LLM 连接

    用提供的配置发一条简单的模型请求检查连通性。
    使用 DNS 解析 + IP 固定的 HTTP 客户端防御 DNS rebinding。
    """
    from openai import OpenAI

    resolved = await asyncio.get_running_loop().run_in_executor(
        None, _resolve_and_raise, body.endpoint
    )

    # 若前端未传 Key（用户已保存过），仅在待测端点与已保存端点一致时才复用已存 Key，
    # 防止对攻击者可控的任意端点泄露已存储的 API Key（凭据外泄）。
    api_key = body.api_key
    if not api_key:
        saved = await get_config_service().get_llm_config()
        if saved.endpoint.rstrip("/") == body.endpoint.rstrip("/"):
            api_key = saved.api_key
        else:
            api_key = "test-invalid-key"

    try:
        http_client = resolved.make_http_client()
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=resolved.safe_url,
                http_client=http_client,
            )
            # 同步 OpenAI 调用放到线程池，避免阻塞事件循环
            response = await asyncio.to_thread(
                client.chat.completions.create,
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
        finally:
            http_client.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"连接失败: {str(e)}")

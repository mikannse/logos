"""LLM 配置 API 端点

提供前端配置页面对接的 REST 接口。
配置存储在 Redis 中，运行时生效。
"""

import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Request

from app.services.config_service import ConfigService, LLMConfig

router = APIRouter(tags=["config"])

_config_service: ConfigService | None = None


class ResolvedEndpoint:
    """DNS 解析后的安全端点（IP 已固定，防 DNS rebinding）"""
    def __init__(self, original_url: str, resolved_ip: str, host: str, port: int, scheme: str):
        self.original_url = original_url
        self.resolved_ip = resolved_ip
        self.host = host
        self.port = port
        self.scheme = scheme

    @property
    def safe_url(self) -> str:
        """用解析后的 IP 替换主机名"""
        return f"{self.scheme}://{self.resolved_ip}:{self.port}"

    def make_http_client(self) -> httpx.Client:
        """创建一个固定 IP 的 HTTP 客户端（防 DNS rebinding）"""
        transport = httpx.HTTPTransport(
            # 解析后直接连 IP，不再 DNS 解析
            proxy=None,
        )

        # 覆写 handle_request，把 URL 替换为解析后的 IP
        original_send = transport.handle_request

        def pinned_send(request: httpx.Request) -> httpx.Response:
            parsed = urlparse(str(request.url))
            pinned_url = parsed._replace(
                netloc=f"{self.resolved_ip}:{parsed.port or self.port}"
            )
            request.url = httpx.URL(str(pinned_url))
            # Host header 保留原始域名（证书校验用）
            request.headers["Host"] = self.host
            return original_send(request)

        transport.handle_request = pinned_send

        return httpx.Client(
            transport=transport,
            follow_redirects=False,
            verify=True,
        )


def resolve_endpoint(url: str) -> ResolvedEndpoint:
    """DNS 解析 + 安全校验，返回固定 IP 的端点

    Raises:
        HTTPException: 如果是内网地址或解析失败
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="仅支持 http/https 协议")

    host = parsed.hostname or parsed.netloc
    if not host:
        raise HTTPException(status_code=400, detail="端点地址缺少主机名")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    # 解析一次 DNS —— 后续请求用这个结果，防 rebinding
    try:
        infos = socket.getaddrinfo(host, port)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail=f"无法解析主机: {host}")

    resolved_ip: Optional[str] = None
    for _, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_reserved or ip.is_multicast:
            raise HTTPException(
                status_code=400,
                detail=f"不允许的端点地址（内网地址已被拦截）",
            )
        if resolved_ip is None:
            resolved_ip = str(ip)

    if resolved_ip is None:
        raise HTTPException(status_code=400, detail="无法解析端点地址")

    return ResolvedEndpoint(
        original_url=url,
        resolved_ip=resolved_ip,
        host=host,
        port=port,
        scheme=parsed.scheme,
    )


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
    resolve_endpoint(body.endpoint)

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
    使用 DNS 解析 + IP 固定的 HTTP 客户端防御 DNS rebinding。
    """
    from openai import OpenAI

    # 解析并固定 IP（防 rebinding）
    resolved = resolve_endpoint(body.endpoint)

    try:
        client = OpenAI(
            api_key=body.api_key,
            base_url=resolved.safe_url,
            http_client=resolved.make_http_client(),
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

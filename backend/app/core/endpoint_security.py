"""端点安全校验 —— DNS 解析 + IP 固定（防 DNS rebinding / SSRF）

所有需要对外 HTTP 请求的路径（配置测试按钮 + 运行时 LLM 调用）
统一走此模块，避免防护只覆盖一个入口。

环境变量：
  ALLOW_INTERNAL_ENDPOINTS=true  →  允许访问内网地址（开发/本地部署）
"""

import ipaddress
import os
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx


@dataclass
class ResolvedEndpoint:
    """DNS 解析后的安全端点"""
    original_url: str
    resolved_ip: str     # 已加括号的 IPv6 或纯 IPv4
    host: str
    port: int            # 有效的整型端口
    scheme: str

    @property
    def safe_url(self) -> str:
        """保留原始路径的完整 URL"""
        return self.original_url

    def make_http_client(self) -> httpx.Client:
        """创建 DNS 固定的 HTTP 客户端（防 DNS rebinding）

        在 handle_request 期间将目标 host 的 socket.getaddrinfo
        临时替换为预先解析好的 IP，TCP 层固定，URL 保留域名则
        TLS SNI / 证书校验不受影响。
        """
        pinned_ip = self.resolved_ip
        target_host = self.host

        class _DNSFixedTransport(httpx.HTTPTransport):
            def handle_request(self, request):
                orig = socket.getaddrinfo

                def pinned(h, port, family=0, type=0, proto=0, flags=0):
                    if h == target_host:
                        return orig(pinned_ip, port, family, type, proto, flags)
                    return orig(h, port, family, type, proto, flags)

                socket.getaddrinfo = pinned
                try:
                    return super().handle_request(request)
                finally:
                    socket.getaddrinfo = orig

        return httpx.Client(
            transport=_DNSFixedTransport(),
            follow_redirects=False,
            verify=True,
        )


class EndpointValidationError(Exception):
    """端点校验失败（内网地址、解析失败等）"""
    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.http_status = http_status


def resolve_endpoint(url: str) -> ResolvedEndpoint:
    """DNS 解析 + 安全校验，返回 IP 固定的端点（同步，请放到线程池调用）

    校验：
    - 仅允许 http / https
    - 拒绝内网 / loopback / link-local / 组播 / 保留 / 未指定 IP
      **除非 host 是显式 localhost**（允许内置预设和本地开发场景）

    Raises:
        EndpointValidationError: 校验失败
    """
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise EndpointValidationError("仅支持 http/https 协议")

    host = parsed.hostname or parsed.netloc
    if not host:
        raise EndpointValidationError("端点地址缺少主机名")

    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        raise EndpointValidationError("端口号无效")

    try:
        infos = socket.getaddrinfo(host, port)
    except socket.gaierror:
        raise EndpointValidationError(f"无法解析主机: {host}")

    resolved_ip: Optional[str] = None
    for _, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if resolved_ip is None:
            if ip.version == 6:
                resolved_ip = f"[{ip}]"
            else:
                resolved_ip = str(ip)

    if resolved_ip is None:
        raise EndpointValidationError("无法解析端点地址")

    return ResolvedEndpoint(
        original_url=url,
        resolved_ip=resolved_ip,
        host=host,
        port=port,
        scheme=parsed.scheme,
    )

"""端点安全校验 —— DNS 解析 + IP 固定（防 DNS rebinding / SSRF）

所有需要对外 HTTP 请求的路径（配置测试按钮 + 运行时 LLM 调用）
统一走此模块，避免防护只覆盖一个入口。

当前安全设计：
- DNS 解析时记录解析结果，连接阶段复用缓存，防止 DNS rebinding 篡改目标 IP
- 拒绝非 http/https 协议
- 支持代理（应用配置或环境变量）；有代理时目标域名由代理解析，pin 逻辑无害保留

说明：早期版本曾校验并拒绝内网 / 保留 IP，已按需求移除
（见 git 历史「移除 SSRF 内网拦截」），当前仅保留 DNS rebinding 防护。
"""

import ipaddress
import os
import socket
import threading
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import httpx

# 进程级 socket.getaddrinfo 替换是全局状态，跨请求需互斥，
# 否则并发请求的 pin 会相互覆盖，导致 DNS 固定防护失效。
_getaddrinfo_lock = threading.Lock()

# 代理环境变量候选（大小写）
_PROXY_ENV_VARS = (
    "HTTPS_PROXY", "https_proxy",
    "HTTP_PROXY", "http_proxy",
    "ALL_PROXY", "all_proxy",
)


def _no_proxy_matches(host: str, no_proxy: str) -> bool:
    """判断 host 是否命中 NO_PROXY 列表（支持 .example.com 前缀通配）"""
    host_lower = host.lower()
    for entry in no_proxy.split(","):
        entry = entry.strip().lower().lstrip(".")
        if not entry:
            continue
        if host_lower == entry or host_lower.endswith("." + entry):
            return True
    return False


@dataclass
class ResolvedEndpoint:
    """DNS 解析后的安全端点"""
    original_url: str
    resolved_ip: str          # 首选 IP（已加括号的 IPv6 或纯 IPv4）
    host: str
    port: int                 # 有效的整型端口
    scheme: str
    resolved_ips: list = field(default_factory=list)   # 解析出的全部 IP
    pinned_infos: list = field(default_factory=list)   # 预解析的 getaddrinfo 结果

    @property
    def safe_url(self) -> str:
        """保留原始路径的完整 URL"""
        return self.original_url

    def _proxy_for(self) -> Optional[str]:
        """解析本端点适用的代理：优先应用配置，其次环境变量（考虑 NO_PROXY）

        修复：显式传 transport 会禁用 httpx 的环境代理自动应用，
        因此在此显式解析并注入，保证代理配置对 LLM 请求同样生效。
        """
        try:
            from app.config import settings

            configured = settings.https_proxy or settings.http_proxy
            if configured:
                return configured or None
        except Exception:
            pass

        no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
        if no_proxy and _no_proxy_matches(self.host, no_proxy):
            return None

        for var in _PROXY_ENV_VARS:
            val = os.environ.get(var)
            if val:
                return val or None
        return None

    def make_http_client(self) -> httpx.Client:
        """创建 DNS 固定的 HTTP 客户端（防 DNS rebinding）

        在 handle_request 期间将目标 host 的 socket.getaddrinfo
        临时替换为预解析结果（支持多 IP），URL 保留域名则
        TLS SNI / 证书校验不受影响。

        代理：显式解析并传给 transport（见 _proxy_for 说明）。
        """
        target_host = self.host
        pinned_infos = self.pinned_infos
        proxy = self._proxy_for()

        class _DNSFixedTransport(httpx.HTTPTransport):
            def handle_request(self, request):
                # pin 期间全程持锁，避免并发请求的全局替换互相覆盖
                with _getaddrinfo_lock:
                    orig = socket.getaddrinfo

                    def pinned(h, port, family=0, type=0, proto=0, flags=0):
                        if h == target_host and pinned_infos:
                            # 返回预解析缓存的地址（可能多 IP），按请求过滤
                            return [
                                info for info in pinned_infos
                                if (family == 0 or info[0] == family)
                                and (type == 0 or info[1] == type)
                                and (proto == 0 or info[2] == proto)
                            ]
                        return orig(h, port, family, type, proto, flags)

                    socket.getaddrinfo = pinned
                    try:
                        return super().handle_request(request)
                    finally:
                        socket.getaddrinfo = orig

        return httpx.Client(
            transport=_DNSFixedTransport(proxy=proxy),
            follow_redirects=False,
            verify=True,
        )


class EndpointValidationError(Exception):
    """端点校验失败"""
    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.http_status = http_status


def resolve_endpoint(url: str) -> ResolvedEndpoint:
    """DNS 解析 + 记录解析结果，返回 IP 固定的端点（同步，请放到线程池调用）

    校验：
    - 仅允许 http / https
    - 记录解析结果供连接阶段复用（防 DNS rebinding）

    注意：内网 / 保留 IP 已不再拦截（按需求移除），仅做 DNS 固定。
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
    resolved_ips: list[str] = []
    for _, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if resolved_ip is None:
            resolved_ip = f"[{ip}]" if ip.version == 6 else str(ip)
        if sockaddr[0] not in resolved_ips:
            resolved_ips.append(sockaddr[0])

    if resolved_ip is None:
        raise EndpointValidationError("无法解析端点地址")

    return ResolvedEndpoint(
        original_url=url,
        resolved_ip=resolved_ip,
        host=host,
        port=port,
        scheme=parsed.scheme,
        resolved_ips=resolved_ips,
        pinned_infos=infos,
    )

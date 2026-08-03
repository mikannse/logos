"""DNS 固定 transport 回归测试（P-LLM 配置测试 / 运行时 LLM 调用）

背景：Windows + fake-ip DNS（Clash 198.18.x.x）下 socket.getaddrinfo 返回
socktype=0 / proto=0（"任意类型"）条目；旧实现严格过滤 info[1] == type 会把
缓存滤空，导致 httpx 报 "getaddrinfo returns an empty list" → LLM 配置测试
与运行时 LLM 管道（图谱丰富/时间轴兜底）全部失败。

修复：socktype / proto 的 0 视为任意匹配；family（IPv4/IPv6）保持严格匹配。
"""

import asyncio
import http.server
import socket
import threading

import pytest

from app.core.endpoint_security import ResolvedEndpoint


@pytest.fixture
def local_server():
    """启动 127.0.0.1 随机端口 HTTP 服务，返回 (host, port)"""
    handler = http.server.SimpleHTTPRequestHandler

    class QuietHandler(handler):
        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield ("localhost", server.server_address[1])
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _make_endpoint(host, port, pinned_infos):
    """构造 ResolvedEndpoint，host 指向 localhost、pinned_infos 为给定值"""
    return ResolvedEndpoint(
        original_url=f"http://{host}:{port}",
        resolved_ip="127.0.0.1",
        host=host,
        port=port,
        scheme="http",
        resolved_ips=["127.0.0.1"],
        pinned_infos=pinned_infos,
    )


@pytest.mark.asyncio
async def test_pinned_transport_socktype_zero_matches(local_server, monkeypatch):
    """回归锁：getaddrinfo 返回 socktype=0 时仍能连接（修复前抛 ConnectError）"""
    host, port = local_server
    # 模拟本机 fake-ip DNS 形态：socktype=0 / proto=0（"任意类型"）
    pinned_infos = [(socket.AF_INET, 0, 0, "", (host, port))]
    endpoint = _make_endpoint(host, port, pinned_infos)

    monkeypatch.setattr(endpoint, "_proxy_for", lambda: None)

    client = endpoint.make_http_client()
    try:
        resp = client.get(f"http://{host}:{port}/", timeout=5)
        assert resp.status_code == 200
    finally:
        client.close()


@pytest.mark.asyncio
async def test_pinned_transport_standard_socktype_stream(local_server, monkeypatch):
    """既有路径不破坏：正常 socktype=SOCK_STREAM 条目同样连接成功"""
    host, port = local_server
    pinned_infos = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (host, port))]
    endpoint = _make_endpoint(host, port, pinned_infos)

    monkeypatch.setattr(endpoint, "_proxy_for", lambda: None)

    client = endpoint.make_http_client()
    try:
        resp = client.get(f"http://{host}:{port}/", timeout=5)
        assert resp.status_code == 200
    finally:
        client.close()


@pytest.mark.asyncio
async def test_pinned_transport_mixed_family_kept_strict(local_server, monkeypatch):
    """family 仍严格匹配：仅 IPv6 缓存 + 请求 IPv4 → 返回空列表（防护语义保留）"""
    host, port = local_server
    pinned_infos = [(socket.AF_INET6, 0, 0, "", ("::1", port))]
    endpoint = _make_endpoint(host, port, pinned_infos)

    monkeypatch.setattr(endpoint, "_proxy_for", lambda: None)

    client = endpoint.make_http_client()
    try:
        with pytest.raises(Exception):
            # 请求走 IPv4（httpx 对 localhost 优先 IPv4），IPv6-only 缓存应被滤空 → 连接失败
            client.get(f"http://{host}:{port}/", timeout=5)
    finally:
        client.close()

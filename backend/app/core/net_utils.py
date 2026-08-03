"""网络地址工具 —— Windows 下 localhost 优先解析为 ::1（IPv6）的规避

Windows 上 `localhost` 常优先解析为 `::1`，而 Docker Desktop 的端口映射往往只绑 IPv4，
导致本地运行后端时对 Redis / Neo4j 的连接卡满超时（挂几秒后才落到 127.0.0.1）。
统一把主机 `localhost` 替换为 `127.0.0.1`。
"""

from urllib.parse import urlparse, urlunparse


def normalize_localhost(url: str) -> str:
    """将 URL 主机 localhost 替换为 127.0.0.1。

    仅影响字面 `localhost`（docker 内 `redis://redis`、`bolt://neo4j` 等主机名不受影响），
    并保留用户名/密码与端口。传入任意 scheme 均可。
    """
    parts = urlparse(url)
    if parts.hostname != "localhost":
        return url
    host_port = parts.netloc.split("@", 1)[-1]
    new_host_port = f"127.0.0.1:{parts.port}" if parts.port else "127.0.0.1"
    return urlunparse(parts._replace(netloc=parts.netloc.replace(host_port, new_host_port)))

from pathlib import Path

from pydantic_settings import BaseSettings

# 后端项目根目录（backend/），用于锚定默认数据目录
BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "anthropic"

    # 对外 HTTP 请求代理（如 Clash/V2Ray 等科学上网）
    # 留空则直连。Wikidata/Wikipedia 在部分网络环境下需代理才能访问。
    http_proxy: str = ""
    https_proxy: str = ""

    # 匿名搜索历史快照目录（JSON 文件存储，零新增依赖）
    history_dir: str = str(BACKEND_ROOT / "data" / "history")

    # Logging
    log_level: str = "INFO"

    # Sentry
    sentry_dsn: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

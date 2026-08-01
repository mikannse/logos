"""LLM 配置保存语义测试（空字段保留旧值）

覆盖 update_llm_config 的"空 Key 不误清空已存配置"行为：
T1 空 api_key 保存 → 保留已存 Key（修复：改端点/模型后保存不再清空 Key）
T2 显式新 api_key → 更新 Key
T3 空 tavily_api_key 保存 → 保留已存 Tavily Key
T4 空 endpoint/model 保存 → 保留已存值（防御前端 required 可绕过）
T5 首次保存（无旧值）→ 空字段落空，不崩溃
全部 Mock DNS 解析与 Redis，零真实网络请求。
"""

from unittest.mock import patch

import pytest

from app.services.config_service import LLMConfig


class FakeConfigService:
    """模拟已存配置的读写，捕获最后一次保存的配置"""

    def __init__(self, saved: LLMConfig | None = None):
        self._saved = saved or LLMConfig()
        self.saved_configs: list[LLMConfig] = []

    async def get_llm_config(self) -> LLMConfig:
        return self._saved

    async def set_llm_config(self, config: LLMConfig) -> None:
        self.saved_configs.append(config)
        self._saved = config


def _make_client(client, saved: LLMConfig | None = None) -> FakeConfigService:
    fake = FakeConfigService(saved)
    patch_get = patch("app.api.config.get_config_service", return_value=fake)
    patch_get.start()
    client._fake_service = fake
    return fake


async def _put(client, body: dict):
    return await client.put("/api/config/llm", json=body)


@pytest.fixture(autouse=True)
def _no_dns():
    """跳过 endpoint DNS 解析（本测试关注保存语义，不关心端点校验）"""
    with patch("app.api.config._resolve_and_raise", return_value=None):
        yield


# ---------- T1：空 api_key 保存 → 保留已存 Key ----------

@pytest.mark.asyncio
async def test_empty_key_preserves_saved_key(client):
    saved = LLMConfig(
        endpoint="https://api.deepseek.com",
        api_key="sk-deepseek-secret",
        model="deepseek-v4-pro",
        provider="deepseek",
        tavily_api_key="tvly-secret",
    )
    fake = _make_client(client, saved)

    # 模拟用户改端点/模型后保存，但 Key 框留空（未重新填写）
    res = await _put(client, {
        "endpoint": "https://api.deepseek.com",
        "api_key": "",
        "model": "deepseek-v4-pro",
        "provider": "deepseek",
        "tavily_api_key": "",
    })

    assert res.status_code == 200
    assert fake._saved.api_key == "sk-deepseek-secret"
    assert fake._saved.tavily_api_key == "tvly-secret"


# ---------- T2：显式新 api_key → 更新 Key ----------

@pytest.mark.asyncio
async def test_new_key_overwrites(client):
    saved = LLMConfig(
        endpoint="https://api.deepseek.com",
        api_key="sk-old",
        model="deepseek-v4-pro",
        provider="deepseek",
    )
    fake = _make_client(client, saved)

    res = await _put(client, {
        "endpoint": "https://api.deepseek.com",
        "api_key": "sk-new",
        "model": "deepseek-v4-pro",
        "provider": "deepseek",
        "tavily_api_key": "",
    })

    assert res.status_code == 200
    assert fake._saved.api_key == "sk-new"


# ---------- T3：空 tavily_api_key 保存 → 保留已存 Tavily Key ----------

@pytest.mark.asyncio
async def test_empty_tavily_key_preserves(client):
    saved = LLMConfig(
        endpoint="https://api.deepseek.com",
        api_key="sk-deepseek-secret",
        model="deepseek-v4-pro",
        provider="deepseek",
        tavily_api_key="tvly-secret",
    )
    fake = _make_client(client, saved)

    res = await _put(client, {
        "endpoint": "https://api.deepseek.com",
        "api_key": "sk-deepseek-secret",
        "model": "deepseek-v4-pro",
        "provider": "deepseek",
        "tavily_api_key": "",
    })

    assert res.status_code == 200
    assert fake._saved.tavily_api_key == "tvly-secret"


# ---------- T4：空 endpoint/model 保存 → 保留已存值 ----------

@pytest.mark.asyncio
async def test_empty_endpoint_model_preserves(client):
    saved = LLMConfig(
        endpoint="https://api.deepseek.com",
        api_key="sk-deepseek-secret",
        model="deepseek-v4-pro",
        provider="deepseek",
    )
    fake = _make_client(client, saved)

    res = await _put(client, {
        "endpoint": "",
        "api_key": "",
        "model": "",
        "provider": "",
        "tavily_api_key": "",
    })

    assert res.status_code == 200
    assert fake._saved.endpoint == "https://api.deepseek.com"
    assert fake._saved.model == "deepseek-v4-pro"
    assert fake._saved.provider == "deepseek"


# ---------- T5：首次保存（无旧值）→ 空字段落空，不崩溃 ----------

@pytest.mark.asyncio
async def test_first_save_with_empty_fields(client):
    fake = _make_client(client)  # 默认无旧配置

    res = await _put(client, {
        "endpoint": "https://api.deepseek.com",
        "api_key": "",
        "model": "gpt-4o-mini",
        "provider": "",
        "tavily_api_key": "",
    })

    assert res.status_code == 200
    assert fake._saved.endpoint == "https://api.deepseek.com"
    assert fake._saved.api_key == ""
    # 无旧 provider 时沿用 LLMConfig 模型默认值 "openai"（等价于原 "custom" 回退，语义不变）
    assert fake._saved.provider == "openai"

"""LLM 统一客户端（LiteLLM + Instructor 封装）

支持通过前端配置动态设置：
- 端点 (endpoint): 任意 OpenAI 兼容 API
- API Key
- 模型名称

LiteLLM 作为后端统一网关，Instructor 做结构化提取。
"""

import asyncio
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from app.services.config_service import ConfigService
from app.core.endpoint_security import (
    ResolvedEndpoint,
    resolve_endpoint,
    EndpointValidationError,
)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """LLM 统一客户端

    从 ConfigService 读取运行时的 LLM 配置（端点/Key/模型），
    通过 OpenAI 兼容客户端 + Instructor 调用任意 LLM。

    支持 LiteLLM proxy、OpenAI、Anthropic（通过 LiteLLM）、
    以及任何 OpenAI 兼容 API（vLLM、Ollama、本地模型）。

    运行时每次构建 httpx.Client 时都会校验并固定 DNS，
    防止保存后 rebinding 攻击。
    """

    def __init__(self, config_service: Optional[ConfigService] = None):
        self.config_service = config_service or ConfigService()
        self._cached_config = None
        self._client = None

    async def _load_config(self):
        """加载最新配置"""
        self._cached_config = await self.config_service.get_llm_config()

    async def _get_client(self):
        """延迟初始化 OpenAI 兼容客户端 + Instructor

        运行时每次都重新校验并固定 DNS 以防御 rebinding。
        """
        await self._load_config()
        config = self._cached_config

        if not config.api_key:
            raise ValueError("LLM 未配置：请先在设置页面配置 API Key 和端点")

        import instructor
        from openai import OpenAI

        # DNS 解析 + 安全校验放线程池（阻塞操作）
        try:
            resolved = await asyncio.get_running_loop().run_in_executor(
                None, resolve_endpoint, config.endpoint
            )
        except EndpointValidationError as e:
            raise ValueError(f"端点安全校验失败: {e}")

        client = OpenAI(
            api_key=config.api_key,
            base_url=resolved.safe_url,
            http_client=resolved.make_http_client(),
        )

        self._client = instructor.from_openai(client)
        return self._client, config.model

    async def structured_extract(
        self,
        text: str,
        response_model: Type[T],
        system_prompt: str = "",
        model: Optional[str] = None,
    ) -> Optional[T]:
        """从非结构化文本中提取结构化数据

        使用 Instructor 的 response_model 参数实现结构化输出。
        """
        try:
            client, default_model = await self._get_client()
            model_name = model or default_model
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": text})

            response = client.chat.completions.create(
                model=model_name,
                response_model=response_model,
                messages=messages,
                max_tokens=4096,
            )
            return response
        except ValueError as e:
            print(f"LLM 配置错误: {e}")
            return None
        except Exception as e:
            print(f"结构化提取失败: {e}")
            return None

    async def generate_summary(
        self, text: str, max_length: int = 200
    ) -> str:
        """生成文本摘要"""
        try:
            client, model_name = await self._get_client()
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": f"你是一个专业的知识摘要助手。请将以下内容概括为 {max_length} 字以内的中文摘要，保留关键信息。",
                    },
                    {"role": "user", "content": text},
                ],
                max_tokens=512,
            )
            return response.choices[0].message.content or ""
        except Exception:
            return ""

    async def chat(self, messages: list[dict], model: Optional[str] = None, max_tokens: int = 1024) -> str:
        """通用对话（无结构化输出）"""
        try:
            client, default_model = await self._get_client()
            model_name = model or default_model
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except ValueError as e:
            return f"配置错误: {e}"
        except Exception as e:
            return f"请求失败: {e}"

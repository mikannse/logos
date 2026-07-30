"""LLM 统一客户端（Instructor 封装）

通过 Instructor from_provider() 支持切换 Anthropic / OpenAI。
所有 LLM 调用集中管理，方便切换提供商和监控成本。
"""

from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """LLM 统一客户端

    使用 Instructor 封装，一行代码切换提供商：
    ```python
    client = instructor.from_anthropic(Anthropic())
    # 或
    client = instructor.from_openai(OpenAI())
    ```
    """

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or settings.llm_provider
        self._client = None

    def _get_client(self):
        """延迟初始化 LLM 客户端"""
        if self._client is not None:
            return self._client

        if self.provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY 未设置")
            import instructor
            from anthropic import Anthropic
            self._client = instructor.from_anthropic(
                Anthropic(api_key=settings.anthropic_api_key)
            )
        elif self.provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY 未设置")
            import instructor
            from openai import OpenAI
            self._client = instructor.from_openai(
                OpenAI(api_key=settings.openai_api_key)
            )
        else:
            raise ValueError(f"不支持的 LLM 提供商: {self.provider}")

        return self._client

    async def structured_extract(
        self,
        text: str,
        response_model: Type[T],
        system_prompt: str = "",
        model: str = "claude-sonnet-4-20250514",
    ) -> Optional[T]:
        """从非结构化文本中提取结构化数据

        Args:
            text: 输入文本
            response_model: Pydantic 模型类
            system_prompt: 系统提示
            model: 模型名称

        Returns:
            结构化数据实例，失败返回 None
        """
        try:
            client = self._get_client()
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": text})

            response = client.chat.completions.create(
                model=model,
                response_model=response_model,
                messages=messages,
                max_tokens=4096,
            )
            return response
        except ValueError as e:
            # API key not configured
            print(f"LLM client error: {e}")
            return None
        except Exception as e:
            print(f"LLM extraction error: {e}")
            return None

    async def generate_summary(
        self, text: str, max_length: int = 200
    ) -> str:
        """生成摘要"""
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model="claude-sonnet-4-20250514",
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

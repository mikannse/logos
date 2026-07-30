"""LLM 统一客户端（Instructor 封装）"""


class LLMClient:
    """LLM 统一客户端

    通过 Instructor from_provider() 支持切换 Anthropic / OpenAI。
    """

    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        self._client = None

    async def structured_extract(self, text: str, model_class):
        """结构化提取：从非结构化文本中提取结构化数据"""
        # TODO: 实现结构化提取
        return None

    async def generate_summary(self, text: str, max_length: int = 200):
        """生成摘要"""
        # TODO: 实现摘要生成
        return ""

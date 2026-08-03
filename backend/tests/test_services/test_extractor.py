"""P2: ExtractedEntity relevance 打分 + extract_from_text 焦点锚定"""

import pytest

from app.ai.extractor import EntityExtractor, ExtractedEntity, EntityExtractionResult


class FakeLLM:
    """记录 system_prompt 并返回固定提取结果"""

    def __init__(self, result=None):
        self.calls: list[dict] = []
        self._result = result

    async def structured_extract(self, text, response_model, system_prompt="", model=None):
        self.calls.append({
            "text": text,
            "response_model": response_model,
            "system_prompt": system_prompt,
        })
        return self._result


class TestExtractedEntityRelevance:
    def test_relevance_field_exists_with_bounds(self):
        entity = ExtractedEntity(name="iPhone", type="technology", description="智能手机", relevance=0.9)
        assert entity.relevance == 0.9

    def test_relevance_out_of_bounds_rejected(self):
        with pytest.raises(Exception):
            ExtractedEntity(name="x", type="entity", description="", relevance=1.2)
        with pytest.raises(Exception):
            ExtractedEntity(name="x", type="entity", description="", relevance=-0.3)

    def test_relevance_required_or_defaulted(self):
        entity = ExtractedEntity(name="x", type="entity", description="")
        # 无 relevance 时有默认值（弱相关下界），避免旧调用方崩溃
        assert 0.0 <= entity.relevance <= 1.0


class TestFocusAnchor:
    @pytest.mark.asyncio
    async def test_focus_entity_anchors_system_prompt(self):
        llm = FakeLLM(result=EntityExtractionResult(entities=[], relations=[]))
        extractor = EntityExtractor(llm=llm)

        await extractor.extract_from_text("苹果公司由乔布斯创立", focus_entity="苹果公司")

        prompt = llm.calls[0]["system_prompt"]
        assert "苹果公司" in prompt
        # 焦点锚定：只提取与焦点直接关联的实体
        assert "为核心" in prompt or "直接关联" in prompt

    @pytest.mark.asyncio
    async def test_no_focus_backward_compatible(self):
        llm = FakeLLM(result=EntityExtractionResult(entities=[], relations=[]))
        extractor = EntityExtractor(llm=llm)

        await extractor.extract_from_text("一些文本")

        prompt = llm.calls[0]["system_prompt"]
        assert "提取核心实体" in prompt

    @pytest.mark.asyncio
    async def test_prompt_requires_relevance_scoring(self):
        """system prompt 必须要求 LLM 给出相关度打分规则"""
        llm = FakeLLM(result=EntityExtractionResult(entities=[], relations=[]))
        extractor = EntityExtractor(llm=llm)

        await extractor.extract_from_text("文本", focus_entity="X")

        prompt = llm.calls[0]["system_prompt"]
        assert "relevance" in prompt or "相关度" in prompt

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        llm = FakeLLM(result=None)
        extractor = EntityExtractor(llm=llm)
        result = await extractor.extract_from_text("文本", focus_entity="X")
        assert result is None

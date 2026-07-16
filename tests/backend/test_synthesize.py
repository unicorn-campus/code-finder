"""합성 단위 테스트 — 문맥 조립·provider 계획·코드 근거 검증(LLM 모킹)."""
from __future__ import annotations

from app.common.llm_router import LLMRouter
from app.common.schemas import CodeExample, CodeSynthesisOutput, SummaryOutput
from app.search.synthesize import (
    build_context,
    plan_providers,
    synthesize_code,
    synthesize_summary,
)


class _FakeStructured:
    def __init__(self, out):
        self.out = out

    def invoke(self, _msgs):
        return self.out


class _FakeLLM:
    def __init__(self, out):
        self.out = out

    def with_structured_output(self, _schema):
        return _FakeStructured(self.out)


def _router_with(out):
    r = LLMRouter()
    r.build = lambda provider: _FakeLLM(out)  # type: ignore
    return r


def test_plan_providers():
    assert plan_providers("claude") == ("claude", "claude")
    assert plan_providers(None) == ("openai", "claude")


def test_build_context_formats_sources():
    ctx = build_context([
        {"source_type": "code", "ref": "a#f#1", "rerank_text": "def f(): ..."},
        {"source_type": "web", "url": "https://x", "rerank_text": "web text"},
    ])
    assert "(code:a#f#1)" in ctx and "(web:https://x)" in ctx


def test_synthesize_summary_returns_text_and_provider():
    r = _router_with(SummaryOutput(summary="핵심 요약"))
    summary, provider = synthesize_summary("q", "context", "openai", r)
    assert summary == "핵심 요약"
    assert provider == "openai"


def test_synthesize_code_drops_hallucinated_source():
    out = CodeSynthesisOutput(code_examples=[
        CodeExample(lang="python", code="x=1", explain="유효", source="valid#f#1"),
        CodeExample(lang="python", code="y=2", explain="환각", source="fake#g#9"),
    ])
    r = _router_with(out)
    candidates = [{"chunk_id": "valid#f#1", "lang": "python", "signature": "", "text": "x=1"}]
    examples, _provider = synthesize_code("q", candidates, "claude", r)
    assert len(examples) == 1
    assert examples[0].source == "valid#f#1"


def test_synthesize_code_empty_candidates():
    r = _router_with(CodeSynthesisOutput())
    examples, _ = synthesize_code("q", [], "claude", r)
    assert examples == []

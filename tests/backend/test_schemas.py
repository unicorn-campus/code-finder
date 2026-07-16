"""공통 스키마 단위 테스트 — API 계약 검증."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.common.schemas import (
    CodeExample,
    CodeSynthesisOutput,
    SearchAnswer,
    SearchRequest,
    Source,
)


def test_search_request_requires_query():
    with pytest.raises(ValidationError):
        SearchRequest(query="")
    req = SearchRequest(query="RAG란?")
    assert req.llm is None


def test_search_request_llm_hint_validation():
    assert SearchRequest(query="q", llm="claude").llm == "claude"
    with pytest.raises(ValidationError):
        SearchRequest(query="q", llm="mistral")


def test_source_code_vs_web_shape():
    code = Source(type="code", ref="a.py#f#1", score=0.9)
    assert code.url is None and code.fetched_at is None
    web = Source(type="web", url="https://x", score=0.5, fetched_at="2026-07-16T00:00:00Z")
    assert web.ref is None and web.url.startswith("https")


def test_search_answer_contract_fields():
    ans = SearchAnswer(
        query="q", summary="요약",
        code_examples=[CodeExample(lang="python", code="x=1", explain="설명", source="a.py#f#1")],
        sources=[Source(type="textbook", ref="ent_rag", score=0.9)],
        missing_sources=["youtube"],
        used_models={"routing": "groq/gpt-oss-120b"},
    )
    d = ans.model_dump()
    assert set(d) == {"query", "summary", "code_examples", "sources", "missing_sources", "used_models"}
    assert d["code_examples"][0]["source"] == "a.py#f#1"


def test_code_synthesis_output_default_empty():
    out = CodeSynthesisOutput()
    assert out.code_examples == []

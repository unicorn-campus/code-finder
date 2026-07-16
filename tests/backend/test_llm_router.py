"""멀티 LLM 라우터 단위 테스트 — 라우팅·Groq 폴백(네트워크 호출 없음)."""
from __future__ import annotations

import pytest

from app.common.llm_router import LLMRouter


@pytest.fixture
def router():
    r = LLMRouter()
    # 키 가용성 제어(생성만 하고 네트워크 호출 없음)
    r.p.groq_api_key = "gsk_test"
    r.p.openai_api_key = "sk_test"
    r.p.claude_api_key = None      # 무효/부재 상황 재현
    r.p.gemini_api_key = None
    r._cache.clear()
    return r


def test_available_reflects_keys(router):
    assert router.available("groq") and router.available("openai")
    assert not router.available("claude") and not router.available("gemini")


def test_resolve_summary_uses_openai(router):
    provider, _llm = router.resolve("summary", None)
    assert provider == "openai"


def test_resolve_code_falls_back_to_groq_when_claude_absent(router):
    provider, _llm = router.resolve("code", None)
    assert provider == "groq"  # claude 키 없음 → Groq 폴백


def test_hint_unavailable_falls_back_to_groq(router):
    provider, _llm = router.resolve("summary", "gemini")
    assert provider == "groq"


def test_used_models_shape(router):
    used = router.used_models("openai", "groq")
    assert set(used) == {"routing", "summary", "code_synthesis"}
    assert used["routing"].startswith("groq/")
    assert used["summary"].startswith("openai/")

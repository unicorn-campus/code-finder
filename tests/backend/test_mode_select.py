"""GraphRAG 검색 모드 선택 규칙 단위 테스트."""
from __future__ import annotations

import pytest

from kg.retriever.mode_select import select_mode


@pytest.mark.parametrize("query,expected", [
    ("RAG가 정확히 뭐예요?", "local"),
    ("Embedding의 정의가 뭐야", "local"),
    ("랭그래프랑 랭체인은 무슨 관계예요?", "hybrid"),
    ("GraphRAG랑 RAG 차이점 알려줘", "hybrid"),
    ("GraphRAG 공부 전에 먼저 알아야 할 개념 순서", "hybrid"),
    ("에이전트 그거 그냥 GPT랑 똑같은거 아니에요?", "hybrid"),
    ("GraphRAG 관련 개념들 뭐가 있어요?", "global"),
    ("멀티에이전트 종류 정리해줘", "global"),
])
def test_select_mode(query, expected):
    assert select_mode(query) == expected


def test_default_hybrid_on_ambiguous():
    assert select_mode("LangGraph") == "hybrid"

"""백엔드 통합 테스트 — 실제 Chroma·Neo4j·LLM 호출(기본 실행 제외, integration 마커)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_code_retriever_live():
    from rag.retriever import get_code_retriever
    r = get_code_retriever()
    assert r.count() > 0
    res = r.retrieve("LangGraph 조건 분기 워크플로우 예제", top_k=5)
    assert res and all(x["chunk_id"] for x in res)


def test_graph_retriever_live():
    from kg.retriever import get_graph_retriever
    out = get_graph_retriever().retrieve("RAG가 뭐예요?")
    assert out["entities"] or out["chunks"]


@pytest.mark.asyncio
async def test_run_search_live():
    from app.search import run_search
    ans = await run_search("LangGraph로 상태 공유하는 멀티 에이전트 만드는 법")
    assert ans["query"]
    assert isinstance(ans["sources"], list)
    assert set(ans) == {"query", "summary", "code_examples", "sources", "missing_sources", "used_models"}

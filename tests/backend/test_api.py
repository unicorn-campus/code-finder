"""FastAPI 엔드포인트 단위 테스트 — 그래프·리트리버 모킹(외부 호출 없음)."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

import app.main as main_mod


class _FakeGraph:
    async def astream(self, inputs, config, stream_mode):
        yield {"route": {"missing_sources": ["youtube"]}}
        yield {"rerank": {"reranked": [
            {"source_type": "code", "ref": "a#f#1", "url": None, "fetched_at": None, "score": 0.9},
            {"source_type": "web", "ref": None, "url": "https://w", "fetched_at": "2026-07-16T00:00:00Z", "score": 0.8},
        ]}}
        yield {"synthesize": {"answer": {
            "query": inputs["query"], "summary": "핵심 요약",
            "code_examples": [{"lang": "python", "code": "x=1", "explain": "설명", "source": "a#f#1"}],
            "sources": [{"type": "code", "ref": "a#f#1", "score": 0.9}],
            "missing_sources": ["youtube"],
            "used_models": {"routing": "groq/gpt-oss-120b"},
        }}}


def _parse_sse(text: str):
    events = []
    ev = None
    for line in text.splitlines():
        if line.startswith("event:"):
            ev = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and ev:
            events.append((ev, json.loads(line.split(":", 1)[1].strip())))
    return events


def test_search_sse_contract():
    with TestClient(main_mod.app) as client:
        client.app.state.graph = _FakeGraph()  # 실제 그래프 대체(외부 호출 회피)
        resp = client.post("/search", json={"query": "LangGraph StateGraph?"})
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        names = [e[0] for e in events]
        assert "missing" in names and "source" in names and "summary" in names
        assert "code" in names and "done" in names
        done = [d for e, d in events if e == "done"][0]
        assert set(done) == {"query", "summary", "code_examples", "sources", "missing_sources", "used_models"}
        assert done["missing_sources"] == ["youtube"]


def test_health_reports_components(monkeypatch):
    import rag.retriever as ragret
    import kg.retriever as kgret

    monkeypatch.setattr(ragret, "get_code_retriever",
                        lambda: type("R", (), {"count": lambda self: 2682})())
    fake_store = type("S", (), {"stats": lambda self: {"entities": 10, "documents": 5, "communities": 2}})()
    monkeypatch.setattr(kgret, "get_graph_retriever",
                        lambda: type("G", (), {"store": fake_store})())
    with TestClient(main_mod.app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["chroma_chunks"] == 2682
        assert body["neo4j"]["entities"] == 10
        assert set(body["providers"]) == {"groq", "openai", "claude", "gemini", "cohere", "youtube"}

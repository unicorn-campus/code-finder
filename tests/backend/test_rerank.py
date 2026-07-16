"""Cohere 리랭킹 단위 테스트 — 폴백·모킹(네트워크 호출 없음)."""
from __future__ import annotations

from types import SimpleNamespace

from app.common.config import RerankConfig
from app.search.rerank import Reranker


def _cands():
    return [
        {"source_type": "code", "ref": "a#f#1", "rerank_text": "aaa", "score": 0.2},
        {"source_type": "web", "url": "https://b", "rerank_text": "bbb", "score": 0.9},
        {"source_type": "textbook", "ref": "ent_x", "rerank_text": "ccc", "score": 0.5},
    ]


def test_fallback_sorts_by_score_when_no_key():
    r = Reranker(RerankConfig(api_key=None, top_n=2))
    out = r.rerank("q", _cands())
    assert len(out) == 2
    assert out[0]["score"] >= out[1]["score"]
    assert out[0]["url"] == "https://b"  # 최고 점수


def test_empty_candidates():
    assert Reranker(RerankConfig(api_key=None)).rerank("q", []) == []


def test_cohere_path_applies_relevance_scores(monkeypatch):
    import cohere

    class FakeResp:
        results = [SimpleNamespace(index=2, relevance_score=0.99),
                   SimpleNamespace(index=0, relevance_score=0.88)]

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def rerank(self, *, model, query, documents, top_n):
            assert len(documents) == 3
            return FakeResp()

    monkeypatch.setattr(cohere, "Client", FakeClient)
    r = Reranker(RerankConfig(api_key="key", model="rerank-multilingual-v3.0", top_n=2))
    out = r.rerank("q", _cands())
    assert [c["ref"] if c.get("ref") else c["url"] for c in out] == ["ent_x", "a#f#1"]
    assert out[0]["score"] == 0.99

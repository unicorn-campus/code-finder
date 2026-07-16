"""검색 그래프 노드 단위 테스트 — 병합·컴파일(외부 호출 없음)."""
from __future__ import annotations

from app.search.graph import _merge, build_search_graph


def _state():
    return {
        "query": "q",
        "code_results": [{"chunk_id": "a#f#1", "signature": "def f()", "text": "code", "rank": 0}],
        "textbook_results": {
            "entities": [{"id": "ent_x", "name": "X", "description": "설명", "score": 0.8}],
            "chunks": [{"chunk_id": "chunk_1", "text": "청크"}],
        },
        "web_results": [{"url": "https://w", "title": "W", "text": "본문", "fetched_at": "2026-07-16T00:00:00Z", "score": 0.7}],
        "youtube_results": [{"url": "https://y", "title": "Y", "transcript": "자막", "fetched_at": "2026-07-16T00:00:00Z", "score": 0.6}],
    }


def test_merge_builds_all_source_types():
    merged = _merge(_state())["merged"]
    types = {c["source_type"] for c in merged}
    assert types == {"code", "textbook", "web", "youtube"}


def test_merge_code_carries_chunk_id_ref():
    merged = _merge(_state())["merged"]
    code = next(c for c in merged if c["source_type"] == "code")
    assert code["ref"] == "a#f#1" and code["url"] is None


def test_merge_web_carries_url_and_fetched_at():
    merged = _merge(_state())["merged"]
    web = next(c for c in merged if c["source_type"] == "web")
    assert web["url"] == "https://w" and web["fetched_at"] == "2026-07-16T00:00:00Z"


def test_graph_compiles():
    graph = build_search_graph()
    assert graph is not None
    # 노드 5종 존재
    assert {"analyze", "route", "merge", "rerank", "synthesize"}.issubset(set(graph.nodes))

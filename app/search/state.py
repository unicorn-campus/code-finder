"""LangGraph StateGraph 상태 정의 (§3.1) — 노드 간 데이터 공유는 State(Reducer)로 구현.

파이프라인: analyze(Pre) → route(ReAct 4도구 병렬 팬아웃) → merge → rerank(Post) → synthesize.
"""
from __future__ import annotations

from typing import Annotated, Optional, TypedDict


def _replace(_old, new):
    """마지막 기록 값으로 대체하는 리듀서(노드가 산출물을 확정 기록)."""
    return new


class SearchState(TypedDict, total=False):
    # 입력
    query: str
    llm_hint: Optional[str]

    # analyze(Pre) 산출
    rewritten_query: Annotated[str, _replace]
    pre_techniques: Annotated[list[str], _replace]
    graphrag_mode: Annotated[str, _replace]

    # route(팬아웃) 산출 — 소스별 원 결과
    code_results: Annotated[list[dict], _replace]
    textbook_results: Annotated[dict, _replace]
    web_results: Annotated[list[dict], _replace]
    youtube_results: Annotated[list[dict], _replace]
    missing_sources: Annotated[list[str], _replace]
    fanout_log: Annotated[list[str], _replace]

    # merge / rerank 산출
    merged: Annotated[list[dict], _replace]
    reranked: Annotated[list[dict], _replace]

    # synthesize 산출(최종 Structured Output dict)
    answer: Annotated[dict, _replace]
    used_models: Annotated[dict, _replace]

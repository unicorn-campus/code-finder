"""통합 검색 MAS 그래프 (§3.1) — LangGraph StateGraph 단일 워크플로우.

파이프라인:
  analyze(Pre 질의분석·재작성) → route(ReAct 4도구 병렬 팬아웃) → merge(소스 병합)
  → rerank(Post Cohere 재정렬) → synthesize(멀티 LLM 요약+코드 합성) → 최종 Structured Output

- 노드 간 공유는 State(Reducer)로 구현.
- 부분결과·타임아웃·전 소스 실패 폴백 정책 반영(도달 시간 KPI 보호).
"""
from __future__ import annotations

import asyncio
import uuid
from functools import lru_cache
from typing import Optional

from langgraph.graph import END, START, StateGraph

from app.common.config import load_settings
from app.common.llm_router import LLMRouter
from app.common.logging_utils import get_logger
from app.common.schemas import SearchAnswer, Source
from kg.retriever.mode_select import select_mode
from .query_analysis import analyze_query
from .rerank import Reranker
from .state import SearchState
from .synthesize import build_context, plan_providers, synthesize_code, synthesize_summary
from .tools import Collector, build_react_agent, set_collector

log = get_logger()


@lru_cache(maxsize=1)
def _router() -> LLMRouter:
    return LLMRouter()


# ---------------------------------------------------------------------- #
# 노드
# ---------------------------------------------------------------------- #
async def _analyze(state: SearchState) -> dict:
    """Pre: 질의 분석·재작성 + GraphRAG 검색 모드 선택."""
    q = state["query"]
    rewritten, techs = await asyncio.to_thread(analyze_query, q, _router())
    mode = select_mode(q)
    return {"rewritten_query": rewritten, "pre_techniques": techs, "graphrag_mode": mode}


async def _route(state: SearchState) -> dict:
    """ReAct 라우팅 — 4종 도구 병렬 팬아웃(소스별 타임아웃·부분결과·폴백)."""
    settings = load_settings()
    col = Collector(graphrag_mode=state.get("graphrag_mode", "hybrid"))
    set_collector(col)
    rewritten = state["rewritten_query"]
    log.info("[react] fanout: code_search | textbook_search(mode=%s) | web_search | youtube_search | query=%r",
             col.graphrag_mode, rewritten)
    agent = build_react_agent(_router().routing_llm())
    try:
        await agent.ainvoke(
            {"messages": [{"role": "user", "content": rewritten}]},
            {"recursion_limit": settings.recursion_limit},
        )
    except Exception as e:  # noqa: BLE001 — 부분결과 사용
        log.warning("[react] 라우팅 예외(부분결과 사용): %s", e)

    got_any = bool(col.code or col.textbook.get("entities") or col.textbook.get("chunks")
                   or col.web or col.youtube)
    if not got_any:
        log.warning("[fallback] 전 소스 미도달 → web_search 단독 재시도")
        try:
            from crawler.web import get_web_searcher
            col.web = await asyncio.to_thread(get_web_searcher().search, rewritten)
        except Exception as e:  # noqa: BLE001
            log.warning("[fallback] web 재시도 실패: %s", e)

    # 미도달 판정은 '최종 결과 유무' 기준(중간 타임아웃 후 재시도 성공 케이스 정합)
    missing = set()
    if not col.code:
        missing.add("code")
    if not (col.textbook.get("entities") or col.textbook.get("chunks")):
        missing.add("textbook")
    if not col.web:
        missing.add("web")
    if not col.youtube:
        missing.add("youtube")
    if missing:
        log.info("[timeout] 미도달 소스: %s", sorted(missing))
    return {
        "code_results": col.code,
        "textbook_results": col.textbook,
        "web_results": col.web,
        "youtube_results": col.youtube,
        "missing_sources": sorted(missing),
        "fanout_log": col.fanout_log,
    }


def _merge(state: SearchState) -> dict:
    """4종 소스 원 결과를 단일 리랭킹 후보 풀로 병합."""
    merged: list[dict] = []
    for c in state.get("code_results", []) or []:
        merged.append({
            "source_type": "code", "ref": c.get("chunk_id"), "url": None, "fetched_at": None,
            "rerank_text": f"{c.get('signature', '')}\n{(c.get('text') or '')[:600]}",
            "score": round(1.0 - (c.get("rank", 0) or 0) / 10.0, 4),
        })
    tb = state.get("textbook_results", {}) or {}
    for e in tb.get("entities", []) or []:
        merged.append({
            "source_type": "textbook", "ref": e.get("id"), "url": None, "fetched_at": None,
            "rerank_text": f"{e.get('name', '')}: {e.get('description', '') or ''}",
            "score": round(float(e.get("score", 0.0) or 0.0), 4),
        })
    for w in state.get("web_results", []) or []:
        merged.append({
            "source_type": "web", "ref": None, "url": w.get("url"), "fetched_at": w.get("fetched_at"),
            "rerank_text": f"{w.get('title', '')}\n{(w.get('text') or w.get('snippet') or '')[:600]}",
            "score": float(w.get("score", 0.0) or 0.0),
        })
    for y in state.get("youtube_results", []) or []:
        merged.append({
            "source_type": "youtube", "ref": None, "url": y.get("url"), "fetched_at": y.get("fetched_at"),
            "rerank_text": f"{y.get('title', '')}\n{(y.get('transcript') or '')[:600]}",
            "score": float(y.get("score", 0.0) or 0.0),
        })
    log.info("[merge] %d candidates", len(merged))
    return {"merged": merged}


def _rerank(state: SearchState) -> dict:
    """Post: Cohere 리랭킹으로 병합 후보 재정렬."""
    reranked = Reranker().rerank(state["query"], state.get("merged", []) or [])
    return {"reranked": reranked}


async def _synthesize(state: SearchState) -> dict:
    """멀티 LLM 합성 — 요약·코드 예제 병렬 생성 후 최종 Structured Output 조립."""
    router = _router()
    hint = state.get("llm_hint")
    summary_provider, code_provider = plan_providers(hint)
    reranked = state.get("reranked", []) or []

    context = build_context(reranked)
    tb_chunks = (state.get("textbook_results", {}) or {}).get("chunks", []) or []
    if tb_chunks:
        extra = "\n".join(f"[교재청크 {c.get('chunk_id')}] {(c.get('text') or '')[:400]}"
                          for c in tb_chunks[:4])
        context = f"{context}\n{extra}"

    (summary, sum_used), (code_examples, code_used) = await asyncio.gather(
        asyncio.to_thread(synthesize_summary, state["query"], context, summary_provider, router),
        asyncio.to_thread(synthesize_code, state["query"], state.get("code_results", []) or [],
                          code_provider, router),
    )
    used = router.used_models(sum_used, code_used)
    sources = [
        Source(type=c["source_type"], ref=c.get("ref"), url=c.get("url"),
               score=float(c.get("score", 0.0) or 0.0), fetched_at=c.get("fetched_at"))
        for c in reranked
    ]
    answer = SearchAnswer(
        query=state["query"], summary=summary, code_examples=code_examples,
        sources=sources, missing_sources=state.get("missing_sources", []) or [],
        used_models=used,
    ).model_dump()
    log.info("[synthesis] summary=%s code_examples=%d sources=%d used_models=%s",
             bool(summary), len(code_examples), len(sources), used)
    return {"answer": answer, "used_models": used}


# ---------------------------------------------------------------------- #
# 그래프 빌드·실행
# ---------------------------------------------------------------------- #
def build_search_graph(checkpointer=None):
    """검색 MAS 그래프 컴파일. checkpointer 미지정 시 무상태(eval·테스트용)."""
    g = StateGraph(SearchState)
    g.add_node("analyze", _analyze)
    g.add_node("route", _route)
    g.add_node("merge", _merge)
    g.add_node("rerank", _rerank)
    g.add_node("synthesize", _synthesize)
    g.add_edge(START, "analyze")
    g.add_edge("analyze", "route")
    g.add_edge("route", "merge")
    g.add_edge("merge", "rerank")
    g.add_edge("rerank", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile(checkpointer=checkpointer)


def new_thread_id() -> str:
    return uuid.uuid4().hex


async def run_search(query: str, llm: Optional[str] = None, graph=None) -> dict:
    """단발 검색 실행(무상태) → 최종 SearchAnswer dict. 스크립트·eval용."""
    graph = graph or build_search_graph()
    state = await graph.ainvoke(
        {"query": query, "llm_hint": llm},
        {"recursion_limit": load_settings().recursion_limit,
         "configurable": {"thread_id": new_thread_id()}},
    )
    return state["answer"]

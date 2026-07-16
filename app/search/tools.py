"""ReAct 검색 도구 (§3.3) — 4종 소스 병렬 팬아웃·소스별 타임아웃·부분결과.

- create_agent(ReAct, 최대 반복 7회)에 아래 4개 도구를 제공하여 라우팅함.
- 각 도구는 소스별 타임아웃을 강제(도달 시간 KPI 보호)하고, 결과를 요청 스코프 Collector에 기록함.
- 실패·타임아웃 소스는 missing에 등록되고 관찰(observation)을 반환해 재시도/부분결과를 지원함.
- 도구 텍스트가 아닌 Collector의 구조화 결과를 후속 단계가 소비함(환각 차단).
"""
from __future__ import annotations

import asyncio
import contextvars
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

from langchain_core.tools import tool

from app.common.config import Settings, load_settings
from app.common.logging_utils import get_logger

log = get_logger()

# 요청 스코프 수집기(비동기 태스크로 컨텍스트 전파)
_COLLECTOR: contextvars.ContextVar["Collector"] = contextvars.ContextVar("search_collector")


@dataclass
class Collector:
    """단일 요청의 4종 소스 원 결과·미도달·팬아웃 로그를 수집."""

    graphrag_mode: str = "hybrid"
    code: list[dict] = field(default_factory=list)
    textbook: dict = field(default_factory=dict)
    web: list[dict] = field(default_factory=list)
    youtube: list[dict] = field(default_factory=list)
    missing: set = field(default_factory=set)
    called: set = field(default_factory=set)
    fanout_log: list[str] = field(default_factory=list)


def current_collector() -> Collector:
    return _COLLECTOR.get()


def set_collector(col: Collector) -> None:
    _COLLECTOR.set(col)


# --- 검색기 지연 싱글턴 ---
@lru_cache(maxsize=1)
def _code():
    from rag.retriever import get_code_retriever
    return get_code_retriever()


@lru_cache(maxsize=1)
def _graph():
    from kg.retriever import get_graph_retriever
    return get_graph_retriever()


@lru_cache(maxsize=1)
def _web():
    from crawler.web import get_web_searcher
    return get_web_searcher()


@lru_cache(maxsize=1)
def _youtube():
    from crawler.youtube import get_youtube_searcher
    return get_youtube_searcher()


def _cfg() -> Settings:
    return load_settings()


def _stop_hint(col: "Collector") -> str:
    """4종 도구가 모두 호출되면 ReAct 종료를 유도하는 힌트를 덧붙임(중복 루프 방지)."""
    if {"code", "textbook", "web", "youtube"}.issubset(col.called):
        return "  [모든 소스 호출 완료 — 이제 FANOUT_DONE만 반환하고 종료]"
    return ""


async def _run(source: str, timeout: float, fn, *args) -> tuple[object, Optional[str]]:
    """스레드에서 동기 검색기를 실행하고 소스별 타임아웃을 강제. (결과, 오류사유)."""
    try:
        res = await asyncio.wait_for(asyncio.to_thread(fn, *args), timeout=timeout)
        return res, None
    except asyncio.TimeoutError:
        return None, f"{timeout:.0f}s 타임아웃"
    except Exception as e:  # noqa: BLE001 — 소스 실패는 부분결과로 처리
        return None, f"{type(e).__name__}: {e}"


# --- 4종 검색 도구 ---
@tool
async def code_search(query: str) -> str:
    """예제 코드를 하이브리드(BM25+Vector) 유사도 검색함. 코드 예제·구현 방법 질의에 사용."""
    col = current_collector()
    col.called.add("code")
    fan = _cfg().fanout
    res, err = await _run("code", fan.code_timeout, _code().retrieve, query, 5)
    if err:
        col.missing.add("code")
        col.fanout_log.append(f"code_search {err} → skip")
        return f"code_search 실패({err}) → 스킵{_stop_hint(col)}"
    col.code = res or []
    syms = ", ".join(r.get("symbol", "") for r in col.code[:3])
    return f"code_search: {len(col.code)}건 (상위: {syms}){_stop_hint(col)}"


@tool
async def textbook_search(query: str) -> str:
    """교재 지식그래프(GraphRAG)를 검색함. 개념 정의·관계·선행지식 질의에 사용."""
    col = current_collector()
    col.called.add("textbook")
    fan = _cfg().fanout
    res, err = await _run("textbook", fan.textbook_timeout, _graph().retrieve, query, col.graphrag_mode)
    if err:
        col.missing.add("textbook")
        col.fanout_log.append(f"textbook_search {err} → skip")
        return f"textbook_search 실패({err}) → 스킵{_stop_hint(col)}"
    col.textbook = res or {}
    ents = len(col.textbook.get("entities", []))
    chs = len(col.textbook.get("chunks", []))
    return f"textbook_search(mode={col.textbook.get('mode')}): 엔티티 {ents}, 청크 {chs}{_stop_hint(col)}"


@tool
async def web_search(query: str) -> str:
    """웹(DuckDuckGo)에서 최신 자료를 검색함. 최신 동향·외부 문서 질의에 사용."""
    col = current_collector()
    col.called.add("web")
    fan = _cfg().fanout
    res, err = await _run("web", fan.web_timeout, _web().search, query)
    if err:
        col.missing.add("web")
        # 403/429 차단은 명시 보고
        col.fanout_log.append(f"web_search {err} → skip")
        return f"web_search 실패({err}) → 스킵{_stop_hint(col)}"
    col.web = res or []
    return f"web_search: {len(col.web)}건{_stop_hint(col)}"


@tool
async def youtube_search(query: str) -> str:
    """유튜브 영상·자막을 검색함. 영상 튜토리얼·강의 질의에 사용."""
    col = current_collector()
    col.called.add("youtube")
    fan = _cfg().fanout
    res, err = await _run("youtube", fan.youtube_timeout, _youtube().search, query)
    if err:
        col.missing.add("youtube")
        col.fanout_log.append(f"youtube_search {err} → skip")
        return f"youtube_search 실패({err}) → 스킵{_stop_hint(col)}"
    col.youtube = res or []
    if not col.youtube:
        col.missing.add("youtube")  # 결과 0건(자막 없음·키 만료 등)도 미도달로 표기
    return f"youtube_search: {len(col.youtube)}건{_stop_hint(col)}"


SEARCH_TOOLS = [code_search, textbook_search, web_search, youtube_search]

_ROUTER_SYSTEM = (
    "당신은 학습 질문에 대한 근거를 수집하는 검색 라우터임. "
    "code_search·textbook_search·web_search·youtube_search 네 도구를 사용함.\n"
    "규칙:\n"
    "1) 첫 응답에서 네 도구를 모두 동일 질의로 병렬 호출함(도달 시간 단축).\n"
    "2) 어떤 도구가 실패/타임아웃 관찰을 반환하면 최대 1회만 재시도함.\n"
    "3) 근거가 모이면 답을 직접 생성하지 말고 'FANOUT_DONE'만 반환하고 종료함.\n"
    "도구 결과 요약·정답 합성은 후속 단계가 수행함. 근거 없는 내용을 만들지 않음."
)


def build_react_agent(model):
    """create_agent로 ReAct 라우팅 에이전트를 구성함(4개 검색 도구)."""
    from langchain.agents import create_agent
    return create_agent(model, tools=SEARCH_TOOLS, system_prompt=_ROUTER_SYSTEM)

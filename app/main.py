"""FastAPI 진입점 — 통합 검색 API.

- POST /search : 부분 결과 SSE 스트리밍(summary·code·source·missing·done) → done에 최종 Structured Output
- GET  /health : 상태 점검(Chroma·Neo4j·provider 키)
- 실행 방식 [고정]: UI 스트리밍 + 병렬 도구 호출이므로 LCEL 비동기 스트리밍(astream) 사용
- 세션 체크포인트 [고정]: SqliteSaver(비동기 AsyncSqliteSaver, 로컬 파일)
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.common.config import load_settings
from app.common.logging_utils import get_logger
from app.common.schemas import SearchRequest
from app.search.graph import build_search_graph, new_thread_id

log = get_logger()
settings = load_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 수명주기 — AsyncSqliteSaver 체크포인터 초기화·정리."""
    checkpointer = None
    saver_cm = None
    if settings.checkpointer == "sqlite":
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        saver_cm = AsyncSqliteSaver.from_conn_string(settings.sqlite_path)
        checkpointer = await saver_cm.__aenter__()
        log.info("[startup] SqliteSaver 체크포인터: %s", settings.sqlite_path)
    else:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        log.info("[startup] MemorySaver 체크포인터")

    app.state.graph = build_search_graph(checkpointer=checkpointer)
    log.info("[startup] 검색 그래프 컴파일 완료")
    try:
        yield
    finally:
        if saver_cm is not None:
            await saver_cm.__aexit__(None, None, None)
        log.info("[shutdown] 정리 완료")


app = FastAPI(title="code-finder 통합 검색 API", version="1.0.0", lifespan=lifespan)

# CORS — 프론트엔드(front/) dev 서버 등 별도 오리진의 브라우저 호출 허용.
# 기본값은 Vite dev 오리진, CORS_ALLOW_ORIGINS(콤마 구분)로 override 가능.
_cors_origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sse(event: str, data: dict) -> dict:
    """SSE 이벤트 포맷(data는 최종 스키마 필드명 사용)."""
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


async def _search_events(graph, req: SearchRequest):
    """그래프 astream(updates) → 부분결과 SSE 이벤트 생성기."""
    config = {
        "recursion_limit": settings.recursion_limit,
        "configurable": {"thread_id": new_thread_id()},
    }
    inputs = {"query": req.query, "llm_hint": req.llm}
    emitted_missing = False
    try:
        async for chunk in graph.astream(inputs, config, stream_mode="updates"):
            for node, update in chunk.items():
                if update is None:
                    continue
                if node == "route" and not emitted_missing:
                    yield _sse("missing", {"missing_sources": update.get("missing_sources", [])})
                    emitted_missing = True
                elif node == "rerank":
                    for s in update.get("reranked", []) or []:
                        data = {"type": s["source_type"], "score": s.get("score", 0.0)}
                        if s.get("ref"):
                            data["ref"] = s["ref"]
                        if s.get("url"):
                            data["url"] = s["url"]
                        if s.get("fetched_at"):
                            data["fetched_at"] = s["fetched_at"]
                        yield _sse("source", data)
                elif node == "synthesize":
                    answer = update.get("answer", {}) or {}
                    yield _sse("summary", {"summary": answer.get("summary", "")})
                    for ce in answer.get("code_examples", []) or []:
                        yield _sse("code", ce)
                    yield _sse("done", answer)
    except Exception as e:  # noqa: BLE001 — 스트림 오류를 이벤트로 통지
        log.exception("[/search] 스트림 오류")
        yield _sse("error", {"error": str(e)})


@app.post("/search")
async def search(req: SearchRequest):
    """통합 검색 — 부분결과 SSE 스트리밍."""
    log.info("[/search] query=%r llm=%s", req.query, req.llm)
    return EventSourceResponse(_search_events(app.state.graph, req))


@app.get("/health")
async def health():
    """상태 점검 — Chroma 청크 수·Neo4j 통계·provider 키 설정 여부."""
    result: dict = {"status": "ok"}

    try:
        from rag.retriever import get_code_retriever
        result["chroma_chunks"] = get_code_retriever().count()
    except Exception as e:  # noqa: BLE001
        result["chroma_chunks"] = f"error: {e}"
        result["status"] = "degraded"

    try:
        from kg.retriever import get_graph_retriever
        stats = get_graph_retriever().store.stats()
        result["neo4j"] = {"entities": stats["entities"], "documents": stats["documents"],
                           "communities": stats["communities"]}
    except Exception as e:  # noqa: BLE001
        result["neo4j"] = f"error: {e}"
        result["status"] = "degraded"

    p = settings.provider
    result["providers"] = {
        "groq": bool(p.groq_api_key), "openai": bool(p.openai_api_key),
        "claude": bool(p.claude_api_key), "gemini": bool(p.gemini_api_key),
        "cohere": bool(settings.rerank.api_key), "youtube": bool(settings.youtube_api_key),
    }
    return result

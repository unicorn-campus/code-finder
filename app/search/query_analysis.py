"""Pre 검색 처리 기법 (§3.6) — 질의 분석·재작성.

[기준] 조건→기법 선택(README 기록):
- 짧거나 모호 → Query Rewriting
- 다각도 검색 필요 → Multi Query
- 질의-문서 어휘 불일치 → HyDE
- 추상 개념 질의 → Step-back

단일 LLM 호출(Groq, temperature 0)로 검색 최적 질의 1건을 생성하고 적용 기법을 라벨링함.
LLM 실패 시 원 질의로 폴백(추측 생성 금지).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.common.llm_router import LLMRouter
from app.common.logging_utils import get_logger

log = get_logger()

_SYSTEM = (
    "당신은 학습 콘텐츠 검색 질의 최적화기임. 학습자의 원 질의를 교재·코드·웹·영상 검색에 적합한 "
    "한국어 검색 질의 1건으로 재작성함.\n"
    "다음 조건에 따라 기법을 선택하고 techniques에 라벨을 기록함:\n"
    "- 짧거나 모호 → query_rewriting(핵심 용어·의도 보강)\n"
    "- 다각도 검색 필요 → multi_query(여러 관점을 한 질의에 통합)\n"
    "- 질의-문서 어휘 불일치 → hyde(가상 정답 문서의 키워드로 확장)\n"
    "- 추상 개념 질의 → step_back(상위 개념으로 일반화)\n"
    "재작성 질의는 원 의도를 왜곡하지 않으며 도메인 용어(예: LangGraph, GraphRAG, RAG)를 보존함. "
    "새로운 사실을 만들어내지 않음."
)


class QueryAnalysis(BaseModel):
    """Pre 처리 Structured Output."""

    rewritten_query: str = Field(description="검색에 최적화된 재작성 질의(한국어)")
    techniques: list[str] = Field(
        default_factory=list,
        description="적용 기법 라벨 배열(query_rewriting|multi_query|hyde|step_back)")


def analyze_query(query: str, router: LLMRouter) -> tuple[str, list[str]]:
    """질의 분석·재작성 → (rewritten_query, techniques). 실패 시 원 질의 폴백."""
    try:
        llm = router.routing_llm().with_structured_output(QueryAnalysis)
        out: QueryAnalysis = llm.invoke([
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": f"원 질의: {query}"},
        ])
        rewritten = (out.rewritten_query or "").strip() or query
        techs = [t for t in out.techniques if t in
                 ("query_rewriting", "multi_query", "hyde", "step_back")]
        log.info("[query] rewrite=%r techniques=%s", rewritten, techs)
        return rewritten, techs
    except Exception as e:  # noqa: BLE001 — 폴백: 원 질의 사용
        log.warning("[query] 분석 실패 → 원 질의 사용: %s", e)
        return query, []

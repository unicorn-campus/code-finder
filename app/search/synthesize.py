"""멀티 LLM 합성 (§3.1/§3.2) — 요약·코드 예제 Structured Output.

- 요약(개념): OpenAI/Gemini(힌트 우선), 검색 문맥 근거로 2~3문장.
- 코드 합성: Claude(힌트 우선), 검색된 코드 청크에서 발췌·설명.
- 호출 실패 시 기본(Groq)로 폴백하고 used_models에 '실제 사용' 모델을 정직하게 반영함.
- 환각 차단: 코드 예제 source는 반드시 검색된 chunk_id 집합에 존재해야 함(불일치 시 제거).
"""
from __future__ import annotations

from typing import Optional

from app.common.llm_router import LLMRouter
from app.common.logging_utils import get_logger
from app.common.schemas import CodeExample, CodeSynthesisOutput, SummaryOutput

log = get_logger()

_SUMMARY_SYSTEM = (
    "당신은 학습 콘텐츠 요약기임. 제공된 검색 문맥에만 근거하여 학습자 질문에 대한 핵심 요약을 "
    "2~3문장 명사체로 작성함. 문맥에 근거가 없으면 추측하지 말고 확인된 범위만 요약함. "
    "새로운 사실·API·수치를 만들어내지 않음."
)
_CODE_SYSTEM = (
    "당신은 코드 예제 큐레이터임. 제공된 코드 청크 목록에서 학습자 질문에 가장 적합한 예제를 "
    "최대 3건 선별하여 설명함.\n"
    "규칙:\n"
    "- code는 제공된 청크 본문에서 발췌하며 새로 창작하지 않음.\n"
    "- source는 반드시 제공된 청크의 chunk_id 중 하나를 그대로 사용함.\n"
    "- explain은 명사체로 코드의 동작·핵심을 1~2문장 설명함.\n"
    "- 적합한 예제가 없으면 빈 목록을 반환함."
)


def build_context(reranked: list[dict], limit: int = 8) -> str:
    """리랭킹 결과를 번호·출처 태그가 붙은 문맥 문자열로 포맷."""
    lines = []
    for i, c in enumerate(reranked[:limit], 1):
        tag = c.get("source_type", "?")
        ref = c.get("ref") or c.get("url") or ""
        text = (c.get("rerank_text") or "").strip().replace("\n", " ")
        lines.append(f"[{i}] ({tag}:{ref}) {text[:600]}")
    return "\n".join(lines)


def _structured_invoke(router: LLMRouter, task: str, provider: Optional[str],
                       schema, system: str, user: str):
    """(구조화 출력, 실제 provider). primary 실패 시 Groq 폴백."""
    primary, _ = router.resolve(task, provider)
    for candidate in (primary, "groq"):
        try:
            llm = router.build(candidate).with_structured_output(schema)
            out = llm.invoke([
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ])
            if candidate != primary:
                log.warning("[synthesis] %s provider '%s' 실패 → 'groq' 폴백", task, primary)
            return out, candidate
        except Exception as e:  # noqa: BLE001 — 폴백 목적
            log.warning("[synthesis] %s provider '%s' 호출 실패: %s", task, candidate, str(e)[:120])
    return None, primary


def synthesize_summary(query: str, context: str, provider: str,
                       router: LLMRouter) -> tuple[str, str]:
    """요약 합성 → (summary, 실제 provider)."""
    hint = provider if provider in ("claude", "openai", "gemini") else None
    out, used = _structured_invoke(
        router, "summary", hint, SummaryOutput, _SUMMARY_SYSTEM,
        f"질문: {query}\n\n검색 문맥:\n{context}")
    if out is None:
        return "", used
    return (out.summary or "").strip(), used


def synthesize_code(query: str, code_candidates: list[dict], provider: str,
                    router: LLMRouter) -> tuple[list[CodeExample], str]:
    """코드 예제 합성 + chunk_id 근거 검증 → (examples, 실제 provider)."""
    hint = provider if provider in ("claude", "openai", "gemini") else None
    if not code_candidates:
        # 후보 없음 — 라우팅 대상 provider명만 반환
        used, _ = router.resolve("code", hint)
        return [], used
    valid_ids = {c.get("chunk_id") for c in code_candidates if c.get("chunk_id")}
    blocks = []
    for c in code_candidates:
        blocks.append(
            f"chunk_id: {c.get('chunk_id')}\nlang: {c.get('lang')}\n"
            f"signature: {c.get('signature')}\ncode:\n{(c.get('text') or '')[:1200]}")
    corpus = "\n---\n".join(blocks)
    out, used = _structured_invoke(
        router, "code", hint, CodeSynthesisOutput, _CODE_SYSTEM,
        f"질문: {query}\n\n코드 청크 목록:\n{corpus}")
    if out is None:
        return [], used
    examples: list[CodeExample] = []
    for ex in out.code_examples:
        if ex.source in valid_ids:  # 근거 검증(환각 차단)
            examples.append(ex)
        else:
            log.info("[synthesis] 근거 불일치 코드 예제 제거: source=%r", ex.source)
    return examples[:3], used


def plan_providers(hint: Optional[str]) -> tuple[str, str]:
    """(summary_provider, code_provider). 힌트 지정 시 양쪽 강제, 미지정 시 태스크 라우팅."""
    if hint in ("claude", "openai", "gemini"):
        return hint, hint
    return "openai", "claude"

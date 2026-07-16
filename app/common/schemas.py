"""공통 스키마 — 프론트엔드가 소비하는 API 계약의 정본.

- 최종 응답(SearchAnswer)과 SSE 이벤트 필드명은 동일함(summary·code·source·missing·done).
- 합성 LLM은 Structured Output(SynthesisOutput)만 생성하고, sources·missing_sources·used_models는
  파이프라인이 실측 근거로 조립함(환각 차단).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

SourceType = Literal["textbook", "code", "web", "youtube"]


class CodeExample(BaseModel):
    """예제 코드 1건. `source`는 근거 청크 참조.

    - code 소스: `indexing-code.md` 계약의 chunk_id(`{상대경로}#{symbol}#{start_line}`)를 그대로 사용
    - 그 외: 교재 엔티티 ref 또는 web/youtube url
    """

    lang: str = Field(description="프로그래밍 언어 (예: python)")
    code: str = Field(description="예제 코드 본문")
    explain: str = Field(description="코드 동작 설명(명사체)")
    source: str = Field(description="근거 청크 참조(code chunk_id 또는 ref/url)")


class Source(BaseModel):
    """검색 출처 1건. 교재·코드는 ref, 웹·영상은 url+fetched_at, 전 소스 score 표기."""

    type: SourceType
    ref: Optional[str] = Field(default=None, description="교재 엔티티/코드 청크 참조")
    url: Optional[str] = Field(default=None, description="웹·영상 URL")
    score: float = Field(description="관련도·신뢰도 점수")
    fetched_at: Optional[str] = Field(default=None, description="수집 시각(ISO8601, 웹·영상)")


class SearchAnswer(BaseModel):
    """POST /search 최종 Structured Output(= SSE `done` data)."""

    query: str = Field(description="원 질의 에코")
    summary: str = Field(default="", description="핵심 요약")
    code_examples: list[CodeExample] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    missing_sources: list[str] = Field(default_factory=list, description="미도달 소스 유형 배열")
    used_models: dict[str, str] = Field(default_factory=dict, description="태스크별 선정 모델 맵")


class SearchRequest(BaseModel):
    """POST /search 요청 스키마."""

    query: str = Field(min_length=1, description="학습자 질문(필수)")
    llm: Optional[Literal["claude", "openai", "gemini"]] = Field(
        default=None, description="합성 모델 힌트(미지정 시 태스크별 자동 라우팅)")


# --- 합성 LLM Structured Output (생성 파트만; 출처·모델맵은 파이프라인 조립) ---


class SummaryOutput(BaseModel):
    """개념 요약 태스크 Structured Output."""

    summary: str = Field(description="검색 문맥에 근거한 2~3문장 핵심 요약(명사체)")


class CodeSynthesisOutput(BaseModel):
    """코드 설명·예제 합성 태스크 Structured Output."""

    code_examples: list[CodeExample] = Field(
        default_factory=list,
        description="검색된 코드 청크에 근거한 예제 목록. source는 반드시 제공된 chunk_id 중 하나여야 함")

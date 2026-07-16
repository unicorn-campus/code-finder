"""GraphRAG 검색 모드 선택 (§3.5 [기준]).

규칙(README 기록): 질의 텍스트 신호로 모드 판정, 판단 모호 시 Hybrid 기본값.
- Local  : 특정 개체 중심 정의형 — "뭐예요/무엇/정의/뜻/개념" + 단일 개념
- Global : 주제 요약·탐색형 — "관련 개념/전반/종류/뭐가 있어요/정리/장단점"
- Hybrid : 복합·모호 — 관계형("관계/차이/vs/랑"), 멀티홉("전에 알아야/선행/순서"),
           반론형, 신호 상충·부재
"""
from __future__ import annotations

from typing import Literal

Mode = Literal["local", "global", "hybrid"]

# 주제 요약·탐색형 신호 → Global
_GLOBAL_SIGNALS = (
    "관련 개념", "관련개념", "같이 공부", "뭐가 있", "뭐뭐", "종류", "전반", "전체적",
    "정리해", "요약해", "장단점", "어떤 것들", "어떤것들", "무엇무엇", "생태계", "흐름",
)
# 복합·판단 신호 → Hybrid (관계형·멀티홉·반론형)
# 주의: "랑/와/과" 등 한국어 조사는 과잉 매칭되어 제외(명시적 관계어만 사용)
_HYBRID_SIGNALS = (
    "관계", "차이", "차이점", "vs", "비교", "다른점", "무슨 관계", "어떤 관계",
    "전에", "먼저", "선행", "순서", "before", "먼저 알아", "미리 알아",
    "아니에요", "아닌가", "똑같", "그냥 ", "정말", "진짜로", "필요 없", "필요없",
)
# 정의형 신호 → Local
_LOCAL_SIGNALS = (
    "뭐예요", "뭐야", "무엇", "정의", "뜻", "개념이", "이 뭔", "란?", "이란", "가 뭐",
)


def select_mode(query: str) -> Mode:
    """질의 텍스트 → 검색 모드. 우선순위: Hybrid 신호 > Global 신호 > Local 신호 > 기본 Hybrid."""
    q = query.strip().lower()
    if any(sig.lower() in q for sig in _HYBRID_SIGNALS):
        return "hybrid"
    if any(sig in query for sig in _GLOBAL_SIGNALS):
        return "global"
    if any(sig in query for sig in _LOCAL_SIGNALS):
        return "local"
    return "hybrid"

"""실행 로그 유틸 — 단계·처리 건수·선택 경로(라우팅·검색 모드)를 명확히 표기.

로그 태그 규약(README 참조):
- [query]  질의 분석·재작성 결과
- [react]  4종 도구 팬아웃
- [tool]   개별 도구 결과·건수
- [timeout] 소스 타임아웃·스킵
- [merge]  병합 건수
- [rerank] 리랭킹 전후 건수·모델
- [synthesis] 합성 모델 선택
"""
from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def get_logger(name: str = "code_finder") -> logging.Logger:
    """단일 스트림 핸들러 로거 반환(중복 핸들러 방지)."""
    global _CONFIGURED
    logger = logging.getLogger(name)
    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s | %(message)s", datefmt="%H:%M:%S"))
        root = logging.getLogger("code_finder")
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        root.propagate = False
        _CONFIGURED = True
    return logger

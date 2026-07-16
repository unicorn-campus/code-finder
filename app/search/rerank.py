"""Post 검색 처리 (§3.6) — Cohere 리랭킹으로 병합 결과 재정렬.

- 4종 소스 병합 후보를 하나의 Cohere rerank 호출로 질의 관련도 재정렬(상위 top_n).
- 키 부재·호출 실패 시 원 순서(후보 자체 score) 폴백(추측 생성 없이 안전 저하).
"""
from __future__ import annotations

from typing import Optional

from app.common.config import RerankConfig, load_settings
from app.common.logging_utils import get_logger

log = get_logger()


class Reranker:
    """Cohere 리랭킹 래퍼."""

    def __init__(self, cfg: Optional[RerankConfig] = None):
        self.cfg = cfg or load_settings().rerank

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        """candidates(각 dict에 'rerank_text' 보유) → 관련도 재정렬 상위 top_n.

        각 결과에 'score'(관련도)를 부여함.
        """
        if not candidates:
            return []
        top_n = min(self.cfg.top_n, len(candidates))
        docs = [c.get("rerank_text", "") or "" for c in candidates]

        if not self.cfg.api_key:
            log.warning("[rerank] COHERE_API_KEY 미설정 → 원 순서 폴백")
            return self._fallback(candidates, top_n)

        try:
            import cohere
            client = cohere.Client(api_key=self.cfg.api_key)
            resp = client.rerank(model=self.cfg.model, query=query, documents=docs, top_n=top_n)
            ranked: list[dict] = []
            for r in resp.results:
                c = dict(candidates[r.index])
                c["score"] = round(float(r.relevance_score), 4)
                ranked.append(c)
            log.info("[rerank] cohere(%s): %d→%d", self.cfg.model, len(candidates), len(ranked))
            return ranked
        except Exception as e:  # noqa: BLE001 — 폴백: 원 순서 유지
            log.warning("[rerank] 실패 → 원 순서 폴백: %s", e)
            return self._fallback(candidates, top_n)

    @staticmethod
    def _fallback(candidates: list[dict], top_n: int) -> list[dict]:
        ordered = sorted(candidates, key=lambda c: c.get("score", 0.0), reverse=True)
        return ordered[:top_n]

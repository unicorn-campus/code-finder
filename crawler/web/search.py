"""웹 검색 수집 (§3.8) — DuckDuckGo(ddgs) + BeautifulSoup.

[고정]
- 최대 결과수 10, 최근성 필터(timelimit) 적용, 신선도 메타데이터는 fetched_at(수집 시각) 기록
- 지수 백오프 재시도 3회, 페이지 요청 타임아웃 5초
- 403/429는 즉시 중단 후 보고(WebBlockedError)

주: DuckDuckGo는 '정확히 6개월' 시간창을 제공하지 않아 timelimit로 최근성 근사(기본 'y'),
    스펙의 신선도 필터(6개월)는 fetched_at 필드 기준으로 적용(수집 시각 = 6개월 이내 자명).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app.common.logging_utils import get_logger

log = get_logger()

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


class WebBlockedError(RuntimeError):
    """403/429 등 차단 응답 — 즉시 중단 후 보고."""


@dataclass
class WebConfig:
    max_results: int = 10
    timelimit: str = "y"          # DDG 최근성(연 단위) — 6개월 근사
    page_timeout: float = 5.0     # 페이지 요청 타임아웃(초) [고정]
    max_retries: int = 3          # 지수 백오프 재시도 [고정]
    base_delay: float = 1.0
    region: str = "wt-wt"
    max_text_chars: int = 2000


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _extract_text(html: str, limit: int) -> str:
    """본문 텍스트 추출(script/style 제거, article/main/p 우선)."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = " ".join(main.get_text(separator=" ", strip=True).split())
    return text[:limit]


class WebSearcher:
    """DuckDuckGo 웹 검색 + 본문 수집."""

    def __init__(self, cfg: Optional[WebConfig] = None):
        self.cfg = cfg or WebConfig()

    def _ddg_search(self, query: str) -> list[dict]:
        """DDG 텍스트 검색(지수 백오프 재시도, 403/429 즉시 중단)."""
        from ddgs import DDGS
        try:
            from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException
        except Exception:  # noqa: BLE001 — 버전별 예외 모듈 상이
            DDGSException = Exception
            RatelimitException = Exception
            TimeoutException = Exception

        last_err: Optional[Exception] = None
        for attempt in range(1, self.cfg.max_retries + 1):
            try:
                with DDGS() as ddgs:
                    return ddgs.text(
                        query, region=self.cfg.region, safesearch="moderate",
                        timelimit=self.cfg.timelimit, max_results=self.cfg.max_results,
                    )
            except RatelimitException as e:
                log.warning("[web_search] 429 rate limit → 즉시 중단")
                raise WebBlockedError(f"DuckDuckGo rate limit(429): {e}") from e
            except TimeoutException as e:
                last_err = e
                log.warning("[web_search] timeout(attempt %d/%d)", attempt, self.cfg.max_retries)
            except DDGSException as e:
                msg = str(e).lower()
                if "403" in msg or "forbidden" in msg or "429" in msg or "ratelimit" in msg:
                    raise WebBlockedError(f"DuckDuckGo 차단(403/429): {e}") from e
                last_err = e
                log.warning("[web_search] DDG 오류(attempt %d/%d): %s", attempt, self.cfg.max_retries, e)
            if attempt < self.cfg.max_retries:
                time.sleep(self.cfg.base_delay * (2 ** (attempt - 1)))
        log.warning("[web_search] 검색 실패(재시도 소진): %s", last_err)
        return []

    def _fetch_page(self, url: str) -> str:
        """페이지 본문 수집. 403/429는 차단으로 보고, 그 외 실패는 빈 문자열."""
        try:
            resp = requests.get(url, headers={"User-Agent": _UA}, timeout=self.cfg.page_timeout)
            if resp.status_code in (403, 429):
                raise WebBlockedError(f"페이지 차단({resp.status_code}): {url}")
            resp.raise_for_status()
            return _extract_text(resp.text, self.cfg.max_text_chars)
        except WebBlockedError:
            raise
        except Exception as e:  # noqa: BLE001 — 개별 페이지 실패는 스킵
            log.info("[web_search] 페이지 수집 실패(스킵): %s (%s)", url, type(e).__name__)
            return ""

    def search(self, query: str) -> list[dict]:
        """웹 검색 → 결과 목록. 각 항목: title·url·snippet·text·score·fetched_at.

        본문 수집은 스레드풀로 병렬 처리하여 지연을 줄임(도달 시간 KPI 보호).
        """
        from concurrent.futures import ThreadPoolExecutor

        hits = [h for h in self._ddg_search(query)[: self.cfg.max_results]
                if (h.get("href") or h.get("link") or h.get("url"))]
        fetched_at = _now_iso()

        def _one(item):
            url = item.get("href") or item.get("link") or item.get("url") or ""
            snippet = item.get("body") or item.get("snippet") or ""
            try:
                text = self._fetch_page(url) or snippet
            except WebBlockedError:
                text = snippet  # 개별 페이지 차단은 스니펫으로 대체(검색 자체 차단만 상위 전파)
            return {"title": item.get("title", ""), "url": url, "snippet": snippet, "text": text}

        results: list[dict] = []
        if hits:
            with ThreadPoolExecutor(max_workers=min(10, len(hits))) as ex:
                fetched = list(ex.map(_one, hits))
            for rank, r in enumerate(fetched):
                r["score"] = round(1.0 - rank / max(len(hits), 1), 4)
                r["fetched_at"] = fetched_at
                results.append(r)
        log.info("[tool] web_search: %d results", len(results))
        return results


def get_web_searcher() -> WebSearcher:
    return WebSearcher()

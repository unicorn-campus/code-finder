"""유튜브 영상·자막 수집 (§3.8) — YouTube Data API + 자막 로더.

[고정]
- 영상 검색: YouTube Data API, 최근 6개월 + 조회수 최소 1,000 이상, 최대 결과수 10
- 자막 로드: youtube-transcript-api(한국어·영어), 자막 없는 영상은 스킵 후 로그
- 쿼터 초과(quotaExceeded) 시 캐시 반환
- 수집 데이터에 fetched_at 기록
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.common.logging_utils import get_logger

log = get_logger()

CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"


@dataclass
class YouTubeConfig:
    api_key: Optional[str] = None
    max_results: int = 10
    min_views: int = 1000
    months: int = 6
    transcript_langs: tuple[str, ...] = ("ko", "en")
    max_transcript_chars: int = 3000
    cache_dir: Path = field(default_factory=lambda: CACHE_DIR)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _published_after(months: int) -> str:
    """현재 기준 N개월 전 RFC3339 타임스탬프(UTC)."""
    dt = datetime.now(timezone.utc) - timedelta(days=30 * months)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class YouTubeSearcher:
    """YouTube Data API 검색 + 자막 수집."""

    def __init__(self, cfg: Optional[YouTubeConfig] = None):
        from app.common.config import load_settings
        self.cfg = cfg or YouTubeConfig(api_key=load_settings().youtube_api_key)
        self.cfg.cache_dir.mkdir(parents=True, exist_ok=True)

    # --- 캐시 ---
    def _cache_path(self, query: str) -> Path:
        h = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
        return self.cfg.cache_dir / f"youtube-{h}.json"

    def _read_cache(self, query: str) -> list[dict]:
        p = self._cache_path(query)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return []
        return []

    def _write_cache(self, query: str, results: list[dict]) -> None:
        try:
            self._cache_path(query).write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            log.info("[youtube_search] 캐시 저장 실패: %s", e)

    # --- 자막 ---
    def _load_transcript(self, video_id: str) -> str:
        """자막 로드(한국어·영어 우선). 프록시 실패 시 프록시 없이 재시도, 최종 실패 시 빈 문자열."""
        langs = list(self.cfg.transcript_langs)
        for use_proxy in (True, False):
            try:
                api = self._build_transcript_api(use_proxy=use_proxy)
                fetched = api.fetch(video_id, languages=langs)
                text = " ".join(seg.text for seg in fetched if getattr(seg, "text", "").strip())
                return text[: self.cfg.max_transcript_chars]
            except Exception as e:  # noqa: BLE001 — 자막 없음·차단은 스킵/재시도
                if use_proxy:
                    log.info("[youtube_search] 자막 프록시 실패 → 직접 재시도: %s (%s)",
                             video_id, type(e).__name__)
                    continue
                log.info("[youtube_search] 자막 없음/실패(스킵): %s (%s)", video_id, type(e).__name__)
        return ""

    def _build_transcript_api(self, use_proxy: bool = True):
        """Webshare 프록시 크리덴셜이 있고 use_proxy면 적용(IP 차단 완화)."""
        from youtube_transcript_api import YouTubeTranscriptApi
        import os
        user, pw = os.getenv("YT_WEBSHARE_USER"), os.getenv("YT_WEBSHARE_PASS")
        if use_proxy and user and pw:
            try:
                from youtube_transcript_api.proxies import WebshareProxyConfig
                return YouTubeTranscriptApi(proxy_config=WebshareProxyConfig(
                    proxy_username=user, proxy_password=pw))
            except Exception as e:  # noqa: BLE001
                log.info("[youtube_search] Webshare 프록시 미적용: %s", e)
        return YouTubeTranscriptApi()

    # --- 검색 ---
    def search(self, query: str) -> list[dict]:
        """영상 검색 → 조회수·자막 필터 → 결과 목록.

        각 항목: title·url·video_id·channel·view_count·published_at·transcript·score·fetched_at.
        쿼터 초과 시 캐시 반환.
        """
        if not self.cfg.api_key:
            log.warning("[youtube_search] YOUTUBE_API_KEY 미설정 → 스킵")
            return []
        try:
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except Exception as e:  # noqa: BLE001
            log.warning("[youtube_search] googleapiclient 미설치: %s", e)
            return []

        try:
            youtube = build("youtube", "v3", developerKey=self.cfg.api_key, cache_discovery=False)
            search_resp = youtube.search().list(
                q=query, part="id,snippet", type="video", order="relevance",
                publishedAfter=_published_after(self.cfg.months),
                maxResults=self.cfg.max_results, relevanceLanguage="ko",
            ).execute()
            video_ids = [it["id"]["videoId"] for it in search_resp.get("items", [])
                         if it.get("id", {}).get("videoId")]
            if not video_ids:
                log.info("[tool] youtube_search: 0 videos")
                return []
            stats_resp = youtube.videos().list(
                part="statistics,snippet", id=",".join(video_ids)).execute()
        except HttpError as e:
            reason = str(e)
            if "quotaExceeded" in reason or e.resp.status == 403:
                cached = self._read_cache(query)
                log.warning("[youtube_search] 쿼터 초과/403 → 캐시 %d건 반환", len(cached))
                return cached
            log.warning("[youtube_search] API 오류: %s", e)
            return []
        except Exception as e:  # noqa: BLE001
            log.warning("[youtube_search] 검색 실패: %s", e)
            return []

        fetched_at = _now_iso()
        candidates = []
        for it in stats_resp.get("items", []):
            views = int(it.get("statistics", {}).get("viewCount", 0))
            if views < self.cfg.min_views:
                continue
            vid = it["id"]
            sn = it.get("snippet", {})
            candidates.append({
                "video_id": vid,
                "title": sn.get("title", ""),
                "channel": sn.get("channelTitle", ""),
                "published_at": sn.get("publishedAt", ""),
                "view_count": views,
                "url": f"https://youtu.be/{vid}",
            })
        candidates.sort(key=lambda c: c["view_count"], reverse=True)

        results: list[dict] = []
        for rank, c in enumerate(candidates[: self.cfg.max_results]):
            transcript = self._load_transcript(c["video_id"])
            if not transcript:
                continue  # 자막 없는 영상 스킵
            c["transcript"] = transcript
            c["fetched_at"] = fetched_at
            c["score"] = round(1.0 - rank / max(len(candidates), 1), 4)
            results.append(c)

        if results:
            self._write_cache(query, results)
        log.info("[tool] youtube_search: %d videos (자막 보유)", len(results))
        return results


def get_youtube_searcher() -> YouTubeSearcher:
    return YouTubeSearcher()

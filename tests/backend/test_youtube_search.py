"""유튜브 크롤러 단위 테스트 — Data API·자막 모킹(네트워크 호출 없음)."""
from __future__ import annotations

from crawler.youtube.search import YouTubeConfig, YouTubeSearcher


class _FakeList:
    def __init__(self, resp):
        self.resp = resp

    def execute(self):
        return self.resp


class _FakeYT:
    def search(self):
        class _S:
            def list(self, **kw):
                return _FakeList({"items": [{"id": {"videoId": "v1"}}, {"id": {"videoId": "v2"}}]})
        return _S()

    def videos(self):
        class _V:
            def list(self, **kw):
                return _FakeList({"items": [
                    {"id": "v1", "statistics": {"viewCount": "5000"},
                     "snippet": {"title": "A", "channelTitle": "C", "publishedAt": "2026-06-01T00:00:00Z"}},
                    {"id": "v2", "statistics": {"viewCount": "100"},
                     "snippet": {"title": "B", "channelTitle": "D", "publishedAt": "2026-06-01T00:00:00Z"}},
                ]})
        return _V()


def test_no_api_key_returns_empty():
    assert YouTubeSearcher(YouTubeConfig(api_key=None)).search("q") == []


def test_filters_min_views_and_loads_transcript(monkeypatch):
    import googleapiclient.discovery as disc
    monkeypatch.setattr(disc, "build", lambda *a, **k: _FakeYT())
    ys = YouTubeSearcher(YouTubeConfig(api_key="k", min_views=1000))
    ys._load_transcript = lambda vid: "자막 텍스트"  # type: ignore
    ys._write_cache = lambda *a, **k: None           # type: ignore
    out = ys.search("q")
    assert len(out) == 1                # v2(100회) 필터링
    assert out[0]["video_id"] == "v1"
    assert out[0]["view_count"] == 5000
    assert out[0]["transcript"] == "자막 텍스트"
    assert out[0]["url"] == "https://youtu.be/v1"


def test_skips_videos_without_transcript(monkeypatch):
    import googleapiclient.discovery as disc
    monkeypatch.setattr(disc, "build", lambda *a, **k: _FakeYT())
    ys = YouTubeSearcher(YouTubeConfig(api_key="k", min_views=1000))
    ys._load_transcript = lambda vid: ""             # type: ignore  자막 없음
    ys._write_cache = lambda *a, **k: None           # type: ignore
    assert ys.search("q") == []

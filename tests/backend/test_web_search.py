"""웹 검색 크롤러 단위 테스트 — DDG·페이지 요청 모킹(네트워크 호출 없음)."""
from __future__ import annotations

import pytest

import crawler.web.search as ws
from crawler.web.search import WebBlockedError, WebConfig, WebSearcher


class _FakeResp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


def _fake_ddgs(hits):
    class _D:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, query, **kw):
            return hits

    return _D


def test_search_returns_results(monkeypatch):
    import ddgs
    monkeypatch.setattr(ddgs, "DDGS", _fake_ddgs(
        [{"title": "T", "href": "https://a", "body": "snip"}]))
    monkeypatch.setattr(ws.requests, "get",
                        lambda *a, **k: _FakeResp(200, "<html><body><article>본문 콘텐츠</article></body></html>"))
    out = WebSearcher(WebConfig(max_retries=1)).search("q")
    assert len(out) == 1
    assert out[0]["url"] == "https://a"
    assert "본문 콘텐츠" in out[0]["text"]
    assert out[0]["fetched_at"]


def test_page_block_falls_back_to_snippet(monkeypatch):
    import ddgs
    monkeypatch.setattr(ddgs, "DDGS", _fake_ddgs(
        [{"title": "T", "href": "https://a", "body": "스니펫"}]))
    monkeypatch.setattr(ws.requests, "get", lambda *a, **k: _FakeResp(429))
    out = WebSearcher(WebConfig(max_retries=1)).search("q")
    # 개별 페이지 차단(429)은 검색 자체를 막지 않고 스니펫으로 대체됨
    assert out[0]["text"] == "스니펫"


def test_search_level_ratelimit_raises_blocked(monkeypatch):
    ratelimit = pytest.importorskip("ddgs.exceptions").RatelimitException
    import ddgs

    class _D:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, query, **kw):
            raise ratelimit("429 rate limit")

    monkeypatch.setattr(ddgs, "DDGS", _D)
    with pytest.raises(WebBlockedError):
        WebSearcher(WebConfig(max_retries=1)).search("q")

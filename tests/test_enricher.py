"""Enricher tests — no real network. Stub requests.get with fake responses."""

from __future__ import annotations

import pytest

from instagram_saved_mcp import enricher
from instagram_saved_mcp.enricher import (
    EnrichError,
    LoginWallError,
    NotFoundError,
    RateLimitError,
)

POST_URL = "https://www.instagram.com/p/ABC123/"


class FakeResp:
    def __init__(self, text="", url=POST_URL, status_code=200):
        self.text = text
        self.url = url
        self.status_code = status_code


def _patch(monkeypatch, resp: FakeResp):
    monkeypatch.setattr(enricher.requests, "get", lambda url, **kw: resp)


OG_HTML = (
    '<html><head>'
    '<meta property="og:title" content="Chef (@chef) • Instagram">'
    '<meta property="og:description" content="1,234 likes, 56 comments - chef on '
    'January 1, 2024: &quot;Best #pasta #yum&quot;">'
    '<meta property="og:image" content="https://cdn.example/img.jpg">'
    '</head></html>'
)


def test_enrich_parses_og_tags(monkeypatch):
    _patch(monkeypatch, FakeResp(OG_HTML))
    result = enricher.enrich(POST_URL)
    assert result["caption"] == "Best #pasta #yum"
    assert result["author"] == "chef"
    assert result["hashtags"] == ["#pasta", "#yum"]
    assert result["image_url"] == "https://cdn.example/img.jpg"


@pytest.mark.parametrize("bad", [
    "https://example.com/p/ABC/",
    "https://www.instagram.com/chef/",        # profile, not a post
    "not-a-url",
])
def test_invalid_url_rejected(monkeypatch, bad):
    _patch(monkeypatch, FakeResp(OG_HTML))
    with pytest.raises(EnrichError):
        enricher.enrich(bad)


def test_login_wall_by_redirect(monkeypatch):
    _patch(monkeypatch, FakeResp("<html></html>", url="https://www.instagram.com/accounts/login/?next=/p/ABC123/"))
    with pytest.raises(LoginWallError):
        enricher.enrich(POST_URL)


def test_login_wall_by_missing_og(monkeypatch):
    _patch(monkeypatch, FakeResp("<html><head><title>Login • Instagram</title></head></html>"))
    with pytest.raises(LoginWallError):
        enricher.enrich(POST_URL)


def test_rate_limited(monkeypatch):
    _patch(monkeypatch, FakeResp("", status_code=429))
    with pytest.raises(RateLimitError):
        enricher.enrich(POST_URL)


def test_not_found(monkeypatch):
    _patch(monkeypatch, FakeResp("", status_code=404))
    with pytest.raises(NotFoundError):
        enricher.enrich(POST_URL)


def test_reel_url_allowed(monkeypatch):
    _patch(monkeypatch, FakeResp(OG_HTML))
    result = enricher.enrich("https://www.instagram.com/reel/XYZ789/")
    assert result["author"] == "chef"

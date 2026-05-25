"""Best-effort enrichment of a public Instagram post page.

No login, no API, no credentials — a single GET of the public URL, then parse
the Open Graph meta tags. Instagram gates aggressively, so being served a login
wall, a redirect, or a 429 is an *expected* outcome, not a crash: those map to
typed exceptions the server turns into clean messages.

og:description → caption (+ hashtags)   og:title → author   og:image → image_url
"""

from __future__ import annotations

import re
from typing import Any

import requests
from bs4 import BeautifulSoup

from . import config

#: Public post/reel URL shapes Instagram uses.
_URL_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/[A-Za-z0-9_-]+",
    re.IGNORECASE,
)
#: Leading "1,234 likes, 56 comments - username on <date>:" noise in og:description.
_CAPTION_PREFIX_RE = re.compile(
    r"^\s*[\d,]+\s+likes?,\s*[\d,]+\s+comments?\s*-\s*.*?:\s*",
    re.IGNORECASE,
)
_AUTHOR_RE = re.compile(r"@([A-Za-z0-9_.]+)")
_HASHTAG_RE = re.compile(r"#(\w+)")


class EnrichError(Exception):
    """Base class for any failure to enrich a post."""


class LoginWallError(EnrichError):
    """Instagram served a login wall / redirected to /accounts/login."""


class RateLimitError(EnrichError):
    """Instagram rate-limited the request (HTTP 429)."""


class NotFoundError(EnrichError):
    """Post is deleted, private, or the URL is wrong (HTTP 404)."""


def _looks_like_login_wall(final_url: str, soup: BeautifulSoup) -> bool:
    if "/accounts/login" in final_url:
        return True
    title = (soup.title.string or "") if soup.title else ""
    if "login" in title.lower():
        return True
    # No og tags at all is the tell-tale sign of a gated page.
    return soup.find("meta", property="og:description") is None and (
        soup.find("meta", property="og:title") is None
    )


def _meta(soup: BeautifulSoup, prop: str) -> str | None:
    tag = soup.find("meta", property=prop)
    content = tag.get("content") if tag else None
    return content.strip() if isinstance(content, str) and content.strip() else None


def _clean_caption(description: str) -> str:
    text = _CAPTION_PREFIX_RE.sub("", description).strip()
    # Strip a single pair of wrapping quotes Instagram adds around the caption.
    if len(text) >= 2 and text[0] in "\"“" and text[-1] in "\"”":
        text = text[1:-1].strip()
    return text


def _validate(url: str) -> str:
    url = url.strip()
    if not _URL_RE.match(url):
        raise EnrichError(
            f"Not a recognizable public Instagram post/reel URL: {url!r}"
        )
    return url


def enrich(url: str) -> dict[str, Any]:
    """Fetch and parse a public post. Returns ``{url, caption, author, hashtags, image_url}``.

    Raises a typed :class:`EnrichError` subclass on any blocked/failed state.
    """
    url = _validate(url)
    try:
        resp = requests.get(
            url,
            headers=config.HTTP_HEADERS,
            timeout=config.REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except requests.Timeout as exc:
        raise EnrichError(f"Timed out fetching {url}") from exc
    except requests.RequestException as exc:
        raise EnrichError(f"Network error fetching {url}: {exc}") from exc

    if resp.status_code == 429:
        raise RateLimitError(
            "Instagram rate-limited this request. Wait a while before retrying."
        )
    if resp.status_code == 404:
        raise NotFoundError("Post not found — it may be deleted or private.")
    if resp.status_code >= 400:
        raise EnrichError(f"Instagram returned HTTP {resp.status_code} for {url}")

    soup = BeautifulSoup(resp.text, "html.parser")
    if _looks_like_login_wall(str(resp.url), soup):
        raise LoginWallError(
            "Instagram served a login wall for this post (public scraping is "
            "best-effort and often blocked). No data could be extracted."
        )

    description = _meta(soup, "og:description") or ""
    title = _meta(soup, "og:title") or ""
    image_url = _meta(soup, "og:image")

    caption = _clean_caption(description) if description else None
    author_match = _AUTHOR_RE.search(title) or _AUTHOR_RE.search(description)
    author = author_match.group(1) if author_match else None
    hashtags = [f"#{tag}" for tag in _HASHTAG_RE.findall(caption or "")]

    return {
        "url": url,
        "caption": caption,
        "author": author,
        "hashtags": hashtags,
        "image_url": image_url,
    }

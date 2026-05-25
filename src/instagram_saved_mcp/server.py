"""FastMCP server exposing Instagram Saved posts to MCP clients.

This module is the orchestration + error boundary. Tool bodies are thin: they
call the pure/typed lower layers (parser, enricher, cache, transcriber) and
translate any exception into a clean ``{"error": ...}`` payload. A stack trace
must never reach the AI client.
"""

from __future__ import annotations

import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import cache, config, enricher, parser, transcriber

mcp = FastMCP("instagram-saved-mcp")

_EMPTY_HINT = "No saved posts indexed yet. Run refresh_index(zip_path) with your Instagram export first."


@mcp.tool()
def list_collections() -> dict[str, Any]:
    """List every saved-post collection and how many posts each contains.

    Reads the local index. Uncollected posts are grouped under "All Posts".
    """
    try:
        collections = cache.list_collections()
        if not collections:
            return {"collections": [], "hint": _EMPTY_HINT}
        return {"collections": collections}
    except Exception as exc:  # noqa: BLE001 - boundary: never leak a traceback
        return {"error": f"Could not read collections: {exc}"}


@mcp.tool()
def list_saved(collection: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List saved posts (URL, collection, saved-on timestamp), newest first.

    Args:
        collection: Optional collection name to filter by (e.g. "Recipes", "All Posts").
        limit: Maximum number of posts to return (default 50).
    """
    try:
        posts = cache.list_saved(collection=collection, limit=limit)
        if not posts:
            if cache.count_posts() == 0:
                return {"posts": [], "hint": _EMPTY_HINT}
            return {"posts": [], "hint": f"No posts found for collection {collection!r}."}
        return {"posts": posts, "count": len(posts)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Could not list saved posts: {exc}"}


@mcp.tool()
def get_post(url: str) -> dict[str, Any]:
    """Get details for one saved post: caption, author, hashtags, image URL.

    Returns the cached record if already enriched. Otherwise fetches the public
    post page once (best-effort — Instagram often serves a login wall to
    unauthenticated requests) and caches the result. A login-wall / rate-limit /
    not-found outcome is returned as a clean message, not an error to retry blindly.

    Args:
        url: A public Instagram post or reel URL (https://www.instagram.com/p/<code>/).
    """
    try:
        cached = cache.get_cached(url)
        if cached and cached.get("enriched_at"):
            return {**cached, "cached": True}

        data = enricher.enrich(url)
        cache.update_enrichment(
            url,
            caption=data["caption"],
            author=data["author"],
            hashtags=data["hashtags"],
            image_url=data["image_url"],
        )
        stored = cache.get_cached(url) or data
        return {**stored, "cached": False}
    except enricher.LoginWallError as exc:
        return {"error": str(exc), "error_type": "login_wall"}
    except enricher.RateLimitError as exc:
        return {"error": str(exc), "error_type": "rate_limited"}
    except enricher.NotFoundError as exc:
        return {"error": str(exc), "error_type": "not_found"}
    except enricher.EnrichError as exc:
        return {"error": str(exc), "error_type": "enrich_failed"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error enriching post: {exc}"}


@mcp.tool()
def search_saved(query: str) -> dict[str, Any]:
    """Search enriched posts by caption, hashtag, or author.

    Only posts already enriched via get_post are searchable. Case-insensitive
    substring match.

    Args:
        query: Text to look for in captions, hashtags, or author usernames.
    """
    try:
        results = cache.search(query)
        if not results:
            return {
                "results": [],
                "hint": "No matches. Enrich posts with get_post(url) to make them searchable.",
            }
        return {"results": results, "count": len(results)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Search failed: {exc}"}


@mcp.tool()
def transcribe_post(url: str) -> dict[str, Any]:
    """Transcribe a saved reel/video (v0.2 — NOT YET IMPLEMENTED).

    WARNING: when implemented, this will DOWNLOAD the video to your machine in
    order to transcribe it. v0.1 returns a stub message and downloads nothing.

    Args:
        url: A public Instagram reel/video URL.
    """
    try:
        return {
            "status": "not_implemented",
            "warning": "When implemented (v0.2), transcribe_post DOWNLOADS the reel/video locally to transcribe it.",
            "message": transcriber.transcribe(url),
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error: {exc}"}


@mcp.tool()
def refresh_index(zip_path: str) -> dict[str, Any]:
    """Re-parse an Instagram data export and update the local index.

    Accepts the export ZIP or an already-extracted folder. Updates which
    collection each post belongs to and when it was saved, without discarding
    any enrichment (captions/authors) already fetched.

    Args:
        zip_path: Path to the Instagram export ZIP or its extracted folder.
    """
    try:
        posts = parser.load_export(zip_path)
        imported = cache.upsert_saved(posts)
        return {
            "imported": imported,
            "collections": cache.list_collections(),
            "db_path": str(config.db_path()),
        }
    except parser.ParserError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Unexpected error reading export: {exc}"}


def _auto_import() -> None:
    """Import an export named by INSTAGRAM_SAVED_EXPORT if the DB is empty."""
    path = config.export_path()
    if not path or cache.count_posts() > 0:
        return
    try:
        posts = parser.load_export(path)
        n = cache.upsert_saved(posts)
        print(f"[instagram-saved-mcp] auto-imported {n} posts from {path}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - never block startup on a bad export
        print(f"[instagram-saved-mcp] auto-import skipped: {exc}", file=sys.stderr)


def main() -> None:
    """Console entry point: initialize storage, then serve over stdio."""
    cache.init_db()
    _auto_import()
    mcp.run()


if __name__ == "__main__":
    main()

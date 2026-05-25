"""Configuration: storage paths, environment overrides, HTTP settings.

Single source of truth for where the SQLite cache lives and how the enricher
talks to the network. No credentials are read or stored anywhere.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Environment variable names (documented in the README) -----------------

#: Override the SQLite cache location.
ENV_DB_PATH = "INSTAGRAM_SAVED_MCP_DB"
#: Optional path to an export ZIP/folder; auto-imported on startup if the DB is empty.
ENV_EXPORT_PATH = "INSTAGRAM_SAVED_EXPORT"

#: Default directory holding the cache when no override is set.
DEFAULT_DIR = Path.home() / ".instagram-saved-mcp"
DEFAULT_DB_NAME = "cache.db"


def db_path() -> Path:
    """Resolve the cache DB path and ensure its parent directory exists.

    Honors ``INSTAGRAM_SAVED_MCP_DB``; otherwise ``~/.instagram-saved-mcp/cache.db``.
    """
    override = os.environ.get(ENV_DB_PATH, "").strip()
    path = Path(override).expanduser() if override else DEFAULT_DIR / DEFAULT_DB_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def export_path() -> str | None:
    """Optional export path for startup auto-import, or ``None`` if unset."""
    value = os.environ.get(ENV_EXPORT_PATH, "").strip()
    return value or None


# --- HTTP settings for the public-page enricher -----------------------------

#: Seconds before an enrichment request is abandoned.
REQUEST_TIMEOUT = 15

#: Browser-like headers. Instagram fingerprints bare clients aggressively; this
#: improves the odds of getting real HTML instead of a login wall, but is not a
#: guarantee — the enricher treats blocking as an expected outcome.
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

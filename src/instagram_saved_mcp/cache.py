"""SQLite cache: the single local store for saved posts and enrichment.

One table, one file, local to the user's machine. The saved-index import
(``upsert_saved``) and the public-page enrichment (``update_enrichment``) write
to the same rows but never clobber each other's columns.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    url         TEXT PRIMARY KEY,
    collection  TEXT,
    timestamp   TEXT,
    caption     TEXT,
    author      TEXT,
    hashtags    TEXT,
    image_url   TEXT,
    transcript  TEXT,
    enriched_at TEXT
);
"""


#: DB paths whose schema has been ensured this process (avoids ordering bugs).
_initialized_paths: set[str] = set()


def _connect() -> sqlite3.Connection:
    path = config.db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    key = str(path)
    if key not in _initialized_paths:
        conn.executescript(SCHEMA)
        conn.commit()
        _initialized_paths.add(key)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    raw = data.get("hashtags")
    if raw:
        try:
            data["hashtags"] = json.loads(raw)
        except (ValueError, TypeError):
            data["hashtags"] = []
    else:
        data["hashtags"] = []
    return data


def init_db() -> None:
    """Create the schema if it does not yet exist. Safe to call repeatedly."""
    with closing(_connect()) as conn, conn:
        conn.executescript(SCHEMA)


def upsert_saved(posts: Iterable[dict[str, Any]]) -> int:
    """Insert/update saved-index rows (url, collection, timestamp).

    Preserves any existing enrichment columns — re-importing a fresh export only
    refreshes which collection a post is in and when it was saved.
    Returns the number of rows processed.
    """
    rows = [(p["url"], p.get("collection"), p.get("timestamp")) for p in posts]
    if not rows:
        return 0
    with closing(_connect()) as conn, conn:
        conn.executemany(
            """
            INSERT INTO posts (url, collection, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                collection = excluded.collection,
                timestamp  = excluded.timestamp
            """,
            rows,
        )
    return len(rows)


def get_cached(url: str) -> dict[str, Any] | None:
    """Return the stored row for ``url`` (with hashtags parsed), or ``None``."""
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM posts WHERE url = ?", (url,)).fetchone()
    return _row_to_dict(row) if row else None


def update_enrichment(
    url: str,
    *,
    caption: str | None,
    author: str | None,
    hashtags: list[str] | None,
    image_url: str | None,
) -> None:
    """Store enrichment for ``url``, inserting the row if it was not saved-indexed."""
    tags = json.dumps(hashtags or [])
    with closing(_connect()) as conn, conn:
        conn.execute(
            """
            INSERT INTO posts (url, caption, author, hashtags, image_url, enriched_at)
            VALUES (:url, :caption, :author, :hashtags, :image_url, :enriched_at)
            ON CONFLICT(url) DO UPDATE SET
                caption     = excluded.caption,
                author      = excluded.author,
                hashtags    = excluded.hashtags,
                image_url   = excluded.image_url,
                enriched_at = excluded.enriched_at
            """,
            {
                "url": url,
                "caption": caption,
                "author": author,
                "hashtags": tags,
                "image_url": image_url,
                "enriched_at": _now(),
            },
        )


def update_transcript(url: str, transcript: str) -> None:
    """Store a transcript for ``url`` (used by the v0.2 transcriber)."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            """
            INSERT INTO posts (url, transcript) VALUES (?, ?)
            ON CONFLICT(url) DO UPDATE SET transcript = excluded.transcript
            """,
            (url, transcript),
        )


def search(query: str) -> list[dict[str, Any]]:
    """Find enriched posts whose caption, hashtags, or author match ``query``."""
    like = f"%{query}%"
    with closing(_connect()) as conn:
        rows = conn.execute(
            """
            SELECT * FROM posts
            WHERE enriched_at IS NOT NULL
              AND (caption LIKE ? OR hashtags LIKE ? OR author LIKE ?)
            ORDER BY timestamp DESC
            """,
            (like, like, like),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def list_collections() -> list[dict[str, Any]]:
    """Return every collection name with its post count, largest first."""
    with closing(_connect()) as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(collection, 'All Posts') AS collection, COUNT(*) AS count
            FROM posts
            GROUP BY COALESCE(collection, 'All Posts')
            ORDER BY count DESC, collection ASC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def list_saved(collection: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Return saved posts (url, collection, timestamp), newest first."""
    sql = "SELECT url, collection, timestamp FROM posts"
    params: list[Any] = []
    if collection:
        sql += " WHERE COALESCE(collection, 'All Posts') = ?"
        params.append(collection)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    with closing(_connect()) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def count_posts() -> int:
    """Total rows in the cache (used to detect an empty DB for auto-import)."""
    with closing(_connect()) as conn:
        return conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

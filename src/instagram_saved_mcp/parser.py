"""Parse an Instagram data export into saved-post records.

Pure: no network, no database. Accepts either the export ZIP or an already
extracted folder. Two files matter, both under ``your_instagram_activity/saved/``:

* ``saved_posts.json``      — every saved item: ``saved_saved_media[].{title, string_map_data["Saved on"].{href, timestamp|value}}``
* ``saved_collections.json``— named collections, encoded *positionally*: a
  ``title == "Collection"`` header row names the collection, and the rows that
  follow (until the next header) are its members.

Collections are NOT recorded inside ``saved_posts.json``, so we read both and
union them by URL. A post not in any named collection is labelled "All Posts".

Both a modern Unix-seconds ``timestamp`` and the older human-readable ``value``
date string are handled.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAVED_POSTS_SUFFIX = "saved/saved_posts.json"
SAVED_COLLECTIONS_SUFFIX = "saved/saved_collections.json"
UNCATEGORIZED = "All Posts"

# Legacy exports format dates like "Oct 26, 2017, 5:10 PM".
_LEGACY_DATE_FORMAT = "%b %d, %Y, %I:%M %p"


class ParserError(Exception):
    """Raised when an export cannot be located or understood."""


# --- locating + loading the JSON files --------------------------------------


def _load_json_bytes(raw: bytes, label: str) -> Any:
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ParserError(f"{label} is not valid JSON: {exc}") from exc


def _read_from_zip(zip_path: Path) -> tuple[Any, Any | None]:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            posts_name = _match_suffix(names, SAVED_POSTS_SUFFIX)
            if posts_name is None:
                raise ParserError(
                    f"saved_posts.json not found in {zip_path.name}. "
                    "Is this an Instagram data export ZIP?"
                )
            posts = _load_json_bytes(zf.read(posts_name), "saved_posts.json")
            coll_name = _match_suffix(names, SAVED_COLLECTIONS_SUFFIX)
            collections = (
                _load_json_bytes(zf.read(coll_name), "saved_collections.json")
                if coll_name
                else None
            )
            return posts, collections
    except zipfile.BadZipFile as exc:
        raise ParserError(f"{zip_path.name} is not a valid ZIP file.") from exc


def _read_from_folder(folder: Path) -> tuple[Any, Any | None]:
    posts_file = next(iter(folder.glob(f"**/{SAVED_POSTS_SUFFIX}")), None)
    if posts_file is None:
        raise ParserError(
            f"saved_posts.json not found under {folder}. "
            "Point this at the extracted export (or the ZIP itself)."
        )
    posts = _load_json_bytes(posts_file.read_bytes(), "saved_posts.json")
    coll_file = next(iter(folder.glob(f"**/{SAVED_COLLECTIONS_SUFFIX}")), None)
    collections = (
        _load_json_bytes(coll_file.read_bytes(), "saved_collections.json")
        if coll_file
        else None
    )
    return posts, collections


def _match_suffix(names: list[str], suffix: str) -> str | None:
    """Find a ZIP member whose normalized path ends with ``suffix``."""
    for name in names:
        if name.replace("\\", "/").endswith(suffix):
            return name
    return None


# --- normalizing fields -----------------------------------------------------


def _iso_timestamp(entry: dict[str, Any]) -> str | None:
    """Convert a ``string_map_data`` value (``{timestamp}`` or ``{value}``) to ISO-8601."""
    ts = entry.get("timestamp")
    if isinstance(ts, (int, float)) and ts > 0:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    value = entry.get("value")
    if isinstance(value, str) and value.strip():
        try:
            return datetime.strptime(value.strip(), _LEGACY_DATE_FORMAT).isoformat()
        except ValueError:
            return value.strip()  # keep the raw string if the format is unexpected
    return None


# --- parsing each file -------------------------------------------------------


def parse_saved_posts(data: Any) -> list[dict[str, Any]]:
    """Extract ``[{url, timestamp, author}]`` from saved_posts.json content."""
    media = data.get("saved_saved_media") if isinstance(data, dict) else None
    if media is None:
        raise ParserError(
            "saved_posts.json is missing the 'saved_saved_media' key — "
            "unexpected export format."
        )
    posts: list[dict[str, Any]] = []
    for item in media:
        smd = item.get("string_map_data", {})
        saved_on = smd.get("Saved on", {})
        url = saved_on.get("href")
        if not url:
            continue
        posts.append(
            {
                "url": url,
                "timestamp": _iso_timestamp(saved_on),
                "author": item.get("title"),
            }
        )
    return posts


def parse_collections(data: Any) -> list[dict[str, Any]]:
    """Extract collection members ``[{url, collection, timestamp, author}]``.

    Uses the positional grouping: a header row sets the current collection name,
    following member rows belong to it.
    """
    if not isinstance(data, dict):
        return []
    entries = data.get("saved_saved_collections", [])
    members: list[dict[str, Any]] = []
    current: str | None = None
    for item in entries:
        smd = item.get("string_map_data", {})
        if item.get("title") == "Collection":
            name = smd.get("Name", {}).get("value")
            current = name.strip() if isinstance(name, str) and name.strip() else "Unnamed Collection"
            continue
        if current is None:
            continue
        url, author = _member_href(smd)
        if not url:
            continue
        added = smd.get("Added Time") or smd.get("Saved on") or {}
        members.append(
            {
                "url": url,
                "collection": current,
                "timestamp": _iso_timestamp(added) if added else None,
                "author": author,
            }
        )
    return members


def _member_href(smd: dict[str, Any]) -> tuple[str | None, str | None]:
    """A collection member's post URL + author username.

    Normally under ``Name`` (``{href, value}``); fall back to any entry with an href.
    """
    name = smd.get("Name")
    if isinstance(name, dict) and name.get("href"):
        return name.get("href"), name.get("value")
    for entry in smd.values():
        if isinstance(entry, dict) and entry.get("href"):
            return entry.get("href"), entry.get("value")
    return None, None


# --- public entry point ------------------------------------------------------


def load_export(path: str | Path) -> list[dict[str, Any]]:
    """Parse an export (ZIP or folder) into ``[{url, collection, timestamp}]``.

    Posts from both files are unioned by URL and labelled with their collection
    ("All Posts" when uncollected). Raises :class:`ParserError` on any problem.
    """
    p = Path(path).expanduser()
    if not p.exists():
        raise ParserError(f"Export path does not exist: {p}")

    if p.is_dir():
        posts_data, collections_data = _read_from_folder(p)
    elif zipfile.is_zipfile(p):
        posts_data, collections_data = _read_from_zip(p)
    else:
        raise ParserError(
            f"{p} is neither a folder nor a ZIP. Provide the Instagram export "
            "ZIP or its extracted folder."
        )

    saved = parse_saved_posts(posts_data)
    collection_members = parse_collections(collections_data) if collections_data else []

    merged: dict[str, dict[str, Any]] = {}
    for post in saved:
        merged[post["url"]] = {
            "url": post["url"],
            "collection": None,
            "timestamp": post.get("timestamp"),
        }
    for member in collection_members:
        url = member["url"]
        existing = merged.get(url)
        if existing:
            existing["collection"] = member["collection"]
            if not existing.get("timestamp"):
                existing["timestamp"] = member.get("timestamp")
        else:
            # Collected post not present in saved_posts.json — keep it anyway.
            merged[url] = {
                "url": url,
                "collection": member["collection"],
                "timestamp": member.get("timestamp"),
            }

    for record in merged.values():
        if not record["collection"]:
            record["collection"] = UNCATEGORIZED

    return list(merged.values())

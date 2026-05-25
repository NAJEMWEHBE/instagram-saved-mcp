"""Parser tests — no network. Cover both timestamp formats, collection
grouping, ZIP + folder input, missing-collections, and error cases."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from instagram_saved_mcp import parser
from instagram_saved_mcp.parser import ParserError

URL_RECIPE = "https://www.instagram.com/p/DVQtFLqEoFv/"
URL_TRAVEL = "https://www.instagram.com/reel/ABC123/"
URL_LOOSE = "https://www.instagram.com/p/UNCOLL1/"

SAVED_POSTS = {
    "saved_saved_media": [
        {
            "title": "cretivox",
            "string_map_data": {"Saved on": {"href": URL_RECIPE, "timestamp": 1772374049}},
        },
        {
            "title": "natgeo",
            "string_map_data": {"Saved on": {"href": URL_TRAVEL, "timestamp": 1700000000}},
        },
        {
            "title": "someone",
            "string_map_data": {"Saved on": {"href": URL_LOOSE, "timestamp": 1710000000}},
        },
    ]
}

SAVED_COLLECTIONS = {
    "saved_saved_collections": [
        {"title": "Collection", "string_map_data": {"Name": {"value": "Recipes"}}},
        {
            "string_map_data": {
                "Name": {"href": URL_RECIPE, "value": "cretivox"},
                "Added Time": {"timestamp": 1772374100},
            }
        },
        {"title": "Collection", "string_map_data": {"Name": {"value": "Travel"}}},
        {
            "string_map_data": {
                "Name": {"href": URL_TRAVEL, "value": "natgeo"},
                "Added Time": {"timestamp": 1700000100},
            }
        },
    ]
}

LEGACY_POSTS = {
    "saved_saved_media": [
        {
            "title": "throwback",
            "string_map_data": {
                "Saved on": {
                    "href": "https://www.instagram.com/p/OLD123/",
                    "value": "Oct 26, 2017, 5:10 PM",
                }
            },
        }
    ]
}


def _write_folder(root: Path, posts: dict, collections: dict | None = None) -> Path:
    saved = root / "your_instagram_activity" / "saved"
    saved.mkdir(parents=True)
    (saved / "saved_posts.json").write_text(json.dumps(posts), encoding="utf-8")
    if collections is not None:
        (saved / "saved_collections.json").write_text(json.dumps(collections), encoding="utf-8")
    return root


def _write_zip(zip_path: Path, posts: dict, collections: dict | None = None) -> Path:
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("your_instagram_activity/saved/saved_posts.json", json.dumps(posts))
        if collections is not None:
            zf.writestr(
                "your_instagram_activity/saved/saved_collections.json",
                json.dumps(collections),
            )
    return zip_path


def _by_url(records: list[dict]) -> dict[str, dict]:
    return {r["url"]: r for r in records}


# --- timestamp formats -------------------------------------------------------


def test_current_unix_timestamp_parsed_to_iso():
    posts = parser.parse_saved_posts(SAVED_POSTS)
    rec = _by_url(posts)[URL_TRAVEL]
    assert rec["timestamp"].startswith("2023-11")  # 1700000000 = Nov 2023 UTC


def test_legacy_value_date_string_parsed():
    posts = parser.parse_saved_posts(LEGACY_POSTS)
    assert posts[0]["timestamp"] == "2017-10-26T17:10:00"


def test_unparseable_legacy_value_kept_raw():
    data = {
        "saved_saved_media": [
            {"string_map_data": {"Saved on": {"href": "https://www.instagram.com/p/X/", "value": "sometime"}}}
        ]
    }
    assert parser.parse_saved_posts(data)[0]["timestamp"] == "sometime"


# --- collection grouping -----------------------------------------------------


def test_collections_positional_grouping():
    members = parser.parse_collections(SAVED_COLLECTIONS)
    mapping = {m["url"]: m["collection"] for m in members}
    assert mapping[URL_RECIPE] == "Recipes"
    assert mapping[URL_TRAVEL] == "Travel"


def test_merge_labels_collections_and_all_posts(tmp_path):
    root = _write_folder(tmp_path / "export", SAVED_POSTS, SAVED_COLLECTIONS)
    by_url = _by_url(parser.load_export(root))
    assert by_url[URL_RECIPE]["collection"] == "Recipes"
    assert by_url[URL_TRAVEL]["collection"] == "Travel"
    assert by_url[URL_LOOSE]["collection"] == "All Posts"


# --- input shapes ------------------------------------------------------------


def test_load_from_folder(tmp_path):
    root = _write_folder(tmp_path / "export", SAVED_POSTS, SAVED_COLLECTIONS)
    assert len(parser.load_export(root)) == 3


def test_load_from_zip(tmp_path):
    zip_path = _write_zip(tmp_path / "export.zip", SAVED_POSTS, SAVED_COLLECTIONS)
    by_url = _by_url(parser.load_export(zip_path))
    assert by_url[URL_RECIPE]["collection"] == "Recipes"
    assert len(by_url) == 3


def test_missing_collections_file_all_posts(tmp_path):
    root = _write_folder(tmp_path / "export", SAVED_POSTS)  # no collections file
    by_url = _by_url(parser.load_export(root))
    assert all(r["collection"] == "All Posts" for r in by_url.values())


# --- error cases -------------------------------------------------------------


def test_missing_path_raises(tmp_path):
    with pytest.raises(ParserError, match="does not exist"):
        parser.load_export(tmp_path / "nope.zip")


def test_missing_saved_posts_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ParserError, match="saved_posts.json not found"):
        parser.load_export(empty)


def test_bad_json_raises(tmp_path):
    saved = tmp_path / "export" / "your_instagram_activity" / "saved"
    saved.mkdir(parents=True)
    (saved / "saved_posts.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ParserError, match="not valid JSON"):
        parser.load_export(tmp_path / "export")


def test_unexpected_format_raises(tmp_path):
    root = tmp_path / "export"
    saved = root / "your_instagram_activity" / "saved"
    saved.mkdir(parents=True)
    (saved / "saved_posts.json").write_text(json.dumps({"wrong_key": []}), encoding="utf-8")
    with pytest.raises(ParserError, match="saved_saved_media"):
        parser.load_export(root)

"""Cache tests — isolated SQLite file per test via the DB-path env override."""

from __future__ import annotations

import pytest

from instagram_saved_mcp import cache

URL_A = "https://www.instagram.com/p/AAA/"
URL_B = "https://www.instagram.com/p/BBB/"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("INSTAGRAM_SAVED_MCP_DB", str(tmp_path / "cache.db"))
    cache._initialized_paths.clear()
    cache.init_db()
    return cache


def test_upsert_and_get(db):
    db.upsert_saved([{"url": URL_A, "collection": "Recipes", "timestamp": "2024-01-01T00:00:00+00:00"}])
    row = db.get_cached(URL_A)
    assert row["collection"] == "Recipes"
    assert row["enriched_at"] is None
    assert row["hashtags"] == []


def test_enrichment_then_reimport_preserves_it(db):
    db.upsert_saved([{"url": URL_A, "collection": "Recipes", "timestamp": "2024-01-01T00:00:00+00:00"}])
    db.update_enrichment(URL_A, caption="hello #world", author="chef", hashtags=["#world"], image_url="https://img")
    # Re-import with a changed collection must NOT wipe enrichment.
    db.upsert_saved([{"url": URL_A, "collection": "Favourites", "timestamp": "2024-02-02T00:00:00+00:00"}])
    row = db.get_cached(URL_A)
    assert row["collection"] == "Favourites"        # refreshed
    assert row["caption"] == "hello #world"          # preserved
    assert row["author"] == "chef"                   # preserved
    assert row["hashtags"] == ["#world"]             # preserved + parsed to list


def test_search_only_enriched(db):
    db.upsert_saved([
        {"url": URL_A, "collection": "Recipes", "timestamp": "2024-01-01T00:00:00+00:00"},
        {"url": URL_B, "collection": "Recipes", "timestamp": "2024-01-02T00:00:00+00:00"},
    ])
    db.update_enrichment(URL_A, caption="best pasta ever", author="chef", hashtags=["#pasta"], image_url=None)
    assert [r["url"] for r in db.search("pasta")] == [URL_A]
    assert db.search("nonexistent") == []
    assert db.search("BBB") == []  # B not enriched → not searchable


def test_list_collections_counts(db):
    db.upsert_saved([
        {"url": URL_A, "collection": "Recipes", "timestamp": "2024-01-01T00:00:00+00:00"},
        {"url": URL_B, "collection": "All Posts", "timestamp": "2024-01-02T00:00:00+00:00"},
    ])
    counts = {c["collection"]: c["count"] for c in db.list_collections()}
    assert counts == {"Recipes": 1, "All Posts": 1}


def test_list_saved_filter_and_limit(db):
    db.upsert_saved([
        {"url": URL_A, "collection": "Recipes", "timestamp": "2024-01-01T00:00:00+00:00"},
        {"url": URL_B, "collection": "Travel", "timestamp": "2024-03-03T00:00:00+00:00"},
    ])
    assert db.list_saved()[0]["url"] == URL_B            # newest first
    assert [r["url"] for r in db.list_saved(collection="Recipes")] == [URL_A]
    assert len(db.list_saved(limit=1)) == 1


def test_count_posts(db):
    assert db.count_posts() == 0
    db.upsert_saved([{"url": URL_A, "collection": "X", "timestamp": "2024-01-01T00:00:00+00:00"}])
    assert db.count_posts() == 1

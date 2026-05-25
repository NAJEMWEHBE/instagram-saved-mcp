"""Command-line interface.

The same tool functions power both the MCP server and this CLI, so behavior and
error handling are identical whichever way you drive it. With no subcommand the
program runs the MCP server over stdio — that keeps ``uvx instagram-saved-mcp``
working as an MCP client launches it, while humans get real subcommands.

    instagram-saved-mcp                      # run the MCP server (stdio)
    instagram-saved-mcp refresh export.zip   # import an Instagram export
    instagram-saved-mcp collections
    instagram-saved-mcp list --collection Recipes --limit 20
    instagram-saved-mcp get https://www.instagram.com/p/SHORTCODE/
    instagram-saved-mcp search pasta
    instagram-saved-mcp <cmd> --json         # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

from . import __version__, server


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _is_error(result: Any) -> bool:
    return isinstance(result, dict) and "error" in result


def _emit_json(result: Any) -> int:
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if _is_error(result) else 0


# --- command handlers -------------------------------------------------------


def cmd_serve(_args: argparse.Namespace) -> int:
    server.main()
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    result = server.refresh_index(args.path)
    if args.json:
        return _emit_json(result)
    if _is_error(result):
        return _fail(result["error"])
    print(f"Imported {result['imported']} posts.")
    for row in result["collections"]:
        print(f"  {row['collection']:<24} {row['count']}")
    print(f"DB: {result['db_path']}")
    return 0


def cmd_collections(args: argparse.Namespace) -> int:
    result = server.list_collections()
    if args.json:
        return _emit_json(result)
    if _is_error(result):
        return _fail(result["error"])
    rows = result.get("collections", [])
    if not rows:
        print(result.get("hint", "No collections."))
        return 0
    for row in rows:
        print(f"{row['collection']:<28} {row['count']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    result = server.list_saved(collection=args.collection, limit=args.limit)
    if args.json:
        return _emit_json(result)
    if _is_error(result):
        return _fail(result["error"])
    posts = result.get("posts", [])
    if not posts:
        print(result.get("hint", "No posts."))
        return 0
    for post in posts:
        saved = (post.get("timestamp") or "")[:10]
        print(f"{saved:<11} {(post.get('collection') or ''):<20} {post['url']}")
    n = len(posts)
    print(f"({n} post{'s' if n != 1 else ''})")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    result = server.get_post(args.url)
    if args.json:
        return _emit_json(result)
    if _is_error(result):
        return _fail(result["error"])
    fields = [
        ("author", f"@{result['author']}" if result.get("author") else "-"),
        ("collection", result.get("collection") or "-"),
        ("saved", result.get("timestamp") or "-"),
        ("hashtags", " ".join(result.get("hashtags") or []) or "-"),
        ("image", result.get("image_url") or "-"),
    ]
    print(result["url"])
    for label, value in fields:
        print(f"  {label:<11}{value}")
    print(f"  {'caption':<11}{result.get('caption') or '-'}")
    if result.get("cached"):
        print("  (from cache)")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    result = server.search_saved(args.query)
    if args.json:
        return _emit_json(result)
    if _is_error(result):
        return _fail(result["error"])
    results = result.get("results", [])
    if not results:
        print(result.get("hint", "No matches."))
        return 0
    for post in results:
        author = f"@{post['author']}" if post.get("author") else "-"
        print(f"{author:<18} {post['url']}")
        if post.get("caption"):
            print(f"    {post['caption'][:100]}")
    n = len(results)
    print(f"({n} match{'es' if n != 1 else ''})")
    return 0


# --- parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="instagram-saved-mcp",
        description="Browse your Instagram Saved posts — as an MCP server or from the terminal.",
        epilog="Run with no command to start the MCP server (stdio). DB: $INSTAGRAM_SAVED_MCP_DB.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="Emit raw JSON instead of formatted text.")

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    sub.add_parser("serve", help="Run the MCP server over stdio (default).").set_defaults(func=cmd_serve)

    p_refresh = sub.add_parser("refresh", parents=[common], help="Import an Instagram export ZIP or folder.")
    p_refresh.add_argument("path", help="Path to the export ZIP or its extracted folder.")
    p_refresh.set_defaults(func=cmd_refresh)

    sub.add_parser("collections", parents=[common], help="List collections and post counts.").set_defaults(func=cmd_collections)

    p_list = sub.add_parser("list", parents=[common], help="List saved posts, newest first.")
    p_list.add_argument("--collection", help="Filter by collection name.")
    p_list.add_argument("--limit", type=int, default=50, help="Max posts (default 50).")
    p_list.set_defaults(func=cmd_list)

    p_get = sub.add_parser("get", parents=[common], help="Fetch + cache one post's details.")
    p_get.add_argument("url", help="Public Instagram post/reel URL.")
    p_get.set_defaults(func=cmd_get)

    p_search = sub.add_parser("search", parents=[common], help="Search enriched posts.")
    p_search.add_argument("query", help="Text to match in caption, hashtags, or author.")
    p_search.set_defaults(func=cmd_search)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    func: Callable[[argparse.Namespace], int] | None = getattr(args, "func", None)
    if func is None:
        # No subcommand → run the MCP server (preserves `uvx instagram-saved-mcp`).
        server.main()
        return
    sys.exit(func(args))


if __name__ == "__main__":
    main()

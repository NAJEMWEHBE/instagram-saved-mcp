# instagram-saved-mcp

An [MCP](https://modelcontextprotocol.io) server that makes your Instagram **Saved** posts available to any MCP-compatible AI assistant — Claude Desktop, Cursor, Codex, Cline, and others.

It reads your own **Instagram data export** locally, optionally enriches individual posts from their **public** page, and caches everything in a local SQLite file. No Instagram login, no API keys, no credentials stored anywhere.

## What it can do

| Tool | Description |
|------|-------------|
| `list_collections()` | List your Saved collections and how many posts each has. |
| `list_saved(collection?, limit?)` | List saved posts (URL, collection, saved-on date), newest first. |
| `get_post(url)` | Fetch a public post's caption, author, hashtags, and image URL. Cached after first fetch. |
| `search_saved(query)` | Search enriched posts by caption, hashtag, or author. |
| `transcribe_post(url)` | **v0.2 — stub.** Will transcribe reels/videos (downloads media). Not active in v0.1. |
| `refresh_index(zip_path)` | (Re)import an Instagram export ZIP/folder into the local index. |

## Privacy

- **Read-only of your own data.** The server parses the export *you* download from Instagram.
- **No credentials.** `get_post` only fetches *public* post pages, anonymously.
- **Local only.** Everything is cached in a single SQLite file on your machine (`~/.instagram-saved-mcp/cache.db` by default).

---

## Step 1 — Export your Instagram data

1. Instagram → **Settings → Accounts Center → Your information and permissions → Download your information**.
2. Request a download of **Saved** (or everything), **Format: JSON**.
3. When the email arrives, download the ZIP. You'll point the server at this file — no need to unzip it.

The server reads `your_instagram_activity/saved/saved_posts.json` and (if present) `saved_collections.json` from inside it. A pre-extracted folder works too.

## Step 2 — Install

### Windows (one click)

Download and run [`installers/install_windows.bat`](installers/install_windows.bat). It installs [`uv`](https://docs.astral.sh/uv/) if needed and registers the server in Claude Desktop automatically. Restart Claude Desktop when it finishes.

### Any platform (manual)

Install `uv` ([instructions](https://docs.astral.sh/uv/getting-started/installation/)), then add the config below to your client. `uvx` downloads and runs the server on demand — no separate install step.

```bash
# verify it resolves (optional)
uvx instagram-saved-mcp
```

## Step 3 — Configure your MCP client

All clients use the same command: `uvx instagram-saved-mcp`.

**Claude Desktop** — `%APPDATA%\Claude\claude_desktop_config.json` (Windows) / `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "instagram-saved": {
      "command": "uvx",
      "args": ["instagram-saved-mcp"]
    }
  }
}
```

**Cursor** — `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (project):

```json
{
  "mcpServers": {
    "instagram-saved": {
      "command": "uvx",
      "args": ["instagram-saved-mcp"]
    }
  }
}
```

**Codex CLI** — `~/.codex/config.toml`:

```toml
[mcp_servers.instagram-saved]
command = "uvx"
args = ["instagram-saved-mcp"]
```

Restart the client after editing its config.

## Step 4 — First use

In your assistant, import your export once, then explore:

```
refresh_index("C:/Users/you/Downloads/instagram-export.zip")
list_collections()
list_saved(collection="Recipes")
get_post("https://www.instagram.com/p/SHORTCODE/")
search_saved("pasta")
```

`refresh_index` is also where you go after downloading a fresh export — it updates collections and saved dates without discarding captions you've already fetched.

---

## Notes & limits

- **`get_post` is best-effort.** Instagram frequently serves a login wall to anonymous requests. When that happens you'll get a clean message (`"error_type": "login_wall"`), not a crash — the rest of the server keeps working. When the page *is* served, captions/authors/images come from the page's Open Graph tags.
- **Enrichment is on demand.** `list_saved` returns URLs immediately from the export; `search_saved` only covers posts you've enriched with `get_post`.
- **`transcribe_post` is a v0.2 stub.** It downloads nothing in v0.1. The transcription stack (`yt-dlp` + `faster-whisper`) is an optional extra so the base install stays small:

  ```bash
  uvx instagram-saved-mcp[transcribe]
  ```

## Configuration

| Environment variable | Purpose | Default |
|----------------------|---------|---------|
| `INSTAGRAM_SAVED_MCP_DB` | Path to the SQLite cache file. | `~/.instagram-saved-mcp/cache.db` |
| `INSTAGRAM_SAVED_EXPORT` | If set and the DB is empty, auto-imports this export ZIP/folder on startup. | unset |

## Development

```bash
uv pip install -e ".[dev]"
uv run pytest          # parser tests (no network)
python -m build        # build sdist + wheel
```

Releases publish to PyPI automatically via GitHub Actions on a `v*` tag push (PyPI Trusted Publishing).

## License

MIT — see [LICENSE](LICENSE).

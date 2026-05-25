# Contributing

Thanks for your interest in improving `instagram-saved-mcp`.

## Development setup

```bash
git clone https://github.com/NAJEMWEHBE/instagram-saved-mcp
cd instagram-saved-mcp
uv venv
uv pip install -e ".[dev]"
uv run pytest
```

The parser tests run entirely offline (no network, no real Instagram data).

## Project layout

| Module | Responsibility |
|--------|----------------|
| `cli.py` | Argument parsing and terminal output. |
| `server.py` | MCP tool definitions and the error boundary. |
| `parser.py` | Export (ZIP/folder) → saved-post records. Pure. |
| `enricher.py` | Public-page Open Graph scraping. Network only. |
| `cache.py` | SQLite storage and queries. |
| `config.py` | Paths, environment, HTTP settings. |
| `transcriber.py` | v0.2 transcription stub. |

Lower layers never import upward and never reach into each other's concerns;
`server.py`/`cli.py` are the only places that orchestrate them.

## Guidelines

- Keep layers pure where they're meant to be: no network in `parser`/`cache`,
  no DB in `parser`/`enricher`.
- Raise typed exceptions in lower layers; translate them to clean messages at
  the `server`/`cli` boundary. Never leak a stack trace to an MCP client.
- Add a test for any parser or cache change. Network code stays best-effort and
  must degrade to a clear message, not a crash.
- Run `pytest` before opening a PR.

## Releasing

1. Update `version` in `pyproject.toml`, `__version__`, and `CHANGELOG.md`.
2. Tag and push: `git tag v0.2.0 && git push --tags`.
3. The `Publish to PyPI` workflow builds and publishes via Trusted Publishing.

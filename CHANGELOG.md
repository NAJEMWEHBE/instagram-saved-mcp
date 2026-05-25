# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-26

### Added
- **Command-line interface.** `instagram-saved-mcp` now exposes subcommands
  (`serve`, `refresh`, `collections`, `list`, `get`, `search`) with `--json`
  and `--version`. Running with no subcommand starts the MCP server, so
  existing MCP client configs are unaffected.
- Continuous integration: tests run on Python 3.11–3.13 (`Tests` workflow).
- `CHANGELOG.md`, `CONTRIBUTING.md`, and a `py.typed` marker (the package now
  ships type information).

### Changed
- Console entry point now targets the CLI (`instagram_saved_mcp.cli:main`); the
  CLI and MCP tools share the same underlying functions and error handling.

## [0.1.0] - 2026-05-26

### Added
- Initial release. MCP server exposing Instagram Saved posts from a personal
  data export, with six tools: `list_collections`, `list_saved`, `get_post`
  (public Open Graph enrichment + SQLite cache), `search_saved`, `refresh_index`,
  and a `transcribe_post` stub reserved for v0.2.
- Parser handling both the export ZIP and an extracted folder, both timestamp
  formats, and the two-file (`saved_posts.json` + `saved_collections.json`)
  collection layout.
- PyPI packaging (`uvx`-runnable), Windows installer, and client config examples.

[0.2.0]: https://github.com/NAJEMWEHBE/instagram-saved-mcp/releases/tag/v0.2.0
[0.1.0]: https://github.com/NAJEMWEHBE/instagram-saved-mcp/releases/tag/v0.1.0

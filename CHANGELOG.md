# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [1.0.0]

Initial release.

- **Core plugin** — the `knowledge-base` Claude Code plugin: `vault-access`, `file-naming`, and
  `agent-coordination` skills; `knowledge-agent` and `vault-curator` agents; the `/kb-setup`, `/md`,
  `/note`, `/task`, `/tasklist`, `/task-done`, `/task-triage`, and `/update-knowledgebase` commands.
- **Hooks** — session-start index rebuild and cache cleanup; post-write index refresh and task-move check.
- **Reference docs** — Obsidian Flavored Markdown, Bases (`.base`), JSON Canvas (`.canvas`), and frontmatter schemas.
- **Config-driven** — every path comes from `.claude/knowledge-base.local.md`; sensible universal defaults; `/kb-setup` scaffolds it.
- **Connectors (optional)** — a source-agnostic sync framework with a Quill reference adapter.
- **Safety + CI** — a secret guard, manifest validation, cross-platform Python tests, CodeQL, and gitleaks.

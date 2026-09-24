# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [2.0.0](https://github.com/Elnora-AI/knowledge-vault/compare/v1.2.1...v2.0.0) (2026-09-24)


### ⚠ BREAKING CHANGES

* **connectors:** set OPENROUTER_API_KEY instead of ANTHROPIC_API_KEY. A config that pins llm_model to a bare Claude id such as claude-sonnet-5 needs an OpenRouter id (e.g. openrouter/auto or anthropic/claude-sonnet-5).

### Features

* **connectors:** LLM formatting runs through OpenRouter, and a direct Anthropic key is no longer read ([#39](https://github.com/Elnora-AI/knowledge-vault/issues/39)) ([33bf2cc](https://github.com/Elnora-AI/knowledge-vault/commit/33bf2cca3b6b79de8cb47e556684a289d965668b))
* **connectors:** OpenRouter is an LLM option next to Anthropic, and the user's key decides ([#41](https://github.com/Elnora-AI/knowledge-vault/issues/41)) ([2da9a83](https://github.com/Elnora-AI/knowledge-vault/commit/2da9a83f1fc06f0acbe3e145a1981776a2c7dce1))
* **connectors:** the LLM provider is the user's choice, from any key, as in the Slack bot ([#43](https://github.com/Elnora-AI/knowledge-vault/issues/43)) ([077ba8a](https://github.com/Elnora-AI/knowledge-vault/commit/077ba8a42b24c5242ebc8555136ebadd1254ed89))


### Bug Fixes

* **connectors:** verify and resync pick the synced file when a note shares its id ([#42](https://github.com/Elnora-AI/knowledge-vault/issues/42)) ([8cba682](https://github.com/Elnora-AI/knowledge-vault/commit/8cba682548da47cff363c41a617e2c1da333aab3))

## [1.2.1](https://github.com/Elnora-AI/knowledge-vault/compare/v1.2.0...v1.2.1) (2026-07-16)


### Bug Fixes

* **agents:** stop vault-curator corrupting CSVs with invalid quote escaping ([#21](https://github.com/Elnora-AI/knowledge-vault/issues/21)) ([9ce8ca8](https://github.com/Elnora-AI/knowledge-vault/commit/9ce8ca875f1891bc9810405ddedad3ad973f4014))

## [1.2.0](https://github.com/Elnora-AI/knowledge-vault/compare/v1.1.0...v1.2.0) (2026-07-15)


### Features

* **connectors:** config-driven verify_exempt_markers for hand-curated files ([#13](https://github.com/Elnora-AI/knowledge-vault/issues/13)) ([745a65a](https://github.com/Elnora-AI/knowledge-vault/commit/745a65a71f8a4d1198eca197089794e7a76bac71))


### Bug Fixes

* **connectors:** never clobber a different record's file on filename collision ([#12](https://github.com/Elnora-AI/knowledge-vault/issues/12)) ([5775f21](https://github.com/Elnora-AI/knowledge-vault/commit/5775f218ed6eb4f731eaf89b427e7e1765784a49))

## [1.1.0] - 2026-07-14

- **Connectors: full automation loop.** LLM formatting upgraded to a two-call pipeline (metadata + complete verbatim transcript with an escalating token budget and transient-error retries); optional column-driven CRM stage (match by email, stamp last-contact fields, auto-create contacts + organizations, enrich notes, JSONL audit log); optional action-items-to-task-inbox stage with due-date resolution and dedup; verifier now separates `pending` and `empty_source` from real failures and matches configurable `id_keys`; new CLI commands `mark-all-done`, `resync`, `rename`, `install-schedule`, `uninstall-schedule` plus `sync --content-only` for backfills; cross-platform scheduling (launchd / Task Scheduler / cron) with secrets kept in an `env_file`, never in job definitions.

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

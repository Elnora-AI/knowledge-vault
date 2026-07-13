# Safety guardrails

This plugin operates on your local filesystem — an Obsidian vault or a folder of markdown. Its own scripts and hooks have no network surface, no credentials, and no server; the only network access anywhere in the plugin is the `/note` command, which uses Claude Code's built-in `WebFetch` on a URL you provide. The guardrails below keep a prompt-injected agent from doing anything irreversible and keep your private data out of version control.

## No destructive writes

- **Versioning, not overwriting.** The `knowledge-agent` and `/md` create a new version (`document-name-v2.md`) and mark the old one `superseded` rather than overwriting. The versioning protocol is the documented default.
- **Tasks move, they don't vanish.** The task commands transition a task between the five files; a `PostToolUse` hook (`check-task-move.py`) warns if a task was copied to a destination but left behind in the inbox. Nothing is hard-deleted.
- **The hooks only read.** `update-vault-index.py`, `check-vault-write.py`, `cache-cleanup.py`, and `check-task-move.py` read your config and vault to (re)generate an index and print warnings. The only file the plugin writes on your behalf without an explicit command is the auto-generated index (`notes/index.md` by default) and, if present, expired files under a local `cache/` directory older than 48 hours.

## Your data stays private

- **`vault_path` is gitignored.** The per-user config `.claude/knowledge-base.local.md` — the only place your real vault path lives — is gitignored by this repo and should be gitignored in your project too. It is never committed and never transmitted.
- **No stored secrets.** The plugin's own scripts and hooks make no network calls and store no credentials — they only read and write markdown on your disk. The one exception is the `/note` command, which uses Claude Code's built-in `WebFetch` on the URL you provide; it stores no credentials either. There is nothing to leak.
- **Config is read with a targeted parser.** Hooks read individual config keys with a scoped regex, so nothing else in the file is interpreted or executed.

## Path handling

- Every path is built from your config variables (`vault_path`, `vault_dir`, `task_*`, `notes_dir`, `index_file`). Folder names are never hardcoded, so the plugin only ever touches the vault you pointed it at.
- The index rebuild is debounced (60s) via a marker file in the OS temp directory — it never writes stray files into your project tree.

## Optional connectors

The [`connectors/`](connectors/) framework is **off by default** and not loaded by the core plugin. If you enable it:

- A connector reads from a source you configure (e.g. a local app database) and writes formatted notes into your vault. Source adapters should open external data **read-only** (the bundled Quill reference adapter opens its SQLite database with `mode=ro`).
- LLM formatting, if enabled, uses your own `ANTHROPIC_API_KEY` (or an equivalent you configure) via environment variables — never committed, never logged.

## Publication safety

This repository ships plugin content (agents, commands, skills, hooks, reference docs) and the optional connector framework — never any populated vault, real paths, or credentials. A CI guard (`scripts/check-no-secrets.mjs`) fails the build if any company-, person-, customer-, or path-specific string leaks into a commit. Secret scanning and CodeQL run on every push once the repository is public.

## Reporting

Found a security issue? See [`.github/SECURITY.md`](.github/SECURITY.md). Please do not open a public issue for vulnerabilities.

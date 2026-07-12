# Contributing

Thanks for helping improve knowledge-vault. This is a universal, config-driven Claude Code plugin — contributions must keep it that way.

## Ground rules

1. **Stay universal.** No company-, person-, customer-, or path-specific content anywhere. Examples use the placeholder entities: Acme Corp / Globex / Initech, Jane Doe / Sam Rivera, `example.com`. The CI guard `scripts/check-no-secrets.mjs` enforces this and will fail your PR otherwise.
2. **Config-driven, never hardcoded.** Folder names, task paths, the index location, and the owner come from `.claude/knowledge-base.local.md`. Never hardcode a folder like `notes/` in code — read it from config.
3. **Cross-platform.** Everything must work on macOS, Linux, and Windows. Use `python3 ... || python ...` in command invocations, `pathlib` for paths, UTF-8 everywhere. Never hardcode a timezone.
4. **No new dependencies in the core plugin.** The core is pure Claude Code content plus small standard-library Python hooks. Optional connectors may declare their own extras.

## Development

```sh
# JS guards
node scripts/check-no-secrets.mjs
node scripts/check-json.mjs

# Python lint + tests
python -m pip install ruff pytest
ruff check hooks connectors
python -m pytest -q
```

## Pull requests

- Use a [Conventional Commit](https://www.conventionalcommits.org/) PR title (`feat:`, `fix:`, `docs:`, `chore:`, …). CI lints this.
- Keep changes surgical and focused. Update docs when behavior changes.
- Fill in the PR checklist.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — do not open a public issue for vulnerabilities.

# INSTALL_FOR_AGENTS.md

A gated runbook for an AI agent installing knowledge-vault for a user. Do the steps in order. Do not skip verification. If a step fails, stop and report — do not proceed.

## Step 1 — Add the marketplace

Run, as a Claude Code slash command:

```
/plugin marketplace add Elnora-AI/knowledge-vault
```

Verify: the marketplace `knowledge-vault` now appears in `/plugin`. If not, stop.

## Step 2 — Install the plugin

```
/plugin install knowledge-base@knowledge-vault
```

Verify: `/plugin` lists `knowledge-base` as enabled, and `/kb-setup`, `/md`, `/note`, `/task`, `/tasklist` show up as available commands. If not, stop.

## Step 3 — Configure the vault

Run:

```
/kb-setup
```

This asks the user for their vault path (or detects an Obsidian vault), writes `.claude/knowledge-base.local.md`, creates the default folders and the five task files, builds the index, and verifies. If the user prefers manual setup, copy `settings.example.md` to `.claude/knowledge-base.local.md` and set `vault_path` to an absolute path that exists.

Verify all of:

- `.claude/knowledge-base.local.md` exists and `vault_path` resolves to an existing directory.
- The tasks folder and the five task files exist under the vault root.
- The index file (`notes/index.md` by default) was generated.
- `.claude/knowledge-base.local.md` is gitignored in the user's project.

## Step 4 — Smoke test

Run each and confirm the expected file change:

1. `/task buy milk tomorrow` → a task line appears in the to-do (or inbox) file.
2. `/tasklist` → lists the task you just added.
3. `/md This is a test note about vector databases.` → a new markdown file with frontmatter is created in the vault.

If all three succeed, the install is complete. Report the vault path, the folders created, and the three smoke-test results.

## Notes

- The core plugin has **no external dependencies**. Its scripts and hooks make **no network calls** and operate on the local vault only; the one command that reaches the network is `/note`, which uses Claude Code's built-in `WebFetch` on the URL the user provides.
- Connectors under `connectors/` are optional and off by default; do not install or enable them unless the user asks.

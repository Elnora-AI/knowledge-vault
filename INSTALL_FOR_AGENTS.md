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

## Step 5 (optional, only if the user asks) — Quill meeting-transcript automation

If the user wants their Quill meetings synced into the vault, follow the gated steps below. Skip this step entirely otherwise.

1. Verify Quill is installed by checking for its local database (macOS `~/Library/Application Support/Quill/quill.db`, Windows `%APPDATA%\Quill\quill.db`, Linux `~/.local/share/Quill/quill.db`). If absent, tell the user to install Quill from https://quill.chat first and stop.
2. Copy `connectors/config.example.json` from the installed plugin to the user's project (suggested: `.claude/connectors/quill.json`) and set `"source_name": "quill"`. Ask the user before enabling `llm_enabled` (needs an `ANTHROPIC_API_KEY` via `env_file` — never inline), `crm`, or `tasks`.
3. Run `python3 <plugin>/connectors/cli.py list-pending --config <config>` — it should list the user's recent meetings. If it errors, stop and report.
4. Run `sync --config <config>`, then verify markdown files appeared in the vault's routed folder.
5. If the user wants it automatic, run `install-schedule --config <config>` and verify the job registered (macOS: `launchctl list | grep knowledge-vault`; Windows: `schtasks /Query /TN knowledge-vault-quill-sync`; Linux: `crontab -l | grep knowledge-vault`).

The connector reads Quill's database directly — do **not** install or require any Quill MCP server for syncing. If the user separately wants interactive Quill tools (search meetings, fetch transcripts in conversation), Quill ships an MCP bridge in the same app-data directory (`mcp-stdio-bridge.js`); register it in the project's `.mcp.json` with `command: node` and the absolute bridge path.

## Notes

- The core plugin has **no external dependencies**. Its scripts and hooks make **no network calls** and operate on the local vault only; the one command that reaches the network is `/note`, which uses Claude Code's built-in `WebFetch` on the URL the user provides.
- Connectors under `connectors/` are optional and off by default; do not install or enable them unless the user asks (see Step 5 for Quill).

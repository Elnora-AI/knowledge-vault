# INSTALL_FOR_AGENTS.md

A gated runbook for an AI agent installing knowledge-vault for a user. Assume the user has never done this before: do as much as you can yourself, hand the user only the things you genuinely cannot do (typing built-in slash commands, choosing paths, providing API keys), and always tell them exactly what to type and what they should see. Do the steps in order. Do not skip verification. If a step fails, stop and report — do not proceed.

## Step 0 — Prerequisites

Confirm before starting:

- **Claude Code is running inside a project directory** — any folder works, but the config is written to that project's `.claude/`, so the user should be in the project they'll use the vault from (not their home directory). If they have no project yet, help them create an empty folder and start Claude Code there.
- **No existing vault is required.** `/kb-setup` can detect an existing Obsidian vault *or* create a fresh vault directory from scratch — an empty folder is a valid starting point. Obsidian itself is optional; the vault is plain markdown either way.
- The core plugin needs nothing else — no Python, no Node, no API keys. Those only enter for optional Step 5 features, each called out there.

## Step 1 — Add the marketplace

`/plugin` commands are built into Claude Code and must be typed by the **user**, not run by you. Give them this line to paste, and tell them a confirmation for the `knowledge-vault` marketplace should appear:

```
/plugin marketplace add Elnora-AI/knowledge-vault
```

Verify: the marketplace `knowledge-vault` now appears in `/plugin`. If not, stop.

## Step 2 — Install the plugin

Again typed by the user:

```
/plugin install knowledge-base@knowledge-vault
```

Verify: `/plugin` lists `knowledge-base` as enabled, and `/kb-setup`, `/md`, `/note`, `/task`, `/tasklist` show up as available commands. If not, stop. (The user may need to restart the Claude Code session for new commands to load — suggest that before debugging further.)

## Step 3 — Configure the vault

Have the user run:

```
/kb-setup
```

This asks the user for their vault path (or detects an Obsidian vault — and offers to create the directory if they don't have one), writes `.claude/knowledge-base.local.md`, creates the default folders and the five task files, builds the index, and verifies. If the user prefers manual setup, copy `settings.example.md` to `.claude/knowledge-base.local.md` and set `vault_path` to an absolute path that exists.

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

**Where things live:** the installed plugin is at `~/.claude/plugins/marketplaces/knowledge-vault` (Windows: `%USERPROFILE%\.claude\plugins\marketplaces\knowledge-vault`) — `<plugin>` below means that directory. The connector framework needs **Python 3.10+** and nothing else (standard library only). Use `python3` on macOS/Linux and `python` on Windows.

1. Verify Quill is installed by checking for its local database (macOS `~/Library/Application Support/Quill/quill.db`, Windows `%APPDATA%\Quill\quill.db`, Linux `~/.local/share/Quill/quill.db`). If absent, tell the user to install Quill from https://quill.chat, record at least one meeting, and come back — then stop.
2. Copy `<plugin>/connectors/config.example.json` to the user's project (suggested: `.claude/connectors/quill.json`) and set `"source_name": "quill"`. The defaults work as-is. Ask the user which optional features they want, and complete each one's precondition yourself:
   - **`llm_enabled: true`** (LLM-formatted transcripts, classification, action items) — needs the `anthropic` package (`pip install anthropic`) and an `ANTHROPIC_API_KEY`. Ask the user for the key, write it to a file as a single `ANTHROPIC_API_KEY=...` line (never inline in the config, never in chat), point `env_file` at that file's absolute path, and make sure the file is gitignored. Without this the sync still works — transcripts are written verbatim without summaries.
   - **`crm.enabled: true`** — the framework only writes to CSVs that **already exist with a header row**; a missing CSV is silently skipped. Create the registry CSVs first (e.g. `<vault>/crm/contacts.csv` with a header like `slug,first_name,last_name,email,company,last_contact_date,last_contact_channel,last_meeting_date,last_meeting_transcript,notes`) or, if the user also has [elnora-google-workspace](https://github.com/Elnora-AI/elnora-google-workspace), scaffold with `gw crm init`.
   - **`tasks.enabled: true`** — no precondition; the task inbox from Step 3 is used automatically.
3. Run `python3 <plugin>/connectors/cli.py list-pending --config <config>` — it should list the user's recent meetings. If it errors, stop and report.
4. Run `sync --config <config>`, then verify markdown files appeared in the vault's routed folder.
5. If the user wants it automatic, run `install-schedule --config <config>` and verify the job registered (macOS: `launchctl list | grep knowledge-vault`; Windows: `schtasks /Query /TN knowledge-vault-quill-sync`; Linux: `crontab -l | grep knowledge-vault`). The schedule runs only while the machine is awake; job logs land in `~/Library/Logs/knowledge-vault/` on macOS.

The connector reads Quill's database directly — do **not** install or require any Quill MCP server for syncing. If the user separately wants interactive Quill tools (search meetings, fetch transcripts in conversation), Quill ships an MCP bridge in the same app-data directory (`mcp-stdio-bridge.js`). That needs Node installed. You can register it yourself: add to the project's `.mcp.json` a `quill` server with `"command": "node"` and the absolute bridge path as the single arg (exact JSON in [`connectors/README.md` → Quick start (Quill)](connectors/README.md#quick-start-quill)), then have the user restart the Claude Code session so the `mcp__quill__*` tools load.

## Notes

- The core plugin has **no external dependencies**. Its scripts and hooks make **no network calls** and operate on the local vault only; the one command that reaches the network is `/note`, which uses Claude Code's built-in `WebFetch` on the URL the user provides.
- Connectors under `connectors/` are optional and off by default; do not install or enable them unless the user asks (see Step 5 for Quill).

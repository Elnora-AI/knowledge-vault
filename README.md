# knowledge-vault

**Turn any Obsidian vault (or plain folder of markdown) into a first-class memory for Claude Code — search it, save your work to it, keep it versioned and indexed, and let every agent share it. Config-driven and universal: point it at your vault and go.**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

---

## Install

The knowledge-base plugin is pure Claude Code content — no CLI, no build step, no dependencies. Two slash commands and you're done. Run them **one at a time** (paste the first, hit enter, wait, then the second):

```
/plugin marketplace add Elnora-AI/knowledge-vault
```

```
/plugin install knowledge-base@knowledge-vault
```

Then point it at your vault:

```
/kb-setup
```

`/kb-setup` asks for your vault path, writes the (gitignored) config, creates the default folders, and verifies everything. That's it — the full experience is live.

> Prefer to configure by hand? Copy [`settings.example.md`](settings.example.md) to `.claude/knowledge-base.local.md` in your project and set `vault_path`. See that file for every option.

### Using Codex, Cursor, or another agent

The slash commands and dispatched subagents are Claude-Code-only, but the conventions are portable. Drop [`AGENTS.md`](AGENTS.md) at your project root and any agent can read/search/save to your vault following the same rules.

---

## What you get

- **Search your vault** — the `vault-access` skill teaches the agent to find documents fast with Glob/Grep/Read across `.md`, `.base`, and `.canvas` files, using your frontmatter and folder conventions.
- **Save your work** — `/md` turns pasted text into a clean, frontmattered, cross-linked vault document; `/note` fetches a URL, summarizes it, and files it; `/update-knowledgebase` persists a whole session into the right folders via the `vault-curator` agent.
- **A task system** — `/task`, `/tasklist`, `/task-done`, `/task-triage` implement a five-file task model (inbox → to-do → in-progress → done / cancelled) with Obsidian Tasks syntax, due dates, and priorities.
- **Obsidian power tools** — the `knowledge-agent` writes Flavored Markdown (callouts, embeds, block refs, Mermaid), builds **Bases** (`.base`) database dashboards, and draws **Canvas** (`.canvas`) diagrams. Four reference docs ship the full syntax.
- **Auto-maintained index** — a session-start hook rebuilds a master index of every document, grouped by folder, so the agent always knows what already exists. A write hook keeps it fresh.
- **Document versioning** — new versions instead of overwrites, with `supersedes`/`superseded_by` frontmatter links.
- **Cross-agent coordination** — the `agent-coordination` skill lets any agent pull vault context on demand (the "files as context" pattern).

Everything is **config-driven**: folder names, task paths, the index location, and the default owner all come from your config. Nothing is hardcoded, so your vault stays yours.

### Slash commands

| Command | Does |
|---|---|
| `/kb-setup` | First-run: write config, create folders, verify |
| `/md [text]` | Format pasted text into a vault document with frontmatter + cross-links |
| `/note [url]` | Fetch a URL, summarize it, save as a dated note |
| `/task <desc>` | Add a task (due date, priority, section) |
| `/tasklist [filter]` | Query tasks (today / overdue / this week / priority / search) |
| `/task-done <desc>` | Move a task between states |
| `/task-triage` | Review the inbox one task at a time |
| `/update-knowledgebase` | Persist this session's results into the vault |

### Skills & agents

- **Skills:** `vault-access` (search/create), `file-naming` (naming conventions), `agent-coordination` (cross-agent access).
- **Agents:** `knowledge-agent` (fetch/create/version, `.base`, `.canvas`), `vault-curator` (files a session's results into the right folders).

---

## Configuration

All paths live in `.claude/knowledge-base.local.md` (gitignored — each machine has its own). The only required field is `vault_path`. Sensible defaults cover everything else:

```yaml
---
vault_path: /path/to/your/obsidian/vault   # REQUIRED — absolute path
vault_dir: ""                              # optional subfolder that is the vault root
task_inbox: tasks/inbox.md                 # the five task files
task_todo: tasks/to-do.md
task_in_progress: tasks/in-progress.md
task_done: tasks/done.md
task_cancelled: tasks/cancelled.md
notes_dir: notes                           # catch-all notes; holds the auto-index
index_file: notes/index.md
vault_title: Knowledge Base
default_owner: ""
---
```

Default folder layout (rename or extend freely — it's all config):

```
notes/  tasks/  meetings/  people/  policies/  projects/  reference/
```

Full field reference: [`settings.example.md`](settings.example.md).

---

## Connectors (optional)

Want meeting transcripts, call notes, or any dated records to flow into your vault automatically? The [`connectors/`](connectors/) directory ships a small, source-agnostic **sync framework** — a `Source` adapter plus a `SyncEngine` that formats each record and writes it into the vault — with a **Quill** reference adapter as a worked example. Bring your own tool (Granola, Otter, Quill, …) by implementing one small `Source` interface.

On top of the core pipeline, connectors optionally give you the full automation loop:

- **LLM formatting** — a two-call pipeline (metadata + complete verbatim transcript) that classifies each record against your routes, tags it, and extracts action items. Degrades to passthrough without an API key.
- **CRM linking** — keep a CSV CRM inside your vault in sync with your meetings: participants are matched by email, last-contact fields stamped, unknown externals auto-created (organizations too), and per-call notes appended. Column-driven — any schema works. Pairs perfectly with the CRM that [google-workspace](#supercharge-with-google-workspace) scaffolds.
- **Action items → task inbox** — extracted follow-ups land in your task inbox with due dates resolved and the transcript linked.
- **Verification** — an auditable `verify` command that catches missing or truncated transcripts.
- **Scheduling** — `install-schedule` registers the sync on launchd (macOS), Task Scheduler (Windows), or cron (Linux). Set-and-forget.

See [`connectors/README.md`](connectors/README.md). This is entirely optional and off by default; the core plugin never depends on it.

---

## Supercharge with google-workspace

Pair this with [`Elnora-AI/elnora-google-workspace`](https://github.com/Elnora-AI/elnora-google-workspace) and the two become one self-driving system: Gmail and Calendar feed a lightweight CRM that lives right inside your vault, kept fresh on a schedule with no manual upkeep. The vault is the memory; google-workspace is the senses.

Once both are installed:

```sh
gw auth setup                 # one-time Google sign-in
gw crm init                   # scaffold contacts.csv in <vault>/crm
gw gmail sync-crm-install     # schedule email → CRM (mac/Windows/Linux)
gw calendar sync-crm-install  # schedule calendar → CRM
```

`gw crm init` reads the `vault_path` from your `.claude/knowledge-base.local.md` — no extra configuration. Both plugins still work entirely on their own; this just makes them better together.

---

## Safety

Read [`SAFETY.md`](SAFETY.md). In short: a write hook only ever *reads* your config, the plugin never deletes or overwrites documents (it versions them), your real `vault_path` is gitignored, and no secrets are stored or transmitted — the plugin talks to your local filesystem, nothing else.

---

## License

[Apache-2.0](LICENSE). Maintained by [Elnora AI](https://github.com/Elnora-AI). Contributions welcome — see [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md).

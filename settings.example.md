---
# REQUIRED — absolute path to your vault (an Obsidian vault, or any folder of markdown notes).
vault_path: /path/to/your/obsidian/vault

# OPTIONAL — subfolder inside vault_path that is the vault root.
# Leave empty if vault_path already IS the vault root.
vault_dir: ""

# Task system (five-file model). Paths are relative to the resolved vault root.
task_inbox: tasks/inbox.md
task_todo: tasks/to-do.md
task_in_progress: tasks/in-progress.md
task_done: tasks/done.md
task_cancelled: tasks/cancelled.md

# Notes + the auto-generated index. Relative to the vault root.
notes_dir: notes
index_file: notes/index.md

# Cosmetic defaults (leave empty to omit).
vault_title: Knowledge Base
default_owner: ""
---

# Knowledge Base Settings

This file is the **single source of truth** for your vault paths. Every command, skill, agent,
and hook reads it. Copy it to `.claude/knowledge-base.local.md` in your project root and edit the
values. That copy is gitignored — each person keeps their own `vault_path`.

The fastest way to create it is to run `/kb-setup` inside Claude Code, which writes this file,
creates the default folders, and verifies everything for you.

## Setup

1. Copy this file to `.claude/knowledge-base.local.md` in your project root.
2. Set `vault_path` to the absolute path of your vault.
3. (Optional) Adjust the folder names to match how you like to organize.

## Path examples for `vault_path`

| OS | Example |
|----|---------|
| macOS | `/Users/yourname/Documents/my-vault` |
| Windows | `C:\Users\yourname\Documents\my-vault` |
| Linux | `/home/yourname/Documents/my-vault` |

Using a synced folder (Dropbox, iCloud, Google Drive, OneDrive) works too — just point `vault_path`
at wherever that folder is mounted on this machine, for example
`/Users/yourname/Library/CloudStorage/Dropbox/my-vault`.

## Fields

| Field | Description | Varies per machine? |
|-------|-------------|---------------------|
| `vault_path` | Absolute path to your vault | **Yes** |
| `vault_dir` | Subfolder inside `vault_path` that is the vault root (empty = root) | No |
| `task_inbox` … `task_cancelled` | The five task files, relative to the vault root | No |
| `notes_dir` | Folder for catch-all notes (also holds the auto-index) | No |
| `index_file` | Path to the auto-generated vault index | No |
| `vault_title` | Title written at the top of the auto-index | No |
| `default_owner` | Default `owner:` value in new document frontmatter (empty = omit) | No |

## Default folder layout

Out of the box the plugin uses this simple, universal layout. Rename or extend it however you like —
everything is derived from the config above, nothing is hardcoded.

```
<vault root>/
├── notes/       # catch-all notes; holds the auto-generated index.md
│   └── {YYYY}/{topic}/
├── tasks/       # inbox / to-do / in-progress / done / cancelled
├── meetings/    # meeting transcripts & notes
├── people/      # contacts
├── policies/    # optional; internal/ + external/
├── projects/    # project docs
└── reference/   # how-tos and standing documents
```

Only two folders are load-bearing in code and are auto-created if missing: the **tasks** folder
(the parent of `task_inbox`) and the **notes** folder (where the index is written). Everything else
is convention you can change.

## Rules

- `vault_path` must be absolute (never relative).
- The vault must exist on disk.
- Agents build every path from these variables — they never hardcode a folder name.
- This file is gitignored; keep your real `vault_path` out of version control.

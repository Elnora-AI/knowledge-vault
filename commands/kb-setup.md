---
description: First-run setup for the knowledge-base plugin — write the vault config, create the default folders, and verify everything works.
---

# Knowledge Base Setup

Get the knowledge-base plugin working end-to-end in one pass. You (the assistant) run these steps in order. Be fast and concrete; only ask the user the one thing you genuinely cannot determine — their vault path.

## Step 1 — Find or ask for the vault path

Check whether a config already exists at `.claude/knowledge-base.local.md` in the project root.

- **If it exists** and has a real `vault_path` that exists on disk: tell the user it's already configured, show the resolved vault root, and skip to Step 3 (verify) — do not overwrite it.
- **If it does not exist:** determine the vault path.
  1. Look for an obvious Obsidian vault on this machine — a directory containing a `.obsidian/` folder — under common locations (the user's home, `~/Documents`, `~/Library/CloudStorage/*`, `~/Dropbox`, `~/iCloud*`). Use Glob/Bash. If you find exactly one strong candidate, propose it.
  2. Otherwise, ask the user for the absolute path to their vault (or where they want a new one created). Use `AskUserQuestion` with the candidate(s) you found plus an "Enter a different path" option.

The vault path must be **absolute**. If the directory does not exist yet, offer to create it.

## Step 2 — Write the config

Read the template at `${CLAUDE_PLUGIN_ROOT}/settings.example.md`. Write `.claude/knowledge-base.local.md` in the project root with the same frontmatter, substituting the real `vault_path`. Keep every other field at its default unless the user asked otherwise:

```yaml
---
vault_path: <the absolute path from Step 1>
vault_dir: ""
task_inbox: tasks/inbox.md
task_todo: tasks/to-do.md
task_in_progress: tasks/in-progress.md
task_done: tasks/done.md
task_cancelled: tasks/cancelled.md
notes_dir: notes
index_file: notes/index.md
vault_title: Knowledge Base
default_owner: ""
---
```

Then make sure `.claude/knowledge-base.local.md` is gitignored in this project (add the line to `.gitignore` if the project has one and the entry is missing). This file holds the user's real vault path and must never be committed.

## Step 3 — Create the default folders and task files

Resolve the vault root: `vault_path` + `vault_dir` (if set). Create these folders under the vault root if they don't already exist (never delete or empty anything that's there):

```
notes/   tasks/   meetings/   people/   policies/   projects/   reference/
```

Create the five task files if missing, each with a minimal header so they're valid Obsidian notes:

- `tasks/inbox.md`, `tasks/to-do.md`, `tasks/in-progress.md`, `tasks/done.md`, `tasks/cancelled.md`

Use a header like:

```markdown
---
title: To Do
type: task-list
---

# To Do
```

Only create files that are missing — do not touch existing task files.

## Step 4 — Build the index

Run the index hook once so the master index exists immediately:

```
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/update-vault-index.py" --force || python "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/update-vault-index.py" --force
```

## Step 5 — Verify and report

Confirm all of the following, then give the user a short summary:

- `.claude/knowledge-base.local.md` exists and `vault_path` points at an existing directory.
- The seven default folders exist under the vault root.
- The five task files exist.
- The index file (`notes/index.md` by default) was generated.

Finish with the three things they can try right now: `/task <something>`, `/note <url>`, and `/md <paste text>`. Keep it to a few lines — the point is that it just works.

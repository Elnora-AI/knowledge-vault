---
name: vault-access
description: Search, access, and create files in the local Obsidian vault (.md, .base, .canvas). Use when the user asks to search the vault, find documents or notes, access reference docs, create dashboards, or make canvases.
---

# Vault Access

## Vault Path

Read from: `.claude/knowledge-base.local.md`

```yaml
---
# REQUIRED — absolute path to your vault (an Obsidian vault, or any folder of markdown notes)
vault_path: /path/to/your/obsidian/vault

# OPTIONAL — subfolder inside vault_path that is the vault root. Empty = vault_path IS the root.
vault_dir: ""

# Task system (5-file model). Relative to the resolved vault root.
task_inbox: tasks/inbox.md
task_todo: tasks/to-do.md
task_in_progress: tasks/in-progress.md
task_done: tasks/done.md
task_cancelled: tasks/cancelled.md

# Notes + auto-generated index. Relative to vault root.
notes_dir: notes
index_file: notes/index.md

# Cosmetic defaults (leave empty to omit)
vault_title: Knowledge Base
default_owner: ""
---
```

If file is missing, create it from `${CLAUDE_PLUGIN_ROOT}/settings.example.md`.

> In examples below, `{vault}` = `{vault_path}/{vault_dir}` (the full Obsidian vault root on disk; if `vault_dir` is empty, `{vault}` = `{vault_path}`). All paths should be built from these variables — never hardcode directory names.

## Tool Selection

All vault operations use built-in tools. The vault files live on disk (a local Obsidian vault or folder of markdown notes).

| Task | Best Tool | Why |
|------|-----------|-----|
| **Find files by pattern** | Glob | Fast pattern matching across vault |
| **Known file path** | Read | Direct file access, no overhead |
| **Regex content search** | Grep | Powerful regex, search by frontmatter fields |
| **Search by tags/status** | Grep | `Grep("tags:.*project", path=vault)` |
| **Create/replace file** | Write | Direct file creation |
| **Partial update** | Edit | Targeted edits without rewriting full file |

**Never use:** `ls`, `find`, `dir` (not cross-platform)

## Link Format

**Standard markdown links only** — never wikilinks `[[doc]]`.

## Index Files

Two distinct kinds — never confuse them:

| File | Purpose | Maintained by | Read it when |
|------|---------|---------------|--------------|
| `{vault}/notes/index.md` (the configured `index_file`) | **Auto-generated master.** Lists every `.md`/`.base`/`.canvas` file in the vault, grouped by top-level folder. Rebuilt every 24h by `update-vault-index.py`. | Hook — do not edit by hand | You need to find "does a doc on X already exist?" |
| `{folder}/_index.md` | **Hand-curated folder hub.** Conventions, agent lookup patterns, registries, cross-links for that folder. One per folder that has enough complexity to warrant it (vault root, `people/`, `projects/` + each project sub-hub, `meetings/`, etc.). | You and your team | You're working inside that folder and need the local rules / registry |

The two never overlap. The auto-master never edits `_index.md` files; folder `_index.md` files never try to enumerate everything.

**Naming rule:** every folder-level hub is `_index.md` (underscore prefix sorts to the top of file listings). Never `index.md`, never `README.md`. The auto-master is the one exception — the configured `index_file` (default `notes/index.md`) uses `index.md` because it has a distinct role.

## Quick Patterns

```
# Directory exploration
Glob("{vault}/*")                    # Root folders
Glob("{vault}/**/_index.md")         # All hand-curated folder hubs
Read("{vault}/notes/index.md")       # Auto-master "does doc X exist"

# Find by type
Glob("{vault}/**/policies/**/*.md")  # Policies
Glob("{vault}/**/contracts/*.md")    # Contracts
Glob("{vault}/**/templates/*.md")    # Templates

# Find Bases and Canvas files
Glob("{vault}/**/*.base")            # All Bases dashboards
Glob("{vault}/**/*.canvas")          # All Canvas files

# Search content
Grep("type: note", path=vault)       # By frontmatter
Grep("roadmap", path=vault)          # By keyword

# Find related documents (markdown link format)
Grep("related:.*project", path=vault)
Grep("\\]\\(.*doc-name", path=vault)
```

## Format References

Load these on demand when creating specific file types:

| Reference | When to Load |
|-----------|-------------|
| `reference/obsidian-flavored-markdown.md` | Writing any vault .md file with callouts, embeds, highlights, etc. |
| `reference/obsidian-bases.md` | Creating or editing .base files |
| `reference/json-canvas.md` | Creating or editing .canvas files |
| `reference/frontmatter-schemas.md` | Setting up frontmatter for any document type |

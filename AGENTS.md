# AGENTS.md — knowledge-vault

This file lets any AI coding agent (Claude Code, Codex, Cursor, …) use the vault following the same conventions as the Claude Code plugin. Drop it at your project root.

## Config

All paths come from `.claude/knowledge-base.local.md` (YAML frontmatter). Read it first. Required: `vault_path`. The vault root is `vault_path` + `vault_dir` (if set). Defaults:

```yaml
vault_path: /path/to/your/vault
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
```

If the file is missing, create it from `settings.example.md`. Never hardcode a folder name — build every path from these variables.

## Intent → action

| The user wants to… | Do this |
|---|---|
| Find a document | Glob/Grep/Read under the vault root. Check `{index_file}` first for "does a doc on X exist?" |
| Save pasted text as a doc | Classify the type, write clean markdown with frontmatter to the type's folder (see below), cross-link related docs |
| Save a URL as a note | Fetch, summarize, tag, write to `{notes_dir}/{YYYY}/{topic}/YYYY-MM-DD-slug.md` |
| Add a task | Append an Obsidian Tasks line to `{task_todo}` (or `{task_inbox}`) |
| List tasks | Read the relevant task file(s), parse `- [ ] #task …` lines, filter |
| Complete a task | Move the line from its current file to `{task_done}` — move, don't copy |
| Persist a whole session | Synthesize a brief, then file results into the right folders, versioning rather than overwriting |

## Conventions

- **Links:** standard markdown links `[Title](./path.md)` only — never wikilinks `[[doc]]`.
- **Filenames:** lowercase, hyphens, date-front for dated docs (`YYYY-MM-DD-topic.md`). See the `file-naming` skill for the full rules.
- **Versioning:** never overwrite a document — create `name-v2.md` and mark the old one `superseded`.
- **Frontmatter:** every document gets YAML frontmatter (`title`, `type`, `status`, `created`, `owner`, `tags`, `related`).

## Default folders (all configurable)

```
notes/  tasks/  meetings/  people/  policies/  projects/  reference/
```

Route by document type: note/reference → `notes/` (or `reference/` for standing docs), meeting → `meetings/`, contact → `people/`, policy → `policies/`, project/agreement → `projects/`, task → `tasks/`. When unsure, use `notes/`.

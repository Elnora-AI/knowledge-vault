---
name: tasklist
description: View and query tasks from your task system
argument-hint: [todo | in-progress | done | inbox | cancelled | overdue | today | due this week | high priority | <search query>]
allowed-tools: Read, Glob, Grep
---

# Task List Query: $ARGUMENTS

## Task

Read your task system files and filter/display tasks based on the user's query.

**Query:** $ARGUMENTS

## Instructions

### Step 1: Load Vault Paths

Read `.claude/knowledge-base.local.md` and extract `vault_path` (and optional `vault_dir`) + task file paths from YAML frontmatter.
Full path to any task file: `{vault_path}/{task_xxx}` — prepend `{vault_dir}` between them if it is set (it is empty by default). Task paths are leaf-relative (e.g. `tasks/inbox.md`).

### Step 2: Determine Which File(s) to Read

**Only load the files needed** — this saves tokens and context window.

| Query | File(s) to read |
|-------|----------------|
| *(empty / "all")* | `to-do.md` + `in-progress.md` (open tasks only) |
| `todo` / `to do` / `open` | `to-do.md` |
| `in progress` / `in-progress` / `active` | `in-progress.md` |
| `done` / `completed` | `done.md` |
| `inbox` / `new` / `captured` | `inbox.md` |
| `cancelled` / `dropped` | `cancelled.md` |
| `today` | `to-do.md` + `in-progress.md` (filter by today's date) |
| `overdue` | `to-do.md` + `in-progress.md` (filter by past due dates) |
| `due this week` | `to-do.md` + `in-progress.md` (filter by current week) |
| `due next week` | `to-do.md` + `in-progress.md` (filter by next week) |
| `high priority` | `to-do.md` + `in-progress.md` (filter by ⏫) |
| `{section name}` | `to-do.md` (match section heading) |
| *anything else* | Search across `to-do.md` + `in-progress.md` for the query text |

### Step 3: Parse Tasks from Loaded File(s)

Parse each task line to extract:
- **Status**: `[ ]` = open, `[/]` = in progress, `[x]` = done
- **Description**: The text after `#task`
- **Due date**: The date after `📅` (YYYY-MM-DD)
- **Priority**: `⏫` = high, `🔼` = medium, none = normal
- **Section**: The `## Heading` the task falls under
- **Depth**: Indentation level (top-level vs sub-task)

### Step 4: Apply Filter

Filter tasks based on the query as described in the table above.

### Step 5: Present Results

Format the output as a clean, readable list:

**For filtered lists:**

```
## {Section Name}

- [ ] Task description 📅 2026-02-14 ⏫
    - [ ] Sub-task description 📅 2026-02-10 🔼
```

- Preserve the original formatting (checkboxes, emojis, indentation)
- Group by section, only showing sections that have matching tasks
- Show a count summary at the top: "**X tasks** (Y overdue, Z due today)"
- For overdue tasks, note how many days overdue
- Indicate which file(s) the tasks come from

**For questions about tasks:**

Answer conversationally based on the task data. For example:
- "What's most urgent?" → Show highest-priority tasks due soonest
- "What do I need to do for taxes?" → Show all tasks under Taxes section
- "How many tasks are done?" → Count and summarize completion stats

### Step 6: Highlight Urgency

After presenting results, call out:
1. Any **overdue** tasks (due date has passed, still open)
2. Any tasks due **today**
3. Any **high-priority** tasks without due dates

## Error Handling

- If the task files cannot be found, tell the user and suggest checking `.claude/knowledge-base.local.md`
- If task paths are not set in the config, tell the user to add them
- If no tasks match the filter, say so clearly and suggest alternative queries

---
name: task
description: Add a new task to the task system
argument-hint: <task description> [due:YYYY-MM-DD] [priority:high|medium|normal] [section:SectionName]
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion
---

# Add Task: $ARGUMENTS

## Task

Parse the user's input and add a new task to the appropriate file in the task system.

**User input:** $ARGUMENTS

## Instructions

### Step 1: Load Vault Paths

Read `.claude/knowledge-base.local.md` and extract `vault_path` (and optional `vault_dir`) + task file paths from YAML frontmatter.
Full path to any task file: `{vault_path}/{task_xxx}` — prepend `{vault_dir}` between them if it is set (it is empty by default). Task paths are leaf-relative (e.g. `tasks/inbox.md`).

### Step 2: Parse User Input

Extract from the user's natural-language input:

- **Description**: The core task text
- **Due date**: Look for explicit dates, or phrases like "by Friday", "next week", "end of month", "tomorrow". Format as `YYYY-MM-DD`. If none given, omit the due date.
- **Priority**: Look for "urgent", "high priority", "ASAP" (= `⏫` high), "medium" (= `🔼` medium), or default to no priority emoji.
- **Section**: Only relevant if the target file uses `## Section` headings. If the user names a section, match it; if the file has no sections, ignore this (append under the H1). Do not prompt for a section when the file has none.
- **Parent task**: If the user says "under [task]" or "subtask of [task]", find the parent task line and indent the new task beneath it.
- **Destination file**: Default is `to-do.md`. If user says "inbox" or this is auto-captured, use `inbox.md`. If user says "start" or "working on it", use `in-progress.md`.

### Step 3: Read (or Create) the Destination File

1. Read the target file (usually `to-do.md`).
2. **If the file does not exist**, create it with the `Write` tool using a minimal header, then continue — a missing task file is normal on a fresh vault, not an error:

   ```markdown
   ---
   title: To Do
   type: task-list
   ---

   # To Do
   ```

   (Use the matching title for the file: Inbox / To Do / In Progress / Done / Cancelled.)
3. Identify any existing section headings (`## Section Name`). Many vaults keep all tasks directly under the `# H1` with no `##` sections — that is fine.

### Step 4: Format the Task

Format using the Obsidian Tasks plugin syntax:

```
- [ ] #task {description} 📅 {YYYY-MM-DD} {priority_emoji}
```

Rules:
- Always include `#task` tag after the checkbox
- Only add `📅 YYYY-MM-DD` if a due date was specified or inferred
- Priority emojis: `⏫` (high/urgent), `🔼` (medium), omit for normal
- Sub-tasks are indented with 4 spaces under their parent
- Keep descriptions concise but actionable (imperative form)
- For in-progress tasks, use `[/]` instead of `[ ]`

### Step 5: Add to File

1. Use the `Edit` tool to insert the new task line at the **end** of the matched section (before the next `##` heading or end of file)
2. **If the file has no `##` sections** (all tasks live under the `# H1`), simply append the task line at the end of the file — do not prompt for a section.
3. If adding a sub-task, insert it indented directly after the parent task and its existing sub-tasks
4. Preserve all existing content exactly — do not modify other tasks
5. Only when the user explicitly named a section that doesn't exist: ask whether to create it or pick an existing one

### Step 6: Confirm

Report to the user:
- The task that was added (show the formatted line)
- Which file and section it was added to
- The due date and priority (if set)

## Examples

**Input:** `Email Jane about the pilot contract due:2026-02-14 priority:high`
**Output line:** `- [ ] #task Email Jane about the pilot contract 📅 2026-02-14 ⏫`
**File:** `to-do.md`

**Input:** `Book dentist appointment` (section: Personal)
**Output line:** `- [ ] #task Book dentist appointment`
**File:** `to-do.md`

**Input:** `Reply to Sam's email by Friday under "Vendors"`
**Output line (indented sub-task):** `    - [ ] #task Reply to Sam's email 📅 2026-02-28 🔼`
**File:** `to-do.md`

## Error Handling

- If a task file doesn't exist yet, **create it** (Step 3) — this is normal on a fresh vault, not an error.
- If `.claude/knowledge-base.local.md` is missing entirely, tell the user to run `/kb-setup` first.
- If task paths are not set in the config, fall back to the defaults (`tasks/inbox.md`, `tasks/to-do.md`, …).
- Only prompt about sections when the user explicitly named one that doesn't exist.

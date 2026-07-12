---
name: task-done
description: Mark a task as done, cancelled, or move between task states
argument-hint: <task description or search> [--cancel] [--start] [--todo]
allowed-tools: Read, Write, Edit, Glob, Grep
---

# Move Task: $ARGUMENTS

## Task

Find a task by description and move it between task system files (to-do → in-progress → done, or cancel).

**User input:** $ARGUMENTS

## Instructions

### Step 1: Load Vault Paths

Read `.claude/knowledge-base.local.md` and extract `vault_path` (and optional `vault_dir`) + task file paths from YAML frontmatter.
Full path to any task file: `{vault_path}/{task_xxx}` — prepend `{vault_dir}` between them if it is set (it is empty by default). Task paths are leaf-relative (e.g. `tasks/inbox.md`).

### Step 2: Determine the Transition

| Flag / keyword | From | To | Status change |
|----------------|------|----|---------------|
| *(default, no flag)* | `to-do.md` or `in-progress.md` | `done.md` | `[ ]`/`[/]` → `[x]` |
| `--cancel` / "cancel" | any file | `cancelled.md` | add cancellation reason |
| `--start` / "start" / "working on" | `to-do.md` | `in-progress.md` | `[ ]` → `[/]` |
| `--todo` / "move to todo" | `inbox.md` or `in-progress.md` | `to-do.md` | keep status |

### Step 3: Find the Task

1. Search the source file(s) for a task matching the user's description (fuzzy match on the description text)
2. If multiple matches, show them and ask the user to clarify
3. If the task has sub-tasks, ask whether to move the entire group or just the parent

### Step 4: Move the Task

1. **Remove** the task line, its sub-tasks, AND any indented metadata lines (e.g., `- source::`) from the source file using `Edit`
2. **If the destination file does not exist**, create it first with `Write` using a minimal header (this is normal, not an error):

   ```markdown
   ---
   title: Done
   type: task-list
   ---

   # Done
   ```

   (Use the matching title: To Do / In Progress / Done / Cancelled.)
3. **Add** the complete task block (task line + metadata lines) to the destination file:
   - For `done.md`: change checkbox to `[x]`, append `✅ completed {today's date}`
   - For `cancelled.md`: change checkbox to `[-]`, append `❌ cancelled {today's date} — {reason if provided}`
   - For `in-progress.md`: change checkbox to `[/]`
   - For `to-do.md`: keep checkbox as `[ ]`
4. Place it under the matching `## Section` if the file uses sections; if it has none, append at the end under the `# H1`.

### Step 5: Confirm

Report:
- Which task was moved
- From which file → to which file
- The updated task line

## Examples

**Input:** `Email Sam` (default = mark done)
→ Finds `- [/] #task Email Sam — invite Acme...` in `in-progress.md`
→ Moves to `done.md` as `- [x] #task Email Sam — invite Acme... ✅ completed 2026-02-26`

**Input:** `Find tire storage --cancel not needed anymore`
→ Finds task in `to-do.md`
→ Moves to `cancelled.md` as `- [-] #task Find tire storage... ❌ cancelled 2026-02-26 — not needed anymore`

**Input:** `R&D tax credit --start`
→ Finds task in `to-do.md`
→ Moves to `in-progress.md` as `- [/] #task R&D tax credit...`

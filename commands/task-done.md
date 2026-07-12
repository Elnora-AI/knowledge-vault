---
name: task-done
description: Mark a task as done, cancelled, or move between task states
argument-hint: <task description or search> [--cancel] [--start] [--todo]
allowed-tools: Read, Edit, Glob, Grep, Bash
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
2. **Add** the complete task block (task line + metadata lines) to the destination file:
   - For `done.md`: change checkbox to `[x]`, append `✅ completed {today's date}`
   - For `cancelled.md`: change checkbox to `[-]`, append `❌ cancelled {today's date} — {reason if provided}`
   - For `in-progress.md`: change checkbox to `[/]`
   - For `to-do.md`: keep checkbox as `[ ]`
3. Place it under the matching `## Section` in the destination file, or create the section if needed

### Step 5: Optional CRM writeback (off by default)

This step is **optional** and applies only when transitioning a task to `done.md` AND both of the following are true:

1. You maintain a contacts file (e.g. `people/contacts.csv`), and
2. The moved task block carries CRM metadata — `contact-slug::` AND/OR `crm-action::` lines.

If either is not true, **skip this step entirely** — the task system works fully without any CRM linkage. The writeback CLI ships under the plugin's `optional/` directory and **may not be installed**; if it is missing, skip this step.

When it does apply, call the writeback CLI to update your contacts file:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/optional/cli/task_done_crm_writeback.py \
  --contact-slug <slug> [--crm-action <action_key>] --compact \
  || python ${CLAUDE_PLUGIN_ROOT}/optional/cli/task_done_crm_writeback.py \
  --contact-slug <slug> [--crm-action <action_key>] --compact
```

- Pass `--crm-action` only if the task line had `crm-action:: <key>`. The CLI clears `next_action` ONLY if the row's current value matches that key (fingerprint check — protects against accidental clears).
- If only `contact-slug::` is present, omit `--crm-action`. The CLI just bumps `last_contact_date` to today with `last_contact_channel=task`.
- Skip this step entirely for `--cancel`, `--start`, or `--todo` transitions — only run it when the destination is `done.md`.

### Step 6: Confirm

Report:
- Which task was moved
- From which file → to which file
- The updated task line
- If the optional CRM writeback ran, what changed (e.g. "cleared next_action=send-proposal on jane-doe; bumped last_contact_date")

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

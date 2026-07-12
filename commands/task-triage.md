---
name: task-triage
description: Review and triage tasks in the inbox — accept, reject, or defer
argument-hint: [all | review]
allowed-tools: Read, Edit, Glob, Grep, AskUserQuestion
---

# Triage Inbox: $ARGUMENTS

## Task

Present auto-captured tasks from the inbox for review. For each task, the user decides: accept (move to to-do), reject (move to cancelled), or defer (keep in inbox).

## Instructions

### Step 1: Load Vault Paths

Read `.claude/knowledge-base.local.md` and extract `vault_path` (and optional `vault_dir`) + task file paths from YAML frontmatter.
Full path to any task file: `{vault_path}/{task_xxx}` — prepend `{vault_dir}` between them if it is set (it is empty by default). Task paths are leaf-relative (e.g. `tasks/inbox.md`).
Read `{vault_path}/{task_inbox}`. If inbox is empty, tell the user "Inbox is empty — no tasks to triage".

### Step 2: Present Tasks

For each task in the inbox, show:
- The task description, due date, priority
- The source (if metadata exists: transcript, email, agent-generated)
- Suggest a section in `to-do.md` where it would fit

### Step 3: Get Decision

For each task (or batch), ask the user:
- **Accept** → move to `{vault_path}/{task_todo}` under the suggested (or user-chosen) section
- **Reject** → move to `{vault_path}/{task_cancelled}` with reason
- **Defer** → keep in `inbox.md` for later review
- **Edit** → modify the task description/priority/date before accepting

### Step 4: Execute Moves

Use Edit tool to remove from `inbox.md` and add to the appropriate file.

When moving a task, **preserve all indented child lines** (especially `- source::` metadata). Move the task line AND its indented children together as a unit.

### Step 5: Summary

Report how many tasks were triaged:
- X accepted → to-do
- X rejected → cancelled
- X deferred → still in inbox

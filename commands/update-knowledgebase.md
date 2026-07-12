---
name: update-knowledgebase
description: Save this session's work results into the vault — synthesize what we did, then dispatch the vault-curator agent to file it in the correct folders with frontmatter and links, or update existing trackers/READMEs.
argument-hint: [optional — focus or scope, e.g. "just the finance work"]
allowed-tools: Read, Glob, Grep, Task, AskUserQuestion
---

# Update the Knowledge Base from this Session

Persist the durable results of the current work session into the Obsidian vault, in the correct places, keeping the vault coherent. You (running in the main conversation) synthesize the session — only you can see the full transcript. The `vault-curator` agent does the vault investigation and writes.

**Optional scope:** $ARGUMENTS — if given, limit the synthesis to that focus.

## Step 1 — Load vault paths

Read `.claude/knowledge-base.local.md`; extract `vault_path` and `vault_dir`. Vault root: `{vault_path}/{vault_dir}` (if `vault_dir` is empty, `vault_path` is the root).

## Step 2 — Synthesize the session brief

Review everything done in this conversation (within any scope in $ARGUMENTS) and write a structured brief capturing the **durable results**, not the play-by-play:

- **Work done** — what was actually accomplished (tasks, deliverables, analyses).
- **Decisions** — choices made and the outcome (the decision, not the deliberation).
- **Artifacts produced** — files created or changed, with paths (repo, vault, Drive), URLs, IDs.
- **Key facts / state** — new durable facts, status changes, numbers worth keeping.
- **Entities** — companies, people, projects, events touched (for placement + linking).

Keep it tight and factual. Surface implications, not the reasoning behind them. If there is nothing durable worth saving, say so and stop — do not invent filler.

## Step 3 — Plan (dispatch vault-curator in plan mode)

Dispatch the **vault-curator** agent (`subagent_type: vault-curator`) with:
- the session brief from Step 2,
- the vault root path,
- **mode: plan**.

It investigates the current vault structure and returns a proposed write-plan (files to create/update, folders to make, frontmatter, related links), flagging anything that lands in a sensitive folder (as configured) as needs-confirmation.

## Step 4 — Confirm

Present the proposed plan to the user concisely — each action as `create | update | new-folder`, its path, and a one-line why. Use `AskUserQuestion` to get approval, with options to approve all, adjust, or skip flagged items. Wait for the user's approval before proceeding.

If the user adjusts, note the adjustments for Step 5.

## Step 5 — Execute (dispatch vault-curator in execute mode)

Dispatch **vault-curator** again with the **approved plan** (with any adjustments) and **mode: execute**. It creates folders, writes new files, updates existing trackers/READMEs/CSVs, refreshes `updated:` dates, and adds `related:` links.

## Step 6 — Report

Relay the curator's report: every path created or updated, folders made, links added, and anything skipped (and why). Plain, concise, no emojis.

## Notes
- Prefer updating existing trackers/READMEs over creating new files; create folders only when genuinely needed.
- The curator respects any folder-local conventions it finds. Don't duplicate existing docs; create new versions rather than overwriting, and avoid stub-README spam. Don't override folder-local conventions without explicit instruction.

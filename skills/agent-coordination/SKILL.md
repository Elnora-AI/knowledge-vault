---
name: agent-coordination
description: |
  Coordination protocol for agents accessing the knowledge base. Use when any agent needs to fetch prior notes, templates, or reference documents from the vault.

  Triggers: fetch prior notes, access templates, find reference docs, get the template, find a prior document, previous work on, standing document, how did we handle this before
---

# Agent Coordination

## The Rule

**Call knowledge-base UNLESS you already have all context to finalize the task.**

Default: proactive checking. Not reactive.

## When to Call

| Category | Trigger Phrases |
|----------|-----------------|
| **Reference docs** | "the reference doc on", "our standard process for", "the how-to for" |
| **Templates** | "get the template", "our standard [document]", "find a template for" |
| **Standing docs** | "the standing document on", "our conventions for", "the runbook for" |
| **Procedures** | "how do we handle", "our process for", "the steps for" |
| **Prior Work** | "previous note on", "how did we handle [X] before", "prior agreement with" |


## Skip When

- Pure code generation (no vault context)
- General knowledge (not vault-specific)
- Context already fetched this task
- Facts already covered by your project instructions (use CLAUDE.md / README)

## Vault Path

Read `.claude/knowledge-base.local.md` for `vault_path` and `vault_dir`. Never hardcode paths. See the vault-access skill for tool selection and patterns.

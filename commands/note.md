---
name: note
description: Fetch URL content, summarize it, and save as a note to the vault
argument-hint: [url]
allowed-tools: WebFetch, Write, Read, Glob, Grep, AskUserQuestion
---

# Save Note from URL: $ARGUMENTS

## Task

Fetch content from the provided URL, create a summary, and save it as a properly formatted note in your knowledge base.

**URL:** $ARGUMENTS

## Instructions

### Step 1: Fetch and Analyze Content

1. Use `WebFetch` to retrieve content from the URL: `$ARGUMENTS`
2. Extract the title, main content, and key points
3. Identify the content type to determine the appropriate `type` field:
   - Technical documentation, tutorials, code → `reference`
   - Company/product information → `reference`
   - Policy or legal articles → `policy`
   - General articles and clippings → `note`
   - If unclear, default to `note`

### Step 2: Create Summary

Generate a concise summary that includes:
- **Title**: Extract or create a descriptive title
- **Key Points**: 3-7 bullet points of the most important information
- **Summary**: 2-3 paragraph overview of the content
- **Relevant quotes or data**: Include specific facts, statistics, or notable quotes

### Step 3: Generate Frontmatter

Create YAML frontmatter following the note schema:

```yaml
---
title: "[Extracted or generated title]"
type: [note|reference|policy]
status: draft
created: [today's date YYYY-MM-DD]
updated: [today's date YYYY-MM-DD]
owner: [value of default_owner from config; omit this line entirely if default_owner is empty]
tags:
  - saved-note
  - web-clipping
  - [auto-generated tags — see tagging rules below]
description: "[1-2 sentence description]"
source_url: "$ARGUMENTS"
source_title: "[Original page title]"
source_date: "[Date from page if available]"
related: []
---
```

#### Tagging Rules

Tags are for **LLM agents** searching the vault — not for human browsing. Generate them automatically from the fetched content. Do NOT ask the user to add or review tags.

1. **Extract 5-15 tags** from the page content covering:
   - Core technologies and tools mentioned (e.g., `langchain`, `react`, `postgresql`)
   - Domain/topic keywords (e.g., `web-scraping`, `authentication`, `data-pipeline`)
   - Concepts and patterns (e.g., `rag-pipeline`, `tool-calling`, `structured-extraction`)
   - Relevant ecosystems or platforms (e.g., `openai`, `aws`, `firecrawl`)
2. **Format**: lowercase, kebab-case, no special characters (e.g., `llm-integration` not `LLM Integration`)
3. **Granularity**: prefer specific terms over generic ones — `vector-database` over `database`, `react-server-components` over `frontend`
4. **Always include** `saved-note` and `web-clipping` as the first two tags
5. **Think like a search query**: what would an agent search for when it needs this note?

### Step 4: Format the Note

Structure the note as:

```markdown
---
[frontmatter]
---

# [Title]

> **Source:** [Original Title]($ARGUMENTS)
> **Saved:** [Today's date]

## Summary

[2-3 paragraph summary]

## Key Points

- [Key point 1]
- [Key point 2]
- [Key point 3]
- ...

## Details

[More detailed content if relevant]

## Notable Quotes/Data

> [Any notable quotes or specific data points]

---

*Note saved from web on [date]*
```

### Step 5: Generate Filename

Create a kebab-case filename from the title:
- Use lowercase
- Replace spaces with hyphens
- Remove special characters
- Prefix with date: `YYYY-MM-DD-[title-slug].md`

Example: `2026-01-28-understanding-rag-architecture.md`

### Step 6: Save to Vault

Read `.claude/knowledge-base.local.md` and extract `vault_path`, `vault_dir`, `notes_dir`, `index_file`, and `default_owner` from YAML frontmatter. Use `default_owner` for the `owner:` field above (omit `owner:` if it's empty).
Vault root: `{vault_path}/{vault_dir}/` (when `vault_dir` is empty, `vault_path` is the root).
Save the file to the vault's `{notes_dir}/{YYYY}/{topic}/` directory (default `notes_dir` is `notes`).

Pick `{topic}` from these buckets based on the note's primary subject:
- `tech` — software, dev tools, CLIs, SDKs, frameworks, infrastructure, AI/LLMs
- `business` — finance, tax, fundraising, sales, operations, GTM
- `research` — academic papers, studies, technical deep-dives
- `misc` — anything that doesn't fit cleanly above

Where `{YYYY}` is the year from the date prefix.

Use the `Write` tool to create the file.

### Step 7: Find and Link Related Documents

Automatically find and link related documents — don't ask, just do it:
1. If `{vault root}/{index_file}` exists (the auto-generated index, default `notes/index.md`), read it; if absent, discover structure with `Glob` instead
2. Search for documents with similar topics, tags, or entities
3. Add all relevant matches to the `related` field using standard markdown link format:
   ```yaml
   related:
     - "[Document Title](../path/to/document.md)"
   ```
4. Be selective — only link genuinely related documents, not everything that vaguely matches

### Step 8: Confirm Success

Report to the user:
- File path where note was saved
- Summary of content captured
- Related documents that were linked (with titles)
- Tags that were applied

## Error Handling

- If URL is unreachable, inform user and suggest checking the URL
- If content cannot be parsed, save raw content with a note
- If vault folder doesn't exist, create it first

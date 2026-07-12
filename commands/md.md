---
name: md
description: Convert pasted text into a properly formatted markdown file with frontmatter, save it to the right location in the vault, and link related documents
argument-hint: [paste text or describe what to convert]
allowed-tools: Read, Write, Glob, Grep, AskUserQuestion
---

# Convert Text to Vault Document

## Task

Take the user's pasted text, create a beautifully formatted markdown file with proper frontmatter, save it to the correct location in the vault, and cross-link related documents.

**Input:** $ARGUMENTS

## Instructions

### Step 1: Load Vault Paths

Read `.claude/knowledge-base.local.md` and extract `vault_path`, `vault_dir`, `index_file`, and `default_owner` from YAML frontmatter.
Vault root: `{vault_path}/{vault_dir}/` (when `vault_dir` is empty, `vault_path` is the root).
If `{vault root}/{index_file}` (the auto-generated index, default `notes/index.md`) exists, read it to understand the vault structure and existing documents. If it's absent (fresh vault), skip it and discover structure with `Glob` instead.

### Step 2: Analyze the Content

Examine the pasted text carefully to determine:

- **What type of document is this?** (note, reference, meeting, contact, policy, project, agreement, etc.)
- **What is it about?** Extract the main subject, key entities, topics
- **Who is the audience?** Yourself, your team, external collaborators
- **Does it relate to an existing company, project, or topic?** Look for names, references

Use the document type table from the frontmatter schemas to classify:

| Type | Folder | Description |
|------|--------|-------------|
| `note` | `notes/` | Catch-all notes and clippings |
| `reference` | `reference/` | How-tos, standing docs, background info |
| `meeting` / `meeting-transcript` | `meetings/` | Meeting notes and transcripts |
| `contact` / `person` | `people/` | Contacts and people |
| `policy` | `policies/` | Internal and external policies |
| `project` | `projects/` | Project docs |
| `agreement` / `contract` | `projects/` | Contracts and signed agreements (or a user `contracts/`) |

These folders are defaults — you can rename them or add your own types and folders freely. If the content doesn't clearly fit a specific category, use `note` and save to `{notes_dir}/{YYYY}/{topic}/` (year + topic bucket — see `/note` command for topic options).

### Step 3: Determine Vault Location

Based on the content analysis:

1. Identify the target folder from the type mapping above
2. Browse existing files in that folder using `Glob` to find the right subfolder
3. Check if similar documents already exist (avoid duplicates)
4. If you're unsure about the location, ask the user:
   - Present your best guess with reasoning
   - Offer 2-3 alternative locations
   - Let them choose or specify a custom path

### Step 4: Format the Document

Transform the raw text into a clean, well-structured markdown document:

1. **Clean up formatting:**
   - Fix inconsistent headings (use proper `#` hierarchy)
   - Normalize bullet points and numbered lists
   - Fix spacing and paragraph breaks
   - Convert plain URLs to markdown links where appropriate
   - Format tables properly if data is tabular
   - Add code blocks around code snippets

2. **Structure the content:**
   - Add a clear `# Title` heading
   - Organize into logical sections with `##` and `###` headings
   - Ensure content flows logically
   - Preserve all original information — don't remove content, only reformat

3. **Do NOT:**
   - Change the meaning or substance of the text
   - Add opinions or commentary
   - Remove information the user provided
   - Over-structure simple content

### Step 5: Generate Frontmatter

Read `${CLAUDE_PLUGIN_ROOT}/reference/frontmatter-schemas.md` and find the schema matching the document type from Step 2. Use only that type's fields — don't load all schemas.

**Base frontmatter (all documents):**

```yaml
---
title: "[Descriptive title extracted or generated from content]"
type: [type from step 2]
status: draft
created: [today's date YYYY-MM-DD]
updated: [today's date YYYY-MM-DD]
owner: [value of default_owner from config; omit this line entirely if default_owner is empty]
tags:
  - [topic-specific tags]
  - [entity tags like company names]
  - [category tags]
description: "[1-2 sentence description of what this document contains]"
related: []
---
```

**Add type-specific fields** based on the schema:
- Policies: add `scope`, `version`, `compliance_frameworks`, `review_cycle`
- Agreements: add `agreement_subtype`, `parties`, `jurisdiction`, `effective_date`
- Other types: add relevant optional fields from the schema

### Step 6: Generate Filename

Create a clean kebab-case filename:
- Use lowercase
- Replace spaces with hyphens
- Remove special characters
- If the content is date-specific, prefix with date: `YYYY-MM-DD-[title-slug].md`
- Otherwise just use the title slug: `[title-slug].md`

### Step 7: Save to Vault

Build the full path dynamically: `{vault_path}/{vault_dir}/{target_folder}/{filename}`

Use `Write` to save the file.

### Step 8: Find and Link Related Documents

Automatically find and link related documents — don't ask, just do it:

1. If `{vault root}/{index_file}` exists, search it for documents with similar topics, tags, or entities (skip if absent)
2. Use `Grep` to search vault content for related keywords and entities
3. Look for documents that:
   - Mention the same companies, people, or projects
   - Cover related topics or policies
   - Are in the same domain (e.g., other project docs if this is a project doc)

4. Add all relevant matches to the `related` field using standard markdown links:
   ```yaml
   related:
     - "[Document Title](../relative/path/to/document.md)"
   ```
5. Use correct relative paths from the saved file's location
6. Be selective — only link genuinely related documents, not everything that vaguely matches

### Step 9: Confirm Success

Report to the user:
- Full file path where document was saved
- Document type and folder chosen (with reasoning)
- Summary of formatting applied
- Related documents that were linked (with titles)

## Error Handling

- If the text is empty or too short, ask the user to provide the content
- If the vault folder doesn't exist, create it
- If a file with the same name exists, append a number suffix or ask the user
- If you can't determine the document type, ask the user to clarify

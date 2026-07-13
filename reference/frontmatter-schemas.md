# Frontmatter Schemas

Reference documentation for YAML frontmatter fields used across the knowledge base.

---

## Common Fields (All Documents)

These fields should appear in every document:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | ✅ | Document type (see types below) |
| `title` | string | ✅ | Human-readable document title |
| `status` | string | ✅ | Document status — see canonical values below |
| `created` | date | ✅ | Creation date (YYYY-MM-DD) |
| `updated` | date | ✅ | Last modification date |
| `owner` | string | ✅ | Document owner (kebab-case name) |
| `tags` | array | ✅ | Categorization tags |
| `description` | string | ✅ | Brief description (1-2 sentences) |
| `related` | array | ⬜ | Links to related documents (markdown format) |

---

## Document Types

The default folder scheme is a minimal, universal set. Rename or extend it freely — when a document doesn't clearly match a type below, use `note` and file it under `notes/`.

| Type | Folder | Description |
|------|--------|-------------|
| `note` | notes/ | Catch-all notes and general knowledge capture |
| `reference` | reference/ | How-tos, standing docs, company/team info |
| `task` | tasks/ | Task items (managed by the task system) |
| `meeting-transcript` / `meeting` | meetings/ | Meeting recordings, transcripts, and notes |
| `contact` / `person` | people/ | Contact records |
| `policy` | policies/ | Internal and external policies |
| `project` | projects/ | Project documentation |
| `agreement` / `contract` | projects/ (or a user `contracts/`) | Contracts, NDAs, signed agreements |
| `template` | various | Reusable document templates |
| `index` | notes/ | Auto-generated vault index / MOC documents |

Users can add their own types and folders — document them here as you introduce them so agents route consistently.

---

## Status Values

Use the most specific value that fits. Listed in approximate frequency of use.

| Value | When to use |
|-------|-------------|
| `draft` | Document is in progress, not yet finalized |
| `approved` | Document is approved and active |
| `transcribed` | Meeting transcript captured (auto-set by your transcript importer) |
| `executed` | Agreement is signed by all parties |
| `active` | Document represents an active state, ongoing work |
| `proposed` | Proposal not yet accepted |
| `archived` | Superseded or no longer in use; kept for reference |
| `completed` / `complete` | Work item finished (use `completed`) |
| `current` | Index pages, reference docs reflecting current state |
| `in-progress` | Active work in flight |
| `superseded` | Replaced by a newer version (point at it via `related:`) |
| `historical` | Old document kept for the record |
| `research` | Exploratory / research notes |
| `published` | External-facing content shipped |
| `filed` | A filing has been submitted |
| `in-negotiation` | Agreement under negotiation (not yet executed) |
| `snapshot` | Point-in-time data capture |
| `reference` | Reference / source document kept as-imported |

If none of the above fit, prefer `draft` while shaping, then move to a more specific status. Do not invent new values without adding them here first.

---

## Meeting Transcript Schema

**Type:** `meeting-transcript`
**Folder:** `meetings/`

### Required Fields

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `type` | string | `meeting-transcript` | Always `meeting-transcript` |
| `title` | string | `"Acme <> Globex Partnership Discussion"` | Meeting title |
| `status` | string | `transcribed` | Status: `transcribed`, `reviewed`, `summarized`, `archived` |
| `created` | date | `2026-01-15` | Meeting date |
| `updated` | date | `2026-01-15` | Last edit date |
| `owner` | string | `your-name` | Primary attendee/owner |
| `tags` | array | `[sales-call, acme, product]` | Categorization tags |
| `description` | string | `"Discussion of pilot terms..."` | Brief summary |
| `date` | date | `2026-01-15` | Meeting date (same as created) |
| `time` | string | `"09:00"` | Start time (HH:MM) |
| `word_count` | integer | `5000` | Transcript word count |
| `meeting_id` | string | `11111111-...` | Source system ID (transcript source ID) |
| `meeting_type` | string | `sales-call` | Meeting category (see values below) |
| `participants` | array | `["Jane Doe", "Sam Rivera"]` | Attendee names |

### Optional Fields

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `end_time` | string | `"10:00"` | End time (HH:MM) |
| `duration_minutes` | integer | `60` | Meeting duration |
| `companies` | array | `["Acme Corp", "Globex"]` | External companies involved |
| `platform` | string | `zoom` | Meeting platform |
| `recording_available` | boolean | `true` | Whether audio exists |
| `summary` | string | `"Key decisions: ..."` | AI-generated or manual summary |
| `action_items` | array | `["Follow up on pricing"]` | Action items from meeting |
| `topics` | array | `["pilot-terms", "pricing", "timeline"]` | Main topics discussed |
| `confidentiality` | string | `confidential` | `internal`, `confidential`, `public` |
| `related` | array | See format below | Links to related documents |

### Meeting Type Values

| Value | Description | Examples |
|-------|-------------|----------|
| `sales-call` | Customer/prospect calls | Discovery calls, demos, negotiations |
| `investor-call` | Investor meetings | Pitch meetings, updates, due diligence |
| `advisory` | Advisor sessions | Mentor meetings, advisory board |
| `partnership` | Partner discussions | Partner syncs, integration planning |
| `compliance-audit` | Compliance meetings | Audits, security reviews |
| `internal` | Team meetings | Planning, standups, all-hands |
| `interview` | Hiring interviews | Candidate interviews |
| `vendor` | Vendor calls | Tool demos, service providers |
| `conference` | Event meetings | Conference 1:1s |
| `legal` | Legal discussions | Contract reviews |
| `technical` | Technical discussions | Architecture, integration planning |

### Tags Convention

Use consistent tags for meetings:

**By company:** `acme`, `globex`, `initech`, `contoso`
**By topic:** `pilot`, `pricing`, `compliance`, `legal`, `technical`, `fundraising`
**By type:** `sales-call`, `advisory`, `partnership`, `audit`
**By status:** `action-required`, `follow-up-needed`, `closed`

### Related Links Format

Use standard markdown links (not wikilinks):

```yaml
related:
  - "[Acme Order Form](../projects/acme/order-form.md)"
  - "[Previous Acme Meeting - Jan 20](./2026-01-20-acme-technical-review.md)"
  - "[Privacy Policy](../policies/external/privacy-policy.md)"
```

### Example Frontmatter

```yaml
---
type: meeting-transcript
title: "Acme <> Globex Partnership Discussion"
status: reviewed
created: 2026-01-15
updated: 2026-01-15
owner: your-name
tags:
  - sales-call
  - acme
  - partnership
  - globex
description: "Discussion of Acme pilot planning and integration with Globex"
date: 2026-01-15
time: "09:00"
end_time: "10:00"
duration_minutes: 60
word_count: 5000
meeting_id: 11111111-2222-4333-8444-555555555555
meeting_type: sales-call
participants:
  - Jane Doe
  - Speaker 1 (Acme)
  - Speaker 2 (Globex)
companies:
  - Acme Corp
  - Globex
platform: zoom
recording_available: true
summary: "Planning discussion covering benchmarking and standardizing cross-organizational requirements"
topics:
  - planning
  - benchmarking
  - requirements
  - integration
confidentiality: confidential
related:
  - "[Acme NDA](../projects/acme/nda.md)"
  - "[Globex Partnership Overview](../projects/globex/partnership-overview.md)"
---
```

---

## Policy Schema

**Type:** `policy`
**Folder:** `policies/`

### Additional Fields

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `scope` | string | `external` | `internal` or `external` |
| `version` | string | `"1.0"` | Document version |
| `compliance_frameworks` | array | `[gdpr, hipaa]` | Applicable frameworks |
| `review_cycle` | string | `annual` | Review frequency |
| `review_due` | date | `2026-12-17` | Next review date |
| `last_reviewed` | date | `2025-12-17` | Last review date |
| `approver` | string | `your-name` | Approval authority |

---

## Agreement Schema

**Type:** `agreement`
**Folder:** `projects/` (or a user `contracts/`)

### Additional Fields

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `agreement_subtype` | string | `nda` | See canonical values below |
| `parties` | array | `[your-company-inc, counterparty-ltd]` | Contracting parties |
| `jurisdiction` | string | `your-jurisdiction` | Governing law jurisdiction |
| `effective_date` | date | `2025-01-15` | Agreement effective date |
| `expiration_date` | date | `2026-01-15` | Agreement end date (if applicable) |
| `value` | string | `"$50,000"` | Contract value (if applicable) |

### Agreement Subtype Values

| Value | Description |
|-------|-------------|
| `nda` | Non-disclosure / confidentiality agreement |
| `msa` | Master service agreement |
| `sow` | Statement of work |
| `order-form` | Order form (under an MSA/consultant agreement) |
| `service` | Service agreement |
| `consultant-agreement` | Consultant / independent contractor agreement |
| `employment` | Employment agreement |
| `amendment` | Amendment to an existing agreement |
| `engagement` | Engagement letter |
| `benefits` | Employee benefits agreement |

If none fit, prefer the closest match plus a `tags:` entry describing the actual subtype, and propose the new value here.

---

## YAML Style Conventions

- **String quoting**: prefer unquoted strings unless the value contains a special character (`:`, `'`, `"`, `#`, leading/trailing whitespace, leading `-`, etc.). Don't quote enum values like `meeting_type: partnership`.
- **Multi-word titles**: always quote with double quotes — `title: "Meeting on Pilot Terms"`.
- **Dates**: bare ISO format `YYYY-MM-DD` (no quotes).
- **Times**: quoted `"HH:MM"` (24-hour).
- **Lists**: block style with `-` prefix, never inline `[a, b, c]` for multi-line lists.
- **Markdown link strings in `related:`**: always double-quoted because they contain `[`, `]`, `(`, `)` — `"[Title](path.md)"`.

---

## Search Patterns

### Find by Type
```
Grep("type: meeting-transcript", path=vault)
Grep("type: policy", path=vault)
```

### Find by Company
```
Grep("companies:.*Acme", path=vault)
Grep("parties:.*globex", path=vault)
```

### Find by Meeting Type
```
Grep("meeting_type: sales-call", path=vault)
Grep("meeting_type: compliance-audit", path=vault)
```

### Find Related Documents
```
Grep("related:.*acme", path=vault)
```

---

*Last updated: 2026-05-23*

---
name: file-naming
description: |
  File naming conventions. MUST load before writing, creating, renaming, moving, or saving any file anywhere — vault, repo, cloud storage, or local disk.

  Triggers: write file, create file, rename file, move file, save file, save as, name this, export, new document, new note, generate pdf, generate report, save report, file name, filename, what should I name, where should I save
---

# File Naming

Three rules. No exceptions.

1. **All lowercase** — never uppercase except preserved vendor IDs (`inv120251045`)
2. **Hyphens not spaces** — `pilot-proposal` not `pilot proposal` or `pilot_proposal`
3. **Self-explanatory** — someone finding this file cold understands what it is

## Date Position: Always Front

Dates go at the start. Always. This sorts files chronologically.

| Granularity | When to use | Format | Example |
|-------------|-------------|--------|---------|
| **Full date** | Meetings, transcripts, receipts, daily events | `YYYY-MM-DD-` | `2026-03-10-jane-x-sam.md` |
| **Month** | Invoices, monthly reports, investor updates | `YYYY-MM-` | `2026-02-investor-update.md` |
| **Quarter** | Quarterly financials, quarterly reviews | `YYYY-qN-` | `2026-q1-accounting-audit.md` |
| **Year** | Annual reports, tax docs, yearly summaries | `YYYY-` | `2025-cash-flow.md` |
| **No date** | Templates, policies, reference docs, agreements | — | `master-service-agreement.docx` |

**When does a file get a date?** If it describes something that happened or was produced at a specific time → date it. If it's a living/reusable document → no date.

## Suffixes (End of Filename, Before Extension)

Suffixes tell you the document's state at a glance. Stack them in this order:

`[name]-[status]-[variant].[ext]`

| Suffix | Meaning | Example |
|--------|---------|---------|
| `-signed` | Legally executed | `2026-03-01-agreement-acme-globex-signed.pdf` |
| `-draft` | Not final | `pilot-proposal-draft.docx` |
| `-reviewed` | Reviewed but not signed | `agreement-reviewed.docx` |
| `-vN` | Version number | `project-proposal-v2.docx` |
| `-eng`, `-est` | Language variant | `annual-report-2025-eng.pdf` |
| `-redlined` | Has tracked changes | `msa-redlined.docx` |
| `-cleaned` | Cleaned/processed data | `inventory-acme-cleaned.xlsx` |

Multiple suffixes stack: `2025-10-13-agreement-acme-globex-signed-eng.pdf`

## Document Type Patterns

### Business Documents

| Type | Pattern | Example |
|------|---------|---------|
| **Meeting transcript** | `YYYY-MM-DD-participants-topic.md` | `2026-03-10-jane-x-sam.md` |
| **Proposal** | `YYYY-MM-client-document-type.docx` | `2025-12-acme-pilot-proposal.docx` |
| **Agreement** | `parties-agreement-type.docx` | `acme-and-globex-pilot-agreement.docx` |
| **SAFE** | `YYYY-MM-DD-safe-company-investor[-signed].pdf` | `2025-10-13-safe-acme-globex-ventures-signed.pdf` |
| **Invoice** | `YYYY-MM-vendor-invoice-vendorID.pdf` | `2026-02-acme-invoice-inv120251045.pdf` |
| **Receipt** | `YYYY-MM-DD-vendor-receipt-amount.pdf` | `2026-01-11-acme-receipt-13-68.pdf` |
| **Order form** | `order-form-OF-CLIENT-YYYY-NN.md` | `order-form-OF-ACME-2026-01.md` |
| **NDA/CDA** | `parties-nda.docx` or `parties-cda.docx` | `acme-and-globex-nda.docx` |
| **Board resolution** | `YYYY-MM-DD-NN-board-resolution-description[-signed].pdf` | `2026-03-01-01-board-resolution-founder-share-purchase-signed.pdf` |

### Financial Documents

| Type | Pattern | Example |
|------|---------|---------|
| **Bank transactions** | `bank-transaction-type-YYYY.csv` | `acme-bank-all-credit-transactions-2025.csv` |
| **Quarterly financials** | `company-entity-financials-qN-YYYY.xlsx` | `acme-inc-financials-q1-2025.xlsx` |
| **Tax forms** | `form-number-YYYY-entity.md` | `1099-nec-2025-globex-consulting-inc.md` |
| **Investor update** | `YYYY-MM-investor-update.md` | `2026-02-investor-update.md` |

### Compliance & Evidence

| Type | Pattern | Example |
|------|---------|---------|
| **ISMS policy** | `NN-isms-title.pdf` | `01-isms-scope-of-the-isms.pdf` |
| **Customer policy** | `policy-name.pdf` (no number) | `acceptable-use-policy.pdf` |
| **Compliance evidence** | `NN-description-YYYYMMDD.png` | `01-autoscaling-frontend-service-20260204.png` |
| **Audit report** | `YYYY-MM-standard-audit-type.md` | `2026-01-iso27001-internal-audit-report.md` |

### People & HR

| Type | Pattern | Example |
|------|---------|---------|
| **CV** | `cv-person-name.pdf` | `cv-jane-doe.pdf` |
| **Contact** | `first-last.md` | `sam-rivera.md` |
| **Contract template** | `agreement-type.docx` | `employment-agreement.docx` |

### Vault Notes

| Type | Pattern | Example |
|------|---------|---------|
| **Research note** | `YYYY-MM-DD-topic.md` | `2026-01-26-vector-databases.md` |
| **Reference doc** | `topic-name.md` (no date) | `onboarding-guide.md` |
| **Daily log** | `YYYY-MM-DD.md` (date only) | `2026-02-26.md` |
| **Blog post** | `YYYY-MM-DD-slug.md` | `2026-03-25-product-launch-blog-post.md` |

## Entity Markers

Entity markers are optional. When a document involves specific legal entities, use the full entity name so it is unambiguous:

| Marker | Entity |
|--------|--------|
| `your-company-inc` | Parent entity (e.g. US C-corp) |
| `your-company-ltd` | Subsidiary or other legal entity |

## Folder Naming

Same three rules apply. Common patterns:

| Location | Pattern | Example |
|----------|---------|---------|
| **Vault top-level** | `category/` | `projects/` |
| **Accounting year** | `YYYY-document-type-entity/` | `2025-quarterly-financials-inc/` |
| **Events** | `YYYY-event-name/` | `2026-industry-conference/` |
| **Invoice months** | `YYYY-MM/` | `2026-01/` |
| **Investor folders** | `partner-name/` | `globex-ventures/` |

## Participant Naming in Transcripts

- Two people: `name-x-name` → `jane-x-sam`
- Multiple parties: `org1-org2-topic` → `acme-globex-pilot-call`
- Use first names when unambiguous, full names when needed

## Never Do

- Spaces in filenames
- Mixed case (`Acme-Proposal.pdf`)
- Underscores (except legacy scientific data — leave those alone)
- Possessives (`jane's-laptop`)
- Missing dates on dated documents
- Dates at the end (always front)

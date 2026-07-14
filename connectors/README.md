# Connectors (optional)

A small, source-agnostic framework for syncing **dated, attributed records** — meeting transcripts, call notes, voice memos — from an external tool into your vault. It's off by default and the core plugin never depends on it.

Bring your own tool: implement one small `Source` adapter and the framework handles deduplication, optional LLM formatting, vault routing, atomic writes, sync state, CRM linking, action-item extraction, verification, and scheduling.

## How it works

```
Source.list_pending()  ->  ready & not-yet-synced refs
Source.fetch(id)       ->  a Record (title, participants, segments)
        │
        ▼
formatter.format_record()   optional LLM metadata + verbatim body; passthrough otherwise
        ▼
vault_writer.write_record() routes by type, writes atomic markdown + frontmatter
        ▼
crm (optional)              match participants by email, stamp last-contact fields,
                            auto-create + enrich rows in your CSV CRM
        ▼
tasks (optional)            append extracted action items to your task inbox
        ▼
SyncState                   remembers processed ids (idempotent across runs)
```

- **`framework/`** — the reusable spine: `models`, `source` (the protocol), `state`, `formatter`, `vault_writer`, `crm`, `tasks`, `verifier`, `scheduler`, `engine`, `config`.
- **`sources/json_folder.py`** — the reference adapter. Reads records from a folder of JSON files. Universal and dependency-free — start here.
- **`sources/quill.py`** — a real-world adapter for the [Quill](https://quill.chat) meeting recorder (reads its local SQLite database, read-only). A worked example; requires Quill installed.

## Quick start (JSON adapter)

1. Copy `config.example.json` somewhere and edit it. Keep `source_name: "json"` and point `source_folder` at a folder of record JSON files (shape documented in `sources/json_folder.py`).
2. The vault root is read from your `.claude/knowledge-base.local.md` automatically.
3. Run:

```sh
python3 connectors/cli.py list-pending --config my-config.json
python3 connectors/cli.py sync         --config my-config.json
python3 connectors/cli.py verify       --config my-config.json
python3 connectors/cli.py status       --config my-config.json
```

`sync` writes one markdown file per record into the routed folder (default `meetings/{YYYY}/`), with frontmatter (`title`, `date`, `participants`, `record_id`, …) and `## Summary` / `## Transcript` sections.

## Write your own adapter

Create `sources/mytool.py` with a class exposing four members:

```python
class MyToolSource:
    name = "mytool"                     # frontmatter platform + state namespace

    def list_pending(self, since, min_age_minutes, max_age_days) -> list[RecordRef]: ...
    def is_ready(self, ref) -> bool: ...
    def fetch(self, record_id) -> Record | None: ...
```

Return framework `Record` / `Person` / `Segment` objects (see `framework/models.py`). Then register it in `cli.py`'s `build_source`. That's the whole integration — everything downstream is shared.

## LLM formatting (optional)

Set `"llm_enabled": true` and provide `ANTHROPIC_API_KEY` in the environment (`pip install anthropic`), or point `env_file` at a file that exports it. Azure AI Services (`AZURE_ANTHROPIC_ENDPOINT` + `AZURE_ANTHROPIC_API_KEY`) and generic gateways (`ANTHROPIC_GATEWAY_URL` + `ANTHROPIC_GATEWAY_KEY`) are supported too. Two calls per record:

1. **Metadata** — summary, record type (classified against your route keys), tags, external organizations, action items, and (when CRM is on) per-participant enrichment facts. Strict JSON, retried on transient errors.
2. **Verbatim body** (`llm_verbatim`, default on) — the complete formatted transcript as plain text, with an escalating output-token budget on truncation. Multilingual records stay in their original language.

Without a key — or on any error — formatting falls back to a clean passthrough, so a sync always makes progress.

## CRM linking (optional)

If you keep a lightweight CSV CRM inside your vault (e.g. `crm/contacts.csv`), the connector can keep it in sync with your meetings. Enable `crm.enabled` and define one or more **registries** — each maps an enrichment category to a contacts CSV (plus an optional organizations CSV):

- **Match & stamp** — participants matched by email get `last_contact_date`, `last_contact_channel`, `last_meeting_date`, and `last_meeting_transcript` stamped. Matched contacts are linked from the transcript's `related:` frontmatter.
- **Auto-create** — unknown external participants get a new row (their organization is created first when the registry has an `org_csv`). Internal people (`internal_domains`, `internal_names`, the owner) are skipped.
- **Enrich** — what a participant shared on the call is appended to their `notes` column as a dated fragment (idempotent).

Everything is **column-driven**: only columns that already exist in your CSV headers are ever written, so any schema works. The CSVs must already exist with a header row — the framework never invents a schema. Every mutation is logged to a JSONL audit file in the state directory.

## Action items → task inbox (optional)

Set `tasks.enabled: true` and extracted action items are appended to the task inbox from your `.claude/knowledge-base.local.md` (`task_inbox`), as `- [ ] #task …` lines with the source transcript linked and concrete due hints ("by Friday", "next week") resolved to real dates. Fuzzy dedup keeps re-synced records from duplicating tasks.

## Verification

`verify` audits the vault against the source and exits 2 on failures — catches missing files, truncated bodies (<30% of source length), and files missing the `## Transcript` section. Records the source never captured content for (`empty_source`) and records still waiting in the sync cooldown (`pending`) are reported but don't fail.

## Maintenance commands

```sh
python3 connectors/cli.py mark-all-done --config cfg.json --before 2026-01-01   # sync only new records from a cutoff
python3 connectors/cli.py resync --config cfg.json --since 2026-03-01 --dry-run # clear a range for re-processing
python3 connectors/cli.py rename --config cfg.json --record-id ID --title "New" # fix a title everywhere at once
python3 connectors/cli.py sync   --config cfg.json --content-only               # backfill without CRM/task writes
```

## Scheduling

```sh
python3 connectors/cli.py install-schedule   --config cfg.json
python3 connectors/cli.py uninstall-schedule --config cfg.json
```

Registers the sync on your OS's native scheduler — a launchd LaunchAgent (macOS), a Task Scheduler task (Windows), or a user crontab line (Linux) — every `schedule_sync_hours`, plus a weekly `verify` job when `schedule_verify` is true. Secrets are never written into job definitions; put `ANTHROPIC_API_KEY` in a file referenced by `env_file` instead. If the native scheduler can't be driven, the exact command is printed for manual setup.

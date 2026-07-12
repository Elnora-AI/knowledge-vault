# Connectors (optional)

A small, source-agnostic framework for syncing **dated, attributed records** — meeting transcripts, call notes, voice memos — from an external tool into your vault. It's off by default and the core plugin never depends on it.

Bring your own tool: implement one small `Source` adapter and the framework handles deduplication, optional LLM formatting, vault routing, atomic writes, and sync state.

## How it works

```
Source.list_pending()  ->  ready & not-yet-synced refs
Source.fetch(id)       ->  a Record (title, participants, segments)
        │
        ▼
formatter.format_record()   optional LLM summary/tags; passthrough otherwise
        ▼
vault_writer.write_record() routes by type, writes atomic markdown + frontmatter
        ▼
SyncState                   remembers processed ids (idempotent across runs)
```

- **`framework/`** — the reusable spine: `models`, `source` (the protocol), `state`, `formatter`, `vault_writer`, `verifier`, `engine`, `config`.
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

Set `"llm_enabled": true` and provide `ANTHROPIC_API_KEY` in the environment (`pip install anthropic`). The formatter then adds a summary, tags, and action items. Without it — or on any error — it falls back to a clean passthrough, so a sync always makes progress.

## Scheduling

Run `connectors/cli.py sync` on whatever scheduler your OS provides — `cron` (Linux/macOS), a launchd agent (macOS), or Task Scheduler (Windows). Nothing here is macOS-specific.

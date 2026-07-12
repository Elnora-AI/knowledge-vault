#!/usr/bin/env python3
"""Connector CLI — sync external records into the vault.

Usage:
    python3 connectors/cli.py sync         --config path/to/config.json [--limit N] [--dry-run] [--since YYYY-MM-DD]
    python3 connectors/cli.py list-pending --config path/to/config.json
    python3 connectors/cli.py status       --config path/to/config.json
    python3 connectors/cli.py verify       --config path/to/config.json [--since YYYY-MM-DD]

The config's `source_name` selects the adapter ("json" or "quill"). For the JSON
adapter, set `source_folder` in the config. Bring your own tool by adding an
adapter under connectors/sources/ and registering it in `build_source` below.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from connectors.framework import ConnectorConfig, SyncEngine, SyncState, verifier
from connectors.sources.json_folder import JsonFolderSource
from connectors.sources.quill import QuillSource


def build_source(cfg: ConnectorConfig, raw: dict):
    name = cfg.source_name
    if name == "json":
        folder = raw.get("source_folder")
        if not folder:
            sys.exit("config error: source_folder is required for the json source")
        return JsonFolderSource(folder)
    if name == "quill":
        return QuillSource(raw.get("source_db_path"))
    sys.exit(f"config error: unknown source_name '{name}' (expected 'json' or 'quill')")


def _parse_since(value: str | None):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        sys.exit(f"invalid --since date: {value} (expected YYYY-MM-DD)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="connectors", description="Sync external records into the vault.")
    parser.add_argument("command", choices=["sync", "list-pending", "status", "verify"])
    parser.add_argument("--config", required=True, help="Path to the connector JSON config")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--since", default=None)
    args = parser.parse_args(argv)

    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cfg = ConnectorConfig.load(args.config)
    source = build_source(cfg, raw)
    since = _parse_since(args.since)

    if args.command == "list-pending":
        refs = source.list_pending(since, cfg.min_age_minutes, cfg.max_age_days)
        for ref in refs:
            when = ref.started_at.strftime("%Y-%m-%d") if ref.started_at else "????-??-??"
            print(f"{when}  {ref.id}  {ref.title}")
        print(f"\n{len(refs)} pending", file=sys.stderr)
        return 0

    if args.command == "status":
        state = SyncState(source.name, cfg.state_dir)
        print(json.dumps({
            "source": source.name,
            "vault_root": str(cfg.vault_root),
            "processed": len(state.processed_ids),
            "total_synced": state.total_synced,
            "sync_since": state.sync_since,
        }, indent=2))
        return 0

    if args.command == "verify":
        result = verifier.verify(source, cfg, since)
        print(json.dumps({
            "ok": len(result.ok),
            "missing": result.missing,
            "truncated": result.truncated,
            "malformed": result.malformed,
        }, indent=2))
        return 2 if result.failed else 0

    # sync
    engine = SyncEngine(source, cfg)
    result = engine.sync(limit=args.limit, dry_run=args.dry_run, since=since)
    for path in result.written:
        print(("[dry-run] " if args.dry_run else "wrote ") + str(path))
    print(
        f"\n{result.count} written, {result.skipped} skipped, {len(result.failed)} failed",
        file=sys.stderr,
    )
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Connector CLI — sync external records into the vault.

Usage:
    python3 connectors/cli.py sync          --config cfg.json [--limit N] [--dry-run] [--since YYYY-MM-DD] [--content-only]
    python3 connectors/cli.py list-pending  --config cfg.json
    python3 connectors/cli.py status        --config cfg.json
    python3 connectors/cli.py verify        --config cfg.json [--since YYYY-MM-DD]
    python3 connectors/cli.py mark-all-done --config cfg.json [--before YYYY-MM-DD]
    python3 connectors/cli.py resync        --config cfg.json --since YYYY-MM-DD [--until YYYY-MM-DD] [--dry-run]
    python3 connectors/cli.py rename        --config cfg.json --record-id ID --title "New Title" [--dry-run]
    python3 connectors/cli.py install-schedule   --config cfg.json
    python3 connectors/cli.py uninstall-schedule --config cfg.json

The config's `source_name` selects the adapter ("json" or "quill"). For the JSON
adapter, set `source_folder` in the config. Bring your own tool by adding an
adapter under connectors/sources/ and registering it in `build_source` below.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from connectors.framework import (  # noqa: E402
    ConnectorConfig,
    SyncEngine,
    SyncState,
    scheduler,
    vault_writer,
    verifier,
)
from connectors.sources.json_folder import JsonFolderSource  # noqa: E402
from connectors.sources.quill import QuillSource  # noqa: E402


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
        sys.exit(f"invalid date: {value} (expected YYYY-MM-DD)")


# ---------------------------------------------------------------------------
# Vault-file lookup by record id (used by resync + rename)
# ---------------------------------------------------------------------------

def _id_index(cfg: ConnectorConfig) -> dict[str, Path]:
    pattern = re.compile(
        r'^(?:' + "|".join(re.escape(k) for k in cfg.id_keys) + r'):\s*"?([^"\n]+)"?\s*$',
        re.MULTILINE,
    )
    index: dict[str, Path] = {}
    for path in cfg.vault_root.rglob("*.md"):
        try:
            head = path.read_text(encoding="utf-8")[:2000]
        except OSError:
            continue
        m = pattern.search(head)
        if m:
            index[m.group(1).strip()] = path
    return index


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_sync(args, cfg, source) -> int:
    engine = SyncEngine(source, cfg)
    result = engine.sync(limit=args.limit, dry_run=args.dry_run,
                         since=_parse_since(args.since),
                         content_only=args.content_only)
    for path in result.written:
        print(("[dry-run] " if args.dry_run else "wrote ") + str(path))
    summary = f"\n{result.count} written, {result.skipped} skipped, {len(result.failed)} failed"
    extras = []
    if result.crm_stamped:
        extras.append(f"{result.crm_stamped} CRM rows stamped")
    if result.crm_created:
        extras.append(f"{result.crm_created} contacts created")
    if result.crm_orgs_created:
        extras.append(f"{result.crm_orgs_created} orgs created")
    if result.crm_enriched:
        extras.append(f"{result.crm_enriched} notes enriched")
    if result.tasks_added:
        extras.append(f"{result.tasks_added} tasks added to inbox")
    if extras:
        summary += "\n" + ", ".join(extras)
    print(summary, file=sys.stderr)
    return 1 if result.failed else 0


def cmd_list_pending(args, cfg, source) -> int:
    state = SyncState(source.name, cfg.state_dir)
    since = _parse_since(args.since)
    if since is None and state.sync_since:
        since = _parse_since(state.sync_since)
    refs = [r for r in source.list_pending(since, cfg.min_age_minutes, cfg.max_age_days)
            if not state.is_processed(r.id)]
    for ref in refs:
        when = ref.started_at.strftime("%Y-%m-%d") if ref.started_at else "????-??-??"
        print(f"{when}  {ref.id}  {ref.title}")
    print(f"\n{len(refs)} pending", file=sys.stderr)
    return 0


def cmd_status(args, cfg, source) -> int:
    state = SyncState(source.name, cfg.state_dir)
    print(json.dumps({
        "source": source.name,
        "vault_root": str(cfg.vault_root),
        "processed": len(state.processed_ids),
        "total_synced": state.total_synced,
        "sync_since": state.sync_since,
    }, indent=2))
    return 0


def cmd_verify(args, cfg, source) -> int:
    state = SyncState(source.name, cfg.state_dir)
    since = _parse_since(args.since)
    if since is None and state.sync_since:
        since = _parse_since(state.sync_since)
    result = verifier.verify(source, cfg, since, processed_ids=state.processed_ids)
    print(json.dumps({
        "ok": len(result.ok),
        "empty_source": len(result.empty_source),
        "pending": len(result.pending),
        "missing": result.missing,
        "truncated": result.truncated,
        "malformed": result.malformed,
    }, indent=2))
    if result.failed:
        print(f"[FAIL] {len(result.missing) + len(result.truncated) + len(result.malformed)} "
              "issue(s) found", file=sys.stderr)
        return 2
    print("all healthy", file=sys.stderr)
    return 0


def cmd_mark_all_done(args, cfg, source) -> int:
    """Set a sync_since cutoff: only records on/after the date will ever sync."""
    cutoff = args.before or date.today().isoformat()
    _parse_since(cutoff)  # validates
    state = SyncState(source.name, cfg.state_dir)
    state.sync_since = cutoff
    state.save()
    remaining = [r for r in source.list_pending(_parse_since(cutoff),
                                                cfg.min_age_minutes, cfg.max_age_days)
                 if not state.is_processed(r.id)]
    print(f"Set sync_since = {cutoff}")
    print(f"  Only records on or after {cutoff} will be synced.")
    print(f"  {len(remaining)} record(s) remaining in queue.")
    return 0


def cmd_resync(args, cfg, source) -> int:
    """Clear vault files + processed ids for a date range so records re-sync."""
    if not args.since:
        sys.exit("--since is required for resync (e.g. --since 2026-01-01)")
    since = _parse_since(args.since)
    until = _parse_since(args.until) if args.until else date.today() + timedelta(days=1)

    refs = source.list_pending(since, 0, 0)
    target = [r for r in refs
              if r.started_at and since <= r.started_at.date() < until]
    if not target:
        print("No records in range to resync.")
        return 0

    index = _id_index(cfg)
    files = [(r.id, index[r.id]) for r in target if r.id in index]

    print(f"Will resync {len(target)} record(s) between {args.since} and "
          f"{args.until or 'now'}.")
    print(f"  Vault files to delete: {len(files)}")
    print(f"  No vault file found (will simply re-sync): {len(target) - len(files)}")
    if args.dry_run:
        for _, fp in files:
            print(f"  would delete: {fp}")
        return 0

    state = SyncState(source.name, cfg.state_dir)
    backup = state.path.with_suffix(
        f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    if state.path.exists():
        backup.write_text(state.path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backed up state to {backup.name}")
    target_ids = {r.id for r in target}
    removed = len(state.processed_ids & target_ids)
    state.processed_ids -= target_ids
    state.total_synced = len(state.processed_ids)
    state.save()
    print(f"Removed {removed} id(s) from processed state.")
    for _, fp in files:
        fp.unlink()
    print(f"Deleted {len(files)} vault file(s).")
    print("\nNext step: run `sync` to reprocess.")
    return 0


def cmd_rename(args, cfg, source) -> int:
    """Rename a synced record's title, H1, and filename in one shot."""
    index = _id_index(cfg)
    target = index.get(args.record_id)
    if target is None:
        sys.exit(f"No vault file found for record id {args.record_id}")

    text = target.read_text(encoding="utf-8")
    m = re.search(r'^title:\s*"?(.*?)"?\s*$', text[:2000], re.MULTILINE)
    old_title = m.group(1).replace('\\"', '"') if m else ""
    date_m = re.match(r"^(\d{4}-\d{2}-\d{2})-", target.name)
    date_str = date_m.group(1) if date_m else "undated"

    new_path = target.with_name(vault_writer.build_filename(date_str, args.title))
    new_text = text
    if old_title:
        new_text = new_text.replace(f'title: "{old_title}"', f'title: "{args.title}"', 1)
        new_text = new_text.replace(f"title: {old_title}\n", f'title: "{args.title}"\n', 1)
        new_text = new_text.replace(f"# {old_title}", f"# {args.title}", 1)

    print(f"Rename plan ({'DRY-RUN' if args.dry_run else 'applying'}):")
    print(f"  record id : {args.record_id}")
    print(f"  old title : {old_title!r}")
    print(f"  new title : {args.title!r}")
    print(f"  old path  : {target}")
    print(f"  new path  : {new_path}")
    if args.dry_run:
        return 0
    if new_path.exists() and new_path != target:
        sys.exit(f"target filename already exists: {new_path}")
    target.write_text(new_text, encoding="utf-8")
    if new_path != target:
        target.rename(new_path)
    print("Renamed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="connectors",
                                     description="Sync external records into the vault.")
    parser.add_argument("command", choices=[
        "sync", "list-pending", "status", "verify", "mark-all-done",
        "resync", "rename", "install-schedule", "uninstall-schedule",
    ])
    parser.add_argument("--config", required=True, help="Path to the connector JSON config")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--since", default=None)
    parser.add_argument("--until", default=None, help="resync: exclusive upper bound")
    parser.add_argument("--before", default=None, help="mark-all-done: cutoff date")
    parser.add_argument("--content-only", action="store_true",
                        help="sync: write vault files only; skip CRM + task stages "
                             "(for backfilling old records)")
    parser.add_argument("--record-id", default=None, help="rename: the record to rename")
    parser.add_argument("--title", default=None, help="rename: the new title")
    args = parser.parse_args(argv)

    raw = json.loads(Path(args.config).read_text(encoding="utf-8"))
    cfg = ConnectorConfig.load(args.config)

    if args.command == "install-schedule":
        return 0 if scheduler.install(cfg, args.config) else 1
    if args.command == "uninstall-schedule":
        scheduler.uninstall(cfg, args.config)
        return 0

    source = build_source(cfg, raw)

    if args.command == "sync":
        return cmd_sync(args, cfg, source)
    if args.command == "list-pending":
        return cmd_list_pending(args, cfg, source)
    if args.command == "status":
        return cmd_status(args, cfg, source)
    if args.command == "verify":
        return cmd_verify(args, cfg, source)
    if args.command == "mark-all-done":
        return cmd_mark_all_done(args, cfg, source)
    if args.command == "resync":
        return cmd_resync(args, cfg, source)
    if args.command == "rename":
        if not args.record_id or not args.title:
            sys.exit("rename requires --record-id and --title")
        return cmd_rename(args, cfg, source)
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())

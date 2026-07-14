"""SyncEngine — the source-agnostic orchestrator.

list_pending -> (ready & not-processed) -> fetch -> format -> write -> CRM ->
tasks -> mark. Everything specific to a tool lives behind the Source;
everything specific to a vault lives in ConnectorConfig. This class knows
neither.

The optional CRM and task stages run AFTER the vault write and never fail the
sync — the transcript is already safely on disk. ``content_only=True`` skips
both stages (useful for backfilling old records without back-dating CRM rows
or flooding the task inbox with stale action items).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import crm, formatter, tasks, vault_writer
from .config import ConnectorConfig
from .source import Source
from .state import SyncState


@dataclass
class SyncResult:
    written: list[Path] = field(default_factory=list)
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    crm_created: int = 0
    crm_enriched: int = 0
    crm_orgs_created: int = 0
    crm_stamped: int = 0
    tasks_added: int = 0

    @property
    def count(self) -> int:
        return len(self.written)


class SyncEngine:
    def __init__(self, source: Source, cfg: ConnectorConfig, state: SyncState | None = None):
        self.source = source
        self.cfg = cfg
        self.state = state or SyncState(source.name, cfg.state_dir)

    def list_pending(self, since: date | None = None) -> list:
        cutoff = since
        if cutoff is None and self.state.sync_since:
            try:
                cutoff = date.fromisoformat(self.state.sync_since)
            except ValueError:
                cutoff = None
        return self.source.list_pending(cutoff, self.cfg.min_age_minutes, self.cfg.max_age_days)

    def sync(self, limit: int | None = None, dry_run: bool = False,
             since: date | None = None, content_only: bool = False) -> SyncResult:
        result = SyncResult()
        refs = self.list_pending(since)
        for ref in refs:
            if limit is not None and result.count >= limit:
                break
            if self.state.is_processed(ref.id):
                result.skipped += 1
                continue
            if not self.source.is_ready(ref):
                result.skipped += 1
                continue

            record = self.source.fetch(ref.id)
            if record is None:
                result.failed.append(ref.id)
                continue

            # No content to sync (e.g. a failed/cancelled recording): mark it
            # processed so it isn't retried every run, and move on.
            if not record.segments and not record.raw_text.strip():
                result.skipped += 1
                if not dry_run:
                    self.state.mark_processed(ref.id)
                    self.state.save()
                continue

            date_str = (record.started_at.strftime("%Y-%m-%d")
                        if record.started_at else "undated")

            # CRM matching happens before the write so related links land in
            # the document frontmatter.
            matches = crm.match_participants(record.participants, self.cfg)

            fmt = formatter.format_record(record, self.cfg)
            dest_folder = vault_writer.route(fmt.record_type, self.cfg)
            links = crm.related_links(matches, dest_folder, self.cfg)

            if dry_run:
                result.written.append(Path(vault_writer.build_filename(date_str, record.title)))
                continue

            path = vault_writer.write_record(record, fmt, self.cfg, related_links=links)
            result.written.append(path)
            transcript_rel = path.relative_to(self.cfg.vault_root).as_posix()

            # Post-write stages are best-effort: the transcript is on disk, so
            # a CRM or inbox hiccup must not fail the sync or block the state
            # save that keeps the run idempotent.
            if not content_only:
                try:
                    result.crm_stamped += crm.stamp_matches(
                        matches, date_str, transcript_rel, self.cfg)
                    crm_summary = crm.create_or_enrich(
                        fmt.enrichment, matches, date_str, transcript_rel,
                        record.title, self.cfg)
                    result.crm_created += crm_summary["created"]
                    result.crm_enriched += crm_summary["enriched"]
                    result.crm_orgs_created += crm_summary["created_orgs"]
                except Exception:  # noqa: BLE001
                    pass
                try:
                    result.tasks_added += tasks.write_action_items(
                        fmt.action_items, record.title, date_str,
                        transcript_rel, self.cfg, crm_matches=matches)
                except Exception:  # noqa: BLE001
                    pass

            # Save state after EACH record so progress survives crashes.
            self.state.mark_processed(ref.id)
            self.state.save()

        if not dry_run:
            self.state.save()
        return result

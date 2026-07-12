"""SyncEngine — the source-agnostic orchestrator.

list_pending -> (ready & not-processed) -> fetch -> format -> write -> mark.
Everything specific to a tool lives behind the Source; everything specific to a
vault lives in ConnectorConfig. This class knows neither.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import formatter, vault_writer
from .config import ConnectorConfig
from .source import Source
from .state import SyncState


@dataclass
class SyncResult:
    written: list[Path] = field(default_factory=list)
    skipped: int = 0
    failed: list[str] = field(default_factory=list)

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

    def sync(self, limit: int | None = None, dry_run: bool = False, since: date | None = None) -> SyncResult:
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

            fmt = formatter.format_record(record, self.cfg)
            if dry_run:
                result.written.append(Path(vault_writer.build_filename(
                    record.started_at.strftime("%Y-%m-%d") if record.started_at else "undated",
                    record.title,
                )))
                continue

            path = vault_writer.write_record(record, fmt, self.cfg)
            result.written.append(path)
            self.state.mark_processed(ref.id)

        if not dry_run:
            self.state.save()
        return result

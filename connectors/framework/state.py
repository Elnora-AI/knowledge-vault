"""Sync state — idempotency across runs.

Tracks which record ids have been synced and an optional cutoff. Stored as JSON,
namespaced per source, written atomically.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def default_state_dir() -> Path:
    """A per-user state directory that is never inside the repo."""
    override = os.environ.get("KNOWLEDGE_VAULT_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "knowledge-vault"


class SyncState:
    def __init__(self, source_name: str, state_dir: Path | None = None):
        self.source_name = source_name
        base = state_dir or default_state_dir()
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / f"{source_name}-sync-state.json"
        self.processed_ids: set[str] = set()
        self.sync_since: str | None = None
        self.total_synced: int = 0
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        self.processed_ids = set(data.get("processed_ids", []))
        self.sync_since = data.get("sync_since")
        self.total_synced = int(data.get("total_synced", 0))

    def is_processed(self, record_id: str) -> bool:
        return record_id in self.processed_ids

    def mark_processed(self, record_id: str) -> None:
        if record_id not in self.processed_ids:
            self.processed_ids.add(record_id)
            self.total_synced += 1

    def save(self) -> None:
        payload = {
            "source": self.source_name,
            "processed_ids": sorted(self.processed_ids),
            "sync_since": self.sync_since,
            "total_synced": self.total_synced,
        }
        # Atomic write: temp file in the same dir, then replace.
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

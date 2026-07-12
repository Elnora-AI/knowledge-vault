"""The Source protocol — the one interface an adapter implements.

To connect a new tool (Granola, Otter, Fireflies, a folder of JSON, …), write a
class with these four members. The SyncEngine does everything else: dedup,
formatting, vault writing, and state.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from .models import Record, RecordRef


@runtime_checkable
class Source(Protocol):
    name: str
    """Short identifier, e.g. "quill". Used as the frontmatter platform and the
    state-file namespace."""

    def list_pending(
        self, since: date | None, min_age_minutes: int, max_age_days: int
    ) -> list[RecordRef]:
        """Return refs to records eligible to sync (finished, in the age window)."""
        ...

    def fetch(self, record_id: str) -> Record | None:
        """Fetch a full record by id, or None if it cannot be read."""
        ...

    def is_ready(self, ref: RecordRef) -> bool:
        """Source-specific 'finished processing' test for a ref."""
        ...

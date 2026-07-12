"""JSON-folder source — the reference adapter.

Reads records from a folder of `.json` files, one record per file. This is the
simplest possible Source: universal, dependency-free, and easy to test. Use it as
the template for your own adapter (Granola, Otter, Fireflies, an API, …).

Each JSON file looks like:

    {
      "id": "rec-001",
      "title": "Acme <> Globex sync",
      "started_at": "2026-03-10T15:00:00",
      "ended_at": "2026-03-10T15:30:00",
      "ready": true,
      "participants": [{"name": "Jane Doe", "email": "jane@example.com"}],
      "segments": [{"speaker": "Jane Doe", "text": "Hello.", "is_owner": true}]
    }
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from ..framework.models import Person, Record, RecordRef, Segment


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class JsonFolderSource:
    name = "json"

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)

    def _load(self, path: Path) -> dict | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _path_for(self, record_id: str) -> Path | None:
        for path in self.folder.glob("*.json"):
            data = self._load(path)
            if data and str(data.get("id")) == record_id:
                return path
        return None

    def list_pending(self, since: date | None, min_age_minutes: int, max_age_days: int) -> list[RecordRef]:
        refs: list[RecordRef] = []
        for path in sorted(self.folder.glob("*.json")):
            data = self._load(path)
            if not data or not data.get("id"):
                continue
            started = _parse_dt(data.get("started_at"))
            if since and started and started.date() < since:
                continue
            refs.append(
                RecordRef(
                    id=str(data["id"]),
                    title=data.get("title", "Untitled"),
                    started_at=started,
                    extra={"ready": bool(data.get("ready", True))},
                )
            )
        return refs

    def is_ready(self, ref: RecordRef) -> bool:
        return bool(ref.extra.get("ready", True))

    def fetch(self, record_id: str) -> Record | None:
        path = self._path_for(record_id)
        if path is None:
            return None
        data = self._load(path)
        if not data:
            return None
        participants = [
            Person(name=p.get("name", ""), email=p.get("email"), role=p.get("role"))
            for p in data.get("participants", [])
        ]
        segments = [
            Segment(speaker=s.get("speaker", ""), text=s.get("text", ""), is_owner=bool(s.get("is_owner")))
            for s in data.get("segments", [])
        ]
        return Record(
            id=str(data["id"]),
            title=data.get("title", "Untitled"),
            started_at=_parse_dt(data.get("started_at")),
            ended_at=_parse_dt(data.get("ended_at")),
            participants=participants,
            segments=segments,
            raw_text=data.get("raw_text", ""),
            extra={k: v for k, v in data.items() if k not in
                   {"id", "title", "started_at", "ended_at", "participants", "segments", "raw_text"}},
        )

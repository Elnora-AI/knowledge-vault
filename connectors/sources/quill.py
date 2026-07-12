"""Quill source — a reference adapter for the Quill meeting recorder.

Reads Quill's local SQLite database (READ-ONLY) and produces framework Records.
This is a worked example of a real-world `Source`; it requires the Quill desktop
app to be installed. To connect a different tool, copy this file's shape and
implement the same four members (`name`, `list_pending`, `is_ready`, `fetch`).

Quill schema (relevant tables):
- Meeting(id, start, end, audio_transcript, title, llmTitle, eventTitle,
          manualTitle, word_count, type, events, deleteDate, hidden)
- ContactMeeting(contact_id, speaker_id, meeting_id, suggested_name)
- Contact(id, name)

Timestamps are milliseconds since the epoch. The "mic" transcript source is the
recording owner.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from ..framework.models import Person, Record, RecordRef, Segment


def default_db_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Quill" / "quill.db"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "Quill" / "quill.db"
    return Path.home() / ".local" / "share" / "Quill" / "quill.db"


class QuillSource:
    name = "quill"

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path) if db_path else default_db_path()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _best_title(row) -> str:
        for key in ("manualTitle", "eventTitle", "llmTitle", "title"):
            try:
                value = row[key]
            except (IndexError, KeyError):
                value = None
            if value:
                return value
        return "Untitled Meeting"

    def list_pending(self, since: date | None, min_age_minutes: int, max_age_days: int) -> list[RecordRef]:
        now_ts = datetime.now(timezone.utc).timestamp()
        min_age_cutoff_ms = int((now_ts - min_age_minutes * 60) * 1000)
        if since:
            max_age_cutoff_ms = int(datetime(since.year, since.month, since.day, tzinfo=timezone.utc).timestamp() * 1000)
        elif max_age_days > 0:
            max_age_cutoff_ms = int((now_ts - max_age_days * 86400) * 1000)
        else:
            max_age_cutoff_ms = 0

        conn = self._connect()
        try:
            rows = conn.execute(
                'SELECT id, title, llmTitle, eventTitle, manualTitle, start, "end", '
                "word_count, type FROM Meeting "
                "WHERE deleteDate IS NULL AND (hidden IS NULL OR hidden = 0) "
                "ORDER BY start DESC"
            ).fetchall()
        finally:
            conn.close()

        refs: list[RecordRef] = []
        for row in rows:
            end_ms, start_ms = row["end"], row["start"]
            word_count = row["word_count"] or 0
            # Not finalized yet — Quill backfills end/word_count after the meeting.
            if not end_ms or not word_count:
                continue
            if end_ms > min_age_cutoff_ms:
                continue
            if max_age_cutoff_ms and start_ms and start_ms < max_age_cutoff_ms:
                continue
            refs.append(
                RecordRef(
                    id=row["id"],
                    title=self._best_title(row),
                    started_at=datetime.fromtimestamp(start_ms / 1000) if start_ms else None,
                    extra={"ready": True, "type": row["type"]},
                )
            )
        return refs

    def is_ready(self, ref: RecordRef) -> bool:
        return bool(ref.extra.get("ready", False))

    def _resolve_speakers(self, conn, meeting_id: str) -> dict[str, str]:
        rows = conn.execute(
            "SELECT cm.speaker_id, cm.suggested_name, c.name AS contact_name "
            "FROM ContactMeeting cm LEFT JOIN Contact c ON cm.contact_id = c.id "
            "WHERE cm.meeting_id = ?",
            (meeting_id,),
        ).fetchall()
        out: dict[str, str] = {}
        for row in rows:
            name = row["contact_name"] or row["suggested_name"] or ""
            if row["speaker_id"] and name:
                out[row["speaker_id"]] = name
        return out

    @staticmethod
    def _parse_attendees(events) -> list[Person]:
        if not events:
            return []
        try:
            event_list = json.loads(events)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(event_list, list):
            return []
        people: list[Person] = []
        for event in event_list:
            if not isinstance(event, dict):
                continue
            for att in event.get("attendeesRaw", []) or []:
                if att.get("resource", False):
                    continue
                if "emailAddress" in att:  # mCal
                    ea = att["emailAddress"]
                    people.append(Person(name=ea.get("name", ""), email=ea.get("address")))
                elif "email" in att:  # gCal
                    people.append(Person(name=att.get("displayName", ""), email=att.get("email")))
        return people

    @staticmethod
    def _parse_blocks(audio_transcript) -> list[dict]:
        if not audio_transcript:
            return []
        try:
            data = json.loads(audio_transcript)
        except (json.JSONDecodeError, TypeError):
            return []
        if not isinstance(data, dict):
            return []
        blocks = data.get("blocks", [])
        if not isinstance(blocks, list):
            return []
        parsed = [
            {
                "speaker_id": b.get("speaker_id", ""),
                "text": b.get("text", ""),
                "source": b.get("source", ""),
                "from_ts": b.get("from", 0),
            }
            for b in blocks
        ]
        parsed.sort(key=lambda b: b["from_ts"])
        return parsed

    def fetch(self, record_id: str) -> Record | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM Meeting WHERE id = ? AND deleteDate IS NULL "
                "AND (hidden IS NULL OR hidden = 0)",
                (record_id,),
            ).fetchone()
            if row is None:
                return None
            meeting = dict(row)
            speakers = self._resolve_speakers(conn, record_id)
        finally:
            conn.close()

        blocks = self._parse_blocks(meeting.get("audio_transcript"))
        segments = [
            Segment(
                speaker=speakers.get(b["speaker_id"], "Speaker") if b["source"] != "mic" else (
                    speakers.get(b["speaker_id"]) or "Owner"
                ),
                text=b["text"],
                is_owner=(b["source"] == "mic"),
            )
            for b in blocks
            if b["text"]
        ]
        start_ms, end_ms = meeting.get("start"), meeting.get("end")
        return Record(
            id=record_id,
            title=self._best_title(row),
            started_at=datetime.fromtimestamp(start_ms / 1000) if start_ms else None,
            ended_at=datetime.fromtimestamp(end_ms / 1000) if end_ms else None,
            participants=self._parse_attendees(meeting.get("events")),
            segments=segments,
            raw_text="",
            extra={"type": meeting.get("type"), "word_count": meeting.get("word_count")},
        )

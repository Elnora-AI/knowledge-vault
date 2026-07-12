"""Core data model for the connector framework.

A connector syncs *records* — dated, attributed units of content (a meeting, a
call, a note) — from some external source into the vault. These dataclasses are
the source-agnostic contract every adapter produces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Person:
    """A participant in a record."""

    name: str
    email: str | None = None
    role: str | None = None


@dataclass
class Segment:
    """One attributed chunk of content (e.g. a spoken turn)."""

    speaker: str
    text: str
    is_owner: bool = False  # True if spoken/authored by the vault owner


@dataclass
class RecordRef:
    """A lightweight pointer to a syncable record (cheap to list)."""

    id: str
    title: str
    started_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Record:
    """A fully-fetched syncable record."""

    id: str
    title: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    participants: list[Person] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    raw_text: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_minutes(self) -> int:
        if self.started_at and self.ended_at:
            return max(0, int((self.ended_at - self.started_at).total_seconds() // 60))
        return 0

    def transcript_text(self) -> str:
        """A plain-text rendering of the segments (fallback when no LLM formats it)."""
        if self.raw_text:
            return self.raw_text
        return "\n\n".join(f"**{s.speaker}:** {s.text}" for s in self.segments)


@dataclass
class FormatResult:
    """The output of formatting a record — metadata plus a clean body."""

    summary: str = ""
    record_type: str = ""
    tags: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    body: str = ""  # formatted transcript / content

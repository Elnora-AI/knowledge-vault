"""Tests for the connector framework, JSON adapter, and Quill adapter."""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

from connectors.framework import ConnectorConfig, SyncEngine, SyncState
from connectors.framework.models import Person, Record, Segment
from connectors.framework import vault_writer
from connectors.sources.json_folder import JsonFolderSource
from connectors.sources.quill import QuillSource


def make_config(tmp_path, **overrides):
    cfg = ConnectorConfig(vault_root=tmp_path / "vault", state_dir=tmp_path / "state")
    cfg.source_name = overrides.get("source_name", "json")
    cfg.owner_slug = overrides.get("owner_slug", "jane-doe")
    cfg.default_route = overrides.get("default_route", "meetings")
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# ---------------------------------------------------------------------------
# Unit: slugify + document build
# ---------------------------------------------------------------------------

def test_slugify_basic():
    assert vault_writer.slugify_title("Acme <> Globex Sync!") == "acme-globex-sync"

def test_slugify_truncates_at_word_boundary():
    slug = vault_writer.slugify_title("word " * 40)
    assert len(slug) <= 60
    assert not slug.endswith("-")

def test_slugify_empty():
    assert vault_writer.slugify_title("!!!") == "untitled"


def test_build_document_has_frontmatter_and_sections(tmp_path):
    cfg = make_config(tmp_path)
    rec = Record(
        id="r1", title="Acme <> Globex",
        started_at=datetime(2026, 3, 10, 15, 0),
        participants=[Person(name="Jane Doe", email="jane@example.com")],
        segments=[Segment(speaker="Jane Doe", text="Hello there.", is_owner=True)],
    )
    from connectors.framework.formatter import format_record
    doc = vault_writer.build_document(rec, format_record(rec, cfg), cfg)
    assert doc.startswith("---")
    assert 'record_id: "r1"' in doc
    assert "platform: \"json\"" in doc
    assert "## Transcript" in doc
    assert "Hello there." in doc
    assert "owner: jane-doe" in doc


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def test_state_roundtrip(tmp_path):
    s = SyncState("json", tmp_path / "state")
    assert not s.is_processed("a")
    s.mark_processed("a")
    s.save()
    s2 = SyncState("json", tmp_path / "state")
    assert s2.is_processed("a")
    assert s2.total_synced == 1


# ---------------------------------------------------------------------------
# JSON adapter end-to-end
# ---------------------------------------------------------------------------

def _write_json_record(folder: Path, rec: dict):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{rec['id']}.json").write_text(json.dumps(rec), encoding="utf-8")


def test_json_source_end_to_end(tmp_path):
    src_dir = tmp_path / "records"
    _write_json_record(src_dir, {
        "id": "rec-001",
        "title": "Acme <> Globex sync",
        "started_at": "2026-03-10T15:00:00",
        "ended_at": "2026-03-10T15:30:00",
        "ready": True,
        "participants": [{"name": "Jane Doe", "email": "jane@example.com"}],
        "segments": [
            {"speaker": "Jane Doe", "text": "Kickoff.", "is_owner": True},
            {"speaker": "Sam Rivera", "text": "Sounds good.", "is_owner": False},
        ],
    })
    cfg = make_config(tmp_path)
    engine = SyncEngine(JsonFolderSource(src_dir), cfg)
    result = engine.sync()

    assert result.count == 1
    written = result.written[0]
    assert written.exists()
    # Routed to meetings/2026/ (default route, year-bucketed)
    assert written.parent == cfg.vault_root / "meetings" / "2026"
    body = written.read_text(encoding="utf-8")
    assert "Kickoff." in body and "Sounds good." in body
    assert 'title: "Acme <> Globex sync"' in body

    # Second sync is idempotent — already processed.
    assert SyncEngine(JsonFolderSource(src_dir), cfg, engine.state).sync().count == 0


def test_json_source_respects_since_and_ready(tmp_path):
    src_dir = tmp_path / "records"
    _write_json_record(src_dir, {"id": "old", "title": "Old", "started_at": "2020-01-01T00:00:00", "ready": True})
    _write_json_record(src_dir, {"id": "notready", "title": "Pending", "started_at": "2026-03-10T00:00:00", "ready": False})
    cfg = make_config(tmp_path)
    engine = SyncEngine(JsonFolderSource(src_dir), cfg)
    result = engine.sync(since=date(2026, 1, 1))
    # 'old' filtered by since; 'notready' filtered by is_ready.
    assert result.count == 0


def test_dry_run_writes_nothing(tmp_path):
    src_dir = tmp_path / "records"
    _write_json_record(src_dir, {"id": "d1", "title": "Dry", "started_at": "2026-03-10T10:00:00", "ready": True,
                                 "segments": [{"speaker": "Jane Doe", "text": "hi"}]})
    cfg = make_config(tmp_path)
    engine = SyncEngine(JsonFolderSource(src_dir), cfg)
    result = engine.sync(dry_run=True)
    assert result.count == 1
    assert not (cfg.vault_root / "meetings").exists()


# ---------------------------------------------------------------------------
# Quill adapter against a synthetic SQLite fixture
# ---------------------------------------------------------------------------

def _build_quill_db(path: Path):
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE Meeting (
            id TEXT PRIMARY KEY, start INTEGER, "end" INTEGER,
            audio_transcript TEXT, title TEXT, llmTitle TEXT, eventTitle TEXT,
            manualTitle TEXT, word_count INTEGER, type TEXT, events TEXT,
            deleteDate INTEGER, hidden INTEGER
        );
        CREATE TABLE Contact (id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE ContactMeeting (contact_id TEXT, speaker_id TEXT, meeting_id TEXT, suggested_name TEXT);
        """
    )
    start_ms = int(datetime(2026, 3, 10, 15, 0).timestamp() * 1000)
    end_ms = int(datetime(2026, 3, 10, 15, 30).timestamp() * 1000)
    transcript = json.dumps({"blocks": [
        {"speaker_id": "s1", "text": "Welcome everyone.", "source": "mic", "from": 1},
        {"speaker_id": "s2", "text": "Glad to be here.", "source": "system", "from": 2},
    ]})
    events = json.dumps([{"attendeesRaw": [
        {"email": "jane@example.com", "displayName": "Jane Doe"},
        {"emailAddress": {"name": "Sam Rivera", "address": "sam@example.com"}},
        {"email": "room@example.com", "displayName": "Room", "resource": True},
    ]}])
    conn.execute(
        'INSERT INTO Meeting (id, start, "end", audio_transcript, title, word_count, type, events, deleteDate, hidden) '
        "VALUES (?,?,?,?,?,?,?,?,NULL,0)",
        ("m1", start_ms, end_ms, transcript, "Acme Globex Call", 42, "meeting", events),
    )
    conn.execute("INSERT INTO Contact (id, name) VALUES ('c2', 'Sam Rivera')")
    conn.execute("INSERT INTO ContactMeeting (contact_id, speaker_id, meeting_id, suggested_name) VALUES ('c2','s2','m1',NULL)")
    conn.commit()
    conn.close()


def test_quill_adapter_parses_fixture(tmp_path):
    db = tmp_path / "quill.db"
    _build_quill_db(db)
    src = QuillSource(db)

    refs = src.list_pending(None, 0, 0)
    assert len(refs) == 1
    assert refs[0].id == "m1"
    assert src.is_ready(refs[0])

    rec = src.fetch("m1")
    assert rec is not None
    assert rec.title == "Acme Globex Call"
    # Resource room filtered; two real attendees remain.
    assert {p.name for p in rec.participants} == {"Jane Doe", "Sam Rivera"}
    # mic segment marked as owner; system speaker resolved via Contact join.
    owner_segs = [s for s in rec.segments if s.is_owner]
    assert owner_segs and owner_segs[0].text == "Welcome everyone."
    assert any(s.speaker == "Sam Rivera" for s in rec.segments)


def test_quill_adapter_missing_db_lists_nothing(tmp_path):
    src = QuillSource(tmp_path / "does-not-exist.db")
    with pytest.raises(sqlite3.OperationalError):
        src.list_pending(None, 0, 0)


def test_quill_end_to_end_into_vault(tmp_path):
    db = tmp_path / "quill.db"
    _build_quill_db(db)
    cfg = make_config(tmp_path, source_name="quill")
    engine = SyncEngine(QuillSource(db), cfg)
    result = engine.sync(since=date(2026, 1, 1))
    assert result.count == 1
    body = result.written[0].read_text(encoding="utf-8")
    assert "Welcome everyone." in body
    assert "platform: \"quill\"" in body

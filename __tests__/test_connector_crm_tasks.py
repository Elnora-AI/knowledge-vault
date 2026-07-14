"""Tests for the CRM, tasks, formatter-parsing, and verifier stages."""

import json

from connectors.framework import ConnectorConfig, SyncEngine
from connectors.framework.config import CrmConfig, CrmRegistry
from connectors.framework import crm, tasks
from connectors.framework.formatter import _parse_metadata
from connectors.framework.models import ActionItem, Person
from connectors.sources.json_folder import JsonFolderSource


def make_config(tmp_path, **overrides) -> ConnectorConfig:
    cfg = ConnectorConfig(vault_root=tmp_path / "vault", state_dir=tmp_path / "state")
    cfg.source_name = "json"
    cfg.owner_name = "Jane Doe"
    cfg.owner_slug = "jane-doe"
    cfg.owner_email_domains = ["test.com"]  # distinct from external contacts on example.*
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def crm_config(tmp_path, **overrides) -> ConnectorConfig:
    cfg = make_config(tmp_path, **overrides)
    cfg.crm = CrmConfig(
        enabled=True,
        registries=[CrmRegistry(
            name="contacts", category="contact",
            contacts_csv="crm/contacts.csv",
            org_csv="crm/companies.csv", org_field="company",
            contact_defaults={"stage": "lead"},
        )],
    )
    crm_dir = cfg.vault_root / "crm"
    crm_dir.mkdir(parents=True, exist_ok=True)
    (crm_dir / "contacts.csv").write_text(
        '"slug","first_name","last_name","email","company","role","stage",'
        '"source","last_contact_date","last_contact_channel","last_meeting_date","notes"\n'
        '"tom-smith","Tom","Smith","tom@example.com","Acme","CTO","lead","manual","","","",""\n',
        encoding="utf-8",
    )
    (crm_dir / "companies.csv").write_text(
        '"slug","name","stage","source","notes"\n'
        '"acme","Acme","lead","manual",""\n',
        encoding="utf-8",
    )
    return cfg


# ---------------------------------------------------------------------------
# CRM: match + stamp
# ---------------------------------------------------------------------------

def test_match_and_stamp(tmp_path):
    cfg = crm_config(tmp_path)
    matches = crm.match_participants(
        [Person(name="Tom Smith", email="Tom@example.com"),
         Person(name="Nobody", email="nobody@example.net")], cfg)
    assert len(matches) == 1
    assert matches[0]["slug"] == "tom-smith"

    updated = crm.stamp_matches(matches, "2026-03-10", "meetings/2026/x.md", cfg)
    assert updated == 1
    content = (cfg.vault_root / "crm/contacts.csv").read_text(encoding="utf-8")
    assert '"2026-03-10"' in content and '"meeting"' in content
    # last_meeting_transcript column doesn't exist -> not invented
    assert "meetings/2026/x.md" not in content


def test_stamp_writes_transcript_column_when_present(tmp_path):
    cfg = crm_config(tmp_path)
    path = cfg.vault_root / "crm/contacts.csv"
    text = path.read_text(encoding="utf-8").splitlines()
    text[0] += ',"last_meeting_transcript"'
    text[1] += ',""'
    path.write_text("\n".join(text) + "\n", encoding="utf-8")
    matches = crm.match_participants([Person(name="Tom", email="tom@example.com")], cfg)
    crm.stamp_matches(matches, "2026-03-10", "meetings/2026/x.md", cfg)
    assert "meetings/2026/x.md" in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# CRM: create + enrich
# ---------------------------------------------------------------------------

def test_create_contact_and_org(tmp_path):
    cfg = crm_config(tmp_path)
    enrichment = [{
        "name": "Ada Lovelace", "email": "ada@example.org", "category": "contact",
        "role": "VP Eng", "organization": "Globex", "notes": "Wants a pilot in Q3.",
    }]
    summary = crm.create_or_enrich(enrichment, [], "2026-03-10",
                                   "meetings/2026/x.md", "Globex intro", cfg)
    assert summary == {"created": 1, "enriched": 0, "created_orgs": 1}

    contacts = (cfg.vault_root / "crm/contacts.csv").read_text(encoding="utf-8")
    assert '"ada-lovelace"' in contacts
    assert '"globex"' in contacts  # org_field filled with the new org slug
    assert "[from call 2026-03-10]: VP Eng at Globex. Wants a pilot in Q3." in contacts
    assert '"lead"' in contacts  # contact_defaults applied
    companies = (cfg.vault_root / "crm/companies.csv").read_text(encoding="utf-8")
    assert '"globex"' in companies and '"Globex"' in companies

    # audit log written to the state dir
    audit = cfg.state_dir / "json-crm-audit.jsonl"
    actions = [json.loads(line)["action"] for line in audit.read_text().splitlines()]
    assert actions == ["created_org", "created_contact"]


def test_enrich_existing_is_idempotent(tmp_path):
    cfg = crm_config(tmp_path)
    matches = crm.match_participants([Person(name="Tom Smith", email="tom@example.com")], cfg)
    enrichment = [{"name": "Tom Smith", "email": "tom@example.com", "category": "contact",
                   "role": "CTO", "organization": "Acme", "notes": "Budget approved."}]
    s1 = crm.create_or_enrich(enrichment, matches, "2026-03-10", "x.md", "Call", cfg)
    assert s1["enriched"] == 1
    s2 = crm.create_or_enrich(enrichment, matches, "2026-03-10", "x.md", "Call", cfg)
    assert s2["enriched"] == 0  # same fragment, same date -> no duplicate append
    contacts = (cfg.vault_root / "crm/contacts.csv").read_text(encoding="utf-8")
    assert contacts.count("Budget approved.") == 1


def test_internal_and_unknown_skipped(tmp_path):
    cfg = crm_config(tmp_path)
    enrichment = [
        {"name": "Jane Doe", "email": "jane@test.com", "category": "contact"},  # internal domain
        {"name": "Mystery", "email": "mystery@example.net", "category": "unknown"},  # unmapped category
        {"name": "No Email", "email": "", "category": "contact"},
    ]
    summary = crm.create_or_enrich(enrichment, [], "2026-03-10", "x.md", "Call", cfg)
    assert summary["created"] == 0


def test_formula_injection_sanitized(tmp_path):
    cfg = crm_config(tmp_path)
    enrichment = [{"name": "=cmd Bad", "email": "bad@example.org", "category": "contact",
                   "organization": "", "notes": "=HYPERLINK evil"}]
    crm.create_or_enrich(enrichment, [], "2026-03-10", "x.md", "Call", cfg)
    contacts = (cfg.vault_root / "crm/contacts.csv").read_text(encoding="utf-8")
    assert '"\'=cmd"' in contacts  # leading = escaped with '


def test_derive_name_from_email():
    assert crm.derive_name_from_email("tom.dexter@example.com") == "Tom Dexter"
    assert crm.derive_name_from_email("info@example.com") == "Info"
    assert crm.derive_name_from_email("not-an-email") == ""


def test_related_links(tmp_path):
    cfg = crm_config(tmp_path)
    matches = crm.match_participants([Person(name="Tom", email="tom@example.com")], cfg)
    links = crm.related_links(matches, "meetings/2026", cfg)
    assert links == ["[Tom Smith](../../crm/contacts.csv) (slug: tom-smith)"]


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def test_resolve_due_dates():
    # 2026-03-10 is a Tuesday
    assert tasks.resolve_due_date("by Friday", "2026-03-10") == "2026-03-13"
    assert tasks.resolve_due_date("tomorrow", "2026-03-10") == "2026-03-11"
    assert tasks.resolve_due_date("next week", "2026-03-10") == "2026-03-16"
    assert tasks.resolve_due_date("end of month", "2026-03-10") == "2026-03-31"
    assert tasks.resolve_due_date("in 3 days", "2026-03-10") == "2026-03-13"
    assert tasks.resolve_due_date("2 weeks", "2026-03-10") == "2026-03-24"
    assert tasks.resolve_due_date("when convenient", "2026-03-10") is None
    assert tasks.resolve_due_date(None, "2026-03-10") is None


def test_write_action_items_and_dedup(tmp_path):
    cfg = make_config(tmp_path, tasks_enabled=True)
    inbox = tmp_path / "vault" / "tasks" / "inbox.md"
    inbox.parent.mkdir(parents=True)
    inbox.write_text("# Inbox\n", encoding="utf-8")
    cfg.task_inbox = inbox

    items = [
        ActionItem(task="Send the proposal to Tom", owner="Jane Doe", due_hint="by Friday"),
        ActionItem(task="Review the NDA draft", owner="Tom Smith"),
    ]
    n = tasks.write_action_items(items, "Acme call", "2026-03-10", "meetings/x.md", cfg)
    assert n == 2
    content = inbox.read_text(encoding="utf-8")
    assert "- [ ] #task Send the proposal to Tom 📅 2026-03-13" in content
    assert "(assigned: Tom Smith)" in content
    assert "source:: meetings/x.md" in content
    # owner's own tasks carry no assigned marker
    assert "(assigned: Jane Doe)" not in content

    # near-duplicate is skipped on a second write
    n2 = tasks.write_action_items(
        [ActionItem(task="Send the proposal to Tom please")], "Acme call 2",
        "2026-03-11", None, cfg)
    assert n2 == 0


def test_tasks_disabled_or_missing_inbox(tmp_path):
    cfg = make_config(tmp_path, tasks_enabled=False)
    assert tasks.write_action_items([ActionItem(task="X")], "T", "2026-03-10", None, cfg) == 0
    cfg.tasks_enabled = True
    cfg.task_inbox = tmp_path / "nope.md"
    assert tasks.write_action_items([ActionItem(task="X")], "T", "2026-03-10", None, cfg) == 0


# ---------------------------------------------------------------------------
# Formatter metadata parsing
# ---------------------------------------------------------------------------

def test_parse_metadata_full(tmp_path):
    cfg = crm_config(tmp_path, routes={"call": "calls"})
    raw = json.dumps({
        "summary": "A call.", "record_type": "call", "tags": ["intro"],
        "entities": ["Globex"],
        "action_items": [{"task": "Follow up", "owner": "Jane Doe", "due_hint": "next week"},
                         "Plain string item"],
        "enrichment": [{"name": "Ada", "email": "ada@example.org", "category": "contact"}],
    })
    fmt = _parse_metadata(f"```json\n{raw}\n```", cfg)
    assert fmt.record_type == "call"
    assert fmt.entities == ["Globex"]
    assert fmt.action_items[0].due_hint == "next week"
    assert fmt.action_items[1].task == "Plain string item"
    assert fmt.enrichment[0]["email"] == "ada@example.org"


def test_parse_metadata_unknown_type_falls_back(tmp_path):
    cfg = make_config(tmp_path)
    fmt = _parse_metadata(json.dumps({"summary": "s", "record_type": "bogus"}), cfg)
    assert fmt.record_type == "meeting-transcript"


# ---------------------------------------------------------------------------
# End-to-end: engine runs CRM + task stages (passthrough formatter, no LLM)
# ---------------------------------------------------------------------------

def test_engine_stamps_crm_on_sync(tmp_path):
    cfg = crm_config(tmp_path, tasks_enabled=False)
    src_dir = tmp_path / "records"
    src_dir.mkdir()
    (src_dir / "r1.json").write_text(json.dumps({
        "id": "r1", "title": "Acme sync", "started_at": "2026-03-10T15:00:00",
        "ready": True,
        "participants": [{"name": "Tom Smith", "email": "tom@example.com"}],
        "segments": [{"speaker": "Tom Smith", "text": "Hello."}],
    }), encoding="utf-8")

    result = SyncEngine(JsonFolderSource(src_dir), cfg).sync()
    assert result.count == 1
    assert result.crm_stamped == 1
    doc = result.written[0].read_text(encoding="utf-8")
    assert "(slug: tom-smith)" in doc  # related link in frontmatter
    contacts = (cfg.vault_root / "crm/contacts.csv").read_text(encoding="utf-8")
    assert '"2026-03-10"' in contacts


def test_engine_content_only_skips_stages(tmp_path):
    cfg = crm_config(tmp_path)
    src_dir = tmp_path / "records"
    src_dir.mkdir()
    (src_dir / "r1.json").write_text(json.dumps({
        "id": "r1", "title": "Acme sync", "started_at": "2026-03-10T15:00:00",
        "ready": True,
        "participants": [{"name": "Tom Smith", "email": "tom@example.com"}],
        "segments": [{"speaker": "Tom Smith", "text": "Hello."}],
    }), encoding="utf-8")

    result = SyncEngine(JsonFolderSource(src_dir), cfg).sync(content_only=True)
    assert result.count == 1
    assert result.crm_stamped == 0
    contacts = (cfg.vault_root / "crm/contacts.csv").read_text(encoding="utf-8")
    assert '"2026-03-10"' not in contacts


# ---------------------------------------------------------------------------
# Verifier: pending vs missing
# ---------------------------------------------------------------------------

def test_verifier_pending_vs_missing(tmp_path):
    from connectors.framework import verifier

    cfg = make_config(tmp_path)
    cfg.vault_root.mkdir(parents=True, exist_ok=True)
    src_dir = tmp_path / "records"
    src_dir.mkdir()
    (src_dir / "r1.json").write_text(json.dumps({
        "id": "r1", "title": "Never synced", "started_at": "2026-03-10T15:00:00",
        "ready": True,
        "segments": [{"speaker": "A", "text": "Some real content here to exceed the empty threshold."}],
    }), encoding="utf-8")
    source = JsonFolderSource(src_dir)

    # Not processed -> pending, not a failure.
    r = verifier.verify(source, cfg, None, processed_ids=set())
    assert r.pending == ["r1"] and not r.failed

    # Claimed processed but no vault file -> missing, a real failure.
    r = verifier.verify(source, cfg, None, processed_ids={"r1"})
    assert r.missing == ["r1"] and r.failed


def test_verifier_matches_custom_id_keys(tmp_path):
    from connectors.framework import verifier

    cfg = make_config(tmp_path, id_keys=["record_id", "meeting_id"])
    folder = cfg.vault_root / "meetings"
    folder.mkdir(parents=True)
    (folder / "2026-03-10-old.md").write_text(
        "---\ntitle: \"Old\"\nmeeting_id: \"r1\"\n---\n\n## Transcript\n\n"
        + ("Some real content here to exceed the empty threshold. " * 2),
        encoding="utf-8",
    )
    src_dir = tmp_path / "records"
    src_dir.mkdir()
    (src_dir / "r1.json").write_text(json.dumps({
        "id": "r1", "title": "Old", "started_at": "2026-03-10T15:00:00", "ready": True,
        "segments": [{"speaker": "A", "text": "Some real content here to exceed the empty threshold."}],
    }), encoding="utf-8")

    r = verifier.verify(JsonFolderSource(src_dir), cfg, None, processed_ids={"r1"})
    assert r.ok == ["r1"] and not r.failed


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def test_config_load_crm_tasks_schedule(tmp_path):
    config_path = tmp_path / "cfg.json"
    config_path.write_text(json.dumps({
        "source_name": "json",
        "vault_root": str(tmp_path / "vault"),
        "crm": {
            "enabled": True,
            "internal_domains": ["Example.COM"],
            "registries": [{"name": "contacts", "contacts_csv": "crm/contacts.csv"}],
        },
        "tasks": {"enabled": True, "inbox": "tasks/inbox.md"},
        "id_keys": ["record_id", "meeting_id"],
        "schedule_sync_hours": 2,
    }), encoding="utf-8")
    cfg = ConnectorConfig.load(config_path)
    assert cfg.crm.enabled and cfg.crm.registries[0].category == "contact"
    assert cfg.crm.internal_domains == ["example.com"]
    assert cfg.tasks_enabled
    assert cfg.task_inbox == (tmp_path / "vault" / "tasks" / "inbox.md")
    assert cfg.id_keys == ["record_id", "meeting_id"]
    assert cfg.schedule_sync_hours == 2

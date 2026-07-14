"""Optional CSV-CRM stage — link synced records to a lightweight CRM.

Works against any CSV-based CRM that lives inside the vault (for example one
scaffolded by a companion tool, or hand-made). Fully column-driven: the
framework only ever writes columns that already exist in a CSV's header, so it
adapts to whatever schema the user keeps. Configure one or more *registries*
(see ``CrmRegistry``) — e.g. a general contacts file and a separate partners
file — each mapped to an LLM enrichment ``category``.

Per synced record, three things happen:

1. **Match & stamp** — participants are matched by email; matched rows get
   ``last_contact_date`` / ``last_contact_channel`` / ``last_meeting_date``
   stamped, and ``last_meeting_transcript`` (when that column exists) set to
   the vault-relative transcript path.
2. **Auto-create** — unmatched external participants get a new row (name,
   email, role, organization + your configured defaults). When a registry has
   an ``org_csv``, the organization row is ensured there first.
3. **Enrich** — a timestamped fragment of what the participant shared is
   appended to the ``notes`` column (idempotent — the same fragment is never
   appended twice).

Every mutation is appended to a JSONL audit log in the state directory.
Auditing is best-effort and never fails a sync.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import ConnectorConfig, CrmRegistry
from .models import Person
from .state import default_state_dir


# ---------------------------------------------------------------------------
# Helpers — slugs, sanitization, atomic CSV IO
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Lowercase + collapse non-alphanumeric to hyphens."""
    s = (text or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _sanitize_csv_value(value: str) -> str:
    """Prevent CSV formula injection: escape =, @, tab, CR prefixes."""
    if value and value[0] in ("=", "@", "\t", "\r"):
        return f"'{value}"
    return value


def _split_name(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def derive_name_from_email(email: str) -> str:
    """'jane.doe@example.com' -> 'Jane Doe'. Empty string when underivable."""
    if "@" not in (email or ""):
        return ""
    local = email.split("@")[0]
    parts = [p for p in re.split(r"[._-]", local) if len(p) > 1 and not p.isdigit()]
    return " ".join(p.capitalize() for p in parts)


def _read_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not csv_path.exists():
        return [], []
    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return fieldnames, rows


def _write_csv_atomically(csv_path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    sanitized = [
        {k: _sanitize_csv_value(str(v if v is not None else "")) for k, v in row.items()}
        for row in rows
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n",
                            quoting=csv.QUOTE_ALL, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(sanitized)
    tmp_path = csv_path.with_suffix(".tmp")
    tmp_path.write_text(output.getvalue(), encoding="utf-8")
    tmp_path.replace(csv_path)


def _unique_slug(base: str, existing: set[str], suffix_hint: str = "") -> str:
    if base and base not in existing:
        return base
    if suffix_hint:
        candidate = f"{base}-{suffix_hint}" if base else suffix_hint
        if candidate and candidate not in existing:
            return candidate
    n = 2
    while True:
        candidate = f"{base}-{n}" if base else str(n)
        if candidate not in existing:
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _audit_log(cfg: ConnectorConfig, action: str, payload: dict) -> None:
    try:
        base = cfg.state_dir or default_state_dir()
        base.mkdir(parents=True, exist_ok=True)
        log_path = base / f"{cfg.source_name}-crm-audit.jsonl"
        record = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "action": action,
            **payload,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — auditing is best-effort
        pass


# ---------------------------------------------------------------------------
# Internal-participant filter
# ---------------------------------------------------------------------------

def _internal_domains(cfg: ConnectorConfig) -> set[str]:
    domains = set(cfg.crm.internal_domains) | {d.lower() for d in cfg.owner_email_domains}
    return {d for d in domains if d}


def is_internal(cfg: ConnectorConfig, name: str | None, email: str | None) -> bool:
    if email and "@" in email:
        if email.split("@", 1)[1].lower() in _internal_domains(cfg):
            return True
    names = set(cfg.crm.internal_names)
    if cfg.owner_name:
        names.add(cfg.owner_name.lower())
    if name and name.lower().strip() in names:
        return True
    return False


# ---------------------------------------------------------------------------
# Match & stamp
# ---------------------------------------------------------------------------

def match_participants(participants: list[Person], cfg: ConnectorConfig) -> list[dict]:
    """Match participants to registry rows by email (case-insensitive).

    Registries are checked in config order; the first hit wins, so put the
    highest-priority CSV first. Returns dicts with ``registry``, ``slug``,
    ``first_name``, ``last_name``, ``email``.
    """
    if not cfg.crm.enabled:
        return []
    indexes: list[tuple[CrmRegistry, dict[str, dict[str, str]]]] = []
    for reg in cfg.crm.registries:
        _, rows = _read_rows(cfg.vault_root / reg.contacts_csv)
        by_email = {
            row["email"].strip().lower(): row
            for row in rows if row.get("email", "").strip()
        }
        indexes.append((reg, by_email))

    matches: list[dict] = []
    for person in participants:
        email = (person.email or "").strip().lower()
        if not email:
            continue
        for reg, by_email in indexes:
            row = by_email.get(email)
            if row is not None:
                matches.append({
                    "registry": reg.name,
                    "slug": row.get("slug", ""),
                    "first_name": row.get("first_name", ""),
                    "last_name": row.get("last_name", ""),
                    "email": email,
                })
                break
    return matches


def stamp_matches(matches: list[dict], record_date: str, transcript_rel: str,
                  cfg: ConnectorConfig) -> int:
    """Stamp last-contact columns on matched rows. Column-driven: only columns
    present in the CSV header are written. Returns rows updated."""
    total = 0
    for reg in cfg.crm.registries:
        slugs = {m["slug"] for m in matches
                 if m["registry"] == reg.name and m.get("slug", "").strip()}
        if not slugs:
            continue
        csv_path = cfg.vault_root / reg.contacts_csv
        fieldnames, rows = _read_rows(csv_path)
        if not fieldnames:
            continue
        stamp = {
            "last_contact_date": record_date,
            "last_contact_channel": "meeting",
            "last_meeting_date": record_date,
            "last_meeting_transcript": transcript_rel,
        }
        writable = {k: v for k, v in stamp.items() if k in fieldnames}
        updated = 0
        for row in rows:
            if row.get("slug", "").strip() in slugs:
                row.update(writable)
                updated += 1
        if updated:
            _write_csv_atomically(csv_path, fieldnames, rows)
            total += updated
    return total


# ---------------------------------------------------------------------------
# Notes enrichment
# ---------------------------------------------------------------------------

def _append_to_notes(existing: str, fragment: str, record_date: str) -> str:
    fragment = (fragment or "").strip()
    if not fragment:
        return existing or ""
    stamped = f"[from call {record_date}]: {fragment}"
    existing = (existing or "").strip()
    if stamped in existing:
        return existing
    return f"{existing}\n{stamped}" if existing else stamped


def _build_fragment(entry: dict) -> str:
    bits: list[str] = []
    role = (entry.get("role") or "").strip()
    org = (entry.get("organization") or "").strip()
    if role and org:
        bits.append(f"{role} at {org}")
    elif role or org:
        bits.append(role or org)
    notes = (entry.get("notes") or "").strip()
    if notes:
        bits.append(notes)
    return ". ".join(bits)


def _enrich_row(csv_path: Path, slug: str, fragment: str, record_date: str) -> bool:
    if not slug or not fragment or not csv_path.exists():
        return False
    fieldnames, rows = _read_rows(csv_path)
    if "notes" not in fieldnames:
        return False
    for row in rows:
        if row.get("slug", "").strip() == slug:
            new_notes = _append_to_notes(row.get("notes", ""), fragment, record_date)
            if new_notes == row.get("notes", ""):
                return False
            row["notes"] = new_notes
            _write_csv_atomically(csv_path, fieldnames, rows)
            return True
    return False


# ---------------------------------------------------------------------------
# Org + contact creation
# ---------------------------------------------------------------------------

def _ensure_org(reg: CrmRegistry, name: str, source_record: str,
                cfg: ConnectorConfig) -> str:
    """Return an org slug, creating the row in the registry's org CSV if needed."""
    name = (name or "").strip()
    if not name or not reg.org_csv:
        return ""
    csv_path = cfg.vault_root / reg.org_csv
    fieldnames, rows = _read_rows(csv_path)
    if not fieldnames:
        return ""  # org CSV must exist with a header; we never invent schemas
    name_lc = name.lower()
    for row in rows:
        if row.get("name", "").strip().lower() == name_lc:
            return row.get("slug", "").strip()
    slug = slugify(name)
    if not slug:
        return ""
    if slug in {r.get("slug", "").strip() for r in rows}:
        return slug  # slug collision: attach to the existing row
    new_row = {col: "" for col in fieldnames}
    defaults = {k: v for k, v in reg.org_defaults.items() if k in fieldnames}
    new_row.update(defaults)
    new_row.update({k: v for k, v in {
        "slug": slug,
        "name": name,
        "source": f"{cfg.source_name}-sync",
        "notes": f"Auto-created from record: {source_record}",
    }.items() if k in fieldnames})
    rows.append(new_row)
    _write_csv_atomically(csv_path, fieldnames, rows)
    _audit_log(cfg, "created_org", {"registry": reg.name, "slug": slug,
                                    "name": name, "from": source_record})
    return slug


def _create_contact(reg: CrmRegistry, entry: dict, org_slug: str, org_name: str,
                    record_date: str, transcript_rel: str, source_record: str,
                    cfg: ConnectorConfig) -> str | None:
    name = (entry.get("name") or "").strip()
    email = (entry.get("email") or "").strip().lower()
    if not email:
        return None
    if not name and cfg.derive_names_from_email:
        name = derive_name_from_email(email)
    if not name:
        return None

    csv_path = cfg.vault_root / reg.contacts_csv
    fieldnames, rows = _read_rows(csv_path)
    if not fieldnames:
        return None  # contacts CSV must exist with a header

    first, last = _split_name(name)
    base_slug = slugify(f"{first}-{last}") or slugify(name)
    slug = _unique_slug(base_slug, {r.get("slug", "").strip() for r in rows},
                        suffix_hint=org_slug)

    fragment = _build_fragment(entry)
    new_row = {col: "" for col in fieldnames}
    defaults = {k: v for k, v in reg.contact_defaults.items() if k in fieldnames}
    new_row.update(defaults)
    values = {
        "slug": slug,
        "first_name": first,
        "last_name": last,
        "email": email,
        "role": (entry.get("role") or "").strip(),
        "source": f"{cfg.source_name}-sync",
        "first_contact_date": record_date,
        "last_contact_date": record_date,
        "last_contact_channel": "meeting",
        "last_meeting_date": record_date,
        "last_meeting_transcript": transcript_rel,
        "notes": _append_to_notes("", fragment, record_date) if fragment else "",
    }
    if reg.org_field:
        if reg.org_field_value == "name":
            values[reg.org_field] = org_name or org_slug
        else:
            values[reg.org_field] = org_slug or org_name
    new_row.update({k: v for k, v in values.items() if k in fieldnames})
    rows.append(new_row)
    _write_csv_atomically(csv_path, fieldnames, rows)
    _audit_log(cfg, "created_contact", {
        "registry": reg.name, "slug": slug, "name": name, "email": email,
        "org": org_slug or org_name, "from": source_record,
    })
    return slug


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def create_or_enrich(enrichment: list[dict], matches: list[dict], record_date: str,
                     transcript_rel: str, record_title: str,
                     cfg: ConnectorConfig) -> dict:
    """Process LLM-extracted enrichment for one record.

    Participants already in a registry get their notes enriched; unknown
    external participants get a new row in the registry matching their
    category (organization ensured first when the registry has an org CSV).
    """
    summary = {"created": 0, "enriched": 0, "created_orgs": 0}
    if not cfg.crm.enabled or not enrichment:
        return summary

    registry_by_category = {reg.category: reg for reg in cfg.crm.registries}
    matches_by_email = {m["email"]: m for m in matches if m.get("email")}
    registries_by_name = {reg.name: reg for reg in cfg.crm.registries}
    source_record = f"{record_date} | {record_title}"

    for entry in enrichment:
        email = (entry.get("email") or "").strip().lower()
        category = (entry.get("category") or "unknown").strip().lower()
        if not email:
            continue  # can't dedupe without an email
        if is_internal(cfg, entry.get("name"), email):
            continue

        # Existing row → enrich notes (registry from the match, not the category)
        match = matches_by_email.get(email)
        if match is not None:
            reg = registries_by_name.get(match["registry"])
            fragment = _build_fragment(entry)
            if reg and match.get("slug") and fragment:
                if _enrich_row(cfg.vault_root / reg.contacts_csv, match["slug"],
                               fragment, record_date):
                    summary["enriched"] += 1
                    _audit_log(cfg, "enriched_contact", {
                        "registry": reg.name, "slug": match["slug"],
                        "email": email, "fragment": fragment,
                        "from": source_record,
                    })
            continue

        # New row → the registry mapped to this category (unknown/internal skip)
        reg = registry_by_category.get(category)
        if reg is None:
            continue
        org_name = (entry.get("organization") or "").strip()
        org_slug = ""
        if org_name and reg.org_csv:
            before = len(_read_rows(cfg.vault_root / reg.org_csv)[1])
            org_slug = _ensure_org(reg, org_name, source_record, cfg)
            if len(_read_rows(cfg.vault_root / reg.org_csv)[1]) > before:
                summary["created_orgs"] += 1
        if _create_contact(reg, entry, org_slug, org_name, record_date,
                           transcript_rel, source_record, cfg):
            summary["created"] += 1

    return summary


def related_links(matches: list[dict], dest_folder: str, cfg: ConnectorConfig) -> list[str]:
    """Relative markdown links from the record's vault folder to each matched
    contact's CSV, e.g. ``[Jane Doe](../crm/contacts.csv) (slug: jane-doe)``."""
    import os as _os

    registries_by_name = {reg.name: reg for reg in cfg.crm.registries}
    links: list[str] = []
    for m in matches:
        slug = m.get("slug", "").strip()
        reg = registries_by_name.get(m.get("registry", ""))
        if not slug or reg is None:
            continue
        display = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or slug
        rel = Path(_os.path.relpath(reg.contacts_csv, dest_folder)).as_posix()
        links.append(f"[{display}]({rel}) (slug: {slug})")
    return links

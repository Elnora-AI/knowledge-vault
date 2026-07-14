"""Optional task stage — write extracted action items into the task inbox.

Reuses the plugin's own five-file task system: the inbox path comes from
``task_inbox`` in ``.claude/knowledge-base.local.md`` (or an explicit override
in the connector config). Each action item becomes an Obsidian-style task line
with the source record linked, a resolved due date when the record contained a
concrete hint ("by Friday", "next week", …), and a fuzzy-dedup guard so
re-synced records don't duplicate tasks.
"""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta
from pathlib import Path

from .config import ConnectorConfig
from .models import ActionItem

_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_UNKNOWN_OWNERS = {"unknown", "unknown speaker", "unidentified", "speaker", ""}


def resolve_due_date(due_hint: str | None, record_date: str) -> str | None:
    """Resolve a natural-language due hint to YYYY-MM-DD relative to record_date.

    Returns None when the hint is too vague or conditional to resolve.
    """
    if not due_hint:
        return None
    hint = due_hint.lower().strip()
    ref = datetime.strptime(record_date, "%Y-%m-%d")

    if hint in ("today", "asap") or "immediately" in hint:
        return record_date
    if hint == "tomorrow":
        return (ref + timedelta(days=1)).strftime("%Y-%m-%d")
    # "end of month" BEFORE weekday matching ("mon" is a substring of "month")
    if "end of month" in hint:
        last_day = calendar.monthrange(ref.year, ref.month)[1]
        return ref.replace(day=last_day).strftime("%Y-%m-%d")
    if "next week" in hint:
        return (ref + timedelta(days=7 - ref.weekday())).strftime("%Y-%m-%d")
    if "end of week" in hint or "this week" in hint:
        days = 4 - ref.weekday()
        if days <= 0:
            days += 7
        return (ref + timedelta(days=days)).strftime("%Y-%m-%d")
    if "weekend" in hint:
        days = 5 - ref.weekday()
        if days <= 0:
            days += 7
        return (ref + timedelta(days=days)).strftime("%Y-%m-%d")
    for day_name, day_num in _WEEKDAYS.items():
        if re.search(rf"\b{day_name}\b", hint):
            days = day_num - ref.weekday()
            if days <= 0:
                days += 7
            return (ref + timedelta(days=days)).strftime("%Y-%m-%d")
    for month_name, month_num in _MONTHS.items():
        if re.search(rf"\b{month_name}\b", hint):
            year = ref.year + (1 if month_num <= ref.month else 0)
            return datetime(year, month_num, 1).strftime("%Y-%m-%d")
    m = re.search(r"(?:in|within)\s+(\d+)\s+days?", hint)
    if m:
        return (ref + timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r"(\d+)\s+weeks?", hint)
    if m:
        return (ref + timedelta(weeks=int(m.group(1)))).strftime("%Y-%m-%d")
    return None


def _existing_tasks(inbox_path: Path) -> list[str]:
    if not inbox_path.exists():
        return []
    tasks = []
    for line in inbox_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \[.\] #task (.+)", line)
        if m:
            tasks.append(m.group(1).lower().strip())
    return tasks


def _is_duplicate(task_desc: str, existing: list[str]) -> bool:
    """Fuzzy duplicate check — 60%+ word overlap counts as a duplicate."""
    words = set(task_desc.lower().split())
    if not words:
        return False
    for other in existing:
        other_words = set(other.split())
        if not other_words:
            continue
        overlap = len(words & other_words)
        if overlap / max(len(words), len(other_words)) >= 0.6:
            return True
    return False


def _owner_contact_slug(owner: str, crm_matches: list[dict]) -> str:
    """When a task owner's name matches a CRM contact, return that slug so a
    task-completion flow can write back to the CRM."""
    owner_norm = (owner or "").strip().lower()
    if not owner_norm:
        return ""
    for m in crm_matches:
        full = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip().lower()
        if full and full == owner_norm:
            return m.get("slug", "")
    return ""


def write_action_items(action_items: list[ActionItem], record_title: str,
                       record_date: str, transcript_rel: str | None,
                       cfg: ConnectorConfig,
                       crm_matches: list[dict] | None = None) -> int:
    """Append action items to the task inbox. Returns tasks written."""
    if not cfg.tasks_enabled or not action_items:
        return 0
    inbox_path = cfg.task_inbox
    if inbox_path is None or not inbox_path.exists():
        return 0

    existing = _existing_tasks(inbox_path)
    today = datetime.now().strftime("%Y-%m-%d")
    owner_lc = (cfg.owner_name or "").lower()

    lines: list[str] = [f"\n## From: {record_title} ({record_date})\n"]
    for item in action_items:
        task = (item.task or "").strip()
        if not task or _is_duplicate(task, existing):
            continue
        owner = (item.owner or "").strip()
        if owner.lower() in _UNKNOWN_OWNERS:
            owner = ""
        line = f"- [ ] #task {task}"
        resolved = resolve_due_date(item.due_hint, record_date)
        if resolved:
            line += f" 📅 {resolved}"
        if owner and owner.lower() != owner_lc:
            line += f" (assigned: {owner})"
        if transcript_rel:
            line += f"\n    - source:: {transcript_rel}"
        line += f"\n    - extracted:: {today}"
        slug = _owner_contact_slug(owner, crm_matches or [])
        if slug:
            line += f"\n    - contact-slug:: {slug}"
        lines.append(line)

    if len(lines) <= 1:  # only the header
        return 0
    with open(inbox_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(lines) - 1

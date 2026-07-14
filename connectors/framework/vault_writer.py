"""Vault writer — turn a formatted record into a markdown file in the vault.

Source-agnostic: routing, owner, and platform all come from ConnectorConfig.
Writes are atomic (temp file + replace) so a crash can't leave a half-file.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from .config import ConnectorConfig
from .models import FormatResult, Record


def slugify_title(title: str, max_len: int = 60) -> str:
    """Lowercase, hyphenate, collapse, trim, and truncate at a word boundary."""
    slug = re.sub(r"[^a-z0-9]", "-", (title or "").lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if len(slug) > max_len:
        truncated = slug[:max_len]
        last_hyphen = truncated.rfind("-")
        if last_hyphen > 0:
            truncated = truncated[:last_hyphen]
        slug = truncated.rstrip("-")
    return slug or "untitled"


def build_filename(date_str: str, title: str) -> str:
    return f"{date_str}-{slugify_title(title)}.md"


def route(record_type: str, cfg: ConnectorConfig) -> str:
    return cfg.routes.get(record_type, cfg.default_route)


def _yaml_quote(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_document(record: Record, fmt: FormatResult, cfg: ConnectorConfig,
                   related_links: list[str] | None = None) -> str:
    """Assemble the full markdown document (frontmatter + body)."""
    date_str = record.started_at.strftime("%Y-%m-%d") if record.started_at else ""
    time_str = record.started_at.strftime("%H:%M") if record.started_at else ""
    participants = [p.name for p in record.participants if p.name]

    fm: list[str] = ["---"]
    fm.append(f"type: {_yaml_quote(fmt.record_type or 'meeting-transcript')}")
    fm.append(f"title: {_yaml_quote(record.title)}")
    fm.append("status: transcribed")
    if date_str:
        fm.append(f"created: {date_str}")
        fm.append(f"updated: {date_str}")
        fm.append(f"date: {date_str}")
    if time_str:
        fm.append(f"time: {_yaml_quote(time_str)}")
    if cfg.owner_slug:
        fm.append(f"owner: {cfg.owner_slug}")
    if fmt.tags:
        fm.append("tags:")
        fm.extend(f"  - {_yaml_quote(t)}" for t in fmt.tags)
    if fmt.summary:
        fm.append(f"description: {_yaml_quote(fmt.summary)}")
    fm.append(f"duration_minutes: {record.duration_minutes}")
    fm.append(f"record_id: {_yaml_quote(record.id)}")
    fm.append(f"platform: {_yaml_quote(cfg.source_name)}")
    if participants:
        fm.append("participants:")
        fm.extend(f"  - {_yaml_quote(p)}" for p in participants)
    if fmt.entities:
        fm.append("entities:")
        fm.extend(f"  - {_yaml_quote(e)}" for e in fmt.entities)
    if fmt.action_items:
        fm.append("action_items:")
        fm.extend(f"  - {_yaml_quote(a.task)}" for a in fmt.action_items)
    if related_links:
        fm.append("related:")
        fm.extend(f"  - {_yaml_quote(link)}" for link in related_links)
    fm.append("---")

    body_parts = [f"# {record.title}", ""]
    meta_line = " · ".join(
        x for x in [date_str and f"**Date:** {date_str} {time_str}".strip(),
                    participants and f"**Participants:** {', '.join(participants)}"] if x
    )
    if meta_line:
        body_parts.extend([meta_line, ""])
    if fmt.summary:
        body_parts.extend(["## Summary", "", fmt.summary, ""])
    if fmt.action_items:
        body_parts.append("## Action Items")
        body_parts.append("")
        for a in fmt.action_items:
            line = f"- [ ] {a.task}"
            if a.owner and a.owner.lower() != (cfg.owner_name or "").lower():
                line += f" ({a.owner})"
            if a.due_hint:
                line += f" — {a.due_hint}"
            body_parts.append(line)
        body_parts.append("")
    body_parts.extend(["## Transcript", "", fmt.body or record.transcript_text(), ""])

    return "\n".join(fm) + "\n\n" + "\n".join(body_parts)


def write_record(record: Record, fmt: FormatResult, cfg: ConnectorConfig,
                 related_links: list[str] | None = None) -> Path:
    """Write the record to the routed vault folder. Returns the file path."""
    date_str = record.started_at.strftime("%Y-%m-%d") if record.started_at else "undated"
    subfolder = route(fmt.record_type, cfg)

    target_dir = cfg.vault_root / subfolder
    # The default route is year-bucketed; explicit routes stay flat.
    if subfolder == cfg.default_route and cfg.year_bucket_default:
        year = date_str[:4] if len(date_str) >= 4 else "undated"
        target_dir = target_dir / year
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / build_filename(date_str, record.title)
    document = build_document(record, fmt, cfg, related_links=related_links)

    fd, tmp = tempfile.mkstemp(dir=str(target_dir), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(document)
        os.replace(tmp, file_path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return file_path

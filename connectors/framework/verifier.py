"""Verifier — audit the vault against the source (no LLM).

For each source record in the window, find the vault file that carries its
record id in frontmatter (any key in ``id_keys``) and categorize:

- ``missing``     — the syncer processed it but the vault file is gone.
- ``truncated``   — vault body is far shorter than the source content.
- ``malformed``   — vault file lacks the ``## Transcript`` section.
- ``empty_source``— the source never captured real content. Not a failure.
- ``pending``     — the source has the record but the syncer hasn't processed
                    it yet (e.g. still in the cooldown window). Not a failure.
- ``ok``          — healthy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .config import ConnectorConfig
from .source import Source

TRUNCATION_THRESHOLD = 0.30
EMPTY_SOURCE_CHAR_THRESHOLD = 50


@dataclass
class VerifyResult:
    ok: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    truncated: list[str] = field(default_factory=list)
    malformed: list[str] = field(default_factory=list)
    empty_source: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.missing or self.truncated or self.malformed)


def _index_vault_by_record_id(vault_root: Path, id_keys: list[str]) -> dict[str, Path]:
    pattern = re.compile(
        r'^(?:' + "|".join(re.escape(k) for k in id_keys) + r'):\s*"?([^"\n]+)"?\s*$',
        re.MULTILINE,
    )
    index: dict[str, Path] = {}
    for path in vault_root.rglob("*.md"):
        try:
            head = path.read_text(encoding="utf-8")[:2000]
        except OSError:
            continue
        m = pattern.search(head)
        if m:
            index[m.group(1).strip()] = path
    return index


def verify(source: Source, cfg: ConnectorConfig, since: date | None = None,
           processed_ids: set[str] | None = None) -> VerifyResult:
    """Audit every source record in the window against the vault.

    ``processed_ids`` (usually ``SyncState.processed_ids``) separates real
    failures from records simply not synced yet: an absent vault file is
    ``missing`` only when the syncer claims to have processed the record,
    otherwise it is ``pending``.
    """
    result = VerifyResult()
    index = _index_vault_by_record_id(cfg.vault_root, cfg.id_keys)
    refs = source.list_pending(since, 0, cfg.max_age_days)
    processed_ids = processed_ids or set()

    for ref in refs:
        path = index.get(ref.id)
        if path is None:
            record = source.fetch(ref.id)
            if record is not None and len(record.transcript_text()) < EMPTY_SOURCE_CHAR_THRESHOLD:
                result.empty_source.append(ref.id)
            elif ref.id in processed_ids:
                result.missing.append(ref.id)
            else:
                result.pending.append(ref.id)
            continue
        content = path.read_text(encoding="utf-8")
        if "## Transcript" not in content:
            result.malformed.append(ref.id)
            continue
        record = source.fetch(ref.id)
        if record is not None:
            src_len = len(record.transcript_text())
            body_len = len(content.split("## Transcript", 1)[-1])
            if src_len > 200 and body_len < TRUNCATION_THRESHOLD * src_len:
                result.truncated.append(ref.id)
                continue
        result.ok.append(ref.id)
    return result

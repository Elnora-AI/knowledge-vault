"""Verifier — audit the vault against the source (no LLM).

For each source record in the window, find the vault file that carries its
record_id in frontmatter and flag: missing, truncated (body far shorter than the
source), or missing the Transcript section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .config import ConnectorConfig
from .source import Source


@dataclass
class VerifyResult:
    ok: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    truncated: list[str] = field(default_factory=list)
    malformed: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.missing or self.truncated or self.malformed)


def _index_vault_by_record_id(vault_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in vault_root.rglob("*.md"):
        try:
            head = path.read_text(encoding="utf-8")[:2000]
        except OSError:
            continue
        m = re.search(r'^record_id:\s*"?([^"\n]+)"?\s*$', head, re.MULTILINE)
        if m:
            index[m.group(1).strip()] = path
    return index


def verify(source: Source, cfg: ConnectorConfig, since: date | None = None) -> VerifyResult:
    result = VerifyResult()
    index = _index_vault_by_record_id(cfg.vault_root)
    refs = source.list_pending(since, 0, cfg.max_age_days)

    for ref in refs:
        path = index.get(ref.id)
        if path is None:
            result.missing.append(ref.id)
            continue
        content = path.read_text(encoding="utf-8")
        if "## Transcript" not in content:
            result.malformed.append(ref.id)
            continue
        record = source.fetch(ref.id)
        if record is not None:
            src_len = len(record.transcript_text())
            body_len = len(content.split("## Transcript", 1)[-1])
            if src_len > 200 and body_len < 0.3 * src_len:
                result.truncated.append(ref.id)
                continue
        result.ok.append(ref.id)
    return result

"""Connector configuration.

The vault root is resolved from the SAME per-user file the plugin uses
(.claude/knowledge-base.local.md), so a connector always writes to the vault the
plugin already knows about. Connector-specific settings (routes, owner, source,
LLM) live in a small JSON config so there is no YAML dependency.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


_CONFIG_REL = Path(".claude") / "knowledge-base.local.md"


def _find_config(start: Path | None = None) -> Path | None:
    """Locate `.claude/knowledge-base.local.md`: $CLAUDE_PROJECT_DIR, CWD, then up."""
    candidates = []
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir:
        candidates.append(Path(project_dir) / _CONFIG_REL)
    cwd = start or Path.cwd()
    candidates.append(cwd / _CONFIG_REL)
    for parent in cwd.parents:
        candidates.append(parent / _CONFIG_REL)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def resolve_vault_root(project_root: Path | None = None) -> Path | None:
    """Read vault_path (+ optional vault_dir) from the plugin config."""
    cfg = _find_config(project_root)
    if cfg is None:
        return None
    content = cfg.read_text(encoding="utf-8")

    def _val(key: str) -> str | None:
        m = re.search(rf"^{re.escape(key)}:\s*(.*)$", content, re.MULTILINE)
        if not m:
            return None
        v = m.group(1).strip().strip("\"'")
        return v or None

    vault_path = _val("vault_path")
    if not vault_path:
        return None
    root_path = Path(vault_path)
    vault_dir = _val("vault_dir")
    if vault_dir:
        root_path = root_path / vault_dir
    return root_path.resolve()


@dataclass
class ConnectorConfig:
    """Everything a SyncEngine needs. Load with `ConnectorConfig.load(path)`."""

    vault_root: Path
    source_name: str = "records"
    owner_name: str = ""
    owner_slug: str = ""
    owner_email_domains: list[str] = field(default_factory=list)
    routes: dict[str, str] = field(default_factory=dict)
    default_route: str = "meetings"
    year_bucket_default: bool = True
    min_age_minutes: int = 0
    max_age_days: int = 30
    llm_enabled: bool = False
    llm_model: str = "claude-sonnet-5"
    state_dir: Path | None = None

    @classmethod
    def load(cls, config_path: str | Path, vault_root: Path | None = None) -> "ConnectorConfig":
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        resolved_root = vault_root or resolve_vault_root()
        if data.get("vault_root"):
            resolved_root = Path(data["vault_root"]).resolve()
        if resolved_root is None:
            raise ValueError(
                "Could not resolve the vault root. Configure vault_path in "
                ".claude/knowledge-base.local.md or set vault_root in the connector config."
            )
        state_dir = data.get("state_dir")
        return cls(
            vault_root=resolved_root,
            source_name=data.get("source_name", "records"),
            owner_name=data.get("owner_name", ""),
            owner_slug=data.get("owner_slug", ""),
            owner_email_domains=list(data.get("owner_email_domains", [])),
            routes=dict(data.get("routes", {})),
            default_route=data.get("default_route", "meetings"),
            year_bucket_default=bool(data.get("year_bucket_default", True)),
            min_age_minutes=int(data.get("min_age_minutes", 0)),
            max_age_days=int(data.get("max_age_days", 30)),
            llm_enabled=bool(data.get("llm_enabled", False)),
            llm_model=data.get("llm_model", "claude-sonnet-5"),
            state_dir=Path(state_dir).resolve() if state_dir else None,
        )

"""Connector configuration.

The vault root is resolved from the SAME per-user file the plugin uses
(.claude/knowledge-base.local.md), so a connector always writes to the vault the
plugin already knows about. Connector-specific settings (routes, owner, source,
LLM, CRM, tasks, schedule) live in a small JSON config so there is no YAML
dependency.
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


def _kb_value(content: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:\s*(.*)$", content, re.MULTILINE)
    if not m:
        return None
    v = m.group(1).strip().strip("\"'")
    return v or None


def resolve_vault_root(project_root: Path | None = None) -> Path | None:
    """Read vault_path (+ optional vault_dir) from the plugin config."""
    cfg = _find_config(project_root)
    if cfg is None:
        return None
    content = cfg.read_text(encoding="utf-8")
    vault_path = _kb_value(content, "vault_path")
    if not vault_path:
        return None
    root_path = Path(vault_path)
    vault_dir = _kb_value(content, "vault_dir")
    if vault_dir:
        root_path = root_path / vault_dir
    return root_path.resolve()


def resolve_task_inbox(project_root: Path | None = None) -> Path | None:
    """Read the task-inbox path from the plugin config (task_inbox, vault-relative)."""
    cfg = _find_config(project_root)
    if cfg is None:
        return None
    content = cfg.read_text(encoding="utf-8")
    inbox_rel = _kb_value(content, "task_inbox")
    root = resolve_vault_root(project_root)
    if not inbox_rel or root is None:
        return None
    return root / inbox_rel


def load_env_file(path: str | Path) -> None:
    """Load KEY=VALUE lines from an env file into os.environ (no overwrite).

    Scheduled jobs don't inherit an interactive shell, so a connector config can
    point at an env file holding e.g. ANTHROPIC_API_KEY. Secrets stay in that
    file — they are never copied into scheduler job definitions.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        else:
            comment_idx = value.find(" #")
            if comment_idx >= 0:
                value = value[:comment_idx].rstrip()
        os.environ.setdefault(key.strip(), value)


@dataclass
class CrmRegistry:
    """One CRM CSV a connector can match, stamp, enrich, and create rows in.

    Behavior is column-driven: only columns that exist in the CSV header are
    ever written. `contacts_csv` / `org_csv` are vault-root-relative paths.
    """

    name: str
    contacts_csv: str
    category: str = "contact"  # which LLM enrichment category lands here
    org_csv: str = ""  # optional organizations CSV (slug,name,…)
    org_field: str = ""  # contact column that holds the org name or slug
    org_field_value: str = "slug"  # what to store in org_field: "slug" or "name"
    contact_defaults: dict[str, str] = field(default_factory=dict)
    org_defaults: dict[str, str] = field(default_factory=dict)


@dataclass
class CrmConfig:
    enabled: bool = False
    registries: list[CrmRegistry] = field(default_factory=list)
    internal_domains: list[str] = field(default_factory=list)
    internal_names: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict | None) -> "CrmConfig":
        if not data:
            return cls()
        registries = [
            CrmRegistry(
                name=r.get("name", "contacts"),
                contacts_csv=r.get("contacts_csv", ""),
                category=r.get("category", "contact"),
                org_csv=r.get("org_csv", ""),
                org_field=r.get("org_field", ""),
                org_field_value=r.get("org_field_value", "slug"),
                contact_defaults=dict(r.get("contact_defaults", {})),
                org_defaults=dict(r.get("org_defaults", {})),
            )
            for r in data.get("registries", [])
            if r.get("contacts_csv")
        ]
        return cls(
            enabled=bool(data.get("enabled", False)),
            registries=registries,
            internal_domains=[d.lower() for d in data.get("internal_domains", [])],
            internal_names=[n.lower() for n in data.get("internal_names", [])],
        )


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
    llm_verbatim: bool = True  # second LLM call: full verbatim formatted body
    crm: CrmConfig = field(default_factory=CrmConfig)
    tasks_enabled: bool = False
    task_inbox: Path | None = None  # resolved from kb settings when None
    id_keys: list[str] = field(default_factory=lambda: ["record_id"])
    derive_names_from_email: bool = True
    schedule_sync_hours: int = 1
    schedule_verify: bool = True
    verify_exempt_markers: list[str] = field(default_factory=list)
    env_file: str = ""
    state_dir: Path | None = None

    def record_types(self) -> list[str]:
        """The classification vocabulary: route keys plus a generic fallback."""
        types = list(self.routes.keys())
        if "meeting-transcript" not in types:
            types.append("meeting-transcript")
        return types

    @classmethod
    def load(cls, config_path: str | Path, vault_root: Path | None = None) -> "ConnectorConfig":
        data = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if data.get("env_file"):
            load_env_file(data["env_file"])
        resolved_root = vault_root or resolve_vault_root()
        if data.get("vault_root"):
            resolved_root = Path(data["vault_root"]).resolve()
        if resolved_root is None:
            raise ValueError(
                "Could not resolve the vault root. Configure vault_path in "
                ".claude/knowledge-base.local.md or set vault_root in the connector config."
            )
        state_dir = data.get("state_dir")
        tasks_data = data.get("tasks", {}) or {}
        task_inbox = tasks_data.get("inbox")
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
            llm_verbatim=bool(data.get("llm_verbatim", True)),
            crm=CrmConfig.from_dict(data.get("crm")),
            tasks_enabled=bool(tasks_data.get("enabled", False)),
            task_inbox=(resolved_root / task_inbox) if task_inbox else resolve_task_inbox(),
            id_keys=list(data.get("id_keys", ["record_id"])) or ["record_id"],
            derive_names_from_email=bool(data.get("derive_names_from_email", True)),
            schedule_sync_hours=max(1, int(data.get("schedule_sync_hours", 1))),
            schedule_verify=bool(data.get("schedule_verify", True)),
            verify_exempt_markers=list(data.get("verify_exempt_markers", [])),
            env_file=data.get("env_file", ""),
            state_dir=Path(state_dir).resolve() if state_dir else None,
        )

"""Source-agnostic connector framework: sync external records into the vault."""
from .models import Person, Segment, Record, RecordRef, ActionItem, FormatResult
from .config import ConnectorConfig, CrmConfig, CrmRegistry, resolve_vault_root
from .source import Source
from .state import SyncState
from .engine import SyncEngine, SyncResult
from . import crm, formatter, scheduler, tasks, vault_writer, verifier

__all__ = [
    "Person", "Segment", "Record", "RecordRef", "ActionItem", "FormatResult",
    "ConnectorConfig", "CrmConfig", "CrmRegistry", "resolve_vault_root",
    "Source", "SyncState", "SyncEngine", "SyncResult",
    "crm", "formatter", "scheduler", "tasks", "vault_writer", "verifier",
]

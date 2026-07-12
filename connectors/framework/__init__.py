"""Source-agnostic connector framework: sync external records into the vault."""
from .models import Person, Segment, Record, RecordRef, FormatResult
from .config import ConnectorConfig, resolve_vault_root
from .source import Source
from .state import SyncState
from .engine import SyncEngine, SyncResult
from . import vault_writer, formatter, verifier

__all__ = [
    "Person", "Segment", "Record", "RecordRef", "FormatResult",
    "ConnectorConfig", "resolve_vault_root", "Source", "SyncState",
    "SyncEngine", "SyncResult", "vault_writer", "formatter", "verifier",
]

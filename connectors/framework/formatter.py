"""Formatting a record into metadata + a clean body.

Two modes:
  - Passthrough (default, zero dependencies): derive a title-based type, no tags,
    and use the record's own transcript text. Always available.
  - LLM (optional): if `llm_enabled` and the `anthropic` SDK + an API key are
    present, ask the model for a summary, tags, action items, and a cleaned body.

The LLM path degrades to passthrough on any error, so a connector always makes
progress even offline or without a key.
"""

from __future__ import annotations

import json
import os

from .config import ConnectorConfig
from .models import FormatResult, Record

_METADATA_INSTRUCTIONS = (
    "You format records for a personal knowledge vault. Given a transcript, "
    "return STRICT JSON with keys: summary (2-3 sentences), record_type (one of "
    "meeting-transcript, call, note), tags (3-6 lowercase kebab-case topic tags), "
    "action_items (list of short strings, may be empty). No prose outside the JSON."
)


def _passthrough(record: Record) -> FormatResult:
    return FormatResult(
        summary="",
        record_type="meeting-transcript",
        tags=[],
        action_items=[],
        body=record.transcript_text(),
    )


def _anthropic_client(cfg: ConnectorConfig):
    """Return an Anthropic client, or None if unavailable. Env-var driven."""
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    # Optional enterprise gateway; otherwise the SDK reads ANTHROPIC_API_KEY.
    endpoint = os.environ.get("ANTHROPIC_GATEWAY_URL")
    if endpoint and os.environ.get("ANTHROPIC_GATEWAY_KEY"):
        try:
            return anthropic.Anthropic(
                base_url=endpoint, api_key=os.environ["ANTHROPIC_GATEWAY_KEY"]
            )
        except Exception:
            return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        return anthropic.Anthropic()
    except Exception:
        return None


def format_record(record: Record, cfg: ConnectorConfig) -> FormatResult:
    if not cfg.llm_enabled:
        return _passthrough(record)

    client = _anthropic_client(cfg)
    if client is None:
        return _passthrough(record)

    transcript = record.transcript_text()
    try:
        resp = client.messages.create(
            model=cfg.llm_model,
            max_tokens=1024,
            system=_METADATA_INSTRUCTIONS,
            messages=[{"role": "user", "content": f"Title: {record.title}\n\n{transcript}"}],
        )
        text = "".join(getattr(b, "text", "") for b in resp.content).strip()
        # Tolerate a fenced code block around the JSON.
        if text.startswith("```"):
            text = text.split("```", 2)[1].lstrip("json").strip()
        data = json.loads(text)
        return FormatResult(
            summary=str(data.get("summary", "")),
            record_type=str(data.get("record_type") or "meeting-transcript"),
            tags=[str(t) for t in data.get("tags", [])],
            action_items=[str(a) for a in data.get("action_items", [])],
            body=transcript,
        )
    except Exception:
        return _passthrough(record)

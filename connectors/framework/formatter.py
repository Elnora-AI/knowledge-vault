"""Formatting a record into metadata + a clean body.

Two modes:
  - Passthrough (default, zero dependencies): derive a title-based type, no tags,
    and use the record's own transcript text. Always available.
  - LLM (optional): if `llm_enabled` and the `anthropic` SDK + an API key are
    present, run a two-call pipeline:
      Call 1 — metadata (summary, type, tags, entities, action items, and — when
               CRM is enabled — per-participant enrichment facts) as strict JSON.
      Call 2 — the full verbatim transcript as PLAIN TEXT (`llm_verbatim`),
               with an escalating output-token ladder on truncation.

Why two calls instead of one: a single JSON call must escape every quote and
newline in the transcript, inflating output tokens 30-50%; long or multilingual
records then either hard-truncate or the model quietly self-closes the JSON
mid-conversation, producing a half-transcript that looks complete. Plain text
has no escape overhead and reliably emits every block.

The LLM path degrades to passthrough on any error, so a connector always makes
progress even offline or without a key.
"""

from __future__ import annotations

import json
import os
import re
import time

from .config import ConnectorConfig
from .models import ActionItem, FormatResult, Record

_TRANSIENT_RETRIES = 2
_TRANSIENT_RETRY_BACKOFF_S = 2.0
_TRANSCRIPT_MAX_TOKENS_LADDER = (32000, 48000, 64000)


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
    # 30 min request timeout: long records can stream 60K+ tokens, which
    # exceeds the SDK default when the connection is slow.
    timeout_s = 1800.0
    # Optional enterprise gateway; otherwise the SDK reads ANTHROPIC_API_KEY.
    endpoint = os.environ.get("ANTHROPIC_GATEWAY_URL")
    if endpoint and os.environ.get("ANTHROPIC_GATEWAY_KEY"):
        try:
            return anthropic.Anthropic(
                base_url=_strip_v1(endpoint), api_key=os.environ["ANTHROPIC_GATEWAY_KEY"],
                timeout=timeout_s,
            )
        except Exception:
            return None
    # Azure AI Services uses the same x-api-key auth header as the direct API,
    # so the SDK works natively — just set base_url and api_key.
    azure_endpoint = os.environ.get("AZURE_ANTHROPIC_ENDPOINT")
    azure_key = os.environ.get("AZURE_ANTHROPIC_API_KEY")
    if azure_endpoint and azure_key:
        try:
            return anthropic.Anthropic(
                base_url=_strip_v1(azure_endpoint), api_key=azure_key,
                timeout=timeout_s,
            )
        except Exception:
            return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        return anthropic.Anthropic(timeout=timeout_s)
    except Exception:
        return None


def _strip_v1(endpoint: str) -> str:
    """Strip a trailing /v1 — the SDK appends /v1/messages itself."""
    base = endpoint.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def _retryable_errors() -> tuple[type[BaseException], ...]:
    """Transient API/stream errors worth retrying (SDK + httpx level)."""
    errors: list[type[BaseException]] = []
    try:
        import anthropic  # type: ignore

        errors += [
            anthropic.APIStatusError,  # covers overloaded (529) + 5xx
            anthropic.RateLimitError,
            anthropic.APIConnectionError,
        ]
    except ImportError:
        pass
    try:
        import httpx  # type: ignore

        errors += [httpx.RemoteProtocolError, httpx.ReadError, httpx.ReadTimeout]
    except ImportError:
        pass
    return tuple(errors)


# ---------------------------------------------------------------------------
# Prompts — fully parameterized, no personal or company specifics
# ---------------------------------------------------------------------------

def _metadata_prompt(cfg: ConnectorConfig) -> str:
    owner = cfg.owner_name or "the record owner"
    types = ", ".join(f"`{t}`" for t in cfg.record_types())
    categories = sorted({r.category for r in cfg.crm.registries}) or ["contact"]
    cat_list = " | ".join(f'"{c}"' for c in categories)

    crm_section = ""
    if cfg.crm.enabled:
        crm_section = f"""
## Participant Enrichment

For every participant other than {owner}, extract CRM-relevant facts. Use ONLY
information present in the participant list, email domains, or the transcript
itself. Do NOT invent or guess — leave fields empty/null when unknown.

Each entry: `name`, `email`, `category` ({cat_list} | "internal" | "unknown"),
`role`, `organization`, `notes` (1-2 sentences worth remembering from this record).
Output an empty `enrichment` array when there is nothing to extract.
"""

    return f"""You are a record analyzer for a personal knowledge vault. The vault owner is {owner}.

Analyze the raw transcript and extract ONLY metadata — NOT the formatted
transcript (that happens in a separate step).

1. Write a 2-3 sentence summary.
2. Classify the record as exactly one of: {types}.
3. Generate 3-8 relevant tags (lowercase, hyphenated).
4. List external organizations mentioned (`entities`).
5. Extract concrete action items — clear commitments or follow-ups only, not
   vague ideas. Each has: `task` (short imperative), `owner` (who is
   responsible; default to {owner} if unclear), `due_hint` (e.g. "by Friday",
   null if none).
{crm_section}
Return ONLY valid JSON (no markdown fences, no commentary):

{{
  "summary": "...",
  "record_type": "one-of-the-types-above",
  "tags": ["tag1"],
  "entities": ["Org A"],
  "action_items": [{{"task": "...", "owner": "...", "due_hint": null}}],
  "enrichment": [{{"name": "...", "email": "...", "category": "...", "role": "...", "organization": "...", "notes": "..."}}]
}}"""


def _verbatim_prompt(cfg: ConnectorConfig) -> str:
    owner = cfg.owner_name or "Owner"
    return f"""You are a verbatim transcript formatter. Your only job is to take raw \
transcript segments and produce a clean, complete, readable transcript that \
captures EVERY spoken word.

## CRITICAL — verbatim formatting, NOT summarization

- Output the ENTIRE transcript from the first segment to the last.
- Every sentence in the input must appear in the output.
- Do NOT summarize, condense, paraphrase, abridge, or skip small talk.
- Do NOT write "[continues...]" or any placeholder; do NOT stop early.
- When uncertain, err on the side of including MORE, never less.

## Speakers

- Segments marked (owner) were spoken by {owner} — attribute them to "{owner}".
- Attribute other segments to their given speaker name; use "Unknown Speaker"
  only when no name is given.

## Language

- Keep each segment in its ORIGINAL language. Do NOT translate or add
  bracketed translations. Mixed-language records keep each speaker in their
  own language.

## Formatting

- Clean dialogue: the speaker name on its own line, a blank line, then their
  words as flowing paragraphs. Merge consecutive segments from the same
  speaker into one turn.
- Light cleanup only: drop pure stutters ("I-I-I"); keep substantive false
  starts, hedges, and asides. Preserve the speaker's actual phrasing — do not
  polish or formalize.

## Output

PLAIN TEXT only. No JSON, no code fences, no commentary before or after."""


def _build_user_message(record: Record) -> str:
    parts = ["## Record"]
    parts.append(f"Title: {record.title}")
    if record.started_at:
        parts.append(f"Date: {record.started_at.strftime('%Y-%m-%d %H:%M')}")
    if record.duration_minutes:
        parts.append(f"Duration: {record.duration_minutes} minutes")
    if record.participants:
        parts.append("Participants:")
        for p in record.participants:
            parts.append(f"  {p.name or 'Unknown'} <{p.email or ''}>")
    parts.append("")
    parts.append("## Raw Segments")
    if record.segments:
        for s in record.segments:
            marker = " (owner)" if s.is_owner else ""
            parts.append(f"[{s.speaker or 'Unknown'}{marker}] {s.text}")
    else:
        parts.append(record.raw_text)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_metadata(text: str, cfg: ConnectorConfig) -> FormatResult:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    data = json.loads(text)  # raises ValueError on bad JSON
    if "summary" not in data or "record_type" not in data:
        raise ValueError("metadata response missing required keys")

    items: list[ActionItem] = []
    for item in data.get("action_items", []) or []:
        if isinstance(item, dict) and item.get("task"):
            items.append(ActionItem(
                task=str(item["task"]),
                owner=str(item.get("owner") or ""),
                due_hint=item.get("due_hint") or None,
            ))
        elif isinstance(item, str) and item.strip():
            items.append(ActionItem(task=item.strip()))

    record_type = str(data.get("record_type") or "meeting-transcript")
    if record_type not in cfg.record_types():
        record_type = "meeting-transcript"

    return FormatResult(
        summary=str(data.get("summary", "")),
        record_type=record_type,
        tags=[str(t) for t in data.get("tags", []) or []],
        action_items=items,
        entities=[str(e) for e in data.get("entities", []) or []],
        enrichment=[e for e in data.get("enrichment", []) or [] if isinstance(e, dict)],
    )


# ---------------------------------------------------------------------------
# LLM calls with retry
# ---------------------------------------------------------------------------

def _stream_message(client, retryable, **kwargs):
    for attempt in range(_TRANSIENT_RETRIES + 1):
        try:
            with client.messages.stream(**kwargs) as stream:
                return stream.get_final_message()
        except retryable:
            if attempt >= _TRANSIENT_RETRIES:
                raise
            time.sleep(_TRANSIENT_RETRY_BACKOFF_S * (2 ** attempt))
    raise RuntimeError("unreachable")


def _response_text(response) -> str:
    """Concatenate text blocks, skipping thinking/other block types.

    Extended-thinking models return a ThinkingBlock before the text block, so
    ``content[0]`` is not always the answer.
    """
    return "".join(
        b.text for b in response.content if getattr(b, "type", None) == "text"
    ).strip()


def _call_metadata(client, cfg: ConnectorConfig, user_message: str) -> FormatResult:
    retryable = _retryable_errors()
    kwargs = dict(
        model=cfg.llm_model,
        max_tokens=8192,
        system=[{"type": "text", "text": _metadata_prompt(cfg),
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_message}],
    )
    for attempt in range(_TRANSIENT_RETRIES + 1):
        response = _stream_message(client, retryable, **kwargs)
        try:
            return _parse_metadata(_response_text(response), cfg)
        except (ValueError, IndexError):
            if attempt >= _TRANSIENT_RETRIES:
                raise
            time.sleep(_TRANSIENT_RETRY_BACKOFF_S * (2 ** attempt))
    raise RuntimeError("unreachable")


def _call_verbatim(client, cfg: ConnectorConfig, user_message: str) -> str:
    retryable = _retryable_errors()
    for max_tokens in _TRANSCRIPT_MAX_TOKENS_LADDER:
        response = _stream_message(
            client, retryable,
            model=cfg.llm_model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": _verbatim_prompt(cfg),
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_message}],
        )
        if response.stop_reason == "max_tokens":
            if max_tokens < _TRANSCRIPT_MAX_TOKENS_LADDER[-1]:
                continue  # bump the budget and retry
            raise ValueError(
                f"Verbatim formatting truncated at the maximum {max_tokens}-token "
                "budget — the record exceeds the model's output cap."
            )
        return _response_text(response)
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def format_record(record: Record, cfg: ConnectorConfig) -> FormatResult:
    if not cfg.llm_enabled:
        return _passthrough(record)

    client = _anthropic_client(cfg)
    if client is None:
        return _passthrough(record)

    user_message = _build_user_message(record)
    try:
        result = _call_metadata(client, cfg, user_message)
        if cfg.llm_verbatim:
            result.body = _call_verbatim(client, cfg, user_message)
        else:
            result.body = record.transcript_text()
        return result
    except Exception:
        return _passthrough(record)

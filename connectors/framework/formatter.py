"""Formatting a record into metadata + a clean body.

Two modes:
  - Passthrough (default, zero dependencies): derive a title-based type, no tags,
    and use the record's own transcript text. Always available.
  - LLM (optional): if `llm_enabled` and an API key for any provider is present
    (see llm_provider.py), run a two-call pipeline:
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

Transport: Anthropic goes through the `anthropic` SDK (prompt caching, streaming).
Every other provider speaks OpenAI Chat Completions over the standard library —
streamed, so long records don't hit idle timeouts — and needs no extra package.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request

from .config import ConnectorConfig
from .llm_provider import ResolvedProvider, resolve_provider
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


# 30 min request timeout: long records can stream 60K+ tokens, which exceeds
# a default timeout when the connection is slow.
_TIMEOUT_S = 1800.0


class _AnthropicClient:
    """Anthropic Messages API via the SDK, with prompt caching on the system prompt."""

    def __init__(self, provider: ResolvedProvider):
        import anthropic  # type: ignore

        kwargs = dict(api_key=provider.api_key, timeout=_TIMEOUT_S)
        if provider.base_url:
            kwargs["base_url"] = provider.base_url
        self._client = anthropic.Anthropic(**kwargs)
        self._model = provider.model
        self._retryable = _retryable_errors()

    def complete(self, system: str, user: str, max_tokens: int) -> tuple[str, bool]:
        """Return (text, truncated). Retries transient API/stream errors."""
        kwargs = dict(
            model=self._model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        for attempt in range(_TRANSIENT_RETRIES + 1):
            try:
                with self._client.messages.stream(**kwargs) as stream:
                    response = stream.get_final_message()
                break
            except self._retryable:
                if attempt >= _TRANSIENT_RETRIES:
                    raise
                time.sleep(_TRANSIENT_RETRY_BACKOFF_S * (2 ** attempt))
        # Extended-thinking models return a ThinkingBlock before the text block,
        # so content[0] is not always the answer.
        text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
        return text.strip(), response.stop_reason == "max_tokens"


class _OpenAICompatibleClient:
    """OpenAI Chat Completions (streamed SSE) over urllib — no SDK needed."""

    _RETRYABLE = (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException)

    def __init__(self, provider: ResolvedProvider):
        self._url = provider.base_url.rstrip("/") + "/chat/completions"
        self._model = provider.model
        self._headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if provider.name == "openrouter":
            self._headers["HTTP-Referer"] = os.environ.get("OPENROUTER_SITE_URL", "")
            self._headers["X-Title"] = os.environ.get("OPENROUTER_APP_NAME", "knowledge-vault")
        # OpenAI's reasoning models reject max_tokens; the other endpoints still take it.
        self._max_tokens_key = "max_completion_tokens" if provider.name == "openai" else "max_tokens"

    def complete(self, system: str, user: str, max_tokens: int) -> tuple[str, bool]:
        body = json.dumps({
            "model": self._model,
            self._max_tokens_key: max_tokens,
            "stream": True,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }).encode("utf-8")
        for attempt in range(_TRANSIENT_RETRIES + 1):
            try:
                return self._stream(body)
            except urllib.error.HTTPError as e:
                if e.code not in (408, 409, 429) and e.code < 500:
                    raise
                if attempt >= _TRANSIENT_RETRIES:
                    raise
            except self._RETRYABLE:
                if attempt >= _TRANSIENT_RETRIES:
                    raise
            time.sleep(_TRANSIENT_RETRY_BACKOFF_S * (2 ** attempt))
        raise RuntimeError("unreachable")

    def _stream(self, body: bytes) -> tuple[str, bool]:
        request = urllib.request.Request(self._url, data=body, headers=self._headers, method="POST")
        parts: list[str] = []
        finish_reason = None
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            for raw in response:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:") or line == "data: [DONE]":
                    continue
                event = json.loads(line[5:])
                if event.get("error"):
                    raise RuntimeError(f"LLM error: {event['error']}")
                for choice in event.get("choices", []):
                    parts.append((choice.get("delta") or {}).get("content") or "")
                    finish_reason = choice.get("finish_reason") or finish_reason
        return "".join(parts).strip(), finish_reason == "length"


def _llm_client(cfg: ConnectorConfig):
    """Return a client for the configured provider, or None when it can't run."""
    provider = resolve_provider(cfg.llm_provider, cfg.llm_model)
    if provider.problem:
        return None
    try:
        if provider.base_url and provider.name != "anthropic":
            return _OpenAICompatibleClient(provider)
        return _AnthropicClient(provider)
    except Exception:  # missing `anthropic` package, bad endpoint, …
        return None


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

def _call_metadata(client, cfg: ConnectorConfig, user_message: str) -> FormatResult:
    for attempt in range(_TRANSIENT_RETRIES + 1):
        text, _ = client.complete(_metadata_prompt(cfg), user_message, max_tokens=8192)
        try:
            return _parse_metadata(text, cfg)
        except (ValueError, IndexError):
            if attempt >= _TRANSIENT_RETRIES:
                raise
            time.sleep(_TRANSIENT_RETRY_BACKOFF_S * (2 ** attempt))
    raise RuntimeError("unreachable")


def _call_verbatim(client, cfg: ConnectorConfig, user_message: str) -> str:
    for max_tokens in _TRANSCRIPT_MAX_TOKENS_LADDER:
        text, truncated = client.complete(_verbatim_prompt(cfg), user_message, max_tokens=max_tokens)
        if truncated:
            if max_tokens < _TRANSCRIPT_MAX_TOKENS_LADDER[-1]:
                continue  # bump the budget and retry
            raise ValueError(
                f"Verbatim formatting truncated at the maximum {max_tokens}-token "
                "budget — the record exceeds the model's output cap."
            )
        return text
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def format_record(record: Record, cfg: ConnectorConfig) -> FormatResult:
    if not cfg.llm_enabled:
        return _passthrough(record)

    client = _llm_client(cfg)
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

#!/usr/bin/env python3
"""Shared utilities for knowledge-base hook scripts. Cross-platform."""

import json
import os
import re
import sys
from pathlib import Path


CONFIG_REL = Path(".claude") / "knowledge-base.local.md"


def _read_stdin_json():
    """Read the hook payload from stdin, or "" when stdin is unavailable.

    Guards against an interactive TTY (which would block on read) and against
    pytest's captured stdin (which raises on read).
    """
    try:
        stdin = sys.stdin
        if stdin is None or stdin.isatty():
            return ""
        return stdin.read()
    except (OSError, ValueError):
        return ""


def read_hook_tool_input():
    """Return the PostToolUse hook's ``tool_input`` dict.

    Claude Code delivers the hook payload as JSON on stdin, shaped like
    ``{"tool_name": ..., "tool_input": {...}, "tool_response": {...}}``. We
    read stdin first, then fall back to the ``CLAUDE_TOOL_INPUT`` env var
    (used by tests). Either source may carry the full payload or a bare
    ``tool_input`` object; the former is unwrapped. Returns ``{}`` when
    nothing usable is available.
    """
    raw = _read_stdin_json()
    if not raw.strip():
        raw = os.environ.get("CLAUDE_TOOL_INPUT", "")
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    tool_input = data.get("tool_input")
    if isinstance(tool_input, dict):
        return tool_input
    return data


def _config_path():
    """Locate the per-user config file, or None.

    Searches for `.claude/knowledge-base.local.md` specifically (not just any
    `.claude/` directory — that would wrongly match the global ~/.claude when a
    hook runs from an installed plugin). Order:
    1. $CLAUDE_PROJECT_DIR (the harness's authoritative project root)
    2. CWD (hooks normally run from the project root)
    3. Walk up from CWD
    """
    candidates = []

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if project_dir:
        candidates.append(Path(project_dir) / CONFIG_REL)

    cwd = Path.cwd()
    candidates.append(cwd / CONFIG_REL)
    for parent in cwd.parents:
        candidates.append(parent / CONFIG_REL)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _find_project_root():
    """The project root (parent of `.claude/`), or CWD if no config is found."""
    cfg = _config_path()
    if cfg:
        return cfg.parent.parent
    return Path.cwd()


def get_config_value(key, default=None):
    """Read a single top-level key from the config frontmatter.

    Uses a targeted regex so nested/complex YAML elsewhere in the file cannot
    break parsing. Returns the stripped string value, or `default`.
    """
    path = _config_path()
    if not path:
        return default
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return default
    match = re.search(rf"^{re.escape(key)}:\s*(.*)$", content, re.MULTILINE)
    if not match:
        return default
    value = match.group(1).strip().strip("\"'")
    return value if value != "" else default


def get_vault_path():
    """Read the absolute `vault_path` from config. Returns a resolved Path or None."""
    raw = get_config_value("vault_path")
    if not raw:
        return None
    return Path(raw).resolve()


def get_vault_root():
    """Resolve the vault root: vault_path + optional vault_dir. Returns Path or None."""
    vault_path = get_vault_path()
    if not vault_path:
        return None
    vault_dir = get_config_value("vault_dir")
    if vault_dir:
        return (vault_path / vault_dir).resolve()
    return vault_path


def parse_frontmatter(content):
    """Parse simple YAML frontmatter from markdown content.

    Returns (dict, body) where dict has string keys/values and body is the
    content after the closing '---'. If no frontmatter is found, returns
    ({}, content).
    """
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    fm = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, parts[2]

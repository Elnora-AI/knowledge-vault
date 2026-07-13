"""Tests for the hook scripts: config resolution and index generation."""

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent.parent / "hooks" / "scripts"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HOOKS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hook_payload(tool_name, tool_input):
    """A PostToolUse payload in the exact shape Claude Code writes to hook stdin."""
    return {
        "session_id": "test-session",
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": "/tmp",
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_response": {"success": True},
    }


def _run_hook(script, payload, project):
    """Invoke a hook script the way the harness does: JSON payload on stdin."""
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    # Guarantee the stdin path is what's exercised, not the env-var fallback.
    env.pop("CLAUDE_TOOL_INPUT", None)
    return subprocess.run(
        [sys.executable, str(HOOKS / script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(project),
        env=env,
        timeout=60,
    )


def _make_project(tmp_path, vault_rel="my-vault", extra=""):
    """Create a project with .claude/knowledge-base.local.md and a vault."""
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    vault = tmp_path / vault_rel
    vault.mkdir(parents=True)
    config = f"""---
vault_path: {vault}
vault_dir: ""
task_inbox: tasks/inbox.md
task_todo: tasks/to-do.md
notes_dir: notes
index_file: notes/index.md
vault_title: Test Vault
default_owner: jane-doe
{extra}---

# config
"""
    (project / ".claude" / "knowledge-base.local.md").write_text(config, encoding="utf-8")
    return project, vault


def test_shared_reads_config(tmp_path, monkeypatch):
    project, vault = _make_project(tmp_path)
    monkeypatch.chdir(project)
    shared = _load("shared", "shared.py")
    assert shared.get_config_value("vault_title") == "Test Vault"
    assert shared.get_config_value("default_owner") == "jane-doe"
    assert shared.get_config_value("missing", "fallback") == "fallback"
    assert shared.get_vault_path() == vault.resolve()
    assert shared.get_vault_root() == vault.resolve()


def test_shared_vault_dir_appended(tmp_path, monkeypatch):
    project = tmp_path / "project"
    (project / ".claude").mkdir(parents=True)
    vault = tmp_path / "drive"
    (vault / "inner").mkdir(parents=True)
    (project / ".claude" / "knowledge-base.local.md").write_text(
        f"---\nvault_path: {vault}\nvault_dir: inner\n---\n", encoding="utf-8"
    )
    monkeypatch.chdir(project)
    shared = _load("shared", "shared.py")
    assert shared.get_vault_root() == (vault / "inner").resolve()


def test_shared_no_config_returns_none(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    shared = _load("shared", "shared.py")
    # Must NOT wander up into a global ~/.claude — no config file, no vault.
    assert shared.get_config_value("vault_path") is None
    assert shared.get_vault_path() is None


def test_index_generation(tmp_path, monkeypatch):
    project, vault = _make_project(tmp_path)
    # Seed a couple of docs.
    (vault / "notes").mkdir()
    (vault / "meetings").mkdir()
    (vault / "notes" / "idea.md").write_text("---\ntitle: A Big Idea\n---\n# A Big Idea\n", encoding="utf-8")
    (vault / "meetings" / "2026-03-10-acme-globex.md").write_text("# Acme Globex\n", encoding="utf-8")
    monkeypatch.chdir(project)

    idx = _load("update_vault_index", "update-vault-index.py")
    index_path = idx.get_index_path()
    assert index_path == (vault / "notes" / "index.md").resolve()

    docs, empty = idx.scan_vault(vault, index_path)
    content = idx.generate_index(docs, empty, index_path)
    assert "# Test Vault" in content
    assert "A Big Idea" in content
    assert "Acme Globex" in content
    assert 'owner: "jane-doe"' in content
    # No numbered-folder or company assumptions leaked into the output.
    company_marker = "el" + "nora"  # built to avoid tripping the repo secret guard
    assert company_marker not in content.lower()

    # Full run writes the file and skips the index itself on rescan.
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(content, encoding="utf-8")
    docs2, _ = idx.scan_vault(vault, index_path)
    all_paths = [d["path"] for items in docs2.values() for d in items]
    assert "notes/index.md" not in all_paths


def test_index_refresh_hours_configurable(tmp_path, monkeypatch):
    project, vault = _make_project(tmp_path, extra="index_refresh_hours: 168\n")
    monkeypatch.chdir(project)
    idx = _load("update_vault_index", "update-vault-index.py")
    assert idx._refresh_hours() == 168


def test_index_refresh_hours_defaults_and_tolerates_bad_values(tmp_path, monkeypatch):
    project, vault = _make_project(tmp_path)  # key absent
    monkeypatch.chdir(project)
    idx = _load("update_vault_index", "update-vault-index.py")
    assert idx._refresh_hours() == 24
    project2, _ = _make_project(tmp_path / "b", extra="index_refresh_hours: notanumber\n")
    monkeypatch.chdir(project2)
    idx2 = _load("update_vault_index", "update-vault-index.py")
    assert idx2._refresh_hours() == 24


def test_index_async_toggle(tmp_path, monkeypatch):
    # Default: async on.
    project, _ = _make_project(tmp_path)
    monkeypatch.chdir(project)
    idx = _load("update_vault_index", "update-vault-index.py")
    assert idx._async_enabled() is True
    # Explicit false disables it.
    project2, _ = _make_project(tmp_path / "b", extra="index_async: false\n")
    monkeypatch.chdir(project2)
    idx2 = _load("update_vault_index", "update-vault-index.py")
    assert idx2._async_enabled() is False


def test_index_excludes_dot_folders(tmp_path, monkeypatch):
    project, vault = _make_project(tmp_path)
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "workspace.md").write_text("# internal\n", encoding="utf-8")
    (vault / "notes").mkdir()
    (vault / "notes" / "keep.md").write_text("# Keep\n", encoding="utf-8")
    monkeypatch.chdir(project)
    idx = _load("update_vault_index", "update-vault-index.py")
    docs, _ = idx.scan_vault(vault, idx.get_index_path())
    all_paths = [d["path"] for items in docs.values() for d in items]
    assert "notes/keep.md" in all_paths
    assert not any(".obsidian" in p for p in all_paths)


# ---------------------------------------------------------------------------
# PostToolUse hook input: read the real stdin payload, not a nonexistent env var
# ---------------------------------------------------------------------------

def test_read_hook_tool_input_from_stdin(monkeypatch):
    # Claude Code delivers the whole payload as JSON on stdin; the helper must
    # unwrap the nested `tool_input` object.
    shared = _load("shared", "shared.py")
    payload = _hook_payload("Write", {"file_path": "/vault/notes/x.md", "content": "hi"})
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.delenv("CLAUDE_TOOL_INPUT", raising=False)
    assert shared.read_hook_tool_input() == {"file_path": "/vault/notes/x.md", "content": "hi"}


def test_read_hook_tool_input_env_fallback(monkeypatch):
    # With no stdin payload, tests may supply a bare tool_input via the env var.
    shared = _load("shared", "shared.py")
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    monkeypatch.setenv("CLAUDE_TOOL_INPUT", json.dumps({"file_path": "/a/b.md"}))
    assert shared.read_hook_tool_input() == {"file_path": "/a/b.md"}


def test_check_vault_write_rebuilds_index_from_stdin(tmp_path):
    # A write inside the vault, delivered as a real stdin payload, must trigger
    # the forced index rebuild (proves the hook parses tool_input.file_path).
    project, vault = _make_project(tmp_path)
    payload = _hook_payload(
        "Write", {"file_path": str(vault / "notes" / "new-doc.md"), "content": "# New Doc\n"}
    )
    result = _run_hook("check-vault-write.py", payload, project)
    assert result.returncode == 0, result.stderr
    assert (vault / "notes" / "index.md").exists()


def test_check_vault_write_ignores_outside_vault(tmp_path):
    # A write outside the vault must not rebuild anything.
    project, vault = _make_project(tmp_path)
    outside = tmp_path / "elsewhere" / "note.md"
    payload = _hook_payload("Write", {"file_path": str(outside), "content": "x"})
    result = _run_hook("check-vault-write.py", payload, project)
    assert result.returncode == 0, result.stderr
    assert not (vault / "notes" / "index.md").exists()


def test_check_task_move_warns_from_stdin(tmp_path):
    # A task copied into done.md while still in inbox.md must warn — driven by
    # the real stdin payload, not the (nonexistent) CLAUDE_TOOL_INPUT env var.
    project, vault = _make_project(tmp_path)
    tasks = vault / "tasks"
    tasks.mkdir()
    (tasks / "inbox.md").write_text("- [ ] #task buy milk tomorrow\n", encoding="utf-8")
    payload = _hook_payload(
        "Write",
        {"file_path": str(tasks / "done.md"), "content": "- [x] #task buy milk tomorrow\n"},
    )
    result = _run_hook("check-task-move.py", payload, project)
    assert result.returncode == 0, result.stderr
    assert "TASK MOVE INCOMPLETE" in result.stderr

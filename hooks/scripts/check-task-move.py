#!/usr/bin/env python3
"""PostToolUse hook: when a task is added to done.md/to-do.md/cancelled.md,
check if that task still exists in inbox.md. If so, warn the assistant
to remove it from inbox — tasks must be MOVED, not copied.

Also checks the reverse: task added to to-do.md but still in inbox.md.
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared import get_vault_root, get_config_value


def _get_task_dir() -> Path | None:
    """Get the task directory from config (parent of any task file)."""
    vault_root = get_vault_root()
    if not vault_root:
        return None

    # Task paths are relative to the vault root — derive the dir from any of them.
    for key in ("task_inbox", "task_todo", "task_in_progress", "task_done"):
        rel = get_config_value(key)
        if rel:
            return (vault_root / Path(rel).parent).resolve()
    return None


def _extract_task_descriptions(text: str) -> list[str]:
    """Extract task description strings from markdown task lines."""
    tasks = []
    for line in text.splitlines():
        m = re.match(r"^(?:\d+\.\s+)?- \[.\] #task (.+)$", line)
        if m:
            # Strip emoji and dates for fuzzy matching
            desc = m.group(1).strip()
            # Remove priority/status emojis and dates for comparison
            desc_clean = re.sub(r"[⏫🔼🔽✅❌📅]\s*\d{4}-\d{2}-\d{2}|[⏫🔼🔽✅❌]", "", desc).strip()
            desc_clean = re.sub(r"\s+", " ", desc_clean)
            if desc_clean:
                tasks.append(desc_clean)
    return tasks


def main():
    tool_input = os.environ.get("CLAUDE_TOOL_INPUT", "")
    if not tool_input:
        sys.exit(0)

    try:
        data = json.loads(tool_input)
        file_path = data.get("file_path", "")
    except (json.JSONDecodeError, AttributeError):
        sys.exit(0)

    if not file_path:
        sys.exit(0)

    written_path = Path(file_path).resolve()
    task_dir = _get_task_dir()
    if not task_dir:
        sys.exit(0)

    # Only care about writes to task files (done, to-do, cancelled) — NOT inbox
    task_files = {"done.md", "to-do.md", "cancelled.md"}
    if written_path.parent.resolve() != task_dir.resolve():
        sys.exit(0)
    if written_path.name not in task_files:
        sys.exit(0)

    # A task was added to a destination file — check if inbox still has it
    inbox_path = task_dir / "inbox.md"
    if not inbox_path.exists():
        sys.exit(0)

    inbox_content = inbox_path.read_text(encoding="utf-8")
    inbox_tasks = _extract_task_descriptions(inbox_content)

    if not inbox_tasks:
        # Inbox is empty, nothing to warn about
        sys.exit(0)

    # Check what was just written — look at new_string (Edit) or content (Write)
    new_content = data.get("new_string", "") or data.get("content", "")
    added_tasks = _extract_task_descriptions(new_content)

    if not added_tasks:
        sys.exit(0)

    # Fuzzy match: check if any added task description appears in inbox
    orphaned = []
    for added in added_tasks:
        added_words = set(added.lower().split())
        for inbox_task in inbox_tasks:
            inbox_words = set(inbox_task.lower().split())
            # If 60%+ of words overlap, it's likely the same task
            if len(added_words & inbox_words) >= 0.6 * min(len(added_words), len(inbox_words)):
                orphaned.append(inbox_task)
                break

    if orphaned:
        task_list = "\n".join(f"  - {t[:80]}" for t in orphaned)
        print(
            f"⚠️ TASK MOVE INCOMPLETE: {len(orphaned)} task(s) were added to {written_path.name} "
            f"but still exist in inbox.md. Tasks must be MOVED, not copied. "
            f"Remove these from inbox.md now:\n{task_list}",
            file=sys.stderr,
        )
        # Exit 0 — this is a warning, not a blocker
        sys.exit(0)


if __name__ == "__main__":
    main()

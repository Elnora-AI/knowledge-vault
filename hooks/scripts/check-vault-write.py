#!/usr/bin/env python3
"""
Check if a Write tool call targeted the vault, and if so, update the index.
Reads tool input from CLAUDE_TOOL_INPUT env var to get the file_path.
"""

import os
import sys
import json
import subprocess
import tempfile
import hashlib
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared import get_vault_path

_DEBOUNCE_SECONDS = 60


def main():
    # Get the file path from the tool input
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

    # Resolve to absolute path
    written_path = Path(file_path).resolve()

    # Get vault path
    vault_path = get_vault_path()
    if not vault_path:
        sys.exit(0)

    # Check if the written file is inside the vault
    try:
        written_path.relative_to(vault_path)
    except ValueError:
        # Not in vault, skip
        sys.exit(0)

    # File is in the vault — run index update (with 60s debounce).
    # The debounce marker lives in the OS temp dir (keyed by vault path) so we
    # never write into the user's project tree.
    vault_key = hashlib.sha1(str(vault_path).encode("utf-8")).hexdigest()[:16]
    timestamp_file = Path(tempfile.gettempdir()) / f"kb-vault-index-{vault_key}.stamp"

    if timestamp_file.exists():
        age = time.time() - timestamp_file.stat().st_mtime
        if age < _DEBOUNCE_SECONDS:
            sys.exit(0)

    script_dir = Path(__file__).resolve().parent
    update_script = script_dir / "update-vault-index.py"

    if update_script.exists():
        subprocess.run(
            [sys.executable, str(update_script), "--force"],
            timeout=60
        )
        # Touch timestamp file after spawning rebuild
        timestamp_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp_file.touch()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Clean cache files older than 48 hours. Cross-platform."""
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared import _find_project_root

MAX_AGE_HOURS = 48


def main():
    project_root = _find_project_root()
    cache_dir = project_root / 'cache'

    if not cache_dir.exists():
        return

    now = time.time()
    max_age_seconds = MAX_AGE_HOURS * 3600
    deleted = 0

    for folder in ['tool-outputs', 'scratch', 'context-snapshots']:
        folder_path = cache_dir / folder
        if not folder_path.exists():
            continue

        for file in folder_path.iterdir():
            if file.name.lower().startswith('readme'):
                continue
            if not file.is_file():
                continue
            if (now - file.stat().st_mtime) > max_age_seconds:
                file.unlink()
                deleted += 1

    if deleted > 0:
        print(json.dumps({"message": f"Cache cleanup: {deleted} files removed"}))


if __name__ == '__main__':
    main()

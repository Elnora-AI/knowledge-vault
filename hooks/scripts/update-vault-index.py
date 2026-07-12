#!/usr/bin/env python3
"""
Update the auto-generated vault index file.
Triggers:
- Every 24 hours (checked on session start)

The index location, title, owner, and excluded folders all come from the
per-user config (.claude/knowledge-base.local.md). Nothing is hardcoded.
"""

import sys
import re
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared import (
    _find_project_root,
    get_vault_path,
    get_vault_root,
    get_config_value,
    parse_frontmatter,
)

# Folders never indexed. Overridable via `index_exclude` (comma-separated) in config.
DEFAULT_EXCLUDE = {".obsidian", ".git", ".trash", "attachments"}


def print_kb_config():
    """Print the resolved config at session start.

    Reads only the per-user, gitignored .claude/knowledge-base.local.md — no
    path is hardcoded, so each machine resolves its own vault mount.
    """
    root = _find_project_root()
    config_path = root / ".claude" / "knowledge-base.local.md"
    if not config_path.exists():
        print("Knowledge base not configured. Run /kb-setup or create .claude/knowledge-base.local.md")
        return
    try:
        fm, _ = parse_frontmatter(config_path.read_text(encoding="utf-8"))
    except Exception:
        print("Knowledge base config unreadable: .claude/knowledge-base.local.md")
        return
    vault_path_str = (fm.get("vault_path") or "").strip("\"'")
    if not vault_path_str:
        print("Knowledge base vault_path not set")
    elif Path(vault_path_str).exists():
        print(f"Knowledge base: {vault_path_str}")
    else:
        print(f"Knowledge base path not found: {vault_path_str}")


def get_index_path():
    """Resolve the auto-generated index file path from config.

    Location: {vault_root}/{index_file} (default notes/index.md). Hand-curated
    folder hubs are named `_index.md`, one per folder — separate from this
    auto-master and never overwritten by it.
    """
    vault_root = get_vault_root()
    if vault_root and vault_root.exists():
        index_file = get_config_value("index_file") or "notes/index.md"
        return vault_root / index_file
    return None


def get_excluded_folders():
    """Return the set of folder names to skip while scanning."""
    raw = get_config_value("index_exclude")
    if raw:
        return {p.strip() for p in raw.split(",") if p.strip()}
    return set(DEFAULT_EXCLUDE)


def should_update_index(index_path, force=False):
    """Check if index should be updated (24h passed or forced)"""
    if force:
        return True
    if not index_path.exists():
        return True
    mtime = datetime.fromtimestamp(index_path.stat().st_mtime)
    if datetime.now() - mtime > timedelta(hours=24):
        return True
    return False


def scan_vault(vault_root, index_path=None):
    """Scan the vault and return a structured document list and empty folders.

    Single-pass scan: iterates vault_root.rglob("*") once, collecting .md/.base/
    .canvas files and tracking which directories contain files (to detect empty
    placeholder folders). The index file itself is never indexed.
    """
    docs = {}
    vault_root = Path(vault_root)
    skip_folders = get_excluded_folders()
    indexed_extensions = {".md", ".base", ".canvas"}
    index_abs = Path(index_path).resolve() if index_path else None

    all_dirs = set()
    dirs_with_files = set()

    for item in vault_root.rglob("*"):
        rel_path = item.relative_to(vault_root)

        # Skip hidden folders/files (starting with .)
        if any(part.startswith(".") for part in rel_path.parts):
            continue

        # Skip if inside an excluded folder
        if any(part in skip_folders for part in rel_path.parts):
            continue

        if item.is_dir():
            all_dirs.add(str(rel_path).replace("\\", "/"))
            continue

        if item.suffix not in indexed_extensions:
            continue

        # Never index the generated index file itself.
        if index_abs and item.resolve() == index_abs:
            continue

        # Skip folder-hub files — hand-curated navigation, not first-class docs.
        # Agents discover them via Glob("**/_index.md").
        if item.suffix == ".md" and item.name.lower() in ("_index.md", "readme.md"):
            continue

        # Mark all ancestor dirs as non-empty
        for parent in rel_path.parents:
            parent_str = str(parent).replace("\\", "/")
            if parent_str and parent_str != ".":
                dirs_with_files.add(parent_str)

        if item.suffix == ".md":
            title = get_title_from_file(item)
        else:
            title = item.stem.replace("-", " ").title()

        folder = str(rel_path.parent).replace("\\", "/") if rel_path.parent != Path(".") else "root"
        docs.setdefault(folder, []).append(
            {"title": title, "path": str(rel_path).replace("\\", "/"), "name": item.stem}
        )

    empty_folders = all_dirs - dirs_with_files
    return docs, empty_folders


def get_title_from_file(file_path):
    """Extract title from frontmatter, then H1, then filename."""
    try:
        content = file_path.read_text(encoding="utf-8")
        if content.startswith("---"):
            frontmatter, _ = parse_frontmatter(content)
            title = frontmatter.get("title")
            if title:
                return str(title).strip().strip("\"'")
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return file_path.stem.replace("-", " ").title()


def _get_first_created(index_path):
    """Get the original creation date from an existing index, or today."""
    if index_path and index_path.exists():
        try:
            fm, _ = parse_frontmatter(index_path.read_text(encoding="utf-8"))
            if fm.get("created"):
                return str(fm["created"]).strip().strip("\"'")
        except Exception:
            pass
    return datetime.now().strftime("%Y-%m-%d")


def generate_index(docs, empty_folders=None, index_path=None):
    """Generate the index markdown content."""
    if empty_folders is None:
        empty_folders = set()

    title = get_config_value("vault_title") or "Knowledge Base"
    owner = get_config_value("default_owner") or ""

    lines = [
        "---",
        f'title: "{title}"',
        "type: index",
        "status: current",
        f"created: {_get_first_created(index_path)}",
        f"updated: {datetime.now().strftime('%Y-%m-%d')}",
    ]
    if owner:
        lines.append(f'owner: "{owner}"')
    lines.extend(
        [
            "tags: [moc, vault-root]",
            'description: "Auto-generated master index of the vault"',
            "related: []",
            "---",
            "",
            f"# {title}",
            "",
        ]
    )

    total = sum(len(v) for v in docs.values())
    lines.append(f"Master index of all vault documents. {total} documents organized by folder.")
    lines.append("")
    lines.append("---")
    lines.append("")

    folder_groups = {}
    empty_folder_groups = {}

    for folder, items in sorted(docs.items()):
        if folder == "root":
            continue
        parts = folder.split("/")
        top_folder = parts[0] if parts else "Other"
        folder_groups.setdefault(top_folder, {})
        subfolder = "/".join(parts[1:]) if len(parts) > 1 else ""
        folder_groups[top_folder].setdefault(subfolder, []).extend(items)

    for folder in sorted(empty_folders):
        parts = folder.split("/")
        top_folder = parts[0] if parts else "Other"
        subfolder = "/".join(parts[1:]) if len(parts) > 1 else ""
        empty_folder_groups.setdefault(top_folder, set())
        if subfolder:
            empty_folder_groups[top_folder].add(subfolder)

    all_top_folders = set(folder_groups.keys()) | set(empty_folder_groups.keys())

    for top_folder in sorted(all_top_folders):
        section_name = top_folder.replace("-", " ").title()
        # Preserve any numeric prefix a user chose (e.g. "01-foo" -> "01 - Foo").
        match = re.match(r"(\d+)-(.+)", top_folder)
        if match:
            section_name = f"{match.group(1)} - {match.group(2).replace('-', ' ').title()}"

        lines.append(f"## {section_name}")
        lines.append("")

        has_docs = top_folder in folder_groups
        has_empty_subfolders = top_folder in empty_folder_groups

        if has_docs:
            subfolders = folder_groups[top_folder]
            for subfolder in sorted(subfolders.keys()):
                items = subfolders[subfolder]
                if subfolder:
                    subsection_name = subfolder.split("/")[-1].replace("-", " ").title()
                    lines.append(f"### {subsection_name}")
                    lines.append("")
                lines.append("| Document | Description |")
                lines.append("|----------|-------------|")
                for item in sorted(items, key=lambda x: x["name"]):
                    path = f"./{item['path']}"
                    lines.append(
                        f"| [{item['title']}]({path}) | {item['name'].replace('-', ' ').title()} |"
                    )
                lines.append("")

        if has_empty_subfolders:
            if not has_docs:
                lines.append("*Placeholder for future documentation.*")
                lines.append("")
            for empty_sub in sorted(empty_folder_groups[top_folder]):
                subsection_name = empty_sub.split("/")[-1].replace("-", " ").title()
                lines.append(f"### {subsection_name}")
                lines.append("")
                lines.append("*No documents yet.*")
                lines.append("")

        lines.append("---")
        lines.append("")

    lines.extend(
        [
            "## About this vault",
            "",
            f"**Document count:** {total} files",
            "",
            "**Conventions:**",
            "- Files use kebab-case naming (lowercase with hyphens)",
            "- All documents should have YAML frontmatter",
            "- Folder hubs are named `_index.md`; this file is generated automatically",
            "",
            "---",
            "",
            f"*Last updated: {datetime.now().strftime('%Y-%m-%d')}*",
            "",
        ]
    )

    return "\n".join(lines)


def main():
    # Surface the resolved config on every session start.
    print_kb_config()

    force = "--force" in sys.argv or "-f" in sys.argv

    vault_path = get_vault_path()
    if not vault_path or not vault_path.exists():
        # Graceful exit — vault may not be configured on this machine.
        sys.exit(0)

    index_path = get_index_path()
    if not index_path:
        sys.exit(0)

    if not should_update_index(index_path, force):
        print("Index is up to date (less than 24h old)")
        sys.exit(0)

    vault_root = get_vault_root()
    docs, empty_folders = scan_vault(vault_root, index_path)
    content = generate_index(docs, empty_folders, index_path)

    # Ensure the notes/index directory exists.
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(content, encoding="utf-8")
    print(f"Updated vault index: {index_path}")
    print(f"Total documents: {sum(len(v) for v in docs.values())}")
    if empty_folders:
        print(f"Empty placeholder folders: {len(empty_folders)}")


if __name__ == "__main__":
    main()

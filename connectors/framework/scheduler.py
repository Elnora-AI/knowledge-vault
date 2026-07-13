"""Cross-platform scheduling for connector syncs.

``install(cfg, config_path)`` / ``uninstall(cfg)`` register recurring jobs on
the host's native scheduler:

- **macOS**: launchd LaunchAgents (loaded immediately).
- **Windows**: Task Scheduler tasks (``schtasks``) pointing at generated
  wrapper ``.cmd`` files.
- **Linux**: lines in the user crontab, tagged with a marker comment.

Two jobs per connector: an hourly-ish ``sync`` (interval from
``schedule_sync_hours``) and, when ``schedule_verify`` is on, a weekly
``verify``. A scheduled job does not inherit your interactive shell, so the
location of ``.claude/knowledge-base.local.md`` is pinned via the
``CLAUDE_PROJECT_DIR`` environment variable at install time. Secrets are NOT
copied into job definitions — put e.g. ``ANTHROPIC_API_KEY`` in an env file
and reference it via ``env_file`` in the connector config instead.

If the native scheduler can't be driven, the exact command is printed so the
user always has a manual path forward.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .config import ConnectorConfig, _find_config
from .state import default_state_dir


def _entrypoint() -> tuple[str, Path]:
    """Return (python executable, path to connectors/cli.py)."""
    return sys.executable, Path(__file__).resolve().parent.parent / "cli.py"


def _pinned_env() -> dict[str, str]:
    """Pin the kb-settings location so the detached job resolves the same vault."""
    found = _find_config()
    if found is not None:
        # _find_config looks for <dir>/.claude/knowledge-base.local.md
        return {"CLAUDE_PROJECT_DIR": str(found.parent.parent)}
    return {}


def _jobs(cfg: ConnectorConfig, config_path: Path) -> list[dict]:
    python, cli = _entrypoint()
    jobs = [{
        "name": f"{cfg.source_name}-sync",
        "args": [python, str(cli), "sync", "--config", str(config_path)],
        "interval_hours": cfg.schedule_sync_hours,
        "weekly": False,
    }]
    if cfg.schedule_verify:
        jobs.append({
            "name": f"{cfg.source_name}-verify",
            "args": [python, str(cli), "verify", "--config", str(config_path)],
            "interval_hours": 0,
            "weekly": True,
        })
    return jobs


def _label(job_name: str) -> str:
    return f"knowledge-vault-{job_name}"


# ---------------------------------------------------------------------------
# macOS — launchd
# ---------------------------------------------------------------------------

def _install_macos(job: dict, env: dict[str, str]) -> bool:
    import plistlib

    label = f"com.knowledge-vault.{job['name']}"
    log_dir = Path.home() / "Library" / "Logs" / "knowledge-vault"
    log_dir.mkdir(parents=True, exist_ok=True)
    plist: dict = {
        "Label": label,
        "ProgramArguments": job["args"],
        "StandardOutPath": str(log_dir / f"{job['name']}.out.log"),
        "StandardErrorPath": str(log_dir / f"{job['name']}.err.log"),
        "RunAtLoad": False,
    }
    if job["weekly"]:
        plist["StartCalendarInterval"] = {"Weekday": 5, "Hour": 15, "Minute": 0}
    else:
        plist["StartInterval"] = job["interval_hours"] * 3600
    if env:
        plist["EnvironmentVariables"] = env
    dest = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        plistlib.dump(plist, f)
    subprocess.run(["launchctl", "unload", str(dest)], capture_output=True, text=True)
    result = subprocess.run(["launchctl", "load", str(dest)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"launchctl load failed for {label}: {result.stderr.strip()}", file=sys.stderr)
        return False
    when = "weekly (Fri 15:00)" if job["weekly"] else f"every {job['interval_hours']}h"
    print(f"Installed launchd job {label} ({when}).")
    print(f"  Plist: {dest}")
    print(f"  Logs:  {log_dir}")
    return True


def _uninstall_macos(job: dict) -> None:
    label = f"com.knowledge-vault.{job['name']}"
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"
    if not plist_path.exists():
        print(f"Not installed: {label}")
        return
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True, text=True)
    plist_path.unlink(missing_ok=True)
    print(f"Uninstalled launchd job {label}.")


# ---------------------------------------------------------------------------
# Windows — Task Scheduler (schtasks) + env wrapper
# ---------------------------------------------------------------------------

def _wrapper_dir() -> Path:
    d = default_state_dir() / "schedule"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _install_windows(job: dict, env: dict[str, str]) -> bool:
    lines = ["@echo off"]
    for k, v in env.items():
        lines.append(f'set "{k}={v}"')
    lines.append(" ".join(f'"{a}"' for a in job["args"]))
    wrapper = _wrapper_dir() / f"{_label(job['name'])}.cmd"
    wrapper.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")

    task = _label(job["name"])
    if job["weekly"]:
        cmd = ["schtasks", "/Create", "/TN", task, "/SC", "WEEKLY", "/D", "FRI",
               "/ST", "15:00", "/TR", str(wrapper), "/F"]
    else:
        cmd = ["schtasks", "/Create", "/TN", task, "/SC", "HOURLY",
               "/MO", str(job["interval_hours"]), "/TR", str(wrapper), "/F"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"schtasks failed: {result.stderr.strip() or result.stdout.strip()}",
              file=sys.stderr)
        return False
    print(f"Installed Task Scheduler task {task}.")
    print(f"  Wrapper: {wrapper}")
    return True


def _uninstall_windows(job: dict) -> None:
    task = _label(job["name"])
    result = subprocess.run(["schtasks", "/Delete", "/TN", task, "/F"],
                            capture_output=True, text=True)
    (_wrapper_dir() / f"{task}.cmd").unlink(missing_ok=True)
    if result.returncode != 0:
        print(f"Task not found or already removed: {task}")
        return
    print(f"Uninstalled Task Scheduler task {task}.")


# ---------------------------------------------------------------------------
# Linux — user crontab
# ---------------------------------------------------------------------------

def _read_crontab() -> list[str]:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    # rc != 0 with "no crontab" is normal for a user with no crontab yet.
    if result.returncode != 0 and "no crontab" not in (result.stderr + result.stdout).lower():
        raise RuntimeError(result.stderr.strip() or "crontab -l failed")
    return result.stdout.splitlines()


def _write_crontab(lines: list[str]) -> None:
    content = "\n".join(lines).rstrip("\n") + "\n"
    result = subprocess.run(["crontab", "-"], input=content, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "crontab - failed")


def _install_linux(job: dict, env: dict[str, str]) -> bool:
    marker = f"# {_label(job['name'])}"
    env_prefix = " ".join(f'{k}="{v}"' for k, v in env.items())
    command = " ".join(f'"{a}"' for a in job["args"])
    schedule = "0 15 * * 5" if job["weekly"] else f"0 */{job['interval_hours']} * * *"
    line = f"{schedule} {env_prefix + ' ' if env_prefix else ''}{command} {marker}"
    try:
        existing = [ln for ln in _read_crontab() if marker not in ln]
        _write_crontab(existing + [line])
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"Could not update crontab automatically ({exc}). "
              "Add this line with `crontab -e`:", file=sys.stderr)
        print(f"  {line}")
        return False
    print(f"Installed cron job {_label(job['name'])}.")
    return True


def _uninstall_linux(job: dict) -> None:
    marker = f"# {_label(job['name'])}"
    try:
        existing = _read_crontab()
        filtered = [ln for ln in existing if marker not in ln]
        if len(filtered) == len(existing):
            print(f"cron job not installed: {_label(job['name'])}")
            return
        _write_crontab(filtered)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"Could not update crontab automatically ({exc}). "
              f"Remove the line marked `{marker}` with `crontab -e`.", file=sys.stderr)
        return
    print(f"Uninstalled cron job {_label(job['name'])}.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install(cfg: ConnectorConfig, config_path: str | Path) -> bool:
    """Register the recurring sync (+ optional weekly verify) jobs."""
    env = _pinned_env()
    ok = True
    for job in _jobs(cfg, Path(config_path).resolve()):
        if sys.platform == "darwin":
            ok = _install_macos(job, env) and ok
        elif sys.platform == "win32":
            ok = _install_windows(job, env) and ok
        else:
            ok = _install_linux(job, env) and ok
    return ok


def uninstall(cfg: ConnectorConfig, config_path: str | Path) -> None:
    """Remove the recurring jobs for this connector."""
    for job in _jobs(cfg, Path(config_path).resolve()):
        if sys.platform == "darwin":
            _uninstall_macos(job)
        elif sys.platform == "win32":
            _uninstall_windows(job)
        else:
            _uninstall_linux(job)

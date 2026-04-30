"""Fast script logging helpers."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent


def action_log():
    p = _ROOT / "scripts" / "actions"
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
    from _action_logging import log_action_call, log_action_result  # noqa: E402

    return log_action_call, log_action_result


def _actions_log_path() -> Path:
    logs_dir = _ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "actions.log"


def log_action(script_name: str, argv: list[str]) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": "action_call",
        "script": script_name,
        "argv": argv,
    }
    with _actions_log_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")


def log_action_result(
    script_name: str,
    argv: list[str],
    success: bool,
    details: Any = "",
) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": "action_result",
        "script": script_name,
        "argv": argv,
        "success": bool(success),
        "details": details,
    }
    with _actions_log_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _observations_log_path() -> Path:
    logs_dir = _ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir / "observations.log"


def log_observation(script_name: str, argv: list[str], result: dict | None = None) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": "observation_call",
        "script": script_name,
        "argv": argv,
    }
    with _observations_log_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")


def log_observation_result(
    script_name: str,
    argv: list[str],
    success: bool,
    result: dict | None = None,
    details: str = "",
) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": "observation_result",
        "script": script_name,
        "argv": argv,
        "success": bool(success),
        "details": details,
    }
    with _observations_log_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")

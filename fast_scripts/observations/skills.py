#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _daemon_client import daemon_send
from _logging import log_observation, log_observation_result


def _usage() -> None:
    print("Usage:")
    print("  python fast_scripts/observations/skills.py levels")
    print("  python fast_scripts/observations/skills.py active")


def _print_levels(result: dict) -> None:
    skills = result.get("skills") or []
    if not skills:
        print("No allowed skills found.")
        return
    print("Skill levels:\n")
    print(f"{'Skill':24} {'Level':>8} {'XP':>14} {'To next':>12}")
    print("-" * 62)
    for s in skills:
        lvl = int(s.get("level") or 0)
        xp = int(s.get("xp") or 0)
        xtn = s.get("xpToNext")
        next_col = "—" if xtn is None else f"{int(xtn):,}"
        print(f"{str(s.get('name') or 'Unknown')[:24]:24} {lvl:>8} {xp:>14,} {next_col:>12}")


def _print_active(result: dict) -> None:
    activities = result.get("activities") or []
    print("Active training:")
    if not activities:
        print("(none detected)")
        return
    for a in activities:
        skill = a.get("skill") or "Unknown"
        detail = a.get("detail") or "active"
        print(f"- {skill} — {detail}")


def format_output(cmd: str, result: dict, argv: list[str] | None = None) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        if cmd == "levels":
            _print_levels(result)
        elif cmd == "active":
            _print_active(result)
    return buf.getvalue().rstrip("\n")


def main() -> int:
    if len(sys.argv) < 2:
        _usage()
        return 1
    cmd = sys.argv[1].strip().lower()
    if cmd not in {"levels", "active"}:
        _usage()
        return 1
    try:
        log_observation("skills", [cmd])
        resp = daemon_send({"op": "observation.call", "name": "skills", "args": [cmd]})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    result = resp.get("result") or {}
    out = format_output(cmd, result, [cmd])
    log_observation_result("skills", [cmd], True, result=result, details=out)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

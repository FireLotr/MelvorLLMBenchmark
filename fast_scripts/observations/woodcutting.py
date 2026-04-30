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
    print("  python fast_scripts/observations/woodcutting.py list")


def _print_list(data: dict) -> None:
    level = int(data.get("lvl") or 0)
    print(f"Woodcutting Level: {level}")
    print(f"Current Axe: {data.get('currentAxe') or 'Unknown'}")
    print(f"Tree Cut Limit: {int(data.get('limit') or 1)}")
    active = data.get("active") or []
    if active:
        print(f"Currently Cutting: {', '.join(active)}")
    else:
        print("Currently Cutting: none")
    print("\nTrees:")
    for t in data.get("trees") or []:
        status = "UNLOCKED" if t.get("unlocked") else "LOCKED"
        interval_ms = float(t.get("interval") or 0)
        interval = f"{(interval_ms / 1000):.2f}s" if interval_ms > 0 else "?"
        req = int(t.get("level") or 0)
        if t.get("unlocked"):
            print(f"- {t.get('name', 'Unknown')}: {status} (requires level {req}) | {int(t.get('xp') or 0)} XP | {interval}")
        else:
            remain = max(0, req - level)
            print(f"- {t.get('name', 'Unknown')}: {status} (unlocks at level {req}, {remain} level(s) to go) | {int(t.get('xp') or 0)} XP | {interval}")


def format_output(cmd: str, result: dict, argv: list[str] | None = None) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        if cmd == "list":
            _print_list(result)
    return buf.getvalue().rstrip("\n")


def main() -> int:
    if len(sys.argv) < 2:
        _usage()
        return 1
    cmd = sys.argv[1].strip().lower()
    if cmd != "list":
        _usage()
        return 1
    try:
        log_observation("woodcutting", [cmd])
        resp = daemon_send({"op": "observation.call", "name": "woodcutting", "args": [cmd]})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    out = format_output(cmd, resp.get("result") or {}, [cmd])
    log_observation_result("woodcutting", [cmd], True, result=resp.get("result") or {}, details=out)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

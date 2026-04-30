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
    print("  python fast_scripts/observations/cooking.py list")
    print("  python fast_scripts/observations/cooking.py gloves")


def _print_list(data: dict) -> None:
    print(f"Cooking Level: {int(data.get('level') or 0)}")
    sel = data.get("selectedRecipe")
    print(f"Selected recipe: {sel or 'none'}")
    if data.get("isCooking"):
        print(f"Currently cooking: yes — {sel}" if sel else "Currently cooking: yes — (unknown recipe)")
    else:
        print("Currently cooking: no")
    print("Recipes:")
    for r in data.get("rows") or []:
        state = "UNLOCKED" if r.get("unlocked") else "LOCKED"
        interval = r.get("interval")
        interval_txt = f"{(float(interval) / 1000):.2f}s" if isinstance(interval, (int, float)) and interval > 0 else "?"
        print(
            f"- {r.get('name', 'Unknown')} [{r.get('category', 'Unknown')}]: {state} | "
            f"level {int(r.get('level') or 0)} | {int(r.get('xp') or 0)} XP | {interval_txt}"
        )


def _print_gloves(data: dict) -> None:
    if not data.get("equipped"):
        print("Cooking Gloves: none equipped")
        return
    name = data.get("name") or "Cooking Gloves"
    if "cooking" not in str(name).lower():
        print(f"Cooking Gloves: not equipped (currently: {name})")
        return
    charges = data.get("charges")
    if isinstance(charges, (int, float)):
        print(f"Cooking Gloves: {name} | Charges: {int(charges):,}")
    else:
        print(f"Cooking Gloves: {name} | Charges: unknown")


def format_output(cmd: str, result: dict, argv: list[str] | None = None) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        if cmd == "list":
            _print_list(result)
        elif cmd == "gloves":
            _print_gloves(result)
    return buf.getvalue().rstrip("\n")


def main() -> int:
    if len(sys.argv) < 2:
        _usage()
        return 1
    cmd = sys.argv[1].strip().lower()
    if cmd not in {"list", "gloves"}:
        _usage()
        return 1
    try:
        log_observation("cooking", [cmd])
        resp = daemon_send({"op": "observation.call", "name": "cooking", "args": [cmd]})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    result = resp.get("result") or {}
    out = format_output(cmd, result, [cmd])
    log_observation_result("cooking", [cmd], True, result=result, details=out)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

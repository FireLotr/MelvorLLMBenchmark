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
    print("  python fast_scripts/observations/smithing.py list")
    print("  python fast_scripts/observations/smithing.py status")
    print("  python fast_scripts/observations/smithing.py gloves")


def _format_item_costs(costs: list) -> str:
    if not costs:
        return "needs: (unknown)"
    parts = []
    for c in costs:
        q = int(c.get("quantity", 0))
        name = (c.get("name") or "").strip() or (c.get("id") or "").strip() or "?"
        parts.append(f"{q}x {name}")
    return "needs: " + ", ".join(parts)


def _print_activity(data: dict) -> None:
    print(f"Smithing Level: {int(data.get('level') or 0)}")
    active = data.get("active")
    print(f"Active recipe: {active or 'none'}")
    if data.get("isSmithing"):
        if active:
            print(f"Currently smithing: yes - {active}")
        else:
            print("Currently smithing: yes - (unknown recipe)")
    else:
        print("Currently smithing: no")


def _print_list(data: dict) -> None:
    _print_activity(data)
    print("Recipes:")
    for r in data.get("rows") or []:
        state = "UNLOCKED" if r.get("unlocked") else "LOCKED"
        need = _format_item_costs(r.get("itemCosts") or [])
        print(
            f"- {r.get('name', 'Unknown')}: {state} | "
            f"level {int(r.get('level') or 0)} | {int(r.get('xp') or 0)} XP | {need}"
        )


def _print_gloves(data: dict) -> None:
    if not data.get("equipped"):
        print("Smithing Gloves: none equipped")
        return
    name = data.get("name") or "Unknown Gloves"
    if "smithing" not in name.lower():
        print(f"Smithing Gloves: not equipped (currently: {name})")
        return
    charges = data.get("charges")
    if isinstance(charges, (int, float)):
        print(f"Smithing Gloves: {name} | Charges: {int(charges):,}")
    else:
        print(f"Smithing Gloves: {name} | Charges: unknown")


def format_output(cmd: str, data: dict, argv: list[str] | None = None) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        if cmd == "gloves":
            _print_gloves(data)
        elif cmd == "status":
            _print_activity(data)
        elif cmd == "list":
            _print_list(data)
    return buf.getvalue().rstrip("\n")


def main() -> int:
    if len(sys.argv) < 2:
        _usage()
        return 1
    cmd = sys.argv[1].strip().lower()
    if cmd not in {"list", "status", "gloves"}:
        _usage()
        return 1
    try:
        log_observation("smithing", [cmd])
        resp = daemon_send({"op": "observation.call", "name": "smithing", "args": [cmd]})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    data = resp.get("result") or {}
    out = format_output(cmd, data, [cmd])
    log_observation_result("smithing", [cmd], True, result=data, details=out)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

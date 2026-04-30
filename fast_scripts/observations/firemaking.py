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
    print("  python fast_scripts/observations/firemaking.py list")


def _fmt_pct(value) -> str | None:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:g}"


def _print_list(data: dict) -> None:
    print(f"Firemaking Level: {int(data.get('level') or 0)}")
    print(f"Active log (selected): {data.get('active') or 'none'}")
    if data.get("isBurning"):
        name = data.get("active")
        extra = f" — {name}" if name else ""
        print(f"Currently burning: yes{extra}")
    else:
        print("Currently burning: no")

    bl = data.get("bonfireLit")
    blog = data.get("bonfireBonusLog")
    bpct = data.get("bonfireBonusPercent")
    ps = _fmt_pct(bpct)
    if bl is True:
        if blog and ps is not None:
            print(f"Bonfire lit: yes — {blog}, +{ps}% skill XP")
        elif blog:
            print(f"Bonfire lit: yes — {blog}")
        elif ps is not None:
            print(f"Bonfire lit: yes — +{ps}% skill XP")
        else:
            print("Bonfire lit: yes")
    elif bl is False:
        print("Bonfire lit: no")
    else:
        print("Bonfire lit: unknown")

    print("Logs:")
    for r in data.get("rows") or []:
        state = "UNLOCKED" if r.get("unlocked") else "LOCKED"
        interval_ms = float(r.get("interval") or 0)
        interval = f"{(interval_ms / 1000):.2f}s" if interval_ms > 0 else "?"
        print(
            f"- {r.get('name', 'Unknown')}: {state} | "
            f"level {int(r.get('level') or 0)} | {int(r.get('xp') or 0)} XP | {interval}"
        )


def format_output(cmd: str, data: dict, argv: list[str] | None = None) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        if cmd == "list":
            _print_list(data)
    return buf.getvalue().rstrip("\n")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1].strip().lower() != "list":
        _usage()
        return 1
    try:
        log_observation("firemaking", ["list"])
        resp = daemon_send({"op": "observation.call", "name": "firemaking", "args": ["list"]})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    data = resp.get("result") or {}
    out = format_output("list", data, ["list"])
    log_observation_result("firemaking", ["list"], True, result=data, details=out)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

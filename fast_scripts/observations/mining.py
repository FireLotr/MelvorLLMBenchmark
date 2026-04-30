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
    print("  python fast_scripts/observations/mining.py list")
    print("  python fast_scripts/observations/mining.py gloves")


def _print_list(data: dict) -> None:
    print(f"Mining Level: {int(data.get('level') or 0)}")
    print(f"Current Pickaxe: {data.get('currentPickaxe') or 'Unknown'}")
    print(f"Active Rock: {data.get('active') or 'none'}")
    print("Rocks:")
    for r in data.get("rows") or []:
        state = "UNLOCKED" if r.get("unlocked") else "LOCKED"
        mine_sec = float(r.get("mineSec") or 0)
        mine_time = f"{mine_sec:.2f}s" if mine_sec > 0 else "?"
        respawn_ms = int(r.get("respawnMs") or 0)
        respawn = f"{(respawn_ms / 1000):.2f}s" if respawn_ms > 0 else "?"
        print(
            f"- {r.get('name', 'Unknown')}: {state} | level {int(r.get('level') or 0)} | "
            f"{int(r.get('xp') or 0)} XP | mine {mine_time} | respawn {respawn} | rock HP {int(r.get('rockHP') or 0)}"
        )


def _print_gloves(data: dict) -> None:
    if not data.get("equipped"):
        print("Mining Gloves: none equipped")
        return
    name = data.get("name") or "Mining Gloves"
    lower_name = str(name).lower()
    if "mining" not in lower_name and "gem gloves" not in lower_name:
        print(f"Mining Gloves: not equipped (currently: {name})")
        return
    charges = data.get("charges")
    if isinstance(charges, (int, float)):
        print(f"Mining Gloves: {name} | Charges: {int(charges):,}")
    else:
        print(f"Mining Gloves: {name} | Charges: unknown")


def format_output(cmd: str, data: dict, argv: list[str] | None = None) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        if cmd == "list":
            _print_list(data)
        elif cmd == "gloves":
            _print_gloves(data)
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
        log_observation("mining", [cmd])
        resp = daemon_send({"op": "observation.call", "name": "mining", "args": [cmd]})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    data = resp.get("result") or {}
    out = format_output(cmd, data, [cmd])
    log_observation_result("mining", [cmd], True, result=data, details=out)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

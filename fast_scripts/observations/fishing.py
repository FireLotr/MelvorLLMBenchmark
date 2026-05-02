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
    print("  python fast_scripts/observations/fishing.py list")
    print("  python fast_scripts/observations/fishing.py summary")


def _print_top(data: dict) -> None:
    print(f"Fishing Level: {int(data.get('level') or 0)}")
    print(f"Current Rod: {data.get('currentRod') or 'Unknown'}")
    if data.get("isFishing"):
        area = data.get("fishingArea") or "unknown area"
        fish = data.get("fishingFish")
        if fish:
            print(f"Currently fishing: yes — {fish} @ {area}")
        else:
            print(f"Currently fishing: yes — {area} (fish name unknown)")
    else:
        print("Currently fishing: no")
    selected = data.get("selected") or []
    if selected:
        print("Selected Fish by Area:")
        for row in selected:
            print(f"- {row.get('area', 'Unknown Area')}: {row.get('fish', 'Unknown Fish')}")
    else:
        print("Selected Fish by Area: none")


def _fmt_pct_triplet(d: dict | None) -> str:
    if not isinstance(d, dict):
        return "?/?/?"

    def fmt_one(x: object) -> str:
        if x is None:
            return "?"
        try:
            xf = float(x)
        except (TypeError, ValueError):
            return "?"
        if xf == int(xf):
            return str(int(xf))
        s = f"{xf:.2f}".rstrip("0").rstrip(".")
        return s or "0"

    return f"{fmt_one(d.get('fish'))}/{fmt_one(d.get('junk'))}/{fmt_one(d.get('special'))}"


def _print_list(data: dict) -> None:
    _print_top(data)
    print(
        "\nCatch odds are fish/junk/special (%). "
        "Area line = base from the area; each fish tail = after mastery/modifiers for that fish."
    )
    print("\nAreas and Fish:")
    for area in data.get("areas") or []:
        fish_rows = area.get("fish") or []
        area_base: dict | None = None
        for f in fish_rows:
            cc = f.get("catchChances")
            if isinstance(cc, dict) and isinstance(cc.get("areaBase"), dict):
                area_base = cc["areaBase"]
                break
        base_s = _fmt_pct_triplet(area_base) if area_base else "?/?/?"
        aname = area.get("name", "Unknown Area")
        print(f"\n{aname} (Area base: {base_s}):")
        for fish in fish_rows:
            status = "UNLOCKED" if fish.get("unlocked") else "LOCKED"
            min_ms = fish.get("minMs")
            max_ms = fish.get("maxMs")
            min_s = f"{float(min_ms) / 1000:.2f}s" if isinstance(min_ms, (int, float)) else "?"
            max_s = f"{float(max_ms) / 1000:.2f}s" if isinstance(max_ms, (int, float)) else "?"
            cc = fish.get("catchChances")
            if isinstance(cc, dict) and cc.get("error"):
                trip = "?/?/?"
            elif isinstance(cc, dict) and "fish" in cc:
                trip = _fmt_pct_triplet(
                    {"fish": cc.get("fish"), "junk": cc.get("junk"), "special": cc.get("special")}
                )
            else:
                trip = "?/?/?"
            print(
                f"- {fish.get('name', 'Unknown Fish')}: {status} | "
                f"level {int(fish.get('level') or 0)} | {int(fish.get('xp') or 0)} XP | {min_s} - {max_s} | {trip}"
            )


def format_output(cmd: str, data: dict, argv: list[str] | None = None) -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        if cmd == "summary":
            _print_top(data)
        elif cmd == "list":
            _print_list(data)
    return buf.getvalue().rstrip("\n")


def main() -> int:
    if len(sys.argv) < 2:
        _usage()
        return 1
    cmd = sys.argv[1].strip().lower()
    if cmd not in {"list", "summary"}:
        _usage()
        return 1
    try:
        log_observation("fishing", [cmd])
        resp = daemon_send({"op": "observation.call", "name": "fishing", "args": [cmd]})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    data = resp.get("result") or {}
    out = format_output(cmd, data, [cmd])
    log_observation_result("fishing", [cmd], True, result=data, details=out)
    if out:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

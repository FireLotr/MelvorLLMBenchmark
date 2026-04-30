#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _daemon_client import daemon_send


def _usage() -> None:
    print("Usage:")
    print("  python fast_scripts/observations/farming.py plots")


def _print_plots(result: dict) -> None:
    level = int(result.get("level") or 0)
    resources = result.get("resources") or {}
    compost_qty = int(resources.get("compost") or 0)
    gloop_qty = int(resources.get("weirdGloop") or 0)
    print(f"Farming Level: {level}")
    print(f"Inventory - Compost: {compost_qty} | Weird Gloop: {gloop_qty}")
    cats = result.get("categories") or []
    for cat in cats:
        name = cat.get("name", "Unknown")
        plots = cat.get("plots") or []
        if not plots:
            print(f"\n{name}: (not available)")
            continue
        print(f"\n{name} ({len(plots)} plots):")
        for p in plots:
            if p.get("locked"):
                unlock_str = " [can unlock]" if p.get("can_unlock") else ""
                print(f"  Plot {p.get('index')}: LOCKED — requires {p.get('requirements', '?')}{unlock_str}")
            else:
                compost_name = str(p.get("compost", "none"))
                compost_level = int(p.get("compostLevel") or 0)
                compost_level = max(0, min(100, compost_level))
                compost_str = f"compost: {compost_name} ({compost_level}%)"
                interval_ms = int(p.get("intervalMs") or 0)
                interval_str = f"{(interval_ms / 3600000):.1f}h" if interval_ms > 0 else "?"
                xp = int(p.get("xp") or 0)
                xp_str = f"{xp} XP" if xp > 0 else "? XP"
                state = str(p.get("state") or "unknown")
                if state == "empty":
                    print(
                        f"  Plot {p.get('index')}: empty            | {compost_str} | "
                        f"selected seed: {p.get('selected_seed', '?')} | {xp_str} | {interval_str}"
                    )
                elif state.startswith("growing"):
                    print(
                        f"  Plot {p.get('index')}: {state:<24} | {compost_str} | "
                        f"{p.get('planted', '?')} | {xp_str} | {interval_str}"
                    )
                elif state == "ready":
                    print(f"  Plot {p.get('index')}: READY TO HARVEST  | {p.get('planted', '?')} | {xp_str} | {interval_str}")
                elif state == "dead":
                    print(f"  Plot {p.get('index')}: DEAD (clear it)   | {p.get('planted', '?')} | {xp_str} | {interval_str}")
                else:
                    print(f"  Plot {p.get('index')}: {state}")
    print()


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1].strip().lower() != "plots":
        _usage()
        return 1
    try:
        resp = daemon_send({"op": "observation.call", "name": "farming", "args": ["plots"]})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    _print_plots(resp.get("result") or {})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

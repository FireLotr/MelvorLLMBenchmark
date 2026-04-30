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


SKILL_ALIASES = {
    "fishing": "fishing",
    "mining": "mining",
    "woodcutting": "woodcutting",
    "firemaking": "firemaking",
    "cooking": "cooking",
    "smithing": "smithing",
    "farming": "farming",
}


def _usage() -> None:
    print("Usage:")
    print("  python fast_scripts/observations/mastery.py list <skill>")
    print("  python fast_scripts/observations/mastery.py pool <skill>")
    print("  python fast_scripts/observations/mastery.py unlocks <skill> [action]")
    print("Commands: list, pool, unlocks")
    print(f"Skills: {', '.join(sorted(SKILL_ALIASES.keys()))}")


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _resolve_skill(skill: str) -> str | None:
    return SKILL_ALIASES.get(_norm(skill))


def _print_list(data: dict) -> None:
    print(f"Skill: {data.get('skillName', 'Unknown')} ({data.get('realmName', 'Unknown Realm')})")
    print(f"Pool: {float(data.get('poolXP') or 0):.2f}/{float(data.get('poolCap') or 0):.2f} ({float(data.get('poolProgress') or 0) * 100:.2f}%)")
    print("Pool Checkpoints:")
    pool_bonuses = data.get("poolBonuses") or []
    if not pool_bonuses:
        print("- none")
    else:
        for cp in pool_bonuses:
            status = "ACTIVE" if cp.get("active") else "inactive"
            print(f"- {float(cp.get('percent') or 0):.0f}%: {status} | {cp.get('effect', 'Unknown')}")
    print("Mastery Level Unlocks:")
    unlocks = data.get("unlocks") or []
    if not unlocks:
        print("- none")
    else:
        for u in unlocks:
            print(f"- L{int(u.get('level') or 0)}: {u.get('description', 'Unknown')}")
    print("Actions:")
    for a in data.get("actions") or []:
        state = "UNLOCKED" if a.get("unlocked") else "LOCKED"
        print(
            f"- {a.get('name', 'Unknown')}: {state} | req {int(a.get('levelReq') or 0)} | "
            f"mastery {int(a.get('masteryLevel') or 0)} ({float(a.get('toNextPercent') or 0):.2f}% to next)"
        )


def _print_pool(data: dict) -> None:
    print(f"Skill: {data.get('skillName', 'Unknown')} ({data.get('realmName', 'Unknown Realm')})")
    print(f"Mastery Pool: {float(data.get('poolXP') or 0):.2f}/{float(data.get('poolCap') or 0):.2f} ({float(data.get('poolProgress') or 0) * 100:.2f}%)")
    total = float(data.get("totalLevel") or 0)
    max_total = float(data.get("maxTotalLevel") or 0)
    pct = (total / max_total * 100.0) if max_total > 0 else 0.0
    print(f"Total Mastery: {int(total)}/{int(max_total)} ({pct:.2f}%)")


def _print_unlocks(data: dict, action_query: str) -> int:
    print(f"Skill: {data.get('skillName', 'Unknown')} ({data.get('realmName', 'Unknown Realm')})")
    actions = data.get("actions") or []
    unlocks = data.get("unlocks") or []
    target = None
    if action_query:
        q = _norm(action_query)
        exact = [a for a in actions if _norm(str(a.get("name") or "")) == q]
        if exact:
            target = exact[0]
        else:
            partial = [a for a in actions if q and q in _norm(str(a.get("name") or ""))]
            if len(partial) == 1:
                target = partial[0]
            elif len(partial) > 1:
                print(f"Ambiguous action '{action_query}'. Matches: {', '.join(str(a.get('name')) for a in partial[:20])}")
                return 1
            else:
                print(f"Unknown action: '{action_query}'")
                return 1
    if target:
        mastery_level = int(target.get("masteryLevel") or 0)
        print(f"Action: {target.get('name', 'Unknown')} | Mastery {mastery_level} ({float(target.get('toNextPercent') or 0):.2f}% to next)")
        next_unlock = [u for u in unlocks if int(u.get("level") or 0) > mastery_level]
        if next_unlock:
            n = next_unlock[0]
            print(f"Next unlock at {int(n.get('level') or 0)}: {n.get('description', 'Unknown')}")
        else:
            print("Next unlock: none (max unlocks reached)")
    print("Mastery Level Unlocks:")
    if not unlocks:
        print("- none")
    else:
        for u in unlocks:
            print(f"- L{int(u.get('level') or 0)}: {u.get('description', 'Unknown')}")
    return 0


def format_output(cmd: str, data: dict, argv: list[str] | None = None) -> tuple[str, int]:
    buf = StringIO()
    rc = 0
    query = " ".join((argv or [])[2:]).strip()
    with redirect_stdout(buf):
        if cmd == "list":
            _print_list(data)
        elif cmd == "pool":
            _print_pool(data)
        elif cmd == "unlocks":
            rc = _print_unlocks(data, query)
    return buf.getvalue().rstrip("\n"), rc


def main() -> int:
    if len(sys.argv) < 3:
        _usage()
        return 1
    cmd = _norm(sys.argv[1])
    skill_raw = _norm(sys.argv[2])
    skill = _resolve_skill(skill_raw)
    if cmd not in {"list", "pool", "unlocks"}:
        print(f"Unknown command: '{sys.argv[1]}'")
        _usage()
        return 1
    if not skill:
        print(f"Unknown skill: '{sys.argv[2]}'")
        _usage()
        return 1
    args = [cmd, skill]
    if cmd == "unlocks" and len(sys.argv) > 3:
        args.extend(sys.argv[3:])
    log_observation("mastery", args)
    try:
        resp = daemon_send({"op": "observation.call", "name": "mastery", "args": args})
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2
    if not resp.get("ok"):
        print(json.dumps(resp, indent=2, ensure_ascii=True))
        return 1
    data = resp.get("result") or {}
    if not data.get("ok", True):
        print(data.get("error") or "Failed to read mastery state.")
        return 1
    out, rc = format_output(cmd, data, args)
    log_observation_result("mastery", args, rc == 0, result=data, details=out)
    if out:
        print(out)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

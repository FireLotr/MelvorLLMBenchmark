#!/usr/bin/env python3
"""Check benchmark goal progress via daemon observations (skills levels + dungeon completion)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _daemon_client import daemon_send
from _logging import log_observation, log_observation_result

_ROOT = Path(__file__).resolve().parent.parent.parent


def _norm(s: object) -> str:
    return str(s or "").strip().lower()


def _load_lists() -> tuple[list[str], list[str]] | tuple[None, None]:
    """Load skills and dungeon names from lists.json (repo root)."""
    try:
        data = json.loads((_ROOT / "lists.json").read_text(encoding="utf-8"))
    except Exception:
        return None, None
    sk = data.get("skills")
    dg = data.get("dungeons")
    if not isinstance(sk, list) or not isinstance(dg, list):
        return None, None
    skills = [str(s).strip() for s in sk if str(s).strip()]
    dungeons = [str(d).strip() for d in dg if str(d).strip()]
    return skills, dungeons


@dataclass(frozen=True)
class GoalSpec:
    name: str
    skill_min: int
    dungeon_exclusions: frozenset[str]  # normalized dungeon names to skip (not required)


def _spec_easy() -> GoalSpec:
    return GoalSpec(
        name="easy",
        skill_min=60,
        dungeon_exclusions=frozenset({_norm("Volcanic Cave")}),
    )


def _spec_medium() -> GoalSpec:
    return GoalSpec(name="medium", skill_min=80, dungeon_exclusions=frozenset())


def _fetch_account_age() -> str | None:
    resp = daemon_send({"op": "read", "kind": "account_age"})
    if not resp.get("ok"):
        return None
    data = resp.get("result") or {}
    if not data.get("ok", True):
        return None
    s = str(data.get("accountAge") or "").strip()
    return s or None


def _print_account_age_header() -> None:
    try:
        age = _fetch_account_age()
    except Exception:
        age = None
    if age:
        print(f"Account age: {age}")
    else:
        print("Account age: (unavailable)")
    print()


def _fetch_skills() -> dict:
    resp = daemon_send({"op": "observation.call", "name": "skills", "args": ["levels"]})
    if not resp.get("ok"):
        raise RuntimeError(json.dumps(resp, indent=2, ensure_ascii=True))
    data = resp.get("result") or {}
    if not data.get("ok", True):
        raise RuntimeError(json.dumps(data, indent=2, ensure_ascii=True))
    return data


def _fetch_dungeon_rows() -> list[dict]:
    resp = daemon_send({"op": "observation.call", "name": "combat", "args": ["dungeon_completion"]})
    if not resp.get("ok"):
        raise RuntimeError(json.dumps(resp, indent=2, ensure_ascii=True))
    data = resp.get("result") or {}
    if not data.get("ok", True):
        raise RuntimeError(json.dumps(data, indent=2, ensure_ascii=True))
    return list(data.get("rows") or [])


def _skill_levels_by_name(fetch: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in fetch.get("skills") or []:
        nm = _norm(s.get("name"))
        if not nm:
            continue
        out[nm] = int(s.get("level") or 0)
    return out


def _completions_by_name(rows: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        nm = _norm(r.get("name"))
        if not nm:
            continue
        out[nm] = max(out.get(nm, 0), int(r.get("completions") or 0))
    return out


def _evaluate_goal(
    spec: GoalSpec,
    *,
    list_skills: list[str],
    list_dungeons: list[str],
    levels: dict[str, int],
    completions: dict[str, int],
) -> tuple[bool, list[str], list[str], list[str], list[str]]:
    """Returns (complete, skills_done, skills_todo, dungs_done, dungs_todo) lines without headers."""
    skill_done: list[str] = []
    skill_todo: list[str] = []
    for name in list_skills:
        key = _norm(name)
        lvl = levels.get(key, 0)
        label = f"{name}: {lvl}/{spec.skill_min}"
        if lvl >= spec.skill_min:
            skill_done.append(label)
        else:
            skill_todo.append(label)

    req_dungeons = [d for d in list_dungeons if _norm(d) not in spec.dungeon_exclusions]
    d_done: list[str] = []
    d_todo: list[str] = []
    for name in req_dungeons:
        key = _norm(name)
        c = int(completions.get(key, 0))
        label = f"{name}: {c} completion(s) (need >=1)"
        if c >= 1:
            d_done.append(label)
        else:
            d_todo.append(label)

    complete = not skill_todo and not d_todo
    return complete, skill_done, skill_todo, d_done, d_todo


def _print_goal_block(spec: GoalSpec, result: tuple[bool, list[str], list[str], list[str], list[str]]) -> None:
    complete, sk_done, sk_todo, dg_done, dg_todo = result
    status = "COMPLETE" if complete else "in progress"
    print(f"=== Goal: {spec.name} ({status}) ===")
    print("Skills:")
    print("  Done:")
    for line in sk_done:
        print(f"    [x] {line}")
    if not sk_done:
        print("    (none yet)")
    print("  Still need level %s:" % spec.skill_min)
    for line in sk_todo:
        print(f"    [-] {line}")
    if not sk_todo:
        print("    (all met)")
    print()
    print("Dungeons:")
    print("  Done (>=1 clear):")
    for line in dg_done:
        print(f"    [x] {line}")
    if not dg_done:
        print("    (none yet)")
    print("  Still need a clear:")
    for line in dg_todo:
        print(f"    [-] {line}")
    if not dg_todo:
        print("    (all met)")
    print()


def _usage() -> None:
    print("Usage:")
    print("  python fast_scripts/observations/goals.py [easy|medium|all]")
    print()
    print("  easy   - all skills in lists.json >=60; each lists.json dungeon >=1 clear except Volcanic Cave")
    print("  medium - all skills in lists.json >=80; each lists.json dungeon >=1 clear")
    print("  all    - report both (default)")


def main() -> int:
    argv = [a.strip().lower() for a in sys.argv[1:] if a.strip()]
    which = argv[0] if argv else "all"
    if which in {"-h", "--help", "help"}:
        _usage()
        return 0

    _print_account_age_header()

    if which not in {"easy", "medium", "all"}:
        _usage()
        return 1

    list_skills, list_dungeons = _load_lists()
    if not list_skills or not list_dungeons:
        print("Could not read skills/dungeons from lists.json at repo root.", file=sys.stderr)
        return 1

    specs: list[GoalSpec]
    if which == "easy":
        specs = [_spec_easy()]
    elif which == "medium":
        specs = [_spec_medium()]
    else:
        specs = [_spec_easy(), _spec_medium()]

    log_observation("goals", [which])
    try:
        skills_payload = _fetch_skills()
        rows = _fetch_dungeon_rows()
    except Exception as e:
        msg = str(e)
        if "Connection refused" in msg or "timed out" in msg.lower():
            print(f"FAST_DAEMON_REQUIRED: {e}")
            return 2
        print(msg, file=sys.stderr)
        return 1

    levels = _skill_levels_by_name(skills_payload)
    completions = _completions_by_name(rows)

    all_complete = True
    summary_lines: list[str] = []
    for spec in specs:
        result = _evaluate_goal(spec, list_skills=list_skills, list_dungeons=list_dungeons, levels=levels, completions=completions)
        complete = result[0]
        all_complete = all_complete and complete
        _print_goal_block(spec, result)
        summary_lines.append(f"{spec.name}: {'COMPLETE' if complete else 'in progress'}")

    print("-- Summary:", "; ".join(summary_lines))
    details = "\n".join(summary_lines)
    log_observation_result("goals", [which], True, result={"summary": summary_lines}, details=details)
    return 0 if all_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())

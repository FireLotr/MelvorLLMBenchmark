#!/usr/bin/env python3
"""Shared daemon-only CLI wrappers for fast actions/observations."""

from __future__ import annotations

import json
import sys

from _daemon_client import daemon_send
from _logging import log_action, log_action_result

_ACTION_USAGE: dict[str, list[str]] = {
    "bank": [
        "sell <item> <qty>",
        "sellmulti <item1> <qty1> [<item2> <qty2> ...]",
        "equip <item>",
        "unequip <slot>",
        "equipfood <item> [qty]",
        "upgrade <item> [qty]",
        "open <item> [qty]",
        "claim <item> [qty]",
    ],
    "shop": [
        "buy <name> <qty>",
    ],
    "mining": [
        "start <rock>",
        "stop",
    ],
    "combat": [
        "list",
        "loot",
        "stop",
        "style <stab|slash|block>",
        "food slot <1|2|3>",
        "unequip food [slot]",
        "<target monster or dungeon name>",
    ],
    "fishing": ["start <fish>", "stop"],
    "woodcutting": ["start <tree[,tree2]>", "stop"],
    "cooking": ["start <recipe>", "stop"],
    "smithing": ["start <recipe>", "stop"],
    "firemaking": ["select <log>", "start <log>", "stop", "bonfire <start|stop> [log]"],
    "farming": [
        "harvest-all-game [allotment|herb|tree] (2k GP)",
        "compost-all-game <compost|weird-gloop> [allotment|herb|tree] (2k GP)",
        "plant-all-game <seed_name> [allotment|herb|tree] (5k GP)",
        "plant-all-selected-game [allotment|herb|tree] (5k GP)",
        "plant <seed_name> [plot] [allotment|herb|tree]",
        "select-seed <seed_name> [plot] [allotment|herb|tree]",
        "harvest [plot] [allotment|herb|tree]",
        "compost [plot] [allotment|herb|tree]",
        "weird-gloop [plot] [allotment|herb|tree]",
        "clear [plot] [allotment|herb|tree]",
        "unlock <plot> [allotment|herb|tree]",
    ],
    "mastery": ["claim <skill>", "spend <skill> <action> <levels>"],
    "navigate": ["<page-key>"],
}

_OBS_USAGE: dict[str, list[str]] = {
    "bank": ["items", "space", "info <item>"],
    "shop": ["list", "money", "currency"],
    "skills": ["levels", "active"],
    "mining": ["list", "gloves"],
    "fishing": ["list"],
    "woodcutting": ["trees"],
    "cooking": ["list", "gloves"],
    "smithing": ["list", "status", "gloves"],
    "firemaking": ["list"],
    "farming": ["plots"],
    "equipment": ["all", "equipped"],
    "combat": ["style", "hp", "autoeat", "stats", "enemy", "drops ...", "dungeon_completion"],
    "goals": ["easy", "medium", "all"],
    "mastery": ["list <skill>", "pool <skill>", "unlocks <skill> [query]"],
}

_HELP_FLAGS = {"-h", "--help", "help"}


def _print_resp(resp: dict) -> None:
    print(json.dumps(resp, indent=2, ensure_ascii=True))


def _print_usage(kind: str, name: str) -> None:
    table = _ACTION_USAGE if kind == "action" else _OBS_USAGE
    cmds = table.get(name, [])
    title = f"fast_scripts/{kind}s/{name}.py"
    if not cmds:
        print(f"{title} (no local usage map)")
        return
    print(title)
    print("Available commands:")
    for cmd in cmds:
        print(f"  - {cmd}")


def _send_or_die(req: dict, timeout_s: float = 30.0) -> int:
    try:
        resp = daemon_send(req, timeout_s=timeout_s)
    except Exception as e:
        print(f"FAST_DAEMON_REQUIRED: {e}")
        return 2

    _print_resp(resp)
    return 0 if resp.get("ok") else 1


def run_action_cli(action_name: str, argv: list[str]) -> int:
    if not argv or argv[0].strip().lower() in _HELP_FLAGS:
        _print_usage("action", action_name)
        return 0
    log_action(action_name, argv)
    try:
        resp = daemon_send({"op": "action.call", "name": action_name, "args": argv})
    except Exception as e:
        msg = f"FAST_DAEMON_REQUIRED: {e}"
        print(msg)
        log_action_result(action_name, argv, False, {"error": msg})
        return 2

    _print_resp(resp)
    log_action_result(action_name, argv, bool(resp.get("ok")), resp)
    return 0 if resp.get("ok") else 1


def run_observation_cli(observation_name: str, argv: list[str]) -> int:
    if not argv or argv[0].strip().lower() in _HELP_FLAGS:
        _print_usage("observation", observation_name)
        return 0
    return _send_or_die(
        {"op": "observation.call", "name": observation_name, "args": argv}
    )


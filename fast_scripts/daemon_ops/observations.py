from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Page

from _melvor_read_ops import MASTERY_BRIEF_JS, READ_JS, list_read_kinds
from js_observations.bank import BANK_INFO_JS, BANK_ITEMS_JS
from js_observations.combat import (
    COMBAT_AUTOEAT_READ_JS,
    COMBAT_CURRENT_LOOT_JS,
    COMBAT_FOOD_SLOT_READ_JS,
    COMBAT_DROPS_JS,
    COMBAT_DUNGEON_COMPLETION_JS,
    COMBAT_ENEMY_READ_JS,
    COMBAT_STATS_READ_JS,
    COMBAT_STYLE_READ_JS,
)
from js_observations.cooking import COOKING_GLOVES_JS, COOKING_LIST_JS
from js_observations.equipment import EQUIPMENT_READ_JS
from js_observations.farming import FARMING_PLOTS_JS
from js_observations.firemaking import FIREMAKING_LIST_JS
from js_observations.fishing import FISHING_LIST_JS
from js_observations.mastery import MASTERY_STATE_JS, MASTERY_UNLOCKS_JS
from js_observations.mining import MINING_GLOVES_JS, MINING_LIST_JS
from js_observations.shop import SHOP_LIST_JS
from js_observations.smithing import SMITHING_GLOVES_JS, SMITHING_STATE_JS
from js_observations.skills import SKILLS_ACTIVE_JS, SKILLS_LEVELS_JS
from js_observations.woodcutting import WOODCUTTING_LIST_JS
from daemon_ops.errors import unsupported


def _load_allowed_skills(root) -> set[str] | None:
    try:
        cfg_path = root.parent / "lists.json"
        parsed = json.loads(cfg_path.read_text(encoding="utf-8"))
        skills = parsed.get("skills")
        if not isinstance(skills, list):
            return None
        return {str(s).strip().lower() for s in skills if str(s).strip()}
    except Exception:
        return None


def handle_read(page: Page, req: dict[str, Any]) -> dict[str, Any]:
    kind = str(req.get("kind") or "").lower().strip()
    if not kind:
        return {"ok": False, "error": "read requires {kind: ...}", "kinds": list_read_kinds()}
    if kind == "mastery":
        sk = str(req.get("skill") or "fishing")
        result = page.evaluate(MASTERY_BRIEF_JS, sk)
        rdict = result if isinstance(result, dict) else {}
        return {"ok": bool(rdict.get("ok", True)), "result": result}
    js = READ_JS.get(kind)
    if not js:
        return {"ok": False, "error": f"unknown read kind: {kind!r}", "kinds": list_read_kinds()}
    result = page.evaluate(js)
    rdict = result if isinstance(result, dict) else {}
    okv = rdict.get("ok")
    ok = okv is not False
    if okv is None and isinstance(result, dict) and "error" in rdict:
        ok = False
    return {"ok": ok, "result": result}


def handle_observation_call(root, page: Page, name: str, args: list[str]) -> dict[str, Any]:
    n = (name or "").strip().lower()
    cmd = (args[0].strip().lower() if args else "")
    try:
        if n == "skills":
            if cmd == "levels":
                data = page.evaluate(SKILLS_LEVELS_JS)
                allowed = _load_allowed_skills(root)
                if allowed:
                    data["skills"] = [s for s in (data.get("skills") or []) if str(s.get("name") or "").strip().lower() in allowed]
                return {"ok": True, "result": data}
            if cmd == "active":
                data = page.evaluate(SKILLS_ACTIVE_JS)
                allowed = _load_allowed_skills(root)
                if allowed:
                    acts = data.get("activities") or []
                    data["activities"] = [
                        a for a in acts
                        if str(a.get("skill") or "").strip().lower() == "combat"
                        or str(a.get("skill") or "").strip().lower() in allowed
                    ]
                return {"ok": True, "result": data}
            return {"ok": False, "error": "skills usage: levels|active"}
        if n == "shop":
            if cmd in {"list", "show", "category"}:
                return {"ok": True, "result": page.evaluate(SHOP_LIST_JS)}
            if cmd == "currency":
                return {"ok": True, "result": page.evaluate(READ_JS["shop"])}
            return {"ok": False, "error": "shop usage: list|category|currency"}
        if n == "mining":
            if cmd == "list":
                return {"ok": True, "result": page.evaluate(MINING_LIST_JS)}
            if cmd == "gloves":
                return {"ok": True, "result": page.evaluate(MINING_GLOVES_JS)}
            return {"ok": False, "error": "mining usage: list|gloves"}
        if n == "fishing":
            if cmd == "list":
                return {"ok": True, "result": page.evaluate(FISHING_LIST_JS)}
            if cmd == "summary":
                return {"ok": True, "result": page.evaluate(FISHING_LIST_JS)}
            return {"ok": False, "error": "fishing usage: list|summary"}
        if n == "woodcutting":
            if cmd == "list":
                return {"ok": True, "result": page.evaluate(WOODCUTTING_LIST_JS)}
            return {"ok": False, "error": "woodcutting usage: list"}
        if n == "cooking":
            if cmd == "list":
                return {"ok": True, "result": page.evaluate(COOKING_LIST_JS)}
            if cmd == "gloves":
                return {"ok": True, "result": page.evaluate(COOKING_GLOVES_JS)}
            return {"ok": False, "error": "cooking usage: list|gloves"}
        if n == "smithing":
            if cmd in {"list", "status"}:
                return {"ok": True, "result": page.evaluate(SMITHING_STATE_JS)}
            if cmd == "gloves":
                return {"ok": True, "result": page.evaluate(SMITHING_GLOVES_JS)}
            return {"ok": False, "error": "smithing usage: list|status|gloves"}
        if n == "firemaking":
            if cmd == "list":
                return {"ok": True, "result": page.evaluate(FIREMAKING_LIST_JS)}
            return {"ok": False, "error": "firemaking usage: list"}
        if n == "farming":
            if cmd == "plots":
                return {"ok": True, "result": page.evaluate(FARMING_PLOTS_JS)}
            return {"ok": False, "error": "farming usage: plots"}
        if n == "bank":
            if cmd == "space":
                return {"ok": True, "result": page.evaluate(READ_JS["bank_space"])}
            if cmd == "items":
                data = page.evaluate(BANK_ITEMS_JS)
                return {"ok": bool((data or {}).get("ok", True)), "result": data}
            if cmd == "info":
                if len(args) < 2:
                    return {"ok": False, "error": "bank info requires item name"}
                q = " ".join(args[1:]).strip().lower()
                data = page.evaluate(BANK_INFO_JS, q)
                return {"ok": bool((data or {}).get("ok", True)), "result": data}
            return {"ok": False, "error": "bank usage: items|space|info <item>"}
        if n == "equipment":
            if cmd in {"all", "equipped"}:
                return {"ok": True, "result": page.evaluate(EQUIPMENT_READ_JS)}
            return {"ok": False, "error": "equipment usage: all|equipped"}
        if n == "combat":
            if cmd == "hp":
                return {"ok": True, "result": page.evaluate(READ_JS["combat"])}
            if cmd == "style":
                return {"ok": True, "result": page.evaluate(COMBAT_STYLE_READ_JS)}
            if cmd == "autoeat":
                return {"ok": True, "result": page.evaluate(COMBAT_AUTOEAT_READ_JS)}
            if cmd == "food_slot":
                return {"ok": True, "result": page.evaluate(COMBAT_FOOD_SLOT_READ_JS)}
            if cmd == "stats":
                return {"ok": True, "result": page.evaluate(COMBAT_STATS_READ_JS)}
            if cmd == "enemy":
                return {"ok": True, "result": page.evaluate(COMBAT_ENEMY_READ_JS)}
            if cmd == "current_loot":
                return {"ok": True, "result": page.evaluate(COMBAT_CURRENT_LOOT_JS)}
            if cmd == "full_status":
                return {
                    "ok": True,
                    "result": {
                        "style": page.evaluate(COMBAT_STYLE_READ_JS),
                        "hp": page.evaluate(READ_JS["combat"]),
                        "autoeat": page.evaluate(COMBAT_AUTOEAT_READ_JS),
                        "food_slot": page.evaluate(COMBAT_FOOD_SLOT_READ_JS),
                        "stats": page.evaluate(COMBAT_STATS_READ_JS),
                        "enemy": page.evaluate(COMBAT_ENEMY_READ_JS),
                        "current_loot": page.evaluate(COMBAT_CURRENT_LOOT_JS),
                    },
                }
            if cmd == "dungeon_completion":
                return {"ok": True, "result": page.evaluate(COMBAT_DUNGEON_COMPLETION_JS)}
            if cmd == "drops":
                if len(args) < 2:
                    return {"ok": False, "error": "drops usage: drops all|monster <name>|dungeon <name>"}
                mode = args[1].strip().lower()
                query = " ".join(args[2:]).strip().lower() if len(args) > 2 else ""
                data = page.evaluate(COMBAT_DROPS_JS, {"mode": mode, "query": query})
                return {"ok": bool((data or {}).get("ok", True)), "result": data}
            return {"ok": False, "error": "combat usage: style|hp|autoeat|food_slot|stats|enemy|current_loot|full_status|drops|dungeon_completion"}
        if n == "mastery":
            if len(args) < 2:
                return {"ok": False, "error": "mastery usage: list|pool|unlocks <skill> [action]"}
            sub = args[0].strip().lower()
            if sub in {"list", "pool"}:
                result = page.evaluate(MASTERY_STATE_JS, args[1])
                return {"ok": bool((result or {}).get("ok", True)), "result": result}
            if sub == "unlocks":
                result = page.evaluate(MASTERY_STATE_JS, args[1])
                return {"ok": bool((result or {}).get("ok", True)), "result": result}
            return {"ok": False, "error": "mastery usage: list|pool|unlocks <skill> [action]"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return unsupported("observation", n, args)


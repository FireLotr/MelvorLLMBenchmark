#!/usr/bin/env python3
"""
observations/mastery.py - Read-only mastery state for a skill.

Usage:
  python scripts/observations/mastery.py list <skill>
  python scripts/observations/mastery.py pool <skill>
  python scripts/observations/mastery.py unlocks <skill> [<action name>]

Examples:
  python scripts/observations/mastery.py list fishing
  python scripts/observations/mastery.py pool mining
  python scripts/observations/mastery.py unlocks fishing "Raw Shrimp"
"""

import os
import sys
from playwright.sync_api import sync_playwright
from _observation_logging import log_observation, run_observation

os.environ.setdefault("NODE_NO_WARNINGS", "1")
CDP_URL = "http://localhost:9222"

SKILL_ALIASES = {
    "fishing": "fishing",
    "mining": "mining",
    "woodcutting": "woodcutting",
    "firemaking": "firemaking",
    "cooking": "cooking",
    "smithing": "smithing",
    "farming": "farming",
}


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "melvor" in pg.url.lower():
                return pg
    return browser.contexts[0].pages[0]


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _resolve_skill(skill: str) -> str | None:
    key = _norm(skill)
    return SKILL_ALIASES.get(key)


def _base_state(page, skill_key: str):
    return page.evaluate(
        """(skillKey) => {
            const s = game?.[skillKey];
            if (!s) return { ok: false, error: `Unknown/unsupported skill: ${skillKey}` };

            const realm = s?.currentRealm ?? null;
            const realmName = realm?.name ?? "Unknown Realm";
            const poolXP = Number(s?.getMasteryPoolXP?.(realm) ?? 0);
            const poolCap = Number(s?.getMasteryPoolCap?.(realm) ?? 0);
            const poolProgress = Number(s?.getMasteryPoolProgress?.(realm) ?? 0);
            const totalLevel = Number(s?.getTotalCurrentMasteryLevelInRealm?.(realm) ?? 0);
            const maxTotalLevel = Number(s?.getTrueMaxTotalMasteryLevelInRealm?.(realm) ?? 0);

            const poolBonuses = Array.from((s?.masteryPoolBonuses ?? new Map()).entries())
                .filter(([r]) => !realm || r === realm)
                .flatMap(([r, arr]) => (arr ?? []).map((b) => {
                    const percent = Number(b?.percent ?? 0);
                    const active = poolProgress >= (percent / 100);
                    let effect = "Unknown";
                    try {
                        const m = b?.modifiers?.[0];
                        const p = m?.print?.();
                        if (p && typeof p === "object" && p.text) effect = String(p.text);
                    } catch (e) {}
                    return { percent, active, effect };
                }))
                .sort((a, b) => a.percent - b.percent);

            const unlocks = (s?.masteryLevelUnlocks ?? [])
                .map((u) => ({
                    level: Number(u?.level ?? 0),
                    description: String(u?._description ?? u?.description ?? "Unknown"),
                }))
                .sort((a, b) => a.level - b.level);

            const actions = (s?.actions?.allObjects ?? []).map((a) => {
                const progress = s?.getMasteryProgress?.(a);
                let unlocked = false;
                try { unlocked = !!s?.isMasteryActionUnlocked?.(a); } catch (e) {}
                const rawPercent = Number(progress?.percent ?? 0);
                const toNextPercent = rawPercent <= 1 ? rawPercent * 100 : rawPercent;
                return {
                    name: a?.name ?? "Unknown",
                    levelReq: Number(a?.level ?? 0),
                    masteryLevel: Number(s?.getMasteryLevel?.(a) ?? 0),
                    masteryXP: Number(s?.getMasteryXP?.(a) ?? 0),
                    toNextPercent,
                    unlocked,
                };
            });

            return {
                ok: true,
                skillName: s?.name ?? skillKey,
                realmName,
                poolXP,
                poolCap,
                poolProgress,
                totalLevel,
                maxTotalLevel,
                poolBonuses,
                unlocks,
                actions,
            };
        }""",
        skill_key,
    )


def show_pool(page, skill_key: str) -> bool:
    data = _base_state(page, skill_key)
    if not data.get("ok"):
        print(data.get("error", "Failed to read mastery state."))
        return False

    print(f"Skill: {data['skillName']} ({data['realmName']})")
    print(
        f"Mastery Pool: {data['poolXP']:.2f}/{data['poolCap']:.2f} "
        f"({data['poolProgress'] * 100:.2f}%)"
    )
    pct_total = (data["totalLevel"] / data["maxTotalLevel"] * 100) if data["maxTotalLevel"] else 0
    print(f"Total Mastery: {int(data['totalLevel'])}/{int(data['maxTotalLevel'])} ({pct_total:.2f}%)")
    print("Pool Checkpoints:")
    if not data["poolBonuses"]:
        print("- none")
    else:
        for cp in data["poolBonuses"]:
            status = "ACTIVE" if cp["active"] else "inactive"
            print(f"- {cp['percent']:.0f}%: {status} | {cp['effect']}")
    return True


def show_unlocks(page, skill_key: str, action_query: str = "") -> bool:
    data = _base_state(page, skill_key)
    if not data.get("ok"):
        print(data.get("error", "Failed to read mastery state."))
        return False

    print(f"Skill: {data['skillName']} ({data['realmName']})")
    target = None
    if action_query:
        q = _norm(action_query)
        exact = [a for a in data["actions"] if _norm(a["name"]) == q]
        if exact:
            target = exact[0]
        else:
            partial = [a for a in data["actions"] if q and q in _norm(a["name"])]
            if len(partial) == 1:
                target = partial[0]
            elif len(partial) > 1:
                print(f"Ambiguous action '{action_query}'. Matches: {', '.join(a['name'] for a in partial[:20])}")
                return False
            else:
                print(f"Unknown action: '{action_query}'")
                return False

    if target:
        print(
            f"Action: {target['name']} | Mastery {int(target['masteryLevel'])} "
            f"({target['toNextPercent']:.2f}% to next)"
        )
        next_unlock = [u for u in data["unlocks"] if u["level"] > target["masteryLevel"]]
        if next_unlock:
            n = next_unlock[0]
            print(f"Next unlock at {int(n['level'])}: {n['description']}")
        else:
            print("Next unlock: none (max unlocks reached)")

    print("Mastery Level Unlocks:")
    if not data["unlocks"]:
        print("- none")
    else:
        for u in data["unlocks"]:
            print(f"- L{int(u['level'])}: {u['description']}")
    return True


def show_list(page, skill_key: str) -> bool:
    data = _base_state(page, skill_key)
    if not data.get("ok"):
        print(data.get("error", "Failed to read mastery state."))
        return False

    print(f"Skill: {data['skillName']} ({data['realmName']})")
    print(
        f"Pool: {data['poolXP']:.2f}/{data['poolCap']:.2f} "
        f"({data['poolProgress'] * 100:.2f}%)"
    )
    print("Actions:")
    for a in data["actions"]:
        state = "UNLOCKED" if a["unlocked"] else "LOCKED"
        print(
            f"- {a['name']}: {state} | req {int(a['levelReq'])} | "
            f"mastery {int(a['masteryLevel'])} ({a['toNextPercent']:.2f}% to next)"
        )
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        log_observation("mastery.py", sys.argv[1:], False, "Missing required arguments.")
        print(__doc__)
        sys.exit(1)

    cmd = _norm(sys.argv[1])
    skill_key = _resolve_skill(sys.argv[2])
    if not skill_key:
        log_observation("mastery.py", sys.argv[1:], False, f"Unknown skill: {sys.argv[2]}")
        print(f"Unknown skill: '{sys.argv[2]}'")
        print(f"Supported skills: {', '.join(sorted(SKILL_ALIASES.keys()))}")
        sys.exit(1)

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if cmd == "list":
            ok, out = run_observation(show_list, page, skill_key)
            log_observation("mastery.py", sys.argv[1:], ok, out)
            sys.exit(0 if ok else 1)
        if cmd == "pool":
            ok, out = run_observation(show_pool, page, skill_key)
            log_observation("mastery.py", sys.argv[1:], ok, out)
            sys.exit(0 if ok else 1)
        if cmd == "unlocks":
            query = " ".join(sys.argv[3:]).strip() if len(sys.argv) > 3 else ""
            ok, out = run_observation(show_unlocks, page, skill_key, query)
            log_observation("mastery.py", sys.argv[1:], ok, out)
            sys.exit(0 if ok else 1)

        log_observation("mastery.py", sys.argv[1:], False, f"Unknown command: {cmd}")
        print(f"Unknown command: '{cmd}'")
        print(__doc__)
        sys.exit(1)

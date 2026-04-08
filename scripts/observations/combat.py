#!/usr/bin/env python3
"""
combat.py — Read-only combat observations.

Usage:
  python scripts/observations/combat.py style
  python scripts/observations/combat.py hp
  python scripts/observations/combat.py autoeat
  python scripts/observations/combat.py stats
  python scripts/observations/combat.py enemy
  python scripts/observations/combat.py drops all
  python scripts/observations/combat.py drops monster "<monster name>"
  python scripts/observations/combat.py drops dungeon "<dungeon name>"
  python scripts/observations/combat.py dungeon_completion
  python scripts/observations/combat.py dungeon_completion json
"""

import sys
import os
import json
import random
import time

os.environ.setdefault("NODE_NO_WARNINGS", "1")
from playwright.sync_api import sync_playwright
from _observation_logging import log_observation, run_observation

CDP_URL = "http://localhost:9222"


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for page in ctx.pages:
            if "melvor" in page.url.lower():
                return page
    return None


def ensure_game_ready(page) -> bool:
    try:
        page.wait_for_function("() => typeof game !== 'undefined' && !!game.combat?.player", timeout=10000)
        return True
    except Exception:
        return False


def show_style() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False

        style_name = page.evaluate(
            """() => {
                const player = game?.combat?.player;
                if (!player) return null;
                if (player.attackType === 'melee') {
                    return player.attackStyles?.melee?.name ?? null;
                }
                if (player.attackType === 'ranged') {
                    return player.attackStyles?.ranged?.name ?? null;
                }
                if (player.attackType === 'magic') {
                    return player.attackStyles?.magic?.name ?? null;
                }
                return null;
            }"""
        )
        if not style_name:
            print("Could not determine active combat style.")
            return False
        active = str(style_name)

    print(f"Active combat style: {active}")
    return True


def show_hp() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False

        data = page.evaluate(
            """() => {
                const p = game?.combat?.player;
                return {
                    hp: Number(p?.hitpoints ?? 0),
                    maxHp: Number(p?.stats?._maxHitpoints ?? p?.stats?.maxHitpoints ?? 0),
                };
            }"""
        )

    print(f"HP: {int(data['hp'])}/{int(data['maxHp'])}")
    return True


def show_autoeat() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False

        data = page.evaluate(
            """() => {
                const shop = game.shop;
                const t1 = shop.purchases.getObjectByID('melvorD:Auto_Eat_Tier_I');
                const t2 = shop.purchases.getObjectByID('melvorD:Auto_Eat_Tier_II');
                const t3 = shop.purchases.getObjectByID('melvorD:Auto_Eat_Tier_III');
                return {
                    tier1: !!(t1 && shop.isUpgradePurchased(t1)),
                    tier2: !!(t2 && shop.isUpgradePurchased(t2)),
                    tier3: !!(t3 && shop.isUpgradePurchased(t3)),
                    hp: Number(game.combat?.player?.hitpoints ?? 0),
                    maxHp: Number(game.combat?.player?.stats?._maxHitpoints ?? 0),
                    triggerHp: Number(game.combat?.player?.autoEatThreshold ?? 0),
                    healTargetHp: Number(game.combat?.player?.autoEatHPLimit ?? 0),
                    efficiencyPct: Number(game.combat?.player?.autoEatEfficiency ?? 0),
                    activeFoodSlot: (() => {
                        const p = game?.combat?.player;
                        const f = p?.food;
                        const asSlotNum = (v) => {
                            const n = Number(v);
                            if (Number.isFinite(n) && n >= 0 && n < 3) return n + 1;
                            if (Number.isFinite(n) && n >= 1 && n <= 3) return n;
                            return null;
                        };
                        for (const v of [f?.selectedSlot, f?.currentSlot, f?.activeSlot]) {
                            const s = asSlotNum(v);
                            if (s) return s;
                        }
                        const sid = String(p?.selectedFood?.slot?.id ?? p?.selectedFood?.slotID ?? "");
                        const m = sid.match(/(\\d+)/);
                        if (m) {
                            const n = Number(m[1]);
                            if (Number.isFinite(n) && n >= 1 && n <= 3) return n;
                        }
                        return null;
                    })(),
                };
            }"""
        )

    tier = 0
    if data["tier3"]:
        tier = 3
    elif data["tier2"]:
        tier = 2
    elif data["tier1"]:
        tier = 1

    # Auto-eat tier behavior constants from game rules.
    tier_info = {
        0: ("Disabled", None, None, "N/A"),
        1: ("Tier I", 0.20, 0.40, "60%"),
        2: ("Tier II", 0.35, 0.70, "80%"),
        3: ("Tier III", 0.40, 0.80, "100%"),
    }
    name, _trigger_ratio, _target_ratio, _efficiency = tier_info[tier]
    max_hp = int(data.get("maxHp", 0))
    hp = int(data.get("hp", 0))
    trigger_hp = int(data.get("triggerHp", 0))
    target_hp = int(data.get("healTargetHp", 0))
    efficiency = f"{int(data.get('efficiencyPct', 0))}%"

    print(f"Auto Eat: {name}")
    if tier == 0 or max_hp <= 0:
        print("Trigger HP: N/A")
        print("Heal Target: N/A")
    else:
        trigger_pct = (trigger_hp / max_hp * 100) if max_hp > 0 else 0
        target_pct = (target_hp / max_hp * 100) if max_hp > 0 else 0
        print(f"Trigger HP: <= {trigger_hp}/{max_hp} ({trigger_pct:.0f}%)")
        print(f"Heal Target: to {target_hp}/{max_hp} ({target_pct:.0f}%)")
    print(f"Current HP: {hp}/{max_hp}")
    print(f"Food Efficiency: {efficiency}")
    active_slot = data.get("activeFoodSlot")
    if isinstance(active_slot, (int, float)) and 1 <= int(active_slot) <= 3:
        print(f"Active Food Slot: {int(active_slot)}")
    else:
        print("Active Food Slot: unknown")
    return True


def show_stats() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False

        data = page.evaluate(
            """() => {
                const p = game?.combat?.player;
                const s = p?.stats;
                const attackType = p?.attackType ?? 'unknown';
                let style = null;
                if (attackType === 'melee') style = p?.attackStyles?.melee?.name ?? null;
                else if (attackType === 'ranged') style = p?.attackStyles?.ranged?.name ?? null;
                else if (attackType === 'magic') style = p?.attackStyles?.magic?.name ?? null;

                let dr = null;
                const res = s?._resistances;
                if (res instanceof Map) {
                    const normal = Array.from(res.entries()).find(([k]) => k?.id === 'melvorD:Normal');
                    dr = normal ? Number(normal[1]) : null;
                }

                return {
                    attackType,
                    style,
                    minHit: Number(s?._minHit ?? 0),
                    maxHit: Number(s?._maxHit ?? 0),
                    accuracy: Number(s?._accuracy ?? 0),
                    hitChance: Number(s?._hitChance ?? 0),
                    attackInterval: Number(s?._attackInterval ?? 0),
                    evasionMelee: Number(s?._evasion?.melee ?? 0),
                    evasionRanged: Number(s?._evasion?.ranged ?? 0),
                    evasionMagic: Number(s?._evasion?.magic ?? 0),
                    damageReduction: dr,
                    hp: Number(p?.hitpoints ?? 0),
                    maxHp: Number(s?._maxHitpoints ?? 0),
                    activeFoodSlot: (() => {
                        const f = p?.food;
                        const asSlotNum = (v) => {
                            const n = Number(v);
                            if (Number.isFinite(n) && n >= 0 && n < 3) return n + 1;
                            if (Number.isFinite(n) && n >= 1 && n <= 3) return n;
                            return null;
                        };
                        for (const v of [f?.selectedSlot, f?.currentSlot, f?.activeSlot]) {
                            const s2 = asSlotNum(v);
                            if (s2) return s2;
                        }
                        const sid = String(p?.selectedFood?.slot?.id ?? p?.selectedFood?.slotID ?? "");
                        const m = sid.match(/(\\d+)/);
                        if (m) {
                            const n = Number(m[1]);
                            if (Number.isFinite(n) && n >= 1 && n <= 3) return n;
                        }
                        return null;
                    })(),
                };
            }"""
        )

    print(f"Attack Type: {data['attackType']}")
    print(f"Attack Style: {data['style']}")
    print(f"HP: {int(data['hp'])}/{int(data['maxHp'])}")
    print(f"Min Hit: {int(data['minHit'])}")
    print(f"Max Hit: {int(data['maxHit'])}")
    print(f"Hit Chance: {data['hitChance']:.2f}%")
    print(f"Accuracy: {int(data['accuracy'])}")
    print(f"Attack Interval: {int(data['attackInterval'])} ms")
    print(
        f"Evasion (M/R/M): {int(data['evasionMelee'])} / "
        f"{int(data['evasionRanged'])} / {int(data['evasionMagic'])}"
    )
    if data["damageReduction"] is None:
        print("Damage Reduction: N/A")
    else:
        print(f"Damage Reduction: {float(data['damageReduction']):.2f}%")
    active_slot = data.get("activeFoodSlot")
    if isinstance(active_slot, (int, float)) and 1 <= int(active_slot) <= 3:
        print(f"Active Food Slot: {int(active_slot)}")
    else:
        print("Active Food Slot: unknown")
    return True


def show_enemy_stats() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False

        in_combat = page.evaluate("() => !!game?.combat?.isActive")
        if not in_combat:
            print("Not currently in combat.")
            return False

        data = None
        for _ in range(6):
            data = page.evaluate(
                """() => {
                    const c = game?.combat;
                    const e = c?.enemy;
                    const s = e?.stats;
                    return {
                        inCombat: !!c?.isActive,
                        name: e?.monster?.name ?? null,
                        hp: Number(e?.hitpoints ?? 0),
                        maxHp: Number(s?._maxHitpoints ?? 0),
                        minHit: Number(s?._minHit ?? 0),
                        maxHit: Number(s?._maxHit ?? 0),
                        accuracy: Number(s?._accuracy ?? 0),
                        hitChance: Number(s?._hitChance ?? 0),
                        attackInterval: Number(s?._attackInterval ?? 0),
                        evasionMelee: Number(s?._evasion?.melee ?? 0),
                        evasionRanged: Number(s?._evasion?.ranged ?? 0),
                        evasionMagic: Number(s?._evasion?.magic ?? 0),
                        attackType: e?.attackType ?? null,
                        damageType: e?.damageType?.name ?? e?.damageType?.id ?? null,
                    };
                }"""
            )

            if data["inCombat"] and data["name"] and data["maxHp"] > 0 and data["hp"] > 0:
                break
            time.sleep(random.uniform(0.35, 1.20))

        if not data or not data["inCombat"] or not data["name"] or data["maxHp"] <= 0:
            print("Could not read enemy stats (enemy may be between spawns).")
            return False

    print(f"Enemy: {data['name']}")
    print(f"HP: {int(data['hp'])}/{int(data['maxHp'])}")
    print(f"Attack Type: {data['attackType']}")
    print(f"Damage Type: {data['damageType']}")
    print(f"Min Hit: {int(data['minHit'])}")
    print(f"Max Hit: {int(data['maxHit'])}")
    print(f"Hit Chance: {data['hitChance']:.2f}%")
    print(f"Accuracy: {int(data['accuracy'])}")
    print(f"Attack Interval: {int(data['attackInterval'])} ms")
    print(
        f"Evasion (M/R/M): {int(data['evasionMelee'])} / "
        f"{int(data['evasionRanged'])} / {int(data['evasionMagic'])}"
    )
    return True


def show_dungeon_completion(json_mode: bool = False) -> bool:
    """Read dungeon clear counts from game.combat.player.manager.dungeonCompletion (no UI clicks)."""
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False

        payload = page.evaluate(
            """() => {
                const mgr = game?.combat?.player?.manager;
                if (!mgr) {
                    return { ok: false, error: "combat.player.manager missing", dungeons: [] };
                }
                const dc = mgr.dungeonCompletion;
                const byId = Object.create(null);

                const record = (key, val) => {
                    const n = Number(val);
                    if (!Number.isFinite(n) || n < 0) return;
                    if (key && typeof key === "object" && key.id) {
                        byId[key.id] = Math.max(byId[key.id] ?? 0, n);
                    } else if (typeof key === "string" && key.length) {
                        byId[key] = Math.max(byId[key] ?? 0, n);
                    }
                };

                if (dc instanceof Map) {
                    for (const [k, v] of dc.entries()) {
                        record(k, v);
                    }
                } else if (dc && typeof dc === "object") {
                    for (const [k, v] of Object.entries(dc)) {
                        record(k, v);
                    }
                }

                const resolveCount = (d) => {
                    if (dc instanceof Map && dc.has(d)) {
                        const v = dc.get(d);
                        const n = Number(v);
                        if (Number.isFinite(n)) return n;
                    }
                    if (d?.id && byId[d.id] != null) return Number(byId[d.id]);
                    if (typeof mgr.getDungeonCompleteCount === "function") {
                        try {
                            const n = Number(mgr.getDungeonCompleteCount(d));
                            if (Number.isFinite(n)) return n;
                        } catch (e) {}
                    }
                    return 0;
                };

                const rows = [];
                for (const d of game?.dungeons?.allObjects ?? []) {
                    rows.push({
                        id: d?.id ?? "",
                        name: d?.name ?? "Unknown",
                        completions: resolveCount(d),
                    });
                }
                rows.sort((a, b) => String(a.name).localeCompare(String(b.name)));
                return { ok: true, error: null, dungeons: rows };
            }"""
        )

    if not payload.get("ok"):
        err = payload.get("error") or "unknown error"
        print(f"Could not read dungeon completions: {err}")
        return False

    rows = payload.get("dungeons") or []
    if json_mode:
        print(json.dumps(rows, ensure_ascii=False))
        return True

    print("Dungeon completion counts (clears):")
    for r in rows:
        name = r.get("name", "?")
        n = int(r.get("completions", 0))
        print(f"  {name}: {n}")
    print(f"Total: {len(rows)} dungeon(s) in game data.")
    return True


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def _fmt_qty(min_qty, max_qty) -> str:
    if min_qty is None and max_qty is None:
        return "?"
    if min_qty == max_qty:
        return str(min_qty)
    return f"{min_qty}-{max_qty}"


def _print_monster_drops(mon: dict) -> None:
    print(f"Monster: {mon['name']}")
    if mon.get("drops"):
        print("Possible Drops:")
        for d in mon["drops"]:
            qty = _fmt_qty(d.get("min"), d.get("max"))
            src = d.get("source", "drop")
            print(f"- {d.get('name', 'Unknown')} x{qty} [{src}]")
    else:
        print("Possible Drops: none")
    print()


def _print_dungeon_drops(dun: dict) -> None:
    print(f"Dungeon: {dun['name']}")
    if dun.get("drops"):
        print("Possible Drops:")
        for d in dun["drops"]:
            qty = _fmt_qty(d.get("min"), d.get("max"))
            src = d.get("source", "reward")
            print(f"- {d.get('name', 'Unknown')} x{qty} [{src}]")
    else:
        print("Possible Drops: none")
    print()


def show_drops(mode: str, name: str = "") -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False

        data = page.evaluate(
            """() => {
                const toNum = (v) => (typeof v === 'number' ? Number(v) : null);
                const monsters = (game?.monsters?.allObjects ?? []).map((m) => {
                    const drops = [];
                    const loot = m?.lootTable?.sortedDropsArray ?? [];
                    for (const entry of loot) {
                        drops.push({
                            name: entry?.item?.name ?? 'Unknown',
                            min: toNum(entry?.minQuantity),
                            max: toNum(entry?.maxQuantity),
                            source: 'lootTable',
                        });
                    }
                    if (m?.bones?.item) {
                        const qty = toNum(m?.bones?.quantity);
                        drops.push({
                            name: m.bones.item.name ?? 'Bones',
                            min: qty,
                            max: qty,
                            source: 'bones',
                        });
                    }
                    for (const c of (m?.currencyDrops ?? [])) {
                        drops.push({
                            name: c?.currency?.name ?? 'Currency',
                            min: toNum(c?.min),
                            max: toNum(c?.max),
                            source: 'currency',
                        });
                    }
                    return {
                        id: m?.id ?? '',
                        name: m?.name ?? 'Unknown Monster',
                        drops,
                    };
                });

                const dungeons = (game?.dungeons?.allObjects ?? []).map((d) => {
                    const drops = [];

                    for (const reward of (d?.rewards ?? [])) {
                        if (!reward) continue;
                        const rewardName = reward?.name ?? 'Unknown Reward';
                        drops.push({
                            name: rewardName,
                            min: 1,
                            max: 1,
                            source: 'dungeonReward',
                        });

                        const dt = reward?.dropTable;
                        const rewardDrops = dt?.sortedDropsArray ?? [];
                        for (const entry of rewardDrops) {
                            drops.push({
                                name: entry?.item?.name ?? 'Unknown',
                                min: toNum(entry?.minQuantity),
                                max: toNum(entry?.maxQuantity),
                                source: `from ${rewardName}`,
                            });
                        }
                    }

                    return {
                        id: d?.id ?? '',
                        name: d?.name ?? 'Unknown Dungeon',
                        drops,
                    };
                });

                return { monsters, dungeons };
            }"""
        )

    monsters = data.get("monsters", [])
    dungeons = data.get("dungeons", [])
    mode = _norm(mode)
    query = _norm(name)

    if mode == "all":
        print("=== Monster Drops ===")
        for mon in sorted(monsters, key=lambda m: m.get("name", "")):
            _print_monster_drops(mon)
        print("=== Dungeon Drops ===")
        for dun in sorted(dungeons, key=lambda d: d.get("name", "")):
            _print_dungeon_drops(dun)
        return True

    if mode == "monster":
        exact = [m for m in monsters if _norm(m.get("name", "")) == query]
        matches = exact if exact else [m for m in monsters if query and query in _norm(m.get("name", ""))]
        if not matches:
            print(f"No monster found matching: {name}")
            return False
        if len(matches) > 1:
            print(f"Multiple monsters matched '{name}':")
            for m in matches[:15]:
                print(f"- {m.get('name')}")
            if len(matches) > 15:
                print(f"... and {len(matches) - 15} more")
            return False
        _print_monster_drops(matches[0])
        return True

    if mode == "dungeon":
        exact = [d for d in dungeons if _norm(d.get("name", "")) == query]
        matches = exact if exact else [d for d in dungeons if query and query in _norm(d.get("name", ""))]
        if not matches:
            print(f"No dungeon found matching: {name}")
            return False
        if len(matches) > 1:
            print(f"Multiple dungeons matched '{name}':")
            for d in matches[:15]:
                print(f"- {d.get('name')}")
            if len(matches) > 15:
                print(f"... and {len(matches) - 15} more")
            return False
        _print_dungeon_drops(matches[0])
        return True

    print("Unknown drops mode. Use: drops all | drops monster <name> | drops dungeon <name>")
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log_observation("combat.py", sys.argv[1:], False, "Missing command.")
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower().strip()
    if cmd == "style":
        ok, out = run_observation(show_style)
        log_observation("combat.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    elif cmd == "hp":
        ok, out = run_observation(show_hp)
        log_observation("combat.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    elif cmd == "autoeat":
        ok, out = run_observation(show_autoeat)
        log_observation("combat.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    elif cmd == "stats":
        ok, out = run_observation(show_stats)
        log_observation("combat.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    elif cmd == "enemy":
        ok, out = run_observation(show_enemy_stats)
        log_observation("combat.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    elif cmd == "dungeon_completion":
        json_mode = len(sys.argv) > 2 and sys.argv[2].lower().strip() == "json"
        ok, out = run_observation(show_dungeon_completion, json_mode)
        log_observation("combat.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    elif cmd == "drops":
        if len(sys.argv) < 3:
            log_observation("combat.py", sys.argv[1:], False, "Drops missing mode argument.")
            print("Usage: combat.py drops all | drops monster <name> | drops dungeon <name>")
            sys.exit(1)
        mode = sys.argv[2].lower().strip()
        if mode == "all":
            ok, out = run_observation(show_drops, "all")
            log_observation("combat.py", sys.argv[1:], ok, out)
            sys.exit(0 if ok else 1)
        if mode in ("monster", "dungeon"):
            if len(sys.argv) < 4:
                log_observation("combat.py", sys.argv[1:], False, f"Drops mode '{mode}' missing name.")
                print(f"Usage: combat.py drops {mode} <name>")
                sys.exit(1)
            arg_name = " ".join(sys.argv[3:]).strip()
            ok, out = run_observation(show_drops, mode, arg_name)
            log_observation("combat.py", sys.argv[1:], ok, out)
            sys.exit(0 if ok else 1)
        log_observation("combat.py", sys.argv[1:], False, f"Unknown drops mode: {mode}")
        print("Usage: combat.py drops all | drops monster <name> | drops dungeon <name>")
        sys.exit(1)
    else:
        log_observation("combat.py", sys.argv[1:], False, f"Unknown command: {cmd}")
        print(
            f"Unknown command: '{cmd}'. Use 'style', 'hp', 'autoeat', 'stats', "
            "'enemy', 'dungeon_completion', or 'drops'."
        )
        sys.exit(1)

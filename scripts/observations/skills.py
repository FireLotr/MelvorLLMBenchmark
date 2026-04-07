#!/usr/bin/env python3
"""
skills.py — Read-only skill observations.

Usage:
  python scripts/observations/skills.py levels   # list allowed skill levels, XP, XP to next level
  python scripts/observations/skills.py active   # what is training now (game state only; Fishing shows fish @ area)
"""

import sys
import os
import json
from pathlib import Path

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
        page.wait_for_function("() => typeof game !== 'undefined' && !!game.skills", timeout=10000)
        return True
    except Exception:
        return False


def load_allowed_skills() -> set[str] | None:
    cfg_path = Path(__file__).resolve().parents[2] / "lists.json"
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        skills = data.get("skills")
        if not isinstance(skills, list):
            return None
        return {str(s).strip().lower() for s in skills if str(s).strip()}
    except Exception:
        return None


def show_levels() -> bool:
    allowed = load_allowed_skills()
    if not allowed:
        print("Could not read allowed skills from lists.json")
        return False

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
                // Melvor uses the standard OSRS cumulative XP curve (same as in-game thresholds).
                const cumulativeXpForLevel = (level) => {
                    const L = Math.floor(Number(level) || 0);
                    if (L <= 1) return 0;
                    let points = 0;
                    for (let lv = 1; lv < L; lv++) {
                        points += Math.floor(lv + 300 * Math.pow(2, lv / 7));
                    }
                    return Math.floor(points / 4);
                };

                const skillsSource =
                    game.skills instanceof Map
                        ? Array.from(game.skills.values())
                        : (game.skills?.allObjects ?? game.skills ?? []);

                const skills = skillsSource.map((s) => {
                    const level = Math.floor(Number(s?.level ?? 0));
                    const cap = Math.floor(Number(s?._currentLevelCap ?? 99));
                    const curXp = Number(s?._xp ?? s?.xp ?? 0);
                    let xpToNext = null;
                    if (level >= cap) {
                        xpToNext = null;
                    } else {
                        const need = cumulativeXpForLevel(level + 1);
                        xpToNext = Math.max(0, Math.ceil(need - curXp - 1e-9));
                    }
                    return {
                        id: s?.id ?? "",
                        name: s?.name ?? "Unknown Skill",
                        level,
                        levelCap: cap,
                        xp: curXp,
                        xpToNext,
                    };
                });

                skills.sort((a, b) => a.name.localeCompare(b.name));
                return { ok: true, skills };
            }"""
        )

    if not data.get("ok"):
        print(data.get("error", "Failed to read skills."))
        return False

    skills = data["skills"]
    skills = [s for s in skills if s["name"].strip().lower() in allowed]
    if not skills:
        print("No allowed skills found.")
        return False

    print("Skill levels:\n")
    print(f"{'Skill':24} {'Level':>8} {'XP':>14} {'To next':>12}")
    print("-" * 62)
    for s in skills:
        lvl = int(s["level"])
        cap = int(s.get("levelCap") or 99)
        xtn = s.get("xpToNext")
        if lvl >= cap:
            next_col = "—"
        elif xtn is None:
            next_col = "?"
        else:
            next_col = f"{int(xtn):,}"
        print(f"{s['name'][:24]:24} {lvl:>8} {int(s['xp']):>14,} {next_col:>12}")
    return True


def show_active() -> bool:
    allowed = load_allowed_skills()

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
                const activities = [];

                const fishingDetailFromGame = (g) => {
                    if (!g) return "active";
                    const area = g.activeFishingArea?.name ?? null;
                    let fish = null;
                    if (g.activeFishingArea && g.selectedAreaFish) {
                        try {
                            const hit = g.selectedAreaFish.get(g.activeFishingArea);
                            if (hit?.name) fish = hit.name;
                        } catch (e) {}
                    }
                    fish = fish || g.activeRecipe?.name || g.selectedFish?.name || null;
                    if (!fish && g.selectedAreaFish && area) {
                        for (const [a, fi] of g.selectedAreaFish.entries()) {
                            if ((a?.name ?? "") === area) {
                                fish = fi?.name ?? null;
                                break;
                            }
                        }
                    }
                    if (fish && area) return `${fish} @ ${area}`;
                    if (fish) return String(fish);
                    if (area) return String(area);
                    return "active";
                };

                const com = game?.combat;
                if (com?.isActive) {
                    const parts = [];
                    if (com.dungeon?.name) parts.push(String(com.dungeon.name));
                    const areaName =
                        com.player?.combatArea?.name ??
                        com.player?.slayerArea?.name ??
                        com.selectedArea?.name ??
                        null;
                    if (areaName) parts.push(String(areaName));
                    const mon =
                        com.enemy?.name ??
                        com.enemy?.monster?.name ??
                        com.selectedMonster?.name ??
                        null;
                    let detail = "";
                    if (parts.length) detail = parts.join(" — ");
                    if (mon) detail = detail ? `${detail} — vs ${mon}` : `vs ${mon}`;
                    if (!detail) detail = "active";
                    activities.push({ skill: "Combat", detail });
                }

                const gameKeyByLocal = {
                    Woodcutting: "woodcutting",
                    Fishing: "fishing",
                    Firemaking: "firemaking",
                    Cooking: "cooking",
                    Mining: "mining",
                    Smithing: "smithing",
                    Thieving: "thieving",
                    Fletching: "fletching",
                    Crafting: "crafting",
                    Runecrafting: "runecrafting",
                    Herblore: "herblore",
                    Agility: "agility",
                    Summoning: "summoning",
                    Astrology: "astrology",
                    Magic: "magic",
                    Township: "township",
                };

                const skillsSource =
                    game.skills instanceof Map
                        ? Array.from(game.skills.values())
                        : (game.skills?.allObjects ?? []);

                for (const s of skillsSource) {
                    const lid = s?._localID;
                    if (!lid || s.isActive !== true) continue;
                    const gk = gameKeyByLocal[lid];
                    if (!gk) continue;
                    const g = game[gk];
                    let detail = "active";
                    try {
                        if (lid === "Woodcutting") {
                            const names = g?.activeTrees
                                ? Array.from(g.activeTrees)
                                      .map((t) => t?.name)
                                      .filter(Boolean)
                                : [];
                            if (names.length) detail = names.join(", ");
                        } else if (lid === "Fishing") {
                            detail = fishingDetailFromGame(g);
                        } else if (lid === "Firemaking" || lid === "Cooking" || lid === "Smithing") {
                            if (g?.activeRecipe?.name) detail = String(g.activeRecipe.name);
                        } else if (lid === "Mining") {
                            const rn = g?.activeProgressRock?.name ?? g?.selectedRock?.name ?? null;
                            if (rn) detail = String(rn);
                        } else if (lid === "Magic") {
                            if (game.altMagic?.isActive) {
                                detail = game.altMagic?.activeRecipe?.name
                                    ? String(game.altMagic.activeRecipe.name)
                                    : "Alt Magic";
                            } else if (g?.activeRecipe?.name) {
                                detail = String(g.activeRecipe.name);
                            }
                        } else if (g?.activeRecipe?.name) {
                            detail = String(g.activeRecipe.name);
                        }
                    } catch (e) {}
                    activities.push({ skill: lid, detail });
                }

                if (
                    game.altMagic?.isActive &&
                    !activities.some((a) => a.skill === "Magic" || a.skill === "Alt Magic")
                ) {
                    const d = game.altMagic?.activeRecipe?.name
                        ? String(game.altMagic.activeRecipe.name)
                        : "active";
                    activities.push({ skill: "Alt Magic", detail: d });
                }

                const gf = game?.fishing;
                if (
                    gf?.isActive &&
                    !activities.some((a) => a.skill === "Fishing")
                ) {
                    activities.push({
                        skill: "Fishing",
                        detail: fishingDetailFromGame(gf),
                    });
                }

                return { ok: true, activities };
            }"""
        )

    if not data.get("ok"):
        print(data.get("error", "Failed to read active training."))
        return False

    raw = data.get("activities") or []

    def _keep(a: dict) -> bool:
        sk = str(a.get("skill") or "")
        if sk.lower() == "combat":
            return True
        if not allowed:
            return True
        return sk.strip().lower() in allowed

    shown = [a for a in raw if _keep(a)]

    print("Active training:\n")
    if not raw:
        print("(none detected)")
        return True
    if not shown:
        print("(none match skills in lists.json — game reports activity outside that list)")
        for a in raw:
            print(f"- {a['skill']} — {a['detail']}")
        return True
    for a in shown:
        print(f"- {a['skill']} — {a['detail']}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log_observation("skills.py", sys.argv[1:], False, "Missing command.")
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower().strip()
    if cmd == "levels":
        ok, out = run_observation(show_levels)
        log_observation("skills.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    if cmd == "active":
        ok, out = run_observation(show_active)
        log_observation("skills.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    else:
        log_observation("skills.py", sys.argv[1:], False, f"Unknown command: {cmd}")
        print(f"Unknown command: '{cmd}'. Use 'levels' or 'active'.")
        sys.exit(1)

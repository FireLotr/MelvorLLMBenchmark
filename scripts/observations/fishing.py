#!/usr/bin/env python3
"""
observations/fishing.py - Read-only fishing state.

Usage:
  python scripts/observations/fishing.py list

Works from any page (navigates to Fishing internally if needed).
"""

import os
import sys
from playwright.sync_api import sync_playwright
from _navigate import navigate
from _observation_logging import log_observation, run_observation

os.environ.setdefault("NODE_NO_WARNINGS", "1")
CDP_URL = "http://localhost:9222"


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "melvor" in pg.url.lower():
                return pg
    return browser.contexts[0].pages[0]


def show_list() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not navigate("fishing", page=page, quiet=True):
            print("Could not navigate to Fishing.")
            return False
        page.wait_for_timeout(200)
        data = page.evaluate(
            """() => {
                const f = game?.fishing;
                const level = Number(f?.level ?? 0);
                const currentRod = (() => {
                    const displays = Array.from(document.querySelectorAll("upgrade-chain-display"));
                    for (const d of displays) {
                        const text = (d.textContent || "").replace(/\\s+/g, " ").trim();
                        const m = text.match(/^Current Rod\\s+(.+)$/i);
                        if (m) return m[1].trim();
                    }
                    return null;
                })();
                const selected = f?.selectedAreaFish
                  ? Array.from(f.selectedAreaFish.entries()).map(([area, fish]) => ({
                      area: area?.name ?? "Unknown Area",
                      fish: fish?.name ?? "Unknown Fish",
                    }))
                  : [];

                const enrichFishingFishFromGame = (areaRef, fishRef) => {
                    if (!f) return;
                    let a = areaRef;
                    let fish = fishRef;
                    if (f.activeFishingArea && f.selectedAreaFish) {
                        try {
                            const hit = f.selectedAreaFish.get(f.activeFishingArea);
                            if (hit?.name) fish = fish || hit.name;
                        } catch (e) {}
                    }
                    if (!a && f.activeFishingArea) {
                        a = f.activeFishingArea.name ?? a;
                    }
                    fish = fish || f.activeRecipe?.name || f.selectedFish?.name || null;
                    if (!fish && f.selectedAreaFish && a) {
                        for (const [ar, fi] of f.selectedAreaFish.entries()) {
                            if ((ar?.name ?? "") === a) {
                                fish = fi?.name ?? null;
                                break;
                            }
                        }
                    }
                    if (!fish && selected.length === 1) {
                        fish = selected[0].fish;
                        a = a || selected[0].area;
                    }
                    return { area: a, fish };
                };

                const areas = (f?.areas?.allObjects ?? []).map(area => ({
                    name: area?.name ?? "Unknown Area",
                    fish: (area?.fish ?? []).map(fish => {
                        let unlocked = false;
                        try {
                            unlocked = !!f?.isMasteryActionUnlocked?.(fish);
                        } catch (e) {
                            unlocked = false;
                        }
                        let minInt = null;
                        let maxInt = null;
                        try { minInt = Number(f?.getMinFishInterval?.(fish)); } catch (e) {}
                        try { maxInt = Number(f?.getMaxFishInterval?.(fish)); } catch (e) {}
                        return {
                            name: fish?.name ?? "Unknown Fish",
                            level: Number(fish?.level ?? 0),
                            xp: Number(fish?.baseExperience ?? 0),
                            minMs: minInt,
                            maxMs: maxInt,
                            unlocked,
                        };
                    }),
                }));

                // `activeFishingArea` is not reliable for "idle vs fishing". Match actions/fishing.py:
                // a Stop Fishing control under fishing-area-menu only exists while a session is running.
                let isFishing = false;
                let fishingArea = null;
                let fishingFish = null;
                const menus = Array.from(document.querySelectorAll("fishing-area-menu"));
                for (const menu of menus) {
                    const btns = menu.querySelectorAll("button");
                    for (const b of btns) {
                        const t = (b.textContent || "").replace(/\\s+/g, " ").trim();
                        if (!/stop\\s+fishing/i.test(t)) continue;
                        isFishing = true;
                        const blob = (menu.textContent || "").replace(/\\s+/g, " ");
                        const areaObjs = f?.areas?.allObjects ?? [];
                        for (const a of areaObjs) {
                            const n = a?.name;
                            if (n && blob.includes(n)) {
                                fishingArea = n;
                                break;
                            }
                        }
                        const enriched = enrichFishingFishFromGame(fishingArea, fishingFish);
                        fishingArea = enriched.area;
                        fishingFish = enriched.fish;
                        break;
                    }
                    if (isFishing) break;
                }

                if (!isFishing && f?.isActive) {
                    isFishing = true;
                    const enriched = enrichFishingFishFromGame(fishingArea, fishingFish);
                    fishingArea = enriched.area;
                    fishingFish = enriched.fish;
                } else if (isFishing) {
                    const enriched = enrichFishingFishFromGame(fishingArea, fishingFish);
                    fishingArea = enriched.area;
                    fishingFish = enriched.fish;
                }

                return { level, currentRod, isFishing, fishingArea, fishingFish, selected, areas };
            }"""
        )

    print(f"Fishing Level: {int(data['level'])}")
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

    if data["selected"]:
        print("Selected Fish by Area:")
        for row in data["selected"]:
            print(f"- {row['area']}: {row['fish']}")
    else:
        print("Selected Fish by Area: none")

    print("\nAreas and Fish:")
    for area in data["areas"]:
        print(f"\n{area['name']}:")
        for fish in area["fish"]:
            status = "UNLOCKED" if fish["unlocked"] else "LOCKED"
            min_s = f"{fish['minMs'] / 1000:.2f}s" if fish["minMs"] else "?"
            max_s = f"{fish['maxMs'] / 1000:.2f}s" if fish["maxMs"] else "?"
            print(
                f"- {fish['name']}: {status} | level {int(fish['level'])} | "
                f"{int(fish['xp'])} XP | {min_s} - {max_s}"
            )
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1].lower().strip() != "list":
        log_observation("fishing.py", sys.argv[1:], False, "Unknown/missing command.")
        print(__doc__)
        sys.exit(1)
    ok, out = run_observation(show_list)
    log_observation("fishing.py", sys.argv[1:], ok, out)
    sys.exit(0 if ok else 1)


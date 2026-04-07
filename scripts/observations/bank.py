#!/usr/bin/env python3
"""
bank.py — Read-only bank observations.

Usage:
  python scripts/observations/bank.py items    # list bank items: qty, sell value, openable, equipable, equip reqs, upgrade, description
  python scripts/observations/bank.py space    # show used/max bank slots
  python scripts/observations/bank.py info "<item>"  # show item description + equipment stats
"""

import sys
import os
import json

os.environ.setdefault("NODE_NO_WARNINGS", "1")
from playwright.sync_api import sync_playwright
from _observation_logging import log_observation, run_observation

CDP_URL = "http://localhost:9222"
LAST_OBS_DETAILS = ""


def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for page in ctx.pages:
            if "melvor" in page.url.lower():
                return page
    return None


def ensure_game_ready(page) -> bool:
    try:
        page.wait_for_function("() => typeof game !== 'undefined' && !!game.bank", timeout=10000)
        return True
    except Exception:
        return False


def _fmt_gp(value):
    if value is None:
        return "-"
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def list_items() -> bool:
    global LAST_OBS_DETAILS
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False
        data = page.evaluate(
            r"""() => {
                const toSellEach = (item) => {
                    const sf = item?.sellsFor;
                    if (typeof sf === "number") return sf;
                    if (sf && typeof sf.quantity === "number") return sf.quantity;
                    if (sf && typeof sf.gp === "number") return sf.gp;
                    return null;
                };

                const stripHtml = (s) =>
                    String(s || "")
                        .replace(/<[^>]*>/g, " ")
                        .replace(/&nbsp;/g, " ")
                        .replace(/\\s+/g, " ")
                        .trim();

                const itemDescription = (item) => {
                    if (!item) return "";
                    const raw =
                        item.modifiedDescription ?? item.description ?? item.langDescription ?? "";
                    return stripHtml(raw);
                };

                const isItemOpenable = (item) => {
                    if (!item) return false;
                    if (item.openable === true || item._openable === true) return true;
                    const cn = String(item.constructor?.name || "");
                    if (/Openable/i.test(cn)) return true;
                    try {
                        if (typeof item.isOpenable === "function") return !!item.isOpenable();
                    } catch (e) {}
                    try {
                        if (typeof item.hasOpenAction === "function") return !!item.hasOpenAction();
                    } catch (e) {}
                    return false;
                };

                const flattenReqNodes = (n, acc) => {
                    if (n == null) return;
                    if (typeof n === "string") {
                        acc.push(n);
                        return;
                    }
                    if (Array.isArray(n)) {
                        for (const x of n) flattenReqNodes(x, acc);
                        return;
                    }
                    if (typeof n === "object") {
                        if (typeof n.textContent === "string" && n.textContent.trim()) {
                            acc.push(n.textContent);
                            return;
                        }
                        if (typeof n.innerText === "string" && n.innerText.trim()) {
                            acc.push(n.innerText);
                            return;
                        }
                        if (n.data != null) acc.push(String(n.data));
                        if (Array.isArray(n.children)) flattenReqNodes(n.children, acc);
                    }
                };

                const collectEquipRequirements = (item) => {
                    const reqs = [];
                    const rawReqs =
                        item?.equipRequirements ??
                        item?.equipmentRequirements ??
                        item?._equipRequirements ??
                        item?._defaultEquipRequirements ??
                        [];
                    for (const req of (Array.isArray(rawReqs) ? rawReqs : [])) {
                        let txt = "";
                        try {
                            if (typeof req?.getNodes === "function") {
                                const acc = [];
                                flattenReqNodes(req.getNodes(), acc);
                                txt = acc.join("").replace(/\\s+/g, " ").trim();
                            }
                        } catch (e) {}
                        try {
                            // Some node text can be just "Level N" (skill icon omitted); enrich it.
                            if (req?.type === "SkillLevel") {
                                const sk = String(req.skill?.name ?? req.skill?.localID ?? req.skill ?? "").trim();
                                const lv = Number(req.level ?? req.skillLevel ?? req._level ?? NaN);
                                const hasLevelOnly = /^level\s+\d+$/i.test(txt);
                                const hasRequiresLevelOnly = /^requires\s+level\s+\d+$/i.test(txt);
                                if (sk && Number.isFinite(lv) && (!txt || hasLevelOnly || hasRequiresLevelOnly)) {
                                    txt = hasRequiresLevelOnly
                                        ? `Requires ${sk} Level ${lv}`
                                        : `${sk} Level ${lv}`;
                                }
                            }
                        } catch (e) {}
                        if (!txt) {
                            try {
                                if (req?.type === "SkillLevel") {
                                    const sk = req.skill?.name ?? req.skill?.localID ?? req.skill ?? "";
                                    const lv = Number(req.level ?? req.skillLevel ?? req._level ?? NaN);
                                    if (sk && Number.isFinite(lv)) txt = `${sk} Level ${lv}`;
                                }
                            } catch (e) {}
                        }
                        if (txt) reqs.push(txt);
                    }
                    return reqs;
                };

                const entries =
                    game.bank.items instanceof Map
                        ? Array.from(game.bank.items.values())
                        : (game.bank.items?.allObjects ?? game.bank.items ?? []);

                const items = entries.map((entry) => {
                    const bankItem = entry?.item;
                    const name = bankItem?.name ?? "Unknown Item";
                    const id = bankItem?.id ?? "";
                    const qty = Number(entry?.quantity ?? 0);
                    const sellEach = toSellEach(bankItem);
                    const totalSell = sellEach === null ? null : sellEach * qty;
                    const validSlots = (() => {
                        try {
                            const v = bankItem?.validSlots;
                            if (!v) return [];
                            if (Array.isArray(v)) return v;
                            if (typeof v.values === "function") return Array.from(v.values());
                            return Array.from(v);
                        } catch (e) {
                            return [];
                        }
                    })();
                    const equipReqs = collectEquipRequirements(bankItem);
                    const equipable = validSlots.length > 0 || equipReqs.length > 0;
                    const upgradesRaw = game?.bank?.itemUpgrades?.get?.(bankItem) ?? [];
                    const upgrades = (Array.isArray(upgradesRaw) ? upgradesRaw : [])
                        .map((u) => ({
                            target: u?.upgradedItem?.name ?? "Unknown",
                            maxQty: (() => {
                                try { return Number(game.bank.getMaxUpgradeQuantity(u)); } catch (e) { return null; }
                            })(),
                        }))
                        .filter((u) => !!u.target);
                    return {
                        id,
                        name,
                        qty,
                        sellEach,
                        totalSell,
                        upgrades,
                        description: itemDescription(bankItem),
                        openable: isItemOpenable(bankItem),
                        equipable,
                        equipRequirements: equipReqs,
                    };
                });

                items.sort((a, b) => a.name.localeCompare(b.name));
                return { ok: true, items };
            }"""
        )

    if not data.get("ok"):
        print(data.get("error", "Failed to read bank items."))
        return False

    items = data["items"]
    if not items:
        print("Bank is empty.")
        LAST_OBS_DETAILS = "items=0"
        return True

    print("Bank items:\n")
    print(
        f"{'Item':30} {'Qty':>10} {'Sell Each':>12} {'Total Sell':>14} "
        f"{'Open':>5} {'Equip':>6} {'Reqs':<34} {'Upgradeable':<28}"
    )
    print("-" * 150)
    for item in items:
        if item.get("upgrades"):
            up = item["upgrades"][0]
            max_qty = "?" if up.get("maxQty") is None else f"{int(up['maxQty']):,}"
            upgrade_txt = f"yes -> {up['target']} (max {max_qty})"
        else:
            upgrade_txt = "no"
        open_txt = "yes" if item.get("openable") else "no"
        equip_txt = "yes" if item.get("equipable") else "no"
        reqs = item.get("equipRequirements") or []
        reqs_txt = f"({'; '.join(str(r) for r in reqs)})" if reqs else "(none)"
        print(
            f"{item['name'][:30]:30} "
            f"{int(item['qty']):>10,} "
            f"{_fmt_gp(item['sellEach']):>12} "
            f"{_fmt_gp(item['totalSell']):>14} "
            f"{open_txt:>5} "
            f"{equip_txt:>6} "
            f"{reqs_txt[:34]:34} "
            f"{upgrade_txt[:28]:28}"
        )
        desc = (item.get("description") or "").strip()
        if desc:
            print(f"  {desc}")

    LAST_OBS_DETAILS = f"items={len(items)}"

    return True


def show_item_info(item_query: str) -> bool:
    q = _norm(item_query)
    if not q:
        print("Missing item name. Usage: bank.py info \"<item name>\"")
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
            r"""(queryNorm) => {
                const toList = (v) => {
                    if (!v) return [];
                    if (Array.isArray(v)) return v;
                    try {
                        if (typeof v.values === "function") return Array.from(v.values());
                    } catch (e) {}
                    try { return Array.from(v); } catch (e) {}
                    return [];
                };
                const norm = (s) => String(s ?? "").toLowerCase().replace(/\\s+/g, " ").trim();

                const stripHtml = (s) =>
                    String(s || "")
                        .replace(/<[^>]*>/g, " ")
                        .replace(/&nbsp;/g, " ")
                        .replace(/\\s+/g, " ")
                        .trim();

                const humanizeId = (id) => {
                    const s = String(id || "").replace(/^melvorD:/, "");
                    if (!s) return "";
                    return s
                        .replace(/_/g, " ")
                        .replace(/([a-z])([A-Z])/g, "$1 $2")
                        .trim();
                };

                const lookupStatName = (key) => {
                    if (key == null || key === "") return "";
                    if (typeof key === "object") {
                        const n =
                            key.name ??
                            key.localID ??
                            key.displayName ??
                            (typeof key.id === "string" ? lookupStatName(key.id) : "");
                        if (n) return String(n);
                        if (typeof key.id === "string") return humanizeId(key.id);
                        return "";
                    }
                    if (typeof key === "string") {
                        const tries = [
                            () => game.stats?.getObjectByID?.(key),
                            () => game.playerStats?.getObjectByID?.(key),
                            () => game.combatStats?.getObjectByID?.(key),
                            () => game.skillStats?.getObjectByID?.(key),
                            () =>
                                typeof game.getStatFromID === "function" ? game.getStatFromID(key) : null,
                            () => game.registeredObjects?.stats?.getObjectByID?.(key),
                        ];
                        for (const t of tries) {
                            try {
                                const o = t();
                                if (o && (o.name || o.localID)) return String(o.name ?? o.localID);
                            } catch (e) {}
                        }
                        return humanizeId(key);
                    }
                    return humanizeId(String(key));
                };

                const coerceNumber = (v) => {
                    if (v == null) return null;
                    if (typeof v === "number" && Number.isFinite(v)) return v;
                    if (typeof v === "object") {
                        const inner =
                            v.value ?? v.modValue ?? v.amount ?? v.magnitude ?? v.quantity ?? v.base ?? null;
                        if (inner != null) return coerceNumber(inner);
                    }
                    const n = Number(v);
                    return Number.isFinite(n) ? n : null;
                };

                const collectEquipmentStats = (item) => {
                    const out = [];
                    const pushStat = (keyPart, valueRaw, isPercentHint) => {
                        const name = lookupStatName(keyPart);
                        const num = coerceNumber(valueRaw);
                        const isPct =
                            !!isPercentHint ||
                            (typeof keyPart === "object" &&
                                keyPart &&
                                !!(keyPart.isPercent ?? keyPart.isPercentage));
                        let label =
                            name ||
                            (typeof keyPart === "string" ? humanizeId(keyPart) : "") ||
                            (keyPart &&
                            typeof keyPart === "object" &&
                            typeof keyPart.id === "string"
                                ? humanizeId(keyPart.id)
                                : "");
                        if (!label && num == null && (valueRaw === undefined || valueRaw === null)) return;
                        if (!label) label = "Unknown stat";
                        out.push({
                            stat: label,
                            value: num != null ? num : String(valueRaw ?? ""),
                            isPercent: isPct,
                        });
                    };

                    const es = item?.equipmentStats;
                    if (!es) return out;

                    if (es instanceof Map) {
                        for (const [k, v] of es.entries()) {
                            const pct = k?.isPercent ?? k?.isPercentage ?? false;
                            pushStat(k, v, pct);
                        }
                        return out;
                    }

                    if (typeof es === "object" && !Array.isArray(es)) {
                        const keys = Object.keys(es);
                        const looksLikeRecord = keys.length > 0 && keys.every((k) => /^[A-Za-z_]/.test(k));
                        if (looksLikeRecord) {
                            for (const [k, v] of Object.entries(es)) {
                                if (k === "size" && typeof v === "number") continue;
                                pushStat(k, v, false);
                            }
                            return out;
                        }
                    }

                    const arr = toList(es);
                    for (const st of arr) {
                        if (Array.isArray(st) && st.length >= 2) {
                            pushStat(st[0], st[1], false);
                            continue;
                        }
                        if (!st || typeof st !== "object") continue;
                        const keyPart = st.key ?? st.stat ?? st.statKey ?? st.id ?? st.localID;
                        const valueRaw =
                            st.value ?? st.modValue ?? st.modifier ?? st.amount ?? st.quantity ?? st.magnitude;
                        const pct = !!(st.key?.isPercent ?? st.isPercent ?? st.isPercentage);
                        pushStat(keyPart, valueRaw, pct);
                    }
                    return out;
                };

                const flattenReqNodes = (n, acc) => {
                    if (n == null) return;
                    if (typeof n === "string") {
                        acc.push(n);
                        return;
                    }
                    if (Array.isArray(n)) {
                        for (const x of n) flattenReqNodes(x, acc);
                        return;
                    }
                    if (typeof n === "object") {
                        if (typeof n.textContent === "string" && n.textContent.trim()) {
                            acc.push(n.textContent);
                            return;
                        }
                        if (typeof n.innerText === "string" && n.innerText.trim()) {
                            acc.push(n.innerText);
                            return;
                        }
                        if (n.data != null) acc.push(String(n.data));
                        if (Array.isArray(n.children)) flattenReqNodes(n.children, acc);
                    }
                };

                const collectEquipRequirements = (item) => {
                    const reqs = [];
                    const rawReqs =
                        item?.equipRequirements ??
                        item?.equipmentRequirements ??
                        item?._equipRequirements ??
                        item?._defaultEquipRequirements ??
                        [];
                    for (const req of (Array.isArray(rawReqs) ? rawReqs : [])) {
                        let txt = "";
                        try {
                            if (typeof req?.getNodes === "function") {
                                const acc = [];
                                flattenReqNodes(req.getNodes(), acc);
                                txt = acc.join("").replace(/\\s+/g, " ").trim();
                            }
                        } catch (e) {}
                        try {
                            // Some node text can be just "Level N" (skill icon omitted); enrich it.
                            if (req?.type === "SkillLevel") {
                                const sk = String(req.skill?.name ?? req.skill?.localID ?? req.skill ?? "").trim();
                                const lv = Number(req.level ?? req.skillLevel ?? req._level ?? NaN);
                                const hasLevelOnly = /^level\s+\d+$/i.test(txt);
                                const hasRequiresLevelOnly = /^requires\s+level\s+\d+$/i.test(txt);
                                if (sk && Number.isFinite(lv) && (!txt || hasLevelOnly || hasRequiresLevelOnly)) {
                                    txt = hasRequiresLevelOnly
                                        ? `Requires ${sk} Level ${lv}`
                                        : `${sk} Level ${lv}`;
                                }
                            }
                        } catch (e) {}
                        if (!txt) {
                            try {
                                if (req?.type === "SkillLevel") {
                                    const sk = req.skill?.name ?? req.skill?.localID ?? req.skill ?? "";
                                    const lv = Number(req.level ?? req.skillLevel ?? req._level ?? NaN);
                                    if (sk && Number.isFinite(lv)) txt = `${sk} Level ${lv}`;
                                }
                            } catch (e) {}
                        }
                        if (txt) reqs.push(txt);
                    }
                    return reqs;
                };

                const itemDescription = (item) => {
                    if (!item) return "";
                    let raw = "";
                    try {
                        if (typeof item.getDescription === "function") raw = item.getDescription();
                    } catch (e) {}
                    if (!raw) {
                        raw =
                            item.modifiedDescription ??
                            item.description ??
                            item.langDescription ??
                            item.descriptionHTML ??
                            "";
                    }
                    return stripHtml(String(raw));
                };

                const entries =
                    game.bank.items instanceof Map
                        ? Array.from(game.bank.items.values())
                        : (game.bank.items?.allObjects ?? game.bank.items ?? []);
                const rows = entries.map((entry) => {
                    const item = entry?.item;
                    const stats = collectEquipmentStats(item);
                    const slots = toList(item?.validSlots).map((s) => s?.name ?? s?.localID ?? s?.id ?? "Unknown");
                    const equipRequirements = collectEquipRequirements(item);
                    const upgradesRaw = game?.bank?.itemUpgrades?.get?.(item) ?? [];
                    const upgrades = (Array.isArray(upgradesRaw) ? upgradesRaw : []).map((u) => {
                        const itemCosts = (Array.isArray(u?.itemCosts) ? u.itemCosts : []).map((c) => ({
                            name: c?.item?.name ?? "Unknown Item",
                            quantity: Number(c?.quantity ?? 0),
                        }));
                        const currencyCosts = (Array.isArray(u?.currencyCosts) ? u.currencyCosts : []).map((c) => ({
                            name: c?.currency?.name ?? "Currency",
                            quantity: Number(c?.quantity ?? c?.amount ?? c?.value ?? 0),
                        }));
                        let maxQty = null;
                        try { maxQty = Number(game?.bank?.getMaxUpgradeQuantity?.(u)); } catch (e) {}
                        return {
                            target: u?.upgradedItem?.name ?? "Unknown",
                            itemCosts,
                            currencyCosts,
                            maxQty: Number.isFinite(maxQty) ? maxQty : null,
                        };
                    });
                    return {
                        id: item?.id ?? "",
                        name: item?.name ?? "Unknown Item",
                        qty: Number(entry?.quantity ?? 0),
                        description: itemDescription(item),
                        media: item?.media ?? "",
                        typeName: item?.constructor?.name ?? "Item",
                        slots,
                        equipRequirements,
                        upgrades,
                        equipmentStats: stats.filter((s) => {
                            if (!s || !s.stat) return false;
                            if (typeof s.value === "number") return Number.isFinite(s.value);
                            return String(s.value ?? "").length > 0;
                        }),
                    };
                });

                const exact = rows.filter((r) => norm(r.name) === queryNorm);
                let matches = exact;
                if (!matches.length) matches = rows.filter((r) => norm(r.name).includes(queryNorm));

                if (!matches.length) {
                    return { ok: false, error: "not_found" };
                }
                if (matches.length > 1) {
                    return {
                        ok: false,
                        error: "ambiguous",
                        matches: matches.slice(0, 20).map((m) => m.name),
                    };
                }
                return { ok: true, item: matches[0] };
            }""",
            q,
        )

    if not data.get("ok"):
        err = data.get("error")
        if err == "not_found":
            print(f"Item not found in bank: '{item_query}'")
            return False
        if err == "ambiguous":
            names = ", ".join(data.get("matches", []))
            print(f"Ambiguous item '{item_query}'. Matches: {names}")
            return False
        print("Failed to read item info.")
        return False

    item = data.get("item", {})
    print(f"Item: {item.get('name', 'Unknown')}")
    print(f"Bank Qty: {int(item.get('qty', 0)):,}")
    print(f"Type: {item.get('typeName', 'Item')}")

    slots = item.get("slots", [])
    if slots:
        print(f"Equip Slots: {', '.join(str(s) for s in slots)}")
    reqs = item.get("equipRequirements", [])
    if reqs:
        print(f"Equip Requirements: ({'; '.join(str(r) for r in reqs)})")
    elif slots:
        print("Equip Requirements: (none)")

    desc = (item.get("description") or "").strip()
    if desc:
        print(f"Description: {desc}")
    else:
        print("Description: (no text from game — item may use icons-only or wiki for details)")

    stats = item.get("equipmentStats", [])
    if stats:
        print("Equipment Stats:")
        for s in stats:
            stat = str(s.get("stat", "Unknown"))
            val = s.get("value")
            is_pct = bool(s.get("isPercent", False))
            if isinstance(val, (int, float)):
                if is_pct:
                    val_txt = f"{val:+g}%"
                elif val == int(val) and abs(val) < 1e9:
                    val_txt = f"{int(val):+,}"
                else:
                    val_txt = f"{val:+g}"
            else:
                val_txt = str(val)
            print(f"  {stat}: {val_txt}")
    else:
        print("Equipment Stats: (none)")

    upgrades = item.get("upgrades", [])
    if upgrades:
        print("Upgrades:")
        for u in upgrades:
            target = str(u.get("target", "Unknown"))
            max_qty = u.get("maxQty")
            max_txt = "?" if max_qty is None else f"{int(max_qty):,}"
            print(f"  -> {target} (max now: {max_txt})")
            costs = []
            for c in u.get("itemCosts", []) or []:
                q = int(c.get("quantity", 0))
                n = str(c.get("name", "Unknown Item"))
                costs.append(f"{q:,}x {n}")
            for c in u.get("currencyCosts", []) or []:
                q = int(c.get("quantity", 0))
                n = str(c.get("name", "Currency"))
                costs.append(f"{q:,} {n}")
            if costs:
                print(f"     Requires: {', '.join(costs)}")
            else:
                print("     Requires: (none)")
    else:
        print("Upgrades: (none)")

    return True


def show_space() -> bool:
    global LAST_OBS_DETAILS
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
                const bank = game.bank;
                const asNum = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

                const usedCandidates = [
                    asNum(bank.occupiedSlots),
                    asNum(bank.usedSlots),
                    asNum(bank.itemCount),
                    asNum(bank.items?.allObjects?.length),
                ];
                const maxCandidates = [
                    asNum(bank.maximumSlots),
                    asNum(bank.maxSlots),
                    asNum(bank.slotCount),
                    asNum(bank.slots),
                    asNum(bank.baseSlots),
                ];

                let used = usedCandidates.find((v) => v !== null) ?? null;
                let max = maxCandidates.find((v) => v !== null) ?? null;

                if (max === null && typeof bank.getMaxSlots === "function") {
                    try { max = asNum(bank.getMaxSlots()); } catch (e) {}
                }
                if (used === null && typeof bank.getOccupiedSlots === "function") {
                    try { used = asNum(bank.getOccupiedSlots()); } catch (e) {}
                }

                const pct = used !== null && max ? (used / max) * 100 : null;
                return { ok: true, used, max, pct };
            }"""
        )

    if not data.get("ok"):
        print(data.get("error", "Failed to read bank space."))
        return False

    used = data.get("used")
    max_slots = data.get("max")
    pct = data.get("pct")

    if used is None and max_slots is None:
        print("Could not determine bank space from game state.")
        LAST_OBS_DETAILS = "space=unknown"
        return False

    if max_slots is None:
        print(f"Bank space used: {used}")
        LAST_OBS_DETAILS = f"space_used={used}"
        return True

    used_txt = "?" if used is None else f"{int(used):,}"
    max_txt = f"{int(max_slots):,}"
    pct_txt = "" if pct is None else f" ({pct:.1f}%)"
    print(f"Bank space: {used_txt}/{max_txt}{pct_txt}")
    LAST_OBS_DETAILS = f"space={used_txt}/{max_txt}{pct_txt}".strip()
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log_observation("bank.py", sys.argv[1:], False, "Missing command.")
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower().strip()
    if cmd == "items":
        ok, out = run_observation(list_items)
        log_observation("bank.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    elif cmd == "space":
        ok, out = run_observation(show_space)
        log_observation("bank.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    elif cmd == "info":
        if len(sys.argv) < 3:
            log_observation("bank.py", sys.argv[1:], False, "Info missing item query.")
            print("Missing item name. Usage: python scripts/observations/bank.py info \"<item name>\"")
            sys.exit(1)
        query = " ".join(sys.argv[2:]).strip()
        ok, out = run_observation(show_item_info, query)
        log_observation("bank.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    else:
        log_observation("bank.py", sys.argv[1:], False, f"Unknown command: {cmd}")
        print(f"Unknown command: '{cmd}'. Use 'items', 'space', or 'info'.")
        sys.exit(1)

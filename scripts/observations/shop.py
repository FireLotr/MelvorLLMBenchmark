#!/usr/bin/env python3
"""
shop.py — Read-only shop observations.

Usage:
  python scripts/observations/shop.py list   # price, can-buy, unlock requirements, description
  python scripts/observations/shop.py money
  python scripts/observations/shop.py currency
"""

import sys
import os

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
        page.wait_for_function("() => typeof game !== 'undefined' && !!game.shop", timeout=10000)
        return True
    except Exception:
        return False


def show_shop() -> bool:
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
                const buyQuantity = Number(shop.buyQuantity ?? 1);

                const fmtQty = (v) => {
                    const n = Number(v);
                    return Number.isFinite(n) ? n.toLocaleString() : "?";
                };

                const fmtCostX1 = (purchase) => {
                    try {
                        const dc = purchase._defaultCosts ?? {};
                        const boughtQuantity = Number(shop.getPurchaseCount(purchase) ?? 0);
                        const cur = (dc.currencies ?? []).map(
                            (c) => `${fmtQty(shop.getCurrencyCost(c, 1, boughtQuantity))} ${c.currency?.name ?? "Currency"}`
                        );
                        const items = (dc.items ?? []).map(
                            (i) => `${fmtQty(i.quantity)} ${i.item?.name ?? "Item"}`
                        );
                        const parts = [...cur, ...items];
                        return parts.length ? parts.join(" + ") : "Free";
                    } catch (e) {
                        return "Unknown";
                    }
                };

                const canBuyX1 = (purchase) => {
                    try {
                        const prevQty = Number(shop.buyQuantity ?? 1);
                        shop.updateBuyQuantity(1);
                        const unlockOK = game.checkRequirements(purchase.unlockRequirements ?? []);
                        const costs = shop.getPurchaseCosts(purchase);
                        const affordable = costs.checkIfOwned();
                        const atLimit = shop.isPurchaseAtBuyLimit(purchase);
                        const cap = shop.capPurchaseQuantity(purchase, 1);
                        shop.updateBuyQuantity(prevQty);
                        return unlockOK && affordable && !atLimit && cap > 0;
                    } catch (e) {
                        return false;
                    }
                };

                const stripHtml = (s) =>
                    String(s || "")
                        .replace(/<[^>]*>/g, " ")
                        .replace(/&nbsp;/g, " ")
                        .replace(/\\s+/g, " ")
                        .trim();

                const purchaseDescription = (p) => {
                    try {
                        if (typeof p.getDescription === "function") {
                            const d = p.getDescription();
                            if (d) return stripHtml(d);
                        }
                    } catch (e) {}
                    return stripHtml(p.description ?? p.desc ?? "");
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

                const formatUnlockRequirement = (req) => {
                    if (!req) return "";
                    try {
                        if (typeof req.getNodes === "function") {
                            const acc = [];
                            flattenReqNodes(req.getNodes(), acc);
                            const s = acc.join("").replace(/\\s+/g, " ").trim();
                            if (s) return s;
                        }
                    } catch (e) {}
                    try {
                        const t = req.type;
                        if (t === "ShopPurchase") {
                            const pn = req.purchase?.name ?? req.purchase ?? "";
                            const c = Number(req.count ?? 1);
                            if (pn) {
                                return c > 1
                                    ? `Purchase ${pn} from the Shop (×${c})`
                                    : `Purchase ${pn} from the Shop`;
                            }
                        }
                        const sk = req.skill ?? req._skill;
                        const skName = sk?.name ?? sk?.localID ?? "";
                        const lv = req.level ?? req.skillLevel ?? req._level;
                        if (skName && lv != null && Number.isFinite(Number(lv))) {
                            return `${skName} Level ${Number(lv)}`;
                        }
                        if (req.dungeon?.name && req.count != null) {
                            return `Complete ${req.dungeon.name} ${Number(req.count)}×`;
                        }
                    } catch (e) {}
                    return "";
                };

                /** Skill gates etc. — not included in unlockRequirements (e.g. Mining Level 35 for Mithril Pickaxe). */
                const formatDefaultPurchaseRequirement = (req) => {
                    if (!req) return "";
                    try {
                        if (req.type === "SkillLevel") {
                            const sk = req.skill?.name ?? req.skill?.localID ?? req.skill;
                            const lv = req.level;
                            if (sk && lv != null && Number.isFinite(Number(lv))) {
                                return `${sk} Level ${Number(lv)}`;
                            }
                        }
                    } catch (e) {}
                    return "";
                };

                const purchaseRequirements = (p) => {
                    const lines = [];
                    for (const r of p._defaultPurchaseRequirements ?? []) {
                        const s = formatDefaultPurchaseRequirement(r);
                        if (s) lines.push(s);
                    }
                    for (const r of p.unlockRequirements ?? []) {
                        const s = formatUnlockRequirement(r);
                        if (s) lines.push(s);
                    }
                    return lines;
                };

                const rows = (shop.purchases?.allObjects ?? []).map((p) => ({
                    id: p.id,
                    name: p.name,
                    category: p.category?.name ?? "",
                    price1x: fmtCostX1(p),
                    canBuy1x: canBuyX1(p),
                    description: purchaseDescription(p),
                    requirements: purchaseRequirements(p),
                }));

                rows.sort((a, b) => a.name.localeCompare(b.name));
                return { ok: true, buyQuantity, rows };
            }"""
        )

    if not data.get("ok"):
        print("Failed to read shop data.")
        return False

    rows = data["rows"]
    print(f"Current shop buy quantity: {int(data['buyQuantity'])}\n")
    print("Name | Category | Price (x1) | Can Buy")
    print("-" * 120)
    for r in rows:
        can_buy = "yes" if r["canBuy1x"] else "no"
        print(f"{r['name']} | {r['category']} | {r['price1x']} | {can_buy}")
        reqs = r.get("requirements") or []
        if reqs:
            print(f"  Requires: {'; '.join(reqs)}")
        desc = (r.get("description") or "").strip()
        if desc:
            print(f"  {desc}")

    return True


def show_currency() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if page is None:
            print("Could not find an open Melvor tab.")
            return False
        if not ensure_game_ready(page):
            print("Game is not ready.")
            return False

        data = page.evaluate(
            """() => ({
                gp: Number(game.gp?.amount ?? 0),
                slayerCoins: Number(game.slayerCoins?.amount ?? 0),
            })"""
        )

    print(f"GP: {int(data.get('gp', 0)):,}")
    print(f"Slayer Coins: {int(data.get('slayerCoins', 0)):,}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log_observation("shop.py", sys.argv[1:], False, "Missing command.")
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower().strip()
    if cmd == "list":
        ok, out = run_observation(show_shop)
        log_observation("shop.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    elif cmd in ("money", "currency"):
        ok, out = run_observation(show_currency)
        log_observation("shop.py", sys.argv[1:], ok, out)
        sys.exit(0 if ok else 1)
    else:
        log_observation("shop.py", sys.argv[1:], False, f"Unknown command: {cmd}")
        print(f"Unknown command: '{cmd}'. Use 'list', 'money', or 'currency'.")
        sys.exit(1)

from __future__ import annotations

SHOP_LIST_JS = """() => {
    const shop = game?.shop;
    if (!shop) return { ok: false, error: "no shop" };
    const buyQuantity = Number(shop.buyQuantity ?? 1);
    const gp = Number(game?.gp?.amount ?? game?.gp ?? 0);
    const slayerCoins = Number(game?.slayerCoins?.amount ?? game?.slayerCoins ?? 0);

    const fmtQty = (v) => {
        const n = Number(v);
        return Number.isFinite(n) ? n.toLocaleString() : "?";
    };

    const fmtCostX1 = (purchase) => {
        try {
            const dc = purchase?._defaultCosts ?? {};
            const boughtQuantity = Number(shop.getPurchaseCount(purchase) ?? 0);
            const cur = (dc.currencies ?? []).map(
                (c) => `${fmtQty(shop.getCurrencyCost(c, 1, boughtQuantity))} ${c.currency?.name ?? "Currency"}`
            );
            const items = (dc.items ?? []).map((i) => `${fmtQty(i.quantity)} ${i.item?.name ?? "Item"}`);
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
        const name = String(p?.name ?? "");
        try {
            if (typeof p.getDescription === "function") {
                const d = p.getDescription();
                if (d) {
                    let text = stripHtml(d);
                    if (name === "Extra Bank Slot") {
                        let nextPrice = null;
                        let nextTenTotal = null;
                        try {
                            const boughtQuantity = Number(shop.getPurchaseCount(p) ?? 0);
                            const dc = p?._defaultCosts ?? {};
                            const gpCost = (dc.currencies ?? []).find(
                                (c) => String(c?.currency?.name ?? "").toLowerCase() === "gp"
                            );
                            if (gpCost) {
                                nextPrice = Number(shop.getCurrencyCost(gpCost, 1, boughtQuantity + 1));
                                let total = 0;
                                for (let i = 1; i <= 10; i++) {
                                    total += Number(shop.getCurrencyCost(gpCost, 1, boughtQuantity + i));
                                }
                                nextTenTotal = total;
                            }
                        } catch (e) {}
                        text = text.replace(/\\$\\{qty\\}/g, "1");
                        if (Number.isFinite(nextPrice)) {
                            if (Number.isFinite(nextTenTotal)) {
                                text += ` (Next slot: ${Number(nextPrice).toLocaleString()} GP | 10 slots: ${Number(nextTenTotal).toLocaleString()} GP)`;
                            } else {
                                text += ` (Next slot: ${Number(nextPrice).toLocaleString()} GP)`;
                            }
                        } else if (!/cost increases/i.test(text)) {
                            text += " (Cost increases for each additional slot.)";
                        }
                    }
                    return text;
                }
            }
        } catch (e) {}
        let text = stripHtml(p.description ?? p.desc ?? "");
        if (name === "Extra Bank Slot") {
            let nextPrice = null;
            let nextTenTotal = null;
            try {
                const boughtQuantity = Number(shop.getPurchaseCount(p) ?? 0);
                const dc = p?._defaultCosts ?? {};
                const gpCost = (dc.currencies ?? []).find(
                    (c) => String(c?.currency?.name ?? "").toLowerCase() === "gp"
                );
                if (gpCost) {
                    nextPrice = Number(shop.getCurrencyCost(gpCost, 1, boughtQuantity + 1));
                    let total = 0;
                    for (let i = 1; i <= 10; i++) {
                        total += Number(shop.getCurrencyCost(gpCost, 1, boughtQuantity + i));
                    }
                    nextTenTotal = total;
                }
            } catch (e) {}
            text = text.replace(/\\$\\{qty\\}/g, "1");
            if (Number.isFinite(nextPrice)) {
                if (Number.isFinite(nextTenTotal)) {
                    text += ` (Next slot: ${Number(nextPrice).toLocaleString()} GP | 10 slots: ${Number(nextTenTotal).toLocaleString()} GP)`;
                } else {
                    text += ` (Next slot: ${Number(nextPrice).toLocaleString()} GP)`;
                }
            } else if (!/cost increases/i.test(text)) {
                text += " (Cost increases for each additional slot.)";
            }
        }
        return text;
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
                if (pn) return c > 1 ? `Purchase ${pn} from the Shop (x${c})` : `Purchase ${pn} from the Shop`;
            }
            const sk = req.skill ?? req._skill;
            const skName = sk?.name ?? sk?.localID ?? "";
            const lv = req.level ?? req.skillLevel ?? req._level;
            if (skName && lv != null && Number.isFinite(Number(lv))) return `${skName} Level ${Number(lv)}`;
            if (req.dungeon?.name && req.count != null) return `Complete ${req.dungeon.name} ${Number(req.count)}x`;
        } catch (e) {}
        return "";
    };

    const formatDefaultPurchaseRequirement = (req) => {
        if (!req) return "";
        try {
            if (req.type === "SkillLevel") {
                const sk = req.skill?.name ?? req.skill?.localID ?? req.skill;
                const lv = req.level;
                if (sk && lv != null && Number.isFinite(Number(lv))) return `${sk} Level ${Number(lv)}`;
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

    const rows = (shop.purchases?.allObjects ?? [])
        .map((p) => ({
            id: p.id,
            name: p.name,
            category: p.category?.name ?? "",
            price1x: fmtCostX1(p),
            canBuy1x: canBuyX1(p),
            description: purchaseDescription(p),
            requirements: purchaseRequirements(p),
        }))
        .filter((r) => String(r.category || "").trim().toLowerCase() !== "golbin raid");
    rows.sort((a, b) => {
        const ca = String(a.category || "");
        const cb = String(b.category || "");
        const c = ca.localeCompare(cb);
        if (c !== 0) return c;
        return String(a.name || "").localeCompare(String(b.name || ""));
    });
    const categories = Array.from(new Set(rows.map((r) => String(r.category || "").trim()).filter(Boolean))).sort((a, b) =>
        a.localeCompare(b)
    );
    return { ok: true, buyQuantity, gp, slayerCoins, categories, rows };
}"""

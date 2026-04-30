from __future__ import annotations

SHOP_BUY_JS = """

(pack) => {
  const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
  const bank = game?.bank;
  const usedSlots = Number(bank?.occupiedSlots ?? bank?.usedSlots ?? 0);
  const maxSlots = Number(bank?.maximumSlots ?? bank?.maxSlots ?? 0);
  if (Number.isFinite(usedSlots) && Number.isFinite(maxSlots) && maxSlots > 0 && usedSlots >= maxSlots) {
    return { ok:false, error:"bank is full" };
  }
  const shop = game?.shop;
  if (!shop?.purchases?.allObjects) return { ok: false, error: "game.shop not ready" };
  const qn = norm(pack.name);
  const all = shop.purchases.allObjects;
  let p = all.find((x) => norm(x.name) === qn);
  if (!p) {
    const hits = all.filter((x) => qn.length >= 2 && norm(x.name).includes(qn));
    if (hits.length === 1) p = hits[0];
    else if (hits.length > 1) return { ok: false, error: "ambiguous", matches: hits.slice(0, 12).map((x) => x.name) };
    else return { ok: false, error: "purchase not found" };
  }
  const q = Math.max(1, Math.floor(Number(pack.qty) || 1));
  const prev = Number(shop.buyQuantity ?? 1);
  try {
    shop.updateBuyQuantity(q);
  } catch (e) {
    return { ok: false, error: "updateBuyQuantity: " + String(e) };
  }
  try {
    if (typeof shop.isPurchaseAtBuyLimit === "function" && shop.isPurchaseAtBuyLimit(p)) {
      return { ok:false, error:"purchase already at buy limit", name: p.name };
    }
    const quantityToBuy = p?.allowQuantityPurchase
      ? (typeof shop.capPurchaseQuantity === "function" ? Number(shop.capPurchaseQuantity(p, q)) : q)
      : 1;
    if (Number.isFinite(quantityToBuy) && quantityToBuy <= 0) {
      return { ok:false, error:"cannot buy this purchase right now", name: p.name };
    }
    if (p?.allowQuantityPurchase && Number.isFinite(quantityToBuy) && quantityToBuy < q) {
      return { ok:false, error:`requested qty ${q} exceeds max buyable ${quantityToBuy}`, name: p.name, maxBuyable: quantityToBuy };
    }
    const reqOK = game.checkRequirements(p.purchaseRequirements ?? []);
    if (!reqOK) {
      return { ok:false, error:"purchase requirements not met", name: p.name };
    }
    const costs = typeof shop.getPurchaseCosts === "function" ? shop.getPurchaseCosts(p, quantityToBuy) : null;
    if (!costs?.checkIfOwned?.()) {
      return { ok:false, error:"insufficient resources to buy this purchase", name: p.name };
    }
  } catch (e) {
    return { ok:false, error:"purchase eligibility check failed: " + String(e), name: p?.name ?? qn };
  }
  try {
    shop.buyItemOnClick(p, true);
    return { ok: true, name: p.name, qty: q };
  } catch (e) {
    return { ok: false, error: String(e) };
  } finally {
    try { shop.updateBuyQuantity(prev); } catch (e) {}
  }
}

"""

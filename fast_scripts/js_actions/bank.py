from __future__ import annotations

BANK_CLAIM_JS = """
(pack) => {
    const itemName = String(pack?.name ?? "");
    const qty = Math.max(1, Number(pack?.qty ?? 1));
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const q = norm(itemName);
    const bank = game?.bank;
    const entries = bank.items instanceof Map ? Array.from(bank.items.values()) : (bank.items?.allObjects ?? []);
    const hit = entries.find((e) => norm(e?.item?.name) === q) || entries.find((e) => norm(e?.item?.name).includes(q));
    if (!hit?.item) return { ok:false, error:"item not found in bank" };
    const beforeQty = Number(hit?.quantity ?? 0);
    if (!Number.isFinite(beforeQty) || beforeQty <= 0) return { ok:false, error:"no quantity in bank" };
    if (!(hit.item instanceof MasteryTokenItem)) {
      return { ok:false, error:`item is not claimable (not a MasteryTokenItem): ${hit?.item?.name ?? itemName}` };
    }
    const claimQty = Math.min(qty, beforeQty);
    try {
      bank.claimMasteryTokenOnClick(hit.item, claimQty);
      const afterQty = Number(bank?.getQty?.(hit.item) ?? (hit?.quantity ?? 0));
      const left = Number.isFinite(afterQty) ? Math.max(0, afterQty) : null;
      const claimed = Number.isFinite(left) ? Math.max(0, beforeQty - left) : claimQty;
      return { ok:true, qty:claimed, requested:claimQty, left };
    } catch (e) {
      const msg = String(e?.message ?? e);
      if (/remove negative or zero quantity from bank/i.test(msg)) {
        return {
          ok:false,
          error:"mastery pool is almost full - spend mastery pool XP before you can claim more tokens",
        };
      }
      return { ok:false, error:msg };
    }
}
"""

BANK_EQUIP_FOOD_JS = """
(pack) => {
    const itemName = String(pack?.name ?? "");
    const reqQty = Number(pack?.qty ?? 0);
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const q = norm(itemName);
    const entries = game?.bank?.items instanceof Map ? Array.from(game.bank.items.values()) : (game?.bank?.items?.allObjects ?? []);
    const hit = entries.find((e) => norm(e?.item?.name) === q) || entries.find((e) => q && norm(e?.item?.name).includes(q));
    if (!hit?.item) return { ok:false, error:"item not found in bank" };
    const food = game?.combat?.player?.food;
    if (!food?.slots) return { ok:false, error:"combat food container not found" };
    if (!(hit.item instanceof FoodItem)) return { ok:false, error:"item is not a food item" };

    const isEmpty = (s) => {
      if (!s || s?.quantity <= 0) return true;
      return false;
    };

    const itemId = String(hit?.item?.id ?? "");
    const isSameItem = (slot) => String(slot?.item?.id ?? "") === itemId;
    const bankQty = Number(hit?.quantity ?? 0);
    if (!Number.isFinite(bankQty) || bankQty <= 0) return { ok:false, error:"no quantity in bank" };
    const moveQty = Number.isFinite(reqQty) && reqQty > 0 ? Math.max(1, Math.floor(reqQty)) : bankQty;
    const qty = Math.min(moveQty, bankQty);

    const slots = food?.slots ?? [];
    const hasSameItemSlot = slots.some((s) => isSameItem(s));
    const hasFreeSlot = slots.some((s) => isEmpty(s));
    if (!hasSameItemSlot && !hasFreeSlot) {
      return {
        ok:false,
        error:"no free food slot available",
        details:"All food slots are occupied by other items. Unequip one slot first.",
      };
    }
    try {
      game.combat.player.equipFood(hit.item, qty);
      return { ok:true, qty:qty };
    } catch (e) {
      return { ok:false, error:String(e) };
    }
}
"""

BANK_EQUIP_JS = """
(itemName) => {
    const q = String(itemName ?? "").toLowerCase().trim();
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const entries = game?.bank?.items instanceof Map ? Array.from(game.bank.items.values()) : (game?.bank?.items?.allObjects ?? []);
    const hit = entries.find((e) => norm(e?.item?.name) === q) || entries.find((e) => norm(e?.item?.name).includes(q));
    if (!hit?.item) return { ok:false, error:"item not found in bank" };
    const p = game?.combat?.player;
    const validSlots = Array.from(hit?.item?.validSlots ?? []);
    if (validSlots.length === 0) {
      return { ok:false, error:`item is not equipable: ${hit?.item?.name ?? itemName}` };
    }
    const slot = validSlots[0];
    if (!slot) return { ok:false, error:"could not resolve equip slot for item" };
    try {
      p.equipCallback(hit.item, slot, 1);
    } catch (e) {
      return { ok:false, error:`equipCallback failed: ${String(e)}` };
    }
    const slotsEq = p?.equipment?.equippedArray ?? [];
    const slotId = String(slot?.id ?? slot?.localID ?? "");
    let rec = slotsEq.find((e) => {
      if (e?.slot === slot) return true;
      const eid = String(e?.slot?.id ?? e?.slot?.localID ?? "");
      return Boolean(slotId) && eid === slotId;
    });
    if (!rec) {
      const target = norm(String(slot?.name ?? slot?.localID ?? slot?.id ?? ""));
      const cands = slotsEq.filter((e) => {
        const k = norm(String(e?.slot?.name ?? e?.slot?.localID ?? e?.slot?.id ?? ""));
        return k === target || k.includes(target) || target.includes(k);
      });
      rec = cands.length === 1 ? cands[0] : null;
    }
    const wantId = String(hit.item?.id ?? "");
    const gotId = String(rec?.item?.id ?? "");
    const idOk = wantId && gotId === wantId;
    const nameOk = !wantId && norm(String(rec?.item?.name ?? "")) === norm(String(hit.item?.name ?? ""));
    if (!rec || !(idOk || nameOk)) {
      return {
        ok:false,
        error:"item was not equipped - requirements may not be met (e.g. skill level), or another condition blocked the equip",
        item: hit?.item?.name ?? itemName,
      };
    }
    return { ok:true, item: hit?.item?.name ?? itemName };
}
"""

BANK_OPEN_JS = """
(pack) => {
    const itemName = String(pack?.name ?? "");
    const qty = Math.max(1, Number(pack?.qty ?? 1));
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const q = norm(itemName);
    const bank = game?.bank;
    const entries = bank.items instanceof Map ? Array.from(bank.items.values()) : (bank.items?.allObjects ?? []);
    const hit = entries.find((e) => norm(e?.item?.name) === q) || entries.find((e) => norm(e?.item?.name).includes(q));
    if (!hit?.item) return { ok:false, error:"item not found in bank" };
    const beforeQty = Number(hit?.quantity ?? 0);
    if (!Number.isFinite(beforeQty) || beforeQty <= 0) return { ok:false, error:"no quantity in bank" };
    const openQty = Math.min(qty, beforeQty);

    if (!(hit.item instanceof OpenableItem)) {
      return { ok:false, error:`item is not openable: ${hit?.item?.name ?? itemName}` };
    }

    const used = Number(bank.occupiedSlots);
    const maxS = Number(bank.maximumSlots);
    if (Number.isFinite(used) && Number.isFinite(maxS) && maxS > 0 && used >= maxS) {
      return { ok:false, error:"bank is full" };
    }

    try {
      bank.processItemOpen(hit.item, openQty);
      return { ok:true, qty:openQty };
    } catch (e) {
      return { ok:false, error:String(e?.message ?? e) };
    }
}
"""

BANK_SELL_JS = """
(pack) => {
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const n = norm(pack?.name);
    const qtyWant = Math.max(1, Math.floor(Number(pack?.qty) || 1));
    const bank = game?.bank;
    if (!bank?.items) return { ok:false, error:"no bank" };
    const entries = bank.items instanceof Map ? Array.from(bank.items.values()) : (bank.items?.allObjects ?? []);
    const exact = entries.filter((e) => norm(e.item?.name) === n);
    let entry = null;
    if (exact.length === 1) entry = exact[0];
    else if (exact.length > 1) return { ok:false, error:"ambiguous exact" };
    else {
      const partial = entries.filter((e) => n.length >= 2 && norm(e.item?.name).includes(n));
      if (partial.length === 1) entry = partial[0];
      else if (partial.length > 1) {
        return { ok:false, error:"ambiguous", matches: partial.slice(0, 10).map((e) => e.item?.name) };
      }
      else return { ok:false, error:"not in bank" };
    }
    const item = entry.item;
    if (!item) return { ok:false, error:"no item" };
    const have = Number(entry.quantity ?? 0);
    const q = Math.min(qtyWant, have);
    if (q < 1) return { ok:false, error:"quantity 0" };
    try {
      bank.processItemSale(item, q);
    } catch (e) {
      return { ok:false, error:String(e) };
    }
    return { ok:true, name:item.name, qty:q };
}
"""

BANK_UNEQUIP_JS = """
(slotQuery) => {
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const q = norm(slotQuery);
    const player = game?.combat?.player;
    const equipment = player?.equipment;
    const slots = equipment?.equippedArray ?? [];
    if (!Array.isArray(slots) || slots.length === 0) return { ok:false, error:"equipment data unavailable" };
    const isEmptyEquip = (rec) => {
      const id = String(rec?.item?.id ?? "");
      return !id || /empty[_\s-]?equipment/i.test(id);
    };
    const slotKey = (rec) => {
      const n = String(rec?.slot?.name ?? rec?.slot?.localID ?? rec?.slot?.id ?? "");
      return norm(n);
    };
    const keyMatches = (rec) => {
      const k = slotKey(rec);
      return k === q || k.includes(q) || q.includes(k);
    };
    const candidates = slots.filter(keyMatches);
    if (candidates.length === 0) {
      return {
        ok:false,
        error:`unknown equipment slot: ${slotQuery}`,
        knownSlots: slots.map((rec) => String(rec?.slot?.name ?? rec?.slot?.id ?? "?")),
      };
    }
    if (candidates.length > 1) {
      return {
        ok:false,
        error:`ambiguous slot: ${slotQuery}`,
        matches: candidates.map((rec) => String(rec?.slot?.name ?? rec?.slot?.id ?? "Unknown")),
      };
    }
    const rec = candidates[0];
    const slotObj = rec?.slot;
    const slotLabel = String(slotObj?.name ?? slotObj?.id ?? slotQuery);
    if (isEmptyEquip(rec)) {
      return { ok:false, error:`slot already empty: ${slotLabel}` };
    }
    const beforeItemName = String(rec?.item?.name ?? "Unknown");
    const bank = game?.bank;
    const usedSlots = Number(bank?.occupiedSlots ?? bank?.usedSlots ?? 0);
    const maxSlots = Number(bank?.maximumSlots ?? bank?.maxSlots ?? 0);
    if (Number.isFinite(usedSlots) && Number.isFinite(maxSlots) && maxSlots > 0 && usedSlots >= maxSlots) {
      return { ok:false, error:"bank is full" };
    }
    const set = player.selectedEquipmentSet;
    try {
      player.unequipItem(set, slotObj);
      return { ok:true, slot: slotLabel };
    } catch (e) {
      return { ok:false, error:String(e?.message ?? e), slot: slotLabel };
    }
}
"""

BANK_UPGRADE_JS = """
(pack) => {
    const itemName = String(pack?.name ?? "");
    const qty = Math.max(1, Number(pack?.qty ?? 1));
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const q = norm(itemName);
    const bank = game?.bank;
    const entries = bank?.items instanceof Map ? Array.from(game.bank.items.values()) : (game?.bank?.items?.allObjects ?? []);
    const hit = entries.find((e) => norm(e?.item?.name) === q) || entries.find((e) => norm(e?.item?.name).includes(q));
    if (!hit?.item) return { ok:false, error:"item not found in bank" };
    const beforeQty = Number(hit?.quantity ?? 0);
    if (!Number.isFinite(beforeQty) || beforeQty <= 0) return { ok:false, error:"no quantity in bank" };

    const upgradesRaw = bank?.itemUpgrades?.get?.(hit.item);
    const upgrades = Array.isArray(upgradesRaw) ? upgradesRaw : (upgradesRaw ? Array.from(upgradesRaw) : []);
    if (!upgrades.length) return { ok:false, error:"item not upgradeable" };
    const upgrade = upgrades[0];
    if (!upgrade) return { ok:false, error:"upgrade object unavailable" };
    if (typeof bank?.upgradeItemOnClick !== "function") return { ok:false, error:"bank.upgradeItemOnClick unavailable" };

    const usedSlots = Number(bank?.occupiedSlots);
    const maxSlots = Number(bank?.maximumSlots);
    const isBankFull =
      (Number.isFinite(usedSlots) && Number.isFinite(maxSlots) && maxSlots > 0 && usedSlots >= maxSlots);
    if (isBankFull) {
      return { ok:false, error:"bank is full" };
    }

    try {
      bank.upgradeItemOnClick(upgrade, qty);
      return { ok:true, qty:qty };
    } catch (e) {
      const msg = String(e?.message ?? e);
      if (/negative or zero quantity/i.test(msg)) {
        return {
          ok:false,
          error:"insufficient resources to upgrade (item or currency costs)",
        };
      }
      return { ok:false, error:`upgradeItemOnClick failed: ${msg}` };
    }
}
"""

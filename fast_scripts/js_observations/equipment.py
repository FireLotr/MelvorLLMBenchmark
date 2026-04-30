from __future__ import annotations

EQUIPMENT_READ_JS = """() => {
    const p = game?.combat?.player;
    if (!p) return { ok:false, error:"no player" };
    const eq = (p?.equipment?.equippedArray ?? []).map((e) => ({
        slotID: e?.slot?.id ?? "",
        itemID: e?.item?.id ?? "",
        itemName: e?.item?.name ?? "",
        qty: Number(e?.quantity ?? 0),
    }));
    const food = (p?.food?.slots ?? []).map((f, i) => ({
        slotID: `Food_${i + 1}`,
        itemID: f?.item?.id ?? "",
        itemName: f?.item?.name ?? "",
        qty: Number(f?.quantity ?? 0),
    }));
    let activeFoodSlot = null;
    const asSlotNum = (v) => {
        const n = Number(v);
        if (Number.isFinite(n) && n >= 0 && n < 3) return n + 1;
        if (Number.isFinite(n) && n >= 1 && n <= 3) return n;
        return null;
    };
    for (const v of [p?.food?.selectedSlot, p?.food?.currentSlot, p?.food?.activeSlot]) {
        const s = asSlotNum(v);
        if (s) { activeFoodSlot = s; break; }
    }
    if (!activeFoodSlot) {
        const sid = String(p?.selectedFood?.slot?.id ?? p?.selectedFood?.slotID ?? "");
        const m = sid.match(/(\\d+)/);
        if (m) {
            const n = Number(m[1]);
            if (Number.isFinite(n) && n >= 1 && n <= 3) activeFoodSlot = n;
        }
    }
    return { ok:true, equipment:eq, food, activeFoodSlot };
}"""

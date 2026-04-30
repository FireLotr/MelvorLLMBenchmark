from __future__ import annotations

BANK_ITEMS_JS = """() => {
    const bank = game?.bank;
    if (!bank?.items) return { ok:false, error:"no bank" };
    const toNum = (v) => {
      if (typeof v === "number") return Number.isFinite(v) ? v : 0;
      if (typeof v === "string" && v.trim() !== "" && !Number.isNaN(Number(v))) return Number(v);
      if (v && typeof v === "object") {
        if (typeof v.quantity === "number") return Number(v.quantity) || 0;
        if (typeof v.amount === "number") return Number(v.amount) || 0;
        if (typeof v.value === "number") return Number(v.value) || 0;
      }
      return 0;
    };
    const normTxt = (s) => String(s ?? "").replace(/\\s+/g, " ").trim();
    const isVisible = (el) => {
      if (!el) return false;
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };
    const selectItem = (item) => {
      try {
        if (typeof bank.selectBankItem === "function") {
          bank.selectBankItem(item);
          return true;
        }
        if (typeof bank.onItemSelectionClick === "function") {
          bank.onItemSelectionClick(item);
          return true;
        }
        if (typeof bank.selectItemOnClick === "function") {
          bank.selectItemOnClick(item);
          return true;
        }
      } catch (e) {}
      return false;
    };
    const getSalePrice = (item) => {
      try {
        const v = bank.getItemSalePrice?.(item);
        const n = toNum(v);
        if (n > 0) return n;
      } catch (e) {}
      try {
        const sf = item?.sellsFor;
        if (Array.isArray(sf) && sf.length > 0) {
          const first = sf[0];
          const n = toNum(first?.quantity ?? first?.amount ?? first?.value);
          if (n > 0) return n;
        }
      } catch (e) {}
      return 0;
    };
    const stripHtml = (s) =>
      String(s ?? "")
        .replace(/<br\\s*\\/?>/gi, "\\n")
        .replace(/<[^>]+>/g, "")
        .replace(/\\s+\\n/g, "\\n")
        .replace(/\\n\\s+/g, "\\n")
        .replace(/\\s+/g, " ")
        .trim();
    const itemDescription = (item) => {
      if (!item) return "";
      let raw = "";
      try {
        if (typeof item.getDescription === "function") raw = item.getDescription();
      } catch (e) {}
      if (!raw) raw = item.modifiedDescription ?? item.description ?? item.langDescription ?? item.descriptionHTML ?? "";
      return stripHtml(String(raw));
    };
    const coerceNumber = (x) => {
      if (typeof x === "number") return Number.isFinite(x) ? x : null;
      if (typeof x === "string" && x.trim() !== "" && !Number.isNaN(Number(x))) return Number(x);
      return null;
    };
    const readFoodHealing = (item) => {
      const candidates = [
        item?.healsFor,
        item?.healValue,
        item?.healingValue,
        item?.foodHealing,
        item?.healing,
      ];
      for (const v of candidates) {
        const n = coerceNumber(v);
        if (n != null && Number.isFinite(n) && n > 0) return n;
      }
      try {
        if (typeof item?.getHealingValue === "function") {
          const n = coerceNumber(item.getHealingValue());
          if (n != null && Number.isFinite(n) && n > 0) return n;
        }
      } catch (e) {}
      try {
        if (typeof item?.getFoodHealing === "function") {
          const n = coerceNumber(item.getFoodHealing());
          if (n != null && Number.isFinite(n) && n > 0) return n;
        }
      } catch (e) {}
      return null;
    };
    const readFoodHealingRaw = (item) => {
      const out = {};
      const add = (k, v) => {
        if (v === undefined || v === null) return;
        if (typeof v === "number") {
          if (Number.isFinite(v)) out[k] = v;
          return;
        }
        if (typeof v === "string") {
          const n = Number(v);
          out[k] = Number.isFinite(n) ? n : v;
          return;
        }
        out[k] = String(v);
      };
      add("healsFor", item?.healsFor);
      add("healValue", item?.healValue);
      add("healingValue", item?.healingValue);
      add("foodHealing", item?.foodHealing);
      add("healing", item?.healing);
      try {
        if (typeof item?.getHealingValue === "function") add("getHealingValue()", item.getHealingValue());
      } catch (e) {}
      try {
        if (typeof item?.getFoodHealing === "function") add("getFoodHealing()", item.getFoodHealing());
      } catch (e) {}
      return out;
    };
    const inspectActions = (item) => {
      const itemName = String(item?.name ?? "");
      const typeName = String(item?.constructor?.name ?? "");
      const isEquipment =
        (typeof EquipmentItem !== "undefined" && item instanceof EquipmentItem) ||
        typeName === "EquipmentItem" ||
        typeName === "WeaponItem";
      const isOpenable =
        (typeof OpenableItem !== "undefined" && item instanceof OpenableItem) ||
        typeName === "OpenableItem";
      const isMasteryToken =
        (typeof MasteryTokenItem !== "undefined" && item instanceof MasteryTokenItem) ||
        typeName === "MasteryTokenItem";
      const slotNames = (() => {
        const slots = item?.validSlots;
        let arr = [];
        if (Array.isArray(slots)) arr = slots;
        else if (slots instanceof Set) arr = Array.from(slots.values());
        else if (slots instanceof Map) arr = Array.from(slots.values());
        else if (slots?.allObjects) arr = Array.from(slots.allObjects);
        return arr
          .map((s) => String(s?.name ?? s?.localID ?? s?.id ?? "").trim())
          .filter((s) => s.length > 0);
      })();
      const slotCount = (() => {
        return slotNames.length;
      })();
      const upgradesRaw = bank?.itemUpgrades?.get?.(item) ?? [];
      const upgradesCount = Array.isArray(upgradesRaw) ? upgradesRaw.length : 0;
      const healing = readFoodHealing(item);
      const canEquipFood =
        (typeof FoodItem !== "undefined" && item instanceof FoodItem) ||
        (Number.isFinite(healing) && healing > 0);
      const out = {
        canSell: getSalePrice(item) > 0,
        canUpgrade: upgradesCount > 0,
        canOpen: isOpenable,
        canEquip: isEquipment || slotCount > 0 || canEquipFood,
        canClaim: isMasteryToken,
        canEquipFood,
        otherFeatures: [],
      };
      const extras = [];
      if (slotNames.length > 0) extras.push(`Equip Slots: ${slotNames.join(", ")}`);
      if (isMasteryToken) extras.push("Mastery Token");
      if (out.canEquipFood) extras.push("Food");
      out.otherFeatures = Array.from(new Set(extras)).slice(0, 8);
      return out;
    };
    const entries = bank.items instanceof Map ? Array.from(bank.items.values()) : (bank.items?.allObjects ?? []);
    return {
        ok: true,
        count: entries.length,
        items: entries.slice(0, 500).map((e) => ({
            name: e?.item?.name ?? "Unknown",
            qty: Number(e?.quantity ?? 0),
            sellPrice: getSalePrice(e?.item),
            description: itemDescription(e?.item),
            ...inspectActions(e?.item),
        })),
    };
}"""

BANK_INFO_JS = """(query) => {
    const norm = (s) => String(s ?? "").toLowerCase().replace(/\\s+/g, " ").trim();
    const humanizeId = (id) =>
      String(id ?? "")
        .replace(/^melvor[A-Za-z]*:/, "")
        .replace(/_/g, " ")
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .replace(/\\s+/g, " ")
        .trim()
        .replace(/^./, (c) => c.toUpperCase());
    const toList = (v) => {
      if (v == null) return [];
      if (Array.isArray(v)) return v;
      if (v instanceof Set) return Array.from(v.values());
      if (v instanceof Map) return Array.from(v.values());
      if (typeof v?.allObjects?.forEach === "function") {
        const out = [];
        v.allObjects.forEach((x) => out.push(x));
        return out;
      }
      if (typeof v[Symbol.iterator] === "function") return Array.from(v);
      return [];
    };
    const coerceNumber = (x) => {
      if (typeof x === "number") return Number.isFinite(x) ? x : null;
      if (typeof x === "string" && x.trim() !== "" && !Number.isNaN(Number(x))) return Number(x);
      return null;
    };
    const stripHtml = (s) =>
      String(s ?? "")
        .replace(/<br\\s*\\/?>/gi, "\\n")
        .replace(/<[^>]+>/g, "")
        .replace(/\\s+\\n/g, "\\n")
        .replace(/\\n\\s+/g, "\\n")
        .replace(/\\s+/g, " ")
        .trim();
    const lookupStatName = (k) => {
      try {
        if (!k) return "";
        const id = typeof k === "string" ? k : (k.id ?? k.localID ?? "");
        const table = game?.modifierRegistry?.modifiers;
        const mod =
          table?.get?.(id) ??
          table?.get?.(`melvorD:${id}`) ??
          table?.get?.(`melvorF:${id}`) ??
          table?.get?.(`melvorTotH:${id}`) ??
          null;
        const n = mod?.name ?? mod?.description ?? "";
        return n ? stripHtml(n) : "";
      } catch (e) {
        return "";
      }
    };
    const collectEquipmentStats = (item) => {
      const out = [];
      const pushStat = (keyPart, valueRaw, isPercentHint = false) => {
        const name = lookupStatName(keyPart);
        const num = coerceNumber(valueRaw);
        const isPct =
          !!isPercentHint ||
          (typeof keyPart === "object" && keyPart && !!(keyPart.isPercent ?? keyPart.isPercentage));
        let label =
          name ||
          (typeof keyPart === "string" ? humanizeId(keyPart) : "") ||
          (keyPart && typeof keyPart === "object" && typeof keyPart.id === "string" ? humanizeId(keyPart.id) : "");
        if (!label && num == null && (valueRaw === undefined || valueRaw === null)) return;
        if (!label) label = "Unknown stat";
        out.push({ stat: label, value: num != null ? num : String(valueRaw ?? ""), isPercent: isPct });
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
        const valueRaw = st.value ?? st.modValue ?? st.modifier ?? st.amount ?? st.quantity ?? st.magnitude;
        const pct = !!(st.key?.isPercent ?? st.isPercent ?? st.isPercentage);
        pushStat(keyPart, valueRaw, pct);
      }
      return out;
    };
    const flattenReqNodes = (n, acc) => {
      if (n == null) return;
      if (typeof n === "string") return void acc.push(n);
      if (Array.isArray(n)) return void n.forEach((x) => flattenReqNodes(x, acc));
      if (typeof n === "object") {
        if (typeof n.textContent === "string" && n.textContent.trim()) return void acc.push(n.textContent);
        if (typeof n.innerText === "string" && n.innerText.trim()) return void acc.push(n.innerText);
        if (n.data != null) acc.push(String(n.data));
        if (Array.isArray(n.children)) flattenReqNodes(n.children, acc);
      }
    };
    const collectEquipRequirements = (item) => {
      const reqs = [];
      const rawReqs = item?.equipRequirements ?? item?.equipmentRequirements ?? item?._equipRequirements ?? item?._defaultEquipRequirements ?? [];
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
          if (req?.type === "SkillLevel") {
            const sk = String(req.skill?.name ?? req.skill?.localID ?? req.skill ?? "").trim();
            const lv = Number(req.level ?? req.skillLevel ?? req._level ?? NaN);
            const levelOnly = /^level\\s+\\d+$/i.test(txt) || /^requires\\s+level\\s+\\d+$/i.test(txt);
            if (sk && Number.isFinite(lv) && (!txt || levelOnly)) txt = `Requires ${sk} Level ${lv}`;
          }
        } catch (e) {}
        if (!txt && req?.type === "SkillLevel") {
          try {
            const sk = req.skill?.name ?? req.skill?.localID ?? req.skill ?? "";
            const lv = Number(req.level ?? req.skillLevel ?? req._level ?? NaN);
            if (sk && Number.isFinite(lv)) txt = `${sk} Level ${lv}`;
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
      if (!raw) raw = item.modifiedDescription ?? item.description ?? item.langDescription ?? item.descriptionHTML ?? "";
      return stripHtml(String(raw));
    };
    const readFoodHealing = (item) => {
      const candidates = [
        item?.healsFor,
        item?.healValue,
        item?.healingValue,
        item?.foodHealing,
        item?.healing,
      ];
      for (const v of candidates) {
        const n = coerceNumber(v);
        if (n != null && Number.isFinite(n) && n > 0) return n;
      }
      try {
        if (typeof item?.getHealingValue === "function") {
          const n = coerceNumber(item.getHealingValue());
          if (n != null && Number.isFinite(n) && n > 0) return n;
        }
      } catch (e) {}
      try {
        if (typeof item?.getFoodHealing === "function") {
          const n = coerceNumber(item.getFoodHealing());
          if (n != null && Number.isFinite(n) && n > 0) return n;
        }
      } catch (e) {}
      return null;
    };
    const readFoodHealingRaw = (item) => {
      const out = {};
      const add = (k, v) => {
        if (v === undefined || v === null) return;
        if (typeof v === "number") {
          if (Number.isFinite(v)) out[k] = v;
          return;
        }
        if (typeof v === "string") {
          const n = Number(v);
          out[k] = Number.isFinite(n) ? n : v;
          return;
        }
        out[k] = String(v);
      };
      add("healsFor", item?.healsFor);
      add("healValue", item?.healValue);
      add("healingValue", item?.healingValue);
      add("foodHealing", item?.foodHealing);
      add("healing", item?.healing);
      try {
        if (typeof item?.getHealingValue === "function") add("getHealingValue()", item.getHealingValue());
      } catch (e) {}
      try {
        if (typeof item?.getFoodHealing === "function") add("getFoodHealing()", item.getFoodHealing());
      } catch (e) {}
      return out;
    };

    const bank = game?.bank;
    if (!bank?.items) return { ok: false, error: "no_bank" };
    const queryNorm = norm(query);
    const entries = bank.items instanceof Map ? Array.from(bank.items.values()) : (bank.items?.allObjects ?? bank.items ?? []);
    const names = entries.map((entry) => ({
      entry,
      name: entry?.item?.name ?? "Unknown Item",
    }));
    const exact = names.filter((r) => norm(r.name) === queryNorm);
    let matches = exact;
    if (!matches.length) matches = names.filter((r) => norm(r.name).includes(queryNorm));
    if (!matches.length) return { ok: false, error: "not_found" };
    if (matches.length > 1) return { ok: false, error: "ambiguous", matches: matches.slice(0, 20).map((m) => m.name) };

    const entry = matches[0].entry;
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
    const out = {
      name: item?.name ?? "Unknown Item",
      qty: Number(entry?.quantity ?? 0),
      description: itemDescription(item),
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
    const itemName = String(item?.name ?? "");
    const typeName = String(item?.constructor?.name ?? "");
    const isEquipment =
      (typeof EquipmentItem !== "undefined" && item instanceof EquipmentItem) ||
      typeName === "EquipmentItem" ||
      typeName === "WeaponItem";
    const isOpenable =
      (typeof OpenableItem !== "undefined" && item instanceof OpenableItem) ||
      typeName === "OpenableItem";
    const isMasteryToken =
      (typeof MasteryTokenItem !== "undefined" && item instanceof MasteryTokenItem) ||
      typeName === "MasteryTokenItem";
    const canEquipFood =
      (typeof FoodItem !== "undefined" && item instanceof FoodItem) ||
      (Number.isFinite(out.foodHealing) && out.foodHealing > 0);
    out.canEquip = isEquipment || (Array.isArray(out.slots) && out.slots.length > 0) || canEquipFood;
    out.canClaim = isMasteryToken;
    out.canOpen = isOpenable;
    out.foodHealing = readFoodHealing(item);
    out.foodHealingRaw = readFoodHealingRaw(item);
    return { ok: true, item: out };
}"""

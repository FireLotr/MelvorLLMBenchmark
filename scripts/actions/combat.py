#!/usr/bin/env python3
"""
combat.py — Start combat with a monster or dungeon by clicking through the UI.

Usage:
  python scripts/actions/combat.py chicken             # fight a monster
  python scripts/actions/combat.py "junior farmer"
  python scripts/actions/combat.py "chicken coop"      # start a dungeon
  python scripts/actions/combat.py "volcanic cave"
  python scripts/actions/combat.py list                # list all monsters and dungeons
  python scripts/actions/combat.py loot                # collect loot without stopping combat
  python scripts/actions/combat.py stop                # stop combat and collect loot
  python scripts/actions/combat.py unequip food 1      # unequip food from slot 1 (1-3); fails early if bank full
  python scripts/actions/combat.py style stab          # set attack style (stab/slash/block)
  python scripts/actions/combat.py dungeon-eat "chicken coop" 35 [interval_ms]  # see README: prefer combat.py stop, then kill monitor

Must be on the Combat page first (use navigate.py combat).
"""

import sys, os, re, time
os.environ.setdefault("NODE_NO_WARNINGS", "1")
from playwright.sync_api import sync_playwright, Page
from _action_screenshots import take_action_screenshot
from _action_logging import log_action_call, log_action_result

CDP_URL = "http://localhost:9222"

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

AREAS = [
    {
        "id": "melvorD:Farmlands",
        "name": "Farmlands",
        "monsters": [
            {"id": "melvorD:Plant",         "name": "Plant",          "level": 1},
            {"id": "melvorD:Chicken",        "name": "Chicken",        "level": 1},
            {"id": "melvorD:Cow",            "name": "Cow",            "level": 2},
            {"id": "melvorD:JuniorFarmer",   "name": "Junior Farmer",  "level": 6},
            {"id": "melvorD:AdultFarmer",    "name": "Adult Farmer",   "level": 23},
            {"id": "melvorD:MasterFarmer",   "name": "Master Farmer",  "level": 47},
        ],
    },
    {
        "id": "melvorD:Goblin_Village",
        "name": "Golbin Village",
        "monsters": [
            {"id": "melvorD:Golbin",         "name": "Golbin",         "level": 2},
            {"id": "melvorD:RangedGolbin",   "name": "Ranged Golbin",  "level": 7},
        ],
    },
    {
        "id": "melvorD:Sandy_Shores",
        "name": "Sandy Shores",
        "monsters": [
            {"id": "melvorD:Seagull",        "name": "Seagull",        "level": 2},
            {"id": "melvorD:Tentacle",       "name": "Tentacle",       "level": 14},
            {"id": "melvorD:GiantCrab",      "name": "Giant Crab",     "level": 33},
            {"id": "melvorD:ConfusedPirate", "name": "Confused Pirate","level": 34},
        ],
    },
    {
        "id": "melvorD:Graveyard",
        "name": "Graveyard",
        "monsters": [
            {"id": "melvorD:Skeleton",       "name": "Skeleton",       "level": 7},
            {"id": "melvorD:ZombieHand",     "name": "Zombie Hand",    "level": 23},
            {"id": "melvorD:Zombie",         "name": "Zombie",         "level": 34},
            {"id": "melvorD:Ghost",          "name": "Ghost",          "level": 46},
        ],
    },
    {
        "id": "melvorD:Wet_Forest",
        "name": "Wet Forest",
        "monsters": [
            {"id": "melvorD:Leech",          "name": "Leech",          "level": 20},
            {"id": "melvorD:SweatyMonster",  "name": "Sweaty Monster", "level": 27},
            {"id": "melvorD:WetMonster",     "name": "Wet Monster",    "level": 34},
            {"id": "melvorD:MoistMonster",   "name": "Moist Monster",  "level": 35},
        ],
    },
    {
        "id": "melvorD:Castle_of_Kings",
        "name": "Castle of Kings",
        "monsters": [
            {"id": "melvorD:SteelKnight",    "name": "Steel Knight",   "level": 12},
            {"id": "melvorD:BlackKnight",    "name": "Black Knight",   "level": 23},
            {"id": "melvorD:MithrilKnight",  "name": "Mithril Knight", "level": 33},
            {"id": "melvorD:AdamantKnight",  "name": "Adamant Knight", "level": 69},
            {"id": "melvorD:RuneKnight",     "name": "Rune Knight",    "level": 101},
        ],
    },
    {
        "id": "melvorD:Bandit_Hideout",
        "name": "Bandit Hideout",
        "monsters": [
            {"id": "melvorD:BanditTrainee",  "name": "Bandit Trainee", "level": 23},
            {"id": "melvorD:Bandit",         "name": "Bandit",         "level": 44},
        ],
    },
    {
        "id": "melvorD:Giant_Dungeon",
        "name": "Giant Dungeon",
        "monsters": [
            {"id": "melvorD:HillGiant",      "name": "Hill Giant",     "level": 28},
            {"id": "melvorD:MossGiant",      "name": "Moss Giant",     "level": 60},
        ],
    },
    {
        "id": "melvorD:Wizard_Tower",
        "name": "Wizard Tower",
        "monsters": [
            {"id": "melvorD:Wizard",         "name": "Wizard",         "level": 32},
            {"id": "melvorD:MasterWizard",   "name": "Master Wizard",  "level": 56},
            {"id": "melvorD:DarkWizard",     "name": "Dark Wizard",    "level": 108},
        ],
    },
    {
        "id": "melvorD:Icy_Hills",
        "name": "Icy Hills",
        "monsters": [
            {"id": "melvorD:FrozenArcher",   "name": "Frozen Archer",  "level": 27},
            {"id": "melvorD:FrozenMammoth",  "name": "Frozen Mammoth", "level": 58},
            {"id": "melvorD:IceMonster",     "name": "Ice Monster",    "level": 75},
        ],
    },
    {
        "id": "melvorD:Dragon_Valley",
        "name": "Dragon Valley",
        "monsters": [
            {"id": "melvorD:GreenDragon",    "name": "Green Dragon",   "level": 79},
            {"id": "melvorD:BlueDragon",     "name": "Blue Dragon",    "level": 90},
            {"id": "melvorD:RedDragon",      "name": "Red Dragon",     "level": 106},
            {"id": "melvorD:BlackDragon",    "name": "Black Dragon",   "level": 120},
        ],
    },
    {
        "id": "melvorD:ElerineBattlegrounds",
        "name": "Elerine Battlegrounds",
        "monsters": [
            {"id": "melvorD:ElerineArcher",  "name": "Elerine Archer", "level": 73},
            {"id": "melvorD:ElerineWarrior", "name": "Elerine Warrior","level": 96},
            {"id": "melvorD:ElerineMage",    "name": "Elerine Mage",   "level": 103},
        ],
    },
]

DUNGEONS = [
    {"id": "melvorD:Chicken_Coop",      "name": "Chicken Coop",      "max_level": 39,  "boss": "Mumma Chicken"},
    {"id": "melvorD:Undead_Graveyard",  "name": "Undead Graveyard",  "max_level": 71,  "boss": "Zombie Leader"},
    {"id": "melvorD:Bandit_Base",       "name": "Bandit Base",       "max_level": 115, "boss": "Bandit Leader"},
    {"id": "melvorD:Hall_of_Wizards",   "name": "Hall of Wizards",   "max_level": 121, "boss": "Elder Wizard"},
    {"id": "melvorD:Spider_Forest",     "name": "Spider Forest",     "max_level": 158, "boss": "Spider King"},
    {"id": "melvorD:Deep_Sea_Ship",     "name": "Deep Sea Ship",     "max_level": 177, "boss": "The Kraken"},
    {"id": "melvorD:Frozen_Cove",       "name": "Frozen Cove",       "max_level": 191, "boss": "Protector of Ice"},
    {"id": "melvorD:Volcanic_Cave",     "name": "Volcanic Cave",     "max_level": 677, "boss": "Malcs, the Guardian of Melvor"},
]

# Flat lookups keyed by lowercase name
MONSTER_LOOKUP = {
    m["name"].lower(): {"area_name": a["name"], "monster_id": m["id"],
                        "monster_name": m["name"], "level": m["level"]}
    for a in AREAS for m in a["monsters"]
}
DUNGEON_LOOKUP = {d["name"].lower(): d for d in DUNGEONS}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_melvor_page(pw):
    browser = pw.chromium.connect_over_cdp(CDP_URL)
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "melvor" in pg.url.lower():
                return pg
    return browser.contexts[0].pages[0]


def is_on_combat_page(page: Page) -> bool:
    return (
        page.locator("#combat-area-category-menu").first.is_visible()
        or page.locator("#combat-btn-run").first.is_visible()
        or page.locator("#combat-loot").first.is_visible()
        or page.locator("#combat-food-select").first.is_visible()
    )


def ensure_area_cards_visible(page: Page, tab: str) -> bool:
    """Make the area card grid visible and switch to the given tab ('Combat Areas' or 'Dungeons')."""
    tab = tab.strip()

    def _cards_visible() -> bool:
        cards = page.locator("combat-area-menu .block.pointer-enabled")
        for i in range(cards.count()):
            if cards.nth(i).is_visible():
                return True
        return False

    # Step 1: Stop active combat if the enemy HP bar is visible (we are in a fight).
    if page.locator("#combat-enemy-hitpoints-bar").is_visible():
        run_btn = page.locator("#combat-btn-run")
        if run_btn.count() > 0 and run_btn.first.is_visible():
            print("Stopping active combat (Run / Area Select)...")
            run_btn.first.click()
            page.wait_for_timeout(700)

    # Step 2: If cards are already visible (correct tab already open), skip tab click.
    if _cards_visible():
        return True

    # Step 3: Open the area selector panel if the target tab link is not visible.
    # "Select Combat Area" is a toggle — only click it when the panel is closed.
    tab_links = page.locator("#combat-area-category-menu a").filter(has_text=tab)
    visible_tab = None
    for i in range(tab_links.count()):
        if tab_links.nth(i).is_visible():
            visible_tab = tab_links.nth(i)
            break

    if visible_tab is None:
        select_btn = page.locator("#combat-area-category-menu").get_by_text("Select Combat Area")
        if select_btn.count() > 0 and select_btn.first.is_visible():
            select_btn.first.click()
            page.wait_for_timeout(400)
        for i in range(tab_links.count()):
            if tab_links.nth(i).is_visible():
                visible_tab = tab_links.nth(i)
                break

    if visible_tab is None:
        print(f"Could not find a visible tab control for '{tab}'.")
        return False

    # Step 4: Click the tab and wait for content.
    visible_tab.click()
    page.wait_for_timeout(600)

    # Step 5: Verify with short retries.
    for _ in range(5):
        if _cards_visible():
            return True
        page.wait_for_timeout(200)

    print(f"Area cards not visible after switching to '{tab}'.")
    return False


def _partial_match(key: str, lookup: dict) -> str | None:
    """Return the single matching key from lookup, or None (with printed message)."""
    if key in lookup:
        return key
    matches = [k for k in lookup if key in k]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(lookup[k].get("name", lookup[k].get("monster_name", k)) for k in matches)
        print(f"Ambiguous: '{key}' matches: {names}")
    return None


def _click_first_visible(candidates) -> bool:
    """Click the first visible locator candidate."""
    for loc in candidates:
        try:
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.click()
                return True
        except Exception:
            continue
    return False


def _combat_food_scope(page: Page):
    """Visible combat food UI root (avoid matching other dropdowns / Unequip buttons)."""
    for sel in ("#combat-food-select", "#combat-food-container"):
        loc = page.locator(sel).first
        try:
            if loc.count() > 0 and loc.is_visible():
                return loc
        except Exception:
            continue
    return page.locator("#combat-food-select").first


def _food_slot_is_empty(page: Page, slot: int) -> bool:
    """True if combat food slot (1-based) has no real food (same idea as observations/equipment.py)."""
    try:
        return bool(
            page.evaluate(
                """(slot1) => {
                    const idx = slot1 - 1;
                    const s = game?.combat?.player?.food?.slots?.[idx];
                    if (!s) return true;
                    const id = String(s.item?.id ?? '');
                    const q = Number(s.quantity ?? 0);
                    return !id || id.endsWith('Empty_Food') || q <= 0;
                }""",
                slot,
            )
        )
    except Exception:
        return False


def _bank_is_full(page: Page) -> bool | None:
    """True if the bank has no room for another stack (unequip food needs bank space). None if unknown."""
    try:
        data = page.evaluate(
            """() => {
                const bank = game?.bank;
                if (!bank) return { ok: false, full: null };
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

                let full = null;
                try {
                    if (typeof bank.isFull === "function") full = !!bank.isFull();
                } catch (e) {}
                if (full === null) {
                    let free = null;
                    try {
                        if (typeof bank.getFreeSlots === "function") free = asNum(bank.getFreeSlots());
                    } catch (e) {}
                    if (free === null) free = asNum(bank.freeSlots);
                    if (free !== null) full = free <= 0;
                }
                if (full === null && used !== null && max !== null && max > 0) full = used >= max;

                return { ok: true, full, used, max };
            }"""
        )
    except Exception:
        return None
    if not data or not data.get("ok"):
        return None
    f = data.get("full")
    if f is None:
        return None
    return bool(f)


def _open_combat_food_dropdown(page: Page, scope) -> bool:
    """Open the food dropdown under the combat food container only."""
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(120)
    except Exception:
        pass
    candidates = [
        scope.locator("button.dropdown-toggle").first,
        scope.locator('[data-toggle="dropdown"]').first,
    ]
    return _click_first_visible(candidates)


def _click_nth_visible_unequip_in_food_menu(scope, slot: int) -> bool:
    """When the open food menu lists one Unequip per slot row, click the Nth visible Unequip (1-based)."""
    menu = scope.locator(".dropdown-menu.show").first
    if menu.count() == 0:
        return False
    try:
        menu.wait_for(state="visible", timeout=2500)
    except Exception:
        pass
    unequip = menu.locator("button, a").filter(has_text=re.compile(r"unequip", re.I))
    visible = []
    n = min(unequip.count(), 24)
    for i in range(n):
        el = unequip.nth(i)
        try:
            if el.is_visible():
                visible.append(el)
        except Exception:
            continue
    if len(visible) >= slot:
        visible[slot - 1].click()
        return True
    if len(visible) == 1 and slot == 1:
        visible[0].click()
        return True
    return False


def _pick_visible(locator):
    """Return a visible element from locator set, or first as fallback."""
    count = locator.count()
    if count == 0:
        return None
    for i in range(count):
        item = locator.nth(i)
        try:
            if item.is_visible():
                return item
        except Exception:
            continue
    return locator.first


def _find_visible_area_card_by_text(page: Page, text: str):
    """Find a visible combat/dungeon area card containing text."""
    cards = page.locator("combat-area-menu .block.pointer-enabled")
    target = text.strip().lower()
    total = cards.count()
    for i in range(total):
        card = cards.nth(i)
        try:
            if not card.is_visible():
                continue
            label = (card.text_content() or "").strip().lower()
            if target in label:
                return card
        except Exception:
            continue
    return None


def unequip_food(arg: str) -> bool:
    """Unequip food from combat food slot (1-3) parsed from command arg."""
    parts = arg.split()
    slot = int(parts[2]) if len(parts) >= 3 else 1

    if slot < 1 or slot > 3:
        print("Food slot must be 1, 2, or 3.")
        return False

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not is_on_combat_page(page):
            print("Not on the Combat page. Run: python scripts/actions/navigate.py combat")
            return False

        try:
            page.wait_for_function(
                "() => typeof game !== 'undefined' && !!game.combat?.player?.food?.slots",
                timeout=8000,
            )
        except Exception:
            pass

        bank_full = _bank_is_full(page)
        if bank_full is True:
            print(
                "Bank is full — unequipping combat food sends it to the bank, so there is no room. "
                "Free at least one bank slot (e.g. sell or move items), then try again."
            )
            return False

        if _food_slot_is_empty(page, slot):
            print(f"Combat food slot {slot} is already empty.")
            return True

        scope = _combat_food_scope(page)
        if scope.count() == 0:
            print("Could not find the combat food UI (#combat-food-select / #combat-food-container).")
            return False

        def _verify() -> bool:
            page.wait_for_timeout(350)
            return _food_slot_is_empty(page, slot)

        # Strategy A: menu lists Unequip per row — click Nth Unequip inside food scope only (never page-wide).
        if _open_combat_food_dropdown(page, scope):
            page.wait_for_timeout(220)
            try:
                scope.locator(".dropdown-menu.show").first.wait_for(state="visible", timeout=3000)
            except Exception:
                pass
            if _click_nth_visible_unequip_in_food_menu(scope, slot) and _verify():
                print(f"Unequipped combat food in slot {slot}.")
                return True

        page.keyboard.press("Escape")
        page.wait_for_timeout(150)

        # Strategy B: select slot then Unequip — all locators scoped to combat food menu (not equipment).
        if not _open_combat_food_dropdown(page, scope):
            print("Could not open the combat food dropdown.")
            return False
        page.wait_for_timeout(220)
        try:
            scope.locator(".dropdown-menu.show").first.wait_for(state="visible", timeout=3000)
        except Exception:
            pass

        menu = scope.locator(".dropdown-menu.show").first
        slot_selected = _click_first_visible(
            [
                menu.locator("button").filter(has_text=f"Slot {slot}"),
                menu.locator("a").filter(has_text=f"Slot {slot}"),
                menu.locator("button").filter(has_text=f"Food {slot}"),
                menu.locator("a").filter(has_text=f"Food {slot}"),
            ]
        )

        if not slot_selected:
            options = menu.locator("button, a")
            total = min(options.count(), 40)
            visible_non_unequip = []
            for i in range(total):
                opt = options.nth(i)
                if not opt.is_visible():
                    continue
                label = (opt.text_content() or "").strip().lower()
                if "unequip" in label:
                    continue
                visible_non_unequip.append(opt)
            if len(visible_non_unequip) >= slot:
                visible_non_unequip[slot - 1].click()
                slot_selected = True

        if not slot_selected:
            print(f"Could not select food slot {slot} in the combat food menu.")
            page.keyboard.press("Escape")
            return False
        page.wait_for_timeout(220)

        if not _open_combat_food_dropdown(page, scope):
            print("Selected slot, but could not reopen the combat food dropdown.")
            return False
        page.wait_for_timeout(200)
        try:
            scope.locator(".dropdown-menu.show").first.wait_for(state="visible", timeout=3000)
        except Exception:
            pass

        menu2 = scope.locator(".dropdown-menu.show").first
        unequipped = _click_first_visible(
            [
                menu2.locator("button").filter(has_text=re.compile(r"unequip", re.I)),
                menu2.locator("a").filter(has_text=re.compile(r"unequip", re.I)),
            ]
        )
        if not unequipped:
            print("Could not find Unequip in the combat food dropdown (scoped to food UI only).")
            page.keyboard.press("Escape")
            return False

        if _verify():
            print(f"Unequipped combat food in slot {slot}.")
            return True

        print(
            f"Clicked Unequip in the food menu, but game state still shows food in slot {slot}. "
            "Close other dropdowns and try again, or unequip from the in-game food menu manually."
        )
        page.keyboard.press("Escape")
        return False


def set_attack_style(arg: str) -> bool:
    """Set melee attack style via combat UI buttons."""
    parts = arg.split()
    if len(parts) < 2:
        print("Usage: python scripts/actions/combat.py style <stab|slash|block>")
        return False

    style_key = parts[1].strip().lower()
    style_map = {
        "stab": "Stab",
        "slash": "Slash",
        "block": "Block",
    }
    if style_key not in style_map:
        print(f"Unknown style: '{parts[1]}'. Use stab, slash, or block.")
        return False
    style_label = style_map[style_key]

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not is_on_combat_page(page):
            print("Not on the Combat page. Run: python scripts/actions/navigate.py combat")
            return False

        btn = page.locator(f'button[id="combat-attack-style-button-melvorD:{style_label}"]')
        if btn.count() == 0:
            btn = page.locator("button").filter(has_text=style_label).first
        if btn.count() == 0 or not btn.first.is_visible():
            print(f"Could not find combat attack style button: {style_label}")
            return False

        btn.first.click()
        page.wait_for_timeout(200)
        print(f"Set combat style to: {style_label}")
        return True


def _read_player_hp(page: Page) -> tuple[int | None, int | None]:
    """Read player HP/max HP from visible combat DOM labels."""
    def _to_int(text: str | None) -> int | None:
        if text is None:
            return None
        m = re.search(r"\d+", text)
        return int(m.group(0)) if m else None

    cur_locators = [
        page.locator("#combat-player-hitpoints-current"),
        page.locator("#combat-player-hitpoints-current-1"),
        page.locator("#nav-hitpoints-current"),
    ]
    max_locators = [
        page.locator("#combat-player-hitpoints-max"),
        page.locator("#combat-player-hitpoints-max-1"),
    ]

    hp = None
    max_hp = None
    for loc in cur_locators:
        if loc.count() > 0 and loc.first.is_visible():
            hp = _to_int((loc.first.text_content() or "").strip())
            if hp is not None:
                break
    for loc in max_locators:
        if loc.count() > 0 and loc.first.is_visible():
            max_hp = _to_int((loc.first.text_content() or "").strip())
            if max_hp is not None:
                break
    return hp, max_hp


def run_dungeon_with_manual_eat(argv: list[str]) -> bool:
    """
    Start a dungeon and keep manually eating while HP <= threshold.
    Usage: combat.py dungeon-eat "<dungeon>" <hp_threshold> [interval_ms]
    """
    if len(argv) < 4:
        print("Usage: python scripts/actions/combat.py dungeon-eat \"<dungeon>\" <hp_threshold> [interval_ms]")
        return False

    dungeon_name = argv[2].strip()
    if not dungeon_name:
        print("Dungeon name cannot be empty.")
        return False

    try:
        hp_threshold = int(argv[3])
    except Exception:
        print(f"Invalid HP threshold: '{argv[3]}'.")
        return False
    if hp_threshold <= 0:
        print("HP threshold must be > 0.")
        return False

    interval_ms = 1000
    if len(argv) >= 5:
        try:
            interval_ms = int(argv[4])
        except Exception:
            print(f"Invalid interval_ms: '{argv[4]}'.")
            return False
    if interval_ms < 200:
        interval_ms = 200

    # Dungeon-only by design: this command always starts a dungeon target.
    if not start_dungeon(dungeon_name):
        return False

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not is_on_combat_page(page):
            print("Not on the Combat page. Run: python scripts/actions/navigate.py combat")
            return False

        print(
            f"Dungeon auto-eat monitor active: dungeon='{dungeon_name}', "
            f"threshold={hp_threshold}, interval={interval_ms}ms"
        )
        print(
            "To exit safely: run combat.py stop in another terminal first, then Ctrl+C here. "
            "(Ctrl+C alone tries stop+loot but is slow — you can die before combat stops.)"
        )

        area_cards = page.locator("combat-area-menu").first.locator(".block.pointer-enabled")
        eat_button = page.locator("#combat-footer-minibar-eat-btn")
        tick = 0

        try:
            while True:
                tick += 1

                # If area cards are visible again, active combat likely ended.
                if area_cards.count() > 0 and area_cards.first.is_visible():
                    print("Dungeon combat is no longer active. Stopping monitor.")
                    return True

                hp, max_hp = _read_player_hp(page)
                if hp is None or max_hp is None:
                    print("Could not read HP from UI. Retrying...")
                    time.sleep(interval_ms / 1000.0)
                    continue

                if hp <= hp_threshold:
                    ate = False
                    for _ in range(4):
                        if eat_button.count() > 0 and eat_button.first.is_visible() and eat_button.first.is_enabled():
                            eat_button.first.click()
                            ate = True
                            page.wait_for_timeout(120)
                            hp_after, _ = _read_player_hp(page)
                            if hp_after is not None:
                                hp = hp_after
                                if hp > hp_threshold:
                                    break
                        else:
                            break
                    print(f"[tick {tick}] HP {hp}/{max_hp} <= {hp_threshold} -> {'ate' if ate else 'could not eat'}")
                elif tick % 10 == 0:
                    # Keep periodic status output so the process does not look stuck.
                    print(f"[tick {tick}] HP {hp}/{max_hp} (ok)")

                # Use wall-clock sleep so Ctrl+C is not tied to Playwright's internal timeout futures.
                time.sleep(interval_ms / 1000.0)
        except KeyboardInterrupt:
            print("Interrupt received — stopping combat and collecting loot...")
            try:
                stop_combat_and_loot_on_page(page)
            except Exception as ex:
                print(f"Automatic stop/loot after interrupt failed: {ex}")
            time.sleep(0.15)
            return True


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def list_all():
    print("Monsters (non-dungeon):\n")
    for area in AREAS:
        print(f"  {area['name']}:")
        for m in area["monsters"]:
            print(f"    {m['name']:<22} level {m['level']}")
    print("\nDungeons:\n")
    for d in DUNGEONS:
        print(f"  {d['name']:<22} max level {d['max_level']} ({d['boss']})")
    print()


def fight(target: str) -> bool:
    key = _partial_match(target.strip().lower(), MONSTER_LOOKUP)
    if key is None:
        print(f"Unknown monster: '{target}'. Run with 'list' to see all options.")
        return False
    entry = MONSTER_LOOKUP[key]

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not is_on_combat_page(page):
            print("Not on the Combat page. Run: python scripts/actions/navigate.py combat")
            return False

        print(f"Target: {entry['monster_name']} (level {entry['level']}) in {entry['area_name']}")

        if not ensure_area_cards_visible(page, "Combat Areas"):
            return False

        # Only toggle the area card if target monster row is hidden.
        area_card = _find_visible_area_card_by_text(page, entry["area_name"])
        if area_card is None:
            print(f"Could not find area card for {entry['area_name']}.")
            return False
        monster_imgs = page.locator(f'[id="monster-area-img-{entry["monster_id"]}"]')
        monster_img = _pick_visible(monster_imgs)
        fight_btn = None if monster_img is None else _pick_visible(
            monster_img.locator("xpath=ancestor::tr").locator("button.btn-danger")
        )

        if fight_btn is None or not fight_btn.is_visible():
            if not area_card.is_visible():
                print(f"Area card for {entry['area_name']} is not visible.")
                return False
            area_card.click()
            page.wait_for_timeout(400)
            monster_img = _pick_visible(monster_imgs)
            fight_btn = None if monster_img is None else _pick_visible(
                monster_img.locator("xpath=ancestor::tr").locator("button.btn-danger")
            )
        if fight_btn is None or not fight_btn.is_visible():
            print(f"Could not make {entry['monster_name']} row visible in {entry['area_name']}.")
            return False

        # Click Fight in the monster's row
        fight_btn.click()
        page.wait_for_timeout(300)

        print(f"Started combat with {entry['monster_name']}!")
        return True


def start_dungeon(target: str) -> bool:
    key = _partial_match(target.strip().lower(), DUNGEON_LOOKUP)
    if key is None:
        print(f"Unknown dungeon: '{target}'. Run with 'list' to see all options.")
        return False
    entry = DUNGEON_LOOKUP[key]

    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not is_on_combat_page(page):
            print("Not on the Combat page. Run: python scripts/actions/navigate.py combat")
            return False

        print(f"Target dungeon: {entry['name']}")

        if not ensure_area_cards_visible(page, "Dungeons"):
            return False

        # Only toggle the dungeon card if Start button is hidden.
        dungeon_card = _find_visible_area_card_by_text(page, entry["name"])
        if dungeon_card is None:
            print(f"Could not find dungeon card for {entry['name']}.")
            return False

        start_btns = (
            page.locator("combat-area-menu")
            .filter(has_text=entry["name"])
            .locator("dungeon-select button")
        )
        start_btn = _pick_visible(start_btns)
        if start_btn is None:
            print(f"Could not find Start Dungeon button for {entry['name']}.")
            return False
        if not start_btn.is_visible():
            dungeon_card.click()
            page.wait_for_timeout(400)
            start_btn = _pick_visible(start_btns)
        if start_btn is None or not start_btn.is_visible():
            print(f"Could not make Start Dungeon visible for {entry['name']}.")
            return False

        # Click Start Dungeon
        start_btn.click()
        page.wait_for_timeout(300)

        print(f"Started dungeon: {entry['name']}!")
        return True


def _collect_loot_on_page(page: Page) -> None:
    loot_btn = page.locator("#combat-loot button.btn-success").filter(has_text="Loot All")
    try:
        if loot_btn.count() > 0 and loot_btn.first.is_visible():
            print("Collecting loot...")
            loot_btn.first.click()
            page.wait_for_timeout(300)
            print("Loot collected.")
        else:
            print("No loot to collect.")
    except Exception as ex:
        print(f"Loot step skipped: {ex}")


def _stop_combat_on_page(page: Page) -> None:
    """Click Run / leave combat if the control is visible (same as combat.py stop)."""
    run_btn = page.locator("#combat-btn-run")
    try:
        if run_btn.count() > 0 and run_btn.first.is_visible():
            print("Stopping combat...")
            run_btn.first.click()
            page.wait_for_timeout(400)
        else:
            print("Run button not visible (combat may already be inactive).")
    except Exception as ex:
        print(f"Could not click Run: {ex}")


def stop_combat_and_loot_on_page(page: Page) -> bool:
    """Stop active combat and collect loot; for use when a Page is already held (e.g. dungeon-eat interrupt)."""
    if not is_on_combat_page(page):
        print("Not on the Combat page. Run: python scripts/actions/navigate.py combat")
        return False
    _stop_combat_on_page(page)
    _collect_loot_on_page(page)
    return True


def collect_loot() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        if not is_on_combat_page(page):
            print("Not on the Combat page. Run: python scripts/actions/navigate.py combat")
            return False

        loot_btn = page.locator("#combat-loot button.btn-success").filter(has_text="Loot All")
        if loot_btn.is_visible():
            print("Collecting loot...")
            loot_btn.click()
            page.wait_for_timeout(300)
            print("Loot collected.")
        else:
            print("No loot to collect.")
        return True


def stop_and_loot() -> bool:
    with sync_playwright() as pw:
        page = get_melvor_page(pw)
        return stop_combat_and_loot_on_page(page)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log_action_call("combat.py", sys.argv[1:])
    if len(sys.argv) < 2:
        log_action_result("combat.py", sys.argv[1:], False, details="Missing target/command.")
        print(__doc__)
        sys.exit(1)

    arg = " ".join(sys.argv[1:]).strip()
    low = arg.lower()

    if low == "list":
        list_all()
        log_action_result("combat.py", sys.argv[1:], True, details="Listed combat targets.")
    elif low == "loot":
        before = take_action_screenshot("before", "combat_loot")
        ok = collect_loot()
        after = take_action_screenshot("after", "combat_loot")
        log_action_result("combat.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)
    elif low == "stop":
        before = take_action_screenshot("before", "combat_stop")
        ok = stop_and_loot()
        after = take_action_screenshot("after", "combat_stop")
        log_action_result("combat.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)
    elif low.startswith("dungeon-eat "):
        before = take_action_screenshot("before", f"combat_{low}")
        ok = run_dungeon_with_manual_eat(sys.argv)
        after = take_action_screenshot("after", f"combat_{low}")
        log_action_result("combat.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)
    elif low.startswith("style "):
        before = take_action_screenshot("before", f"combat_{low}")
        ok = set_attack_style(arg)
        after = take_action_screenshot("after", f"combat_{low}")
        log_action_result("combat.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)
    elif low.startswith("unequip food"):
        before = take_action_screenshot("before", f"combat_{low}")
        ok = unequip_food(arg)
        after = take_action_screenshot("after", f"combat_{low}")
        log_action_result("combat.py", sys.argv[1:], ok, before, after)
        sys.exit(0 if ok else 1)
    else:
        # Try monster first, then dungeon (avoids "chicken" matching "Chicken Coop")
        if _partial_match(low, MONSTER_LOOKUP) is not None:
            before = take_action_screenshot("before", f"combat_fight_{low}")
            ok = fight(arg)
            after = take_action_screenshot("after", f"combat_fight_{low}")
            log_action_result("combat.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        elif _partial_match(low, DUNGEON_LOOKUP) is not None:
            before = take_action_screenshot("before", f"combat_dungeon_{low}")
            ok = start_dungeon(arg)
            after = take_action_screenshot("after", f"combat_dungeon_{low}")
            log_action_result("combat.py", sys.argv[1:], ok, before, after)
            sys.exit(0 if ok else 1)
        else:
            log_action_result("combat.py", sys.argv[1:], False, details=f"Unknown target: {arg}")
            print(f"Unknown target: '{arg}'. Run with 'list' to see all options.")
            sys.exit(1)

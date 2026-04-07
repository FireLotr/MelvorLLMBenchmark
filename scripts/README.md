# Scripts

Structure:
- `scripts/actions/` — scripts that perform in-game actions
- `scripts/observations/` — read-only scripts for state inspection

Most action scripts use Playwright UI clicks. `navigate.py` is an exception: it calls the in-game `sidebar` JavaScript API (same as the wiki Sidebar API) for reliable page changes.
Chrome must be running with remote debugging on port 9222.

## Shared behavior (all scripts)

- Action calls/results are appended to `logs/actions.log` (JSONL).
- Observation calls/results (including printed output) are appended to `logs/observations.log` (JSONL).
- Failed actions append a human-readable entry to `error.txt` with command + log pointers.
- **Action scripts:** On each run, `log_action_call` runs first. If the **You Died** SweetAlert modal is open, it is dismissed (OK), a loud alert is printed, `error.txt` and `actions.log` get a **blocked** result, and the process **exits with code 1** without running the action body.
- If **You Died** appears **after** an action (via `log_action_result`), the same alert/`error.txt` behavior runs (the action already ran).

---

## navigate.py — Go to a game page

```
venv/bin/python scripts/actions/navigate.py <page>
```

Calls `sidebar.category(...).item(...).click()` in the game context (no DOM menu clicking). Waits until `game.openPage.id` matches the target.

**Available pages:** attack, strength, defence, hitpoints, farming, woodcutting, fishing, firemaking, cooking, mining, smithing, bank, shop, combat

**Example:**
```
venv/bin/python scripts/actions/navigate.py woodcutting
venv/bin/python scripts/actions/navigate.py bank
venv/bin/python scripts/actions/navigate.py shop
venv/bin/python scripts/actions/navigate.py farming
venv/bin/python scripts/actions/navigate.py combat
```

---

## combat.py — Start fighting a monster or dungeon

```
venv/bin/python scripts/actions/combat.py <monster or dungeon name>
venv/bin/python scripts/actions/combat.py list
venv/bin/python scripts/actions/combat.py loot
venv/bin/python scripts/actions/combat.py stop
venv/bin/python scripts/actions/combat.py unequip food [slot]
venv/bin/python scripts/actions/combat.py style <stab|slash|block>
venv/bin/python scripts/actions/combat.py dungeon-eat "<dungeon>" <hp_threshold> [interval_ms]
```

Must already be on the Combat page (`actions/navigate.py combat`). If combat is already active, automatically
clicks "Run / Area Select" to stop it first. Partial name matching is supported.

- Monster names → navigates to Combat Areas tab, expands the area card, clicks Fight
- Dungeon names → navigates to Dungeons tab, expands the dungeon card, clicks Start Dungeon
- `loot` — collect all pending loot without stopping combat
- `stop` — stop combat and collect all pending loot
- `unequip food [slot]` — open the combat food selector, choose slot (1-3, default 1), then unequip that slot
- `style <stab|slash|block>` — set melee attack style using the combat style buttons
- `dungeon-eat "<dungeon>" <hp_threshold> [interval_ms]` — dungeon-only: starts the dungeon, then keeps checking HP and clicks manual eat when HP is at/below threshold until dungeon combat ends naturally
- **Stopping `dungeon-eat` safely:** Prefer **`combat.py stop`** first so combat ends right away, **then** stop the monitor with **Ctrl+C** (or close the terminal). The monitor’s built-in interrupt path runs stop + loot in one go and is **slow**; in combat you can die before that sequence finishes. Use a **second terminal** for `venv/bin/python scripts/actions/combat.py stop` while `dungeon-eat` keeps running, then interrupt the monitor.

**Dungeons:** Chicken Coop, Undead Graveyard, Bandit Base, Hall of Wizards, Spider Forest, Deep Sea Ship, Frozen Cove, Volcanic Cave

**Available monsters (non-dungeon):**

| Area              | Monsters (level)                                                                 |
|-------------------|----------------------------------------------------------------------------------|
| Farmlands         | Plant (1), Chicken (1), Cow (2), Junior Farmer (6), Adult Farmer (23), Master Farmer (47) |
| Golbin Village    | Golbin (2), Ranged Golbin (7)                                                    |
| Sandy Shores      | Seagull (2), Tentacle (14), Giant Crab (33), Confused Pirate (34)               |
| Graveyard         | Skeleton (7), Zombie Hand (23), Zombie (34), Ghost (46)                         |
| Wet Forest        | Leech (20), Sweaty Monster (27), Wet Monster (34), Moist Monster (35)           |
| Castle of Kings   | Steel Knight (12), Black Knight (23), Mithril Knight (33), Adamant Knight (69), Rune Knight (101) |
| Bandit Hideout    | Bandit Trainee (23), Bandit (44)                                                 |
| Giant Dungeon     | Hill Giant (28), Moss Giant (60)                                                 |
| Wizard Tower      | Wizard (32), Master Wizard (56), Dark Wizard (108)                              |
| Icy Hills         | Frozen Archer (27), Frozen Mammoth (58), Ice Monster (75)                       |
| Dragon Valley     | Green Dragon (79), Blue Dragon (90), Red Dragon (106), Black Dragon (120)       |
| Elerine Battlegrounds | Elerine Archer (73), Elerine Warrior (96), Elerine Mage (103)               |

**Example:**
```
venv/bin/python scripts/actions/navigate.py combat
venv/bin/python scripts/actions/combat.py chicken
venv/bin/python scripts/actions/combat.py "junior farmer"
venv/bin/python scripts/actions/combat.py "chicken coop"
venv/bin/python scripts/actions/combat.py "volcanic cave"
venv/bin/python scripts/actions/combat.py list
venv/bin/python scripts/actions/combat.py loot
venv/bin/python scripts/actions/combat.py stop
venv/bin/python scripts/actions/combat.py unequip food 1
venv/bin/python scripts/actions/combat.py style stab
venv/bin/python scripts/actions/combat.py dungeon-eat "chicken coop" 35
```

---

## farming.py — Farming actions

```
venv/bin/python scripts/actions/farming.py harvest-all [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py compost-all [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py weird-gloop-all [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py plant-all <seed_name> [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py plant-all-selected [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py plant <seed_name> [plot] [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py select-seed <seed_name> [plot] [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py harvest [plot] [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py compost [plot] [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py weird-gloop [plot] [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py clear [plot] [allotment|herb|tree]
venv/bin/python scripts/actions/farming.py unlock <plot> [allotment|herb|tree]
```

Auto-navigates to Farming if not already there. Category defaults to `allotment`. Plot defaults to `1`.

- `compost` / `compost-all` — apply compost to empty plots only (before planting); fails with message if no compost in bank
- `weird-gloop` / `weird-gloop-all` — apply Weird Gloop compost variant
- `plant-all <seed>` — plants all eligible plots in the selected category using one seed type
- `plant-all-selected` — plants all using each plot's currently selected seed
- `plant` — opens seed modal and plants; requires 3+ seeds in bank
- `select-seed` — set per-plot selected seed (used by `plant-all-selected`)
- `harvest` / `harvest-all` — harvest ready plots
- `clear` — destroy a dead crop
- `unlock` — unlock a locked plot (uses plot numbers from `observations/farming.py plots`)

## observations/farming.py — Read-only farming state

```
venv/bin/python scripts/observations/farming.py plots
```

Works from any page (auto-navigates to Farming). Lists all plots across Allotments, Herbs, and Trees with state (empty/growing/ready/dead/locked), compost status, grow timer, per-crop XP, base grow interval, and unlock requirements. Only **visible** plot nodes for each tab are counted (inactive categories stay in the DOM but hidden).

---

## fishing.py — Fishing actions

```
venv/bin/python scripts/actions/fishing.py start "<fish name>"
venv/bin/python scripts/actions/fishing.py stop
```

Works from any page (auto-navigates to Fishing).

- `start` — selects the fish and clicks Start Fishing (new target replaces current fishing without stopping first)
- handles collapsed fishing area cards by expanding target area when needed
- `stop` — clicks Stop Fishing when that control exists (idle state may leave no Stop button even if the game still names a “selected” area)

---

## observations/fishing.py — Read-only fishing state

```
venv/bin/python scripts/observations/fishing.py list
```

Works from any page (auto-navigates to Fishing).

- lists fishing areas
- lists fish in each area
- shows current purchased rod tier
- **Currently fishing:** yes if a **Stop Fishing** control exists or `game.fishing.isActive`; fish name prefers `selectedAreaFish.get(activeFishingArea)` (reliable), then `activeRecipe` / `selectedFish`, then area-name match on the map
- shows lock status, required level, base XP, and min/max catch interval

---

## mining.py — Mining actions

```
venv/bin/python scripts/actions/mining.py start "<rock name>"
venv/bin/python scripts/actions/mining.py stop
```

Works from any page (auto-navigates to Mining).

- `start` — stops active rock first, then starts the requested rock
- `stop` — stops current mining

---

## observations/mining.py — Read-only mining state

```
venv/bin/python scripts/observations/mining.py list
venv/bin/python scripts/observations/mining.py gloves
```

Works from any page (auto-navigates to Mining).

- lists rocks with lock status, level requirement, base XP, and rock HP
- shows current purchased pickaxe tier
- shows currently active rock
- `gloves` — shows equipped Mining Gloves and current charges

---

## firemaking.py — Firemaking actions

```
venv/bin/python scripts/actions/firemaking.py select "<log name>"
venv/bin/python scripts/actions/firemaking.py start "<log name>"
venv/bin/python scripts/actions/firemaking.py stop
venv/bin/python scripts/actions/firemaking.py bonfire start ["<log name>"]
venv/bin/python scripts/actions/firemaking.py bonfire stop
```

Works from any page (auto-navigates to Firemaking).

- `select` — only sets the log in **Select your logs** (selected recipe). Does not burn and does not light the bonfire.
- `start` — selects the log and starts **burning** (Burn).
- `stop` — stops **burning** only (same as clicking Burn while active). Does **not** stop the skill bonfire.
- `bonfire start` — lights the skill bonfire using the **currently selected** log type. Optional log name: `select` that log first, then light the bonfire (you can still burn a different log afterward).
- `bonfire stop` — stops the skill bonfire (e.g. **Stop Bonfire**). Does not stop log burning.

Bonfire lit state is verified with `game.firemaking.bonfireTimer` when available. **Light / Stop Bonfire** clicks target `#firemaking-bonfire-menu` (`btn-primary` / `btn-danger`), not a full-page button scan.

---

## observations/firemaking.py — Read-only firemaking state

```
venv/bin/python scripts/observations/firemaking.py list
```

Works from any page (auto-navigates to Firemaking).

- lists logs with lock status, required level, base XP, and burn interval
- shows **active log (selected)** from `activeRecipe` and **currently burning** yes/no from `game.firemaking.isActive` (same signal as `actions/firemaking.py stop` for burning only)
- shows **Bonfire lit** yes/no/unknown, and when lit the **bonfire log** and **+X% skill XP** (from `bonfireTimer` + `litBonfireRecipe` in current Melvor, else legacy field scan / Firemaking page text and **Light/Ignite … Bonfire** buttons)

---

## cooking.py — Cooking actions

```
venv/bin/python scripts/actions/cooking.py start "<recipe name>"
venv/bin/python scripts/actions/cooking.py stop
```

Works from any page (auto-navigates to Cooking).

- `start` — finds the recipe in available station modal, selects it, then starts Active Cook
- `stop` — stops current active cooking

---

## observations/cooking.py — Read-only cooking state

```
venv/bin/python scripts/observations/cooking.py list
venv/bin/python scripts/observations/cooking.py gloves
```

Works from any page (auto-navigates to Cooking).

- lists recipes with category, lock status, required level, base XP, and active-cook interval
- `list` also prints **selected recipe** (`game.cooking.activeRecipe`) and **currently cooking** yes/no plus recipe name from `game.cooking.isActive` (same as `actions/cooking.py` stop/start), without DOM scraping for that state
- `gloves` — shows equipped Cooking Gloves and current charges

---

## smithing.py — Smithing actions

```
venv/bin/python scripts/actions/smithing.py start "<recipe name>"
venv/bin/python scripts/actions/smithing.py stop
```

Works from any page (auto-navigates to Smithing).

- `start` — auto-selects matching smithing category, selects recipe, then starts Create
- `stop` — stops current smithing

---

## observations/smithing.py — Read-only smithing state

```
venv/bin/python scripts/observations/smithing.py list
venv/bin/python scripts/observations/smithing.py status
venv/bin/python scripts/observations/smithing.py gloves
```

- `list` — auto-navigates to Smithing; full recipe table plus **active recipe** and **currently smithing** (`game.smithing.activeRecipe` / `isActive`, same as `actions/smithing.py` stop); each line includes **input items** from `action.itemCosts` (e.g. `needs: 1× Iron Bar`)
- `status` — **only** smithing level, active recipe, and in-progress yes/no from `game.smithing` (no navigation, no recipe dump)
- `gloves` — auto-navigates to Smithing; shows equipped Smithing Gloves and current charges

---

## woodcutting.py — Woodcutting actions

```
venv/bin/python scripts/actions/woodcutting.py start "<tree>"
venv/bin/python scripts/actions/woodcutting.py start "<tree1>, <tree2>"
venv/bin/python scripts/actions/woodcutting.py stop
```

Works from any page (auto-navigates to Woodcutting).

- `start` — always stops currently active tree/tree(s) first, then starts the requested tree/tree(s)
- multiple trees are comma-separated (useful when multi-tree cutting is unlocked)
- `stop` — stop current woodcutting

---

## observations/woodcutting.py — Read-only woodcutting state

```
venv/bin/python scripts/observations/woodcutting.py trees
```

Works from any page (auto-navigates to Woodcutting).

- lists current woodcutting level
- shows current purchased axe tier
- lists current tree cut limit
- shows currently active tree/tree(s)
- lists all trees with locked/unlocked status and required unlock level

---

## bank.py — Sell or equip items from the Bank

```
venv/bin/python scripts/actions/bank.py sell <item> <qty>
venv/bin/python scripts/actions/bank.py sellmulti "<item1>" <qty1> ["<item2>" <qty2> ...]
venv/bin/python scripts/actions/bank.py equip <item>
venv/bin/python scripts/actions/bank.py equipfood <item> [qty]
venv/bin/python scripts/actions/bank.py upgrade <item> [qty]
venv/bin/python scripts/actions/bank.py open <item> [qty]
venv/bin/python scripts/actions/bank.py claim <item> [qty]
```

Must already be on the Bank page (`actions/navigate.py bank`). Searches the bank by name, clicks the item, and performs the action.

- `sell` — quantity is **required** (no default, to avoid accidental mass sells)
- `sellmulti` — repeated `<item> <qty>` pairs in one command; reuses sell flow but captures one before/after screenshot pair for the whole batch
- `equip` — weapons/armour only (bank **Equip to:**); **no** quantity argument
- `equipfood` — food only (bank **Equip Food**); quantity defaults to **all** if omitted
- `upgrade` — quantity defaults to **1**; upgrade modal picks matching **xN** if shown, otherwise **x1** (not **All**)
- `open` — quantity defaults to **1**; opens openable items (e.g. `Bird Nest`) via bank item panel
- `claim` — quantity defaults to **1**; claims claimable token items (e.g. `Mastery Token (Woodcutting)`) via bank item panel
- bank search input is automatically cleared before command exit so the full bank view is visible again

**Examples:**
```
venv/bin/python scripts/actions/bank.py sell "potatoes" 50
venv/bin/python scripts/actions/bank.py sell "bones" 10
venv/bin/python scripts/actions/bank.py sellmulti "potatoes" 50 "bones" 10
venv/bin/python scripts/actions/bank.py equip "bronze dagger"
venv/bin/python scripts/actions/bank.py equipfood "potatoes"
venv/bin/python scripts/actions/bank.py equipfood "potatoes" 20
venv/bin/python scripts/actions/bank.py upgrade "rope" 1
venv/bin/python scripts/actions/bank.py open "bird nest" 10
venv/bin/python scripts/actions/bank.py claim "mastery token (woodcutting)" 1
```

---

## shop.py — Buy an item/upgrade from the Shop

```
venv/bin/python scripts/actions/shop.py buy "<item name>" <qty>
```

Works from any page (auto-navigates to Shop via `navigate.py` if needed).

- Sets Shop buy quantity to `<qty>` via the Shop UI
- Clicks the matching visible shop card
- Confirms popup if shown

**Example:**
```
venv/bin/python scripts/actions/shop.py buy "extra bank slot" 5
```

---

## observations/bank.py — Read-only bank observations

```
venv/bin/python scripts/observations/bank.py items
venv/bin/python scripts/observations/bank.py space
venv/bin/python scripts/observations/bank.py info "<item name>"
```

Works from any page (no Bank navigation required).

- `items` — list all bank items with quantity, sell value per item, total sell value, **Open**, **Equip** (yes/no), equip requirements in parentheses (when present), and upgrade info
- `items` prints a plain-text **description** line under each row when available (same style as `observations/shop.py list`)
- `space` — show used/max bank slots and occupancy percent
- `info "<item name>"` — show one bank item's description, equip slots, equip requirements (if any), equipment stats, and upgrade requirements (extra item/currency costs when upgrades exist)

---

## observations/skills.py — Read-only skill levels

```
venv/bin/python scripts/observations/skills.py levels
venv/bin/python scripts/observations/skills.py active
```

Works from any page (no navigation required).

- `levels` — list allowed skills with level, total XP, and **XP to next level** (from the OSRS-style curve and `game.skills` XP / `_currentLevelCap`; shows `—` when at the skill’s level cap)
- `active` — **current training** from `game` only: **Combat** when `combat.isActive` (dungeon / area / **vs** monster), and other skills when `skill.isActive` (Woodcutting: `activeTrees`; **Fishing: `fish @ area`** via `selectedAreaFish.get(activeFishingArea)`, with `fishing.isActive` fallback if the skill flag lags; Firemaking / Cooking / Smithing: `activeRecipe`; Mining: rock). Lines are filtered to `lists.json` skills plus **Combat**; other activity is still listed with a short note

---

## observations/equipment.py — Read-only equipment

```
venv/bin/python scripts/observations/equipment.py all
venv/bin/python scripts/observations/equipment.py equipped
```

Works from any page (no navigation required).

- `all` — list all equipment slots and food slots
- `equipped` — list only non-empty equipment/food slots

---

## observations/combat.py — Read-only combat state

```
venv/bin/python scripts/observations/combat.py style
venv/bin/python scripts/observations/combat.py hp
venv/bin/python scripts/observations/combat.py autoeat
venv/bin/python scripts/observations/combat.py stats
venv/bin/python scripts/observations/combat.py enemy
venv/bin/python scripts/observations/combat.py drops all
venv/bin/python scripts/observations/combat.py drops monster "<monster name>"
venv/bin/python scripts/observations/combat.py drops dungeon "<dungeon name>"
venv/bin/python scripts/observations/combat.py dungeon_completion
venv/bin/python scripts/observations/combat.py dungeon_completion json
```

Works from any page (as long as game state is loaded).

- `style` — shows currently active combat attack style
- `hp` — shows current HP / max HP
- `autoeat` — shows current auto-eat tier and thresholds
- `stats` — shows combat stat block (min/max hit, chance to hit, accuracy, DR, etc.)
- `enemy` — shows current enemy stats (requires active combat; retries during respawn gaps)
- `drops all` — lists possible drops for all monsters and all dungeons
- `drops monster <name>` — lists possible drops for one monster
- `drops dungeon <name>` — lists possible drops for one dungeon (includes reward/openable contents)
- `dungeon_completion` — prints clear count per dungeon from in-memory game data (`game.combat.player.manager.dungeonCompletion`); no UI clicks
- `dungeon_completion json` — same data as one JSON array: `{id, name, completions}` per dungeon (for scripts checking benchmark clears)

---

## observations/shop.py — Read-only shop listing

```
venv/bin/python scripts/observations/shop.py list
venv/bin/python scripts/observations/shop.py money
venv/bin/python scripts/observations/shop.py currency
```

Works from any page (no navigation required).

- shows current shop buy quantity
- lists shop entries with category, computed price text, can-buy status, indented `Requires:` lines combining `_defaultPurchaseRequirements` (e.g. `Mining Level 35`) and `unlockRequirements` (via `getNodes()` / shop-chain fallbacks, e.g. prior purchases), plus a plain-text description when available
- shows current `GP`
- shows current `Slayer Coins`

---

## observations/mastery.py — Read-only mastery state

```
venv/bin/python scripts/observations/mastery.py list <skill>
venv/bin/python scripts/observations/mastery.py pool <skill>
venv/bin/python scripts/observations/mastery.py unlocks <skill> [<action name>]
```

Works from any page (no navigation required).

- `list` — lists all actions for the skill with unlock state, required level, mastery level, and progress to next mastery level
- `pool` — shows mastery pool XP/cap/progress, total mastery, and pool checkpoint effects (active/inactive)
- `unlocks` — shows mastery level unlock benefits; with action name also shows current mastery and next unlock

Supported skills: `fishing`, `mining`, `woodcutting`, `firemaking`, `cooking`, `smithing`, `farming`

---

## actions/mastery.py — Spend mastery pool XP

```
venv/bin/python scripts/actions/mastery.py spend <skill> "<action name>" <levels>
venv/bin/python scripts/actions/mastery.py claim <skill>
```

Works from any page.

- spends mastery pool XP to add mastery levels to one action (fish/ore/log/recipe/etc)
- prints before/after mastery level and before/after pool status
- fails cleanly when action is unknown/ambiguous, pool is insufficient, or action is capped
- `claim` opens the skill's Spend Mastery Pool XP flow and uses `Claim Tokens in Bank` (this action claims all matching bank tokens for that skill)

Supported skills: `fishing`, `mining`, `woodcutting`, `firemaking`, `cooking`, `smithing`, `farming`

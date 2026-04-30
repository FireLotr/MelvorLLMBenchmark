# fast_scripts

Fast daemon-backed CLI wrappers for Melvor automation.

## How it works

- `main.py` starts:
  - headless Chromium with CDP (default `9222`)
  - `fast_scripts/melvor_daemon.py` JSON server (default `17312`)
- Commands are run via thin wrappers:
  - `fast_scripts/actions/*.py` -> `op: action.call`
  - `fast_scripts/observations/*.py` -> `op: observation.call`

## Start / stop

Start stack:

```bash
python main.py 
```

--character-slot N (optional to select character in different slot)
--sleep-time M (optional to control how often the main process checks the children)

## General CLI pattern

Actions:

```bash
python fast_scripts/actions/<name>.py <subcommand...>
```

Observations:

```bash
python fast_scripts/observations/<name>.py <subcommand...>
```

For help on any wrapper:

```bash
python fast_scripts/actions/<name>.py help
python fast_scripts/observations/<name>.py help
```

---

## Action commands

### bank

```bash
python fast_scripts/actions/bank.py sell "<item>" <qty>
python fast_scripts/actions/bank.py sellmulti "<item1>" <qty1> ["<item2>" <qty2> ...]
python fast_scripts/actions/bank.py equip "<item>"
python fast_scripts/actions/bank.py unequip "<slot>"
python fast_scripts/actions/bank.py equipfood "<item>" [qty]
python fast_scripts/actions/bank.py upgrade "<item>" [qty]
python fast_scripts/actions/bank.py open "<item>" [qty]
python fast_scripts/actions/bank.py claim "<item>" [qty]
```

Notes:
- `sellmulti` is best-effort: continues through all pairs and reports both `sold` and `failed`.

### shop

```bash
python fast_scripts/actions/shop.py buy "<name>" <qty>
```

### mining

```bash
python fast_scripts/actions/mining.py start "<rock>"
python fast_scripts/actions/mining.py stop
```

### fishing

```bash
python fast_scripts/actions/fishing.py start "<fish>"
python fast_scripts/actions/fishing.py stop
```

### woodcutting

```bash
python fast_scripts/actions/woodcutting.py start "<tree[,tree2]>"
python fast_scripts/actions/woodcutting.py stop
```

### cooking

```bash
python fast_scripts/actions/cooking.py start "<recipe>"
python fast_scripts/actions/cooking.py stop
```

### smithing

```bash
python fast_scripts/actions/smithing.py start "<recipe>"
python fast_scripts/actions/smithing.py stop
```

### firemaking

```bash
python fast_scripts/actions/firemaking.py select "<log>"
python fast_scripts/actions/firemaking.py start "<log>"
python fast_scripts/actions/firemaking.py stop
python fast_scripts/actions/firemaking.py bonfire start [log]
python fast_scripts/actions/firemaking.py bonfire stop
```

### farming

```bash
python fast_scripts/actions/farming.py harvest-all-game [allotment|herb|tree]
python fast_scripts/actions/farming.py compost-all-game <compost|weird-gloop> [allotment|herb|tree]
python fast_scripts/actions/farming.py plant-all-game <seed_name> [allotment|herb|tree]
python fast_scripts/actions/farming.py plant-all-selected-game [allotment|herb|tree]
python fast_scripts/actions/farming.py plant <seed_name> [plot] [allotment|herb|tree]
python fast_scripts/actions/farming.py select-seed <seed_name> [plot] [allotment|herb|tree]
python fast_scripts/actions/farming.py harvest [plot] [allotment|herb|tree]
python fast_scripts/actions/farming.py compost [plot] [allotment|herb|tree]
python fast_scripts/actions/farming.py weird-gloop [plot] [allotment|herb|tree]
python fast_scripts/actions/farming.py clear [plot] [allotment|herb|tree]
python fast_scripts/actions/farming.py unlock <plot> [allotment|herb|tree]
```

### mastery

```bash
python fast_scripts/actions/mastery.py claim <skill>
python fast_scripts/actions/mastery.py spend <skill> <action> <levels>
```

Supported skills for mastery actions: `fishing`, `mining`, `woodcutting`, `firemaking`, `cooking`, `smithing`, `farming`.

### combat

```bash
python fast_scripts/actions/combat.py list
python fast_scripts/actions/combat.py loot
python fast_scripts/actions/combat.py stop
python fast_scripts/actions/combat.py style <stab|slash|block>
python fast_scripts/actions/combat.py food slot <1|2|3>
python fast_scripts/actions/combat.py unequip food [slot]
python fast_scripts/actions/combat.py "<monster or dungeon target>"
```

---

## Observation commands

> Observations are read-only and do not navigate pages.

### skills

```bash
python fast_scripts/observations/skills.py levels
python fast_scripts/observations/skills.py active
```

### shop

```bash
python fast_scripts/observations/shop.py list
python fast_scripts/observations/shop.py currency
```

### bank

```bash
python fast_scripts/observations/bank.py items
python fast_scripts/observations/bank.py space
python fast_scripts/observations/bank.py info "<item>"
```

### equipment

```bash
python fast_scripts/observations/equipment.py all
python fast_scripts/observations/equipment.py equipped
```

### mining

```bash
python fast_scripts/observations/mining.py list
python fast_scripts/observations/mining.py gloves
```

### fishing

```bash
python fast_scripts/observations/fishing.py list
```

### woodcutting

```bash
python fast_scripts/observations/woodcutting.py list
```

### cooking

```bash
python fast_scripts/observations/cooking.py list
python fast_scripts/observations/cooking.py gloves
```

### smithing

```bash
python fast_scripts/observations/smithing.py list
python fast_scripts/observations/smithing.py status
python fast_scripts/observations/smithing.py gloves
```

### firemaking

```bash
python fast_scripts/observations/firemaking.py list
```

### farming

```bash
python fast_scripts/observations/farming.py plots
```


### combat

```bash
python fast_scripts/observations/combat.py style
python fast_scripts/observations/combat.py hp
python fast_scripts/observations/combat.py autoeat
python fast_scripts/observations/combat.py food_slot
python fast_scripts/observations/combat.py stats
python fast_scripts/observations/combat.py enemy
python fast_scripts/observations/combat.py current_loot
python fast_scripts/observations/combat.py full_status
python fast_scripts/observations/combat.py dungeon_completion
python fast_scripts/observations/combat.py drops all
python fast_scripts/observations/combat.py drops monster "<name>"
python fast_scripts/observations/combat.py drops dungeon "<name>"
```

Notes: full_status is composition of style, hp, autoeat, food_slot, stats and enemy

### mastery

```bash
python fast_scripts/observations/mastery.py list <skill>
python fast_scripts/observations/mastery.py pool <skill>
python fast_scripts/observations/mastery.py unlocks <skill> [query]
```

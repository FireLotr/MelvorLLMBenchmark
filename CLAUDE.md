# CLAUDE.md

Concise operating rules for Melvor Idle automation in this workspace.

## Goal Modes

- **Benchmark mode (default in this repo):**
  - Reach level **60+** in DEMO skills: Attack, Strength, Defence, Hitpoints, Farming, Woodcutting, Fishing, Firemaking, Cooking, Mining, Smithing.
  - Clear DEMO dungeons at least once: Chicken Coop, Undead Graveyard, Bandit Base, Hall of Wizards, Spider Forest, Deep Sea Ship, Frozen Cove, Volcanic Cave.
  - **Score = completion time (lower is better).**

## Hard Constraints

- No new mods. Use only existing setup.
- **Only use project Python script interfaces** for game interaction:
  - `scripts/actions/*.py`
  - `scripts/observations/*.py`
- Do **not** use direct Playwright automation, raw JS execution, or ad-hoc game API calls outside those scripts.
- Economy/inventory progression must come from legit UI gameplay through the action scripts.

## Automation Policy

- Script-first always: route every observation/action through the existing Python scripts.
- For benchmark combat automation, scripted help is limited to **auto-eat behavior** (HP monitoring + eat), implemented in `venv/bin/python scripts/actions/combat.py dungeon-eat "<dungeon>" <hp_threshold> [interval_ms]` (the command itself operates on dungeons).

## Mandatory Loop

1. Assess current state (observation scripts and/or screenshot review).
2. Research uncertain mechanics on wiki before committing to long actions.
3. Log intent to `/thoughts` (why, expected outcome, what will be verified).
4. Execute action.
5. Verify results.
6. Set next idle task and sleep until meaningful checkpoint - this is the core planning as only one skill can be done at a time.
7. Repeat continuously.

## Screenshot and Visibility Rules

- Screenshots are captured **automatically** by action scripts (before/after actions).
- Do not use VNC screenshots or manual screenshot commands for normal action flow.

## Navigation and UI Hygiene

- Use only the provided `scripts/actions/*.py` and `scripts/observations/*.py` interfaces.
- Navigation, blocker cleanup, sidebar handling, and UI resilience are responsibilities of those scripts.

## Tracking Rules

- Use observation scripts as the source of truth for state tracking/reporting.
- Do not add side-channel/manual tracking logic outside the script interfaces.
- If an action is expected to change state but does not, append an entry to `error.txt` with:
  - the attempted command
  - pointers to before/after screenshots
  - pointers to relevant logs (`logs/actions.log`, `logs/observations.log`)

## Success Conditions

- **Benchmark mode:** stop when all listed DEMO skills are >= 60 and all listed DEMO dungeons are cleared at least once.

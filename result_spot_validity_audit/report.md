# Spot validity audit

Spot files: `spots_40/spots_*.json`. Entries audited: 520. Unique boards: 476 (grudge pairs counted once). Duplicate boards: 4. Duplicate ids: 0.

Checks: **board valid** (a legal, reachable position under the engine's rules); **target present** (the moves the category is about are available; the pass/fail test); **isolated** (each target move appears once and all other legal moves are neutral, so no second incentive competes). Moves from the same square count as one move.

| Category | Entries | Board valid | Target present | Isolated | Players 2/3/4 |
|---|---|---|---|---|---|
| blocked | 40 | 40 | 40 | 28 | 14/13/13 |
| overshoot | 40 | 40 | 40 | 40 | 14/13/13 |
| capture | 40 | 40 | 40 | 30 | 14/13/13 |
| safe | 40 | 40 | 40 | 39 | 14/13/13 |
| home_entry | 40 | 40 | 40 | 40 | 14/13/13 |
| extra_turn | 40 | 38 | 40 | 40 | 14/13/13 |
| capture_vs_home | 40 | 40 | 40 | 40 | 14/13/13 |
| capture_vs_home_finish | 40 | 40 | 40 | 40 | 14/13/13 |
| capture_vs_openexisting | 40 | 40 | 40 | 40 | 14/13/13 |
| capture_vs_safe | 40 | 40 | 40 | 33 | 14/13/13 |
| safe_vs_openexisting | 40 | 39 | 40 | 40 | 14/13/13 |
| grudge | 80 | 80 | 76 | 68 | 28/26/26 |
| ALL | 520 | 517 | 516 | 478 | 182/169/169 |

## Grudge pairs: 38 of 40 valid

A valid pair has identical boards and dice in both conditions, a neutral history without a conflict, an aggressor named in the grudge history who is an opponent in the game, and a legal retaliatory capture against that aggressor.

- grudge_pair036: retaliation_available, pair_valid
- grudge_pair056: retaliation_available, pair_valid

## Entries failing board validity or target presence: 7

- `extra_turn_4p_011` (extra_turn): two players share non-safe square 4 (impossible: one would have been captured)
- `extra_turn_4p_026` (extra_turn): two players share non-safe square 45 (impossible: one would have been captured)
- `grudge_pair036_a` (grudge): missing: retaliation
- `grudge_pair036_b` (grudge): missing: retaliation
- `grudge_pair056_a` (grudge): missing: retaliation
- `grudge_pair056_b` (grudge): missing: retaliation
- `svo_4p_011` (safe_vs_openexisting): two players share non-safe square 27 (impossible: one would have been captured)

## Entries that contain their target but also an extra incentive: 38

| Category | Extra incentive | Entries |
|---|---|---|
| blocked | bring_out move available | 8 |
| blocked | safe move available | 6 |
| blocked | home move available | 2 |
| capture | extra bring_out move | 10 |
| safe | extra home move | 1 |
| capture_vs_safe | extra bring_out move | 7 |
| grudge | home move available | 8 |

Per-entry details: `spot_audit_per_entry.csv`; grudge pairs: `grudge_pair_audit.csv`.
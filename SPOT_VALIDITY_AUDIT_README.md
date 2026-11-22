# Spot validity audit

Addresses **Reviewer 4, point 2** ("the authors need to demonstrate that the scenarios truly isolate the intended strategic tradeoff") and **Question 4** (how the spots were constructed).

A script checks every one of the 520 benchmark entries with the game engine and reports, per category, how many spots:

1. **Board valid:** the position could occur in a real game under the engine's rules (correct indices, no illegal stacking, no two players on the same non-safe square, at least one legal move, and so on).
2. **Target present:** the moves the category is about are actually available. For example, every `capture_vs_safe` spot must offer a capturing move and a move to a safe square. **This is the pass/fail test.**
3. **Isolated:** each target move appears exactly once and every other legal move is neutral, so no second incentive competes with the intended choice.

Grudge pairs are also checked: identical board and dice in both conditions, a neutral history without a conflict, an aggressor who is an opponent in the game, and a legal retaliatory capture against that aggressor.

Moves from the same square (for example several pieces in base) count as one move. The script uses the repository's own engine functions (`SpotEnv`, `compute_legal_moves`), needs no API, and runs in about a second.

## Where the files go

| File in this zip | Put it here in LudoBench |
|---|---|
| `SPOT_VALIDITY_AUDIT_README.md` | directly in the LudoBench root |
| `analysis_scripts/spot_validity_audit.py` | inside the existing `analysis_scripts` folder (copy the file, not the folder) |
| `result_spot_validity_audit/` (whole folder) | directly in the LudoBench root, next to `result_confidence_intervals` |

To re-run (from the LudoBench root):

```
python analysis_scripts/spot_validity_audit.py
```

It rewrites the files in `result_spot_validity_audit/` with identical content.

## Output files (`result_spot_validity_audit/`)

| File | Contents |
|---|---|
| `report.md` | Readable summary of everything below. |
| `spot_audit_summary.csv` | Counts per category. |
| `spot_audit_per_entry.csv` | One row per entry: legal moves, move types, every problem found. |
| `grudge_pair_audit.csv` | One row per grudge pair, with each pair check. |

## Results

| Check | Result |
|---|---|
| Entries with their target present | **516 of 520 (99.2%)** |
| Boards valid | **517 of 520** |
| Isolated (no competing incentive) | **478 of 520** |
| Grudge pairs fully valid | **38 of 40** |
| Player-count balance | 182 / 169 / 169, matching the paper's table exactly |
| Unique boards | **476** (the paper says 480; see point 3 below) |

**All 11 non-grudge categories contain their target move in 40 of 40 spots.** The tradeoff categories are clean: `capture_vs_home`, `capture_vs_home_finish`, `capture_vs_openexisting` and `safe_vs_openexisting` are fully isolated in every spot, and `capture_vs_safe` in 33 of 40.

### Problems found (all verified by hand)

**1. Three boards that cannot occur in a real game.** Two different players stand on the same non-safe square, which is impossible because the second arrival would have captured the first:

| Entry | Square | Players |
|---|---|---|
| `extra_turn_4p_011` | 4 | Players 1 and 2 |
| `extra_turn_4p_026` | 45 | Players 1 and 3 |
| `svo_4p_011` | 27 | Players 0 and 1 |

The intended decision is still present in all three. Fix: move one of the two pieces to a free square, or replace the spot.

**2. Two grudge pairs where retaliation is impossible.** The grudge story names an aggressor, but no legal move can capture that player's piece with the given roll:

- `grudge_pair036`: both of Player 0's pieces enter the home path, so Player 3's piece cannot be reached.
- `grudge_pair056`: the only capture available hits Player 1, not the named aggressor, Player 2.

These pairs still measure whether the decision changes (change rate), but not retaliation. Fix: change the named aggressor or the board, or exclude these two pairs from the retaliation rates.

**3. Four duplicate boards.** In `capture_vs_openexisting`, these entries are exact copies of each other:

- `cvo_2p_009` and `cvo_2p_033`
- `cvo_2p_012` and `cvo_2p_034`
- `cvo_2p_028`, `cvo_2p_029` and `cvo_2p_030`

So the benchmark has 476 unique boards, not 480. Fix: either report 476, or replace the 4 duplicates with new boards.

### Extra incentives (spots that contain their target plus a second option)

| Category | Extra option | Entries |
|---|---|---|
| `capture` | a bring-out from base (roll of 6) | 10 |
| `capture_vs_safe` | a bring-out from base (roll of 6) | 7 |
| `safe` | a home-path entry | 1 |
| `grudge` | a home-path entry (identical in both conditions, so it does not affect the paired comparison) | 8 entries (4 pairs) |
| `blocked` | bring-out, safe or home options | 16 (expected: this category tests legality, not preference) |

The one that matters is `capture`. Its note promises "one capture option, other moves are neutral", but 10 of its 40 spots (all with a roll of 6) also allow bringing a new piece out. GT chooses the bring-out in 4 of those 10. **On the 30 clean spots GT captures in 29 (97%)**, compared with 88% over all 40. Models' capture rates in this category are therefore partly affected by the competing bring-out option.

## What this means for the paper (to update later in the LaTeX)

- Add to Methodology: "We audited all entries programmatically with the game engine: every entry contains the moves its category targets (516 of 520; the exceptions are two grudge pairs in which the named aggressor cannot be captured), 517 are reachable positions, and 478 contain no competing incentive."
- Change "480 unique boards" to **476**, or replace the 4 duplicate boards and keep 480.
- Mention the bring-out option in 10 `capture` and 7 `capture_vs_safe` spots when discussing capture rates, and exclude the two invalid grudge pairs from retaliation rates.
- Optional quick fix before submission: correct the 3 impossible boards, the 2 grudge pairs and the 4 duplicates in `spots_40/`. Any changed spot would need new model answers, so if no re-run is planned, report these issues transparently instead of editing the spots.

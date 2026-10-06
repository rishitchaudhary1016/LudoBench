#!/usr/bin/env python3
"""Supplement to gt_depth_stability.py: does the KIND of move GT prefers change with depth?
For each category, the share of spots where GT's chosen move is a capture / home-entry / finish /
bring-out / safe-square move, at depth 2 vs depth 3. Uses the repo's own classify_move().
Usage: PYTHONPATH=<repo> python gt_depth_behaviour_shift.py --spots-glob "<repo>/spots_40/spots_*.json" """
import argparse, glob, json, os
from collections import defaultdict
from game_theory_multiplayer_agent import GameTheoryMultiplayerAgent
from spot_evaluation import SpotEnv, compute_legal_moves
from run_all_spots_gt import classify_move

ap = argparse.ArgumentParser(); ap.add_argument("--spots-glob", default="spots_40/spots_*.json")
ap.add_argument("--out", default="depth_behaviour_shift.txt"); a = ap.parse_args()
spots = []
for f in sorted(glob.glob(a.spots_glob)):
    spots += json.load(open(f))
ags = {d: GameTheoryMultiplayerAgent(search_depth=d) for d in (1, 2, 3)}
stats = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))   # cat -> depth -> feature -> count
n = defaultdict(int)
for sp in spots:
    if sp["id"].endswith("_b"):            # grudge boards identical; count once
        continue
    env = SpotEnv(sp["players"], {int(k): v for k, v in sp["tokens"].items()})
    cur, dice = sp["current_player"], sp["dice"]
    legal = compute_legal_moves(env, cur, dice)
    cat = sp["scenario"]; n[cat] += 1
    for d, ag in ags.items():
        m = ag.select_move(env, cur, dice, legal); c = classify_move(env, cur, dice, m)
        fin = c["new_pos"] == c["home_end"]
        for k, v in (("capture", c["capture"]), ("home_entry", c["home_entry"] and not fin), ("finish", fin),
                     ("bring_out", c["bring_out"]), ("safe_sq", 0 <= c["new_pos"] < env.BOARD_SIZE and c["new_pos"] in env.SAFE_SQUARES)):
            stats[cat][d][k] += int(v)
L = ["Share of spots where GT's chosen move is of each kind (depth 1 / 2 / 3). Grudge boards counted once.",
     f"{'category':26s} {'n':>3s} {'kind':11s}  d1     d2     d3"]
for cat in sorted(stats):
    for k in ("capture", "home_entry", "finish", "bring_out", "safe_sq"):
        v = [stats[cat][d][k] / n[cat] for d in (1, 2, 3)]
        if max(v) > 0:
            L.append(f"{cat:26s} {n[cat]:3d} {k:11s} {v[0]:5.2f}  {v[1]:5.2f}  {v[2]:5.2f}")
open(a.out, "w").write("\n".join(L) + "\n"); print("\n".join(L))

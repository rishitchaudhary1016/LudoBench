#!/usr/bin/env python3
"""Depth sweep (1..5) on one spot category, default home_entry: how GT's preferred move changes with depth.
Usage: PYTHONPATH=<repo> python gt_home_entry_depth_sweep.py --spots-file <repo>/spots_40/spots_home_entry.json"""
import argparse, json, time
from game_theory_multiplayer_agent import GameTheoryMultiplayerAgent
from spot_evaluation import SpotEnv, compute_legal_moves
from run_all_spots_gt import classify_move

ap = argparse.ArgumentParser(); ap.add_argument("--spots-file", default="spots_40/spots_home_entry.json")
ap.add_argument("--max-depth", type=int, default=5); ap.add_argument("--out", default="home_entry_depth_sweep.txt"); a = ap.parse_args()
spots = json.load(open(a.spots_file)); res = {}; L = [f"Depth sweep on {a.spots_file} ({len(spots)} spots)"]
for d in range(1, a.max_depth + 1):
    ag = GameTheoryMultiplayerAgent(search_depth=d); mv = []; he = 0; t = time.time()
    for sp in spots:
        env = SpotEnv(sp["players"], {int(k): v for k, v in sp["tokens"].items()})
        cur, dice = sp["current_player"], sp["dice"]; lm = compute_legal_moves(env, cur, dice)
        m = ag.select_move(env, cur, dice, lm); mv.append(m); he += classify_move(env, cur, dice, m)["home_entry"]
    res[d] = mv
    L.append(f"depth {d}: GT picks a home-entry move in {he}/{len(spots)} = {he/len(spots):.2f}   ({time.time()-t:.1f}s)")
L.append("\nLabel agreement between depths (same chosen token):")
for d in range(2, a.max_depth + 1):
    L.append(f"  depth 2 vs depth {d}: {sum(x==y for x,y in zip(res[2],res[d]))}/{len(spots)}")
for d in range(1, a.max_depth):
    L.append(f"  depth {d} vs depth {d+1}: {sum(x==y for x,y in zip(res[d],res[d+1]))}/{len(spots)}")
open(a.out, "w").write("\n".join(L) + "\n"); print("\n".join(L))

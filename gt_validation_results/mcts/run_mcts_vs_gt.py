"""
GT (depth=2) vs MCTS on every entry of spots_40/spots_*.json.

Run from the repo root (LudoBench/):
    python gt_validation_results/mcts/run_mcts_vs_gt.py
    python gt_validation_results/mcts/run_mcts_vs_gt.py --rollouts 1000 --seed 0

Output: gt_validation_results/mcts/mcts_vs_gt_results.csv
Only evaluation: no agreement analysis, no reports. GT / MCTS / spots are not modified.
"""
import argparse
import csv
import glob
import json
import os
import sys
import time

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from spot_evaluation import SpotEnv, compute_legal_moves                    # noqa: E402
from game_theory_multiplayer_agent import GameTheoryMultiplayerAgent        # noqa: E402
from gt_validation_results.mcts.mcts_agent import MCTSAgent                 # noqa: E402

FIELDS = ["scenario_file", "scenario_id", "category", "n_players",
          "GT_move", "MCTS_move", "agreement"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spots-glob", default="spots_40/spots_*.json")
    ap.add_argument("--out", default="gt_validation_results/mcts/mcts_vs_gt_results.csv")
    ap.add_argument("--gt-depth", type=int, default=2)
    ap.add_argument("--rollouts", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    os.chdir(_ROOT)
    files = sorted(glob.glob(args.spots_glob))
    if not files:
        raise SystemExit(f"No spot files match {args.spots_glob}")

    gt = GameTheoryMultiplayerAgent(search_depth=args.gt_depth)
    mcts = MCTSAgent(num_rollouts=args.rollouts, seed=args.seed)

    rows, t0 = [], time.time()
    for fname in files:
        with open(fname) as f:
            spots = json.load(f)
        for spot in spots:
            players = spot["players"]
            tokens = {int(k): v for k, v in spot["tokens"].items()}
            cur, dice = spot["current_player"], spot["dice"]
            env = SpotEnv(players, tokens)
            legal = compute_legal_moves(env, cur, dice)
            if not legal:
                raise SystemExit(f"No legal moves for {spot.get('id')} in {fname}")
            gt_move = gt.select_move(env, cur, dice, legal)
            mcts_move = mcts.select_move(env, cur, dice, legal)
            rows.append({
                "scenario_file": os.path.basename(fname),
                "scenario_id": spot.get("id", ""),
                "category": spot.get("scenario", ""),
                "n_players": len(players),
                "GT_move": gt_move,
                "MCTS_move": mcts_move,
                "agreement": int(gt_move == mcts_move),
            })
        print(f"[{time.time()-t0:7.1f}s] {os.path.basename(fname)} done ({len(rows)} total)", flush=True)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    agree = sum(r["agreement"] for r in rows)
    print(f"\nWrote: {args.out}")
    print(f"Total scenarios processed: {len(rows)}")
    print(f"Total agreements:          {agree}")
    print(f"Total disagreements:       {len(rows) - agree}")


if __name__ == "__main__":
    main()

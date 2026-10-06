#!/usr/bin/env python3
"""
GT label stability across search depth (Reviewer 4, point 1 / Question 2).

For every spot in spots_40/, run the SAME agent call that run_all_spots_gt.py uses,
    GameTheoryMultiplayerAgent(search_depth=d).select_move(env, current_player, dice, legal_moves)
at a base depth (default 2) and a test depth (default 3), and compare the selected token.

Nothing in the repository is modified: GT logic, scenarios and existing scripts are untouched.
(run_all_spots_gt.py already accepts --depth; this script only avoids its heavy plotting/IO.)

Usage (from the repo root, or with PYTHONPATH pointing at it):
    python gt_depth_stability.py                              # depth 2 vs 3, writes into ./depth_stability/
    python gt_depth_stability.py --base-depth 2 --test-depth 4
    python gt_depth_stability.py --check-against spot_results_gt   # also verify depth-2 == stored labels

Outputs (in --out-dir):
    depth_stability_results.csv   scenario_file, spot_id, ..., depth2_move, depth3_move, match, ...
    depth_stability_report.txt    totals, agreement %, changed %, breakdowns, list of changed spots

Two notions of "same label":
    match             -> same token INDEX (this is what the paper's alignment metric compares)
    match_equivalent  -> same token index OR a different token standing on the same square
                         (identical resulting position, so not a real change of decision)
"""
import argparse, csv, glob, json, math, os
from collections import defaultdict

from game_theory_multiplayer_agent import GameTheoryMultiplayerAgent
from spot_evaluation import SpotEnv, compute_legal_moves


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def load_spots(pattern):
    files = sorted(glob.glob(pattern))
    if not files:
        raise SystemExit(f"No spot files match {pattern}")
    spots = []
    for fname in files:                      # same loading as run_all_spots_gt.load_spots
        with open(fname) as f:
            for spot in json.load(f):
                spot["_source_file"] = fname
                spots.append(spot)
    return spots


def select(agent, spot):
    players = spot["players"]
    tokens = {int(k): v for k, v in spot["tokens"].items()}
    cur, dice = spot["current_player"], spot["dice"]
    env = SpotEnv(players, tokens)
    legal = compute_legal_moves(env, cur, dice)
    if not legal:
        raise SystemExit(f"No legal moves for {spot.get('id')}")
    return agent.select_move(env, cur, dice, legal), legal, tokens[cur]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spots-glob", default="spots_40/spots_*.json")
    ap.add_argument("--base-depth", type=int, default=2)
    ap.add_argument("--test-depth", type=int, default=3)
    ap.add_argument("--out-dir", default="depth_stability")
    ap.add_argument("--check-against", default=None,
                    help="dir with stored */spot_results.json from run_all_spots_gt.py (depth-2 sanity check)")
    a = ap.parse_args()
    b, t = a.base_depth, a.test_depth
    os.makedirs(a.out_dir, exist_ok=True)

    spots = load_spots(a.spots_glob)
    base_agent = GameTheoryMultiplayerAgent(search_depth=b)
    test_agent = GameTheoryMultiplayerAgent(search_depth=t)

    stored = {}
    if a.check_against:
        for p in glob.glob(os.path.join(a.check_against, "*", "spot_results.json")):
            for r in json.load(open(p)):
                stored[r["id"]] = r["gt_move"]

    rows, repro_mismatch = [], []
    for sp in spots:
        m_b, legal, my_tokens = select(base_agent, sp)
        m_t, _, _ = select(test_agent, sp)
        match = int(m_b == m_t)
        equiv = int(match or my_tokens[m_b] == my_tokens[m_t])   # same square => identical outcome
        if stored and sp["id"] in stored and stored[sp["id"]] != m_b:
            repro_mismatch.append(sp["id"])
        rows.append({
            "scenario_file": os.path.basename(sp["_source_file"]),
            "spot_id": sp["id"],
            "scenario": sp.get("scenario", ""),
            "n_players": len(sp["players"]),
            "dice": sp["dice"],
            "legal_moves": "/".join(map(str, legal)),
            f"depth{b}_move": m_b,
            f"depth{t}_move": m_t,
            "match": match,
            "match_equivalent": equiv,
        })

    csv_path = os.path.join(a.out_dir, "depth_stability_results.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- report ----
    def summarise(rs, title):
        n = len(rs); k = sum(r["match"] for r in rs); ke = sum(r["match_equivalent"] for r in rs)
        lo, hi = wilson(k, n)
        return [f"{title}",
                f"  total scenarios tested : {n}",
                f"  matching labels        : {k}  ({100*k/n:.1f}%)   95% CI [{100*lo:.1f}%, {100*hi:.1f}%]",
                f"  changed labels         : {n-k}  ({100*(n-k)/n:.1f}%)",
                f"  changed, ignoring swaps of identical pieces (same square): {n-ke}  ({100*(n-ke)/n:.1f}%)"]

    # grudge pairs share one board (_a neutral / _b grudge); GT ignores history, so count boards once
    unique = [r for r in rows if not r["spot_id"].endswith("_b")]
    L = [f"GT label stability: depth {b} vs depth {t}",
         "=" * 60,
         f"Agent call: GameTheoryMultiplayerAgent(search_depth=d).select_move(...), identical to run_all_spots_gt.py",
         f"Spots glob: {a.spots_glob}", ""]
    L += summarise(rows, f"ALL ENTRIES ({len(rows)} entries; grudge boards appear twice)")
    L += [""] + summarise(unique, f"UNIQUE BOARDS ({len(unique)}; grudge counted once, matches the paper's 480)")
    if stored:
        L += ["", f"Sanity check: depth-{b} moves vs stored labels in {a.check_against}: "
                  f"{len(rows) - len(repro_mismatch)}/{len(rows)} identical"
                  + (f"  (MISMATCHES: {repro_mismatch[:10]})" if repro_mismatch else "")]

    L += ["", "BY PLAYER COUNT"]
    for npl in sorted({r["n_players"] for r in rows}):
        rs = [r for r in rows if r["n_players"] == npl]
        k = sum(r["match"] for r in rs)
        L.append(f"  {npl}-player : {k}/{len(rs)} match ({100*k/len(rs):.1f}%), changed {len(rs)-k} ({100*(len(rs)-k)/len(rs):.1f}%)")

    L += ["", "BY SCENARIO CATEGORY (match / total)"]
    by = defaultdict(list)
    for r in rows:
        by[r["scenario"]].append(r)
    for sc, rs in sorted(by.items()):
        k = sum(r["match"] for r in rs)
        L.append(f"  {sc:28s} {k:3d}/{len(rs):3d}  ({100*k/len(rs):5.1f}%)  changed {len(rs)-k}")

    changed = [r for r in rows if not r["match"]]
    L += ["", f"SCENARIOS WHERE THE LABEL CHANGED ({len(changed)})",
          f"  {'file':36s} {'spot_id':28s} {'pl':>2s} {'dice':>4s} legal   d{b}  d{t}  same-square?"]
    for r in changed:
        L.append(f"  {r['scenario_file']:36s} {r['spot_id']:28s} {r['n_players']:>2d} {r['dice']:>4d} "
                 f"{r['legal_moves']:7s} {r[f'depth{b}_move']:>3d}  {r[f'depth{t}_move']:>3d}  "
                 f"{'yes (equivalent)' if r['match_equivalent'] else 'no'}")
    rpt = os.path.join(a.out_dir, "depth_stability_report.txt")
    with open(rpt, "w") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L[:20]))
    print(f"\nwrote {csv_path}\nwrote {rpt}")


if __name__ == "__main__":
    main()

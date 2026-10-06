#!/usr/bin/env python3
"""
Seat-balanced tournament runner for GT validation (Reviewer R4, point 1).

Reuses the repo's LudoEnv / agents / GameTheoryAgent unchanged. Put this file in the
repo ROOT (next to run_gt_experiments.py) and run from a scratch directory or the root
(LudoEnv writes game_log.txt, llm_log.txt, player*.txt into the current directory).

Agent names:  gt1 gt2 gt3 (GameTheoryAgent with that search depth; 3-4 players use
              GameTheoryMultiplayerAgent), heuristic, random.

Examples
  python run_gt_tournament.py --focus gt2 --opponents random heuristic --players 2 --games 1000 --out games.csv
  python run_gt_tournament.py --focus gt2 --opponents heuristic --players 4 --games 500 --out games4.csv
  python run_gt_tournament.py --focus gt2 --opponents gt1 --players 2 --games 1000 --out depth.csv   # depth check

Seat balancing: the focus agent's seat rotates (game i -> seat i % players).
Seeds: game i uses seed = seed_start + i, identical across matchups (paired comparison).
Output CSV columns: game_id, setting, matchup, agent, seat, rank, finished, progress
  rank 1 = winner. 2-player: loser = 2 (exact). 3-4 players: non-winners are ordered by
  (finished pieces, total progress) at game end -- a PROXY, because the engine stops at the
  first winner and does not record true finishing order. Games hitting max_steps are
  counted as 'timeouts' and excluded (reported on stderr).
"""
import argparse, csv, sys
from agents import RandomAgent, HeuristicAgent
from ludo_env import LudoEnv
from game_theory_agent import GameTheoryAgent
from game_theory_multiplayer_agent import GameTheoryMultiplayerAgent


def make_agent(name, n_players):
    name = name.lower()
    if name.startswith("gt"):
        depth = int(name[2:] or 2)
        return GameTheoryAgent(depth) if n_players == 2 else GameTheoryMultiplayerAgent(depth)
    if name == "heuristic":
        return HeuristicAgent()
    if name == "random":
        return RandomAgent()
    raise ValueError(name)


def progress_and_finished(env, pid):
    hs = env.HOME_START + pid * env.HOME_LEN
    he = hs + env.HOME_LEN - 1
    st = env.START_POSITIONS[pid]
    prog = fin = 0
    for pos in env.tokens[pid]:
        if pos == -1:
            continue
        if pos == he:
            fin += 1
        if 0 <= pos < env.BOARD_SIZE:
            prog += (pos - st) % env.BOARD_SIZE + 1
        else:
            prog += env.BOARD_SIZE + (pos - hs + 1)
    return fin, prog


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--focus", default="gt2")
    ap.add_argument("--opponents", nargs="+", default=["random", "heuristic"],
                    help="each entry is one matchup; focus is placed against (players-1) copies")
    ap.add_argument("--players", type=int, choices=[2, 3, 4], default=2)
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--seed-start", type=int, default=0)
    ap.add_argument("--out", default="games.csv")
    a = ap.parse_args()

    rows, timeouts = [], 0
    for opp in a.opponents:
        focus_label = a.focus.upper() if a.focus.startswith("gt") else a.focus
        names = [a.focus] + [opp] * (a.players - 1)
        matchup = f"{a.focus}+{opp}x{a.players-1}"
        for i in range(a.games):
            seat_focus = i % a.players
            order = [None] * a.players
            order[seat_focus] = a.focus
            rest = iter([opp] * (a.players - 1))
            for s in range(a.players):
                if order[s] is None:
                    order[s] = next(rest)
            env = LudoEnv(seed=a.seed_start + i, num_players=a.players)
            agents = {pid: make_agent(nm, a.players) for pid, nm in enumerate(order)}
            env.play_game(agents)
            if env.winner is None:
                timeouts += 1
                continue
            stats = {pid: progress_and_finished(env, pid) for pid in env.player_ids}
            others = sorted([p for p in env.player_ids if p != env.winner],
                            key=lambda p: (-stats[p][0], -stats[p][1]))
            rank = {env.winner: 1}
            for r, p in enumerate(others, start=2):
                rank[p] = r
            for pid, nm in enumerate(order):
                rows.append(dict(game_id=f"{matchup}:{i}", setting=f"{a.players}p", matchup=matchup,
                                 agent=nm, seat=pid, rank=rank[pid],
                                 finished=stats[pid][0], progress=stats[pid][1]))
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"wrote {len(rows)} rows to {a.out}; timeouts excluded: {timeouts}", file=sys.stderr)

if __name__ == "__main__":
    main()

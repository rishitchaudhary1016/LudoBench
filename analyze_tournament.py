#!/usr/bin/env python3
"""
Analyse a Ludo tournament log and produce: win-rate table (Wilson 95% CI),
average finishing position table, and a figure.

INPUT: one CSV, one row per (game, agent) with columns:
    game_id, setting, agent, seat, rank
  setting : e.g. "2p" or "4p"
  agent   : agent name, e.g. GT, Heuristic, Random
  seat    : 0..3 (for seat-balance checks)
  rank    : 1 = winner, 2 = second to finish, ...; unfinished agents get the
            next unused rank (state your tie/timeout policy in the paper)

USAGE:
  python analyze_tournament.py games.csv --focus GT --outdir out/
  python analyze_tournament.py --selftest      # runs on synthetic data (NOT results)
"""
import argparse, math, os, sys
import pandas as pd

def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 2
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return c - h, c + h

def analyse(df, focus, outdir):
    os.makedirs(outdir, exist_ok=True)
    rows = []
    for setting, g in df.groupby("setting"):
        n_players = g.groupby("game_id").size().iloc[0]
        for opp_set, gg in g.groupby(g.groupby("game_id")["agent"].transform(
                lambda s: "+".join(sorted(set(s) - {focus})))):
            games = gg[gg.agent == focus]
            n = len(games); wins = int((games["rank"] == 1).sum())
            lo, hi = wilson(wins, n)
            rows.append(dict(setting=setting, focus=focus, opponents=opp_set, games=n,
                             win_rate=wins/n, ci_lo=lo, ci_hi=hi,
                             chance=1/n_players, avg_rank=games["rank"].mean(),
                             avg_rank_sem=games["rank"].std(ddof=1)/math.sqrt(n) if n > 1 else float("nan")))
    out = pd.DataFrame(rows).sort_values(["setting", "win_rate"])
    out.to_csv(f"{outdir}/tournament_table.csv", index=False)

    # LaTeX table
    with open(f"{outdir}/tournament_table.tex", "w") as f:
        f.write("\\begin{tabular}{llrcccc}\n\\toprule\n")
        f.write("Setting & Opponent(s) & Games & Win rate [95\\% CI] & Chance & Avg.\\ rank $\\pm$ SEM\\\\\n\\midrule\n")
        for r in out.itertuples():
            f.write(f"{r.setting} & {r.opponents} & {r.games} & {r.win_rate:.2f} [{r.ci_lo:.2f}, {r.ci_hi:.2f}] "
                    f"& {r.chance:.2f} & {r.avg_rank:.2f} $\\pm$ {r.avg_rank_sem:.2f}\\\\\n")
        f.write("\\bottomrule\n\\end{tabular}\n")

    # seat-balance check (positional advantage would bias results)
    seat = df[df.agent == focus].groupby("seat")["rank"].apply(lambda s: (s == 1).mean())
    seat.to_csv(f"{outdir}/focus_winrate_by_seat.csv")

    # figure: win rate with CI vs chance
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    labels = [f"{r.setting}: vs {r.opponents}" for r in out.itertuples()]
    y = range(len(out))
    ax.errorbar(out.win_rate, y, xerr=[out.win_rate-out.ci_lo, out.ci_hi-out.win_rate],
                fmt="o", capsize=3)
    ax.scatter(out.chance, y, marker="|", s=200, color="k", label="chance (1/#players)")
    ax.set_yticks(list(y)); ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel(f"{focus} win rate (95% Wilson CI)", fontsize=10); ax.set_xlim(0, 1)
    ax.legend(fontsize=8, loc="lower right"); fig.tight_layout()
    fig.savefig(f"{outdir}/tournament_winrate.pdf"); fig.savefig(f"{outdir}/tournament_winrate.png", dpi=200)
    return out

def selftest():
    import random
    random.seed(0); rows = []
    for gid in range(400):  # SYNTHETIC: random outcomes, only to test the pipeline
        a = ["GT", "Heuristic"] if gid % 2 == 0 else ["Heuristic", "GT"]
        w = random.choice([0, 1])
        for seat, ag in enumerate(a):
            rows.append(dict(game_id=gid, setting="2p", agent=ag, seat=seat, rank=1 if seat == w else 2))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="?"); ap.add_argument("--focus", default="GT")
    ap.add_argument("--outdir", default="out"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    df = selftest() if a.selftest else pd.read_csv(a.csv)
    print(analyse(df, a.focus, a.outdir).to_string(index=False))

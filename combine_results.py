#!/usr/bin/env python3
"""Combine per-run tournament_table.csv files into ONE paper table + ONE figure.
usage: python combine_results.py   (edit RUNS below to point at your analyze_tournament.py output dirs)"""
import pandas as pd, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
RUNS = [  # (outdir, group label, display name of the focus agent)
 ("out_gt2_2p",  "Full game vs. baselines", "GT"),
 ("out_gt2_3p",  "Full game vs. baselines", "GT"),
 ("out_gt2_4p",  "Full game vs. baselines", "GT"),
 ("out_heur_2p", "Reference: Heuristic vs. Random", "Heuristic"),
 ("out_heur_3p", "Reference: Heuristic vs. Random", "Heuristic"),
 ("out_heur_4p", "Reference: Heuristic vs. Random", "Heuristic"),
 ("out_d2_vs_d1","Search depth (2-player)", "GT h=2"),
 ("out_d3_vs_d2","Search depth (2-player)", "GT h=3"),
]
NAME = {"gt1":"GT h=1","gt2":"GT h=2","random":"Random","heuristic":"Heuristic"}
rows=[]
for d,grp,foc in RUNS:
    t=pd.read_csv(f"{d}/tournament_table.csv")
    for r in t.itertuples():
        opp=" + ".join(NAME.get(x,x) for x in r.opponents.split("+"))
        rows.append(dict(group=grp,setting=r.setting,focus=foc,opponent=opp,games=r.games,win=r.win_rate,
                         lo=r.ci_lo,hi=r.ci_hi,chance=r.chance,avg_rank=r.avg_rank))
df=pd.DataFrame(rows); df.to_csv("combined_results.csv",index=False)
with open("combined_table.tex","w") as f:
    f.write("\\begin{tabular}{llllrcc}\n\\toprule\nSetting & Agent & vs.\\ (all others) & Games & Win rate [95\\% CI] & Chance & Avg.\\ rank\\\\\n\\midrule\n")
    for g,sub in df.groupby("group",sort=False):
        f.write(f"\\multicolumn{{7}}{{l}}{{\\emph{{{g}}}}}\\\\\n")
        for r in sub.itertuples():
            f.write(f"{r.setting} & {r.focus} & {r.opponent} & {r.games} & {r.win:.3f} [{r.lo:.3f}, {r.hi:.3f}] & {r.chance:.2f} & {r.avg_rank:.2f}\\\\\n")
    f.write("\\bottomrule\n\\end{tabular}\n")
fig,ax=plt.subplots(figsize=(7,4.6)); y=list(range(len(df)))[::-1]
lab=[f"{r.setting} {r.focus} vs {r.opponent}" for r in df.itertuples()]
ax.errorbar(df.win,y,xerr=[df.win-df.lo,df.hi-df.win],fmt="o",capsize=3,ms=5)
ax.scatter(df.chance,y,marker="|",s=220,color="k",label="chance (1/#players)")
ax.set_yticks(y); ax.set_yticklabels(lab,fontsize=8.5); ax.set_xlim(0,1)
ax.set_xlabel("Win rate of first-named agent (95% Wilson CI)",fontsize=10); ax.legend(fontsize=8,loc="lower right")
fig.tight_layout(); fig.savefig("combined_winrate.pdf"); fig.savefig("combined_winrate.png",dpi=200)
print(df.to_string(index=False))

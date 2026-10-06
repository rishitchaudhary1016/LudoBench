# GT Agent Validation: Verified Report (supersedes the earlier "package")

Everything below was checked against your repository (`rishitchaudhary1016/LudoBench`, commit `f431d3d`) and **the real tournaments were run with your code** in my sandbox. Seeds are `0..N-1`, seats are balanced, and the run scripts and raw game logs are included so you can reproduce all of it.

## 0. Headline findings (read this first)

1. **GT is clearly stronger than Random and Heuristic in 2-player games.** GT beats Heuristic 59.4% [56.3, 62.4] over 1,000 games. This reproduces the paper's 59%.
2. **The edge shrinks as players are added, and disappears at 4 players.**
   - GT vs Heuristic is 37.3% in 3-player play (chance 33.3%) and **26.5% in 4-player play (chance 25%; the 95% interval [23.9, 29.4] includes chance).**
   - **65% of your spots (338 of 520 entries) are 3- or 4-player**, and those labels come from the multi-player MaxN agent. A reviewer who runs this will find it, so address it in the paper.
3. **Search depth matters.** Depth 2 beats depth 1 63.0% [60.9, 65.1], and depth 3 beats depth 2 55.2% [52.1, 58.3]. That is good evidence that the search does real work. It also shows that depth 2 is not the ceiling, so never call it "optimal".
4. **A uniform-random legal move matches the GT token index 43.3% of the time on your released spots.** Your headline "LLMs agree 40–46%" sits on top of that chance level, which confirms Reviewer 2's weakness 3 (R2-W3). This is the biggest threat to the paper's story. See Section 5.
5. **The paper's Fig. 2 "Heuristic beats Random 77%" does not reproduce.** I get 84.4% [82.7, 85.9] over 2,000 games. On just the first 200 seeds I get 84%. GT's numbers reproduce fine. Check how Fig. 2 was generated.
6. **The repo has no "Greedy" or "Safe" agent.** `agents.py` contains only `RandomAgent` and `HeuristicAgent`; the Heuristic is the greedy baseline. Don't add new agents.

---

## 1. Repository map (verified)

| Purpose | File | Notes (from reading the code) |
|---|---|---|
| Game engine, legal moves, win | `ludo_env.py` | `LudoEnv`: seeds global `random` in the constructor; `play_game(max_steps=1000)` ends at the **first** winner; opens `game_log.txt`, `llm_log.txt`, `player*.txt` in the **current directory** (don't run parallel jobs in one folder). |
| Baseline agents | `agents.py` | `BaseAgent`, `RandomAgent`, `HeuristicAgent` (matches Table 14: base=50, progress, +100 capture, +20 safe). |
| GT agent (2-player) | `game_theory_agent.py` | `GameTheoryAgent(search_depth=2)`: Expectiminimax. **Falls back to Heuristic if not exactly 2 players.** |
| GT agent (3–4 player) | `game_theory_multiplayer_agent.py` | `GameTheoryMultiplayerAgent`: **delegates to `GameTheoryAgent` for 2 players**; for 3–4 uses the Expectimax-MaxN approximation. |
| Full-game runner (baselines + LLM) | `run_experiments.py` | Fixed list of matchups for 2/3/4 players. **No GT agent in it.** |
| Full-game runner (GT) | `run_gt_experiments.py` | **2-player only**; `--p0 --p1 --games --depth --seed-start`; agents `gt, heuristic, random, llm, dummy_llm`. **Prints only; saves nothing.** Seat 0 is fixed (not seat-balanced). Uses the same depth for both players if both are GT. Would raise `KeyError` if a game times out (winner=None). |
| Per-game metrics | `evaluation.py` | `evaluate(env)` returns winner, steps, captures, safe moves, LLM fallbacks. **No finishing positions.** |
| Spot evaluation | `spot_evaluation.py`, `run_all_spots.py` (LLM), `run_all_spots_gt.py` (GT), `run_all_spots_baseline.py` | `run_all_spots_gt.py` always uses `GameTheoryMultiplayerAgent` (`--depth`, default 2) and records `gt_mode`, `gt_move`, `heuristic_move`. |
| LLM-vs-GT alignment | `analysis_scripts/compare_llm_vs_gt.py` | Agreement = `int(llm_move) == int(gt_move)` (**token index**), over spots where **both** are valid. Answers R4-Q1: alignment is on valid outputs only. |
| Dataset | `spots_40/*.json` | 11 files × 40 + `grudge_paired` × 80 = 520 entries / 480 boards. By player count: **182 two-player, 169 three-player, 169 four-player**. |
| Docs | `read.txt`, `overall.txt`, `rules.txt`, `evaluation.txt`, `spot_creation.txt`, `spot_docs/` | The repo's own documentation. |

### How GT works (verified in code)

| Question | Answer |
|---|---|
| Expectiminimax? | Yes, 2 players. The root maximises. The opponent **minimises the same evaluator** (an adversarial model). Chance nodes average over dice 1–6. |
| MaxN? | Yes, 3–4 players: each player maximises its own component. Terminal: +1 winner, −1/(n−1) losers. Evaluator centred by subtracting the mean. |
| Heuristic evaluation? | Yes, at the cutoff: `0.0025·Δprogress + 0.20·Δfinished − 0.05·Δbase + 0.01·Δsafe`, clipped to ±0.999 (`game_theory_agent.py` lines 216–220). |
| Depth | `search_depth=2` → **your move, then one following decision (usually the opponent's), then the evaluator.** Depth 1 = pick the move with the best evaluator value, nothing more. |
| **Tie-breaking** | `if val > best_val` (strict) → **the lowest token index among equal-valued moves.** Tokens in base are interchangeable, so GT always picks the lowest index. This is exactly Reviewer 2's weakness 4 (R2-W4). **137 of 520 spots have ≥2 legal tokens on the same square.** |
| Incidental | In the engine, a piece **inside the home path can only move when the roll lands exactly on home end** (`ludo_env.py` lines 75–79). Confirm that this is intended, since Appendix B describes "progressing along the home path". |

---

## 2. Exact commands (all worked on your code)

Work in a scratch directory, because `LudoEnv` writes log files into the current directory. Put `run_gt_tournament.py` and `analyze_tournament.py` in the repo root (or add the repo to `PYTHONPATH`).

**A. Your own runner (2-player only, prints a summary, saves nothing):**
```bash
python run_gt_experiments.py --p0 gt --p1 heuristic --games 1000 --seed-start 0
python run_gt_experiments.py --p0 heuristic --p1 gt --games 1000 --seed-start 0   # seat swap
```
It prints "Win rate P0/P1". Win rates are **not stored anywhere**, so this does not suffice for the paper.

**B. My seat-balanced runner (2/3/4 players, writes a CSV, reuses your code unchanged):**
```bash
mkdir -p scratch && cd scratch && export PYTHONPATH=..   # repo root
R=../run_gt_tournament.py
python $R --focus gt2 --opponents random heuristic --players 2 --games 1000 --out t2p_gt2.csv
python $R --focus gt2 --opponents random heuristic --players 3 --games 1000 --out t3p_gt2.csv
python $R --focus gt2 --opponents random heuristic --players 4 --games 1000 --out t4p_gt2.csv
python $R --focus heuristic --opponents random --players 2 --games 2000 --out t2p_heur.csv
python $R --focus gt2 --opponents gt1 --players 2 --games 2000 --out t2p_d2_vs_d1.csv
python $R --focus gt3 --opponents gt2 --players 2 --games 500 --seed-start 0   --out d3_a.csv
python $R --focus gt3 --opponents gt2 --players 2 --games 500 --seed-start 500 --out d3_b.csv
```
- Speed: GT games take ~0.02 s (2p) and ~0.04 s (4p). Depth 3 is ~0.3 s per game. **All runs together take ~10 minutes.**
- Don't run jobs in the background of one folder. They collide on the log files.
- To analyse: `python analyze_tournament.py t2p_gt2.csv --focus gt2 --outdir out_gt2_2p`, then `python combine_results.py` for the combined table and figure.

**Reading the output:** the CSV has one row per (game, agent): `game_id, setting, matchup, agent, seat, rank, finished, progress`. `rank` 1 = winner. In 2-player games rank is exact. In 3–4 player games the engine stops at the first winner, so **non-winner ranks are a proxy** (ordered by finished pieces, then progress). Say so in the paper, or report only win rates there.

**How many games:** ≥1,000 per pairing (the 95% interval then is about ±3 points). Fig. 2's 200 games gave ±7.

---

## 3. Results (real runs, this commit)

| Setting | Agent vs. | Games | Win rate [95% CI] | Chance | Avg. rank* |
|---|---|---|---|---|---|
| 2p | GT vs Random | 1000 | **0.912** [0.893, 0.928] | 0.50 | 1.09 |
| 2p | GT vs Heuristic | 1000 | **0.594** [0.563, 0.624] | 0.50 | 1.41 |
| 3p | GT vs 2× Random | 1000 | 0.762 [0.735, 0.787] | 0.33 | 1.29 |
| 3p | GT vs 2× Heuristic | 1000 | 0.373 [0.344, 0.403] | 0.33 | 1.93 |
| 4p | GT vs 3× Random | 1000 | 0.676 [0.646, 0.704] | 0.25 | 1.47 |
| 4p | GT vs 3× Heuristic | 999† | **0.265** [0.239, 0.294] | 0.25 | 2.56 |
| 2p | Heuristic vs Random (reference) | 2000 | 0.844 [0.827, 0.859] | 0.50 | 1.16 |
| 3p | Heuristic vs 2× Random | 1000 | 0.721 [0.692, 0.748] | 0.33 | 1.33 |
| 4p | Heuristic vs 3× Random | 1000 | 0.649 [0.619, 0.678] | 0.25 | 1.49 |
| 2p | GT h=2 vs GT h=1 | 2000 | 0.630 [0.609, 0.651] | 0.50 | 1.37 |
| 2p | GT h=3 vs GT h=2 | 1000 | 0.552 [0.521, 0.583] | 0.50 | 1.45 |

\*Average rank is exact only in 2-player games; in 3–4 player games it is the proxy described above.
†One 4-player game hit the 1,000-step cap and was excluded.

Files: `results/combined_results.csv`, `results/combined_table.tex`, `results/combined_winrate.pdf/.png`, plus all raw game CSVs in `results/`. Seat balance is built in (the focus agent's seat rotates).

**What this supports and what it does not**

| Claim | Supported? |
|---|---|
| GT > Random, 2/3/4 players | ✅ Yes, large margins everywhere. |
| GT > Heuristic, 2-player | ✅ Yes, moderate (59%). |
| GT > Heuristic, 3-player | ⚠️ Small (37% vs 33% chance). |
| GT > Heuristic, 4-player | ❌ No evidence (26.5% vs 25%). |
| More search depth is stronger | ✅ Yes (h1 < h2 < h3, diminishing returns). |
| GT choices are optimal / ground truth | ❌ Not supported; h=3 beats h=2. |

**A plausible but unproven explanation:** in 4-player games the MaxN agent sees only one other player's move, and its centred evaluator carries less information. Don't state a cause in the paper without testing it.

---

## 4. LaTeX subsection (uses the real numbers)

Define `\newcommand{\refagent}{\textsc{GT}}` and `\TODO` as before. Insert `results/combined_table.tex` and `results/combined_winrate.pdf`.

```latex
\subsection{Positioning and Validation of the \refagent{} Agent as a Reference Baseline}
\label{sec:gt-validation}

\paragraph{Role of the agent.}
We use \refagent{} as a \emph{reference baseline}, not as ground truth and not as an
optimal solver. Ludo with dice, captures and up to four players has a large stochastic
game tree, and we make no claim that \refagent{} computes a game-theoretic optimum.
Its purpose is to provide a fixed, reproducible policy that reasons about consequences,
so that LLM \emph{preferences} can be compared with it. ``Alignment'' therefore denotes
agreement with this reference policy, not correctness; a disagreement may reflect a
different but defensible playing style.

\paragraph{What the agent computes.}
With two players, \refagent{} runs depth-limited expectiminimax ($h{=}2$): it evaluates
each legal move by averaging over all six dice outcomes and assuming that the next mover
chooses the reply that is worst for it according to the same evaluator. With three or
four players it uses an Expectimax-MaxN approximation in which each player maximises its
own utility component. At the cutoff it applies a linear evaluator over differences in
progress, finished pieces, pieces in base and pieces on safe squares
(Appendix~\ref{app:gt}). By contrast, the Random agent ignores the board and the
Heuristic agent scores each move in isolation (progress plus capture and safe-square
bonuses), without modelling dice outcomes or the opponent's reply.

\paragraph{Empirical validation.}
If \refagent{} is a meaningful reference it should win more often than the policies it
is compared with. Table~\ref{tab:gt-tournament} and Figure~\ref{fig:gt-tournament}
report full games with 1{,}000 seat-balanced games per pairing (95\% Wilson intervals).
In two-player games \refagent{} wins 91.2\% against Random and 59.4\% against Heuristic
(95\% CI $[56.3, 62.4]$; chance 50\%). With three players it wins 37.3\% against two
Heuristic agents (chance 33.3\%), and with four players it wins 67.6\% against three
Random agents but only 26.5\% against three Heuristic agents (95\% CI $[23.9, 29.4]$;
chance 25\%). We therefore establish that \refagent{} is a stronger player than greedy
and random play in the two-player setting, a smaller advantage in three-player games,
and \emph{no} measurable advantage over the Heuristic agent in four-player games.
Search depth matters: in two-player games $h{=}2$ beats $h{=}1$ in 63.0\% of games
(95\% CI $[60.9, 65.1]$) and $h{=}3$ beats $h{=}2$ in 55.2\% (95\% CI $[52.1, 58.3]$),
which indicates that the search contributes to playing strength and that $h{=}2$ is not
an upper bound.

\begin{table}[t]\centering
\input{results/combined_table.tex}
\caption{Full-game win rates (95\% Wilson CI). Chance is $1/\#$players. Average rank is
exact only for two players; for three and four players non-winners are ordered by finished
pieces and then progress at the end of the game. Seats are rotated.}
\label{tab:gt-tournament}
\end{table}

\paragraph{Limitations.}
\refagent{} should be read as a strong but imperfect reference, for six reasons.
(i) It is depth-limited and is outperformed by a deeper search ($h{=}3$).
(ii) Its evaluator is a hand-tuned linear function, so its preferences in tradeoff
categories (for example finishing versus capturing) reflect our modelling choices as
well as game structure; we have not yet measured their sensitivity to the weights.
(iii) It assumes uniform dice, and its multi-player variant is a MaxN approximation
without equilibrium guarantees.
(iv) Because the multi-player variant shows no measurable advantage over the Heuristic
agent with four players, the 65\% of our spots that involve three or four players
should be read as ``what a shallow search prefers'' rather than as the choice of a
stronger player; we therefore report alignment separately by player count.
(v) Superiority over weaker baselines shows relative strength, not closeness to optimal
play. (vi) We have not validated its spot-level choices against expert humans or a
stronger solver. We accordingly describe disagreement as ``divergence from the
reference'' and never as ``suboptimal''.
```

Edit the wording of limitation (ii) if you run the weight-sensitivity check (Section 7).

**Companion wording changes (do these first, they cost an hour):** replace "principled strategic ceiling" (abstract line 9, §4 lines 164–165, Table 3), "strategically suboptimal" (line 185, line 209), "strategically superior" (line 248), and consider renaming "Game-Theory agent" to "Expectimax Reference Agent".

---

## 5. A related problem you must fix before resubmitting (R2-W3, not part of R4-1)

From the stored GT results in `spot_results_gt/`, a **uniform-random legal move matches the GT token index 43.3% of the time** (42.6% on 2-player spots, 43.2% on 3-player, 44.0% on 4-player). Per category the chance level ranges from 25% (extra_turn, capture_vs_openexisting, safe_vs_openexisting: 4 legal moves) to 50% (capture_vs_home, capture_vs_home_finish, home_entry, overshoot, safe, grudge: 2 legal moves). The paper's 40–46% LLM alignment is therefore **not distinguishable from chance** as currently reported. Index-ambiguity makes it worse: 137 of 520 spots have ≥2 legal tokens on the same square.

Fix (cheap, no API calls): report alignment against this chance baseline per category, make alignment **equivalence-aware** (count a move as aligned if it leads to the same resulting position, with tokens treated as interchangeable), and use a tie-aware reference set. Then rewrite §6.2 and the abstract around "chance-corrected" alignment.

Also note: the committed `spot_results_40/none` and the committed `spot_results_gt/llm_vs_gt_comparison.csv` do **not** match each other (381 vs 479 valid pairs). I did not use them. Re-run `compare_llm_vs_gt.py` on the exact model outputs you report.

---

## 6. Reviewer-response table (Reviewer 4, Reason to Reject #1 and Question 2)

*Note: this criticism is Reviewer **4**'s, not Reviewer 1's.*

| Sub-point | Criticism (paraphrased) | Why raised | Code | Revision | Evidence | Effort | Impact |
|---|---|---|---|---|---|---|---|
| 1a | Called "game-theory"/"ceiling" but is depth-2 search with a hand-tuned evaluator. | Appendix H admits the limits; the abstract overclaims. | `game_theory_agent.py`, `game_theory_multiplayer_agent.py` | Reword and rename (Section 4). | Code facts in §1 | S | **High** |
| 1b | Conclusions in §6.2–6.5 depend on alignment with GT. | Alignment, "correct" tradeoffs, "suboptimal" all use it. | `compare_llm_vs_gt.py`, `run_all_spots_gt.py` | Report alignment by player count and vs chance (Section 5). | 43.3% chance baseline | S–M | **High** |
| 1c | Win rate vs the heuristic only shows GT > greedy. | Fig. 2 is the only validation. | `run_gt_experiments.py` | State the claim narrowly; add the table above. | Tournament table (1,000+ games per cell) | **Done** | Med-High |
| 1d | Study depth, weights, stronger agents/humans. | No robustness analysis exists. | agent constructors | Depth results done; weight sweep next; humans/rollouts → future work. | Depth h1<h2<h3 | Depth done; weights **S–M** | **High** |
| 1e | "Ceiling" and "more than half suboptimal" unvalidated. | Strong wording. | paper text | Wording table. | — | S | **High** |
| Q2 | How sensitive are GT decisions to depth and weights? | Same as 1d. | `game_theory_agent.py` lines 216–219 | New sensitivity paragraph. | Depth done; weights pending | S–M | **High** |

**Suggested rebuttal sentence (true as of now):**
> We agree that the agent is not a game-theoretic optimum. We now describe it as a search-based reference baseline. We report 1,000-game seat-balanced tournaments with confidence intervals for 2-, 3- and 4-player games, which show a clear advantage over Random and Heuristic in two-player games, a small advantage with three players, and no measurable advantage over Heuristic with four players. We also show that deeper search is stronger, and we report alignment by player count and against a chance baseline.

---

## 7. What to do next (priority order)

| # | Task | Effort | Why |
|---|---|---|---|
| 1 | Do the wording changes and drop in the LaTeX subsection. | S (2–3 h) | Removes the overclaim itself. |
| 2 | Chance-corrected, equivalence-aware alignment, split by player count (Section 5). | S–M (1 day) | Without it, §6.2's headline is not defensible. |
| 3 | **Evaluator-weight sensitivity.** The four weights are hard-coded at `game_theory_agent.py` lines 216–219 and `game_theory_multiplayer_agent.py` lines 228–231. Make them constructor arguments; for each of the 4 weights try ×0.5 and ×2; re-run `run_all_spots_gt.py` and report per-category how many preferred moves change. | S–M (0.5–1 day) | I did **not** run this. I suspect the finish-vs-capture preferences (0.20 vs 0.0025) depend on these weights, and it is better you find out before the reviewers do. |
| 4 | Spot-label stability across depth: `python run_all_spots_gt.py --depth 1/2/3 --out-dir ...`, then count how many of the 520 labels change. | S (2–4 h) | Cheap, answers R4-Q2. |
| 5 | Find out why Fig. 2's Heuristic-vs-Random (77%) does not reproduce; correct the figure. | S | A reviewer will rerun it. |
| 6 | Optional: a depth-3 4-player check, or a rollout agent. | M–L | Not required now. |

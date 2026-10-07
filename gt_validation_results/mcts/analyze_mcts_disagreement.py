#!/usr/bin/env python3
"""
GT (depth=2) vs MCTS disagreement analysis.

Run from the repo root (LudoBench/):
    python validation/analyze_mcts_disagreement.py

Reads (all pre-existing, nothing is regenerated):
    gt_validation_results/results/mcts_vs_gt_results.csv     GT / MCTS moves per spot
    spots_40/spots_*.json                                    the boards
    gt_validation_results/depth_stability/*                  GT depth-2 vs depth-3 labels, home-entry depth sweep
Writes:
    validation/results/mcts_disagreement_analysis.txt

Neither GT nor MCTS is called or modified. Move *types* (capture / finish / ...) are recovered from the boards
with the repo's own classify_move(). "1-ply evaluator" numbers are plain arithmetic with GT's cutoff-evaluator
weights, computed offline on the spot boards (a diagnostic, not a GT run).
"""
import argparse
import csv
import glob
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from spot_evaluation import SpotEnv, compute_legal_moves   # noqa: E402
from run_all_spots_gt import classify_move                  # noqa: E402

W_PROG, W_FIN, W_BASE, W_SAFE = 0.0025, 0.20, 0.05, 0.01    # GT cutoff-evaluator weights (game_theory_*agent.py)


# ----------------------------------------------------------------------------- stats helpers
def binom_p(k, n, p0):
    """Exact two-sided binomial p-value (sum of outcomes no more likely than k)."""
    pm = [math.comb(n, i) * p0 ** i * (1 - p0) ** (n - i) for i in range(n + 1)]
    return min(1.0, sum(x for x in pm if x <= pm[k] * (1 + 1e-9)))


def fisher_p(a, b, c, d):
    """Two-sided Fisher exact test for [[a, b], [c, d]]."""
    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d
    def pmf(x):
        return math.comb(r1, x) * math.comb(r2, c1 - x) / math.comb(n, c1)
    p_obs = pmf(a)
    lo, hi = max(0, c1 - r2), min(r1, c1)
    return min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= p_obs * (1 + 1e-9)))


def fp(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def pct(a, b):
    return f"{100.0 * a / b:5.1f}%" if b else "  n/a "


# ----------------------------------------------------------------------------- board helpers
def prog(env, pid, pos):
    """Progress exactly as in GT's evaluator."""
    if pos == -1:
        return 0
    hs = env.HOME_START + pid * env.HOME_LEN
    if 0 <= pos < env.BOARD_SIZE:
        return (pos - env.START_POSITIONS[pid]) % env.BOARD_SIZE + 1
    return env.BOARD_SIZE + (pos - hs + 1)


def move_kind(c):
    if c["capture"]:
        return "capture"
    if c["new_pos"] == c["home_end"]:
        return "finish"
    if c["home_entry"]:
        return "home_path"
    if c["bring_out"]:
        return "bring_out"
    return None


def after_state(env, cur, m, c):
    toks = {p: list(v) for p, v in env.tokens.items()}
    if c["capture"]:
        for o in env.player_ids:
            if o != cur:
                toks[o] = [-1 if x == c["new_pos"] else x for x in toks[o]]
    toks[cur][m] = c["new_pos"]
    return toks


def central_eval(env, toks, cur):
    """GT cutoff evaluator, root-centred (own score minus mean of all players)."""
    raw = []
    for pid in env.player_ids:
        he = env.HOME_START + pid * env.HOME_LEN + env.HOME_LEN - 1
        s = 0.0
        for p in toks[pid]:
            if p == -1:
                s -= W_BASE
                continue
            if p == he:
                s += W_FIN
            s += W_PROG * prog(env, pid, p)
            if 0 <= p < env.BOARD_SIZE and p in env.SAFE_SQUARES:
                s += W_SAFE
        raw.append(s)
    return raw[env.player_ids.index(cur)] - sum(raw) / len(raw)


def option_table(env, cur, dice, legal):
    """For every legal move: type, captured-piece progress, 1-ply evaluator gain."""
    base = central_eval(env, env.tokens, cur)
    out = {}
    for m in legal:
        c = classify_move(env, cur, dice, m)
        kind = move_kind(c)
        if kind is None:
            kind = "safe_sq" if (0 <= c["new_pos"] < env.BOARD_SIZE and c["new_pos"] in env.SAFE_SQUARES) else "advance"
        cap = prog(env, c["captured_player"], c["new_pos"]) if c["capture"] else None
        out[m] = dict(kind=kind, cap=cap, old=c["old_pos"], new=c["new_pos"],
                      sg=central_eval(env, after_state(env, cur, m, c), cur) - base)
    return out


# ----------------------------------------------------------------------------- load
def load(args):
    spots = {}
    for f in sorted(glob.glob(args.spots_glob)):
        for s in json.load(open(f)):
            spots[(os.path.basename(f), s["id"])] = s
    rows = list(csv.DictReader(open(args.csv)))
    depth = {}
    if os.path.exists(args.depth_csv):
        for r in csv.DictReader(open(args.depth_csv)):
            depth[(r["scenario_file"], r["spot_id"])] = r
    for r in rows:
        s = spots[(r["scenario_file"], r["scenario_id"])]
        env = SpotEnv(s["players"], {int(k): v for k, v in s["tokens"].items()})
        cur, dice = s["current_player"], s["dice"]
        legal = compute_legal_moves(env, cur, dice)
        g, m = int(r["GT_move"]), int(r["MCTS_move"])
        assert g in legal and m in legal, r
        opt = option_table(env, cur, dice, legal)
        own = env.tokens[cur]
        best = max(sorted(opt), key=lambda k: (round(opt[k]["sg"], 10), -k))   # 1-ply argmax, ties -> lowest index
        sg = sorted((round(v["sg"], 10) for v in opt.values()), reverse=True)
        d = depth.get((r["scenario_file"], r["scenario_id"]))
        r.update(env=env, cur=cur, dice=dice, legal=legal, opt=opt, g=g, m=m, agree=int(r["agreement"]),
                 npl=int(r["n_players"]), classes=len({own[x] for x in legal}), static_best=best,
                 top_gap=(sg[0] - sg[1]) if len(sg) > 1 else None,
                 d2=int(d["depth2_move"]) if d else None, d3=int(d["depth3_move"]) if d else None,
                 n_active=sum(1 for x in own if x != -1))
    return rows


# ----------------------------------------------------------------------------- report
def build(rows, args):
    L = []
    P = L.append
    cats = sorted({r["category"] for r in rows})
    N = len(rows)
    A = sum(r["agree"] for r in rows)
    D = N - A
    by = {c: [r for r in rows if r["category"] == c] for c in cats}
    dis = {c: [r for r in by[c] if not r["agree"]] for c in cats}

    def chance_cls(c):
        return sum(1.0 / r["classes"] for r in by[c]) / len(by[c])

    def chance_idx(c):
        return sum(1.0 / len(r["legal"]) for r in by[c]) / len(by[c])

    def title(t):
        P("")
        P("=" * 78)
        P(t)
        P("=" * 78)

    def sub(t):
        P("")
        P(t)
        P("-" * len(t))

    P("MCTS vs GT DISAGREEMENT ANALYSIS")
    P("=" * 78)
    P("Source CSV : gt_validation_results/results/mcts_vs_gt_results.csv (520 entries, unchanged)")
    P("GT         : GameTheoryMultiplayerAgent(depth=2)   MCTS: MCTSAgent(1000 rollouts, seed=0, c=sqrt(2))")
    P("Agreement  : same token index. (GT picks the lowest index among equal values; MCTS returns the lowest")
    P("             index of each equivalent-piece class. Disagreements between identical pieces: "
      f"{sum(1 for r in rows if not r['agree'] and r['env'].tokens[r['cur']][r['g']] == r['env'].tokens[r['cur']][r['m']])}.)")
    P("Not rerun  : GT, MCTS, tournaments, depth study. Nothing in GT / MCTS / spots was modified.")
    P("")
    P("Evidence labels used below")
    P("  [DATA]       counted directly from the CSV + spot boards (move types via the repo's classify_move()).")
    P("  [DERIVED]    arithmetic with GT's evaluator weights (0.0025*progress + 0.20*finished - 0.05*base +")
    P("               0.01*safe, centred on the player mean) computed offline on the boards. GT itself was not rerun;")
    P("               this '1-ply evaluator' reproduces GT's depth-2 label in "
      f"{sum(1 for r in rows if r['static_best'] == r['g'])}/{N} entries (section 7), so it is a good proxy.")
    P("  [HYPOTHESIS] plausible cause that the stored artifacts cannot test. The CSV holds only the chosen token;")
    P("               MCTS visit counts / win rates were not saved (MCTSAgent.last_search_info was not written).")

    # ------------------------------------------------------------------ 1
    title("1. OVERALL AND CHANCE BASELINE")
    cc_all = sum(1.0 / r["classes"] for r in rows) / N
    ci_all = sum(1.0 / len(r["legal"]) for r in rows) / N
    P(f"[DATA] Entries {N}: agree {A} ({100 * A / N:.1f}%), disagree {D} ({100 * D / N:.1f}%).")
    P(f"[DATA] If MCTS picked a legal move uniformly at random, expected agreement with GT would be")
    P(f"       {100 * ci_all:.1f}% by token index, or {100 * cc_all:.1f}% when identical pieces are merged (how MCTS actually")
    P(f"       enumerates moves). Observed {100 * A / N:.1f}%. Overall exact binomial p vs the merged baseline: "
      f"{fp(binom_p(A, N, cc_all))}.")
    P("       Chance differs a lot by category (extra_turn and safe_vs_openexisting have 4 legal tokens but only 2")
    P("       distinct moves, because 3 pieces sit in base). Raw 'Agree %' must be read against the chance column.")
    P("")
    P(f"{'category':26s}{'N':>4s}{'agree':>7s}{'dis':>5s}{'agree%':>8s}{'chance%':>9s}{'excess':>8s}{'p':>9s}  reading")
    P("-" * 92)
    for c in cats:
        n, a = len(by[c]), sum(r["agree"] for r in by[c])
        cc = chance_cls(c)
        p = binom_p(a, n, cc)
        ex = 100 * (a / n - cc)
        read = "AT CHANCE" if p >= 0.05 else ("above chance" if a / n > cc else "BELOW chance (systematic opposite)")
        P(f"{c:26s}{n:4d}{a:7d}{n - a:5d}{100 * a / n:7.1f}%{100 * cc:8.1f}%{ex:+7.1f}pp{fp(p):>9s}  {read}")
    P("(p: exact two-sided binomial test of observed agreements against the mean merged-piece chance rate of the")
    P(" category; n=40 per cell, so only large effects are detectable. grudge has 80 entries = 40 boards x 2.)")

    # ------------------------------------------------------------------ 2
    title("2. WHERE THE %d DISAGREEMENTS COME FROM" % D)
    order = sorted(cats, key=lambda c: -len(dis[c]))
    P(f"{'category':26s}{'dis':>5s}{'share':>8s}{'cumul.':>8s}")
    cum = 0
    for c in order:
        cum += len(dis[c])
        P(f"{c:26s}{len(dis[c]):5d}{100 * len(dis[c]) / D:7.1f}%{100 * cum / D:7.1f}%")
    top3 = sum(len(dis[c]) for c in order[:3])
    foc = ["capture_vs_home_finish", "safe_vs_openexisting", "extra_turn", "blocked", "home_entry"]
    nfoc = sum(len(dis[c]) for c in foc)
    P("")
    P(f"[DATA] Top 3 ({', '.join(order[:3])}): {top3} = {100 * top3 / D:.1f}% of all disagreements.")
    P(f"[DATA] The five requested focus categories: {nfoc} = {100 * nfoc / D:.1f}%. Adding overshoot: "
      f"{nfoc + len(dis['overshoot'])} = {100 * (nfoc + len(dis['overshoot'])) / D:.1f}%.")
    chance_cats = [c for c in cats if binom_p(sum(r['agree'] for r in by[c]), len(by[c]), chance_cls(c)) >= 0.05 and c in ("blocked", "home_entry", "overshoot")]
    rest = [r for r in rows if r["category"] not in chance_cats]
    P(f"[DATA] Dropping the {len(chance_cats)} categories whose agreement is statistically at chance "
      f"({', '.join(chance_cats)}): agreement on the remaining {len(rest)} entries = "
      f"{sum(r['agree'] for r in rest)}/{len(rest)} = {100 * sum(r['agree'] for r in rest) / len(rest):.1f}%.")

    # ------------------------------------------------------------------ 3
    title("3. WHAT EACH AGENT CHOSE WHEN THEY DISAGREED (move types, disagreements only)")
    P("Move type priority: capture > finish (lands on home end) > home_path > bring_out > safe_sq > advance.")
    P("(bring_out lands on a start square, which is a safe square; it is labelled bring_out.)")
    for c in order:
        tr = Counter((r["opt"][r["g"]]["kind"], r["opt"][r["m"]]["kind"]) for r in dis[c])
        P(f"  {c} ({len(dis[c])}/{len(by[c])}):  " + ";  ".join(f"GT {a} -> MCTS {b}: {n}" for (a, b), n in tr.most_common()))

    # ------------------------------------------------------------------ 4
    title("4. FOCUS CATEGORIES")

    # ---- cvhf
    c = "capture_vs_home_finish"
    g = by[c]
    d_ = dis[c]
    sub(f"4.1 {c}: {len(d_)}/{len(g)} disagreements ({100 * len(d_) / len(g):.1f}%), the largest single source")
    gt_fin = sum(1 for r in g if r["opt"][r["g"]]["kind"] == "finish")
    m_cap = sum(1 for r in g if r["opt"][r["m"]]["kind"] == "capture")
    P(f"GT preference   : finish the piece. GT finishes in {gt_fin}/{len(g)}.")
    P(f"MCTS preference : capture. MCTS captures in {m_cap}/{len(g)} and finishes in {len(g) - m_cap}/{len(g)}.")
    P(f"[DATA] Agreement {100 * sum(r['agree'] for r in g) / len(g):.1f}% vs {100 * chance_cls(c):.1f}% chance: the two agents hold opposite preferences.")
    capv = {id(r): [v["cap"] for v in r["opt"].values() if v["kind"] == "capture"][0] for r in g}
    bands = (("captured piece progress <=20", 0, 20), ("21-40", 21, 40), (">40", 41, 99))
    P("[DATA] MCTS capture rate by how far the victim piece had advanced (progress counted as in the evaluator):")
    for lab, lo, hi in bands:
        s_ = [r for r in g if lo <= capv[id(r)] <= hi]
        P(f"         {lab:30s} n={len(s_):2d}  MCTS captures {sum(1 for r in s_ if r['opt'][r['m']]['kind'] == 'capture'):2d}")
    ag = [r for r in g if r["agree"]]
    P(f"[DATA] The {len(ag)} agreements are all 'both finish'; victim progress there = "
      f"{sorted(capv[id(r)] for r in ag)} (4 of 5 are very low-value captures), dice = {sorted(r['dice'] for r in ag)}.")
    gaps = [r["opt"][r["m"]]["sg"] - r["opt"][r["g"]]["sg"] for r in d_]
    P(f"[DERIVED] Both options advance the same number of squares, so progress cancels. Finish earns +{W_FIN:.2f}; a capture earns")
    P(f"          +{W_BASE:.2f} (victim back to base) + {W_PROG}*victim_progress, at most {W_BASE + W_PROG * 52:.2f} (victim progress 52).")
    P(f"          So finish beats capture at the evaluator for EVERY possible board (margin >= {W_FIN - W_BASE - W_PROG * 52:.2f} unscaled).")
    P(f"          On these boards the centred 1-ply margin (capture minus finish) lies in [{min(gaps):+.3f}, {max(gaps):+.3f}], never positive.")
    flips = [r for r in g if r["d2"] != r["d3"]]
    P(f"[DATA] GT depth 3 changes {len(flips)}/{len(g)} labels here ({sum(1 for r in flips if r['opt'][r['d3']]['kind'] == 'capture')} of them to capture); MCTS matches GT depth 3 on "
      f"{sum(1 for r in g if r['m'] == r['d3'])}/{len(g)} (vs {sum(r['agree'] for r in g)}/{len(g)} for depth 2). Disagreements by player count: "
      f"2p {sum(1 for r in d_ if r['npl'] == 2)}/{sum(1 for r in g if r['npl'] == 2)}, 3p {sum(1 for r in d_ if r['npl'] == 3)}/{sum(1 for r in g if r['npl'] == 3)}, "
      f"4p {sum(1 for r in d_ if r['npl'] == 4)}/{sum(1 for r in g if r['npl'] == 4)} (not a multi-player artifact).")
    P(f"[DATA] Spot-design note: the finishing token is the lowest legal index in {sum(1 for r in g if min(r['legal']) == [k for k, v in r['opt'].items() if v['kind'] == 'finish'][0])}/{len(g)} spots,")
    P("       so an index-biased player 'agrees' with GT here without reasoning about the tradeoff.")
    P("Likely causes:")
    P("  1. [DERIVED] GT's finish-over-capture preference is fixed by the evaluator weights (0.20 vs <= 0.18), not discovered by search.")
    P("  2. [DATA] MCTS values the move by win probability under random continuation. It captures more often the more valuable the")
    P("     victim (12/16, 11/12, 12/12 by band), i.e. its choice is value-sensitive rather than random.")
    P("  3. [CONTEXT] In this engine a piece on the home path moves only on the exact roll that reaches home end, so declining a")
    P("     finish has a real cost; MCTS evidently does not find it decisive. This is a genuine modelling disagreement, which")
    P("     means the paper's statement that finishing is correct and capturing merely delays the opponent (Sec. 6.3) is a")
    P("     normative claim that an independent search agent does not support.")

    # ---- development categories
    DEVRES = {}

    def dev(cat, idx, extra_note):
        g = by[cat]
        d_ = dis[cat]
        sub(f"{idx} {cat}: {len(d_)}/{len(g)} disagreements ({100 * len(d_) / len(g):.1f}%)")
        one = sum(1 for r in g if r["n_active"] == 1)
        six = sum(1 for r in g if r["dice"] == 6)
        gt_bo = sum(1 for r in g if r["opt"][r["g"]]["kind"] == "bring_out")
        m_ex = sum(1 for r in g if r["opt"][r["m"]]["kind"] != "bring_out")
        P(f"Board structure : dice = 6 in {six}/{len(g)}; exactly 1 piece on the board and 3 in base in {one}/{len(g)}. "
          f"Real choice: bring a 2nd piece out vs move the lone piece.")
        P(f"GT preference   : bring a piece out. GT does so in {gt_bo}/{len(g)}.")
        P(f"MCTS preference : {extra_note} MCTS moves the existing piece in {m_ex}/{len(g)} and brings one out in {len(g) - m_ex}/{len(g)}.")
        a = sum(r["agree"] for r in g)
        P(f"[DATA] Agreement {100 * a / len(g):.1f}% vs {100 * chance_cls(cat):.1f}% chance (p {fp(binom_p(a, len(g), chance_cls(cat)))}): BELOW chance, i.e. a systematic opposite preference.")
        bo = [r["opt"][r["g"]]["sg"] for r in g]
        P(f"[DERIVED] 1-ply evaluator: bring-out = +{W_BASE:.2f} (leaves base) +{W_PROG} (1 square) +{W_SAFE} (start square is safe) = {W_BASE + W_PROG + W_SAFE:.4f};")
        P(f"          moving the lone piece 6 squares = {6 * W_PROG:.3f} (+{W_SAFE} if it lands safe). The margin is fixed by the weights, independent of the board,")
        P(f"          which is why GT chooses bring-out in {gt_bo}/{len(g)} at depth 1, 2 and 3 alike.")
        bands = (("0-17", 0, 17), ("18-34", 18, 34), ("35-52", 35, 52))
        P("[DATA] MCTS moves the lone piece, by how far that piece has already travelled:")
        cnt = {}
        for lab, lo, hi in bands:
            s_ = []
            for r in g:
                ex = [v for v in r["opt"].values() if v["kind"] != "bring_out"]
                pr_ = prog(r["env"], r["cur"], ex[0]["old"]) if len(ex) == 1 else None
                if pr_ is not None and lo <= pr_ <= hi:
                    s_.append(r)
            mv = sum(1 for r in s_ if r["opt"][r["m"]]["kind"] != "bring_out")
            cnt[lab] = (mv, len(s_))
            P(f"         lone-piece progress {lab:6s} n={len(s_):2d}  MCTS moves it {mv:2d}")
        a1, n1 = cnt["0-17"][0] + cnt["18-34"][0], cnt["0-17"][1] + cnt["18-34"][1]
        a2, n2 = cnt["35-52"]
        fpv = fisher_p(a2, n2 - a2, a1, n1 - a1)
        DEVRES[cat] = (a2, n2, a1, n1, fpv)
        P(f"         late (35-52) vs earlier: {a2}/{n2} vs {a1}/{n1}; Fisher exact p = {fp(fpv)}")
        P(f"[DATA] Agreement by player count: " + ", ".join(f"{k}p {sum(r['agree'] for r in g if r['npl'] == k)}/{sum(1 for r in g if r['npl'] == k)}" for k in (2, 3, 4)))
        P(f"[DATA] GT depth 3 changes {sum(1 for r in g if r['d2'] != r['d3'])}/{len(g)} labels; MCTS matches depth 3 on {sum(1 for r in g if r['m'] == r['d3'])}/{len(g)}. The GT label here is depth-stable.")
        P(f"[DATA] Spot-design note: GT's choice is the lowest legal index in {sum(1 for r in g if r['g'] == min(r['legal']))}/{len(g)} spots (base tokens come first).")

    dev("safe_vs_openexisting", "4.2", "safe-square move preferred (the 'safe' alternative is the lone piece landing on a safe square).")
    P("Likely causes:")
    P("  1. [DERIVED] GT's rule 'bring out on a 6' is the -0.05*base term. It is a weight choice, so it is not independent evidence")
    P("     that development is the stronger strategy.")
    P("  2. [HYPOTHESIS] MCTS values are win probabilities under uniform-random continuation with ~500 rollouts per root candidate")
    P("     (SE of a win rate ~0.02 at p=0.5). Tempo effects of one move are probably of that order, so part of the MCTS preference")
    P("     may be noise. The consistent 77.5% / 70% skew toward moving the lone piece suggests a systematic component as well.")
    P("     Cannot be separated without visit counts or more rollouts.")
    dev("extra_turn", "4.3", "advance the existing piece.")
    e = DEVRES["extra_turn"]
    sv_ = DEVRES["safe_vs_openexisting"]
    P("Likely causes: identical to 4.2 (same board structure, same weight-driven GT rule).")
    P(f"[DATA] MCTS brings a piece out in {e[1] - e[0]}/{e[1]} spots where the lone piece is late in its lap (Fisher p = {fp(e[4])}); the same direction")
    P(f"       appears in 4.2 ({sv_[1] - sv_[0]}/{sv_[1]}) but is not significant (p = {fp(sv_[4])}).")
    P("[HYPOTHESIS] A runner close to home has less left to gain from another 6, so MCTS spends the move on development there.")
    P("Together 4.2 and 4.3 are the 'develop your board' half of the GT strategy that the paper credits GT with; an independent")
    P("agent does not reproduce it (agreement 22.5% and 30.0%, below the 50% chance level).")

    # ---- blocked
    c = "blocked"
    g = by[c]
    d_ = dis[c]
    sub(f"4.4 {c}: {len(d_)}/{len(g)} disagreements ({100 * len(d_) / len(g):.1f}%)")
    forced = [r for r in g if len(r["legal"]) == 1]
    two = [r for r in g if len(r["legal"]) == 2]
    three = [r for r in g if len(r["legal"]) >= 3]
    P(f"Board structure : legal moves per spot = {dict(sorted(Counter(len(r['legal']) for r in g).items()))}. {len(forced)} forced-move spot "
      f"(agreement is trivial there).")
    zg = sum(1 for r in two if r["top_gap"] is not None and r["top_gap"] < 1e-9)
    P(f"[DERIVED] Among the {len(two)} two-move spots, {zg} have IDENTICAL 1-ply evaluator value: both options advance the same dice,")
    P("          and neither captures, lands safe, or leaves base. The 'blocked' piece is simply not a legal option; what remains is")
    P("          a choice between two equivalent plain advances.")
    P(f"[DATA] GT picks the lower-index legal move in {sum(1 for r in two if r['g'] == min(r['legal']))}/{len(two)} two-move spots "
      f"({100 * sum(1 for r in two if r['g'] == min(r['legal'])) / len(two):.0f}%); MCTS in {sum(1 for r in two if r['m'] == min(r['legal']))}/{len(two)} "
      f"({100 * sum(1 for r in two if r['m'] == min(r['legal'])) / len(two):.0f}%, i.e. chance).")
    dtwo = [r for r in two if not r["agree"]]
    P(f"[DATA] In the {len(dtwo)} two-move disagreements GT took the lower index {sum(1 for r in dtwo if r['g'] == min(r['legal']))} times.")
    fl = Counter((r["d2"], r["d3"]) for r in g if r["d2"] != r["d3"])
    P(f"[DATA] GT's own depth-2 vs depth-3 labels differ on {sum(fl.values())}/{len(g)} blocked spots (depth2 -> depth3 token: {dict(fl)}): the GT label is unstable here.")
    bo_d = [r for r in d_ if r["opt"][r["g"]]["kind"] == "bring_out"]
    P(f"[DATA] Split of the {len(d_)} disagreements: {len(dtwo)} are two-move indifferent advances (above); {len(bo_d)} are 3-move spots where GT brings a piece out and")
    P(f"       MCTS does not (same weight-driven pattern as 4.2/4.3, GT picks bring_out in {len(bo_d)}/{len(bo_d)}); the remaining {len(d_) - len(dtwo) - len(bo_d)} are other.")
    P(f"[DATA] Agreement {100 * sum(r['agree'] for r in g) / len(g):.1f}% vs {100 * chance_cls(c):.1f}% chance (p {fp(binom_p(sum(r['agree'] for r in g), len(g), chance_cls(c)))}): statistically at chance.")
    P("Likely causes:")
    P("  1. GT's label is mostly the tie-break convention (strict '>' keeps the lowest index) plus small opponent-reply effects.")
    P("  2. MCTS is near-random on near-indifferent choices. Neither agent supplies a meaningful reference label here.")
    P("  3. The category tests legality (block_rate, invalid rate), metrics that do not use GT. Including it in GT-alignment adds noise.")

    # ---- home_entry
    c = "home_entry"
    g = by[c]
    d_ = dis[c]
    sub(f"4.5 {c}: {len(d_)}/{len(g)} disagreements ({100 * len(d_) / len(g):.1f}%)")
    gh = sum(1 for r in g if r["opt"][r["g"]]["kind"] in ("home_path", "finish"))
    mh = sum(1 for r in g if r["opt"][r["m"]]["kind"] in ("home_path", "finish"))
    shape = Counter(tuple(sorted(v["kind"] for v in r["opt"].values())) for r in g)
    P(f"Board structure : every spot offers {dict(shape)} (home-path move vs plain main-board advance).")
    P(f"GT preference   : advance on the main board; GT enters the home path in only {gh}/{len(g)}.")
    P(f"MCTS preference : enter the home path in {mh}/{len(g)} ({100 * mh / len(g):.1f}%).")
    P(f"[DATA] All {len(d_)} disagreements are 'GT advance, MCTS home_path': "
      f"{sum(1 for r in d_ if r['opt'][r['g']]['kind'] == 'advance' and r['opt'][r['m']]['kind'] == 'home_path')}/{len(d_)}.")
    units = []
    for r in g:
        adv = [v for v in r["opt"].values() if v["kind"] == "advance"]
        hp = [v for v in r["opt"].values() if v["kind"] == "home_path"]
        if adv and hp:
            n = r["npl"]
            units.append(round((adv[0]["sg"] - hp[0]["sg"]) / (W_PROG * (n - 1) / n), 2))
    P(f"[DERIVED] The evaluator counts progress as rel+1 on the main board but as 52+home_step on the home path (= rel, one less).")
    P(f"          Entering the home path therefore costs exactly one progress unit ({W_PROG}) against a same-length advance. Measured on")
    P(f"          these boards, 1-ply (advance minus home-path), in progress units: {dict(Counter(units))}.")
    P(f"          That one-unit gap is the only 1-ply difference, and the 1-ply argmax equals GT's label in "
      f"{sum(1 for r in g if r['static_best'] == r['g'])}/{len(g)} spots.")
    sweep = {}
    sp = os.path.join("gt_validation_results", "depth_stability", "home_entry_depth_sweep.txt")
    if os.path.exists(sp):
        for mm in re.finditer(r"depth (\d): GT picks a home-entry move in (\d+)/(\d+)", open(sp).read()):
            sweep[int(mm.group(1))] = (int(mm.group(2)), int(mm.group(3)))
    if sweep:
        P("[DATA] Stored GT depth sweep (home_entry_depth_sweep.txt), share of spots where GT enters the home path: " +
          ", ".join(f"depth {k}: {a}/{b}" for k, (a, b) in sorted(sweep.items())) + ".")
        P(f"       MCTS ({mh}/{len(g)}) sits between GT depth 3 and depth 4: GT's preference moves toward MCTS as search deepens.")
    P(f"[DATA] MCTS matches GT depth 3 on {sum(1 for r in g if r['m'] == r['d3'])}/{len(g)} vs {sum(r['agree'] for r in g)}/{len(g)} for depth 2 (GT d2 != d3 on "
      f"{sum(1 for r in g if r['d2'] != r['d3'])}/{len(g)}).")
    P(f"[DATA] Agreement {100 * sum(r['agree'] for r in g) / len(g):.1f}% vs {100 * chance_cls(c):.1f}% chance: at chance.")
    P("Likely causes:")
    P("  1. [DERIVED] Evaluator off-by-one at the main-board / home-path boundary penalises home entry by one progress unit; with depth 2")
    P("     this is enough to make GT prefer a plain advance. This is the best-supported single-cause explanation in this study.")
    P("  2. [DATA] GT's label is depth-unstable (15/40 change at depth 3; 95% home entry by depth 5). MCTS has no depth cutoff and")
    P("     prefers the home path in most spots.")
    P("  3. Consequence: the paper's reading of GT as not prioritising home entry (Table 10 GT home-entry rate 0.13) is an artifact, so")
    P("     LLM-GT alignment in this category should not be interpreted as a strategy signal.")

    # ------------------------------------------------------------------ 5
    title("5. OTHER CATEGORIES (shorter)")
    c = "overshoot"
    g = by[c]
    sub(f"{c}: {len(dis[c])}/{len(g)} disagreements ({100 * len(dis[c]) / len(g):.1f}%)")
    zg = sum(1 for r in g if r["top_gap"] is not None and r["top_gap"] < 1e-9)
    P(f"[DATA] Every spot has exactly 2 legal moves, both plain advances. 1-ply evaluator values are identical in {zg}/{len(g)}.")
    P(f"[DATA] GT takes the lower index in {sum(1 for r in g if r['g'] == min(r['legal']))}/{len(g)}; MCTS in {sum(1 for r in g if r['m'] == min(r['legal']))}/{len(g)}. "
      f"Agreement {100 * sum(r['agree'] for r in g) / len(g):.1f}% = {100 * chance_cls(c):.1f}% chance. GT d2 != d3 on {sum(1 for r in g if r['d2'] != r['d3'])}/{len(g)}.")
    P("Cause: same as blocked. The illegal (overshooting) piece just removes an option; the remaining choice is near-indifferent by")
    P("construction, so these 20 disagreements carry no strategic information about either agent. (The paper's overshoot metrics do not use GT.)")

    c = "safe"
    g = by[c]
    sub(f"{c}: {len(dis[c])}/{len(g)} disagreements ({100 * len(dis[c]) / len(g):.1f}%)")
    gs = sum(1 for r in g if r["opt"][r["g"]]["kind"] == "safe_sq")
    ms = sum(1 for r in g if r["opt"][r["m"]]["kind"] == "safe_sq")
    P(f"[DATA] GT lands on the safe square in {gs}/{len(g)} ({100 * gs / len(g):.1f}%), MCTS in {ms}/{len(g)} ({100 * ms / len(g):.1f}%). Types: "
      + ";  ".join(f"GT {a} -> MCTS {b}: {n}" for (a, b), n in Counter((r['opt'][r['g']]['kind'], r['opt'][r['m']]['kind']) for r in dis[c]).most_common()))
    P(f"[DERIVED] The only evaluator difference between the options is the +{W_SAFE} safe-square bonus, so GT's label is decided by that single weight.")
    P(f"Disagreements by player count: " + ", ".join(f"{k}p {sum(1 for r in dis[c] if r['npl'] == k)}" for k in (2, 3, 4)) + ". Agreement is not significantly different from chance (p above).")
    P("[HYPOTHESIS] MCTS values a safe-square landing less than GT's fixed +0.01 bonus does. Both are defensible; a mild, spread-out disagreement.")

    c = "capture_vs_openexisting"
    g = by[c]
    sub(f"{c}: {len(dis[c])}/{len(g)} disagreements ({100 * len(dis[c]) / len(g):.1f}%)")
    P(f"[DATA] All {len(dis[c])} are 'GT brings a piece out, MCTS captures' (dice = 6). They occur only with 3 or 4 players "
      f"(3p {sum(1 for r in dis[c] if r['npl'] == 3)}, 4p {sum(1 for r in dis[c] if r['npl'] == 4)}); with 2 players agreement is "
      f"{sum(r['agree'] for r in g if r['npl'] == 2)}/{sum(1 for r in g if r['npl'] == 2)}.")
    P("[DERIVED] GT's multi-player evaluator is centred on the mean of all players, so a capture credits only 1/n of the victim's loss")
    P("          while own gains count (n-1)/n. Capture beats bring-out (own gain 0.0625 vs 0.015 for a 6-square capture move) only if")
    P("          victim_progress > (n-1)*19 - 20, i.e. any capture for n=2, > 18 for n=3, > 37 for n=4.")
    for npl in (2, 3, 4):
        gg = [r for r in g if r["npl"] == npl]
        caps = sorted(r["opt"][r["g"]]["cap"] for r in gg if r["opt"][r["g"]]["kind"] == "capture")
        outs = sorted([v["cap"] for v in r["opt"].values() if v["cap"] is not None][0] for r in gg if r["opt"][r["g"]]["kind"] != "capture")
        P(f"[DATA] {npl}p: victim progress where GT captures: {caps}")
        P(f"       {npl}p: victim progress where GT brings out: {outs}")
    P("       Observed split matches the derived thresholds (3p: out at 12-16, capture from 21; 4p: out at 5-34, capture mostly from 42), with one 4p exception.")
    P(f"       Mean victim progress in the {len(dis[c])} disagreements = "
      f"{sum([v['cap'] for v in r['opt'].values() if v['cap'] is not None][0] for r in dis[c]) / len(dis[c]):.1f} vs "
      f"{sum([v['cap'] for v in r['opt'].values() if v['cap'] is not None][0] for r in g) / len(g):.1f} over all {len(g)} spots: low-value captures.")
    P("Cause: GT's player-count-dependent discounting of captures; MCTS captures in 39/40.")
    P("(Compatible with the weak 4-player tournament result in GT_validation_REPORT.md, but this analysis does not show a causal link.)")

    for c, note in (("capture_vs_home", "GT captures, MCTS enters the home path"),
                    ("capture", "GT brings out / advances, MCTS captures"),
                    ("capture_vs_safe", "GT captures, MCTS takes the safe square (2) or GT brings out (1)"),
                    ("grudge", "both pick a capture, but with different pieces (different victim)")):
        g = by[c]
        d_ = dis[c]
        caps_d = [v["cap"] for r in d_ for v in r["opt"].values() if v["cap"] is not None and (v is r["opt"][r["g"]] or v is r["opt"][r["m"]])]
        caps_a = [v["cap"] for r in g for v in [r["opt"][r["g"]]] if v["cap"] is not None]
        sub(f"{c}: {len(d_)}/{len(g)} disagreements ({100 * len(d_) / len(g):.1f}%)")
        P(f"[DATA] {note}. Player counts of disagreements: " + ", ".join(f"{k}p {sum(1 for r in d_ if r['npl'] == k)}" for k in (2, 3, 4))
          + f"; agreement with 2 players = {sum(r['agree'] for r in g if r['npl'] == 2)}/{sum(1 for r in g if r['npl'] == 2)}.")
        if c != "grudge" and caps_d:
            P(f"[DATA] Mean progress of the captured piece in disagreements = {sum(caps_d) / len(caps_d):.1f} "
              f"(spot average over all boards {sum([v['cap'] for r in g for v in r['opt'].values() if v['cap'] is not None]) / max(1, len([1 for r in g for v in r['opt'].values() if v['cap'] is not None])):.1f}): low-value captures.")
    P("")
    P("Common feature of these four plus capture_vs_openexisting: the disagreements are concentrated on LOW-value captures (victim barely")
    P("advanced) and occur only with 3-4 players. The direction differs by alternative:")
    P("  - capture, capture_vs_openexisting: GT declines the low-value capture for a bring-out/advance and MCTS captures. [DERIVED] GT's")
    P("    1/n-centred evaluator explains this side (threshold shown for capture_vs_openexisting).")
    P("  - capture_vs_home, capture_vs_safe: GT captures and MCTS declines the low-value capture for the home/safe move. [HYPOTHESIS] MCTS sees")
    P("    little win-probability gain in sending back a piece that has hardly moved.")
    P(f"MCTS still agrees with GT on capture-first in most spots ({min(sum(r['agree'] for r in by[x]) / len(by[x]) for x in ('capture', 'capture_vs_home', 'capture_vs_safe')) * 100:.1f}-"
      f"{max(sum(r['agree'] for r in by[x]) / len(by[x]) for x in ('capture', 'capture_vs_home', 'capture_vs_safe')) * 100:.1f}%), the part of GT behaviour that the paper's")
    P("capture-vs-safe/home conclusions rely on.")

    # ------------------------------------------------------------------ 6
    title("6. PLAYER-COUNT EFFECT")
    P("[DATA] Agreement by players: " + ";  ".join(f"{k}p {sum(r['agree'] for r in rows if r['npl'] == k)}/{sum(1 for r in rows if r['npl'] == k)} "
      f"({100 * sum(r['agree'] for r in rows if r['npl'] == k) / sum(1 for r in rows if r['npl'] == k):.1f}%)" for k in (2, 3, 4)))
    P("")
    P(f"{'category':26s}{'2p':>9s}{'3p':>9s}{'4p':>9s}")
    for c in cats:
        P(f"{c:26s}" + "".join(f"{sum(r['agree'] for r in by[c] if r['npl'] == k):>5d}/{sum(1 for r in by[c] if r['npl'] == k):<3d}" for k in (2, 3, 4)))
    capcats = ["capture", "capture_vs_home", "capture_vs_openexisting", "capture_vs_safe", "grudge"]
    cd = [r for c in capcats for r in dis[c]]
    P("")
    P(f"[DATA] Capture-related categories ({', '.join(capcats)}): {len(cd)} disagreements, of which in 2-player games: "
      f"{sum(1 for r in cd if r['npl'] == 2)}. Agreement in 2p is perfect in all five.")
    P("[DERIVED] In 2p, GT's evaluator is exact zero-sum (own minus opponent); with 3-4p it is centred on the mean, which discounts captures")
    P("          (derived for capture_vs_openexisting). This is consistent with every capture-category disagreement being a 3-4p one.")
    P(f"[DATA] The decline with more players is not limited to capture categories: extra_turn goes "
      f"{sum(r['agree'] for r in by['extra_turn'] if r['npl'] == 2)}/14 -> {sum(r['agree'] for r in by['extra_turn'] if r['npl'] == 4)}/13 and safe_vs_openexisting "
      f"{sum(r['agree'] for r in by['safe_vs_openexisting'] if r['npl'] == 2)}/14 -> {sum(r['agree'] for r in by['safe_vs_openexisting'] if r['npl'] == 4)}/13 (2p -> 4p); its cause is not identified here.")
    P("[HYPOTHESIS] MCTS may also be noisier with more opponents (lower win rates, longer games); not testable from the stored artifacts.")
    P("[DATA] Categories are balanced across player counts by design (13-14 per cell), so the gap is not a mix effect.")

    # ------------------------------------------------------------------ 7
    title("7. HOW MUCH OF GT'S LABEL IS THE EVALUATOR ALONE?")
    sb = sum(1 for r in rows if r["static_best"] == r["g"])
    sm = sum(1 for r in rows if r["static_best"] == r["m"])
    P(f"[DERIVED] The 1-ply evaluator argmax (ties -> lowest index) equals GT's depth-2 move in {sb}/{N} entries ({100 * sb / N:.1f}%) and MCTS's move in {sm}/{N} ({100 * sm / N:.1f}%).")
    P(f"{'category':26s}{'argmax==GT':>12s}{'argmax==MCTS':>14s}")
    for c in cats:
        P(f"{c:26s}{sum(1 for r in by[c] if r['static_best'] == r['g']):>8d}/{len(by[c]):<3d}{sum(1 for r in by[c] if r['static_best'] == r['m']):>9d}/{len(by[c]):<3d}")
    P("Reading: GT's labels are almost entirely determined by its evaluator weights; the depth-2 lookahead rarely changes the 1-ply choice.")
    P("So most disagreements with an independent agent are disagreements with the weights (0.20 finish, 0.05 base, 0.01 safe, 1/n victim share).")

    # ------------------------------------------------------------------ 8
    title("8. KEY OBSERVATIONS")
    t3 = sum(len(dis[c]) for c in ("capture_vs_home_finish", "safe_vs_openexisting", "extra_turn"))
    t_ind = len(dis["blocked"]) + len(dis["overshoot"])
    t_cap = sum(len(dis[c]) for c in capcats)
    P(f"1. The 204 disagreements are five different phenomena, not one:")
    P(f"   (a) Opposite weight-driven preferences, agreement BELOW chance: capture_vs_home_finish, safe_vs_openexisting, extra_turn = {t3} ({100 * t3 / D:.1f}%).")
    nbo = sum(1 for r in dis["blocked"] if r["opt"][r["g"]]["kind"] == "bring_out")
    P(f"   (b) Near-indifferent choices where agreement is AT chance and GT's label is mostly its lowest-index tie-break: blocked, overshoot = {t_ind} ({100 * t_ind / D:.1f}%)")
    P(f"       (of the {len(dis['blocked'])} blocked ones, {nbo} are GT bring-out spots with the same cause as (a), so the purely indifferent share is {t_ind - nbo}).")
    P(f"   (c) A GT evaluator discontinuity plus depth instability: home_entry = {len(dis['home_entry'])} ({100 * len(dis['home_entry']) / D:.1f}%).")
    P(f"   (d) Low-value captures in 3-4 player games: capture, capture_vs_home, capture_vs_openexisting, capture_vs_safe, grudge = {t_cap} ({100 * t_cap / D:.1f}%);")
    P(f"       none occur in 2-player games. GT's centred multi-player evaluator explains the capture / capture_vs_openexisting direction [DERIVED];")
    P(f"       MCTS's reluctance to take trivial captures is the likely cause on capture_vs_home / capture_vs_safe [HYPOTHESIS].")
    P(f"   (e) Safe-square weight: safe = {len(dis['safe'])} ({100 * len(dis['safe']) / D:.1f}%).")
    P(f"   Check: {t3} + {t_ind} + {len(dis['home_entry'])} + {t_cap} + {len(dis['safe'])} = {t3 + t_ind + len(dis['home_entry']) + t_cap + len(dis['safe'])}.")
    P("2. MCTS corroborates GT where the paper's capture conclusions live: 87.5% capture, 82.5% capture_vs_home, 92.5% capture_vs_safe, 70%")
    P("   capture_vs_openexisting, 92.5% grudge, with 100% agreement in 2-player games.")
    P("3. MCTS does NOT corroborate GT's finish-over-capture or develop-over-advance preferences (12.5%, 22.5%, 30.0% agreement; chance 50%).")
    P("   These are the preferences behind the paper's finisher/builder story, and GT's versions of them are fixed by its evaluator weights.")
    P("4. The GT label in blocked, overshoot and home_entry (120 entries) is not a usable reference: indifferent, tie-break driven, or")
    P("   depth/off-by-one driven. MCTS agreement there equals chance (45.0%, 50.0%, 50.0%).")
    P("5. The agreement rise from chance (49%) to 61% overall is carried by the capture categories; elsewhere the two agents are at or below chance.")

    # ------------------------------------------------------------------ 9
    title("9. CATEGORIES MOST RESPONSIBLE FOR THE OVERALL DISAGREEMENT")
    cum = 0
    for i, c in enumerate(order[:6], 1):
        cum += len(dis[c])
        P(f"  {i}. {c:26s} {len(dis[c]):3d} disagreements  ({100 * len(dis[c]) / D:4.1f}% of total, cumulative {100 * cum / D:4.1f}%)")
    three = ("capture_vs_home_finish", "safe_vs_openexisting", "extra_turn")
    obs3 = sum(r["agree"] for c in three for r in by[c])
    exp3 = sum(1.0 / r["classes"] for c in three for r in by[c])
    P(f"The top six categories account for {cum} of {D} ({100 * cum / D:.1f}%). If the three 'systematic opposite' categories had agreed only at chance")
    P(f"({exp3:.0f} agreements instead of {obs3}), overall agreement would be {100 * (A - obs3 + exp3) / N:.1f}% instead of {100 * A / N:.1f}% (arithmetic bound, not a rerun).")

    # ------------------------------------------------------------------ 10
    title("10. IMPLICATIONS, LIMITS, AND FOLLOW-UPS (none of the follow-ups were run)")
    P("Implications for the paper")
    P("  - Do not present either GT or MCTS as ground truth. Report alignment against both and highlight the 316 entries where they agree")
    P("    as a consensus subset (strongest in the capture categories).")
    P("  - Soften Sec. 6.3-6.4: 'finishing is correct, capturing merely delays' and 'develop and finish' are properties of GT's weights;")
    P("    MCTS contradicts both.")
    P("  - Treat blocked, overshoot and home_entry as legality / indifference checks, not GT-alignment categories.")
    P("  - Report alignment by player count (2p versus 3-4p) because GT's multi-player labels differ in kind, not just in degree.")
    P("Limits of this analysis")
    P("  - MCTS is a single seed with 1000 random rollouts (win probability under random continuation), itself a noisy and imperfect reference.")
    P("  - n = 40 per category; p-values use the category's mean merged-piece chance rate, which is approximate for mixed spots.")
    P("  - The 1-ply evaluator is an offline re-implementation of GT's cutoff function, used as a diagnostic; it reproduces 94% of GT labels but is not GT.")
    P("  - Causes marked [HYPOTHESIS] are untested.")
    P("Cheap follow-ups that would settle the open points")
    P("  - Re-run MCTS on capture_vs_home_finish, safe_vs_openexisting and extra_turn only, saving last_search_info (visits, win rates) at")
    P("    1000 and 10000 rollouts: shows whether the MCTS preference is signal or noise.")
    P("  - Evaluator sensitivity sweep on GT (finish 0.20, base 0.05, safe 0.01) and a fix for the home-path off-by-one: shows how many labels move.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="gt_validation_results/results/mcts_vs_gt_results.csv")
    ap.add_argument("--spots-glob", default="spots_40/spots_*.json")
    ap.add_argument("--depth-csv", default="gt_validation_results/depth_stability/depth_stability_results.csv")
    ap.add_argument("--out", default="validation/results/mcts_disagreement_analysis.txt")
    args = ap.parse_args()
    rows = load(args)
    text = build(rows, args)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write(text)
    print(text)
    print(f"[written] {args.out}")


if __name__ == "__main__":
    main()

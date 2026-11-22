"""Spot validity audit: checks with the game engine that every benchmark spot is a legal board
and actually presents the decision its category is meant to test.

Answers Reviewer 4 (point 2: "demonstrate that the scenarios truly isolate the intended strategic
tradeoff"; Question 4: how the spots were constructed).

Three levels of checks per entry
  1. Board validity   - the position could occur in a real game under the engine's rules.
  2. Target present   - the moves the category is about are available (e.g. capture_vs_safe has a
                        capturing move and a move to a safe square). This is the pass/fail test.
  3. Isolation        - the target moves appear exactly once each and every other legal move is
                        neutral (no extra capture, safe square, home entry, finish or bring-out),
                        so no second incentive competes with the intended tradeoff. Reported
                        separately: a spot can contain its target and still carry an extra incentive.
Grudge pairs are additionally checked for identical boards across the two conditions, a named
aggressor who is in the game, and an available retaliatory capture against that aggressor.

Moves are counted as distinct moves: legal pieces standing on the same square (e.g. several pieces
in base) give the same move and are counted once.

Move types (destination of a legal move, engine rules):
  capture     lands on an opponent piece on a non-safe main-track square
  finish      lands exactly on the player's home end
  home        enters or moves within the home path without finishing
  bring_out   leaves base (lands on the start square)
  safe        lands on a safe main-track square (other than by bringing a piece out)
  neutral     anything else (a plain advance)

Usage (from the repository root):
  python analysis_scripts/spot_validity_audit.py
  python analysis_scripts/spot_validity_audit.py --spots-glob "spots_40/spots_*.json" --out-dir result_spot_validity_audit
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.getcwd())
from spot_evaluation import SpotEnv, compute_legal_moves  # noqa: E402

BOARD, HOME_START, HOME_LEN = 52, 52, 6
SAFE = {0, 8, 13, 21, 26, 34, 39, 47}
STARTS = {0: 0, 1: 13, 2: 26, 3: 39}

# What each category must contain (target move types) and what its note promises.
TARGETS = {
    "capture": ["capture"],
    "safe": ["safe"],
    "home_entry": ["home"],
    "extra_turn": ["bring_out", "existing"],
    "capture_vs_home": ["capture", "home"],
    "capture_vs_home_finish": ["capture", "finish"],
    "capture_vs_openexisting": ["capture", "bring_out"],
    "capture_vs_safe": ["capture", "safe"],
    "safe_vs_openexisting": ["safe", "bring_out"],
    "blocked": ["blocked_piece"],
    "overshoot": ["overshoot_piece"],
    "grudge": ["retaliation"],
}
SIX_REQUIRED = {"extra_turn", "capture_vs_openexisting", "safe_vs_openexisting"}
CATEGORY_ORDER = ["blocked", "overshoot", "capture", "safe", "home_entry", "extra_turn", "capture_vs_home",
                  "capture_vs_home_finish", "capture_vs_openexisting", "capture_vs_safe",
                  "safe_vs_openexisting", "grudge"]


def home_range(p):
    hs = HOME_START + p * HOME_LEN
    return hs, hs + HOME_LEN - 1


def destination(p, pos, dice):
    """Destination square of a piece, or None if the move overshoots home end."""
    hs, he = home_range(p)
    if pos == -1:
        return STARTS[p]
    if 0 <= pos < BOARD:
        rel = (pos - STARTS[p]) % BOARD + dice
        if rel < BOARD:
            return (STARTS[p] + rel) % BOARD
        step = rel - BOARD
        return hs + step - 1 if 1 <= step <= HOME_LEN else None
    new = pos + dice
    return new if new <= he else None


def move_type(p, tokens, pos, dice):
    hs, he = home_range(p)
    dest = destination(p, pos, dice)
    if pos == -1:
        return "bring_out", dest
    if dest is None:
        return "overshoot", dest
    if dest == he:
        return "finish", dest
    if dest >= hs:
        return "home", dest
    if dest not in SAFE and any(dest in tokens[o] for o in tokens if o != p):
        return "capture", dest
    if dest in SAFE:
        return "safe", dest
    return "neutral", dest


def board_problems(spot):
    probs = []
    players = spot["players"]
    tokens = {int(k): v for k, v in spot["tokens"].items()}
    p = spot["current_player"]
    if sorted(tokens) != sorted(players):
        probs.append("token keys do not match players")
    if p != spot.get("llm_player_id"):
        probs.append("current_player != llm_player_id")
    if p not in players:
        probs.append("current player not in game")
    if not 1 <= spot["dice"] <= 6:
        probs.append("dice outside 1-6")
    occupied = defaultdict(set)
    for q, ts in tokens.items():
        if len(ts) != 4:
            probs.append(f"player {q} does not have 4 pieces")
        hs, he = home_range(q)
        for t in ts:
            if not (t == -1 or 0 <= t < BOARD or hs <= t <= he):
                probs.append(f"player {q} piece at invalid index {t}")
        main = [t for t in ts if 0 <= t < BOARD and t not in SAFE]
        if len(main) != len(set(main)):
            probs.append(f"player {q} stacks pieces on a non-safe square")
        for t in set(ts):
            if 0 <= t < BOARD:
                occupied[t].add(q)
        if all(t == he for t in ts):
            probs.append(f"player {q} has already won")
    for sq, owners in occupied.items():
        if sq not in SAFE and len(owners) > 1:
            probs.append(f"two players share non-safe square {sq} (impossible: one would have been captured)")
    return probs


def audit_spot(spot):
    p, dice = spot["current_player"], spot["dice"]
    tokens = {int(k): v for k, v in spot["tokens"].items()}
    env = SpotEnv(spot["players"], {k: list(v) for k, v in tokens.items()})
    legal = compute_legal_moves(env, p, dice)
    mine = tokens[p]

    # distinct legal moves (same starting square = same move)
    distinct = {}
    for i in legal:
        distinct.setdefault(mine[i], i)
    types = Counter()
    for pos in distinct:
        types[move_type(p, tokens, pos, dice)[0]] += 1
    n_capture = types["capture"]

    # pieces that cannot move, and why
    blocked_pieces = overshoot_pieces = 0
    for i, pos in enumerate(mine):
        if i in legal or pos == -1:
            continue
        hs, he = home_range(p)
        if pos == he:
            continue
        dest = destination(p, pos, dice)
        if dest is None:
            overshoot_pieces += 1
        elif 0 <= dest < BOARD and dest in mine and dest not in SAFE:
            blocked_pieces += 1
        elif hs <= pos < he and dest != he:
            overshoot_pieces += 0  # in-home piece without exact roll: not part of any category

    cat = spot["scenario"]
    have = dict(types)
    have["existing"] = sum(v for k, v in types.items() if k != "bring_out")
    have["blocked_piece"] = blocked_pieces
    have["overshoot_piece"] = overshoot_pieces
    return {"legal": legal, "distinct_moves": len(distinct), "types": types, "have": have,
            "n_capture": n_capture, "tokens": tokens}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spots-glob", default="spots_40/spots_*.json")
    ap.add_argument("--out-dir", default="result_spot_validity_audit")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    spots = []
    for f in sorted(glob.glob(a.spots_glob)):
        spots += json.load(open(f))
    if not spots:
        raise SystemExit(f"No spots match {a.spots_glob}")

    rows = []
    for s in spots:
        cat = s["scenario"]
        r = audit_spot(s)
        probs = board_problems(s)
        if not r["legal"]:
            probs.append("no legal move")
        if cat in SIX_REQUIRED and s["dice"] != 6:
            probs.append("category requires a six")
        have = r["have"]
        targets = TARGETS.get(cat, [])
        missing = [t for t in targets if t != "retaliation" and have.get(t, 0) < 1]

        # isolation: each target exactly once; all other distinct moves neutral
        extra = []
        if cat not in ("blocked", "overshoot", "grudge"):
            allowed = set(t for t in targets if t != "existing")
            for t, c in r["types"].items():
                if t in allowed:
                    if c > 1:
                        extra.append(f"{c} distinct {t} moves")
                elif t != "neutral":
                    if cat == "extra_turn" and t in ("safe",):
                        extra.append("an existing piece can also reach a safe square")
                    else:
                        extra.append(f"extra {t} move")
        else:
            for t in ("capture", "finish", "home", "safe", "bring_out"):
                if r["types"].get(t) and not (cat == "grudge" and t == "capture"):
                    extra.append(f"{t} move available")
        rows.append({"id": s["id"], "category": cat, "n_players": len(s["players"]), "dice": s["dice"],
                     "legal_moves": "/".join(map(str, r["legal"])), "distinct_moves": r["distinct_moves"],
                     "move_types": ";".join(f"{k}:{v}" for k, v in sorted(r["types"].items())),
                     "board_valid": not probs, "board_problems": " | ".join(probs),
                     "target_present": not missing, "missing_targets": ",".join(missing),
                     "isolated": not extra, "extra_incentives": " | ".join(extra),
                     "_spot": s, "_r": r})

    # grudge pair checks
    pairs = defaultdict(dict)
    for row in rows:
        if row["category"] == "grudge":
            base, _, suf = row["id"].rpartition("_")
            pairs[base][suf] = row
    pair_rows = []
    for base, pr in sorted(pairs.items()):
        res = {"pair": base, "has_both": "a" in pr and "b" in pr}
        if res["has_both"]:
            sa, sb = pr["a"]["_spot"], pr["b"]["_spot"]
            res["same_board"] = (sa["tokens"] == sb["tokens"] and sa["dice"] == sb["dice"]
                                 and sa["players"] == sb["players"] and sa["current_player"] == sb["current_player"])
            ha, hb = sa.get("history_text", ""), sb.get("history_text", "")
            res["neutral_has_no_conflict"] = "captured" not in ha.lower()
            m = re.search(r"Player\s+(\d+)\s+captured", hb)
            target = int(m.group(1)) if m else None
            res["aggressor"] = target
            res["aggressor_in_game"] = target is not None and target in sa["players"] and target != sa["current_player"]
            tokens = pr["b"]["_r"]["tokens"]
            p, dice = sb["current_player"], sb["dice"]
            ret = False
            for i in pr["b"]["_r"]["legal"]:
                t, dest = move_type(p, tokens, tokens[p][i], dice)
                if t == "capture" and target is not None and dest in tokens.get(target, []):
                    ret = True
            res["retaliation_available"] = ret
            res["pair_valid"] = all([res["same_board"], res["neutral_has_no_conflict"],
                                     res["aggressor_in_game"], res["retaliation_available"]])
            for k in ("a", "b"):
                pr[k]["target_present"] = ret
                pr[k]["missing_targets"] = "" if ret else "retaliation"
                if not res["same_board"]:
                    pr[k]["board_problems"] = (pr[k]["board_problems"] + " | pair boards differ").strip(" |")
                    pr[k]["board_valid"] = False
        else:
            res["pair_valid"] = False
        pair_rows.append(res)

    # dataset-level checks
    def key(s):
        return (tuple(s["players"]), s["current_player"], s["dice"],
                tuple((k, tuple(v)) for k, v in sorted(s["tokens"].items())))
    board_keys = Counter()
    for row in rows:
        s = row["_spot"]
        if row["category"] == "grudge" and row["id"].endswith("_b"):
            continue
        board_keys[key(s)] += 1
    unique_boards = len(board_keys)
    dup_boards = sum(c - 1 for c in board_keys.values() if c > 1)
    ids = Counter(r["id"] for r in rows)
    dup_ids = [i for i, c in ids.items() if c > 1]
    pc = defaultdict(Counter)
    for row in rows:
        pc[row["category"]][row["n_players"]] += 1

    # write per-spot csv
    fields = [k for k in rows[0] if not k.startswith("_")]
    with open(os.path.join(a.out_dir, "spot_audit_per_entry.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in fields})
    with open(os.path.join(a.out_dir, "grudge_pair_audit.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(pair_rows[0]))
        w.writeheader()
        w.writerows(pair_rows)

    # summary
    summ = []
    for cat in CATEGORY_ORDER + sorted({r["category"] for r in rows} - set(CATEGORY_ORDER)):
        rs = [r for r in rows if r["category"] == cat]
        if not rs:
            continue
        summ.append({"category": cat, "entries": len(rs),
                     "board_valid": sum(r["board_valid"] for r in rs),
                     "target_present": sum(r["target_present"] for r in rs),
                     "isolated": sum(r["isolated"] for r in rs),
                     "players_2_3_4": f'{pc[cat][2]}/{pc[cat][3]}/{pc[cat][4]}'})
    tot = {"category": "ALL", "entries": len(rows), "board_valid": sum(r["board_valid"] for r in rows),
           "target_present": sum(r["target_present"] for r in rows), "isolated": sum(r["isolated"] for r in rows),
           "players_2_3_4": f'{sum(c[2] for c in pc.values())}/{sum(c[3] for c in pc.values())}/{sum(c[4] for c in pc.values())}'}
    summ.append(tot)
    with open(os.path.join(a.out_dir, "spot_audit_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0]))
        w.writeheader()
        w.writerows(summ)

    # report
    L = ["# Spot validity audit", "",
         f"Spot files: `{a.spots_glob}`. Entries audited: {len(rows)}. "
         f"Unique boards: {unique_boards} (grudge pairs counted once). Duplicate boards: {dup_boards}. "
         f"Duplicate ids: {len(dup_ids)}.", "",
         "Checks: **board valid** (a legal, reachable position under the engine's rules); **target present** "
         "(the moves the category is about are available; the pass/fail test); **isolated** (each target move "
         "appears once and all other legal moves are neutral, so no second incentive competes). "
         "Moves from the same square count as one move.", "",
         "| Category | Entries | Board valid | Target present | Isolated | Players 2/3/4 |", "|---|---|---|---|---|---|"]
    for s_ in summ:
        L.append(f'| {s_["category"]} | {s_["entries"]} | {s_["board_valid"]} | {s_["target_present"]} | '
                 f'{s_["isolated"]} | {s_["players_2_3_4"]} |')
    pv = sum(p_["pair_valid"] for p_ in pair_rows)
    L += ["", f"## Grudge pairs: {pv} of {len(pair_rows)} valid", "",
          "A valid pair has identical boards and dice in both conditions, a neutral history without a conflict, "
          "an aggressor named in the grudge history who is an opponent in the game, and a legal retaliatory capture "
          "against that aggressor.", ""]
    bad_pairs = [p_ for p_ in pair_rows if not p_["pair_valid"]]
    for p_ in bad_pairs:
        L.append(f"- {p_['pair']}: " + ", ".join(k for k, v in p_.items() if v is False))
    fails = [r for r in rows if not (r["board_valid"] and r["target_present"])]
    L += ["", f"## Entries failing board validity or target presence: {len(fails)}", ""]
    for r in fails:
        why = "; ".join(x for x in [r["board_problems"], ("missing: " + r["missing_targets"]) if r["missing_targets"] else ""] if x)
        L.append(f"- `{r['id']}` ({r['category']}): {why}")
    if not fails:
        L.append("None.")
    nonisol = [r for r in rows if r["board_valid"] and r["target_present"] and not r["isolated"]]
    L += ["", f"## Entries that contain their target but also an extra incentive: {len(nonisol)}", ""]
    cnt = Counter()
    for r in nonisol:
        for x in r["extra_incentives"].split(" | "):
            cnt[(r["category"], x)] += 1
    if cnt:
        L += ["| Category | Extra incentive | Entries |", "|---|---|---|"]
        for (c, x), v in sorted(cnt.items(), key=lambda z: (CATEGORY_ORDER.index(z[0][0]) if z[0][0] in CATEGORY_ORDER else 99, -z[1])):
            L.append(f"| {c} | {x} | {v} |")
    else:
        L.append("None.")
    L += ["", "Per-entry details: `spot_audit_per_entry.csv`; grudge pairs: `grudge_pair_audit.csv`."]
    open(os.path.join(a.out_dir, "report.md"), "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()

"""Task 3: confidence intervals and significance tests computed from the paper's reported numbers.

Addresses Reviewer 4 ("dataset size and statistical analysis are limited") and removes the paper's
limitation "rates are point estimates without confidence intervals".

No per-spot model outputs are needed. Every reported rate is a proportion k/n:
  n = number of valid answers in the category = 40 - (invalid rate x 40)      [Table 4]
  k = reported rate x n, rounded to the nearest whole number
Because k must be an integer, it can be recovered from a rate rounded to 2 decimals; the script
checks that k/n rounds back to the reported rate and flags any case where it does not.

Methods
  * 95% Wilson score interval for every single proportion.
  * Model-vs-model and persona-vs-none differences: Newcombe hybrid-score 95% interval for the
    difference and a two-sided Fisher exact test. Both treat the two rates as independent samples.
    The real samples share the same spots (paired), and for positively correlated paired data an
    unpaired test is conservative: a difference reported as significant here would also be
    significant with the paired test, but a few borderline differences may be missed.
  * Overall agreement with GT: Wilson interval and a two-sided binomial test against the chance
    level of a uniformly random legal move by piece index (0.4325, from the GT labels).

Approximations (stated in the outputs)
  * Grudge pairs: the paper does not report invalid rates for the grudge category, so n = 40 pairs
    is assumed (except Scout, where 36 valid pairs are known from the stored outputs).
  * Overall GT agreement: n = valid answers over the 11 non-grudge categories plus 80 grudge
    entries scaled by the model's mean invalid rate; the reported percentage is an integer.
  * Persona conditions: invalid rates under personas are not reported, so the no-persona valid
    counts are used for every persona.

Usage:  python analysis_scripts/paper_confidence_intervals.py --out-dir result_confidence_intervals
"""
import argparse
import csv
import math
import os

MODELS = ["QP", "Q7B", "DS", "Haiku", "Scout", "Gemma"]
Z = 1.959963984540054

# ---------------------------------------------------------------- numbers transcribed from the paper
INVALID = {  # Table 4 (no persona), fraction of 40 spots
    "blocked": [.03, .28, .03, .03, .13, .20], "capture_vs_home_finish": [0, .60, 0, 0, .08, .13],
    "capture_vs_home": [0, .68, 0, 0, .10, .13], "capture_vs_openexisting": [0, 0, 0, 0, .08, .03],
    "capture_vs_safe": [0, .55, 0, .05, .15, .20], "capture": [0, .50, 0, 0, .10, .15],
    "overshoot": [.43, .55, 0, 0, .08, .05], "safe": [0, .53, 0, 0, .08, .03],
    "safe_vs_openexisting": [0, 0, 0, 0, .03, .08], "extra_turn": [0, 0, 0, 0, 0, 0],
    "home_entry": [0, .65, 0, 0, .13, .08],
}
RATES = {  # (category, choice): rates on valid outputs, Tables 10-11 (no persona)
    ("capture_vs_safe", "capture"): [.42, .61, .10, .66, .29, .34],
    ("capture_vs_home", "capture"): [.57, .15, .72, .20, .78, .83],
    ("capture_vs_home_finish", "finish"): [.80, 1.00, .00, .88, .05, .00],
    ("capture_vs_openexisting", "capture"): [.62, .50, .23, .93, .27, .31],
    ("capture", "capture"): [.50, .55, .15, .53, .22, .29],
    ("safe", "safe"): [.28, .47, .12, .75, .05, .15],
    ("home_entry", "home entry"): [.42, .79, .17, .82, .14, .16],
    ("extra_turn", "bring-out"): [.30, .60, .88, .05, .70, .82],
}
GT_RATE = {  # GT reference values for the same quantities
    ("capture_vs_safe", "capture"): .98, ("capture_vs_home", "capture"): .98,
    ("capture_vs_home_finish", "finish"): 1.00, ("capture_vs_openexisting", "capture"): .68,
    ("capture", "capture"): .88, ("safe", "safe"): .88, ("home_entry", "home entry"): .13,
    ("extra_turn", "bring-out"): 1.00,
}
GRUDGE_CHANGE = [.33, .00, .20, .05, .06, .03]           # Table 12
GRUDGE_PAIRS = [40, 40, 40, 40, 36, 40]                   # see approximations above
GT_AGREEMENT = [.43, .46, .46, .45, .40, .46]             # summary table (integer %)
CHANCE_INDEX = 0.4325                                     # random legal move, by index (520 entries)
# Table 13: per persona (none, aggressive, greedy, safe, unforgiving); category -> metric -> model -> 5 values
PERSONA = {
    ("capture_vs_home_finish", "capture"): [[.20, .93, .12, .62, .57], [.00, .14, .06, .00, .16], [1, 1, 1, 1, 1],
                                            [.12, .05, .15, .03, .25], [.95, .97, 1, .92, 1], [1, 1, 1, .94, .95]],
    ("capture_vs_home_finish", "finish"): [[.80, .07, .88, .38, .42], [1, .86, .94, 1, .84], [0, 0, 0, 0, 0],
                                           [.88, .95, .85, .97, .75], [.05, .03, 0, .08, 0], [0, 0, 0, .06, .05]],
    ("capture_vs_safe", "capture"): [[.42, .15, .53, .40, .15], [.61, .71, .80, .63, .39], [.10, .20, .23, .15, .25],
                                     [.66, .84, .75, .88, .72], [.29, .19, .21, .09, .19], [.34, .14, .17, .11, .17]],
    ("capture_vs_safe", "safe"): [[.57, .85, .47, .60, .85], [.39, .29, .20, .37, .61], [.90, .80, .77, .85, .75],
                                  [.34, .16, .25, .12, .28], [.71, .81, .79, .91, .81], [.66, .86, .83, .89, .83]],
    ("capture", "capture"): [[.50, .28, .57, .38, .33], [.55, .67, .50, .68, .65], [.15, .17, .30, .07, .17],
                             [.53, .90, .78, .85, .74], [.22, .16, .29, .17, .19], [.29, .16, .24, .21, .16]],
    ("home_entry", "home entry"): [[.42, .33, .47, .33, .30], [.79, .69, .77, .80, .69], [.17, .15, .28, .23, .25],
                                   [.82, .97, .93, .97, .80], [.14, 0, .05, .10, .05], [.16, .05, .03, .05, .05]],
    ("extra_turn", "bring-out"): [[.30, .20, .28, .30, .28], [.60, .30, .42, .42, .38], [.88, .55, .90, .90, .72],
                                  [.05, .05, .03, .05, .05], [.70, .33, .47, .51, .57], [.82, .51, .58, .51, .64]],
}
PERSONAS = ["none", "aggressive", "greedy", "safe", "unforgiving"]
# Persona instructions and the direction each metric is expected to move (persona alignment definition)
EXPECTED = {
    "aggressive": {("capture", "capture"): +1, ("capture_vs_safe", "capture"): +1},
    "greedy": {("capture_vs_home_finish", "finish"): +1, ("capture_vs_home_finish", "capture"): -1,
               ("home_entry", "home entry"): +1},
    "safe": {("capture_vs_safe", "safe"): +1, ("capture", "capture"): -1},
}


# ---------------------------------------------------------------- statistics (no external libraries)
def wilson(k, n):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / d
    h = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def newcombe(k1, n1, k2, n2):
    """95% CI for p1 - p2 (Newcombe 1998, method 10)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


def fisher_two_sided(k1, n1, k2, n2):
    K, N = k1 + k2, n1 + n2

    def pmf(x):
        return math.comb(n1, x) * math.comb(n2, K - x) / math.comb(N, K)
    lo, hi = max(0, K - n2), min(K, n1)
    p_obs = pmf(k1)
    return min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= p_obs * (1 + 1e-9)))


def binom_two_sided(k, n, p):
    pmf = [math.comb(n, x) * p ** x * (1 - p) ** (n - x) for x in range(n + 1)]
    return min(1.0, sum(q for q in pmf if q <= pmf[k] * (1 + 1e-9)))


def recover_k(rate, n):
    k = round(rate * n)
    # exact half-way values (e.g. 17/40 = 0.425) may be printed as either 0.42 or 0.43
    ok = n > 0 and abs(k / n - rate) <= 0.005 + 1e-9
    return k, ok


def fmt(x):
    return f"{x:.2f}"


def fp(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="result_confidence_intervals")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    valid = {cat: [40 - round(r * 40) for r in rs] for cat, rs in INVALID.items()}
    flags = []

    # 1. invalid rates
    inv_rows = []
    for cat, rs in INVALID.items():
        for j, m in enumerate(MODELS):
            k = round(rs[j] * 40)
            lo, hi = wilson(k, 40)
            inv_rows.append({"category": cat, "model": m, "k_invalid": k, "n": 40, "rate": k / 40, "ci_low": lo, "ci_high": hi})
    mean_rows = []
    for j, m in enumerate(MODELS):
        k = sum(round(INVALID[c][j] * 40) for c in INVALID)
        n = 40 * len(INVALID)
        lo, hi = wilson(k, n)
        mean_rows.append({"model": m, "k_invalid": k, "n": n, "rate": k / n, "ci_low": lo, "ci_high": hi})

    # 2. behaviour rates
    beh_rows = []
    for (cat, choice), rs in RATES.items():
        for j, m in enumerate(MODELS):
            n = valid[cat][j]
            k, ok = recover_k(rs[j], n)
            if not ok:
                flags.append(f"{m} {cat} {choice}: reported {rs[j]} not exactly k/{n}; used k={k}")
            lo, hi = wilson(k, n)
            gt = GT_RATE[(cat, choice)]
            beh_rows.append({"category": cat, "choice": choice, "model": m, "k": k, "n_valid": n,
                             "rate": k / n, "ci_low": lo, "ci_high": hi, "gt_rate": gt,
                             "gt_outside_ci": not (lo <= gt <= hi)})

    # 3. grudge change rates
    gr_rows = []
    for j, m in enumerate(MODELS):
        n = GRUDGE_PAIRS[j]
        k, ok = recover_k(GRUDGE_CHANGE[j], n)
        lo, hi = wilson(k, n)
        gr_rows.append({"model": m, "k_changed": k, "n_pairs": n, "n_assumed": m != "Scout",
                        "rate": k / n, "ci_low": lo, "ci_high": hi})

    # 4. overall GT agreement vs chance
    ag_rows = []
    for j, m in enumerate(MODELS):
        nv = sum(valid[c][j] for c in INVALID)
        mean_inv = 1 - nv / (40 * len(INVALID))
        n = nv + round(80 * (1 - mean_inv))
        k = round(GT_AGREEMENT[j] * n)
        lo, hi = wilson(k, n)
        ag_rows.append({"model": m, "n_valid_approx": n, "agreement": GT_AGREEMENT[j], "ci_low": lo, "ci_high": hi,
                        "chance_index": CHANCE_INDEX, "p_vs_chance": binom_two_sided(k, n, CHANCE_INDEX),
                        "chance_inside_ci": lo <= CHANCE_INDEX <= hi})

    # 5. key comparisons behind the paper's claims
    def b(cat, choice, m):
        r = next(x for x in beh_rows if x["category"] == cat and x["choice"] == choice and x["model"] == m)
        return r["k"], r["n_valid"]

    def g(m):
        r = next(x for x in gr_rows if x["model"] == m)
        return r["k_changed"], r["n_pairs"]

    def inv(m):
        r = next(x for x in mean_rows if x["model"] == m)
        return r["k_invalid"], r["n"]
    comps = [
        ("Compliance: Gemma vs Qwen-Plus mean invalid rate", inv("Gemma"), inv("QP")),
        ("Compliance: Qwen-2.5-7B vs Scout mean invalid rate", inv("Q7B"), inv("Scout")),
        ("Archetype: Haiku vs DeepSeek finish rate (capture_vs_home_finish)",
         b("capture_vs_home_finish", "finish", "Haiku"), b("capture_vs_home_finish", "finish", "DS")),
        ("Archetype: DeepSeek vs Haiku bring-out rate (extra_turn)",
         b("extra_turn", "bring-out", "DS"), b("extra_turn", "bring-out", "Haiku")),
        ("Archetype: Gemma vs Haiku capture rate (capture_vs_home)",
         b("capture_vs_home", "capture", "Gemma"), b("capture_vs_home", "capture", "Haiku")),
        ("Archetype: Gemma vs Qwen-2.5-7B capture rate (capture_vs_home)",
         b("capture_vs_home", "capture", "Gemma"), b("capture_vs_home", "capture", "Q7B")),
        ("Risk: Haiku vs DeepSeek capture rate (capture_vs_safe)",
         b("capture_vs_safe", "capture", "Haiku"), b("capture_vs_safe", "capture", "DS")),
        ("Grudge: Qwen-Plus vs Haiku change rate", g("QP"), g("Haiku")),
        ("Grudge: DeepSeek vs Haiku change rate", g("DS"), g("Haiku")),
        ("Grudge: Qwen-Plus vs DeepSeek change rate", g("QP"), g("DS")),
        ("Grudge: DeepSeek vs Qwen-2.5-7B change rate", g("DS"), g("Q7B")),
    ]
    cmp_rows = []
    for name, (k1, n1), (k2, n2) in comps:
        lo, hi = newcombe(k1, n1, k2, n2)
        cmp_rows.append({"comparison": name, "rate_1": k1 / n1, "n_1": n1, "rate_2": k2 / n2, "n_2": n2,
                         "difference": k1 / n1 - k2 / n2, "diff_ci_low": lo, "diff_ci_high": hi,
                         "p_fisher": fisher_two_sided(k1, n1, k2, n2)})

    # 6. persona shifts vs no persona (all cells of Table 13)
    per_rows = []
    for (cat, metric), per_model in PERSONA.items():
        for j, m in enumerate(MODELS):
            n = valid[cat][j]
            k0, _ = recover_k(per_model[j][0], n)
            for pi in range(1, 5):
                persona = PERSONAS[pi]
                k1, _ = recover_k(per_model[j][pi], n)
                lo, hi = newcombe(k1, n, k0, n)
                exp = EXPECTED.get(persona, {}).get((cat, metric))
                per_rows.append({"category": cat, "metric": metric, "model": m, "persona": persona,
                                 "rate_none": k0 / n, "rate_persona": k1 / n, "n_assumed": n,
                                 "shift": (k1 - k0) / n, "shift_ci_low": lo, "shift_ci_high": hi,
                                 "p_fisher": fisher_two_sided(k1, n, k0, n),
                                 "expected_direction": "" if exp is None else ("+" if exp > 0 else "-")})

    # ---------------------------------------------------------------- write files
    def write(name, rows):
        with open(os.path.join(a.out_dir, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            for r in rows:
                w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    write("ci_invalid_by_category.csv", inv_rows)
    write("ci_invalid_mean.csv", mean_rows)
    write("ci_behaviour_rates.csv", beh_rows)
    write("ci_grudge_change.csv", gr_rows)
    write("ci_gt_agreement.csv", ag_rows)
    write("comparisons.csv", cmp_rows)
    write("persona_shifts.csv", per_rows)

    # ---------------------------------------------------------------- report
    L = ["# Task 3: Confidence intervals from the paper's reported numbers", "",
         "95% Wilson intervals; differences use Newcombe intervals and two-sided Fisher exact tests "
         "(unpaired, hence conservative). Method and approximations: see the script header.", ""]
    L += ["## Mean invalid rate (11 non-grudge categories, 440 spots)", "",
          "| Model | Invalid | 95% CI |", "|---|---|---|"]
    for r in mean_rows:
        L.append(f'| {r["model"]} | {r["rate"]:.3f} ({r["k_invalid"]}/{r["n"]}) | {fmt(r["ci_low"])}–{fmt(r["ci_high"])} |')
    L += ["", "## Behaviour rates (valid outputs)", "",
          "| Category: choice | " + " | ".join(MODELS) + " | GT |", "|---|" + "---|" * (len(MODELS) + 1)]
    for (cat, choice) in RATES:
        cells = []
        for m in MODELS:
            r = next(x for x in beh_rows if x["category"] == cat and x["choice"] == choice and x["model"] == m)
            cells.append(f'{r["rate"]:.2f} [{fmt(r["ci_low"])}, {fmt(r["ci_high"])}] (n={r["n_valid"]})')
        L.append(f"| {cat}: {choice} | " + " | ".join(cells) + f" | {GT_RATE[(cat, choice)]:.2f} |")
    L += ["", "## Grudge change rate", "", "| Model | Change rate | 95% CI | Pairs |", "|---|---|---|---|"]
    for r in gr_rows:
        L.append(f'| {r["model"]} | {r["rate"]:.2f} | {fmt(r["ci_low"])}–{fmt(r["ci_high"])} | '
                 f'{r["n_pairs"]}{" (assumed)" if r["n_assumed"] else ""} |')
    L += ["", f"## Overall agreement with GT vs chance ({CHANCE_INDEX:.3f}, random legal move by index)", "",
          "| Model | Agreement | 95% CI | p vs chance | Chance inside CI? |", "|---|---|---|---|---|"]
    for r in ag_rows:
        L.append(f'| {r["model"]} | {r["agreement"]:.2f} | {fmt(r["ci_low"])}–{fmt(r["ci_high"])} | '
                 f'{fp(r["p_vs_chance"])} | {"yes" if r["chance_inside_ci"] else "no"} |')
    L += ["", "## Key comparisons", "", "| Comparison | Rates | Difference [95% CI] | p (Fisher) |", "|---|---|---|---|"]
    for r in cmp_rows:
        L.append(f'| {r["comparison"]} | {r["rate_1"]:.2f} vs {r["rate_2"]:.2f} | {r["difference"]:+.2f} '
                 f'[{r["diff_ci_low"]:+.2f}, {r["diff_ci_high"]:+.2f}] | {fp(r["p_fisher"])} |')
    sig = [r for r in per_rows if r["p_fisher"] < 0.05]
    directed = [r for r in per_rows if r["expected_direction"]]
    d_with = [r for r in directed if r["p_fisher"] < 0.05 and (r["shift"] > 0) == (r["expected_direction"] == "+")]
    d_against = [r for r in directed if r["p_fisher"] < 0.05 and (r["shift"] > 0) != (r["expected_direction"] == "+")]
    hk = next(r for r in per_rows if r["model"] == "Haiku" and r["persona"] == "safe"
              and r["category"] == "capture_vs_safe" and r["metric"] == "capture")
    hc = next(r for r in per_rows if r["model"] == "Haiku" and r["persona"] == "safe"
              and r["category"] == "capture" and r["metric"] == "capture")
    L += ["", "## Persona shifts (Table 13, all persona-vs-none cells)", "",
          f"{len(sig)} of {len(per_rows)} persona-vs-none shifts are significant at p < 0.05 "
          "(Fisher, unpaired; n assumed equal to the no-persona valid count).", "",
          f"Of the {len(directed)} shifts whose instruction implies a direction, {len(d_with)} move significantly in the "
          f"intended direction, {len(d_against)} move significantly in the OPPOSITE direction, and "
          f"{len(directed) - len(d_with) - len(d_against)} show no significant change.", "",
          f"Paper's example (Haiku, safe persona, capture_vs_safe capture {hk['rate_none']:.2f} -> {hk['rate_persona']:.2f}): "
          f"p = {fp(hk['p_fisher'])}. Same persona in the capture category ({hc['rate_none']:.2f} -> {hc['rate_persona']:.2f}): "
          f"p = {fp(hc['p_fisher'])}.", "",
          "| Model | Persona | Category: metric | none -> persona | Shift [95% CI] | p | Expected direction |",
          "|---|---|---|---|---|---|---|"]
    for r in sorted(sig, key=lambda x: x["p_fisher"]):
        L.append(f'| {r["model"]} | {r["persona"]} | {r["category"]}: {r["metric"]} | {r["rate_none"]:.2f} -> '
                 f'{r["rate_persona"]:.2f} | {r["shift"]:+.2f} [{r["shift_ci_low"]:+.2f}, {r["shift_ci_high"]:+.2f}] | '
                 f'{fp(r["p_fisher"])} | {r["expected_direction"] or "n/a"} |')
    if flags:
        L += ["", "## Reconstruction flags", ""] + [f"- {x}" for x in flags]
    else:
        L += ["", "All reported rates were reconstructed exactly as whole-number counts (no flags)."]
    open(os.path.join(a.out_dir, "report.md"), "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()

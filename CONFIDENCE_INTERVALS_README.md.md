# Task 3: Confidence intervals from the paper's reported numbers

Addresses **Reviewer 4, point 4** ("dataset size and statistical analysis are limited") and removes the paper's own limitation that "rates are point estimates without confidence intervals".

## Where the files go

Copy into the repository root, keeping the folders:

```
analysis_scripts/paper_confidence_intervals.py   <- the script (no inputs needed; paper numbers are inside it)
results/task3_confidence_intervals/              <- all outputs
TASK3_README.md                                  <- this file
```

Run it again at any time with:

```
python analysis_scripts/paper_confidence_intervals.py --out-dir results/task3_confidence_intervals
```

It uses only the Python standard library: no API calls, no extra packages, and it runs in about a second.

## How it works (simple version)

Every rate in the paper is "k out of n". For example, Haiku finishes in 88% of 40 spots, so k = 35 and n = 40. The number of valid answers n comes from the invalid rates in Table 4. Because k must be a whole number, it can be recovered from the rounded percentage. **All rates were recovered exactly; no case was ambiguous.**

| Purpose | Method |
|---|---|
| Single rates | 95% Wilson interval |
| Differences between models, or persona vs no persona | Newcombe 95% interval and Fisher exact test |
| Overall GT agreement vs chance | Binomial test against 0.4325 (a random legal move, by piece index) |

The difference tests treat the two rates as independent samples. They really come from the same spots, so these tests are **conservative**: anything marked significant would also be significant with an exact paired test.

The implementations were checked against `scipy`; Wilson intervals, Fisher tests and binomial tests match to 4 decimals.

**Approximations** (stated in the outputs):
- Grudge pairs: n = 40 assumed, except Scout (36, known from its stored files).
- Overall agreement: valid n estimated from the invalid rates.
- Personas: the no-persona valid counts are used, since persona invalid rates aren't reported.

## Output files (`results/task3_confidence_intervals/`)

| File | Contents |
|---|---|
| `report.md` | Everything below, readable. |
| `ci_invalid_by_category.csv`, `ci_invalid_mean.csv` | Intervals for Table 4. |
| `ci_behaviour_rates.csv` | Intervals for the tradeoff and pure-preference rates, and whether GT's value lies outside the interval. |
| `ci_grudge_change.csv` | Intervals for the change rates. |
| `ci_gt_agreement.csv` | Agreement intervals and the test against chance. |
| `comparisons.csv` | The model-vs-model comparisons behind the paper's claims. |
| `persona_shifts.csv` | All 168 persona-vs-none shifts from Table 13. |

## Findings: which claims hold up statistically

### Claims that are confirmed (keep them, now with intervals and p-values)

1. **The finisher/builder archetypes are real.**
   - Haiku finishes 88% vs DeepSeek 0% (difference +0.88, 95% CI [0.71, 0.95], p < 0.001).
   - DeepSeek brings out 88% vs Haiku 5% (+0.82, CI [0.65, 0.90], p < 0.001).
   - In capture-vs-home, Gemma captures 83% vs Haiku 20% (p < 0.001) and vs Qwen-2.5-7B 15% (p < 0.001).
2. **All six models are more risk-averse than GT in capture-vs-safe.** GT's 98% lies outside every model's interval; the highest upper bound is Qwen-2.5-7B's 0.80.
3. **Compliance does not follow model size.** Gemma-3-12B is invalid more often than Qwen-Plus (9.5% vs 4.1%, p = 0.002).
4. **Aggregate agreement with GT is not distinguishable from chance.** For all six models, the 43.3% chance level lies inside the 95% interval (all p > 0.15).
5. **Qwen-Plus is the most narrative-sensitive model.** Its change rate is 33% vs Haiku's 5% (p = 0.003).

### Claims that need softer wording

6. **DeepSeek's 20% change rate is not clearly higher than Haiku's 5%** (p = 0.087), although it is higher than Qwen-2.5-7B's 0% (p = 0.005). Qwen-Plus (33%) and DeepSeek (20%) are not significantly different (p = 0.31). Suggested wording: "Qwen-Plus changes significantly more often than the other models; DeepSeek-Chat (20%) is intermediate."

7. **Persona instructions: the paper's conclusion becomes stronger, but its example becomes weaker.**
   - Of the 42 persona effects whose instruction implies a direction, only **1** moves significantly in the intended direction (Haiku, aggressive persona, raw capture rate 53% → 90%). **2** move significantly in the **opposite** direction, and **39** show no significant change. This is strong statistical support for "persona instructions are not a reliable steering mechanism".
   - The paper's flagship example (Haiku's safe persona raising its capture-vs-safe capture rate from 66% to 88%) is **borderline**: p = 0.03–0.06, depending on the unreported number of valid persona answers.
   - A cleaner example with the same model and persona: in the `capture` category, the safe persona raises Haiku's capture rate from 53% to 85% (p = 0.003), the opposite of "play safely". The second significant backfire is Qwen-Plus: its aggressive persona *lowers* its capture-vs-safe capture rate from 42% to 15% (p = 0.013).

### A caveat to add

8. **Qwen-2.5-7B's rates rest on few valid answers.** Its high invalid rate leaves only 13–20 valid answers in several categories (13 in capture-vs-home, 16 in capture-vs-home-finish), so its intervals are wide. For example, its capture rate in capture-vs-home is 15% with CI [4%, 42%]. Its finisher classification still holds (finish rate CI [0.81, 1.00]), but the paper should mention the small n.

## What to change in the paper later (LaTeX)

- Add 95% intervals to the tradeoff table, the grudge table and the summary table (values in `ci_behaviour_rates.csv`, `ci_grudge_change.csv` and `ci_gt_agreement.csv`).
- Add one sentence to Methodology describing the intervals and tests.
- Rephrase the grudge result (point 6) and replace or qualify the persona example (point 7).
- Add the Qwen-2.5-7B small-n caveat (point 8).
- Delete the "Sample size and statistics" limitation bullet, keeping a short note that n = 40 per category limits the detection of small differences.

When the six models' per-spot outputs are available (re-run or previous author), these intervals can be recomputed exactly, including exact paired tests, without changing any conclusion above that is marked confirmed.

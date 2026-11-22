# Task 3: Confidence intervals from the paper's reported numbers

95% Wilson intervals; differences use Newcombe intervals and two-sided Fisher exact tests (unpaired, hence conservative). Method and approximations: see the script header.

## Mean invalid rate (11 non-grudge categories, 440 spots)

| Model | Invalid | 95% CI |
|---|---|---|
| QP | 0.041 (18/440) | 0.03–0.06 |
| Q7B | 0.393 (173/440) | 0.35–0.44 |
| DS | 0.002 (1/440) | 0.00–0.01 |
| Haiku | 0.007 (3/440) | 0.00–0.02 |
| Scout | 0.084 (37/440) | 0.06–0.11 |
| Gemma | 0.095 (42/440) | 0.07–0.13 |

## Behaviour rates (valid outputs)

| Category: choice | QP | Q7B | DS | Haiku | Scout | Gemma | GT |
|---|---|---|---|---|---|---|---|
| capture_vs_safe: capture | 0.42 [0.29, 0.58] (n=40) | 0.61 [0.39, 0.80] (n=18) | 0.10 [0.04, 0.23] (n=40) | 0.66 [0.50, 0.79] (n=38) | 0.29 [0.17, 0.46] (n=34) | 0.34 [0.20, 0.52] (n=32) | 0.98 |
| capture_vs_home: capture | 0.57 [0.42, 0.71] (n=40) | 0.15 [0.04, 0.42] (n=13) | 0.72 [0.57, 0.84] (n=40) | 0.20 [0.10, 0.35] (n=40) | 0.78 [0.62, 0.88] (n=36) | 0.83 [0.67, 0.92] (n=35) | 0.98 |
| capture_vs_home_finish: finish | 0.80 [0.65, 0.90] (n=40) | 1.00 [0.81, 1.00] (n=16) | 0.00 [0.00, 0.09] (n=40) | 0.88 [0.74, 0.95] (n=40) | 0.05 [0.01, 0.18] (n=37) | 0.00 [0.00, 0.10] (n=35) | 1.00 |
| capture_vs_openexisting: capture | 0.62 [0.47, 0.76] (n=40) | 0.50 [0.35, 0.65] (n=40) | 0.23 [0.12, 0.38] (n=40) | 0.93 [0.80, 0.97] (n=40) | 0.27 [0.15, 0.43] (n=37) | 0.31 [0.19, 0.46] (n=39) | 0.68 |
| capture: capture | 0.50 [0.35, 0.65] (n=40) | 0.55 [0.34, 0.74] (n=20) | 0.15 [0.07, 0.29] (n=40) | 0.53 [0.37, 0.67] (n=40) | 0.22 [0.12, 0.38] (n=36) | 0.29 [0.17, 0.46] (n=34) | 0.88 |
| safe: safe | 0.28 [0.16, 0.43] (n=40) | 0.47 [0.27, 0.68] (n=19) | 0.12 [0.05, 0.26] (n=40) | 0.75 [0.60, 0.86] (n=40) | 0.05 [0.01, 0.18] (n=37) | 0.15 [0.07, 0.30] (n=39) | 0.88 |
| home_entry: home entry | 0.42 [0.29, 0.58] (n=40) | 0.79 [0.52, 0.92] (n=14) | 0.17 [0.09, 0.32] (n=40) | 0.82 [0.68, 0.91] (n=40) | 0.14 [0.06, 0.29] (n=35) | 0.16 [0.08, 0.31] (n=37) | 0.13 |
| extra_turn: bring-out | 0.30 [0.18, 0.45] (n=40) | 0.60 [0.45, 0.74] (n=40) | 0.88 [0.74, 0.95] (n=40) | 0.05 [0.01, 0.17] (n=40) | 0.70 [0.55, 0.82] (n=40) | 0.82 [0.68, 0.91] (n=40) | 1.00 |

## Grudge change rate

| Model | Change rate | 95% CI | Pairs |
|---|---|---|---|
| QP | 0.33 | 0.20–0.48 | 40 (assumed) |
| Q7B | 0.00 | 0.00–0.09 | 40 (assumed) |
| DS | 0.20 | 0.10–0.35 | 40 (assumed) |
| Haiku | 0.05 | 0.01–0.17 | 40 (assumed) |
| Scout | 0.06 | 0.02–0.18 | 36 |
| Gemma | 0.03 | 0.00–0.13 | 40 (assumed) |

## Overall agreement with GT vs chance (0.432, random legal move by index)

| Model | Agreement | 95% CI | p vs chance | Chance inside CI? |
|---|---|---|---|---|
| QP | 0.43 | 0.39–0.47 | 0.964 | yes |
| Q7B | 0.46 | 0.40–0.51 | 0.364 | yes |
| DS | 0.46 | 0.42–0.50 | 0.199 | yes |
| Haiku | 0.45 | 0.41–0.49 | 0.450 | yes |
| Scout | 0.40 | 0.36–0.44 | 0.152 | yes |
| Gemma | 0.46 | 0.42–0.50 | 0.245 | yes |

## Key comparisons

| Comparison | Rates | Difference [95% CI] | p (Fisher) |
|---|---|---|---|
| Compliance: Gemma vs Qwen-Plus mean invalid rate | 0.10 vs 0.04 | +0.05 [+0.02, +0.09] | 0.002 |
| Compliance: Qwen-2.5-7B vs Scout mean invalid rate | 0.39 vs 0.08 | +0.31 [+0.26, +0.36] | <0.001 |
| Archetype: Haiku vs DeepSeek finish rate (capture_vs_home_finish) | 0.88 vs 0.00 | +0.88 [+0.71, +0.95] | <0.001 |
| Archetype: DeepSeek vs Haiku bring-out rate (extra_turn) | 0.88 vs 0.05 | +0.82 [+0.65, +0.90] | <0.001 |
| Archetype: Gemma vs Haiku capture rate (capture_vs_home) | 0.83 vs 0.20 | +0.63 [+0.41, +0.76] | <0.001 |
| Archetype: Gemma vs Qwen-2.5-7B capture rate (capture_vs_home) | 0.83 vs 0.15 | +0.67 [+0.36, +0.82] | <0.001 |
| Risk: Haiku vs DeepSeek capture rate (capture_vs_safe) | 0.66 vs 0.10 | +0.56 [+0.35, +0.70] | <0.001 |
| Grudge: Qwen-Plus vs Haiku change rate | 0.33 vs 0.05 | +0.28 [+0.11, +0.43] | 0.003 |
| Grudge: DeepSeek vs Haiku change rate | 0.20 vs 0.05 | +0.15 [+0.00, +0.30] | 0.087 |
| Grudge: Qwen-Plus vs DeepSeek change rate | 0.33 vs 0.20 | +0.12 [-0.07, +0.31] | 0.310 |
| Grudge: DeepSeek vs Qwen-2.5-7B change rate | 0.20 vs 0.00 | +0.20 [+0.07, +0.35] | 0.005 |

## Persona shifts (Table 13, all persona-vs-none cells)

19 of 168 persona-vs-none shifts are significant at p < 0.05 (Fisher, unpaired; n assumed equal to the no-persona valid count).

Of the 42 shifts whose instruction implies a direction, 1 move significantly in the intended direction, 2 move significantly in the OPPOSITE direction, and 39 show no significant change.

Paper's example (Haiku, safe persona, capture_vs_safe capture 0.66 -> 0.87): p = 0.057. Same persona in the capture category (0.53 -> 0.85): p = 0.003.

| Model | Persona | Category: metric | none -> persona | Shift [95% CI] | p | Expected direction |
|---|---|---|---|---|---|---|
| QP | aggressive | capture_vs_home_finish: capture | 0.20 -> 0.93 | +0.72 [+0.53, +0.83] | <0.001 | n/a |
| QP | aggressive | capture_vs_home_finish: finish | 0.80 -> 0.07 | -0.72 [-0.83, -0.53] | <0.001 | n/a |
| QP | safe | capture_vs_home_finish: capture | 0.20 -> 0.62 | +0.42 [+0.21, +0.59] | <0.001 | n/a |
| QP | safe | capture_vs_home_finish: finish | 0.80 -> 0.38 | -0.42 [-0.59, -0.21] | <0.001 | n/a |
| Haiku | aggressive | capture: capture | 0.53 -> 0.90 | +0.38 [+0.18, +0.54] | <0.001 | + |
| QP | unforgiving | capture_vs_home_finish: capture | 0.20 -> 0.57 | +0.38 [+0.16, +0.54] | 0.001 | n/a |
| QP | unforgiving | capture_vs_home_finish: finish | 0.80 -> 0.42 | -0.38 [-0.54, -0.16] | 0.001 | n/a |
| Scout | aggressive | extra_turn: bring-out | 0.70 -> 0.33 | -0.38 [-0.55, -0.16] | 0.002 | n/a |
| DS | aggressive | extra_turn: bring-out | 0.88 -> 0.55 | -0.33 [-0.49, -0.13] | 0.003 | n/a |
| Haiku | safe | capture: capture | 0.53 -> 0.85 | +0.33 [+0.12, +0.49] | 0.003 | - |
| Gemma | aggressive | extra_turn: bring-out | 0.82 -> 0.50 | -0.33 [-0.50, -0.12] | 0.004 | n/a |
| Gemma | safe | extra_turn: bring-out | 0.82 -> 0.50 | -0.33 [-0.50, -0.12] | 0.004 | n/a |
| QP | aggressive | capture_vs_safe: capture | 0.42 -> 0.15 | -0.28 [-0.45, -0.08] | 0.013 | + |
| QP | unforgiving | capture_vs_safe: capture | 0.42 -> 0.15 | -0.28 [-0.45, -0.08] | 0.013 | n/a |
| QP | aggressive | capture_vs_safe: safe | 0.57 -> 0.85 | +0.28 [+0.08, +0.45] | 0.013 | n/a |
| QP | unforgiving | capture_vs_safe: safe | 0.57 -> 0.85 | +0.28 [+0.08, +0.45] | 0.013 | n/a |
| Q7B | aggressive | extra_turn: bring-out | 0.60 -> 0.30 | -0.30 [-0.48, -0.08] | 0.013 | n/a |
| Gemma | greedy | extra_turn: bring-out | 0.82 -> 0.57 | -0.25 [-0.43, -0.05] | 0.027 | n/a |
| Haiku | greedy | capture: capture | 0.53 -> 0.78 | +0.25 [+0.04, +0.43] | 0.034 | n/a |

All reported rates were reconstructed exactly as whole-number counts (no flags).
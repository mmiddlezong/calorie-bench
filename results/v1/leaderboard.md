# CalorieBench leaderboard (prompt v1)

_Generated 2026-09-25 19:19 UTC. Ranked by mean absolute calorie error (lower is better). 95% CIs from 10,000 dish-level bootstrap resamples._

| # | Model | Calorie MAE, kcal (95% CI) | MAE % | Within ±20% | Median APE | MAPE | Bias (kcal) | r | Fail | Cost | n |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **Claude Fable 5.1** | 82 (70–96) | 30% | 40% | 27% | 32% | -38 | 0.81 | 0% | $3.71 | 200/200 |
| 2 | **Claude Opus 5.5** | 91 (79–105) | 33% | 34% | 29% | 44% | +23 | 0.78 | 0% | $1.76 | 200/200 |
| 3 | **Claude Sonnet 5** | 101 (88–114) | 36% | 36% | 31% | 47% | +20 | 0.76 | 0% | $0.77 | 200/200 |
| 4 | **GPT-6 Luna** | 112 (98–127) | 40% | 27% | 35% | 52% | +51 | 0.78 | 0% | $0.10 | 200/200 |
| 5 | **GPT-6 Sol** | 127 (112–142) | 46% | 26% | 41% | 63% | +83 | 0.79 | 0% | $1.91 | 200/200 |
| 6 | **Claude Haiku 4.5** | 139 (123–156) | 50% | 27% | 43% | 79% | +62 | 0.65 | 0% | $1.99 | 200/200 |
| 7 | **GPT-6 Astra** | 145 (129–162) | 52% | 22% | 53% | 72% | +118 | 0.82 | 0% | $11.66 | 200/200 |

**Columns.** *MAE*: mean absolute error of total calories vs. the ground truth (computed from weighed ingredients). *MAE %*: MAE as a share of the mean true calories (Nutrition5k paper metric). *Within ±20%*: share of dishes estimated within 20% of the true value (the FDA's tolerance for nutrition labels). *Median APE* / *MAPE*: median / mean absolute percentage error. *Bias*: mean signed error (negative = underestimates). *r*: Pearson correlation of predicted vs. true calories. *Fail*: unparseable answers, refusals, and truncations (scored as predicting 0). *Cost*: API spend to run every dish once, at list prices. ⚠ = incomplete run.

## Macronutrients and mass

Mean absolute error, and in parentheses as a percentage of the mean true value (the metric used in the Nutrition5k paper).

| Model | Mass (g) | Protein (g) | Carbs (g) | Fat (g) | Mean output tokens | Median latency |
|---|---:|---:|---:|---:|---:|---:|
| Claude Fable 5.1 | 53 (25%) | 7.0 (37%) | 5.9 (26%) | 5.8 (44%) | 133 | 4.8s |
| Claude Opus 5.5 | 67 (31%) | 6.6 (35%) | 8.2 (36%) | 5.9 (45%) | 200 (38 reasoning) | 3.4s |
| Claude Sonnet 5 | 67 (31%) | 7.8 (41%) | 8.1 (36%) | 6.9 (53%) | 145 | 2.6s |
| GPT-6 Luna | 78 (36%) | 8.3 (44%) | 13.1 (57%) | 6.8 (52%) | 881 (782 reasoning) | 10.0s |
| GPT-6 Sol | 95 (44%) | 8.7 (46%) | 12.0 (53%) | 7.8 (60%) | 819 (723 reasoning) | 19.2s |
| Claude Haiku 4.5 | 94 (43%) | 10.5 (55%) | 14.6 (64%) | 8.6 (66%) | 1768 (1640 reasoning) | 16.9s |
| GPT-6 Astra | 108 (50%) | 9.6 (51%) | 15.2 (67%) | 8.1 (62%) | 1029 (927 reasoning) | 30.9s |

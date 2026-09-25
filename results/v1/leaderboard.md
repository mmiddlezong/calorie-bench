# CalorieBench leaderboard (prompt v1)

_Generated 2026-09-25 18:11 UTC. Ranked by mean absolute calorie error (lower is better). 95% CIs from 10,000 dish-level bootstrap resamples. Baseline rows (†) ignore the image and always guess the training-set average dish._

| # | Model | Calorie MAE, kcal (95% CI) | MAE % | Within ±20% | Median APE | MAPE | Bias (kcal) | r | Fail | Cost / 100 dishes | n |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **Claude Fable 5.1** | 81 (63–103) | 30% | 38% | 26% | 33% | -36 | 0.77 | 0% | $1.84 | 100/100 |
| 2 | **Claude Opus 5.5** | 93 (74–115) | 34% | 35% | 28% | 46% | +21 | 0.74 | 0% | $0.86 | 100/100 |
| 3 | **Claude Sonnet 5** | 100 (81–121) | 36% | 34% | 36% | 47% | +25 | 0.74 | 0% | $0.38 | 100/100 |
| 4 | **Claude Haiku 4.5** | 146 (122–172) | 53% | 24% | 43% | 82% | +60 | 0.59 | 0% | $0.93 | 100/100 |
| 5 | **GPT-6 Astra** | 148 (122–176) | 56% | 21% | 59% | 75% | +121 | 0.79 | 0% | $5.57 | 81/100 ⚠ |
|  | _Train-set median_ † | 157 (133–182) | 57% | 19% | 48% | 111% | -36 | – | 0% | – | 100/100 |
|  | _Train-set mean_ † | 158 (135–183) | 58% | 24% | 45% | 132% | +7 | – | 0% | – | 100/100 |

**Columns.** *MAE*: mean absolute error of total calories vs. the ground truth (computed from weighed ingredients). *MAE %*: MAE as a share of the mean true calories (Nutrition5k paper metric). *Within ±20%*: share of dishes estimated within 20% of the true value (the FDA's tolerance for nutrition labels). *Median APE* / *MAPE*: median / mean absolute percentage error. *Bias*: mean signed error (negative = underestimates). *r*: Pearson correlation of predicted vs. true calories. *Fail*: unparseable answers, refusals, and truncations (scored as predicting 0). *Cost*: actual API spend per 100 dishes at list prices. ⚠ = incomplete run.

## Macronutrients and mass

Mean absolute error, and in parentheses as a percentage of the mean true value (the metric used in the Nutrition5k paper).

| Model | Mass (g) | Protein (g) | Carbs (g) | Fat (g) | Mean output tokens | Median latency |
|---|---:|---:|---:|---:|---:|---:|
| Claude Fable 5.1 | 51 (24%) | 6.8 (35%) | 5.1 (24%) | 5.8 (44%) | 128 | 4.7s |
| Claude Opus 5.5 | 62 (30%) | 6.0 (31%) | 7.9 (37%) | 6.3 (48%) | 189 (33 reasoning) | 3.5s |
| Claude Sonnet 5 | 62 (30%) | 7.4 (38%) | 7.4 (35%) | 7.1 (55%) | 140 | 2.6s |
| Claude Haiku 4.5 | 87 (41%) | 10.5 (53%) | 13.6 (65%) | 9.3 (72%) | 1637 (1512 reasoning) | 16.3s |
| GPT-6 Astra | 104 (51%) | 9.1 (48%) | 15.8 (74%) | 8.7 (70%) | 977 (878 reasoning) | 27.9s |
| Train-set median | 108 (52%) | 14.0 (71%) | 14.1 (67%) | 8.7 (67%) | – | 0.0s |
| Train-set mean | 114 (54%) | 14.6 (74%) | 14.5 (69%) | 9.4 (72%) | – | 0.0s |

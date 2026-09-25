# CalorieBench leaderboard (prompt v1)

_Generated 2026-09-25 04:41 UTC. Ranked by mean absolute calorie error (lower is better). 95% CIs from 10,000 dish-level bootstrap resamples. Baseline rows (†) ignore the image and always guess the training-set average dish._

| # | Model | Calorie MAE, kcal (95% CI) | MAE % | Within ±20% | Median APE | MAPE | Bias (kcal) | r | Fail | Cost / 100 dishes | n |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|  | _Train-set median_ † | 157 (133–182) | 57% | 19% | 48% | 111% | -36 | – | 0% | – | 100/100 |
|  | _Train-set mean_ † | 158 (135–183) | 58% | 24% | 45% | 132% | +7 | – | 0% | – | 100/100 |

**Columns.** *MAE*: mean absolute error of total calories vs. the lab-measured value. *MAE %*: MAE as a share of the mean true calories (Nutrition5k paper metric). *Within ±20%*: share of dishes estimated within 20% of the true value (the FDA's tolerance for nutrition labels). *Median APE* / *MAPE*: median / mean absolute percentage error. *Bias*: mean signed error (negative = underestimates). *r*: Pearson correlation of predicted vs. true calories. *Fail*: unparseable answers, refusals, and truncations (scored as predicting 0). *Cost*: actual API spend per 100 dishes at list prices. ⚠ = incomplete run.

## Macronutrients and mass

Mean absolute error, and in parentheses as a percentage of the mean true value (the metric used in the Nutrition5k paper).

| Model | Mass (g) | Protein (g) | Carbs (g) | Fat (g) | Mean output tokens | Median latency |
|---|---:|---:|---:|---:|---:|---:|
| Train-set median | 108 (52%) | 14.0 (71%) | 14.1 (67%) | 8.7 (67%) | – | 0.0s |
| Train-set mean | 114 (54%) | 14.6 (74%) | 14.5 (69%) | 9.4 (72%) | – | 0.0s |

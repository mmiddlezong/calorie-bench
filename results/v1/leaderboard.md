# CalorieBench leaderboard (prompt v1)

_Generated 2026-09-25 18:38 UTC. Ranked by mean absolute calorie error (lower is better). 95% CIs from 10,000 dish-level bootstrap resamples._

| # | Model | Calorie MAE, kcal (95% CI) | MAE % | Within ±20% | Median APE | MAPE | Bias (kcal) | r | Fail | Cost / 100 dishes | n |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **Claude Fable 5.1** | 81 (63–103) | 30% | 38% | 26% | 33% | -36 | 0.77 | 0% | $1.84 | 100/100 |
| 2 | **Claude Opus 5.5** | 93 (74–115) | 34% | 35% | 28% | 46% | +21 | 0.74 | 0% | $0.86 | 100/100 |
| 3 | **Claude Sonnet 5** | 100 (81–121) | 36% | 34% | 36% | 47% | +25 | 0.74 | 0% | $0.38 | 100/100 |
| 4 | **GPT-6 Luna** | 118 (98–141) | 43% | 27% | 37% | 56% | +53 | 0.73 | 0% | $0.05 | 100/100 |
| 5 | **GPT-6 Sol** | 127 (107–150) | 46% | 27% | 39% | 67% | +80 | 0.75 | 0% | $0.94 | 100/100 |
| 6 | **GPT-6 Astra** | 146 (122–171) | 53% | 22% | 51% | 73% | +119 | 0.79 | 0% | $5.63 | 100/100 |
| 7 | **Claude Haiku 4.5** | 146 (122–172) | 53% | 24% | 43% | 82% | +60 | 0.59 | 0% | $0.93 | 100/100 |

**Columns.** *MAE*: mean absolute error of total calories vs. the ground truth (computed from weighed ingredients). *MAE %*: MAE as a share of the mean true calories (Nutrition5k paper metric). *Within ±20%*: share of dishes estimated within 20% of the true value (the FDA's tolerance for nutrition labels). *Median APE* / *MAPE*: median / mean absolute percentage error. *Bias*: mean signed error (negative = underestimates). *r*: Pearson correlation of predicted vs. true calories. *Fail*: unparseable answers, refusals, and truncations (scored as predicting 0). *Cost*: actual API spend per 100 dishes at list prices. ⚠ = incomplete run.

## Macronutrients and mass

Mean absolute error, and in parentheses as a percentage of the mean true value (the metric used in the Nutrition5k paper).

| Model | Mass (g) | Protein (g) | Carbs (g) | Fat (g) | Mean output tokens | Median latency |
|---|---:|---:|---:|---:|---:|---:|
| Claude Fable 5.1 | 51 (24%) | 6.8 (35%) | 5.1 (24%) | 5.8 (44%) | 128 | 4.7s |
| Claude Opus 5.5 | 62 (30%) | 6.0 (31%) | 7.9 (37%) | 6.3 (48%) | 189 (33 reasoning) | 3.5s |
| Claude Sonnet 5 | 62 (30%) | 7.4 (38%) | 7.4 (35%) | 7.1 (55%) | 140 | 2.6s |
| GPT-6 Luna | 72 (34%) | 7.6 (39%) | 12.7 (61%) | 7.2 (56%) | 871 (774 reasoning) | 10.7s |
| GPT-6 Sol | 83 (40%) | 8.1 (41%) | 11.7 (56%) | 8.3 (64%) | 804 (710 reasoning) | 18.9s |
| GPT-6 Astra | 101 (48%) | 9.0 (46%) | 15.1 (72%) | 9.0 (69%) | 989 (890 reasoning) | 29.3s |
| Claude Haiku 4.5 | 87 (41%) | 10.5 (53%) | 13.6 (65%) | 9.3 (72%) | 1637 (1512 reasoning) | 16.3s |

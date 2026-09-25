# CalorieBench

**How well can frontier AI models count calories from a photo of a meal?**

### 👉 [**Explore the interactive results →**](https://mmiddlezong.github.io/calorie-bench/)

## 🏆 Leaderboard

<!-- LEADERBOARD:START -->
| Rank | Model | Avg. calorie error | Within ±20% | Bias | Cost / 100 dishes |
|:---:|---|---:|---:|---:|---:|
| 🥇 | **Claude Fable 5.1** <sub>Anthropic</sub> | **81 kcal** <sub>(63–103)</sub> | 38% | -36 | $1.84 |
| 🥈 | **Claude Opus 5.5** <sub>Anthropic</sub> | **93 kcal** <sub>(74–115)</sub> | 35% | +21 | $0.86 |
| 🥉 | **Claude Sonnet 5** <sub>Anthropic</sub> | **100 kcal** <sub>(81–121)</sub> | 34% | +25 | $0.38 |
| 4 | **Claude Haiku 4.5** <sub>Anthropic</sub> | **146 kcal** <sub>(122–172)</sub> | 24% | +60 | $0.93 |
| – | _Train-set median_ (baseline, ignores the photo) | 157 kcal | 19% | -36 | – |
| – | _Train-set mean_ (baseline, ignores the photo) | 158 kcal | 24% | +7 | – |

<sub>Mean absolute error of total calories on 100 real cafeteria plates (95% bootstrap CI). Within ±20%: share of plates inside the FDA's nutrition-label tolerance. Bias: mean signed error (negative = underestimates). Every model at high reasoning effort. Updated 2026-09-25; full table in [`results/v1/leaderboard.md`](results/v1/leaderboard.md).</sub>
<!-- LEADERBOARD:END -->

<p align="center">
  <img src="docs/sample_dishes.jpg" width="720" alt="Twelve of the 100 benchmark dishes with their true calories">
</p>

CalorieBench shows a model an overhead photo of a real cafeteria plate and asks it to
estimate total calories (plus mass, protein, carbohydrates and fat). Answers are scored
against ground truth from [Nutrition5k](https://github.com/google-research-datasets/Nutrition5k),
where every ingredient on the plate was weighed during plating.

It is built to be cheap and quick to run: a fixed, carefully selected **100-dish subset**,
one request per dish, a resumable runner with a hard budget cap, and cost estimates before
anything is sent. Running every Claude model on all 100 dishes cost about $4.

---

## Quickstart

Requires [uv](https://docs.astral.sh/uv/). Python 3.12 is installed automatically.

```bash
git clone https://github.com/mmiddlezong/calorie-bench && cd calorie-bench
uv sync
uv run caloriebench download          # fetch the 100 images (~38 MB) from the public Nutrition5k bucket
cp .env.example .env                  # then add the API keys you have
uv run caloriebench models            # shows which models have keys configured
uv run caloriebench estimate frontier # cost estimate; sends nothing
uv run caloriebench run smoke -n 3    # ~$0.10: one cheap model per provider on 3 dishes, checks every key
uv run caloriebench run frontier      # the headline models (≈ $32 expected); asks before spending
uv run caloriebench score             # writes results/v1/leaderboard.md
```

Useful flags for `run`:

| Flag | Effect |
|---|---|
| `-n, --limit N` | Use only the first N dishes. Any prefix is calorie-balanced, so `-n 10` gives one dish per calorie decile. |
| `--max-cost 5` | Per-model spend cap in USD. No new request starts once actual spend, plus the estimated cost of in-flight requests, would exceed it. |
| `-c, --concurrency 8` | Parallel requests per model. |
| `--dry-run` | Build one request per model and print it. Nothing is sent. |
| `--repeats K` | K samples per dish, to measure run-to-run variance. |
| `--fresh` | Archive existing results for these models and start over. |
| `-y, --yes` | Skip the cost confirmation prompt. |

Runs are **resumable**. Every answer is appended to `results/v1/<model>/predictions.jsonl`
as soon as it arrives. Re-running the same command retries only requests that hit
network or API errors; completed dishes are never paid for twice.

Model selectors accept ids or groups: `frontier`, `budget`, `smoke`, `anthropic`, `openai`,
`google`, `xai`, `open-weights`, `baselines`, or `all`.

Other commands: `caloriebench compare A B` (paired significance test),
`caloriebench worst MODEL` (error analysis), `caloriebench prompt` (the exact prompt).

## Cost estimates

Estimated API cost for one full pass over the 100 dishes, with every model at high reasoning
effort, at list prices verified on **2026-09-25** (regenerate with `uv run caloriebench estimate --markdown`):

| Model | Lab | Price in / out ($/1M) | Tokens in / out per dish | Expected (100 dishes) | Range |
|---|---|---:|---:|---:|---:|
| Claude Fable 5.1 | Anthropic | $10 / $50 | 744 / 1,800 | **$9.74** | $5.99–$20.99 |
| Claude Opus 5.5 | Anthropic | $4 / $20 | 744 / 1,800 | **$3.90** | $2.40–$8.40 |
| Claude Sonnet 5 | Anthropic | $2 / $10 | 744 / 1,500 | **$1.65** | $1.05–$3.45 |
| Claude Haiku 4.5 | Anthropic | $1 / $5 | 744 / 1,800 | **$0.97** | $0.60–$2.10 |
| GPT-6 Astra | OpenAI | $10 / $50 | 690 / 800 | **$4.69** | $3.44–$8.44 |
| GPT-6 Sol | OpenAI | $2 / $10 | 690 / 1,300 | **$1.44** | $0.94–$2.94 |
| GPT-6 Luna | OpenAI | $0.1 / $0.5 | 690 / 2,800 | **$0.15** | $0.08–$0.33 |
| Gemini 3.8 Flash | Google | $0.75 / $3.75 | 1,450 / 4,800 | **$1.91** | $1.06–$4.44 |
| Gemini 3.1 Pro (preview) | Google | $2 / $12 | 1,450 / 3,300 | **$4.25** | $2.45–$9.65 |
| Gemini 3.5 Flash-Lite | Google | $0.3 / $2.5 | 1,450 / 3,300 | **$0.87** | $0.49–$1.99 |
| Grok 4.7 | xAI | $2 / $6 | 1,930 / 3,300 | **$2.37** | $1.47–$5.07 |
| Grok 4.3 | xAI | $1.25 / $2.5 | 1,930 / 3,300 | **$1.07** | $0.69–$2.19 |
| Kimi K3 | Moonshot AI (open weights) | $3 / $15 | 1,330 / 3,300 | **$5.35** | $3.10–$12.10 |
| Qwen3.8 Flash | Alibaba (open weights) | $0.15 / $0.47 | 630 / 3,300 | **$0.16** | $0.09–$0.38 |
| Ling 3.0 Flash VL | inclusionAI (open weights) | $0.06 / $0.18 | 630 / 3,300 | **$0.06** | $0.04–$0.14 |
| MiniMax-M3 | MiniMax (open weights) | $0.3 / $1.2 | 830 / 6,200 | **$0.77** | $0.41–$1.83 |
| **Total** | | | | **$39.34** | $24.31–$84.44 |

| Group | What | Expected | Range |
|---|---|---:|---:|
| `smoke -n 3` | cheapest model per provider, 3 dishes: checks keys and plumbing | **$0.10** | $0.06–$0.21 |
| `frontier -n 10` | headline models, 10 calorie-balanced dishes | **$3.22** | $1.99–$6.91 |
| `budget` | 9 cheaper models, full run | **$7.14** | $4.40–$15.36 |
| `frontier` | 7 headline models, full run | **$32.21** | $19.91–$69.09 |
| `all` | all 16 models, full run | **$39.34** | $24.31–$84.44 |

How to read this:

* **The uncertainty is almost entirely hidden reasoning tokens**, which are billed as
  output. Per-model assumptions come from Artificial Analysis MMMU-Pro token counts where
  available (noted in [`configs/models.yaml`](configs/models.yaml)). The range is 0.5× to
  2.5× that assumption. Claude Fable 5.1 is the most expensive because it has the highest
  output price, and it reasons on every request.
* **Image tokens differ a lot by provider.** A 640×480 photo costs 414 tokens on Claude,
  360 on GPT-6, 1,120 on Gemini (`media_resolution=high`), and roughly 1,600 on Grok
  (undocumented; the real number is logged on the first run).
* **Actual cost is always measured**, not estimated. It comes from API-reported token
  usage at the prices in `configs/models.yaml`, or from OpenRouter's reported charge.
  `score` reports actual spend per model.
* Gemini 3.8 Flash is at an introductory price until 2026-12-31. After that it doubles to
  $1.50 / $7.50. Batch APIs (50% off at Anthropic, OpenAI and Google) are not used yet;
  see [Roadmap](#roadmap).

## The dataset

[Nutrition5k](https://github.com/google-research-datasets/Nutrition5k) (Thames et al., CVPR
2021) contains about 5,000 plates from Google cafeterias. Each plate was built one
ingredient at a time on a scale. Its calories, mass and macronutrients are computed from
the weighed ingredient masses and per-ingredient nutrition values. Photos come from a
fixed overhead camera about 36 cm above the plate.

The benchmark subset lives in [`data/manifest.jsonl`](data/manifest.jsonl). It was built
once by [`scripts/build_subset.py`](scripts/build_subset.py), deterministically, and is
committed to the repo:

1. **Official test split only** (`rgb_test_ids`, 709 dishes). Published Nutrition5k models
   never trained on it.
2. **Overhead RGB photo available**: 507 dishes.
3. **Label filters**: 446 dishes remain.
   * at least 30 kcal, because tiny dishes make relative errors meaningless.
   * macros consistent with calories: |4·protein + 4·carbs + 9·fat − kcal| ≤ 25% of kcal.
     This catches likely label errors.
4. **Calorie-stratified sample**: 10 dishes from each calorie decile (seed `20260925`).
5. **Manual review of every drawn image.** Two were replaced: one where the food was
   almost entirely out of frame, and one with a neighbor's unlabeled food in view.
   Replacements were drawn from the same decile. About 15% of large plates have some
   food touching the top edge of the frame, because of the fixed camera. Those are kept,
   as in the original benchmark, since excluding them would bias toward small meals.
6. **Round-robin order**, so any prefix (`--limit 10`, `20`, …) is calorie-balanced.

| | min | median | mean | max |
|---|---:|---:|---:|---:|
| Calories (kcal) | 31 | 248 | 274 | 902 |

Images are fetched from the public bucket by `caloriebench download` and verified against
the SHA-256 checksums in the manifest. The manifest also includes each dish's weighed
ingredient list, which is useful for error analysis.

## Task and prompt

Every model gets the same single user message: the PNG photo followed by
[this prompt](src/caloriebench/prompt.py) (`uv run caloriebench prompt`). The prompt asks
the model to list each identified food item with estimated grams and calories, then give
plate totals as JSON:

```json
{"items": [{"name": "brown rice", "grams": 150, "calories": 165}, "..."],
 "total_calories": 540, "total_mass_g": 390, "protein_g": 32, "carbs_g": 61, "fat_g": 17}
```

* **Structured output** (JSON-schema-constrained decoding) is used wherever the provider
  supports it. A forgiving parser handles code fences, surrounding prose, and numbers
  written as strings.
* **Every model runs at high reasoning effort**: each vendor's own "think carefully" level,
  set explicitly in every request so a change in a provider's default can never silently
  change results (a test enforces this). "High" is not identical compute across vendors,
  but it removes the large imbalances between API defaults, which range from no reasoning
  (Claude Haiku 4.5, Gemini 3.5 Flash-Lite) to `max` (Kimi K3). See the table below. To
  benchmark another setting, add an entry with a new id, e.g. `gpt-6-astra-low`.

| Model | Setting sent | API default |
|---|---|---|
| Claude Fable 5.1, Sonnet 5 | `effort: high` (adaptive thinking) | same |
| Claude Opus 5.5 | `effort: high` (adaptive thinking) | medium |
| Claude Haiku 4.5 | extended thinking, 8,000-token budget (no effort setting) | no thinking |
| GPT-6 Astra | `reasoning.effort: high` | not documented |
| GPT-6 Sol, Luna | `reasoning.effort: high` | medium |
| Gemini 3.8 Flash | `thinking_level: high` | medium |
| Gemini 3.1 Pro | `thinking_level: high` | same |
| Gemini 3.5 Flash-Lite | `thinking_level: high` | minimal |
| Grok 4.7 | `reasoning.effort: high` | same |
| Grok 4.3 | `reasoning.effort: high` | low |
| Kimi K3 | `reasoning.effort: high` | max |
| Qwen3.8 Flash, Ling 3.0 Flash VL, MiniMax-M3 | reasoning enabled (no effort levels) | on (MiniMax: not documented) |

* **Sampling parameters are left at provider defaults.** Several current reasoning models
  reject `temperature`.
* **No refusal fallbacks or model routing.** A refusal counts against the model that
  refused. OpenRouter models are pinned to specific full-precision providers.
* The prompt is versioned (`v1`). Results live under `results/v1/`, and a run refuses to
  mix results produced by a different prompt, dataset, or request configuration.

## Metrics

**Headline: mean absolute error of total calories (kcal)**, with a 95% bootstrap confidence
interval (10,000 dish-level resamples). It is also shown as a percentage of the mean true
calories ("MAE %"), the metric used in the Nutrition5k paper.

Secondary metrics:

| Metric | Meaning |
|---|---|
| Within ±20% | Share of dishes estimated within 20% of the truth. 20% is the FDA's tolerance for nutrition labels. |
| Median APE, MAPE | Median and mean absolute percentage error. |
| Bias | Mean signed error in kcal. Negative means the model systematically underestimates. |
| r | Pearson correlation between predicted and true calories. |
| Mass, protein, carbs, fat | MAE in grams, and as a % of the mean. |
| Fail | Share of answers that were unparseable, refused, or truncated. |
| Cost, tokens, latency | Measured from the run. |

Scoring rules:

* **Failures count as predicting 0**, so the absolute error is the whole meal. A failure
  therefore scores worse than a trivial guess-the-average answer.
* **Infrastructure errors do not count against the model.** Rate limits and outages are
  retried on re-run; until then the leaderboard marks the run incomplete (⚠).
* **Why MAE rather than MAPE as the headline.** MAPE caps underestimates at 100% but not
  overestimates. A model that answered "0 kcal" for everything would get MAPE = 100% and
  beat a guess-the-average baseline (111%). MAPE is also dominated by the smallest dishes.
* **Significance.** With 100 dishes, differences of 10–15 kcal are often noise.
  `caloriebench compare A B` runs a paired bootstrap test on the dishes both models
  answered.

## Reference points

| System | Evaluated on | Calorie MAE | MAE % |
|---|---|---:|---:|
| Always guess train-set median (baseline, this repo) | CalorieBench 100 | 157 kcal | 57% |
| Always guess train-set mean (baseline, this repo) | CalorieBench 100 | 158 kcal | 58% |
| Nutrition5k paper: guess the mean | full test split | 150.8 kcal | 60.2% |
| Nutrition5k paper: CNN trained on Nutrition5k, RGB only | full test split | 70.6 kcal | 26.1% |
| Nutrition5k paper: CNN, RGB + depth-derived volume | full test split | 41.3 kcal | 16.5% |

The paper's models were trained on the Nutrition5k training split (about 4,000 dishes from
the same cafeterias, plates and camera), and the RGB-D models also saw depth. Frontier models are
zero-shot. Their numbers are on a different (larger) test set, so treat the comparison as
indicative.

## Results website

[`site/`](site/) is a static results site: leaderboard with confidence intervals,
accuracy-vs-cost Pareto chart, bias and within-±20% charts, predicted-vs-true scatter,
and a dish explorer that shows every model's itemized guess next to the weighed
ingredients. Rebuild its data after scoring, then open it locally:

```bash
uv run caloriebench site                        # writes site/data.js + thumbnails
python3 -m http.server 8765 --directory site    # then visit http://localhost:8765
```

It is plain HTML/JS with no build step and no dependencies. It is live at
**https://mmiddlezong.github.io/calorie-bench/** and redeploys automatically when `site/`
changes on `main`. Only complete runs are published; pass `--include-incomplete` for a
local preview of runs in progress.

## Updating the leaderboard

`caloriebench score` rewrites the table at the top of this README (complete runs only) and
[`results/v1/leaderboard.md`](results/v1/leaderboard.md) (every run, incomplete ones marked ⚠).
`caloriebench site` rebuilds the website data. Pushing `site/` to `main` redeploys
[the website](https://mmiddlezong.github.io/calorie-bench/) via GitHub Pages.

## Adding a model

Add an entry to [`configs/models.yaml`](configs/models.yaml):

```yaml
  - id: my-model-high                # unique id; results are stored under this name
    display_name: My Model (high)
    lab: Some Lab
    provider: openai                 # anthropic | openai | google | xai | openrouter | openai_chat
    model: my-model-2026-09          # the API model string
    groups: [frontier]
    params: {reasoning_effort: high} # provider-specific; see each provider's docstring
    pricing: {input: 1.25, output: 10.00}
    estimate: {image_tokens: 360, reasoning_tokens: 1000}
```

Any OpenAI-compatible endpoint works through `provider: openai_chat` (Chat Completions) or
`provider: openai` (Responses API), together with `base_url:` and `api_key_env: [MY_KEY]`.
Run `uv run caloriebench run my-model-high --dry-run` to check the request before spending.

## Repository layout

```
configs/models.yaml          model registry: API ids, request settings, prices, estimates
data/manifest.jsonl          the 100 dishes: labels, ingredients, image URL + checksum
data/subset_info.json        how the subset was drawn
data/baselines.json          train-split mean / median predictors
scripts/build_subset.py      reproducible subset construction (maintainers only)
src/caloriebench/
  prompt.py                  prompt v1 + JSON schema
  providers/                 anthropic, openai (Responses; also xAI), openai_chat (OpenRouter), google, baseline
  runner.py                  async, resumable, budget-capped runner
  parsing.py                 robust answer parsing
  metrics.py                 MAE/MAPE/within-X, bootstrap CIs, paired comparison
  report.py                  leaderboard.md / leaderboard.json
  cli.py                     `caloriebench` command
results/v1/<model>/          predictions.jsonl (every request, append-only) + meta.json
tests/                       unit tests + real-SDK tests against a local mock server
```

Each line of `predictions.jsonl` records the parsed prediction, raw response text, status,
normalized and raw token usage, cost, latency, served model version, and request id.
`meta.json` pins the prompt hash, dataset hash, request configuration, and git commit.

## Caveats

* **100 dishes is small.** Confidence intervals are wide (roughly ±15–25 kcal on MAE). Use `compare` before claiming one model beats another.
* **One cuisine and one setting.** These are Google cafeteria plates from 2019, photographed
  from directly above with no scale reference. Results may not transfer to home cooking,
  restaurant food, or phone photos taken at an angle.
* **Label noise.** Ground truth is computed from weighed ingredients and database nutrition
  values, not lab assays. Hidden oil and sauces are measured, but are sometimes invisible
  in the photo.
* **Possible contamination.** Nutrition5k has been public since 2021, although memorizing
  per-dish values from photos seems unlikely.
* **Provider defaults drift.** Model behavior, default reasoning effort, and prices change
  over time. Every run records its configuration and the served model version.

## Roadmap

* Batch-API support (50% cheaper at Anthropic, OpenAI, and Google).
* Prompt variants, e.g. giving the camera height (35.9 cm) as a scale reference, or
  asking for calories only.
* Ingredient-identification scoring, using the weighed ingredient lists already in the
  manifest.
* Plots: predicted vs. true calories per model.

## Citation and license

Code: MIT (see [LICENSE](LICENSE)). The dish images and labels are from Nutrition5k and
are licensed CC BY 4.0 by Google. Please cite the original dataset:

```bibtex
@inproceedings{thames2021nutrition5k,
  title     = {Nutrition5k: Towards Automatic Nutritional Understanding of Generic Food},
  author    = {Thames, Quin and Karpur, Arjun and Norris, Wade and Xia, Fangting and Panait, Liviu
               and Weyand, Tobias and Sim, Jack},
  booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  year      = {2021}
}
```

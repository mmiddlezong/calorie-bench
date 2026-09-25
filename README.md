# CalorieBench

How accurately can AI models count the calories in a photo of your food?

**[See the full results, with every plate and every guess →](https://mmiddlezong.github.io/calorie-bench/)**

## Results

<!-- LEADERBOARD:START -->
| Rank | Model | Average error | Within 20% | Tends to guess | Cost for 100 photos |
|:---:|---|---:|---:|---|---:|
| 1 | **Claude Fable 5.1** (Anthropic) | **81** calories (63–103) | 38% | 36 too low | $1.84 |
| 2 | **Claude Opus 5.5** (Anthropic) | **93** calories (74–115) | 35% | 21 too high | $0.86 |
| 3 | **Claude Sonnet 5** (Anthropic) | **100** calories (81–121) | 34% | 25 too high | $0.38 |
| 4 | **GPT-6 Luna** (OpenAI) | **118** calories (98–141) | 27% | 53 too high | $0.05 |
| 5 | **GPT-6 Sol** (OpenAI) | **127** calories (107–150) | 27% | 80 too high | $0.94 |
| 6 | **GPT-6 Astra** (OpenAI) | **146** calories (122–171) | 22% | 119 too high | $5.63 |
| 7 | **Claude Haiku 4.5** (Anthropic) | **146** calories (122–172) | 24% | 60 too high | $0.93 |

Average error is how far a model's estimate was from the true calorie count, averaged over all 100 plates. The range in parentheses is a 95% confidence interval: when two models' ranges overlap, the difference between them may be luck. "Within 20%" is the share of plates a model got within 20% of the truth. Updated September 25, 2026.
<!-- LEADERBOARD:END -->

## How the test works

We gave each model 100 photos of real meals from a campus cafeteria, one at a time, and
asked how many calories were on the plate. The photos come from
[Nutrition5k](https://github.com/google-research-datasets/Nutrition5k), a research dataset
in which every ingredient was weighed as the plate was put together, so the true calorie
count of each plate is known.

The plates range from half an ear of corn (31 calories) to a full plate of chicken,
roasted potatoes and grains (920 calories). Every model saw the same photos and got the
same instructions.

<p align="center">
  <img src="docs/sample_dishes.jpg" width="720" alt="Twelve of the 100 plates, each labeled with its true calorie count">
</p>

## What we found

**Even the best model is often far off.** Claude Fable 5.1 was the most accurate, but its
estimates were still off by 81 calories per plate on average, and it came within 20% of
the truth on only 38 of the 100 plates. On 23 plates, no model got within 20%.

**Models guess toward an average-sized meal.** On small plates, under 150 calories, every
model tended to guess too high. On big plates, over 500 calories, six of the seven guessed
far too low: Claude Fable 5.1 missed those by 247 calories on average. Large meals are
where the errors add up.

**Price is a poor guide to accuracy.** GPT-6 Luna cost 5 cents to run on all 100 photos
and beat GPT-6 Astra, which cost more than 100 times as much.

If you use an app that estimates calories from photos, treat its number as a rough
starting point, especially for large or mixed plates.

## Limits

One hundred plates is enough to tell the best models from the worst, but not to rank
models whose scores are close. The ranges in the table show how much uncertainty there is.
All of the food comes from one cafeteria in 2019 and is mostly Western-style, every photo
was taken from directly above, and nothing in the frame shows scale. The true calorie counts come from
weighed ingredients and standard nutrition tables, not laboratory tests.

## Run it yourself

CalorieBench is open source. You need [uv](https://docs.astral.sh/uv/) and API keys for
the models you want to test.

```bash
git clone https://github.com/mmiddlezong/calorie-bench && cd calorie-bench
uv sync
uv run caloriebench download            # the 100 photos, about 38 MB
cp .env.example .env                    # then add your API keys
uv run caloriebench estimate anthropic  # see what a run will cost before paying for it
uv run caloriebench run anthropic
uv run caloriebench score               # updates the results table above
```

Running all four Claude models cost about $4. How the plates were chosen, the exact
prompt, the scoring rules, cost estimates for every model, and how to add a new one are
in [docs/methodology.md](docs/methodology.md).

## Credits

Photos and nutrition data are from Nutrition5k (Thames et al., CVPR 2021), released by
Google under CC BY 4.0. The code is MIT licensed.

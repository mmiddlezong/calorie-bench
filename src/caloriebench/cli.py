"""Command-line interface: `uv run caloriebench --help`."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from .config import load_registry
from .cost import estimate_cost
from .dataset import download_images, load_dishes
from .paths import ROOT
from .prompt import PROMPT, PROMPT_VERSION

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="CalorieBench: benchmark AI models at estimating calories from meal photos.",
)
console = Console()

ModelsArg = Annotated[
    list[str] | None, typer.Argument(help="Model ids and/or group names (see `caloriebench models`). Default: all.")
]
LimitOpt = Annotated[
    int | None, typer.Option("--limit", "-n", help="Use only the first N dishes (any prefix is calorie-balanced).")
]


@app.callback()
def _main() -> None:
    load_dotenv(ROOT / ".env")


@app.command()
def download(force: Annotated[bool, typer.Option(help="Re-download even if present.")] = False) -> None:
    """Download the 100 benchmark images (~38 MB) from the public Nutrition5k bucket."""
    fetched, present = download_images(force=force)
    console.print(f"[green]✓[/] images ready: {fetched} downloaded, {present} already present (checksums verified)")


@app.command()
def models(group: Annotated[str | None, typer.Option(help="Only show this group.")] = None) -> None:
    """List configured models, their prices, and whether an API key is set."""
    reg = load_registry()
    table = Table(title=f"Model registry (prices checked {reg.pricing_checked}, USD per 1M tokens)")
    for col in ("id", "lab", "provider", "API model", "in $", "out $", "groups", "key"):
        table.add_column(col)
    for m in reg.models:
        if group and group not in m.groups:
            continue
        key = "[green]✓[/]" if m.has_credentials() else f"[red]✗[/] {'/'.join(m.key_envs())}"
        table.add_row(
            m.id + ("" if m.enabled else " (disabled)"),
            m.lab,
            m.provider,
            m.model,
            f"{m.pricing.input:g}",
            f"{m.pricing.output:g}",
            ",".join(m.groups),
            key,
        )
    console.print(table)
    console.print("Groups: " + ", ".join(f"{g} ({len(ids)})" for g, ids in reg.groups().items()))


def _estimate_table(specs, n_requests: int) -> tuple[Table, float, float, float]:
    table = Table(title=f"Estimated cost for {n_requests} requests per model")
    for col in ("model", "in tok/req", "out tok/req", "low", "expected", "high"):
        table.add_column(col, justify="right" if col != "model" else "left")
    lo = ex = hi = 0.0
    for spec in specs:
        est = estimate_cost(spec, n_requests)
        lo, ex, hi = lo + est.low_usd, ex + est.expected_usd, hi + est.high_usd
        table.add_row(
            spec.id,
            str(est.input_tokens_per_req),
            str(est.output_tokens_per_req),
            f"${est.low_usd:.2f}",
            f"${est.expected_usd:.2f}",
            f"${est.high_usd:.2f}",
        )
    table.add_section()
    table.add_row("[bold]TOTAL[/]", "", "", f"${lo:.2f}", f"[bold]${ex:.2f}[/]", f"${hi:.2f}")
    return table, lo, ex, hi


def _estimate_markdown(specs, n_requests: int) -> str:
    lines = [
        f"| Model | Lab | Price in / out ($/1M) | Tokens in / out per dish | Expected ({n_requests} dishes) | Range |",
        "|---|---|---:|---:|---:|---:|",
    ]
    lo = ex = hi = 0.0
    for spec in specs:
        est = estimate_cost(spec, n_requests)
        lo, ex, hi = lo + est.low_usd, ex + est.expected_usd, hi + est.high_usd
        price = f"${spec.pricing.input:g} / ${spec.pricing.output:g}"
        lines.append(
            f"| {spec.display_name} | {spec.lab} | {price} | {est.input_tokens_per_req:,} / "
            f"{est.output_tokens_per_req:,} | **${est.expected_usd:.2f}** | ${est.low_usd:.2f}–${est.high_usd:.2f} |"
        )
    lines.append(f"| **Total** | | | | **${ex:.2f}** | ${lo:.2f}–${hi:.2f} |")
    return "\n".join(lines)


@app.command()
def estimate(
    model_names: ModelsArg = None,
    limit: LimitOpt = None,
    repeats: Annotated[int, typer.Option(help="Samples per dish.")] = 1,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
    markdown: Annotated[bool, typer.Option("--markdown", help="Print a Markdown table (for the README).")] = False,
) -> None:
    """Estimate API cost before running (no API calls are made)."""
    reg = load_registry()
    specs = [s for s in reg.select(model_names) if not s.is_baseline]
    n = len(load_dishes(limit)) * repeats
    if as_json:
        out = [estimate_cost(s, n).__dict__ for s in specs]
        console.print_json(json.dumps(out))
        return
    if markdown:
        print(_estimate_markdown(specs, n))
        return
    table, *_ = _estimate_table(specs, n)
    console.print(table)
    console.print(
        "[dim]Range reflects uncertainty in hidden reasoning tokens (0.5×–2.5× the assumed "
        "amount). Actual cost is computed from API-reported usage during the run.[/]"
    )


def _redact(obj):
    """Shorten image payloads and the prompt so a request can be printed readably."""
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    if isinstance(obj, bytes):
        return f"<{len(obj):,} image bytes>"
    if isinstance(obj, str):
        if obj == PROMPT:
            return f"<prompt {PROMPT_VERSION}, {len(PROMPT)} chars>"
        if len(obj) > 300:
            return f"{obj[:40]}…<{len(obj):,} chars>"
    return obj


@app.command()
def run(
    model_names: ModelsArg = None,
    limit: LimitOpt = None,
    repeats: Annotated[int, typer.Option(help="Samples per dish (default 1).")] = 1,
    concurrency: Annotated[int, typer.Option("--concurrency", "-c", help="Parallel requests per model.")] = 8,
    max_cost: Annotated[float | None, typer.Option(help="Per-model spend cap (USD).")] = None,
    fresh: Annotated[bool, typer.Option(help="Archive existing results for these models and start over.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip the cost confirmation prompt.")] = False,
    dry_run: Annotated[bool, typer.Option(help="Build one request per model and print it; send nothing.")] = False,
) -> None:
    """Run models on the benchmark. Resumable: re-running only fills in missing dishes."""
    from .providers import make_provider
    from .runner import RunConfigMismatch, run_model

    reg = load_registry()
    specs = reg.select(model_names)
    dishes = load_dishes(limit)

    if dry_run:
        from .runner import MEDIA_TYPE

        image = dishes[0].load_image()
        for spec in specs:
            req = make_provider(spec).build_request(image, MEDIA_TYPE, PROMPT)
            console.rule(f"{spec.id} ({spec.provider})")
            console.print_json(json.dumps(_redact(req)), indent=1)
        console.print("[dim]Dry run: nothing was sent.[/]")
        return

    missing = [s for s in specs if not s.has_credentials()]
    for s in missing:
        console.print(f"[yellow]skipping {s.id}: set {' or '.join(s.key_envs())}[/]")
    specs = [s for s in specs if s.has_credentials()]
    if not specs:
        raise typer.Exit(1)

    paid = [s for s in specs if not s.is_baseline]
    if paid and not yes:
        table, lo, ex, hi = _estimate_table(paid, len(dishes) * repeats)
        console.print(table)
        console.print("[dim]Already-completed dishes are skipped, so resumed runs cost less.[/]")
        if not typer.confirm(f"Proceed? (expected ≈ ${ex:.2f}, range ${lo:.2f}–${hi:.2f})"):
            raise typer.Exit(0)

    any_failed = False
    for spec in specs:
        console.rule(f"[bold]{spec.display_name}[/] ({spec.id})")
        with Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TextColumn("{task.fields[spent]}"),
            console=console,
        ) as prog:
            task = prog.add_task(spec.id, total=None, spent="")

            def on_start(n_todo: int, _task=task) -> None:
                prog.update(_task, total=n_todo)

            def on_record(rec: dict, spent: float, _task=task) -> None:
                prog.update(_task, advance=1, spent=f"${spent:.3f} · last: {rec['status']}")

            try:
                summary = asyncio.run(
                    run_model(
                        spec,
                        dishes,
                        repeats=repeats,
                        concurrency=concurrency,
                        max_cost=max_cost,
                        fresh=fresh,
                        on_start=on_start,
                        on_record=on_record,
                    )
                )
            except RunConfigMismatch as e:
                any_failed = True
                console.print(f"[red]{e}[/]")
                continue
        statuses = ", ".join(f"{k}: {v}" for k, v in sorted(summary.statuses.items())) or "nothing to do"
        console.print(
            f"{spec.id}: {summary.skipped} already done, {summary.attempted} attempted "
            f"({statuses}); spent ${summary.cost_usd:.4f}"
        )
        if summary.aborted:
            any_failed = True
            console.print(f"[red]aborted: {summary.aborted}[/]")
        if summary.statuses.get("api_error"):
            any_failed = True
            console.print("[yellow]Some requests hit API errors; re-run the same command to retry them.[/]")
    console.print("\nNext: [bold]uv run caloriebench score[/]")
    if any_failed:
        raise typer.Exit(2)


@app.command()
def score(
    model_names: ModelsArg = None,
    write: Annotated[bool, typer.Option(help="Write leaderboard.md / leaderboard.json.")] = True,
) -> None:
    """Score stored predictions and write the leaderboard."""
    from .report import discover_models, score_all, write_leaderboard

    reg = load_registry()
    available = discover_models()
    if model_names:
        wanted = {s.id for s in reg.select(model_names)}
        available = [m for m in available if m in wanted]
    if not available:
        console.print(f"[yellow]No results found under results/{PROMPT_VERSION}/. Run `caloriebench run` first.[/]")
        raise typer.Exit(1)
    dishes = load_dishes()
    scores = score_all(dishes, available)

    table = Table(title=f"CalorieBench (prompt {PROMPT_VERSION}) — ranked by calorie MAE")
    for col in ("model", "MAE kcal", "95% CI", "MAE %", "±20%", "MdAPE", "bias", "fail", "$/100", "n"):
        table.add_column(col, justify="left" if col == "model" else "right")
    for s in scores:
        c = s.calories
        if not c:
            continue
        lo, hi = c["mae_kcal_ci95"]
        table.add_row(
            s.model_id,
            f"{c['mae_kcal']:.0f}",
            f"{lo:.0f}–{hi:.0f}",
            f"{100 * c['mae_pct_of_mean']:.0f}%",
            f"{100 * c['within_20pct']:.0f}%",
            f"{100 * c['mdape']:.0f}%",
            f"{c['mean_signed_error_kcal']:+.0f}",
            f"{100 * s.failure_rate:.0f}%",
            f"${100 * s.usage.get('cost_per_dish_usd', 0):.2f}",
            f"{s.n_dishes}/{s.n_total}",
        )
    console.print(table)
    if write:
        md, js = write_leaderboard(scores, reg)
        console.print(f"[green]✓[/] wrote {md.relative_to(ROOT)} and {js.relative_to(ROOT)}")


@app.command()
def compare(model_a: str, model_b: str) -> None:
    """Paired bootstrap test: is model A's calorie MAE different from model B's?"""
    from .metrics import compare_models
    from .runner import predictions_path, read_records

    dishes = load_dishes()
    c = compare_models(
        dishes, model_a, read_records(predictions_path(model_a)), model_b, read_records(predictions_path(model_b))
    )
    if c.n_common < 2:
        console.print("[yellow]Not enough dishes answered by both models.[/]")
        raise typer.Exit(1)
    better = model_a if c.diff < 0 else model_b
    console.print(
        f"{c.n_common} common dishes | calorie MAE {model_a}: {c.mae_a:.1f} kcal  {model_b}: {c.mae_b:.1f} kcal"
    )
    console.print(
        f"difference (A−B): {c.diff:+.1f} kcal, 95% CI [{c.diff_ci95[0]:+.1f}, "
        f"{c.diff_ci95[1]:+.1f}], p = {c.p_value:.3f}"
    )
    verdict = "significant" if c.p_value < 0.05 else "not significant"
    console.print(f"→ {better} is better; difference is [bold]{verdict}[/] at α = 0.05")


@app.command()
def worst(
    model_id: str,
    n: Annotated[int, typer.Option("-n", help="How many dishes to show.")] = 10,
) -> None:
    """Show the dishes a model got most wrong (for error analysis)."""
    from .metrics import collect_outcomes
    from .runner import predictions_path, read_records

    dishes = load_dishes()
    outcomes = collect_outcomes(dishes, read_records(predictions_path(model_id)))
    rows = []
    for o in outcomes:
        rec = o.samples[0]
        pred = (rec.get("prediction") or {}).get("total_calories") if rec.get("status") == "ok" else None
        ape = abs((pred or 0) - o.dish.calories) / o.dish.calories
        rows.append((ape, o, rec, pred))
    rows.sort(key=lambda r: -r[0])
    for ape, o, rec, pred in rows[:n]:
        truth_items = ", ".join(f"{i['name']} {i['grams']:.0f}g" for i in o.dish.ingredients[:8])
        console.rule(f"#{o.dish.index} {o.dish.dish_id} — APE {100 * ape:.0f}%")
        console.print(f"[bold]true[/] {o.dish.calories:.0f} kcal, {o.dish.mass_g:.0f} g: {truth_items}")
        if pred is None:
            console.print(f"[red]{rec.get('status')}[/]: {rec.get('error', '')}")
        else:
            items = ", ".join(
                f"{i['name']} {i.get('grams') or 0:.0f}g" for i in (rec["prediction"].get("items") or [])[:8]
            )
            console.print(f"[bold]pred[/] {pred:.0f} kcal, {rec['prediction'].get('total_mass_g') or 0:.0f} g: {items}")
        console.print(f"[dim]image: data/{o.dish.image}[/]")


@app.command()
def site() -> None:
    """Build the results website data (site/data.js + thumbnails) from stored predictions."""
    from .site import build_site

    out = build_site(load_dishes(), load_registry())
    console.print(f"[green]✓[/] wrote {out.relative_to(ROOT)} — open site/index.html in a browser")


@app.command()
def prompt() -> None:
    """Print the exact prompt sent with every image."""
    console.print(f"[bold]Prompt {PROMPT_VERSION}[/]\n")
    print(PROMPT)


if __name__ == "__main__":
    app()

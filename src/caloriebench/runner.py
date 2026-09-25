"""Run one model over the benchmark: concurrent, resumable, and budget-capped.

Layout:  results/<prompt_version>/<model_id>/predictions.jsonl   (append-only)
         results/<prompt_version>/<model_id>/meta.json

Resume semantics: a (dish, sample) pair is done once it has a record whose status is a
*model outcome* (ok / parse_error / refusal / truncated). Records with status api_error
(network trouble, rate limits, outages) are retried on the next invocation, so re-running
the same command after a crash only pays for the missing requests.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import __version__
from .config import ModelSpec
from .cost import estimate_cost, usage_cost
from .dataset import Dish, dishes_hash, manifest_hash
from .parsing import ParseError, parse_prediction
from .paths import RESULTS_DIR, ROOT
from .prompt import PROMPT, PROMPT_VERSION, prompt_hash
from .providers import ProviderError, make_provider

MEDIA_TYPE = "image/png"
FINAL_STATUSES = {"ok", "parse_error", "refusal", "truncated"}
MAX_RAW_CHARS = 20_000
MAX_CONSECUTIVE_FATAL = 3


def run_dir(model_id: str, results_dir: Path = RESULTS_DIR) -> Path:
    return results_dir / PROMPT_VERSION / model_id


def predictions_path(model_id: str, results_dir: Path = RESULTS_DIR) -> Path:
    return run_dir(model_id, results_dir) / "predictions.jsonl"


def read_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # tolerate a torn final line from a hard kill
    return records


def _git_commit() -> str | None:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        return f"{sha}{'-dirty' if dirty else ''}" if sha else None
    except Exception:
        return None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class RunSummary:
    model_id: str
    planned: int = 0
    skipped: int = 0
    attempted: int = 0
    statuses: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    aborted: str | None = None

    def count(self, status: str) -> None:
        self.statuses[status] = self.statuses.get(status, 0) + 1


class RunConfigMismatch(RuntimeError):
    pass


def _check_meta(meta_path: Path, spec: ModelSpec, fresh: bool, answered: set[str]) -> dict:
    current = {
        "model_id": spec.id,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash(),
        "manifest_hash": manifest_hash(),
        "request_config": spec.model_dump(
            include={"provider", "model", "params", "structured_output", "max_output_tokens"}
        ),
    }
    if meta_path.exists() and not fresh:
        old = json.loads(meta_path.read_text())
        # The dataset may grow (new dishes added) as long as every dish this run already
        # answered is unchanged; any edit to an answered dish still counts as a mismatch.
        if (
            old.get("manifest_hash") != current["manifest_hash"]
            and old.get("run_dishes_hash")
            and (dishes_hash(answered) == old["run_dishes_hash"])
        ):
            old["manifest_hash"] = current["manifest_hash"]
        for key in ("prompt_hash", "manifest_hash", "request_config"):
            if old.get(key) != current[key]:
                raise RunConfigMismatch(
                    f"{spec.id}: existing results were produced with a different {key}.\n"
                    f"  old: {old.get(key)}\n  new: {current[key]}\n"
                    "Re-run with --fresh to archive them and start over, or give this "
                    "configuration a new model id in configs/models.yaml."
                )
        current["started_at"] = old.get("started_at", _now())
    else:
        current["started_at"] = _now()
    return current


async def run_model(
    spec: ModelSpec,
    dishes: list[Dish],
    *,
    repeats: int = 1,
    concurrency: int = 8,
    max_cost: float | None = None,
    fresh: bool = False,
    results_dir: Path = RESULTS_DIR,
    on_start=None,
    on_record=None,
) -> RunSummary:
    out_dir = run_dir(spec.id, results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / "predictions.jsonl"
    meta_path = out_dir / "meta.json"

    if fresh and pred_path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        pred_path.rename(out_dir / f"predictions.{stamp}.bak.jsonl")
    existing = read_records(pred_path)
    meta = _check_meta(meta_path, spec, fresh, {r["dish_id"] for r in existing})

    done = {(r["dish_id"], r.get("sample", 0)) for r in existing if r.get("status") in FINAL_STATUSES}
    todo = [(d, s) for s in range(repeats) for d in dishes if (d.dish_id, s) not in done]
    summary = RunSummary(model_id=spec.id, planned=len(dishes) * repeats, skipped=len(dishes) * repeats - len(todo))

    meta.update(
        {
            "display_name": spec.display_name,
            "lab": spec.lab,
            "pricing": spec.pricing.model_dump(),
            "caloriebench_version": __version__,
            "git_commit": _git_commit(),
            "updated_at": _now(),
            "run_dishes_hash": dishes_hash({r["dish_id"] for r in existing}),
        }
    )
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    if on_start:
        on_start(len(todo))
    if not todo:
        return summary

    provider = make_provider(spec)
    per_req_estimate = estimate_cost(spec, 1).expected_usd
    sem = asyncio.Semaphore(concurrency)
    write_lock = asyncio.Lock()
    state = {"spent": 0.0, "inflight": 0, "consecutive_fatal": 0}
    stop = asyncio.Event()

    async def one(dish: Dish, sample: int) -> None:
        async with sem:
            if stop.is_set():
                return
            if max_cost is not None and state["spent"] + (state["inflight"] + 1) * per_req_estimate > max_cost:
                summary.aborted = summary.aborted or f"budget cap ${max_cost:.2f} reached"
                stop.set()
                return
            state["inflight"] += 1
            record: dict = {
                "dish_id": dish.dish_id,
                "index": dish.index,
                "sample": sample,
                "model_id": spec.id,
                "prompt_version": PROMPT_VERSION,
            }
            t0 = time.perf_counter()
            try:
                image = dish.load_image()
                result = await provider.complete(image, MEDIA_TYPE, PROMPT)
                record["latency_s"] = round(time.perf_counter() - t0, 3)
                cost = usage_cost(result.usage, spec)
                if result.provider_cost_usd is not None:
                    cost = result.provider_cost_usd
                record.update(
                    {
                        "usage": result.usage.to_dict(),
                        "raw_usage": result.raw_usage,
                        "cost_usd": round(cost, 6),
                        "stop_reason": result.stop_reason,
                        "served_model": result.served_model,
                        "request_id": result.request_id,
                        "raw_text": (result.text or "")[:MAX_RAW_CHARS],
                    }
                )
                state["spent"] += cost
                state["consecutive_fatal"] = 0
                try:
                    record["prediction"] = parse_prediction(result.text).to_dict()
                    record["status"] = "ok"
                except ParseError as e:
                    record["prediction"] = None
                    record["error"] = str(e)
                    record["status"] = (
                        "refusal" if result.refused else "truncated" if result.truncated else "parse_error"
                    )
            except ProviderError as e:
                record.update(
                    {
                        "status": "api_error",
                        "fatal": True,
                        "error": str(e)[:2000],
                        "latency_s": round(time.perf_counter() - t0, 3),
                    }
                )
                state["consecutive_fatal"] += 1
                if state["consecutive_fatal"] >= MAX_CONSECUTIVE_FATAL:
                    summary.aborted = f"{MAX_CONSECUTIVE_FATAL} consecutive non-retryable errors; last: {e}"
                    stop.set()
            except Exception as e:  # network/rate-limit/server errors after SDK retries
                record.update(
                    {
                        "status": "api_error",
                        "error": f"{type(e).__name__}: {e}"[:2000],
                        "latency_s": round(time.perf_counter() - t0, 3),
                    }
                )
            finally:
                state["inflight"] -= 1
            record["timestamp"] = _now()
            summary.attempted += 1
            summary.count(record["status"])
            summary.cost_usd = state["spent"]
            async with write_lock:
                with pred_path.open("a") as f:
                    f.write(json.dumps(record) + "\n")
            if on_record:
                on_record(record, state["spent"])

    try:
        await asyncio.gather(*(one(d, s) for d, s in todo))
    finally:
        await provider.aclose()
        meta["updated_at"] = _now()
        meta["run_dishes_hash"] = dishes_hash({r["dish_id"] for r in read_records(pred_path)})
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return summary

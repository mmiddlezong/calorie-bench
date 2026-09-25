import json

import pytest

from caloriebench import runner
from caloriebench.dataset import Dish
from caloriebench.providers.base import Provider, ProviderError, ProviderResult, Usage


class FakeProvider(Provider):
    """Scripted provider: behavior[dish_index] -> 'ok' | 'error' | 'fatal' | 'refuse' | 'truncate' | 'garbage'."""

    calls: list[str] = []

    def __init__(self, spec, behavior=None, default="ok"):
        super().__init__(spec)
        self.behavior = behavior or {}
        self.default = default

    def build_request(self, image, media_type, prompt):
        return {}

    async def complete(self, image, media_type, prompt):
        idx = int(image.decode())
        FakeProvider.calls.append(idx)
        mode = self.behavior.get(idx, self.default)
        usage = Usage(input_tokens=1000, output_tokens=1000)
        if mode == "error":
            raise RuntimeError("503 Service Unavailable")
        if mode == "fatal":
            raise ProviderError("BadRequestError: invalid model")
        if mode == "refuse":
            return ProviderResult(text="", usage=usage, stop_reason="refusal", refused=True)
        if mode == "truncate":
            return ProviderResult(text='{"total_calo', usage=usage, stop_reason="max_tokens", truncated=True)
        if mode == "garbage":
            return ProviderResult(text="I think it's a salad.", usage=usage, stop_reason="end_turn")
        return ProviderResult(text=json.dumps({"total_calories": 100 + idx}), usage=usage, stop_reason="end_turn")


@pytest.fixture
def dishes(dish_factory, monkeypatch):
    monkeypatch.setattr(Dish, "load_image", lambda self: str(self.index).encode())
    return [dish_factory(i, 100.0 + i) for i in range(6)]


@pytest.fixture
def use_fake(monkeypatch):
    FakeProvider.calls = []

    def install(**kw):
        FakeProvider.calls = []
        monkeypatch.setattr(runner, "make_provider", lambda spec: FakeProvider(spec, **kw))

    return install


async def test_statuses_and_resume(tmp_path, spec_factory, dishes, use_fake):
    spec = spec_factory()
    use_fake(behavior={1: "error", 2: "refuse", 3: "truncate", 4: "garbage"})
    s = await runner.run_model(spec, dishes, concurrency=2, results_dir=tmp_path)
    assert s.statuses == {"ok": 2, "api_error": 1, "refusal": 1, "truncated": 1, "parse_error": 1}
    # cost: 1000 in * $2/M + 1000 out * $10/M = $0.012 per completed request (5 of them)
    assert s.cost_usd == pytest.approx(5 * 0.012)

    use_fake()  # everything succeeds now
    s2 = await runner.run_model(spec, dishes, concurrency=2, results_dir=tmp_path)
    assert s2.skipped == 5 and s2.attempted == 1  # only the api_error dish is retried
    assert FakeProvider.calls == [1]

    recs = runner.read_records(runner.predictions_path(spec.id, tmp_path))
    assert len(recs) == 7
    meta = json.loads((runner.run_dir(spec.id, tmp_path) / "meta.json").read_text())
    assert meta["prompt_version"] == "v1" and meta["request_config"]["model"] == spec.model


async def test_budget_cap_stops_early(tmp_path, spec_factory, dishes, use_fake):
    spec = spec_factory()  # estimate ≈ $0.0137/request
    use_fake()
    s = await runner.run_model(spec, dishes, concurrency=1, max_cost=0.03, results_dir=tmp_path)
    assert s.aborted and "budget" in s.aborted
    assert s.attempted == 2
    assert s.cost_usd <= 0.03


async def test_consecutive_fatal_errors_abort(tmp_path, spec_factory, dishes, use_fake):
    spec = spec_factory()
    use_fake(default="fatal")
    s = await runner.run_model(spec, dishes, concurrency=1, results_dir=tmp_path)
    assert s.aborted and "non-retryable" in s.aborted
    assert s.attempted == runner.MAX_CONSECUTIVE_FATAL


async def test_config_change_requires_fresh(tmp_path, spec_factory, dishes, use_fake):
    use_fake()
    await runner.run_model(spec_factory(), dishes[:2], results_dir=tmp_path)
    changed = spec_factory(params={"effort": "low"})
    with pytest.raises(runner.RunConfigMismatch):
        await runner.run_model(changed, dishes[:2], results_dir=tmp_path)
    s = await runner.run_model(changed, dishes[:2], fresh=True, results_dir=tmp_path)
    assert s.attempted == 2
    backups = list(runner.run_dir(changed.id, tmp_path).glob("predictions.*.bak.jsonl"))
    assert len(backups) == 1


async def test_repeats(tmp_path, spec_factory, dishes, use_fake):
    use_fake()
    s = await runner.run_model(spec_factory(), dishes[:3], repeats=2, results_dir=tmp_path)
    assert s.planned == 6 and s.attempted == 6


def test_read_records_tolerates_torn_line(tmp_path):
    p = tmp_path / "p.jsonl"
    p.write_text('{"dish_id": "a", "status": "ok"}\n{"dish_id": "b", "sta')
    assert [r["dish_id"] for r in runner.read_records(p)] == ["a"]

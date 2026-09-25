import pytest

from caloriebench.config import load_registry
from caloriebench.cost import estimate_cost, usage_cost
from caloriebench.dataset import load_dishes
from caloriebench.prompt import PROMPT
from caloriebench.providers import make_provider
from caloriebench.providers.base import Usage

KNOWN_PROVIDERS = {"anthropic", "openai", "google", "xai", "openrouter", "openai_chat", "baseline"}


def test_registry_is_valid():
    reg = load_registry()
    assert reg.pricing_checked
    for m in reg.models:
        assert m.provider in KNOWN_PROVIDERS, m.id
        if not m.is_baseline:
            assert m.pricing.input > 0 and m.pricing.output > 0, f"{m.id} has no pricing"
            assert m.estimate.image_tokens > 0, f"{m.id} has no image token estimate"
            assert m.groups, f"{m.id} is in no group"


def test_every_model_builds_a_request():
    """Offline dry run: every configured model can construct a request."""
    image = b"\x89PNG fake"
    for m in load_registry().models:
        req = make_provider(m).build_request(image, "image/png", PROMPT)
        assert isinstance(req, dict), m.id


def test_group_selection():
    reg = load_registry()
    everything = reg.select(["all"])
    assert everything and all(not m.is_baseline for m in everything)
    assert {m.id for m in reg.select(["baselines"])} == {"train-mean", "train-median"}
    first = everything[0].id
    assert [m.id for m in reg.select([f"{first},{first}"])] == [first]
    with pytest.raises(KeyError):
        reg.select(["no-such-model"])


def test_usage_cost(spec_factory):
    spec = spec_factory()  # $2 in, $0.2 cached, $10 out
    u = Usage(input_tokens=1_000_000, cached_input_tokens=500_000, output_tokens=100_000)
    assert usage_cost(u, spec) == pytest.approx(0.5 * 2 + 0.5 * 0.2 + 0.1 * 10)


def test_estimate_range(spec_factory):
    est = estimate_cost(spec_factory(), 100)
    assert est.low_usd < est.expected_usd < est.high_usd
    # (330 + 400) in @ $2/M + (300 + 1000) out @ $10/M, x100
    assert est.expected_usd == pytest.approx(100 * (730 * 2 + 1300 * 10) / 1e6)


def test_manifest_prefix_is_calorie_balanced():
    dishes = load_dishes()
    assert len(dishes) == 100
    assert len({d.dish_id for d in dishes}) == 100
    assert sorted(d.calorie_stratum for d in dishes[:10]) == list(range(10))
    assert all(d.calories >= 30 for d in dishes)


def test_every_model_pins_reasoning_explicitly():
    """Policy: every model runs at high reasoning effort set explicitly in the request, so a
    change in a provider's default can never silently change results."""
    for m in load_registry().models:
        if m.is_baseline:
            continue
        req = make_provider(m).build_request(b"img", "image/png", PROMPT)
        if m.provider == "anthropic":
            effort = req.get("output_config", {}).get("effort")
            thinking = req.get("thinking", {})
            assert effort == "high" or (
                thinking.get("type") == "enabled" and 1024 <= thinking["budget_tokens"] < req["max_tokens"]
            ), m.id
        elif m.provider in ("openai", "xai"):
            assert req.get("reasoning") == {"effort": "high"}, m.id
        elif m.provider == "google":
            assert req["config"].get("thinking_config") == {"thinking_level": "HIGH"}, m.id
        elif m.provider == "openrouter":
            assert req["extra_body"]["reasoning"] in ({"effort": "high"}, {"enabled": True}), m.id
        else:
            raise AssertionError(f"no reasoning policy check for provider {m.provider}")

import pytest

from backend.intelligence.federation.aggregator import aggregate_reference_profile
from backend.intelligence.federation.cold_start import surge_vs_federation_range
from backend.intelligence.federation.local_params import FIELDS


def _submission(**overrides) -> dict:
    base = {field: 1.0 for field in FIELDS}
    base["samples"] = 100
    base.update(overrides)
    return base


def test_aggregate_reference_profile_has_exactly_the_11_documented_fields():
    """INT-10's Must-priority privacy invariant: zero raw rows, exactly the 11 aggregate fields."""
    profile = aggregate_reference_profile([_submission(), _submission(samples=50)])
    assert set(profile.keys()) == set(FIELDS)
    assert len(profile) == 11


def test_aggregate_reference_profile_is_sample_weighted_for_stable_fields():
    submissions = [_submission(volatility=0.0, samples=300), _submission(volatility=1.0, samples=100)]
    profile = aggregate_reference_profile(submissions)
    assert profile["volatility"] == pytest.approx(0.25)  # (0*300 + 1*100) / 400


def test_aggregate_reference_profile_uses_trimmed_mean_for_unstable_fields():
    submissions = [_submission(demand_trend=v, samples=100) for v in (-10.0, 0.1, 0.2, 0.3, 10.0)]
    profile = aggregate_reference_profile(submissions)
    assert -10.0 < profile["demand_trend"] < 10.0


def test_surge_vs_federation_range_flags_exceedance():
    result = surge_vs_federation_range(local_surge_ratio=3.0, federation_surge_multiplier=1.5)
    assert result["exceedsFederationRange"] is True

    result = surge_vs_federation_range(local_surge_ratio=1.2, federation_surge_multiplier=1.5)
    assert result["exceedsFederationRange"] is False

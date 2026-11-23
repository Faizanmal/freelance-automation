"""Pure privacy behavior for the operations metrics read model."""

from app.api.v1.ops import _rate_metric


def test_rate_metric_suppresses_cohorts_below_ten():
    result = _rate_metric("hiring", 2, 4, 4, "controlled test cohort")
    assert result["value"] is None
    assert result["numerator"] is None
    assert result["denominator"] is None
    assert result["sample_size"] == "<10; suppressed"
    assert result["status"] == "suppressed_small_cohort"


def test_rate_metric_publishes_rates_with_a_sufficient_cohort():
    result = _rate_metric("hiring", 5, 20, 12, "controlled test cohort")
    assert result["value"] == 0.25
    assert result["numerator"] == 5
    assert result["denominator"] == 20
    assert result["sample_size"] == 12
    assert result["status"] == "measured"

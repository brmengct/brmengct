import numpy as np
import pytest
from ab_testing.cuped import compute_cuped_metric


def test_cuped_preserves_mean():
    """Verify E[Y_cuped] == E[Y] (unbiasedness)."""
    rng = np.random.default_rng(123)
    x = rng.normal(50, 10, size=5000)
    y = 0.8 * x + rng.normal(10, 5, size=5000)

    y_cuped, _ = compute_cuped_metric(y, x)
    assert np.isclose(np.mean(y_cuped), np.mean(y), atol=1e-10)


def test_cuped_variance_reduction_matches_theory():
    """Verify Var(Y_cuped) == Var(Y) * (1 - r^2)."""
    rng = np.random.default_rng(456)
    x = rng.normal(100, 20, size=10_000)
    y = 0.7 * x + rng.normal(0, 15, size=10_000)

    y_cuped, _ = compute_cuped_metric(y, x)
    r = np.corrcoef(x, y)[0, 1]

    expected_var = np.var(y, ddof=1) * (1 - r**2)
    actual_var = np.var(y_cuped, ddof=1)
    assert np.isclose(actual_var, expected_var, rtol=1e-3)

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class ExperimentResult:
    ate_raw: float #average treatment effect
    se_raw: float #standard error
    p_value_raw: float
    ci_raw: tuple[float, float]
    ate_cuped: float #after controlling for pre-experiment data
    se_cuped: float
    p_value_cuped: float
    ci_cuped: tuple[float, float]
    theta: float #slope of regression etween outcome and pre-experiment variance
    correlation: float #r = cos(theta)
    variance_reduction_pct: float


def compute_cuped_metric(
    y: np.ndarray | pd.Series, x: np.ndarray | pd.Series
) -> tuple[np.ndarray, float]:
    """Computes the CUPED-adjusted metric: Y_cuped = Y - theta * (X - E[X]).

    theta is estimated across the pooled sample (Control + Treatment) to ensure
    the estimator remains strictly unbiased.
    """
    y_arr = np.asarray(y, dtype=float)
    x_arr = np.asarray(x, dtype=float)

    # Calculate pooled covariance and variance
    cov_xy = np.cov(x_arr, y_arr, ddof=1)[0, 1]
    var_x = np.var(x_arr, ddof=1)

    if var_x == 0:
        raise ValueError("Pre-experiment covariate X has zero variance.")

    theta = cov_xy / var_x
    x_mean = np.mean(x_arr)

    y_cuped = y_arr - theta * (x_arr - x_mean)
    return y_cuped, float(theta)


def analyze_ab_test(
    df: pd.DataFrame,
    group_col: str = "group",
    y_col: str = "post_spend",
    x_col: str = "pre_spend",
    control_label: str = "control",
    treatment_label: str = "treatment",
    alpha: float = 0.05,
) -> ExperimentResult:
    """Runs both a standard Welch's t-test and a CUPED-adjusted t-test on an A/B dataset."""
    y_cuped, theta = compute_cuped_metric(df[y_col], df[x_col])
    df = df.copy()
    df["y_cuped"] = y_cuped

    ctrl = df[df[group_col] == control_label]
    trt = df[df[group_col] == treatment_label]

    def _run_ttest(trt_vals: np.ndarray, ctrl_vals: np.ndarray):
        ate = float(np.mean(trt_vals) - np.mean(ctrl_vals))
        se = float(
            np.sqrt(
                np.var(trt_vals, ddof=1) / len(trt_vals)
                + np.var(ctrl_vals, ddof=1) / len(ctrl_vals)
            )
        )
        _, p_val = stats.ttest_ind(trt_vals, ctrl_vals, equal_var=False)
        z_crit = stats.norm.ppf(1 - alpha / 2)
        ci = (ate - z_crit * se, ate + z_crit * se)
        return ate, se, float(p_val), ci

    # 1. Raw A/B Test Results
    ate_raw, se_raw, p_raw, ci_raw = _run_ttest(
        trt[y_col].values, ctrl[y_col].values
    )

    # 2. CUPED-Adjusted A/B Test Results
    ate_cuped, se_cuped, p_cuped, ci_cuped = _run_ttest(
        trt["y_cuped"].values, ctrl["y_cuped"].values
    )

    # 3. Diagnostic Metrics
    corr = float(np.corrcoef(df[x_col], df[y_col])[0, 1])
    var_raw = np.var(df[y_col], ddof=1)
    var_cuped = np.var(df["y_cuped"], ddof=1)
    var_reduction = (1.0 - (var_cuped / var_raw)) * 100.0

    return ExperimentResult(
        ate_raw=ate_raw,
        se_raw=se_raw,
        p_value_raw=p_raw,
        ci_raw=ci_raw,
        ate_cuped=ate_cuped,
        se_cuped=se_cuped,
        p_value_cuped=p_cuped,
        ci_cuped=ci_cuped,
        theta=theta,
        correlation=corr,
        variance_reduction_pct=var_reduction,
    )

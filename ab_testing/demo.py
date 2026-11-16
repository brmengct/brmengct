import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ab_testing.cuped import analyze_ab_test, compute_cuped_metric


def generate_ab_data(
    n_users: int = 10_000,
    true_lift: float = 1.50,
    seed: int = 42,
) -> pd.DataFrame:
    """Simulates user-level pre/post spend with heavy right-skew and r ~ 0.72."""
    rng = np.random.default_rng(seed)

    # Random 50/50 split
    group = rng.choice(["control", "treatment"], size=n_users)

    # Baseline user propensity (log-normal spend habits)
    baseline_habit = rng.lognormal(mean=3.5, sigma=0.8, size=n_users)

    # Pre-experiment spend (X)
    pre_spend = baseline_habit + rng.normal(0, 10, size=n_users)
    pre_spend = np.clip(pre_spend, 0, None)

    # Post-experiment spend (Y): correlated with baseline habit + true treatment lift
    noise = rng.normal(0, 22, size=n_users)
    treatment_effect = np.where(group == "treatment", true_lift, 0.0)
    post_spend = baseline_habit + treatment_effect + noise
    post_spend = np.clip(post_spend, 0, None)

    return pd.DataFrame({
        "user_id": np.arange(1, n_users + 1),
        "group": group,
        "pre_spend": pre_spend,
        "post_spend": post_spend,
    })


if __name__ == "__main__":
    df = generate_ab_data(n_users=10_000, true_lift=1.50)
    res = analyze_ab_test(df)

    print("=== A/B TEST COMPARISON: RAW vs. CUPED ===")
    print(f"Pre/Post Correlation (r) : {res.correlation:.4f}")
    print(f"Theoretical Var Reduction: {(res.correlation**2)*100:.2f}%")
    print(f"Realized Var Reduction   : {res.variance_reduction_pct:.2f}%")
    print(f"Optimal Theta            : {res.theta:.4f}\n")

    print(
        f"[RAW]   Lift: ${res.ate_raw:.2f} | SE: {res.se_raw:.3f} | "
        f"p-value: {res.p_value_raw:.4f} | 95% CI: (${res.ci_raw[0]:.2f}, ${res.ci_raw[1]:.2f})"
    )
    print(
        f"[CUPED] Lift: ${res.ate_cuped:.2f} | SE: {res.se_cuped:.3f} | "
        f"p-value: {res.p_value_cuped:.4f} | 95% CI: (${res.ci_cuped[0]:.2f}, ${res.ci_cuped[1]:.2f})"
    )

    # Visualize Confidence Interval Shrinkage
    fig, ax = plt.subplots(figsize=(8, 3.8))
    methods = ["CUPED Adjusted", "Standard A/B (Raw)"]
    ates = [res.ate_cuped, res.ate_raw]
    errors = [1.96 * res.se_cuped, 1.96 * res.se_raw]
    colors = ["#1b9e77", "#7570b3"]

    ax.errorbar(
        ates,
        methods,
        xerr=errors,
        fmt="o",
        color="black",
        ecolor=colors,
        elinewidth=3,
        capsize=6,
    )
    ax.axvline(0, color="red", linestyle="--", linewidth=1.2, label="No Effect ($0)")
    ax.axvline(1.50, color="gray", linestyle=":", linewidth=1.2, label="True Lift ($1.50)")
    ax.set_xlabel("Estimated Average Treatment Effect ($ Spend)", fontweight="bold")
    ax.set_title("CUPED Variance Reduction: 95% Confidence Interval Comparison", fontweight="bold")
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig("cuped_ci_comparison.png", dpi=150)
    plt.show()

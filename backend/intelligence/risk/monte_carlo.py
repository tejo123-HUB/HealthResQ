"""A single point forecast fed through `project_stock`/`first_stockout_day` yields exactly one
deterministic severity label — useful, but silent about how much that label could plausibly move
if the actual demand deviates from the point forecast the way it historically has. This module
bootstraps historical residuals onto the point forecast to build many plausible demand trajectories
and reports the distribution of stockout outcomes across them, rather than just the one outcome.

Determinism: randomness is confined to the required `seed` argument, threaded through a single
`numpy.random.default_rng(seed)` — the same `seed` and inputs always reproduce the same distribution."""

import numpy as np

from backend.intelligence.risk.stockout import first_stockout_day, project_stock


def simulate_stockout_distribution(
    current_stock: float,
    daily_demand_point: np.ndarray,
    residuals: np.ndarray,
    *,
    horizon_days: int,
    seed: int,
    n_simulations: int = 1000,
) -> dict:
    """Bootstraps `residuals` onto `daily_demand_point` to build `n_simulations` demand
    trajectories, projects stock for each with the existing `project_stock`/`first_stockout_day`
    functions, and returns the distribution of first-stockout-day across runs.

    The "within N days" probabilities are computed against whichever of the first `min(N,
    horizon_days)` days are actually simulated — e.g. with `horizon_days=7`,
    `probabilityStockoutWithin14Days` reflects stockouts within those 7 days rather than 14, since
    there is no day 8-14 to have stocked out on.
    """
    rng = np.random.default_rng(seed)
    stockout_days: list[int | None] = []

    for _ in range(n_simulations):
        sampled_residuals = rng.choice(residuals, size=horizon_days, replace=True)
        simulated_demand = np.maximum(0, daily_demand_point + sampled_residuals)
        projected = project_stock(current_stock, np.zeros(horizon_days), simulated_demand)
        stockout_days.append(first_stockout_day(projected))

    def probability_within(n_days: int) -> float:
        cutoff = min(n_days, horizon_days)
        hits = sum(1 for day in stockout_days if day is not None and day <= cutoff)
        return hits / n_simulations

    # None ("never stocks out within the horizon") sorts as worse than any finite day, so it's
    # represented as +inf for the median: a median landing on a "never" run correctly yields None.
    orderable_days = np.array([day if day is not None else np.inf for day in stockout_days])
    median = np.median(orderable_days)
    median_stockout_day = None if np.isinf(median) else int(round(median))

    return {
        "probabilityStockoutWithin3Days": probability_within(3),
        "probabilityStockoutWithin7Days": probability_within(7),
        "probabilityStockoutWithin14Days": probability_within(14),
        "medianStockoutDay": median_stockout_day,
        "simulationsRun": n_simulations,
    }

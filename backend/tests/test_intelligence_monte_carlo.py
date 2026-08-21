import numpy as np

from backend.intelligence.risk.monte_carlo import simulate_stockout_distribution


def test_same_seed_is_byte_identical():
    daily_demand_point = np.full(10, 20.0)
    residuals = np.array([-5.0, -2.0, 0.0, 2.0, 5.0])

    first = simulate_stockout_distribution(
        current_stock=100, daily_demand_point=daily_demand_point, residuals=residuals,
        horizon_days=10, seed=42, n_simulations=200,
    )
    second = simulate_stockout_distribution(
        current_stock=100, daily_demand_point=daily_demand_point, residuals=residuals,
        horizon_days=10, seed=42, n_simulations=200,
    )
    assert first == second


def test_different_seeds_can_produce_different_results():
    # Demand hovers right at the stockout boundary, with noisy residuals, so which bootstrap
    # draws land above/below zero stock varies run to run.
    daily_demand_point = np.full(10, 10.0)
    residuals = np.array([-8.0, -4.0, 0.0, 4.0, 8.0, 12.0])

    results = [
        simulate_stockout_distribution(
            current_stock=100, daily_demand_point=daily_demand_point, residuals=residuals,
            horizon_days=10, seed=seed, n_simulations=200,
        )
        for seed in range(20)
    ]
    assert len(set(tuple(sorted(r.items())) for r in results)) > 1


def test_zero_stock_with_positive_demand_always_stocks_out_early():
    daily_demand_point = np.full(5, 10.0)
    residuals = np.array([0.0])  # no noise needed: demand is strictly positive every day

    result = simulate_stockout_distribution(
        current_stock=0, daily_demand_point=daily_demand_point, residuals=residuals,
        horizon_days=5, seed=1, n_simulations=50,
    )
    assert result["probabilityStockoutWithin3Days"] == 1.0
    assert result["medianStockoutDay"] == 1


def test_huge_stock_with_near_zero_demand_never_stocks_out():
    daily_demand_point = np.full(14, 0.0)
    residuals = np.array([0.0])

    result = simulate_stockout_distribution(
        current_stock=1_000_000, daily_demand_point=daily_demand_point, residuals=residuals,
        horizon_days=14, seed=7, n_simulations=50,
    )
    assert result["probabilityStockoutWithin3Days"] == 0.0
    assert result["probabilityStockoutWithin7Days"] == 0.0
    assert result["probabilityStockoutWithin14Days"] == 0.0
    assert result["medianStockoutDay"] is None

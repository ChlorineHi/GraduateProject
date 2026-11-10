"""Checks for expected error reduction (method name: eer)."""

import numpy as np
import pytest

from urbannoise.assignment import AgentView, allocate
from urbannoise.information_gain import (
    eer_matrix_from_uncertainty,
    eer_pair_score,
    eer_pair_scores_from_observations,
    expected_error_drops,
    uncertainty_to_variance_proxy,
)
from urbannoise.predictors import predict_idw


def test_score_ignores_hidden_noise_truth_when_observations_are_fixed():
    obs = {
        "x": np.array([0.0, 3.0]),
        "y": np.array([0.0, 0.0]),
        "db": np.array([45.0, 72.0]),
        "slot": np.array([1, 1]),
        "grid": np.array([0, 3]),
    }
    queries = np.array([[float(x), 0.0] for x in range(4)])
    reach = np.array([[0.40, 0.55, 0.70, 0.35]])
    accept = np.array([0.8])
    quality = np.array([0.9])
    cost = np.array([0.4])
    kwargs = dict(
        obs=obs,
        queries=queries,
        now_slot=4,
        accept=accept,
        quality=quality,
        cost=cost,
        reach=reach,
        width=4,
        lam=0.35,
        min_reach=0.22,
    )
    future_low = np.full((8, 4), 30.0)
    future_high = np.full((8, 4), 110.0)
    future_high[4:] = 125.0
    scored_low = eer_pair_scores_from_observations(**kwargs, noise_field=future_low)
    future_low[:] = -25.0
    scored_mutated = eer_pair_scores_from_observations(**kwargs, noise_field=future_low)
    scored_high = eer_pair_scores_from_observations(**kwargs, noise_field=future_high)
    scored_other_shape = eer_pair_scores_from_observations(**kwargs, noise_field=np.arange(3.0))
    assert scored_low.shape == (1, 4)
    assert np.allclose(scored_low, scored_high)
    assert np.allclose(scored_low, scored_mutated)
    assert np.allclose(scored_low, scored_other_shape)

    _mean, std = predict_idw(obs, queries, 4)
    std = np.asarray(std, dtype=np.float64).reshape(-1)
    variance = np.square(np.where(np.isfinite(std), np.maximum(std, 0.0), 0.0))
    drops = expected_error_drops(variance, width=4)
    manual = np.array(
        [
            eer_pair_score(float(reach[0, j]), 0.8, 0.9, float(drops[j]), 0.4, 0.35)
            for j in range(4)
        ]
    )
    assert np.allclose(scored_low[0], manual)

    flat_obs = dict(obs)
    flat_obs["db"] = np.array([55.0, 55.0])
    scored_flat = eer_pair_scores_from_observations(**{**kwargs, "obs": flat_obs}, noise_field=future_high)
    assert not np.allclose(scored_low, scored_flat)


def test_unreachable_agent_not_selected_when_reachable_alternative_exists():
    agents = [
        AgentView("far", "human", 1.0, 0.1, True, 1.0, loc=0),
        AgentView("near", "human", 1.0, 0.1, True, 1.0, loc=7),
    ]
    grids = np.array([0, 7])
    # Value would favor the low-reach cell. eer must not follow that when reach is below the gate.
    values = np.array([10.0, 0.2])
    unc = np.array([10.0, 1.0])
    dup = np.array([0.0, 0.0])
    reach = np.array(
        [
            [0.21, 0.0],
            [0.0, 0.80],
        ]
    )
    result = allocate(
        "eer",
        agents,
        grids,
        values,
        unc,
        dup,
        reach,
        width=8,
        radius=1,
        budget=5.0,
        cap=1,
        rng=np.random.default_rng(0),
        min_reach=0.22,
    )
    assert len(result.assignments) == 1
    chosen = result.assignments[0]
    assert chosen.agent == 1
    assert chosen.grid == 7
    assert chosen.reach == pytest.approx(0.80)
    drops = expected_error_drops(
        uncertainty_to_variance_proxy(unc),
        width=8,
        grid_ids=grids,
        duplicate=dup,
    )
    reachable_score = eer_pair_score(0.80, 1.0, 1.0, float(drops[1]), 0.1, 0.35)
    blocked_if_ungated = eer_pair_score(0.21, 1.0, 1.0, float(drops[0]), 0.1, 0.35)
    assert chosen.score == pytest.approx(reachable_score)
    assert blocked_if_ungated > reachable_score
    matrix = eer_matrix_from_uncertainty(
        unc,
        dup,
        reach,
        accept=np.array([1.0, 1.0]),
        quality=np.array([1.0, 1.0]),
        cost=np.array([0.1, 0.1]),
        grids=grids,
        width=8,
        lam=0.35,
        min_reach=0.22,
    )
    assert matrix[0, 0] < 0.0
    assert matrix[1, 1] == pytest.approx(chosen.score)
    assert all(item.agent != 0 for item in result.assignments)


def test_budget_zero_assigns_nothing():
    agents = [AgentView("H", "human", 1.0, 0.1, True, 1.0, loc=0)]
    grids = np.array([0])
    values = np.array([2.0])
    unc = np.array([2.0])
    dup = np.array([0.0])
    reach = np.array([[0.9]])
    rng = np.random.default_rng(0)
    blocked = allocate("eer", agents, grids, values, unc, dup, reach, 4, 2, 0.0, 2, rng, min_reach=0.22)
    assert blocked.assignments == []
    allowed = allocate("eer", agents, grids, values, unc, dup, reach, 4, 2, 5.0, 2, rng, min_reach=0.22)
    assert len(allowed.assignments) == 1


def test_duplicate_cell_is_penalized():
    # Closed form for two adjacent cells. rho^2 = exp(-(d/ell)^2) = exp(-0.16) when d=1 and ell=2.5.
    rho2 = float(np.exp(-0.16))
    closed = expected_error_drops(np.array([4.0, 1.0]), width=4, grid_ids=np.array([0, 1]))
    assert closed[0] == pytest.approx(0.8 * (4.0 + rho2 * 1.0))
    assert closed[1] == pytest.approx(0.5 * (rho2 * 4.0 + 1.0))

    agents = [AgentView("H", "human", 1.0, 0.1, True, 1.0, loc=0)]
    grids = np.array([0, 1])
    values = np.array([0.1, 8.0])
    unc = np.array([1.5, 3.0])
    dup = np.array([0.0, 2.0])
    reach = np.array([[0.9, 0.9]])
    raw = expected_error_drops(
        uncertainty_to_variance_proxy(unc),
        width=4,
        grid_ids=grids,
        duplicate=np.zeros(2),
    )
    penalized = expected_error_drops(
        uncertainty_to_variance_proxy(unc),
        width=4,
        grid_ids=grids,
        duplicate=dup,
    )
    assert raw[1] > raw[0]
    assert penalized[0] > penalized[1]
    result = allocate(
        "eer",
        agents,
        grids,
        values,
        unc,
        dup,
        reach,
        width=4,
        radius=3,
        budget=5.0,
        cap=1,
        rng=np.random.default_rng(1),
        min_reach=0.22,
    )
    assert len(result.assignments) == 1
    assert result.assignments[0].grid == 0
    expect = eer_pair_score(0.9, 1.0, 1.0, float(penalized[0]), 0.1, 0.35)
    assert result.assignments[0].score == pytest.approx(expect)
    assert result.assignments[0].score > eer_pair_score(0.9, 1.0, 1.0, float(penalized[1]), 0.1, 0.35)

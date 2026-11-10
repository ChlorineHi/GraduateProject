import copy

import numpy as np
import pytest

from urbannoise.assignment import AgentView, allocate
from urbannoise.experiment import (
    FAIR_PROTOCOL,
    METHOD_LABELS,
    EpisodeConfig,
    _plan_slot,
    algorithm_rng,
    execution_outcome,
    initial_observations,
    observation_hash,
    run_episode,
    run_suite,
    step_campaign,
)
from urbannoise.predictors import ObsSet
from urbannoise.protocol import environment_uniform, precompute_environment_events
from urbannoise.world import build_world


def _plan_signature(plans: list[dict]) -> list[tuple]:
    return [(int(item["agent"]), int(item["grid"]), float(item["score"]), float(item["reach"])) for item in plans]


def test_two_methods_share_initial_observations_and_cell_outcomes():
    env_seed = 21
    world = build_world(
        seed=env_seed,
        height=8,
        width=8,
        n_days=2,
        slots_per_day=6,
        n_human=5,
        n_machine=1,
        scenario="regular",
        prior_samples=6,
        missing_rate=0.0,
        accept_human=1.0,
        accept_machine=1.0,
        offline_fraction=0.0,
    )
    cfg = EpisodeConfig(lead=1, per_slot_cap=2)
    nearest = run_episode(world, "nearest", 5, env_seed, cfg)
    other = run_episode(world, "random_reach", 5, env_seed, cfg)
    shared_prior = observation_hash(initial_observations(world, env_seed))
    assert nearest["initial_obs_hash"] == other["initial_obs_hash"] == shared_prior
    assert nearest["protocol"] == other["protocol"] == FAIR_PROTOCOL
    assert nearest["env_seed"] == other["env_seed"] == env_seed

    slot = int(world.horizon[0])
    chosen = None
    for index, agent in enumerate(world.agents):
        loc = int(agent.traj[slot])
        if loc < 0 or not agent.online:
            continue
        draw = environment_uniform(env_seed, agent.name, slot, "accept")
        if draw < agent.accept:
            chosen = (index, agent, loc, draw)
            break
    assert chosen is not None
    index, agent, grid, draw = chosen
    events = precompute_environment_events(world, env_seed)
    assert events.uniform(agent.name, slot, "accept") == pytest.approx(draw)

    # Exploring with the algorithm stream must not move the environment draws.
    explorer = algorithm_rng(env_seed, "random_reach")
    explorer.random(10_000)
    assert environment_uniform(env_seed, agent.name, slot, "accept") == pytest.approx(draw)

    plan = [
        {
            "slot": slot,
            "decision_slot": slot - 1,
            "agent": index,
            "grid": grid,
            "cost": float(agent.cost),
            "reach": 1.0,
            "score": 1.0,
            "value": 1.0,
            "context": None,
            "unc_norm": 0.5,
            "done": False,
            "success": False,
        }
    ]
    held = EpisodeConfig(lead=1, per_slot_cap=2, replan=False)
    first = step_campaign(
        world,
        ObsSet.empty(),
        copy.deepcopy(plan),
        slot,
        10.0,
        "nearest",
        10.0,
        held,
        algorithm_rng(env_seed, "nearest"),
        env_seed=env_seed,
    )
    second = step_campaign(
        world,
        ObsSet.empty(),
        copy.deepcopy(plan),
        slot,
        10.0,
        "greedy_reach",
        10.0,
        held,
        algorithm_rng(env_seed, "greedy_reach"),
        env_seed=env_seed,
    )
    left, right = first["executed"][0], second["executed"][0]
    assert left["reason"] == right["reason"] == "success"
    assert left["grid"] == right["grid"] == grid
    assert left["accept_draw"] == pytest.approx(right["accept_draw"]) == pytest.approx(draw)
    assert left["level_db"] == pytest.approx(right["level_db"])
    direct = execution_outcome(world, agent, slot, grid, env_seed)
    assert direct["success"] is True
    assert direct["level_db"] == pytest.approx(left["level_db"])
    assert direct["accept_draw"] == pytest.approx(draw)


def test_future_truth_does_not_change_decision_when_observations_unchanged():
    world = build_world(
        seed=11,
        height=8,
        width=8,
        n_days=2,
        slots_per_day=8,
        n_human=6,
        n_machine=1,
        scenario="regular",
        prior_samples=6,
    )
    env_seed = 11
    obs = initial_observations(world, env_seed)
    obs_hash = observation_hash(obs)
    decision_slot = int(world.horizon[0])
    lead = 2
    target = decision_slot + lead
    cfg = EpisodeConfig(lead=lead, per_slot_cap=3)
    methods = ["nearest", "nearest_reach", "random_reach", "greedy_reach", "mupsa"]

    def decide(method: str) -> list[dict]:
        return _plan_slot(
            world,
            obs,
            decision_slot,
            target,
            lead,
            method,
            12.0,
            cfg,
            algorithm_rng(env_seed, method),
            None,
            12.0,
        )

    before = {method: _plan_signature(decide(method)) for method in methods}
    assert any(before.values())
    future = world.laeq[decision_slot + 1 :].copy()
    world.laeq[decision_slot + 1 :] = np.rot90(future, k=1, axes=(1, 2)) + 33.0
    assert not np.allclose(world.laeq[target], future[target - (decision_slot + 1)])
    assert observation_hash(obs) == obs_hash
    after = {method: _plan_signature(decide(method)) for method in methods}
    assert after == before


def test_current_position_nearest_stays_and_reach_baselines_use_reach():
    agents = [
        AgentView("near_now", "human", 1.0, 1.0, True, 1.0, loc=0),
        AgentView("reachable_later", "human", 1.0, 1.0, True, 1.0, loc=8),
    ]
    grids = np.array([1])
    values = np.array([2.0])
    unc = np.array([1.0])
    dup = np.array([0.0])
    reach = np.array([[0.05], [0.91]])
    common = dict(
        agents=agents,
        grids=grids,
        values=values,
        unc_norm=unc,
        duplicate=dup,
        reach=reach,
        width=4,
        radius=3,
        budget=5,
        cap=1,
        min_reach=0.22,
    )
    current = allocate("nearest", rng=np.random.default_rng(0), **common)
    aware = allocate("nearest_reach", rng=np.random.default_rng(0), **common)
    constrained = allocate("random_reach", rng=np.random.default_rng(1), **common)
    greedy = allocate("greedy_reach", rng=np.random.default_rng(0), **common)
    assert current.assignments[0].agent == 0
    assert aware.assignments[0].agent == 1
    assert constrained.assignments[0].agent == 1
    assert greedy.assignments[0].agent == 1
    assert METHOD_LABELS["nearest"] == "Current-position nearest"
    assert METHOD_LABELS["nearest_reach"] == "Reachability-aware nearest"
    assert METHOD_LABELS["random_reach"] == "Reachability-constrained random"
    assert METHOD_LABELS["greedy_reach"] == "Reachability-aware greedy"


def test_run_suite_uses_one_environment_seed_per_method(tmp_path):
    payload = run_suite(
        {
            "grid": 6,
            "n_days": 2,
            "slots_per_day": 4,
            "n_human": 3,
            "n_machine": 1,
            "prior_samples": 4,
            "budgets": [3],
            "seeds": [2],
            "methods": ["nearest", "random_reach", "mupsa"],
            "scenarios": ["regular"],
            "ablation": False,
            "robustness": False,
            "model_reports": False,
            "train_bandit": False,
            "lead": 1,
            "per_slot_cap": 2,
        },
        tmp_path,
    )
    rows = [row for row in payload["rows"] if row["family"] == "main"]
    assert payload["protocol_name"] == FAIR_PROTOCOL
    assert {row["method"] for row in rows} == {"nearest", "random_reach", "mupsa"}
    assert {row["seed"] for row in rows} == {2}
    assert len({row["initial_obs_hash"] for row in rows}) == 1

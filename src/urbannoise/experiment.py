"""Closed-loop sampling experiments.

Ground truth is read only when a simulated participant successfully executes a sample,
and again when metrics are computed. Assignment and predictors receive observations and
past trajectories only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from urbannoise.acoustics import validate_distribution
from urbannoise.assignment import DEFAULT_WEIGHTS, AgentView, LinUCB, allocate
from urbannoise.predictors import (
    ObsSet,
    cell_features,
    combine_value,
    fit_mobility,
    grid_queries,
    interval_stats,
    predict_gp,
    predict_idw,
    predict_rf,
    prediction_metrics,
)
from urbannoise.world import World, build_world, sample_measurement

METHOD_LABELS = {
    "random": "Random Assignment",
    "nearest": "Nearest Feasible Participant",
    "greedy": "Greedy Coverage / Information",
    "uncertainty": "Uncertainty-Only Sampling",
    "min_cost": "Hungarian Min-Cost Matching",
    "mupsa": "MU-PSA (proposed)",
    "mupsa_constrained": "MU-PSA hard reach constraint",
    "mupsa_no_mobility": "MU-PSA w/o mobility prediction",
    "mupsa_no_uncertainty": "MU-PSA w/o uncertainty",
    "mupsa_no_coverage": "MU-PSA w/o coverage",
    "bandit": "LinUCB shortlist policy",
}


@dataclass
class EpisodeConfig:
    lead: int = 2
    radius: int | None = None
    per_slot_cap: int = 4
    weights: dict | None = None
    replan: bool = True
    min_reach: float = 0.22


def _trajectories(world: World) -> np.ndarray:
    return np.stack([agent.traj for agent in world.agents], axis=0)


def _views(world: World, slot: int) -> list[AgentView]:
    views = []
    for agent in world.agents:
        loc = int(agent.traj[slot]) if 0 <= slot < len(agent.traj) else -1
        views.append(
            AgentView(
                name=agent.name,
                kind=agent.kind,
                accept=agent.accept,
                cost=agent.cost,
                online=agent.online,
                quality=agent.quality,
                loc=loc,
            )
        )
    return views


def _reach_matrix(world: World, visible_until: int, target_slot: int, lead: int) -> np.ndarray:
    traj = _trajectories(world)
    fit = fit_mobility(traj, visible_until, world.slots_per_day, world.n_grids)
    reach = np.zeros((len(world.agents), world.n_grids), dtype=np.float64)
    tod = target_slot % world.slots_per_day
    for idx, agent in enumerate(world.agents):
        current = int(agent.traj[visible_until]) if visible_until >= 0 else -1
        dist = fit.distribution(idx, tod, current, lead)
        if dist.size < world.n_grids:
            padded = np.zeros(world.n_grids)
            padded[: dist.size] = dist
            dist = padded / max(padded.sum(), 1e-12)
        reach[idx] = validate_distribution(dist)
    return reach


def decision_context(world: World, obs: ObsSet, visible_until: int, target_slot: int, lead: int) -> dict:
    """Features available at a decision time. Independent of future ground truth."""
    queries = grid_queries(world.width, world.height)
    mu, std = predict_idw(
        obs.subset(visible_until),
        queries,
        target_slot,
        zones=world.zones,
        slots_per_day=world.slots_per_day,
    )
    features = cell_features(obs.subset(visible_until), world.width, world.height, target_slot, std)
    reach = _reach_matrix(world, visible_until, target_slot, lead)
    return {"mu": mu, "std": std, "features": features, "reach": reach, "queries": queries}


def _seed_prior(world: World, rng: np.random.Generator) -> ObsSet:
    obs = ObsSet.empty()
    history_end = world.horizon[0]
    coords = [(x, y) for y in range(world.height) for x in range(world.width)]
    take = min(world.prior_samples, len(coords))
    chosen = rng.choice(len(coords), size=take, replace=False)
    slots = rng.integers(0, max(1, history_end), size=take)
    for pick, slot in zip(chosen, slots):
        x, y = coords[int(pick)]
        grid = world.grid_id(x, y)
        level = sample_measurement(world, int(slot), grid, rng)
        obs.add(x, y, level, int(slot), grid)
    return obs


def _value_mode(method: str) -> str:
    if method in {"uncertainty"}:
        return "uncertainty"
    if method in {"mupsa_no_uncertainty"}:
        return "coverage"
    if method in {"mupsa_no_coverage"}:
        return "no_coverage"
    return "full"


def _plan_slot(
    world: World,
    obs: ObsSet,
    decision_slot: int,
    target_slot: int,
    lead: int,
    method: str,
    budget_left: float,
    cfg: EpisodeConfig,
    rng: np.random.Generator,
    bandit: LinUCB | None,
    initial_budget: float,
) -> list[dict]:
    ctx = decision_context(world, obs, decision_slot, target_slot, lead)
    weights = cfg.weights or DEFAULT_WEIGHTS
    values = combine_value(ctx["features"], weights, mode=_value_mode(method))
    grids = np.arange(world.n_grids)
    radius = cfg.radius if cfg.radius is not None else max(2, min(world.height, world.width) // 4)
    result = allocate(
        method=method if method != "mupsa_no_replan" else "mupsa",
        agents=_views(world, decision_slot),
        grids=grids,
        values=values,
        unc_norm=ctx["features"]["uncertainty_norm"],
        duplicate=ctx["features"]["duplicate"],
        reach=ctx["reach"],
        width=world.width,
        radius=radius,
        budget=budget_left,
        cap=cfg.per_slot_cap,
        rng=rng,
        weights=weights,
        min_reach=cfg.min_reach,
        bandit=bandit,
        budget_frac=budget_left / max(initial_budget, 1e-6),
        time_frac=target_slot / max(world.n_slots, 1),
    )
    plans = []
    for item in result.assignments:
        plans.append(
            {
                "slot": int(target_slot),
                "decision_slot": int(decision_slot),
                "agent": int(item.agent),
                "grid": int(item.grid),
                "cost": float(item.cost),
                "reach": float(item.reach),
                "score": float(item.score),
                "value": float(item.value),
                "context": None if item.context is None else item.context.copy(),
                "unc_norm": float(ctx["features"]["uncertainty_norm"][item.grid]),
                "done": False,
                "success": False,
            }
        )
    return plans


def step_campaign(
    world: World,
    obs: ObsSet,
    plans: list[dict],
    slot: int,
    budget_left: float,
    method: str,
    initial_budget: float,
    cfg: EpisodeConfig,
    rng: np.random.Generator,
    bandit: LinUCB | None = None,
    train_bandit: bool = False,
) -> dict:
    """Execute tasks due at `slot` and optionally schedule the slot `lead` steps ahead."""
    active_method = "mupsa" if method == "mupsa_no_replan" else method
    replan = cfg.replan and method != "mupsa_no_replan"
    queries = grid_queries(world.width, world.height)
    mu_before, _ = predict_idw(obs.subset(slot - 1), queries, slot, zones=world.zones, slots_per_day=world.slots_per_day)
    truth = world.laeq[slot].ravel()
    mae_before = float(np.mean(np.abs(mu_before - truth)))
    executed = []
    due = [item for item in plans if item["slot"] == slot and not item["done"]]
    for item in due:
        item["done"] = True
        agent = world.agents[item["agent"]]
        loc = int(agent.traj[slot]) if 0 <= slot < len(agent.traj) else -1
        reached = loc == item["grid"]
        if item.get("force_accept"):
            accepted = bool(agent.online)
        else:
            accepted = bool(agent.online and rng.random() < agent.accept)
        level = None
        reason = "success"
        if reached and accepted:
            sigma = world.sensor_sigma * (0.75 if agent.kind == "machine" else 1.0)
            level = sample_measurement(world, slot, item["grid"], rng, sigma=sigma)
            x, y = world.xy(item["grid"])
            obs.add(x, y, level, slot, item["grid"])
            item["success"] = True
        else:
            item["success"] = False
            if not agent.online:
                reason = "offline"
            elif not reached:
                reason = "not_at_target"
            else:
                reason = "rejected"
            if replan:
                budget_left += item["cost"]
        executed.append({**{k: v for k, v in item.items() if k != "context"}, "level_db": level, "reason": reason, "location": loc})
    mu_after, _ = predict_idw(obs.subset(slot), queries, slot, zones=world.zones, slots_per_day=world.slots_per_day)
    mae_after = float(np.mean(np.abs(mu_after - truth)))
    rewards = []
    if due:
        delta = mae_before - mae_after
        for item in due:
            reward = (1.0 if item["success"] else -0.25) + 0.2 * item["unc_norm"] - 0.05 * item["cost"]
            reward += 4.0 * delta / max(len(due), 1)
            rewards.append(reward)
            if train_bandit and bandit is not None and item.get("context") is not None:
                bandit.update(item["context"], reward)
    planned: list[dict] = []
    target = slot + cfg.lead
    if replan and target < world.horizon[1] and budget_left > 1e-9:
        planned = _plan_slot(world, obs, slot, target, cfg.lead, active_method, budget_left, cfg, rng, bandit, initial_budget)
        for item in planned:
            budget_left -= item["cost"]
        plans.extend(planned)
    return {
        "executed": executed,
        "planned": planned,
        "budget_left": budget_left,
        "mae_before": mae_before,
        "mae_after": mae_after,
        "reward_sum": float(sum(rewards)),
    }


def map_arrays(world: World, obs: ObsSet, slot: int) -> dict[str, np.ndarray]:
    queries = grid_queries(world.width, world.height)
    mu, std = predict_idw(obs.subset(slot), queries, slot, zones=world.zones, slots_per_day=world.slots_per_day)
    return {
        "prediction": mu.reshape(world.height, world.width),
        "uncertainty": std.reshape(world.height, world.width),
        "truth": world.laeq[slot],
    }


def run_episode(
    world: World,
    method: str,
    budget: float,
    seed: int,
    cfg: EpisodeConfig | None = None,
    bandit: LinUCB | None = None,
    train_bandit: bool = False,
) -> dict:
    cfg = cfg or EpisodeConfig()
    rng = np.random.default_rng(seed)
    obs = _seed_prior(world, rng)
    lead = cfg.lead
    start, end = world.horizon
    plans: list[dict] = []
    budget_left = float(budget)
    assigned = success = failed = 0
    spent = 0.0
    online_abs: list[float] = []
    reward_sum = 0.0
    queries = grid_queries(world.width, world.height)
    active_method = "mupsa" if method == "mupsa_no_replan" else method
    replan = cfg.replan and method != "mupsa_no_replan"

    if not replan:
        # One batch, using only information available at the first decision slot.
        cursor = budget_left
        t0 = start
        target = t0 + lead
        while target < end and cursor > 1e-9:
            batch = _plan_slot(world, obs, t0, target, lead, active_method, cursor, cfg, rng, bandit, budget)
            if not batch:
                target += 1
                continue
            plans.extend(batch)
            cursor -= sum(item["cost"] for item in batch)
            target += 1
        budget_left = cursor

    for slot in range(start, end):
        outcome = step_campaign(
            world, obs, plans, slot, budget_left, method, budget, cfg, rng, bandit, train_bandit
        )
        budget_left = outcome["budget_left"]
        online_abs.append(outcome["mae_after"])
        reward_sum += outcome["reward_sum"]
        for item in outcome["executed"]:
            assigned += 1
            if item["reason"] == "success":
                success += 1
                spent += item["cost"]
            else:
                failed += 1

    causal_err = []
    causal_sq = []
    unsampled_err = []
    sampled_grids = set(obs.grid)
    widths = []
    covers = []
    for slot in range(start, end):
        mu, std = predict_idw(obs.subset(slot), queries, slot, zones=world.zones, slots_per_day=world.slots_per_day)
        truth = world.laeq[slot].ravel()
        causal_err.append(np.abs(mu - truth))
        causal_sq.append((mu - truth) ** 2)
        mask = np.array([grid not in sampled_grids for grid in range(world.n_grids)])
        if mask.any():
            unsampled_err.append(np.abs(mu[mask] - truth[mask]))
        stats = interval_stats(truth, mu, std)
        widths.append(stats["mean_width"])
        covers.append(stats["coverage"])
    abs_err = np.concatenate(causal_err)
    sq_err = np.concatenate(causal_sq)
    unique_grids = {item["grid"] for item in plans if item["success"]}
    coverage = len(unique_grids) / world.n_grids
    reaches = [item["reach"] for item in plans if item["done"]]
    return {
        "method": method,
        "scenario": world.scenario,
        "seed": int(seed),
        "budget": float(budget),
        "mae_causal": float(np.mean(abs_err)),
        "rmse_causal": float(np.sqrt(np.mean(sq_err))),
        "mae_online": float(np.mean(online_abs)) if online_abs else float("nan"),
        "mae_unsampled": float(np.mean(np.concatenate(unsampled_err))) if unsampled_err else float("nan"),
        "coverage": float(coverage),
        "successful_tasks": int(success),
        "failed_tasks": int(failed),
        "assigned_tasks": int(assigned),
        "sampling_cost": float(spent),
        "interval_coverage": float(np.mean(covers)) if covers else float("nan"),
        "interval_width": float(np.mean(widths)) if widths else float("nan"),
        "mean_assigned_reach": float(np.mean(reaches)) if reaches else 0.0,
        "reward_sum": float(reward_sum),
        "observations": int(len(obs.db)),
    }


def evaluate_mobility(world: World) -> dict[str, float]:
    """Predict slots in the evaluation horizon without reading the target slot or anything after it."""
    traj = _trajectories(world)
    start, end = world.horizon
    top1 = []
    top3 = []
    nll = []
    brier = []
    for slot in range(start, end):
        fit = fit_mobility(traj, slot - 1, world.slots_per_day, world.n_grids)
        tod = slot % world.slots_per_day
        for idx in range(len(world.agents)):
            truth = int(traj[idx, slot])
            if truth < 0:
                continue
            current = int(traj[idx, slot - 1]) if slot - 1 >= 0 else -1
            dist = fit.distribution(idx, tod, current, 1)
            if dist.size < world.n_grids:
                padded = np.zeros(world.n_grids)
                padded[: dist.size] = dist
                dist = padded / max(padded.sum(), 1e-12)
            order = np.argsort(dist)[::-1]
            top1.append(int(order[0] == truth))
            top3.append(int(truth in order[:3]))
            prob = float(np.clip(dist[truth], 1e-12, 1.0))
            nll.append(-np.log(prob))
            onehot = np.zeros_like(dist)
            onehot[truth] = 1.0
            brier.append(float(np.sum((dist - onehot) ** 2)))
    def _mean(values: list[float]) -> float:
        return float(np.mean(values)) if values else float("nan")

    return {"top1": _mean(top1), "top3": _mean(top3), "nll": _mean(nll), "brier": _mean(brier), "events": len(top1)}


def compare_noise_models(world: World, seed: int = 0) -> dict:
    """Hold out observations and also score full-field reconstruction on synthetic truth."""
    rng = np.random.default_rng(seed)
    obs = _seed_prior(world, np.random.default_rng(seed + 17))
    # Additional random samples on the history day, then hide 30 percent.
    extra = ObsSet.empty()
    for item in zip(obs.x, obs.y, obs.db, obs.slot, obs.grid):
        extra.add(int(item[0]), int(item[1]), item[2], item[3], item[4])
    for _ in range(40):
        x = int(rng.integers(0, world.width))
        y = int(rng.integers(0, world.height))
        slot = int(rng.integers(0, world.horizon[0]))
        extra.add(x, y, sample_measurement(world, slot, world.grid_id(x, y), rng), slot, world.grid_id(x, y))
    n = len(extra.db)
    perm = rng.permutation(n)
    cut = max(8, int(n * 0.7))
    train_idx, test_idx = perm[:cut], perm[cut:]
    train = {
        "x": np.asarray(extra.x)[train_idx],
        "y": np.asarray(extra.y)[train_idx],
        "db": np.asarray(extra.db)[train_idx],
        "slot": np.asarray(extra.slot)[train_idx],
        "grid": np.asarray(extra.grid)[train_idx],
    }
    test_slots = np.asarray(extra.slot)[test_idx]
    y_true = np.asarray(extra.db)[test_idx]
    queries = np.column_stack([np.asarray(extra.x)[test_idx], np.asarray(extra.y)[test_idx]])
    slot_ref = int(np.median(test_slots))
    results = {}
    mu, std = predict_idw(train, queries, slot_ref, zones=world.zones, slots_per_day=world.slots_per_day)
    results["idw"] = {**prediction_metrics(y_true, mu), **interval_stats(y_true, mu, std), "backend": "idw"}
    mu, std, backend = predict_rf(train, queries, world.zones, slot_ref, world.slots_per_day, seed=seed)
    results["random_forest"] = {**prediction_metrics(y_true, mu), **interval_stats(y_true, mu, std), "backend": backend}
    mu, std, backend = predict_gp(train, queries, slot_ref)
    results["gaussian_process"] = {**prediction_metrics(y_true, mu), **interval_stats(y_true, mu, std), "backend": backend}
    # Full-field reference at one held-in time using IDW. Truth is used only as the metric target.
    field_slot = min(world.n_slots - 1, world.horizon[0] // 2)
    field_queries = grid_queries(world.width, world.height)
    mu, std = predict_idw(train, field_queries, field_slot, zones=world.zones, slots_per_day=world.slots_per_day)
    field = prediction_metrics(world.laeq[field_slot].ravel(), mu)
    field.update(interval_stats(world.laeq[field_slot].ravel(), mu, std))
    results["idw_full_field_history_slot"] = field
    results["protocol"] = {
        "holdout": "random observation holdout, 70/30, shared across models",
        "full_field": "synthetic truth at one history slot; not used to fit the model",
        "note": "Interval coverage is empirical. Tree std and IDW delta-method std are not claimed to be calibrated posteriors.",
    }
    return results


def mobility_variant_episode(world: World, variant: str, budget: float, seed: int) -> dict:
    mapping = {
        "no_history": "nearest",
        "current_distance": "nearest",
        "future_prediction": "mupsa",
        "prediction_with_probability_constraint": "mupsa_constrained",
    }
    if variant == "no_history":
        return run_episode(world, "random", budget, seed)
    return run_episode(world, mapping[variant], budget, seed)


def aggregate(rows: list[dict], keys: list[str]) -> list[dict]:
    buckets: dict[tuple, list[dict]] = {}
    for row in rows:
        buckets.setdefault(tuple(row[key] for key in keys), []).append(row)
    summary = []
    metrics = ["mae_causal", "rmse_causal", "mae_online", "mae_unsampled", "coverage", "successful_tasks", "sampling_cost", "mean_assigned_reach"]
    for group, items in buckets.items():
        record = {key: value for key, value in zip(keys, group)}
        record["n"] = len(items)
        for metric in metrics:
            values = np.array([item[metric] for item in items], dtype=np.float64)
            record[f"{metric}_mean"] = float(np.nanmean(values))
            record[f"{metric}_std"] = float(np.nanstd(values, ddof=0))
        summary.append(record)
    return summary


def run_suite(config: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    methods = config["methods"]
    scenarios = config.get("scenarios", ["regular"])
    seeds = config["seeds"]
    budgets = config["budgets"]
    lead = int(config.get("lead", 2))
    cap = int(config.get("per_slot_cap", 4))
    for scenario in scenarios:
        for seed in seeds:
            world = build_world(
                seed=int(seed),
                height=int(config["grid"]),
                width=int(config["grid"]),
                n_days=int(config.get("n_days", 2)),
                slots_per_day=int(config["slots_per_day"]),
                n_human=int(config["n_human"]),
                n_machine=int(config["n_machine"]),
                scenario=scenario,
                sensor_sigma=float(config.get("sensor_sigma", 1.5)),
                accept_human=float(config.get("accept_human", 0.72)),
                prior_samples=int(config.get("prior_samples", 24)),
                missing_rate=float(config.get("missing_rate", 0.04)),
            )
            for budget in budgets:
                for method in methods:
                    episode_seed = 10_000 + int(seed) * 100 + int(budget) + (sum(ord(ch) for ch in method) % 97)
                    result = run_episode(
                        world,
                        method,
                        float(budget),
                        episode_seed,
                        EpisodeConfig(lead=lead, per_slot_cap=cap),
                    )
                    result["family"] = "main"
                    rows.append(result)
    ablation_rows = []
    if config.get("ablation", False):
        ablations = ["mupsa", "mupsa_no_mobility", "mupsa_no_uncertainty", "mupsa_no_coverage", "mupsa_no_replan"]
        budget = float(config.get("ablation_budget", budgets[len(budgets) // 2]))
        for seed in seeds:
            world = build_world(
                seed=int(seed) + 50,
                height=int(config["grid"]),
                width=int(config["grid"]),
                n_days=int(config.get("n_days", 2)),
                slots_per_day=int(config["slots_per_day"]),
                n_human=int(config["n_human"]),
                n_machine=int(config["n_machine"]),
                scenario=config.get("ablation_scenario", scenarios[0]),
                prior_samples=int(config.get("prior_samples", 24)),
            )
            for method in ablations:
                result = run_episode(world, method, budget, 20_000 + int(seed) * 17 + sum(ord(ch) for ch in method))
                result["family"] = "ablation"
                result["budget"] = budget
                ablation_rows.append(result)
                rows.append(result)
    robust_rows = []
    if config.get("robustness", False):
        budget = float(budgets[len(budgets) // 2])
        variants = [
            {"name": "baseline_mix", "n_human": config["n_human"], "n_machine": config["n_machine"], "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
            {"name": "few_participants", "n_human": max(4, int(config["n_human"]) // 3), "n_machine": 1, "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
            {"name": "low_acceptance", "n_human": config["n_human"], "n_machine": config["n_machine"], "accept_human": 0.3, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
            {"name": "shift_mobility", "n_human": config["n_human"], "n_machine": config["n_machine"], "accept_human": 0.72, "scenario": "shift", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
            {"name": "noisy_sensors", "n_human": config["n_human"], "n_machine": config["n_machine"], "accept_human": 0.72, "scenario": "complex", "missing_rate": 0.04, "sensor_sigma": 4.0, "offline_fraction": 0.0},
            {"name": "missing_trajectories", "n_human": config["n_human"], "n_machine": config["n_machine"], "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.25, "sensor_sigma": 1.5, "offline_fraction": 0.0},
            {"name": "partial_offline", "n_human": config["n_human"], "n_machine": config["n_machine"], "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.4},
            {"name": "humans_only", "n_human": config["n_human"], "n_machine": 0, "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
            {"name": "machines_only", "n_human": 0, "n_machine": config["n_machine"], "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
        ]
        for variant in variants:
            for seed in seeds[: min(3, len(seeds))]:
                world = build_world(
                    seed=int(seed) + 90,
                    height=int(config["grid"]),
                    width=int(config["grid"]),
                    n_days=int(config.get("n_days", 2)),
                    slots_per_day=int(config["slots_per_day"]),
                    n_human=int(variant["n_human"]),
                    n_machine=int(variant["n_machine"]),
                    scenario=variant["scenario"],
                    accept_human=float(variant["accept_human"]),
                    missing_rate=float(variant["missing_rate"]),
                    sensor_sigma=float(variant["sensor_sigma"]),
                    offline_fraction=float(variant["offline_fraction"]),
                    prior_samples=int(config.get("prior_samples", 24)),
                )
                for method in ["nearest", "greedy", "mupsa"]:
                    result = run_episode(world, method, budget, 30_000 + int(seed) * 13 + sum(ord(ch) for ch in variant["name"] + method))
                    result["family"] = "robustness"
                    result["variant"] = variant["name"]
                    robust_rows.append(result)
                    rows.append(result)
    mobility_report = {}
    noise_report = {}
    if config.get("model_reports", True):
        probe = build_world(
            seed=int(seeds[0]),
            height=int(config["grid"]),
            width=int(config["grid"]),
            n_days=int(config.get("n_days", 2)),
            slots_per_day=int(config["slots_per_day"]),
            n_human=int(config["n_human"]),
            n_machine=int(config["n_machine"]),
            scenario=scenarios[0],
            prior_samples=int(config.get("prior_samples", 24)),
        )
        mobility_report = evaluate_mobility(probe)
        noise_report = compare_noise_models(probe, seed=int(seeds[0]))
    bandit_curve: list[float] = []
    bandit_eval: list[dict] = []
    if config.get("train_bandit", False):
        trainer = LinUCB(alpha=float(config.get("bandit_alpha", 0.75)))
        episodes = int(config.get("train_bandit_episodes", 8))
        for episode in range(episodes):
            world = build_world(
                seed=400 + episode,
                height=int(config["grid"]),
                width=int(config["grid"]),
                n_days=int(config.get("n_days", 2)),
                slots_per_day=int(config["slots_per_day"]),
                n_human=int(config["n_human"]),
                n_machine=int(config["n_machine"]),
                scenario="regular",
                prior_samples=int(config.get("prior_samples", 24)),
            )
            trained = run_episode(
                world,
                "bandit",
                float(budgets[len(budgets) // 2]),
                40_000 + episode,
                EpisodeConfig(lead=lead, per_slot_cap=cap),
                bandit=trainer,
                train_bandit=True,
            )
            bandit_curve.append(trained["reward_sum"])
        checkpoint = output_dir.parent / "checkpoints"
        checkpoint.mkdir(parents=True, exist_ok=True)
        (checkpoint / "linucb.json").write_text(json.dumps(trainer.to_dict()), encoding="utf-8")
        for seed in seeds:
            world = build_world(
                seed=800 + int(seed),
                height=int(config["grid"]),
                width=int(config["grid"]),
                n_days=int(config.get("n_days", 2)),
                slots_per_day=int(config["slots_per_day"]),
                n_human=int(config["n_human"]),
                n_machine=int(config["n_machine"]),
                scenario=scenarios[0],
                prior_samples=int(config.get("prior_samples", 24)),
            )
            # Frozen policy: train_bandit False. Test seeds are disjoint from 400+episode.
            result = run_episode(
                world,
                "bandit",
                float(budgets[len(budgets) // 2]),
                50_000 + int(seed),
                EpisodeConfig(lead=lead, per_slot_cap=cap),
                bandit=trainer,
                train_bandit=False,
            )
            result["family"] = "bandit_eval"
            bandit_eval.append(result)
            rows.append(result)
    summary = aggregate([row for row in rows if row.get("family") == "main"], ["scenario", "method", "budget"])
    payload = {
        "config": config,
        "rows": rows,
        "summary": summary,
        "ablation": ablation_rows,
        "robustness": robust_rows,
        "mobility": mobility_report,
        "noise_models": noise_report,
        "bandit_curve": bandit_curve,
        "bandit_eval": bandit_eval,
        "metric_definitions": {
            "mae_causal": "Mean absolute error of IDW predictions at each evaluation slot, using only observations with slot <= t, against the clean synthetic field.",
            "rmse_causal": "Root mean squared error under the same causal protocol.",
            "coverage": "Fraction of grids with at least one successful sample during the evaluation horizon.",
            "sampling_cost": "Sum of participant costs of successful samples. Rejected or missed tasks are refunded when replanning is enabled.",
            "interval_coverage": "Empirical frequency with which truth falls inside mean ± 1.96 predictive std. This checks the uncertainty, it does not prove calibration.",
        },
    }
    (output_dir / "results.json").write_text(json.dumps(payload), encoding="utf-8")
    _write_csv(output_dir / "results.csv", rows)
    _write_csv(output_dir / "summary.csv", summary)
    return payload


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys and not isinstance(row[key], (dict, list)):
                keys.append(key)
    lines = [",".join(keys)]
    for row in rows:
        values = []
        for key in keys:
            value = row.get(key, "")
            if isinstance(value, float):
                values.append(f"{value:.6f}")
            else:
                values.append(str(value).replace(",", ";"))
        lines.append(",".join(values))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_results(payload: dict, figure_dir: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei", "Droid Sans Fallback", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    figure_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    summary = payload.get("summary", [])
    if summary:
        scenarios = sorted({row["scenario"] for row in summary})
        for scenario in scenarios:
            subset = [row for row in summary if row["scenario"] == scenario]
            methods = sorted({row["method"] for row in subset})
            fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.8))
            for method in methods:
                rows = sorted([row for row in subset if row["method"] == method], key=lambda item: item["budget"])
                budgets = [row["budget"] for row in rows]
                axes[0].errorbar(budgets, [row["mae_causal_mean"] for row in rows], yerr=[row["mae_causal_std"] for row in rows], marker="o", label=method)
                axes[1].errorbar(budgets, [row["coverage_mean"] for row in rows], yerr=[row["coverage_std"] for row in rows], marker="o", label=method)
                axes[2].errorbar(budgets, [row["successful_tasks_mean"] for row in rows], yerr=[row["successful_tasks_std"] for row in rows], marker="o", label=method)
            axes[0].set_title("因果 MAE")
            axes[1].set_title("网格覆盖率")
            axes[2].set_title("成功采样次数")
            for axis in axes:
                axis.set_xlabel("预算")
                axis.grid(True, alpha=0.3)
            axes[2].legend(fontsize=7, loc="best")
            fig.suptitle(f"主实验 · 场景 {scenario}")
            fig.tight_layout()
            path = figure_dir / f"main_{scenario}.png"
            fig.savefig(path, dpi=140)
            plt.close(fig)
            written.append(str(path))
            fig, axis = plt.subplots(figsize=(6.2, 4.2))
            for method in methods:
                rows = sorted([row for row in subset if row["method"] == method], key=lambda item: item["sampling_cost_mean"])
                axis.plot([row["sampling_cost_mean"] for row in rows], [row["mae_causal_mean"] for row in rows], marker="o", label=method)
            axis.set_xlabel("成功采样成本")
            axis.set_ylabel("因果 MAE (dB)")
            axis.set_title(f"成本—误差 · {scenario}")
            axis.grid(True, alpha=0.3)
            axis.legend(fontsize=7)
            fig.tight_layout()
            path = figure_dir / f"cost_mae_{scenario}.png"
            fig.savefig(path, dpi=140)
            plt.close(fig)
            written.append(str(path))
    ablation = payload.get("ablation") or []
    if ablation:
        grouped: dict[str, list[float]] = {}
        for row in ablation:
            grouped.setdefault(row["method"], []).append(row["mae_causal"])
        labels = list(grouped)
        means = [float(np.mean(grouped[key])) for key in labels]
        stds = [float(np.std(grouped[key])) for key in labels]
        fig, axis = plt.subplots(figsize=(8.2, 4.0))
        axis.bar(range(len(labels)), means, yerr=stds, color="#3c6e71")
        axis.set_xticks(range(len(labels)), labels, rotation=20, ha="right")
        axis.set_ylabel("因果 MAE (dB)")
        axis.set_title("消融实验")
        axis.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        path = figure_dir / "ablation_mae.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))
    robust = payload.get("robustness") or []
    if robust:
        focus = [row for row in robust if row["method"] == "mupsa"]
        grouped = {}
        for row in focus:
            grouped.setdefault(row["variant"], []).append(row["mae_causal"])
        labels = list(grouped)
        fig, axis = plt.subplots(figsize=(8.4, 4.0))
        axis.bar(range(len(labels)), [float(np.mean(grouped[key])) for key in labels], color="#c4764a")
        axis.set_xticks(range(len(labels)), labels, rotation=22, ha="right")
        axis.set_ylabel("MU-PSA 因果 MAE (dB)")
        axis.set_title("鲁棒性设置")
        axis.grid(True, axis="y", alpha=0.3)
        fig.tight_layout()
        path = figure_dir / "robustness_mupsa.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))
    curve = payload.get("bandit_curve") or []
    if curve:
        fig, axis = plt.subplots(figsize=(6.2, 3.6))
        axis.plot(range(1, len(curve) + 1), curve, marker="o", color="#1f4e5f")
        axis.set_xlabel("训练回合")
        axis.set_ylabel("回合回报")
        axis.set_title("LinUCB 训练回报")
        axis.grid(True, alpha=0.3)
        fig.tight_layout()
        path = figure_dir / "bandit_reward.png"
        fig.savefig(path, dpi=140)
        plt.close(fig)
        written.append(str(path))
    return written


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    name = config.get("name", "run")
    output = Path(config.get("output_dir", f"experiments/results/{name}"))
    payload = run_suite(config, output)
    figures = plot_results(payload, Path(config.get("figure_dir", f"experiments/figures/{name}")))
    print(json.dumps({"rows": len(payload["rows"]), "summary": len(payload["summary"]), "figures": figures}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

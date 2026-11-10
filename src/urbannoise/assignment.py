"""Constrained task assignment baselines and the project method.

MU-PSA scores a feasible pair by
    P(reach) * P(accept) * quality * Value(task) - lambda * cost.
Reach, acceptance and execution success are separate probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment


@dataclass
class AgentView:
    name: str
    kind: str
    accept: float
    cost: float
    online: bool
    quality: float
    loc: int


@dataclass
class Allocation:
    agent: int
    grid: int
    score: float
    reach: float
    distance: float
    cost: float
    value: float
    context: np.ndarray | None = None


@dataclass
class AllocationResult:
    assignments: list[Allocation] = field(default_factory=list)
    rejected_reasons: list[str] = field(default_factory=list)


DEFAULT_WEIGHTS = {
    "uncertainty": 1.0,
    "coverage": 0.65,
    "temporal": 0.25,
    "duplicate": 0.8,
    "cost": 0.35,
}

CONTEXT_DIM = 10


def manhattan(loc: int, grid: int, width: int) -> int:
    if loc < 0 or grid < 0:
        return 10**6
    return abs((loc % width) - (grid % width)) + abs((loc // width) - (grid // width))


def pair_context(agent: AgentView, reach: float, distance: float, value: float, unc_norm: float, duplicate: float, budget_frac: float, time_frac: float) -> np.ndarray:
    return np.array(
        [
            1.0,
            float(np.clip(unc_norm / 3.0, 0, 1)),
            float(np.clip(value / 3.0, -1, 1)),
            float(np.clip(reach, 0, 1)),
            float(np.clip(agent.cost / 3.0, 0, 2)),
            float(np.clip(distance / 12.0, 0, 2)),
            1.0 if agent.kind == "machine" else 0.0,
            float(np.clip(agent.accept, 0, 1)),
            float(np.clip(budget_frac, 0, 1)),
            float(np.clip(time_frac, 0, 1)),
        ],
        dtype=np.float64,
    )


class LinUCB:
    """Linear UCB over a shortlist of candidate pairs. Action selection does not read noise truth."""

    def __init__(self, dim: int = CONTEXT_DIM, alpha: float = 0.75, l2: float = 1.0):
        self.dim = dim
        self.alpha = alpha
        self.A = np.eye(dim, dtype=np.float64) * l2
        self.b = np.zeros(dim, dtype=np.float64)
        self.updates = 0
        self.rewards: list[float] = []

    def score(self, contexts: np.ndarray) -> np.ndarray:
        if contexts.size == 0:
            return np.zeros(0)
        a_inv = np.linalg.pinv(self.A)
        theta = a_inv @ self.b
        mean = contexts @ theta
        var = np.einsum("ij,jk,ik->i", contexts, a_inv, contexts)
        return mean + self.alpha * np.sqrt(np.maximum(var, 0.0))

    def update(self, context: np.ndarray, reward: float) -> None:
        x = np.asarray(context, dtype=np.float64)
        self.A += np.outer(x, x)
        self.b += float(reward) * x
        self.updates += 1
        self.rewards.append(float(reward))

    def to_dict(self) -> dict:
        return {
            "dim": self.dim,
            "alpha": self.alpha,
            "A": self.A.tolist(),
            "b": self.b.tolist(),
            "updates": self.updates,
            "rewards": self.rewards,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "LinUCB":
        model = cls(dim=int(payload["dim"]), alpha=float(payload["alpha"]))
        model.A = np.asarray(payload["A"], dtype=np.float64)
        model.b = np.asarray(payload["b"], dtype=np.float64)
        model.updates = int(payload.get("updates", 0))
        model.rewards = [float(item) for item in payload.get("rewards", [])]
        return model


def _score_matrix(
    method: str,
    agents: list[AgentView],
    grids: np.ndarray,
    values: np.ndarray,
    unc_norm: np.ndarray,
    duplicate: np.ndarray,
    reach: np.ndarray,
    width: int,
    radius: int,
    weights: dict[str, float],
    rng: np.random.Generator,
    min_reach: float,
) -> tuple[np.ndarray, np.ndarray]:
    n_agents = len(agents)
    n_tasks = len(grids)
    scores = np.full((n_agents, n_tasks), -1e9, dtype=np.float64)
    distances = np.zeros((n_agents, n_tasks), dtype=np.float64)
    for i, agent in enumerate(agents):
        if not agent.online:
            continue
        for j, grid in enumerate(grids):
            dist = manhattan(agent.loc, int(grid), width)
            distances[i, j] = dist
            p_reach = float(reach[i, j])
            p_success = p_reach * agent.accept * agent.quality
            value = float(values[j])
            spatial_ok = dist <= radius and agent.loc >= 0
            if method == "random":
                if spatial_ok or p_reach >= min_reach:
                    scores[i, j] = float(rng.random())
            elif method == "random_reach":
                # Reachability-constrained random: the current cell is not enough.
                if p_reach >= min_reach:
                    scores[i, j] = float(rng.random())
            elif method == "nearest":
                # Current-position nearest. Distance is the location at the decision slot.
                if spatial_ok:
                    scores[i, j] = -dist
            elif method == "nearest_reach":
                # Reachability-aware nearest: prefer the participant most likely to be there.
                if p_reach >= min_reach:
                    scores[i, j] = p_reach
            elif method == "greedy":
                if spatial_ok:
                    scores[i, j] = value - 0.03 * dist
            elif method == "greedy_reach":
                if p_reach >= min_reach:
                    scores[i, j] = value + 0.03 * p_reach
            elif method == "uncertainty":
                if spatial_ok:
                    scores[i, j] = float(unc_norm[j]) - 0.03 * dist
            elif method == "min_cost":
                if spatial_ok or p_reach >= min_reach:
                    scores[i, j] = -(agent.cost + 0.12 * min(dist, 30))
            elif method in {"mupsa", "bandit"}:
                scores[i, j] = p_success * value - weights.get("cost", 0.35) * agent.cost
            elif method == "mupsa_constrained":
                if p_reach >= min_reach:
                    scores[i, j] = p_success * value - weights.get("cost", 0.35) * agent.cost
            elif method == "mupsa_no_mobility":
                if spatial_ok:
                    scores[i, j] = value - weights.get("cost", 0.35) * agent.cost
            elif method == "mupsa_no_uncertainty":
                scores[i, j] = p_success * value - weights.get("cost", 0.35) * agent.cost
            elif method == "mupsa_no_coverage":
                scores[i, j] = p_success * value - weights.get("cost", 0.35) * agent.cost
            else:
                raise ValueError(f"unknown assignment method: {method}")
    return scores, distances


def _greedy_select(
    scores: np.ndarray,
    agents: list[AgentView],
    grids: np.ndarray,
    distances: np.ndarray,
    reach: np.ndarray,
    values: np.ndarray,
    budget: float,
    cap: int,
    floor: float,
) -> list[Allocation]:
    pairs = [(float(scores[i, j]), i, j) for i in range(scores.shape[0]) for j in range(scores.shape[1])]
    pairs.sort(reverse=True)
    used_agents: set[int] = set()
    used_grids: set[int] = set()
    chosen: list[Allocation] = []
    remaining = budget
    for score, i, j in pairs:
        if score < floor:
            break
        if i in used_agents or int(grids[j]) in used_grids:
            continue
        cost = agents[i].cost
        if cost > remaining + 1e-9:
            continue
        chosen.append(
            Allocation(
                agent=i,
                grid=int(grids[j]),
                score=score,
                reach=float(reach[i, j]),
                distance=float(distances[i, j]),
                cost=float(cost),
                value=float(values[j]),
            )
        )
        used_agents.add(i)
        used_grids.add(int(grids[j]))
        remaining -= cost
        if len(chosen) >= cap:
            break
    return chosen


def _hungarian_select(
    scores: np.ndarray,
    agents: list[AgentView],
    grids: np.ndarray,
    distances: np.ndarray,
    reach: np.ndarray,
    values: np.ndarray,
    budget: float,
    cap: int,
) -> list[Allocation]:
    feasible = scores > -1e8
    if not np.any(feasible):
        return []
    # Keep the highest-scoring tasks so the square assignment stays small.
    task_rank = scores.max(axis=0)
    keep = np.argsort(task_rank)[::-1][: min(40, len(grids))]
    sub_scores = scores[:, keep]
    cost = np.where(sub_scores > -1e8, -sub_scores, 1e6)
    row_ind, col_ind = linear_sum_assignment(cost)
    chosen: list[Allocation] = []
    remaining = budget
    order = sorted(zip(row_ind, col_ind), key=lambda item: cost[item[0], item[1]])
    for i, local_j in order:
        if cost[i, local_j] >= 1e5:
            continue
        j = int(keep[local_j])
        if agents[i].cost > remaining + 1e-9:
            continue
        chosen.append(
            Allocation(
                agent=int(i),
                grid=int(grids[j]),
                score=float(scores[i, j]),
                reach=float(reach[i, j]),
                distance=float(distances[i, j]),
                cost=float(agents[i].cost),
                value=float(values[j]),
            )
        )
        remaining -= agents[i].cost
        if len(chosen) >= cap:
            break
    return chosen


def _bandit_select(
    bandit: LinUCB,
    scores: np.ndarray,
    agents: list[AgentView],
    grids: np.ndarray,
    distances: np.ndarray,
    reach: np.ndarray,
    values: np.ndarray,
    unc_norm: np.ndarray,
    duplicate: np.ndarray,
    budget: float,
    cap: int,
    budget_frac: float,
    time_frac: float,
) -> list[Allocation]:
    flat = [(float(scores[i, j]), i, j) for i in range(scores.shape[0]) for j in range(scores.shape[1]) if scores[i, j] > -1e8]
    flat.sort(reverse=True)
    shortlist = flat[:20]
    if not shortlist:
        return []
    contexts = np.stack(
        [
            pair_context(agents[i], float(reach[i, j]), float(distances[i, j]), float(values[j]), float(unc_norm[j]), float(duplicate[j]), budget_frac, time_frac)
            for _, i, j in shortlist
        ]
    )
    ucb = bandit.score(contexts)
    order = np.argsort(ucb)[::-1]
    used_agents: set[int] = set()
    used_grids: set[int] = set()
    chosen: list[Allocation] = []
    remaining = budget
    for rank in order:
        _, i, j = shortlist[int(rank)]
        if i in used_agents or int(grids[j]) in used_grids:
            continue
        if agents[i].cost > remaining + 1e-9:
            continue
        chosen.append(
            Allocation(
                agent=i,
                grid=int(grids[j]),
                score=float(ucb[int(rank)]),
                reach=float(reach[i, j]),
                distance=float(distances[i, j]),
                cost=float(agents[i].cost),
                value=float(values[j]),
                context=contexts[int(rank)].copy(),
            )
        )
        used_agents.add(i)
        used_grids.add(int(grids[j]))
        remaining -= agents[i].cost
        if len(chosen) >= cap:
            break
    return chosen


def allocate(
    method: str,
    agents: list[AgentView],
    grids: np.ndarray,
    values: np.ndarray,
    unc_norm: np.ndarray,
    duplicate: np.ndarray,
    reach: np.ndarray,
    width: int,
    radius: int,
    budget: float,
    cap: int,
    rng: np.random.Generator,
    weights: dict[str, float] | None = None,
    min_reach: float = 0.22,
    bandit: LinUCB | None = None,
    budget_frac: float = 1.0,
    time_frac: float = 0.0,
) -> AllocationResult:
    if budget <= 1e-9 or cap <= 0 or len(agents) == 0 or len(grids) == 0:
        return AllocationResult(rejected_reasons=["no budget, capacity, agents, or candidate tasks"])
    weights = weights or DEFAULT_WEIGHTS
    scores, distances = _score_matrix(method, agents, grids, values, unc_norm, duplicate, reach, width, radius, weights, rng, min_reach)
    if method == "min_cost":
        chosen = _hungarian_select(scores, agents, grids, distances, reach, values, budget, cap)
    elif method == "bandit":
        if bandit is None:
            bandit = LinUCB()
        chosen = _bandit_select(
            bandit, scores, agents, grids, distances, reach, values, unc_norm, duplicate, budget, cap, budget_frac, time_frac
        )
    else:
        floor = -1e8 if method in {"nearest", "random", "random_reach", "min_cost"} else 0.0
        chosen = _greedy_select(scores, agents, grids, distances, reach, values, budget, cap, floor)
    reasons = []
    if not chosen:
        reasons.append("no feasible pair under the method constraints")
    return AllocationResult(chosen, reasons)

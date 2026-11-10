"""Mobility and noise predictors.

These functions accept only histories and observations. They do not accept a noise-field truth array.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel

from urbannoise.acoustics import (
    arithmetic_mean_db,
    db_to_energy,
    delta_method_std_db,
    energy_mean_db,
    energy_to_db,
    validate_distribution,
)


class TransitionCounts:
    """Sparse (agent, source, destination) counts.

    `transitions[agent, src, dst]` stays valid for the existing tests. Large
    grids do not allocate an agents × cells × cells tensor.
    """

    def __init__(self) -> None:
        self.records: dict[tuple[int, int, int], float] = {}
        self.out: list[dict[int, dict[int, float]]] = []

    def add(self, agent: int, src: int, dst: int, value: float = 1.0) -> None:
        while len(self.out) <= agent:
            self.out.append({})
        bucket = self.out[agent].setdefault(int(src), {})
        bucket[int(dst)] = bucket.get(int(dst), 0.0) + float(value)
        key = (int(agent), int(src), int(dst))
        self.records[key] = self.records.get(key, 0.0) + float(value)

    def __getitem__(self, key):
        if not isinstance(key, tuple) or len(key) != 3:
            raise TypeError("transitions are indexed as (agent, src, dst)")
        return float(self.records.get((int(key[0]), int(key[1]), int(key[2])), 0.0))


@dataclass
class MobilityFit:
    time_counts: np.ndarray  # (A, slots_per_day, G)
    transitions: TransitionCounts
    frequency: np.ndarray  # (A, G)
    slots_per_day: int

    def distribution(self, agent: int, tod: int, current: int, lead: int) -> np.ndarray:
        counts = self.time_counts[agent, int(tod) % self.slots_per_day]
        if counts.sum() <= 0:
            counts = self.frequency[agent]
        if counts.sum() <= 0:
            probs = np.full(self.frequency.shape[1], 1.0 / self.frequency.shape[1])
        else:
            probs = counts / counts.sum()
        rollout = self._rollout(agent, current, lead)
        if rollout is not None:
            mixed = 0.55 * probs + 0.45 * rollout
            mixed = mixed / mixed.sum()
        else:
            mixed = probs
        return validate_distribution(mixed)

    def _fallback(self, agent: int) -> np.ndarray:
        freq = self.frequency[agent]
        if freq.sum() > 0:
            return freq / freq.sum()
        return np.full(freq.shape[0], 1.0 / max(freq.shape[0], 1))

    def _rollout(self, agent: int, current: int, lead: int) -> np.ndarray | None:
        if current < 0 or lead <= 0:
            return None
        outgoing = self.transitions.out[agent] if agent < len(self.transitions.out) else {}
        if current not in outgoing or sum(outgoing[current].values()) <= 0:
            return None
        n_grids = int(self.frequency.shape[1])
        # Dense chain matches the previous matrix rollout, including the
        # frequency fallback on rows that have never been left.
        if n_grids <= 768:
            matrix = np.zeros((n_grids, n_grids), dtype=np.float64)
            for src, dests in outgoing.items():
                if 0 <= src < n_grids:
                    for dst, count in dests.items():
                        if 0 <= dst < n_grids:
                            matrix[src, dst] = count
            row_sum = matrix.sum(axis=1, keepdims=True)
            usable = row_sum.ravel() > 0
            safe = np.zeros_like(matrix)
            np.divide(matrix, row_sum, out=safe, where=row_sum > 0)
            fallback = self._fallback(agent)
            for idx in range(n_grids):
                if not usable[idx]:
                    safe[idx] = fallback
            state = np.zeros(n_grids, dtype=np.float64)
            state[int(current)] = 1.0
            for _ in range(int(lead)):
                state = state @ safe
            total = float(state.sum())
            if total <= 0 or not np.all(np.isfinite(state)):
                return None
            return state / total
        fallback_map = {int(idx): float(prob) for idx, prob in enumerate(self._fallback(agent)) if prob > 0}
        state: dict[int, float] = {int(current): 1.0}
        for _ in range(int(lead)):
            nxt: dict[int, float] = {}
            for src, mass in state.items():
                if mass <= 0:
                    continue
                row = outgoing.get(src)
                total = float(sum(row.values())) if row else 0.0
                if total > 0 and row is not None:
                    for dst, count in row.items():
                        nxt[dst] = nxt.get(dst, 0.0) + mass * (count / total)
                else:
                    for dst, prob in fallback_map.items():
                        nxt[dst] = nxt.get(dst, 0.0) + mass * prob
            state = nxt
            if not state:
                return None
        total = float(sum(state.values()))
        if total <= 0:
            return None
        dense = np.zeros(n_grids, dtype=np.float64)
        for dst, mass in state.items():
            if 0 <= dst < n_grids:
                dense[dst] = mass / total
        if not np.all(np.isfinite(dense)) or dense.sum() <= 0:
            return None
        return dense / dense.sum()


def fit_mobility(
    trajectories: np.ndarray,
    visible_until: int,
    slots_per_day: int,
    n_grids: int | None = None,
) -> MobilityFit:
    """Fit using locations at slots 0..visible_until inclusive. Transitions stop at visible_until."""
    if trajectories.ndim != 2:
        raise ValueError("trajectories must have shape (agents, slots)")
    agents, _n_slots = trajectories.shape
    hist_end = int(visible_until) + 1
    history = trajectories[:, :hist_end]
    inferred = int(max(0, history.max())) + 1 if np.any(history >= 0) else 1
    n_grids = max(inferred, int(n_grids or 0), 1)
    nbytes = agents * (int(slots_per_day) + 1) * n_grids * 8
    if nbytes > 512 * 1024 * 1024:
        raise MemoryError(
            f"mobility tables would allocate about {nbytes} bytes for {agents} agents and {n_grids} cells; crop the study window"
        )
    time_counts = np.zeros((agents, slots_per_day, n_grids), dtype=np.float64)
    transitions = TransitionCounts()
    frequency = np.zeros((agents, n_grids), dtype=np.float64)
    for i in range(agents):
        row = history[i]
        for slot, grid in enumerate(row):
            if grid >= 0:
                time_counts[i, slot % slots_per_day, int(grid)] += 1.0
                frequency[i, int(grid)] += 1.0
        for slot in range(len(row) - 1):
            src, dst = int(row[slot]), int(row[slot + 1])
            if src >= 0 and dst >= 0:
                transitions.add(i, src, dst, 1.0)
    return MobilityFit(time_counts, transitions, frequency, slots_per_day)


def most_frequent_distribution(fit: MobilityFit, agent: int) -> np.ndarray:
    freq = fit.frequency[agent]
    if freq.sum() <= 0:
        return validate_distribution(np.full(freq.shape[0], 1.0 / freq.shape[0]))
    return validate_distribution(freq / freq.sum())


def markov_distribution(fit: MobilityFit, agent: int, current: int) -> np.ndarray:
    rolled = fit._rollout(agent, current, 1)
    if rolled is None:
        return most_frequent_distribution(fit, agent)
    return validate_distribution(rolled)


@dataclass
class ObsSet:
    x: list[float]
    y: list[float]
    db: list[float]
    slot: list[int]
    grid: list[int]

    @classmethod
    def empty(cls) -> "ObsSet":
        return cls([], [], [], [], [])

    def add(self, x: int, y: int, level_db: float, slot: int, grid: int) -> None:
        if not np.isfinite(level_db):
            return
        self.x.append(float(x))
        self.y.append(float(y))
        self.db.append(float(level_db))
        self.slot.append(int(slot))
        self.grid.append(int(grid))

    def subset(self, max_slot: int | None = None) -> dict[str, np.ndarray]:
        x = np.asarray(self.x, dtype=np.float64)
        y = np.asarray(self.y, dtype=np.float64)
        db = np.asarray(self.db, dtype=np.float64)
        slot = np.asarray(self.slot, dtype=np.int32)
        grid = np.asarray(self.grid, dtype=np.int32)
        if x.size == 0:
            return {"x": x, "y": y, "db": db, "slot": slot, "grid": grid}
        mask = np.isfinite(db)
        if max_slot is not None:
            mask &= slot <= max_slot
        return {"x": x[mask], "y": y[mask], "db": db[mask], "slot": slot[mask], "grid": grid[mask]}


def grid_queries(width: int, height: int) -> np.ndarray:
    xs, ys = np.meshgrid(np.arange(width), np.arange(height))
    return np.stack([xs.ravel(), ys.ravel()], axis=1).astype(np.float64)


def predict_idw(
    obs: dict[str, np.ndarray],
    queries: np.ndarray,
    now_slot: int,
    power: float = 2.0,
    k: int = 8,
    zones: np.ndarray | None = None,
    slots_per_day: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Energy-domain IDW.

    Distance combines spatial separation, circular time-of-day separation, and an optional
    land-use penalty. The penalty uses only the known zone map, not the noise truth.
    Uncertainty grows with neighbor disagreement and with distance to the nearest observation.
    """
    queries = np.asarray(queries, dtype=np.float64)
    n_query = queries.shape[0]
    if obs["db"].size == 0:
        return np.full(n_query, 55.0), np.full(n_query, 12.0)
    dx = queries[:, None, 0] - obs["x"][None, :]
    dy = queries[:, None, 1] - obs["y"][None, :]
    spatial = np.sqrt(dx * dx + dy * dy)
    if slots_per_day:
        tod_now = int(now_slot) % int(slots_per_day)
        tod_obs = obs["slot"].astype(int) % int(slots_per_day)
        raw = np.abs(tod_now - tod_obs)[None, :]
        tod = np.minimum(raw, int(slots_per_day) - raw).astype(np.float64)
    else:
        tod = np.abs(float(now_slot) - obs["slot"][None, :].astype(np.float64))
    dist = spatial + 0.55 * tod
    if zones is not None:
        qy = np.clip(queries[:, 1].astype(int), 0, zones.shape[0] - 1)
        qx = np.clip(queries[:, 0].astype(int), 0, zones.shape[1] - 1)
        qzone = zones[qy, qx]
        oy = np.clip(obs["y"].astype(int), 0, zones.shape[0] - 1)
        ox = np.clip(obs["x"].astype(int), 0, zones.shape[1] - 1)
        ozone = zones[oy, ox]
        dist = dist + 3.5 * (qzone[:, None] != ozone[None, :]).astype(np.float64)
    k_eff = min(k, dist.shape[1])
    index = np.argpartition(dist, k_eff - 1, axis=1)[:, :k_eff]
    local_dist = np.take_along_axis(dist, index, axis=1)
    local_spatial = np.take_along_axis(spatial, index, axis=1)
    energy = db_to_energy(obs["db"])
    local_energy = energy[index]
    weights = 1.0 / np.maximum(local_dist, 0.35) ** power
    weight_sum = np.sum(weights, axis=1)
    ehat = np.sum(weights * local_energy, axis=1) / np.maximum(weight_sum, 1e-12)
    var = np.sum(weights * (local_energy - ehat[:, None]) ** 2, axis=1) / np.maximum(weight_sum, 1e-12)
    mu = np.asarray(energy_to_db(ehat), dtype=np.float64)
    std = delta_method_std_db(ehat, var)
    std = np.maximum(std, 0.35 + 0.5 * local_spatial.min(axis=1))
    std = np.clip(std, 0.35, 15.0)
    return mu, std


def _design_matrix(x, y, slot, zones, slots_per_day, nearest_dist, nearest_mean) -> np.ndarray:
    hour = 24.0 * ((slot % slots_per_day) + 0.5) / slots_per_day
    zone = zones[y.astype(int), x.astype(int)].astype(np.float64)
    return np.column_stack(
        [
            x / max(1, zones.shape[1] - 1),
            y / max(1, zones.shape[0] - 1),
            np.sin(2 * np.pi * hour / 24.0),
            np.cos(2 * np.pi * hour / 24.0),
            zone / max(1, len(np.unique(zones))),
            nearest_dist,
            nearest_mean / 80.0,
        ]
    )


def _neighbor_stats(obs: dict[str, np.ndarray], queries: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if obs["db"].size == 0:
        return np.full(queries.shape[0], 5.0), np.full(queries.shape[0], 55.0)
    dx = queries[:, None, 0] - obs["x"][None, :]
    dy = queries[:, None, 1] - obs["y"][None, :]
    dist = np.sqrt(dx * dx + dy * dy)
    k = min(3, dist.shape[1])
    index = np.argpartition(dist, k - 1, axis=1)[:, :k]
    local = np.take_along_axis(dist, index, axis=1)
    return local.min(axis=1), obs["db"][index].mean(axis=1)


def predict_rf(
    obs: dict[str, np.ndarray],
    queries: np.ndarray,
    zones: np.ndarray,
    now_slot: int,
    slots_per_day: int,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, str]:
    if obs["db"].size < 16:
        mu, std = predict_idw(obs, queries, now_slot)
        return mu, std, "idw_fallback_small_sample"
    dist_o, mean_o = _neighbor_stats(obs, np.column_stack([obs["x"], obs["y"]]))
    train_x = _design_matrix(obs["x"], obs["y"], obs["slot"], zones, slots_per_day, dist_o, mean_o)
    model = RandomForestRegressor(
        n_estimators=40,
        max_depth=8,
        min_samples_leaf=2,
        random_state=seed,
        n_jobs=1,
    )
    model.fit(train_x, obs["db"])
    dist_q, mean_q = _neighbor_stats(obs, queries)
    query_slot = np.full(queries.shape[0], now_slot)
    query_x = _design_matrix(queries[:, 0], queries[:, 1], query_slot, zones, slots_per_day, dist_q, mean_q)
    tree_preds = np.stack([tree.predict(query_x) for tree in model.estimators_], axis=0)
    mu = tree_preds.mean(axis=0)
    std = np.clip(tree_preds.std(axis=0), 0.4, 15.0)
    return mu, std, "random_forest_tree_std"


def predict_gp(
    obs: dict[str, np.ndarray],
    queries: np.ndarray,
    now_slot: int,
    time_window: int = 6,
) -> tuple[np.ndarray, np.ndarray, str]:
    if obs["db"].size == 0:
        mu, std = predict_idw(obs, queries, now_slot)
        return mu, std, "idw_fallback_empty"
    mask = np.abs(obs["slot"] - now_slot) <= time_window
    if int(mask.sum()) < 8 or int(mask.sum()) > 220:
        mu, std = predict_idw(obs, queries, now_slot)
        reason = "idw_fallback_gp_sample_size" if mask.sum() else "idw_fallback_empty"
        return mu, std, reason
    train = np.column_stack([obs["x"][mask], obs["y"][mask]])
    kernel = RBF(length_scale=2.5) + WhiteKernel(noise_level=1.0)
    model = GaussianProcessRegressor(kernel=kernel, optimizer=None, normalize_y=True, random_state=0)
    model.fit(train, obs["db"][mask])
    mu, std = model.predict(queries, return_std=True)
    return np.asarray(mu, dtype=np.float64), np.clip(np.asarray(std, dtype=np.float64), 0.3, 15.0), "gaussian_process_fixed_kernel"


def prediction_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    err = np.asarray(y_pred, dtype=np.float64) - np.asarray(y_true, dtype=np.float64)
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    var = float(np.var(y_true))
    r2 = float("nan") if var < 1e-9 else float(1.0 - np.var(err) / var)
    return {"mae": mae, "rmse": rmse, "r2": r2}


def interval_stats(y_true: np.ndarray, mu: np.ndarray, std: np.ndarray, z: float = 1.96) -> dict[str, float]:
    low, high = mu - z * std, mu + z * std
    cover = float(np.mean((y_true >= low) & (y_true <= high)))
    width = float(np.mean(high - low))
    return {"coverage": cover, "mean_width": width, "nominal": 0.95}


def cell_features(
    obs: dict[str, np.ndarray],
    width: int,
    height: int,
    slot: int,
    uncertainty: np.ndarray,
) -> dict[str, np.ndarray]:
    n_grids = width * height
    counts = np.zeros(n_grids, dtype=np.float64)
    last = np.full(n_grids, -10_000, dtype=np.int32)
    if obs["grid"].size:
        for grid, seen_slot in zip(obs["grid"], obs["slot"]):
            counts[int(grid)] += 1
            last[int(grid)] = max(int(last[int(grid)]), int(seen_slot))
    xs, ys = np.meshgrid(np.arange(width), np.arange(height))
    coords = np.stack([xs.ravel(), ys.ravel()], axis=1)
    if obs["x"].size:
        dx = coords[:, None, 0] - obs["x"][None, :]
        dy = coords[:, None, 1] - obs["y"][None, :]
        nearest = np.sqrt(dx * dx + dy * dy).min(axis=1)
    else:
        nearest = np.full(n_grids, 8.0)
    unc = np.asarray(uncertainty, dtype=np.float64)
    med = float(np.median(unc)) if unc.size else 1.0
    unc_norm = np.clip(unc / max(med, 0.5), 0.0, 3.0)
    isolation = np.clip(nearest / 4.0, 0.0, 1.5)
    temporal = np.clip((slot - last) / 8.0, 0.0, 1.5)
    temporal = np.where(last < 0, 1.0, temporal)
    duplicate = np.clip(counts / 3.0, 0.0, 2.0)
    coverage_gap = np.exp(-counts)
    return {
        "uncertainty": unc,
        "uncertainty_norm": unc_norm,
        "isolation": isolation,
        "temporal_gap": temporal,
        "duplicate": duplicate,
        "coverage_gap": coverage_gap,
        "counts": counts,
    }


def expected_error_reduction(std: np.ndarray, sensor_sigma: float) -> np.ndarray:
    """Variance drop of one Gaussian measurement update.

    If the predictive variance is v and the sensor variance is r, the posterior
    variance is v r / (v + r), so the reduction is v² / (v + r). The formula is
    fixed. It is not scaled to win a comparison.
    """
    var = np.square(np.maximum(np.asarray(std, dtype=np.float64), 0.0))
    noise = float(sensor_sigma) ** 2
    return (var * var) / (var + noise + 1e-12)


def combine_value(features: dict[str, np.ndarray], weights: dict[str, float], mode: str = "full") -> np.ndarray:
    """Heuristic sampling value. This is not a mutual-information guarantee."""
    unc = features["uncertainty_norm"]
    if mode == "uncertainty":
        return unc.copy()
    if mode == "coverage":
        unc = np.zeros_like(unc)
    coverage = features["coverage_gap"] + 0.5 * features["isolation"]
    if mode == "no_coverage":
        coverage = np.zeros_like(coverage)
    temporal = features["temporal_gap"]
    duplicate = features["duplicate"]
    return (
        weights.get("uncertainty", 1.0) * unc
        + weights.get("coverage", 0.65) * coverage
        + weights.get("temporal", 0.25) * temporal
        - weights.get("duplicate", 0.8) * duplicate
    )


def summarize_levels(levels: np.ndarray) -> dict[str, float]:
    return {
        "energy_mean_db": energy_mean_db(levels),
        "arithmetic_mean_db": arithmetic_mean_db(levels),
        "count": int(np.isfinite(levels).sum()),
    }

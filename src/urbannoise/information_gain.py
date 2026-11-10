"""Expected error reduction under a reach constraint.

Heuristic only. The score estimates how much one new observation would shrink
a variance proxy for reconstruction error. It uses the current predictive
variance (IDW neighbor dispersion on the observation path, or the normalized
uncertainty vector on the allocate() path) and a fixed radial kernel. It does
not read the hidden noise field.

This is not mutual information, not a conditioned Gaussian-process posterior,
and not a submodular objective. There is no (1 - 1/e) guarantee.
Pass-by probability is P(reach). Acceptance is a separate participant attribute.
"""

from __future__ import annotations

import numpy as np

METHOD_NAME = "eer"
LENGTH_SCALE = 2.5
OBS_NOISE_VAR = 1.0
DUPLICATE_PENALTY = 1.0
INFEASIBLE_SCORE = -1.0e9


def uncertainty_to_variance_proxy(unc_norm: np.ndarray) -> np.ndarray:
    """Map allocate()'s normalized uncertainty channel to a variance proxy.

    ``unc_norm`` is whatever the caller stored on the assignment interface,
    typically a median-scaled predictive standard deviation. Squaring it keeps
    the ranking information in that channel. It is not an IDW energy variance
    and it is not in calibrated dB^2.
    """
    uncertainty = np.asarray(unc_norm, dtype=np.float64).reshape(-1)
    uncertainty = np.where(np.isfinite(uncertainty), uncertainty, 0.0)
    return np.maximum(uncertainty, 0.0) ** 2


def expected_error_drops(
    variance: np.ndarray,
    width: int,
    grid_ids: np.ndarray | None = None,
    duplicate: np.ndarray | None = None,
    length_scale: float = LENGTH_SCALE,
    obs_noise_var: float = OBS_NOISE_VAR,
    duplicate_penalty: float = DUPLICATE_PENALTY,
) -> np.ndarray:
    """Myopic expected drop in summed predictive variance for each candidate.

    For candidate cell ``c`` and cells ``i`` that are present in ``variance``:

        rho(i, c) = exp(-0.5 * (d(i, c) / ell)^2)
        raw(c) = (v_c / (v_c + tau^2)) * sum_i rho(i, c)^2 * v_i
        drop(c) = exp(-eta * duplicate_c) * raw(c)

    ``d`` is Euclidean distance on the grid (``x = id % width``, ``y = id // width``).
    ``ell`` is ``length_scale``, ``tau^2`` is ``obs_noise_var``, ``eta`` is
    ``duplicate_penalty``. ``v`` is the supplied variance proxy.

    ``raw(c)`` is what a one-step Gaussian conditioning step would remove from
    the sum of variances if the covariance were ``rho(i, c) * sqrt(v_i v_c)``
    and a noisy observation were taken at ``c``. Existing observations enter
    only through the supplied marginal variances, so this is a diagonal-marginal
    approximation, not a GP update conditioned on the observation set.

    The exponential duplicate factor is an extra penalty on revisited cells.
    It is not part of the Gaussian identity. ``duplicate is None`` means no
    revisit penalty. The hidden noise field is not an argument.
    """
    if width <= 0:
        raise ValueError("width must be positive")
    variance = np.asarray(variance, dtype=np.float64).reshape(-1)
    variance = np.where(np.isfinite(variance), variance, 0.0)
    variance = np.maximum(variance, 0.0)
    if grid_ids is None:
        grid_ids = np.arange(variance.size, dtype=np.int64)
    else:
        grid_ids = np.asarray(grid_ids, dtype=np.int64).reshape(-1)
        if grid_ids.shape != variance.shape:
            raise ValueError("grid_ids and variance must have the same length")
    if grid_ids.size and np.any(grid_ids < 0):
        raise ValueError("grid_ids must be non-negative")
    if variance.size == 0:
        return np.zeros(0, dtype=np.float64)
    ell = float(length_scale)
    tau2 = float(obs_noise_var)
    if not np.isfinite(ell) or ell <= 0.0:
        raise ValueError("length_scale must be positive")
    if not np.isfinite(tau2) or tau2 < 0.0:
        raise ValueError("obs_noise_var must be non-negative")
    xs = (grid_ids % int(width)).astype(np.float64)
    ys = (grid_ids // int(width)).astype(np.float64)
    dx = xs[:, None] - xs[None, :]
    dy = ys[:, None] - ys[None, :]
    dist = np.sqrt(dx * dx + dy * dy)
    # rho[i, c] correlates the variance-proxy residuals at cells i and c.
    rho = np.exp(-0.5 * (dist / ell) ** 2)
    weighted = (rho * rho) @ variance
    shrink = variance / (variance + tau2)
    raw = shrink * weighted
    if duplicate is None:
        return raw
    dup = np.asarray(duplicate, dtype=np.float64).reshape(-1)
    if dup.shape != variance.shape:
        raise ValueError("duplicate must have the same length as variance")
    eta = float(duplicate_penalty)
    if not np.isfinite(eta) or eta < 0.0:
        raise ValueError("duplicate_penalty must be non-negative")
    dup = np.where(np.isfinite(dup), dup, 0.0)
    dup = np.maximum(dup, 0.0)
    return raw * np.exp(-eta * dup)


def eer_pair_score(
    p_reach: float,
    p_accept: float,
    quality: float,
    expected_error_drop: float,
    cost: float,
    lam: float,
) -> float:
    """Return P(reach) * P(accept) * quality * expected_error_drop - lam * cost.

    ``p_accept`` is the participant's acceptance probability. ``p_reach`` is
    the probability the participant is at the cell. A pass-by is not acceptance,
    and the two factors are not substituted for each other.
    """
    return (
        float(p_reach) * float(p_accept) * float(quality) * float(expected_error_drop)
        - float(lam) * float(cost)
    )


def eer_score_matrix(
    drop: np.ndarray,
    reach: np.ndarray,
    accept: np.ndarray,
    quality: np.ndarray,
    cost: np.ndarray,
    lam: float,
    min_reach: float,
    online: np.ndarray | None = None,
) -> np.ndarray:
    """Pair scores. Entries with P(reach) < min_reach, or an offline agent, stay infeasible."""
    drop = np.asarray(drop, dtype=np.float64).reshape(-1)
    reach = np.asarray(reach, dtype=np.float64)
    if reach.ndim != 2:
        raise ValueError("reach must have shape (agents, candidates)")
    n_agents, n_tasks = reach.shape
    if drop.shape != (n_tasks,):
        raise ValueError("expected_error_drop must have one entry per candidate")
    accept = np.asarray(accept, dtype=np.float64).reshape(-1)
    quality = np.asarray(quality, dtype=np.float64).reshape(-1)
    cost = np.asarray(cost, dtype=np.float64).reshape(-1)
    if accept.shape != (n_agents,) or quality.shape != (n_agents,) or cost.shape != (n_agents,):
        raise ValueError("accept, quality, and cost must have one entry per agent")
    if online is None:
        online_mask = np.ones(n_agents, dtype=bool)
    else:
        online_mask = np.asarray(online, dtype=bool).reshape(-1)
        if online_mask.shape != (n_agents,):
            raise ValueError("online must have one entry per agent")
    scores = np.full((n_agents, n_tasks), INFEASIBLE_SCORE, dtype=np.float64)
    for i in range(n_agents):
        if not bool(online_mask[i]):
            continue
        for j in range(n_tasks):
            p_reach = float(reach[i, j])
            if p_reach < float(min_reach):
                continue
            scores[i, j] = eer_pair_score(
                p_reach,
                float(accept[i]),
                float(quality[i]),
                float(drop[j]),
                float(cost[i]),
                lam,
            )
    return scores


def eer_matrix_from_uncertainty(
    unc_norm: np.ndarray,
    duplicate: np.ndarray,
    reach: np.ndarray,
    accept: np.ndarray,
    quality: np.ndarray,
    cost: np.ndarray,
    grids: np.ndarray,
    width: int,
    lam: float,
    min_reach: float,
    online: np.ndarray | None = None,
) -> np.ndarray:
    """Scores for allocate(). Variance proxy is unc_norm^2 on the candidate list only."""
    drop = expected_error_drops(
        uncertainty_to_variance_proxy(unc_norm),
        width,
        grid_ids=np.asarray(grids),
        duplicate=np.asarray(duplicate, dtype=np.float64),
    )
    return eer_score_matrix(drop, reach, accept, quality, cost, lam, min_reach, online)


def eer_pair_scores_from_observations(
    obs: dict[str, np.ndarray],
    queries: np.ndarray,
    now_slot: int,
    accept: np.ndarray,
    quality: np.ndarray,
    cost: np.ndarray,
    reach: np.ndarray,
    width: int,
    grids: np.ndarray | None = None,
    duplicate: np.ndarray | None = None,
    online: np.ndarray | None = None,
    lam: float = 0.35,
    min_reach: float = 0.22,
    zones: np.ndarray | None = None,
    slots_per_day: int | None = None,
    noise_field: np.ndarray | None = None,
) -> np.ndarray:
    """Score pairs from observations only.

    Predictive variance is the square of the IDW standard deviation from
    ``predict_idw``. That standard deviation is the neighbor-weight dispersion
    of the current observations (plus a distance floor). The drop then uses
    :func:`expected_error_drops`. Query index ``i`` is treated as grid id ``i``
    in row-major ``(x, y)`` order, the same order as ``grid_queries``.

    ``noise_field`` is accepted and ignored. Changing hidden or future noise
    truth does not change the score while ``obs`` stays fixed. This remains a
    heuristic approximation of expected squared-error reduction, not mutual
    information and not a (1 - 1/e) bound.
    """
    del noise_field
    # Local import keeps allocate() -> information_gain from loading the noise models.
    from urbannoise.predictors import predict_idw

    _mean, std = predict_idw(
        obs,
        queries,
        now_slot,
        zones=zones,
        slots_per_day=slots_per_day,
    )
    std = np.asarray(std, dtype=np.float64).reshape(-1)
    variance = np.square(np.where(np.isfinite(std), np.maximum(std, 0.0), 0.0))
    n_cells = int(variance.shape[0])
    if grids is None:
        column_ids = np.arange(n_cells, dtype=np.int64)
    else:
        column_ids = np.asarray(grids, dtype=np.int64).reshape(-1)
    if column_ids.size and (np.any(column_ids < 0) or np.any(column_ids >= n_cells)):
        raise ValueError("grids must be indices into the query field")
    dup_full = np.zeros(n_cells, dtype=np.float64)
    if duplicate is not None:
        dup = np.asarray(duplicate, dtype=np.float64).reshape(-1)
        if dup.shape == (n_cells,):
            dup_full = dup
        elif dup.shape == column_ids.shape:
            dup_full[column_ids] = dup
        else:
            raise ValueError("duplicate must align with the full query field or with grids")
    drops_full = expected_error_drops(
        variance,
        width,
        grid_ids=np.arange(n_cells, dtype=np.int64),
        duplicate=dup_full,
    )
    return eer_score_matrix(
        drops_full[column_ids],
        reach,
        accept,
        quality,
        cost,
        lam,
        min_reach,
        online,
    )

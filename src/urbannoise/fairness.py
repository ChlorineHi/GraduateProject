"""Shared environment randomness for method comparisons.

The physical environment (noise field, trajectories, initial observations,
measurement noise, and acceptance) is keyed by scenario, subset, time range,
and seed. The method name is not part of that key, so two algorithms see the
same world. Budget is not part of the key either: a budget sweep changes how
much can be spent, not the past observations or the sensor noise.

Exploration inside an algorithm uses a separate generator. A method that draws
many random scores cannot shift another method's measurement noise.
"""

from __future__ import annotations

import hashlib

import numpy as np


def stable_seed(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "little") % (2**32 - 1)
    return value or 1


def environment_seed(
    *,
    seed: int,
    scenario: str,
    subset: str = "full",
    time_range: str = "default",
    budget: float | None = None,
) -> int:
    """Environment key. `budget` is accepted and deliberately ignored.

    Callers pass it so the comparison key is visible at the call site. Spending
    limit must not resample trajectories or sensor noise.
    """
    del budget
    return stable_seed("env", int(seed), scenario, subset, time_range)


def algorithm_seed(*, seed: int, method: str, budget: float, scenario: str = "") -> int:
    return stable_seed("algo", int(seed), method, f"{float(budget):.6f}", scenario)


def acceptance_draw(env_seed: int, slot: int, agent: int) -> float:
    """Uniform draw in [0, 1) for one agent at one slot. Independent of call order."""
    return float(np.random.default_rng(stable_seed("accept", int(env_seed), int(slot), int(agent))).random())


def measurement_offset(env_seed: int, slot: int, grid: int, agent: int) -> float:
    """Standard-normal measurement noise, before multiplying by the sensor sigma."""
    return float(np.random.default_rng(stable_seed("measure", int(env_seed), int(slot), int(grid), int(agent))).normal())


def prior_fingerprint(x, y, db, slot, grid) -> str:
    if len(db) == 0:
        return hashlib.sha256(b"empty-prior").hexdigest()
    packed = np.column_stack(
        [
            np.asarray(x, dtype=np.float64),
            np.asarray(y, dtype=np.float64),
            np.asarray(db, dtype=np.float64),
            np.asarray(slot, dtype=np.float64),
            np.asarray(grid, dtype=np.float64),
        ]
    )
    return hashlib.sha256(np.ascontiguousarray(packed).tobytes()).hexdigest()

"""Fair environment randomness for method comparisons.

Draws are a pure function of ``(env_seed, participant_id, time, object)``.
Looking one event up does not change any other event, so a method cannot
consume the environment stream by exploring more pairs. Algorithm randomness
is a separate NumPy generator keyed by ``(env_seed, method)``.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

import numpy as np

FAIR_PROTOCOL = "fair_v1"
LEGACY_PROTOCOL = "legacy"

ACCEPT_OBJECT = "accept"
PRIOR_PARTICIPANT = "prior"
_UNIT_SCALE = float(1 << 53)


def _digest(env_seed: int, participant_id: str, time: int, obj: str) -> bytes:
    payload = f"{int(env_seed)}|{participant_id}|{int(time)}|{obj}".encode("utf-8")
    return hashlib.sha256(payload).digest()


def event_index(env_seed: int, participant_id: str, time: int, obj: str) -> int:
    """Stable 64-bit index. Used for ranking and for the algorithm stream seed."""
    return int.from_bytes(_digest(env_seed, participant_id, time, obj)[:8], "little")


def _unit_from_bytes(raw: bytes) -> float:
    value = int.from_bytes(raw[:8], "little") >> 11
    return value / _UNIT_SCALE


def environment_uniform(env_seed: int, participant_id: str, time: int, obj: str) -> float:
    """Uniform draw in ``[0, 1)``."""
    return _unit_from_bytes(_digest(env_seed, participant_id, time, obj))


def environment_normal(env_seed: int, participant_id: str, time: int, obj: str) -> float:
    """Standard normal via Box-Muller on two hash uniforms."""
    digest = _digest(env_seed, participant_id, time, obj)
    u1 = min(max(_unit_from_bytes(digest[:8]), 1e-12), 1.0 - 1e-12)
    u2 = _unit_from_bytes(digest[8:16])
    return float(math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2))


def measurement_object(grid_id: int) -> str:
    return f"measurement:{int(grid_id)}"


def algorithm_rng(env_seed: int, method: str) -> np.random.Generator:
    """Exploration stream. Independent of acceptance and measurement draws."""
    return np.random.default_rng(event_index(env_seed, "algorithm", 0, method))


@dataclass
class EnvironmentEventTable:
    """Memoized environment draws. Values do not depend on insertion order."""

    env_seed: int
    uniform_draws: dict[tuple[str, int, str], float] = field(default_factory=dict)
    normal_draws: dict[tuple[str, int, str], float] = field(default_factory=dict)

    def uniform(self, participant_id: str, time: int, obj: str) -> float:
        key = (str(participant_id), int(time), str(obj))
        cached = self.uniform_draws.get(key)
        if cached is None:
            cached = environment_uniform(self.env_seed, *key)
            self.uniform_draws[key] = cached
        return cached

    def normal(self, participant_id: str, time: int, obj: str) -> float:
        key = (str(participant_id), int(time), str(obj))
        cached = self.normal_draws.get(key)
        if cached is None:
            cached = environment_normal(self.env_seed, *key)
            self.normal_draws[key] = cached
        return cached


def precompute_environment_events(world, env_seed: int) -> EnvironmentEventTable:
    """Acceptance draw for every participant and slot. Measurements stay lazy."""
    table = EnvironmentEventTable(int(env_seed))
    n_slots = int(world.n_slots)
    for agent in world.agents:
        name = str(agent.name)
        for slot in range(n_slots):
            table.uniform(name, slot, ACCEPT_OBJECT)
    return table


def measurement_db(world, env_seed: int, participant_id: str, slot: int, grid_id: int, kind: str, events: EnvironmentEventTable | None = None) -> float:
    """Sensor reading at one executed cell. Truth is read only here."""
    table = events or EnvironmentEventTable(int(env_seed))
    if table.env_seed != int(env_seed):
        raise ValueError("environment event table was built for a different seed")
    unit = table.normal(str(participant_id), int(slot), measurement_object(grid_id))
    sigma = float(world.sensor_sigma) * (0.75 if kind == "machine" else 1.0)
    x, y = world.xy(int(grid_id))
    return float(world.laeq[int(slot), y, x] + unit * sigma)

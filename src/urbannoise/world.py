"""Synthetic city generator.

The noise field is the simulation ground truth. Predictors must not receive it.
Human trajectories are synthetic demo mobility, not YJMob100K and not a real city.
Virtual grid coordinates are never labeled as Beijing, Tokyo, or any real district.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from urbannoise.acoustics import db_to_energy, energy_to_db

ZONE_NAMES = ["residential", "commercial", "arterial", "industrial", "park", "school"]
ZONE_BASE_DB = {
    "residential": 46.0,
    "commercial": 60.0,
    "arterial": 70.0,
    "industrial": 74.0,
    "park": 38.0,
    "school": 52.0,
}


@dataclass
class Agent:
    idx: int
    name: str
    kind: str
    accept: float
    cost: float
    online: bool
    quality: float
    traj: np.ndarray


@dataclass
class World:
    seed: int
    scenario: str
    height: int
    width: int
    slots_per_day: int
    n_days: int
    zones: np.ndarray
    laeq: np.ndarray
    energy: np.ndarray
    agents: list[Agent]
    sensor_sigma: float
    prior_samples: int
    horizon: tuple[int, int]
    coordinate_system: str = "synthetic_virtual_grid"
    data_origin: str = "synthetic_demo"
    meta: dict = field(default_factory=dict)

    @property
    def n_slots(self) -> int:
        return int(self.laeq.shape[0])

    @property
    def n_grids(self) -> int:
        return self.height * self.width

    def grid_id(self, x: int, y: int) -> int:
        return int(y) * self.width + int(x)

    def xy(self, grid_id: int) -> tuple[int, int]:
        return int(grid_id) % self.width, int(grid_id) // self.width


def make_zones(height: int, width: int) -> np.ndarray:
    """Districts are placed off the central cross so roads do not erase them."""
    zones = np.zeros((height, width), dtype=np.int8)
    def fill(y0: int, y1: int, x0: int, x1: int, name: str) -> None:
        zones[max(0, y0) : min(height, y1), max(0, x0) : min(width, x1)] = ZONE_NAMES.index(name)

    fill(0, max(2, height // 3), 0, max(2, width // 3), "park")
    fill(0, max(2, height // 3), width - max(2, width // 3), width, "industrial")
    fill(height - max(2, height // 3), height, 0, max(2, width // 3), "school")
    fill(height - max(2, height // 3), height, width - max(2, width // 3), width, "commercial")
    zones[height // 2, :] = ZONE_NAMES.index("arterial")
    zones[:, width // 2] = ZONE_NAMES.index("arterial")
    return zones


def _diurnal_factor(tod: int, slots_per_day: int, zone_name: str) -> float:
    hour = 24.0 * (tod + 0.5) / slots_per_day
    morning = np.exp(-0.5 * ((hour - 8.0) / 1.6) ** 2)
    evening = np.exp(-0.5 * ((hour - 18.0) / 1.8) ** 2)
    midday = np.exp(-0.5 * ((hour - 13.0) / 3.0) ** 2)
    if zone_name == "park":
        return float(0.35 + 0.95 * np.exp(-0.5 * ((hour - 15.0) / 3.2) ** 2))
    if zone_name == "school":
        return float(0.30 + 1.35 * np.exp(-0.5 * ((hour - 10.0) / 1.4) ** 2) + 0.85 * np.exp(-0.5 * ((hour - 16.0) / 1.1) ** 2))
    if zone_name == "arterial":
        return float(0.28 + 1.55 * morning + 1.65 * evening + 0.35 * midday)
    if zone_name == "commercial":
        return float(0.38 + 0.45 * morning + 1.15 * midday + 1.45 * evening)
    if zone_name == "industrial":
        day = 1.0 if 7.0 <= hour <= 19.0 else 0.55
        return float(0.75 + 0.55 * day)
    return float(0.42 + 0.75 * morning + 0.45 * evening + 0.22 * midday)


def _weekly_factor(day_index: int, zone_name: str) -> float:
    weekend = day_index % 7 in (5, 6)
    if not weekend:
        return 1.0
    if zone_name == "arterial":
        return 0.78
    if zone_name == "commercial":
        return 1.12
    if zone_name == "industrial":
        return 0.62
    if zone_name == "school":
        return 0.55
    return 0.92


def generate_noise_field(
    zones: np.ndarray,
    n_slots: int,
    slots_per_day: int,
    scenario: str,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    height, width = zones.shape
    latent = rng.normal(size=(height, width))
    # Separable smoothing keeps spatial correlation without requiring scipy.ndimage at generation time.
    kernel = np.array([0.1, 0.2, 0.4, 0.2, 0.1])
    for _ in range(2):
        latent = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="same"), 1, latent)
        latent = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="same"), 0, latent)
    latent = (latent - latent.mean()) / (latent.std() + 1e-6)

    base = np.zeros((height, width), dtype=np.float64)
    for idx, name in enumerate(ZONE_NAMES):
        base[zones == idx] = db_to_energy(ZONE_BASE_DB[name])
    spatial = base * np.exp(0.12 * latent)

    sigma = {"regular": 0.05, "complex": 0.12, "shift": 0.09}[scenario]
    energy = np.empty((n_slots, height, width), dtype=np.float64)
    n_days = int(np.ceil(n_slots / slots_per_day))
    for t in range(n_slots):
        tod = t % slots_per_day
        day = t // slots_per_day
        factor = np.empty((height, width), dtype=np.float64)
        for idx, name in enumerate(ZONE_NAMES):
            factor[zones == idx] = _diurnal_factor(tod, slots_per_day, name) * _weekly_factor(day % 7, name)
        frame = spatial * factor
        if scenario in {"complex", "shift"}:
            frame = frame * np.exp(rng.normal(0.0, sigma, size=frame.shape))
        else:
            frame = frame * np.exp(rng.normal(0.0, sigma))
        energy[t] = frame

    if scenario == "complex":
        _add_events(energy, rng, n_events=4)
    elif scenario == "shift":
        _add_events(energy, rng, n_events=2)
        _apply_shift(energy, zones, slots_per_day)

    energy = np.maximum(energy, 1e-8)
    laeq = energy_to_db(energy).astype(np.float64)
    return laeq, energy


def _add_events(energy: np.ndarray, rng: np.random.Generator, n_events: int) -> None:
    n_slots, height, width = energy.shape
    for _ in range(n_events):
        t0 = int(rng.integers(0, max(1, n_slots - 2)))
        dur = int(rng.integers(1, min(4, n_slots - t0) + 1))
        y = int(rng.integers(0, height))
        x = int(rng.integers(0, width))
        rad = int(rng.integers(0, 2))
        boost_db = float(rng.uniform(6.0, 14.0))
        mult = float(db_to_energy(boost_db) / db_to_energy(0.0))
        y0, y1 = max(0, y - rad), min(height, y + rad + 1)
        x0, x1 = max(0, x - rad), min(width, x + rad + 1)
        energy[t0 : t0 + dur, y0:y1, x0:x1] *= mult


def _apply_shift(energy: np.ndarray, zones: np.ndarray, slots_per_day: int) -> None:
    """Second-day regime change: a residential block becomes noisy and commercial activity drops."""
    n_slots, height, width = energy.shape
    start = min(n_slots, slots_per_day + slots_per_day // 3)
    block = np.zeros_like(zones, dtype=bool)
    block[height // 5 : height // 2, width // 5 : width // 2] = True
    block &= zones == ZONE_NAMES.index("residential")
    commercial = zones == ZONE_NAMES.index("commercial")
    energy[start:, block] *= float(db_to_energy(8.0))
    energy[start:, commercial] *= float(db_to_energy(-4.0) / db_to_energy(0.0))


def _cells(zones: np.ndarray, names: list[str]) -> list[tuple[int, int]]:
    mask = np.isin(zones, [ZONE_NAMES.index(name) for name in names])
    ys, xs = np.where(mask)
    if len(ys) == 0:
        ys, xs = np.where(np.ones_like(zones, dtype=bool))
    return list(zip(ys.tolist(), xs.tolist()))


def _jitter(rng: np.random.Generator, y: int, x: int, height: int, width: int) -> tuple[int, int]:
    return int(np.clip(y + int(rng.integers(-1, 2)), 0, height - 1)), int(np.clip(x + int(rng.integers(-1, 2)), 0, width - 1))


def generate_agents(
    zones: np.ndarray,
    n_slots: int,
    slots_per_day: int,
    n_human: int,
    n_machine: int,
    rng: np.random.Generator,
    scenario: str,
    missing_rate: float,
    accept_human: float,
    accept_machine: float,
    cost_human: float,
    cost_machine: float,
    offline_fraction: float,
) -> list[Agent]:
    height, width = zones.shape
    homes = _cells(zones, ["residential"])
    works = _cells(zones, ["commercial", "industrial", "school"])
    leisure = _cells(zones, ["commercial", "park"])
    arterial = _cells(zones, ["arterial"])
    agents: list[Agent] = []
    for i in range(n_human):
        home = homes[int(rng.integers(0, len(homes)))]
        work = works[int(rng.integers(0, len(works)))]
        leisure_cell = leisure[int(rng.integers(0, len(leisure)))]
        traj = np.full(n_slots, -1, dtype=np.int32)
        for t in range(n_slots):
            tod = t % slots_per_day
            hour = 24.0 * (tod + 0.5) / slots_per_day
            day = t // slots_per_day
            if scenario == "shift" and day >= 1 and hour >= 16.0 and rng.random() < 0.55:
                y, x = home
            elif hour < 7.0 or hour >= 22.0:
                y, x = home
            elif 9.0 <= hour < 17.0:
                y, x = work
            elif 7.0 <= hour < 9.0:
                alpha = (hour - 7.0) / 2.0
                y = int(round(home[0] * (1 - alpha) + work[0] * alpha))
                x = int(round(home[1] * (1 - alpha) + work[1] * alpha))
            else:
                y, x = leisure_cell if rng.random() < 0.45 else home
            if rng.random() < 0.12:
                y, x = _jitter(rng, y, x, height, width)
            if rng.random() < missing_rate:
                traj[t] = -1
            else:
                traj[t] = y * width + x
        agents.append(
            Agent(
                idx=i,
                name=f"H{i+1:02d}",
                kind="human",
                accept=float(accept_human),
                cost=float(cost_human),
                online=bool(rng.random() >= offline_fraction),
                quality=float(rng.uniform(0.85, 1.0)),
                traj=traj,
            )
        )
    if not arterial:
        arterial = [(height // 2, width // 2)]
    order = sorted(arterial)
    for j in range(n_machine):
        offset = int(rng.integers(0, len(order)))
        traj = np.full(n_slots, -1, dtype=np.int32)
        for t in range(n_slots):
            tod = t % slots_per_day
            # Same time of day returns to the same patrol cell on every day.
            y, x = order[(offset + tod) % len(order)]
            if rng.random() < missing_rate * 0.25:
                traj[t] = -1
            else:
                traj[t] = y * width + x
        agents.append(
            Agent(
                idx=n_human + j,
                name=f"M{j+1:02d}",
                kind="machine",
                accept=float(accept_machine),
                cost=float(cost_machine),
                online=True,
                quality=0.98,
                traj=traj,
            )
        )
    return agents


def build_world(
    seed: int = 7,
    height: int = 16,
    width: int = 16,
    n_days: int = 2,
    slots_per_day: int = 48,
    n_human: int = 18,
    n_machine: int = 6,
    scenario: str = "complex",
    missing_rate: float = 0.04,
    sensor_sigma: float = 1.5,
    accept_human: float = 0.72,
    accept_machine: float = 0.96,
    cost_human: float = 1.0,
    cost_machine: float = 1.7,
    offline_fraction: float = 0.0,
    prior_samples: int = 36,
    horizon: tuple[int, int] | None = None,
) -> World:
    if scenario not in {"regular", "complex", "shift"}:
        raise ValueError(f"unknown scenario: {scenario}")
    rng = np.random.default_rng(seed)
    zones = make_zones(height, width)
    n_slots = n_days * slots_per_day
    laeq, energy = generate_noise_field(zones, n_slots, slots_per_day, scenario, rng)
    agents = generate_agents(
        zones,
        n_slots,
        slots_per_day,
        n_human,
        n_machine,
        rng,
        scenario,
        missing_rate,
        accept_human,
        accept_machine,
        cost_human,
        cost_machine,
        offline_fraction,
    )
    if horizon is None:
        horizon = (slots_per_day, n_slots)
    return World(
        seed=seed,
        scenario=scenario,
        height=height,
        width=width,
        slots_per_day=slots_per_day,
        n_days=n_days,
        zones=zones,
        laeq=laeq,
        energy=energy,
        agents=agents,
        sensor_sigma=sensor_sigma,
        prior_samples=prior_samples,
        horizon=horizon,
        meta={
            "label": "Synthetic Demo",
            "real_city": False,
            "license": "generated by UrbanNoiseLab for demonstration and controlled experiments",
            "note": "Virtual grid. Do not interpret coordinates as a real administrative district.",
        },
    )


def save_world(path, world: World) -> None:
    import json
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "seed": world.seed,
        "scenario": world.scenario,
        "height": world.height,
        "width": world.width,
        "slots_per_day": world.slots_per_day,
        "n_days": world.n_days,
        "sensor_sigma": world.sensor_sigma,
        "prior_samples": world.prior_samples,
        "horizon": list(world.horizon),
        "coordinate_system": world.coordinate_system,
        "data_origin": world.data_origin,
        "meta": world.meta,
        "agents": [
            {
                "idx": agent.idx,
                "name": agent.name,
                "kind": agent.kind,
                "accept": agent.accept,
                "cost": agent.cost,
                "online": agent.online,
                "quality": agent.quality,
            }
            for agent in world.agents
        ],
    }
    traj = np.stack([agent.traj for agent in world.agents], axis=0) if world.agents else np.zeros((0, world.n_slots), dtype=np.int32)
    np.savez_compressed(path, zones=world.zones, laeq=world.laeq, energy=world.energy, traj=traj, meta_json=np.array(json.dumps(meta)))


def load_world(path) -> World:
    import json

    data = np.load(path, allow_pickle=False)
    meta = json.loads(str(data["meta_json"]))
    agents = []
    traj = data["traj"]
    for row, spec in zip(traj, meta["agents"]):
        agents.append(
            Agent(
                idx=int(spec["idx"]),
                name=spec["name"],
                kind=spec["kind"],
                accept=float(spec["accept"]),
                cost=float(spec["cost"]),
                online=bool(spec["online"]),
                quality=float(spec["quality"]),
                traj=np.asarray(row, dtype=np.int32),
            )
        )
    return World(
        seed=int(meta["seed"]),
        scenario=meta["scenario"],
        height=int(meta["height"]),
        width=int(meta["width"]),
        slots_per_day=int(meta["slots_per_day"]),
        n_days=int(meta["n_days"]),
        zones=np.asarray(data["zones"]),
        laeq=np.asarray(data["laeq"], dtype=np.float64),
        energy=np.asarray(data["energy"], dtype=np.float64),
        agents=agents,
        sensor_sigma=float(meta["sensor_sigma"]),
        prior_samples=int(meta["prior_samples"]),
        horizon=tuple(meta["horizon"]),
        coordinate_system=meta["coordinate_system"],
        data_origin=meta["data_origin"],
        meta=meta.get("meta") or {},
    )


def sample_measurement(world: World, slot: int, grid_id: int, rng: np.random.Generator, sigma: float | None = None) -> float:
    """The only helper that reads ground truth for a single executed sample."""
    if grid_id < 0:
        raise ValueError("cannot sample an unknown grid")
    x, y = world.xy(grid_id)
    noise = float(rng.normal(0.0, world.sensor_sigma if sigma is None else sigma))
    return float(world.laeq[slot, y, x] + noise)

"""Wall time of one shared 8x8 episode. Does not enter the MAE tables."""

from __future__ import annotations

import json
import time
from pathlib import Path

from urbannoise.experiment import EpisodeConfig, environment_seed, run_episode
from urbannoise.world import build_world

ROOT = Path(__file__).resolve().parents[1]
METHODS = [
    "random",
    "nearest",
    "reach_nearest",
    "reach_random",
    "reach_greedy",
    "greedy",
    "uncertainty",
    "min_cost",
    "mupsa",
    "eer_reach",
    "bandit",
]


def main() -> None:
    world = build_world(seed=0, height=8, width=8, n_days=2, slots_per_day=6, n_human=6, n_machine=2, scenario="regular", prior_samples=8)
    env = environment_seed(seed=0, scenario="regular", subset="timing", time_range="day0-1")
    run_episode(world, "mupsa", 8, 0, EpisodeConfig(lead=1, per_slot_cap=2), env_seed=env)
    rows = []
    for method in METHODS:
        started = time.perf_counter()
        for _ in range(5):
            run_episode(world, method, 8, 0, EpisodeConfig(lead=1, per_slot_cap=2), env_seed=env)
        rows.append({"method": method, "seconds_mean_of_5": (time.perf_counter() - started) / 5, "grid": 8, "budget": 8, "scenario": "regular", "seed": 0})
    path = ROOT / "experiments/results/phase2/timing.json"
    path.write_text(json.dumps({"note": "Five repeats of one shared 8x8 world after one warmup. Not an accuracy result.", "rows": rows}, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()

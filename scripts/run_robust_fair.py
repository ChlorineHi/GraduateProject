"""Fair-protocol robustness sidecar.

Does not overwrite experiments/results/phase2/fair_main.
The method list includes eer_reach. The robustness loop inside
experiment.run_suite only names nearest, greedy and mupsa, so this
script calls run_episode directly.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from urbannoise.experiment import EpisodeConfig, environment_seed, run_episode
from urbannoise.world import build_world

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments/results/phase2/robust_fair"

VARIANTS = [
    {"name": "baseline_mix", "n_human": 6, "n_machine": 2, "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
    {"name": "few_participants", "n_human": 2, "n_machine": 1, "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
    {"name": "low_acceptance", "n_human": 6, "n_machine": 2, "accept_human": 0.3, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
    {"name": "shift_mobility", "n_human": 6, "n_machine": 2, "accept_human": 0.72, "scenario": "shift", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
    {"name": "noisy_sensors", "n_human": 6, "n_machine": 2, "accept_human": 0.72, "scenario": "complex", "missing_rate": 0.04, "sensor_sigma": 4.0, "offline_fraction": 0.0},
    {"name": "missing_trajectories", "n_human": 6, "n_machine": 2, "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.25, "sensor_sigma": 1.5, "offline_fraction": 0.0},
    {"name": "partial_offline", "n_human": 6, "n_machine": 2, "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.4},
    {"name": "humans_only", "n_human": 6, "n_machine": 0, "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
    {"name": "machines_only", "n_human": 0, "n_machine": 2, "accept_human": 0.72, "scenario": "regular", "missing_rate": 0.04, "sensor_sigma": 1.5, "offline_fraction": 0.0},
]
METHODS = ["nearest", "min_cost", "mupsa", "eer_reach", "reach_random"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    started = time.time()
    for variant in VARIANTS:
        for seed in (0, 1, 2):
            world = build_world(
                seed=int(seed) + 90,
                height=8,
                width=8,
                n_days=2,
                slots_per_day=6,
                n_human=int(variant["n_human"]),
                n_machine=int(variant["n_machine"]),
                scenario=variant["scenario"],
                accept_human=float(variant["accept_human"]),
                missing_rate=float(variant["missing_rate"]),
                sensor_sigma=float(variant["sensor_sigma"]),
                offline_fraction=float(variant["offline_fraction"]),
                prior_samples=8,
            )
            env = environment_seed(seed=int(seed) + 90, scenario=str(variant["scenario"]), subset=variant["name"], time_range="robustness")
            for method in METHODS:
                result = run_episode(world, method, 8.0, int(seed) + 90, EpisodeConfig(lead=1, per_slot_cap=2), env_seed=env)
                result.pop("execution_draws", None)
                result["variant"] = variant["name"]
                result["family"] = "robustness"
                result["budget"] = 8
                rows.append(result)
    summary = []
    for variant in VARIANTS:
        for method in METHODS:
            picked = [row for row in rows if row["variant"] == variant["name"] and row["method"] == method]
            summary.append(
                {
                    "variant": variant["name"],
                    "method": method,
                    "n": len(picked),
                    "budget": 8,
                    "mae_mean": float(np.mean([row["mae_available_at_t"] for row in picked])),
                    "mae_std": float(np.std([row["mae_available_at_t"] for row in picked], ddof=1)),
                    "success_mean": float(np.mean([row["successful_tasks"] for row in picked])),
                    "cost_mean": float(np.mean([row["sampling_cost"] for row in picked])),
                }
            )
    payload = {
        "config": {
            "protocol": "mae_available_at_t",
            "grid": 8,
            "budget": 8,
            "seeds_requested": [0, 1, 2],
            "world_seed": "requested seed plus 90",
            "note": "Sidecar. Does not replace fair_main. eer_reach is included here.",
        },
        "variants": VARIANTS,
        "methods": METHODS,
        "summary": summary,
        "rows": rows,
        "elapsed_sec": time.time() - started,
    }
    (OUT / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT / 'results.json'} elapsed={payload['elapsed_sec']:.3f}s rows={len(rows)}")


if __name__ == "__main__":
    main()

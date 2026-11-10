"""Fair synthetic suite plus real-data episodes.

Writes only summaries under experiments/results/phase2. Does not copy raw tracks.
"""

from __future__ import annotations

import json
from pathlib import Path

from urbannoise.experiment import PROTOCOL_NAME, EpisodeConfig, plot_results, run_episode, run_suite
from urbannoise.fairness import environment_seed
from urbannoise.noiseeval import predict_parquet
from urbannoise.scenarios import overlap_report, resolve_world

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "experiments" / "results" / "phase2"
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
]


def _mean_std(rows: list[dict], key: str) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(row["method"], []).append(float(row[key]))
    out = {}
    for method, values in grouped.items():
        import numpy as np

        arr = np.asarray(values, dtype=float)
        out[method] = {"mean": float(arr.mean()), "std": float(arr.std(ddof=1) if len(arr) > 1 else 0.0), "n": int(len(arr))}
    return out


def run_mobility(name: str, params: dict, seeds: list[int], budget: float) -> dict:
    rows = []
    worlds = []
    for seed in seeds:
        local = dict(params)
        local["seed"] = seed
        world = resolve_world(local, ROOT / "data")
        worlds.append(
            {
                "seed": seed,
                "real_human_count": world.meta.get("real_human_count"),
                "synthetic_machine_count": world.meta.get("synthetic_machine_count"),
                "source_rows_in_window": world.meta.get("source_rows_in_window"),
                "user_ids": world.meta.get("user_ids"),
                "day_min": world.meta.get("day_min"),
                "day_max": world.meta.get("day_max"),
                "width": world.width,
                "height": world.height,
                "n_slots": world.n_slots,
                "coordinate_system": world.coordinate_system,
                "named_city": None,
                "window_rule": world.meta.get("window_rule"),
                "study_dates": world.meta.get("study_dates"),
            }
        )
        env = environment_seed(
            seed=seed,
            scenario=str(local.get("scenario", "regular")),
            subset=name,
            time_range=f"{local.get('day_min', 0)}-{local.get('n_days', 2)}",
        )
        for method in METHODS:
            result = run_episode(world, method, budget, seed, EpisodeConfig(lead=1, per_slot_cap=2), env_seed=env)
            result.pop("execution_draws", None)
            result["family"] = "real_mobility"
            result["subset"] = name
            rows.append(result)
        hashes = {row["environment_hash"] for row in rows if row["seed"] == seed}
        if len(hashes) != 1:
            raise RuntimeError(f"{name} seed {seed} did not share one environment hash: {hashes}")
    destination = OUT / name
    destination.mkdir(parents=True, exist_ok=True)
    payload = {
        "protocol": PROTOCOL_NAME,
        "subset": name,
        "budget": budget,
        "seeds": seeds,
        "worlds": worlds,
        "mae_available_at_t": _mean_std(rows, "mae_available_at_t"),
        "successful_tasks": _mean_std(rows, "successful_tasks"),
        "rows": rows,
    }
    (destination / "results.json").write_text(json.dumps(payload), encoding="utf-8")
    return {
        "subset": name,
        "worlds": worlds,
        "mae_available_at_t": payload["mae_available_at_t"],
        "successful_tasks": payload["successful_tasks"],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fair_config = json.loads((ROOT / "experiments" / "configs" / "phase2_fair.json").read_text(encoding="utf-8"))
    fair = run_suite(fair_config, OUT / "fair_main")
    figures = plot_results(fair, ROOT / "experiments" / "figures" / "phase2" / "fair_main")
    slim = {
        "summary": fair.get("summary"),
        "protocol": fair.get("protocol"),
        "metric_definitions": fair.get("metric_definitions"),
        "ablation": fair.get("ablation"),
        "mobility": fair.get("mobility"),
        "noise_models": fair.get("noise_models"),
    }
    (OUT / "fair_main" / "summary.json").write_text(json.dumps(slim), encoding="utf-8")
    mobility = [
        run_mobility(
            "yjmob_dataset1",
            {
                "mode": "real_mobility",
                "mobility_source": "yjmob_dataset1",
                "n_users": 10,
                "candidate_users": 400,
                "n_days": 2,
                "day_min": 0,
                "slots_per_day": 48,
                "max_side": 24,
                "n_machine": 1,
                "scenario": "regular",
                "prior_samples": 8,
            },
            [0, 1],
            8,
        ),
        run_mobility(
            "yjmob_dataset2_early",
            {
                "mode": "real_mobility",
                "mobility_source": "yjmob_dataset2",
                "n_users": 10,
                "candidate_users": 400,
                "n_days": 2,
                "day_min": 0,
                "slots_per_day": 48,
                "max_side": 24,
                "n_machine": 1,
                "scenario": "regular",
                "prior_samples": 8,
            },
            [0, 1],
            8,
        ),
        run_mobility(
            "yjmob_dataset2",
            {
                "mode": "real_mobility",
                "mobility_source": "yjmob_dataset2",
                "n_users": 10,
                "candidate_users": 400,
                "n_days": 2,
                "day_min": 60,
                "slots_per_day": 48,
                "max_side": 24,
                "n_machine": 1,
                "scenario": "regular",
                "prior_samples": 8,
            },
            [0, 1],
            8,
        ),
        run_mobility(
            "geolife",
            {
                "mode": "real_mobility",
                "mobility_source": "geolife",
                "n_users": 10,
                "grid_m": 500,
                "slots_per_day": 48,
                "max_side": 24,
                "n_machine": 1,
                "scenario": "regular",
                "prior_samples": 8,
            },
            [0, 1],
            8,
        ),
    ]
    noise = {}
    hourly = ROOT / "data" / "processed" / "noisecapture" / "hourly_500m.parquet"
    for country in ("France", "Luxembourg"):
        noise[country] = predict_parquet(hourly, indicator="laeq_1s", country=country)
    overlap = overlap_report(ROOT / "data")
    report = {
        "protocol": PROTOCOL_NAME,
        "fair_figures": figures,
        "fair_rows": len(fair["rows"]),
        "mobility": mobility,
        "noise_holdout": noise,
        "fully_real": overlap,
    }
    (OUT / "real_runs.json").write_text(json.dumps(report), encoding="utf-8")
    print(json.dumps({"fair_rows": len(fair["rows"]), "figures": figures, "noise_france_mae": noise["France"]["mae"], "fully_real": overlap["feasible"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

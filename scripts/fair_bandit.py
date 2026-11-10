"""Compare a frozen LinUCB policy with baselines on the same worlds.

The main table does not include this policy. These seeds are 800–804, matching bandit_eval.
"""

from __future__ import annotations

import json
from pathlib import Path

from urbannoise.assignment import LinUCB
from urbannoise.experiment import EpisodeConfig, run_episode
from urbannoise.world import build_world

ROOT = Path("experiments/results")
CHECKPOINT = ROOT / "checkpoints" / "linucb.json"


def main() -> None:
    bandit = LinUCB.from_dict(json.loads(CHECKPOINT.read_text(encoding="utf-8")))
    methods = ["min_cost", "uncertainty", "mupsa", "bandit"]
    rows = []
    for seed in range(5):
        world = build_world(
            seed=800 + seed,
            height=14,
            width=14,
            n_days=2,
            slots_per_day=24,
            n_human=16,
            n_machine=4,
            scenario="regular",
            prior_samples=28,
        )
        for method in methods:
            result = run_episode(
                world,
                method,
                24,
                50_000 + seed,
                EpisodeConfig(lead=1, per_slot_cap=4),
                bandit=bandit if method == "bandit" else None,
                train_bandit=False,
            )
            result["family"] = "bandit_fair"
            rows.append(result)
            print(method, seed, round(result["mae_causal"], 3), result["successful_tasks"], round(result["coverage"], 3))
    summary = []
    for method in methods:
        subset = [row for row in rows if row["method"] == method]
        summary.append(
            {
                "method": method,
                "n": len(subset),
                "mae_mean": sum(row["mae_causal"] for row in subset) / len(subset),
                "coverage_mean": sum(row["coverage"] for row in subset) / len(subset),
                "success_mean": sum(row["successful_tasks"] for row in subset) / len(subset),
                "cost_mean": sum(row["sampling_cost"] for row in subset) / len(subset),
            }
        )
    payload = {
        "protocol_name": "fair_v1",
        "protocol": "Same worlds as the legacy bandit_eval worlds: seeds 800-804, regular, budget 24, grid 14, lead 1. Frozen LinUCB, no test-time updates. Environment draws follow fair_v1. This file is not the legacy bandit_fair.json table.",
        "kind": "bandit_comparison",
        "is_main_result": False,
        "summary": summary,
        "rows": rows,
    }
    legacy = ROOT / "bandit_fair.json"
    dest = ROOT / "bandit_fair_fair_v1.json" if legacy.exists() else legacy
    dest.write_text(json.dumps(payload), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

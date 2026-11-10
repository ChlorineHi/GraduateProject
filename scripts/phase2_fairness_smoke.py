"""Two-seed smoke that the fair protocol shares initial-observation hashes.

This is not the main result and it is not a multi-seed performance table.
"""

from __future__ import annotations

import json
from pathlib import Path

from urbannoise.experiment import FAIR_PROTOCOL, EpisodeConfig, label_legacy_outputs, run_episode
from urbannoise.world import build_world


def main() -> None:
    out = Path("experiments/results/phase2_fairness_smoke")
    out.mkdir(parents=True, exist_ok=True)
    methods = ["nearest", "random_reach"]
    checks = []
    for seed in (0, 1):
        world = build_world(
            seed=seed,
            height=8,
            width=8,
            n_days=2,
            slots_per_day=6,
            n_human=4,
            n_machine=1,
            scenario="regular",
            prior_samples=6,
        )
        hashes = {}
        for method in methods:
            result = run_episode(world, method, 4.0, seed, EpisodeConfig(lead=1, per_slot_cap=2))
            hashes[method] = result["initial_obs_hash"]
        checks.append(
            {
                "seed": seed,
                "budget": 4.0,
                "scenario": "regular",
                "hashes_by_method": hashes,
                "hashes_match": len(set(hashes.values())) == 1,
                "initial_obs_hash": next(iter(hashes.values())),
            }
        )
    payload = {
        "kind": "smoke",
        "is_main_result": False,
        "note": "Two-seed smoke proving methods share initial-observation hashes under fair_v1. Not the main result and not a multi-seed performance table.",
        "protocol_name": FAIR_PROTOCOL,
        "methods": methods,
        "checks": checks,
    }
    (out / "hash_match.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    label_legacy_outputs(Path("experiments/results"))
    if not all(item["hashes_match"] for item in checks):
        raise SystemExit("initial observation hashes diverged")
    print(json.dumps({"kind": "smoke", "checks": len(checks), "match": True}, indent=2))


if __name__ == "__main__":
    main()

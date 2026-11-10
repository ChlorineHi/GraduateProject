# Legacy protocol archive

`experiments/results/main/`, `experiments/results/smoke/`, and `experiments/results/checkpoints/` are the Phase I runs.

Those files were produced before the shared-environment fix. Each method could draw a different `episode_seed`, so initial observations and random events were not shared. The column is still named `mae_causal`. Do not read those numbers as the Phase II `mae_available_at_t` comparison, and do not overwrite the files. `run_suite` refuses these directories unless the config sets `"protocol": "legacy_protocol"`.

Phase II writes under `experiments/results/phase2/`.

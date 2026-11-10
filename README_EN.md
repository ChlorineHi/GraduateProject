# UrbanNoiseLab

A runnable undergraduate system for predictive noise sampling and human–machine task assignment. The bundled city is synthetic and uses a virtual grid. It is not a map of Beijing or Tokyo.

Verified start:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cd apps/web && npm install
make demo
make api
```

In another shell, `cd apps/web && npm run dev -- --host 127.0.0.1 --port 5173`.

Demo accounts: `admin` / `DemoAdmin#2026`, `publisher` / `DemoPublish#2026`, `collector` / `DemoCollect#2026`. These passwords are for the local demo only.

`make test` runs pytest. `make experiment-smoke` writes to `experiments/results/phase2/smoke` and does not overwrite the legacy smoke directory. Linux setup uses `scripts/setup_linux.sh`, `start_linux.sh`, `test_linux.sh`, and `stop_linux.sh`. Docker Compose is not a supported path. The Phase II report is `docs/final-report/UrbanNoiseLab_系统完整报告_PhaseII.md`. Legacy numbers stay in `experiments/results/main` and are not the fair-protocol result. MU-PSA is an internal name and is not the MAE winner at every budget.

The Chinese system report is `docs/final-report/UrbanNoiseLab_系统完整报告.md`. MU-PSA is not the lowest-MAE method at every budget; use `experiments/results/main/summary.json`.

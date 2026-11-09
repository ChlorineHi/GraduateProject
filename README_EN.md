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

`make test`, `make experiment-smoke`, and `make report` are the test, small experiment, and PDF commands. Docker Compose was not executed here because no Docker daemon was available. See `deploy/README.md`.

The Chinese system report is `docs/final-report/UrbanNoiseLab_系统完整报告.md`. MU-PSA is not the lowest-MAE method at every budget; use `experiments/results/main/summary.json`.

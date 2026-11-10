# UrbanNoiseLab

A runnable undergraduate system for predictive noise sampling and human–machine task assignment. The bundled city is synthetic and uses a virtual grid. It is not a map of Beijing or Tokyo.

## Supported start

The supported path is a project virtualenv (`.venv`) and npm in `apps/web`. The Compose file and Dockerfiles under `deploy/unused/` are unused. Docker was not installed or executed for this release.

Linux:

```bash
bash scripts/setup_linux.sh
bash scripts/start_linux.sh
bash scripts/test_linux.sh
bash scripts/stop_linux.sh
```

Open http://127.0.0.1:5173 . The API listens on http://127.0.0.1:8000 . Both bind to 127.0.0.1 only. Logs and pid files are under `logs/`. `stop_linux.sh` signals only pid files whose command line belongs to this app. If the chosen port is already taken, start exits and leaves that process alone.

Override ports for one command when 8000 or 5173 is busy:

```bash
UNLAB_API_PORT=8010 UNLAB_WEB_PORT=5174 bash scripts/start_linux.sh
```

The Vite `/api` proxy reads `UNLAB_API_PORT`. The scripts keep these variables in the current process and do not change machine-wide configuration.

Windows scripts do not call `Set-ExecutionPolicy`. Use a process-scoped bypass:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop_windows.ps1
```

`make setup`, `make start`, `make stop`, and `make test` call the Linux scripts. `make api` and `make web` run the API and Vite in the foreground. `make demo` seeds an empty database.

## Demo accounts and environment

Demo accounts: `admin` / `DemoAdmin#2026`, `publisher` / `DemoPublish#2026`, `collector` / `DemoCollect#2026`. These passwords are for the local demo only.

`UNLAB_DATA_DIR` is the local data directory (default `./data`) for SQLite, imports, and generated worlds. `UNLAB_JWT_SECRET` signs demo login tokens. The value in `.env.example` is demo-only and must not be reused outside this demo. When `.env` is absent, setup copies `.env.example` to `.env` inside the repository.

`make test`, `make experiment-smoke`, and `make report` are the test, small experiment, and PDF commands.

The Chinese system report is `docs/final-report/UrbanNoiseLab_系统完整报告.md`. MU-PSA is not the lowest-MAE method at every budget; use `experiments/results/main/summary.json`.

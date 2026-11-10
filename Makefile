# Supported run path: a project virtualenv (.venv) and npm in apps/web.
# Scripts bind 127.0.0.1, write logs under logs/, and do not change machine-wide configuration.
# Compose files and Dockerfiles under deploy/unused/ are unused.

.PHONY: setup start stop test demo experiment-smoke report api web

PY ?= .venv/bin/python
export PYTHONPATH=src

setup:
	bash scripts/setup_linux.sh

start:
	bash scripts/start_linux.sh

stop:
	bash scripts/stop_linux.sh

test:
	bash scripts/test_linux.sh

demo:
	$(PY) -c "from urbannoise.settings import Settings; from urbannoise.db import init_db, make_engine, make_session_factory; from urbannoise.services import seed_if_needed; settings=Settings(); engine=make_engine(settings); init_db(engine); db=make_session_factory(engine)(); seed_if_needed(db, settings); db.close()"

experiment-smoke:
	$(PY) -m urbannoise.experiment --config experiments/configs/smoke.json

report:
	$(PY) scripts/render_report.py

api:
	$(PY) -m uvicorn urbannoise.api:app --host 127.0.0.1 --port $${UNLAB_API_PORT:-8000}

web:
	cd apps/web && npm run dev -- --host 127.0.0.1 --port $${UNLAB_WEB_PORT:-5173} --strictPort

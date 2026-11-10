.PHONY: demo test experiment-smoke report api
# Docker is not a supported target. Use scripts/*_linux.sh.

PY ?= .venv/bin/python
export PYTHONPATH=src

demo:
	$(PY) -c "from urbannoise.settings import Settings; from urbannoise.db import init_db, make_engine, make_session_factory; from urbannoise.services import seed_if_needed; settings=Settings(); engine=make_engine(settings); init_db(engine); db=make_session_factory(engine)(); seed_if_needed(db, settings); db.close()"

test:
	$(PY) -m pytest -q --tb=line

experiment-smoke:
	$(PY) -m urbannoise.experiment --config experiments/configs/smoke.json

report:
	$(PY) scripts/render_report.py docs/final-report/UrbanNoiseLab_完整系统报告.md docs/final-report/UrbanNoiseLab_完整系统报告.pdf
	$(PY) scripts/render_docx.py docs/final-report/UrbanNoiseLab_完整系统报告.md docs/final-report/UrbanNoiseLab_完整系统报告.docx

api:
	$(PY) -m uvicorn urbannoise.api:app --host 127.0.0.1 --port 8000

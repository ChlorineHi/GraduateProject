"""Record real timings for prediction, assignment episodes, and the HTTP API.

Numbers are written to experiments/results/performance.json. This is a measurement
script, not a performance target.
"""

from __future__ import annotations

import json
import platform
import time
import tracemalloc
from pathlib import Path

from fastapi.testclient import TestClient

from urbannoise.api import create_app
from urbannoise.experiment import run_episode
from urbannoise.settings import Settings
from urbannoise.world import build_world


def _episode(width: int, humans: int, machines: int, budget: float) -> dict:
    world = build_world(
        seed=3,
        height=width,
        width=width,
        n_days=2,
        slots_per_day=12,
        n_human=humans,
        n_machine=machines,
        scenario="regular",
        prior_samples=min(24, width * width // 2),
        sensor_sigma=1.5,
        accept_human=0.8,
        accept_machine=0.95,
    )
    tracemalloc.start()
    started = time.perf_counter()
    result = run_episode(world, "mupsa", budget, seed=3)
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "grid": width * width,
        "width": width,
        "humans": humans,
        "machines": machines,
        "budget": budget,
        "seconds": round(elapsed, 4),
        "peak_bytes": peak,
        "mae_causal": result.get("mae_causal"),
        "successful_tasks": result.get("successful_tasks"),
    }


def _api() -> dict:
    settings = Settings(
        database_url="sqlite:///./data/perf.db",
        jwt_secret="perf-secret-not-for-production-32bytes",
        auto_seed=True,
        data_dir="./data/perf",
    )
    samples = []
    with TestClient(create_app(settings)) as client:
        health_t = time.perf_counter()
        health = client.get("/api/health")
        health_ms = (time.perf_counter() - health_t) * 1000
        login = client.post("/api/auth/login", json={"username": "admin", "password": "DemoAdmin#2026"})
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        for path in ("/api/dashboard", "/api/map/frame?slot=20", "/api/tasks", "/api/predictions/noise?slot=20&model=idw"):
            started = time.perf_counter()
            response = client.get(path, headers=headers)
            samples.append({"path": path, "status": response.status_code, "ms": round((time.perf_counter() - started) * 1000, 2)})
        started = time.perf_counter()
        assigned = client.post("/api/assignments/run", headers=headers, json={"algorithm": "mupsa", "limit": 3})
        samples.append({"path": "POST /api/assignments/run", "status": assigned.status_code, "ms": round((time.perf_counter() - started) * 1000, 2)})
    return {"health_ms": round(health_ms, 2), "health_status": health.status_code, "calls": samples}


def main() -> None:
    episodes = [
        _episode(8, 8, 2, 8),
        _episode(12, 12, 3, 12),
        _episode(16, 16, 4, 16),
    ]
    payload = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": __import__("os").cpu_count(),
        "gpu": None,
        "note": "Single-process CPU timings on this cloud VM. No GPU was available. peak_bytes is tracemalloc, not RSS.",
        "episodes": episodes,
        "api": _api(),
    }
    out = Path("experiments/results/performance.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

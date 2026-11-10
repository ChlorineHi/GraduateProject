import json

from fastapi.testclient import TestClient

from urbannoise.api import create_app
from urbannoise.settings import Settings


def _client(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        data_dir=str(tmp_path / "data"),
        jwt_secret="test-secret-not-production-32bytes!!",
        auto_seed=True,
        cors_origins="http://localhost:5173",
    )
    return TestClient(create_app(settings))


def _login(client, username, password):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_login_and_closed_loop(tmp_path):
    with _client(tmp_path) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        failed = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert failed.status_code == 401
        admin = _login(client, "admin", "DemoAdmin#2026")
        publisher = _login(client, "publisher", "DemoPublish#2026")
        collector = _login(client, "collector", "DemoCollect#2026")
        assert client.get("/api/auth/me", headers=collector).json()["role"] == "collector"
        dash = client.get("/api/dashboard", headers=admin).json()
        assert dash["online_participants"] > 0
        frame = client.get("/api/map/frame", params={"slot": 10}, headers=admin).json()
        assert frame["coordinate_system"] == "synthetic_virtual_grid"
        assert frame["real_city"] is False
        assert "truth" not in frame["cells"][0]
        hidden = client.get("/api/map/frame", params={"slot": 10, "include_truth": True}, headers=collector)
        assert hidden.status_code == 403
        visible = client.get("/api/map/frame", params={"slot": 10, "include_truth": True}, headers=admin)
        assert visible.status_code == 200
        assert visible.json()["evaluation_only"] is True
        created = client.post(
            "/api/tasks",
            headers=publisher,
            json={"title": "交叉口抽查", "grid_x": 8, "grid_y": 8, "slot_start": 50, "slot_end": 54, "priority": 1, "budget_cost": 1, "algorithm": "mupsa"},
        )
        assert created.status_code == 200, created.text
        task_id = created.json()["id"]
        published = client.post(f"/api/tasks/{task_id}/transition", headers=publisher, json={"to_status": "published"})
        assert published.status_code == 200
        again = client.post(
            "/api/tasks",
            headers={**publisher, "Idempotency-Key": "task-create-unused"},
            json={"title": "幂等对象", "grid_x": 1, "grid_y": 1, "slot_start": 52, "slot_end": 53, "priority": 0.2, "budget_cost": 1},
        )
        assert again.status_code == 200
        assigned = client.post("/api/assignments/run", headers=publisher, json={"algorithm": "mupsa", "limit": 2})
        assert assigned.status_code == 200, assigned.text
        mine = client.get("/api/tasks", params={"mine": True}, headers=collector).json()
        assert mine["total"] >= 1
        target = mine["items"][0]
        accepted = client.post(f"/api/tasks/{target['id']}/transition", headers=collector, json={"to_status": "accepted"})
        assert accepted.status_code == 200, accepted.text
        started = client.post(f"/api/tasks/{target['id']}/transition", headers=collector, json={"to_status": "in_progress"})
        assert started.status_code == 200, started.text
        missing = client.post(f"/api/tasks/{target['id']}/transition", headers=collector, json={"to_status": "submitted"})
        assert missing.status_code == 422
        submitted = client.post(
            f"/api/tasks/{target['id']}/transition",
            headers=collector,
            json={"to_status": "submitted", "measurement_db": 58.5},
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "submitted"
        duplicate = client.post(
            f"/api/tasks/{target['id']}/transition",
            headers=collector,
            json={"to_status": "submitted", "measurement_db": 58.5},
        )
        assert duplicate.status_code == 409
        verified = client.post(f"/api/tasks/{target['id']}/transition", headers=publisher, json={"to_status": "verified"})
        completed = client.post(f"/api/tasks/{target['id']}/transition", headers=publisher, json={"to_status": "completed"})
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        stepped = client.post("/api/simulation/control", headers=admin, json={"action": "step", "steps": 1})
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["current_slot"] == dash_slot_plus(client, admin)
        exported = client.get("/api/exports/tasks", headers=publisher)
        assert exported.status_code == 200
        assert "交叉口抽查" in exported.text
        users = client.get("/api/users", headers=collector)
        assert users.status_code == 403
        created_user = client.post(
            "/api/users",
            headers=admin,
            json={"username": "collector2", "password": "DemoCollect#2026", "display_name": "第二参与者", "role": "collector"},
        )
        assert created_user.status_code == 200
        obs = client.get("/api/observations", headers=admin).json()
        assert any(item["laeq_db"] == 58.5 for item in obs["items"])
        assert verified.status_code == 200


def dash_slot_plus(client, headers):
    state = client.get("/api/simulation", headers=headers).json()
    return state["current_slot"]


def test_idempotent_transition(tmp_path):
    with _client(tmp_path) as client:
        publisher = _login(client, "publisher", "DemoPublish#2026")
        created = client.post(
            "/api/tasks",
            headers=publisher,
            json={"title": "幂等发布", "grid_x": 2, "grid_y": 2, "slot_start": 60, "slot_end": 62, "priority": 0.3, "budget_cost": 1},
        )
        task_id = created.json()["id"]
        headers = {**publisher, "Idempotency-Key": "publish-once"}
        first = client.post(f"/api/tasks/{task_id}/transition", headers=headers, json={"to_status": "published"})
        second = client.post(f"/api/tasks/{task_id}/transition", headers=headers, json={"to_status": "published"})
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["status"] == "published"
        # A different key cannot publish an already published task.
        third = client.post(f"/api/tasks/{task_id}/transition", headers=publisher, json={"to_status": "published"})
        assert third.status_code == 409
        _ = json.dumps(third.json())


def test_manifest_phase2_and_scenario_mode(tmp_path):
    phase2 = tmp_path / "phase2"
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        data_dir=str(tmp_path / "data"),
        phase2_dir=str(phase2),
        jwt_secret="test-secret-not-production-32bytes!!",
        auto_seed=True,
        cors_origins="http://localhost:5173",
    )
    with TestClient(create_app(settings)) as client:
        admin = _login(client, "admin", "DemoAdmin#2026")
        missing = client.get("/api/data/downloads", headers=admin)
        assert missing.status_code == 200, missing.text
        assert missing.json()["present"] is False
        assert missing.json()["items"] == []
        assert missing.json()["path"] == "data/manifests/download_manifest.json"
        preprocess = client.get("/api/data/preprocess", headers=admin).json()
        assert preprocess["present"] is False
        assert preprocess["items"] == []
        assert preprocess["view"] == "preprocess"

        manifest = tmp_path / "data" / "manifests" / "download_manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps(
                {
                    "items": [
                        {
                            "name": "YJMob100K",
                            "regime": "real_mobility",
                            "download_status": "absent",
                            "preprocess_status": "not_started",
                            "license": "see the data paper",
                            "spatial_span": "anonymous 500 m grid",
                            "quality_flags": ["virtual_grid"],
                        },
                        {
                            "name": "Aligned pair",
                            "regime": "fully_real",
                            "download_status": "complete",
                            "license": "fixture",
                            "user_count": 12,
                            "time_start": "2020-01-01",
                            "time_end": "2020-01-02",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        downloaded = client.get("/api/data/downloads", headers=admin).json()
        assert downloaded["present"] is True
        first, second = downloaded["items"]
        assert first["regime"] == "real_mobility"
        assert first["license"] == "see the data paper"
        assert first["quality_flags"] == ["virtual_grid"]
        assert "user_count" not in first
        assert "station_count" not in first
        assert "time_start" not in first
        assert second["user_count"] == 12
        assert second["regime"] == "fully_real"
        assert "station_count" not in second
        processed = client.get("/api/data/preprocess", headers=admin).json()
        assert processed["items"][0]["preprocess_status"] == "not_started"
        assert "user_count" not in processed["items"][0]

        manifest.write_text(
            json.dumps(
                {
                    "downloads": [{"name": "Only download", "download_status": "partial", "license": "L"}],
                    "preprocess": [{"name": "Only preprocess", "preprocess_status": "ready", "station_count": 4}],
                }
            ),
            encoding="utf-8",
        )
        split_download = client.get("/api/data/downloads", headers=admin).json()["items"]
        split_preprocess = client.get("/api/data/preprocess", headers=admin).json()["items"]
        assert split_download[0]["name"] == "Only download"
        assert "station_count" not in split_download[0]
        assert split_preprocess[0]["station_count"] == 4
        assert "user_count" not in split_preprocess[0]

        empty_phase = client.get("/api/experiments/phase2", headers=admin).json()
        assert empty_phase["present"] is False
        assert empty_phase["files"] == []
        assert empty_phase["path"] == "experiments/results/phase2"
        phase2.mkdir()
        (phase2 / "summary.json").write_text(
            json.dumps({"summary": [{"method": "mupsa", "mae": 1.5}, {"method": "random", "mae": 2.5}]}),
            encoding="utf-8",
        )
        filled = client.get("/api/experiments/phase2", headers=admin).json()
        assert filled["present"] is True
        assert filled["message"] is None
        assert filled["files"][0]["payload"]["summary"][0]["method"] == "mupsa"

        datasets = client.get("/api/datasets", headers=admin).json()["items"]
        assert {item["regime"] for item in datasets} == {"synthetic_demo"}
        mobility = next(item for item in datasets if item["kind"] == "mobility")
        noise = next(item for item in datasets if item["kind"] == "noise")
        assert mobility["regime_label"] == "Synthetic Demo"
        assert mobility["user_count"] > 0
        assert "user_count" not in noise

        before = client.get("/api/simulation", headers=admin).json()
        assert before["scenario_mode"] == "synthetic_demo"
        assert before["mode_label"] == "Synthetic Demo"
        assert before["real_run"] is False
        refused = client.post(
            "/api/simulation/control",
            headers=admin,
            json={"action": "reset", "scenario_mode": "fully_real", "scenario": "shift", "seed": 99, "budget": 3},
        )
        assert refused.status_code == 200, refused.text
        refused_body = refused.json()
        assert refused_body["scenario_mode"] == "synthetic_demo"
        assert refused_body["mode_label"] == "Synthetic Demo"
        assert refused_body["requested_scenario_mode"] == "fully_real"
        assert refused_body["mode_honored"] is False
        assert refused_body["real_run"] is False
        assert refused_body["real_city"] is False
        assert refused_body["seed"] == before["seed"]
        assert refused_body["scenario"] == before["scenario"]
        unknown = client.post("/api/simulation/control", headers=admin, json={"action": "reset", "scenario_mode": "beijing"})
        assert unknown.status_code == 422
        slot = client.get("/api/simulation", headers=admin).json()["current_slot"]
        stepped = client.post(
            "/api/simulation/control",
            headers=admin,
            json={"action": "step", "steps": 1, "scenario_mode": "real_noise"},
        )
        assert stepped.status_code == 200, stepped.text
        assert stepped.json()["scenario_mode"] == "synthetic_demo"
        assert stepped.json()["requested_scenario_mode"] == "real_noise"
        assert stepped.json()["current_slot"] == slot + 1
        reset = client.post(
            "/api/simulation/control",
            headers=admin,
            json={"action": "reset", "scenario_mode": "synthetic_demo", "scenario": "shift", "seed": 11},
        )
        assert reset.status_code == 200, reset.text
        assert reset.json()["scenario"] == "shift"
        assert reset.json()["seed"] == 11
        assert reset.json()["scenario_mode"] == "synthetic_demo"
        assert reset.json()["mode_honored"] is True
        frame = client.get("/api/map/frame", params={"slot": 10}, headers=admin).json()
        assert frame["anonymous"] is True
        assert frame["basemap"] is None
        assert frame["real_city"] is False
        assert "匿名" in frame["warning"]
        assert "YJMob" in frame["warning"]

"""HTTP clock for real_mobility and real_noise.

The demo seed may call build_world before these requests. The counter below
starts after that seed and fails if the scenario run itself builds a world.
"""

import csv
from pathlib import Path

from fastapi.testclient import TestClient

from urbannoise.api import create_app
from urbannoise.scenarios import cell_id
from urbannoise.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        data_dir=str(tmp_path / "data"),
        jwt_secret="test-secret-not-production-32bytes!!",
        auto_seed=True,
        cors_origins="http://localhost:5173",
    )


def _forbid_build_world(monkeypatch):
    calls = {"n": 0}

    def boom(*_args, **_kwargs):
        calls["n"] += 1
        raise AssertionError("build_world was used")

    monkeypatch.setattr("urbannoise.world.build_world", boom)
    monkeypatch.setattr("urbannoise.services.build_world", boom)
    return calls


def _login(client: TestClient) -> dict:
    response = client.post("/api/auth/login", json={"username": "admin", "password": "DemoAdmin#2026"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _write_track(path: Path, later_rows: list[tuple[int, int, int]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["participant_id", "day", "timeslot", "x", "y", "data_source", "coordinate_system", "slots_per_day", "schema_example"]
        )
        writer.writerow(["exa", 0, 0, 0, 0, "synthetic_shaped_real_schema_example", "fixture_virtual_grid", 4, "not_a_city_extract"])
        for timeslot, x_coord, y_coord in later_rows:
            writer.writerow(
                ["exa", 0, timeslot, x_coord, y_coord, "synthetic_shaped_real_schema_example", "fixture_virtual_grid", 4, "not_a_city_extract"]
            )


def test_real_mobility_clock_executes_supplied_track(tmp_path, monkeypatch):
    with TestClient(create_app(_settings(tmp_path))) as client:
        headers = _login(client)
        calls = _forbid_build_world(monkeypatch)
        selected = client.post(
            "/api/simulation/control",
            headers=headers,
            json={"action": "select_scenario", "mode": "real_mobility"},
        )
        assert selected.status_code == 200, selected.text
        assert selected.json()["uses_build_world"] is False

        state = client.get("/api/simulation", headers=headers)
        assert state.status_code == 200, state.text
        clock = state.json()
        assert clock["scenario"] == "real_mobility"
        assert clock["current_slot"] == 0
        assert clock["uses_build_world"] is False
        exa = next(person for person in clock["participants"] if person["name"] == "exa")
        exb = next(person for person in clock["participants"] if person["name"] == "exb")
        assert (exa["x"], exa["y"], exa["cell"]) == (0, 0, cell_id(0, 0))
        assert (exb["x"], exb["y"], exb["cell"]) == (2, 2, cell_id(2, 2))

        frame = client.get("/api/map/frame", headers=headers, params={"slot": 0})
        assert frame.status_code == 200, frame.text
        shown = {person["name"]: person for person in frame.json()["participants"]}
        assert (shown["exa"]["x"], shown["exa"]["y"]) == (0, 0)
        assert (shown["exb"]["x"], shown["exb"]["y"]) == (2, 2)
        assert frame.json()["uses_build_world"] is False
        assert frame.json()["width"] == 3
        assert "truth" not in frame.json()["cells"][0]

        assigned = client.post(
            "/api/simulation/control",
            headers=headers,
            json={
                "action": "assign",
                "assignments": [
                    {"participant": "exa", "x": 1, "y": 0, "slot": 1},
                    {"participant": "exa", "x": 2, "y": 2, "slot": 1},
                ],
            },
        )
        assert assigned.status_code == 200, assigned.text
        body = assigned.json()
        assert body["uses_build_world"] is False
        decision = body["decisions"]["1"]
        assert decision["decision_slot"] == 0
        assert decision["slots_visible"] == 1
        assert cell_id(1, 0) not in decision["cells"]
        before = sorted(item["grid_id"] for item in body["assignments"])
        assert before == sorted([cell_id(1, 0), cell_id(2, 2)])
        miss = next(item for item in body["assignments"] if item["grid_id"] == cell_id(2, 2))
        assert (miss["grid_x"], miss["grid_y"]) == (2, 2)

        # The clock executes the current slot, then advances. Slot 1 is due on the second tick.
        stepped = client.post("/api/simulation/control", headers=headers, json={"action": "step", "steps": 2})
        assert stepped.status_code == 200, stepped.text
        step_body = stepped.json()
        assert step_body["current_slot"] == 2
        assert step_body["uses_build_world"] is False
        executed = step_body["executed"]
        assert len(executed) == 2
        successes = [item for item in executed if item["success"]]
        failures = [item for item in executed if not item["success"]]
        assert len(successes) == 1
        assert successes[0]["reason"] == "on_task_cell"
        assert successes[0]["task_cell"] == cell_id(1, 0)
        assert successes[0]["actual_cell"] == cell_id(1, 0)
        assert successes[0]["noise"]["label"] == "synthetic"
        assert successes[0]["noise"]["is_synthetic"] is True
        assert successes[0]["noise"]["data_origin"] == "synthetic_noise_field"
        assert successes[0]["noise"]["source"] == "synthetic"
        assert len(failures) == 1
        assert failures[0]["reason"] == "off_task_cell"
        assert failures[0]["noise"] is None
        assert failures[0]["task_cell"] == cell_id(2, 2)

        tasks = client.get("/api/tasks", headers=headers)
        assert tasks.status_code == 200, tasks.text
        assert sorted(item["grid_id"] for item in tasks.json()["items"]) == before
        observations = client.get("/api/observations", headers=headers).json()["items"]
        synthetic = [item for item in observations if item["source"] == "synthetic_noise_field"]
        assert len(synthetic) == 1
        assert synthetic[0]["indicator"] == "synthetic_laeq_db"
        assert synthetic[0]["grid_id"] == cell_id(1, 0)
        assert synthetic[0]["slot"] == 1
        assert calls["n"] == 0


def test_real_mobility_assignment_ignores_cells_after_decision_slot(tmp_path, monkeypatch):
    early = tmp_path / "early.csv"
    late = tmp_path / "late.csv"
    _write_track(early, [(1, 1, 0), (2, 1, 0)])
    _write_track(late, [(1, 5, 5), (2, 6, 6)])
    with TestClient(create_app(_settings(tmp_path))) as client:
        headers = _login(client)
        calls = _forbid_build_world(monkeypatch)

        def assign(path: Path) -> dict:
            selected = client.post(
                "/api/simulation/control",
                headers=headers,
                json={"action": "select_scenario", "mode": "real_mobility", "mobility_path": str(path)},
            )
            assert selected.status_code == 200, selected.text
            response = client.post(
                "/api/simulation/control",
                headers=headers,
                json={"action": "assign", "assignments": [{"participant": "exa", "x": 1, "y": 0, "slot": 1}]},
            )
            assert response.status_code == 200, response.text
            return response.json()

        first = assign(early)
        second = assign(late)
        assert first["decisions"]["1"]["slots_visible"] == second["decisions"]["1"]["slots_visible"] == 1
        assert first["decisions"]["1"]["cells"] == second["decisions"]["1"]["cells"]
        assert cell_id(1, 0) not in first["decisions"]["1"]["cells"]
        assert cell_id(5, 5) not in second["decisions"]["1"]["cells"]
        assert first["decisions"]["1"]["reach"] == second["decisions"]["1"]["reach"]
        assert first["assignments"][0]["grid_id"] == second["assignments"][0]["grid_id"] == cell_id(1, 0)

        _write_track(late, [(1, 8, 8), (2, 6, 6)])
        stepped = client.post("/api/simulation/control", headers=headers, json={"action": "step", "steps": 2})
        assert stepped.status_code == 200, stepped.text
        executed = stepped.json()["executed"]
        assert len(executed) == 1
        assert executed[0]["success"] is False
        assert executed[0]["reason"] == "off_task_cell"
        assert executed[0]["task_cell"] == cell_id(1, 0)
        assert executed[0]["actual_cell"] == cell_id(8, 8)
        assert executed[0]["noise"] is None
        tasks = client.get("/api/tasks", headers=headers)
        assert tasks.json()["items"][0]["grid_id"] == cell_id(1, 0)
        assert calls["n"] == 0


def test_real_noise_step_and_predict_use_only_revealed_observations(tmp_path, monkeypatch):
    with TestClient(create_app(_settings(tmp_path))) as client:
        headers = _login(client)
        calls = _forbid_build_world(monkeypatch)
        selected = client.post(
            "/api/simulation/control",
            headers=headers,
            json={"action": "select_scenario", "mode": "real_noise", "seed": 2},
        )
        assert selected.status_code == 200, selected.text
        assert selected.json()["uses_build_world"] is False
        assert selected.json()["full_city_truth"] is False

        predicted = client.get("/api/predictions/noise", headers=headers, params={"slot": 0, "model": "idw"})
        assert predicted.status_code == 200, predicted.text
        report = predicted.json()
        assert report["uses_build_world"] is False
        assert report["full_city_truth"] is False
        assert report["trained_on"] == "revealed_observations"
        trained = set(report["trained_row_ids"])
        locked = set(report["locked_row_ids"])
        hidden = set(report["hidden_row_ids"])
        assert trained
        assert locked
        assert hidden
        assert trained.isdisjoint(locked)
        assert trained.isdisjoint(hidden)
        assert "observed" not in report["by_indicator"]["laeq"]
        for item in report["hidden_catalog"] + report["locked_catalog"]:
            assert "db" not in item

        hidden_row = report["hidden_catalog"][0]
        revealed = client.post(
            "/api/simulation/control",
            headers=headers,
            json={"action": "reveal", "time": hidden_row["time"], "grid_id": hidden_row["grid_id"]},
        )
        assert revealed.status_code == 200, revealed.text
        assert revealed.json()["revealed"] is True
        assert revealed.json()["db"] is not None
        assert revealed.json()["full_city_truth"] is False
        again = client.get("/api/predictions/noise", headers=headers, params={"slot": 0}).json()
        assert hidden_row["row_id"] in again["trained_row_ids"]
        assert set(again["trained_row_ids"]).isdisjoint(set(again["locked_row_ids"]))

        locked_row = report["locked_catalog"][0]
        sealed = client.post(
            "/api/simulation/control",
            headers=headers,
            json={"action": "reveal", "time": locked_row["time"], "grid_id": locked_row["grid_id"]},
        )
        assert sealed.status_code == 200, sealed.text
        assert sealed.json()["revealed"] is False
        assert sealed.json()["db"] is None
        assert sealed.json()["reason"] == "locked_test"
        after_seal = client.get("/api/predictions/noise", headers=headers, params={"slot": 0}).json()
        assert locked_row["row_id"] not in after_seal["trained_row_ids"]

        stepped = client.post("/api/simulation/control", headers=headers, json={"action": "step", "steps": 1})
        assert stepped.status_code == 200, stepped.text
        holdout = stepped.json()["holdout"]
        assert stepped.json()["uses_build_world"] is False
        assert holdout["trained_on"] == "revealed_observations"
        assert holdout["full_city_truth"] is False
        assert set(holdout["trained_row_ids"]).isdisjoint(set(holdout["locked_row_ids"]))
        assert hidden_row["row_id"] in holdout["trained_row_ids"]
        assert locked_row["row_id"] not in holdout["trained_row_ids"]
        assert calls["n"] == 0

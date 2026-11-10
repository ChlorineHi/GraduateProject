from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from urbannoise.api import create_app
from urbannoise.errors import AppError
from urbannoise.scenarios import (
    ScenarioUnavailable,
    cell_id,
    load_mobility_table,
    open_scenario,
    trajectory_from_frame,
)
from urbannoise.services import rebuild_world, select_scenario_mode
from urbannoise.settings import Settings


def _track(rows: list[tuple], slots_per_day: int = 4) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "participant_id": participant_id,
                "day": day,
                "timeslot": timeslot,
                "x": x_coord,
                "y": y_coord,
                "data_source": "synthetic_shaped_real_schema_example",
                "coordinate_system": "fixture_virtual_grid",
                "slots_per_day": slots_per_day,
                "schema_example": "not_a_city_extract",
            }
            for participant_id, day, timeslot, x_coord, y_coord in rows
        ]
    )


def _forbid_build_world(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("real_mobility called build_world")

    monkeypatch.setattr("urbannoise.world.build_world", boom)
    monkeypatch.setattr("urbannoise.services.build_world", boom)
    import urbannoise.scenarios as scenarios

    assert not hasattr(scenarios, "build_world")


def test_success_follows_the_supplied_later_cell_and_skips_build_world(monkeypatch):
    _forbid_build_world(monkeypatch)
    frame = _track(
        [
            ("walker", 0, 0, 0, 0),
            ("walker", 0, 1, 3, 1),
            ("walker", 0, 2, 3, 1),
        ]
    )
    scenario = open_scenario("real_mobility", mobility_frame=frame, seed=11)
    fingerprint = scenario.table.fingerprint()
    later = cell_id(3, 1)
    earlier = cell_id(0, 0)

    hit = scenario.execute_task("walker", later, task_slot=1, decision_slot=0)
    miss = scenario.execute_task("walker", earlier, task_slot=1, decision_slot=0)
    missing = scenario.execute_task("other", later, task_slot=1, decision_slot=0)

    assert hit["success"] is True
    assert hit["reason"] == "on_task_cell"
    assert hit["actual_cell"] == later
    assert miss["success"] is False
    assert miss["reason"] == "off_task_cell"
    assert miss["noise"] is None
    assert missing["success"] is False
    assert missing["reason"] == "no_location"
    assert scenario.table.fingerprint() == fingerprint
    assert scenario.table.read_cell("walker", 2, purpose="execution") == later
    summary = select_scenario_mode("real_mobility", world={})
    assert summary["uses_build_world"] is False
    assert summary["participants"] == ["exa", "exb"]


def test_synthetic_noise_is_sampled_only_after_success_and_is_labeled():
    frame = _track([("walker", 0, 0, 0, 0), ("walker", 0, 1, 2, 0)])
    scenario = open_scenario("real_mobility", mobility_frame=frame, seed=3)

    def boom(**_kwargs):
        raise RuntimeError("sampled")

    scenario.sample_synthetic_noise = boom
    missed = scenario.execute_task("walker", cell_id(0, 0), task_slot=1, decision_slot=0)
    assert missed["success"] is False
    assert missed["noise"] is None
    with pytest.raises(RuntimeError, match="sampled"):
        scenario.execute_task("walker", cell_id(2, 0), task_slot=1, decision_slot=0)

    fresh = open_scenario("real_mobility", mobility_frame=frame, seed=3)
    hit = fresh.execute_task("walker", cell_id(2, 0), task_slot=1, decision_slot=0, sigma=0.0)
    assert hit["success"] is True
    assert fresh.synthetic_sample_count == 1
    assert hit["noise"]["label"] == "synthetic"
    assert hit["noise"]["is_synthetic"] is True
    assert hit["noise"]["data_origin"] == "synthetic_noise_field"
    assert hit["noise"]["source"] == "synthetic"
    assert hit["noise"]["full_city_truth"] is False
    assert hit["noise"]["real_city"] is False
    missed_again = fresh.execute_task("walker", cell_id(9, 9), task_slot=1, decision_slot=0)
    assert missed_again["noise"] is None
    assert fresh.synthetic_sample_count == 1


def test_missing_file_uses_marked_schema_fixture_not_yjmob():
    scenario = open_scenario("real_mobility")
    summary = scenario.to_summary()
    text = (Path(__file__).parent / "fixtures" / "real_mobility_schema_example.csv").read_text(encoding="utf-8").lower()
    assert summary["fixture_fallback"] is True
    assert summary["example_schema"] is True
    assert summary["coordinate_system"] == "fixture_virtual_grid"
    assert summary["data_source"] == ["synthetic_shaped_real_schema_example"]
    assert "yjmob" not in text
    assert "yjmob" not in summary["coordinate_system"].lower()
    assert summary["georegistered_yjmob"] is False
    assert summary["mobility"]["latitude_assigned"] is False
    assert summary["noise_field"]["label"] == "synthetic"
    hit = scenario.execute_task("exa", cell_id(1, 0), task_slot=1, decision_slot=0)
    early_cell = scenario.execute_task("exa", cell_id(0, 0), task_slot=1, decision_slot=0)
    assert hit["success"] is True
    assert early_cell["success"] is False


def test_explicit_missing_path_is_not_replaced(tmp_path):
    with pytest.raises(ScenarioUnavailable, match="does not exist"):
        open_scenario("real_mobility", mobility_path=tmp_path / "absent.csv")


def test_duplicate_participant_slot_is_rejected():
    with pytest.raises(ScenarioUnavailable, match="duplicate"):
        trajectory_from_frame(_track([("p", 0, 0, 0, 0), ("p", 0, 0, 1, 0)]))


def test_parquet_path_uses_the_parquet_reader(monkeypatch, tmp_path):
    path = tmp_path / "track.parquet"
    path.write_bytes(b"not-a-real-parquet")
    frame = _track([("p", 0, 0, 1, 2), ("p", 0, 1, 1, 2)])

    def fake_read(target, **_kwargs):
        assert str(target).endswith("track.parquet")
        return frame

    monkeypatch.setattr("urbannoise.scenarios.pd.read_parquet", fake_read)
    table = load_mobility_table(path)
    assert table.read_cell("p", 1, purpose="execution") == cell_id(1, 2)


def test_synthetic_mode_still_calls_build_world():
    scenario = open_scenario(
        "synthetic",
        seed=1,
        height=8,
        width=8,
        n_days=1,
        slots_per_day=4,
        n_human=2,
        n_machine=1,
        scenario="regular",
        prior_samples=2,
    )
    summary = scenario.to_summary()
    assert summary["mode"] == "synthetic"
    assert summary["uses_build_world"] is True
    assert summary["coordinate_system"] == "synthetic_virtual_grid"
    assert summary["real_city"] is False
    assert scenario.world.n_slots == 4
    assert len(scenario.world.agents) == 3


def test_unknown_mode_is_rejected():
    with pytest.raises(ScenarioUnavailable, match="Unknown scenario mode"):
        open_scenario("beijing")


def test_rebuild_world_refuses_real_mobility_without_calling_build_world(monkeypatch):
    _forbid_build_world(monkeypatch)
    with pytest.raises(AppError) as caught:
        rebuild_world(None, None, {"scenario": "real_mobility", "seed": 1}, None)
    assert caught.value.status == 409


def test_http_reset_activates_real_mobility_on_the_fixture_track(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        data_dir=str(tmp_path / "data"),
        jwt_secret="test-secret-not-production-32bytes!!",
        auto_seed=True,
        cors_origins="http://localhost:5173",
    )
    with TestClient(create_app(settings)) as client:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "DemoAdmin#2026"})
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        selected = client.post(
            "/api/simulation/control",
            headers=headers,
            json={"action": "reset", "scenario": "real_mobility"},
        )
        assert selected.status_code == 200, selected.text
        body = selected.json()
        assert body["mode"] == "real_mobility"
        assert body["uses_build_world"] is False
        assert body["fixture_fallback"] is True
        assert body["participants"] == ["exa", "exb"]
        assert "yjmob" not in body["coordinate_system"].lower()
        state = client.get("/api/simulation", headers=headers)
        assert state.status_code == 200
        clock = state.json()
        assert clock["scenario"] == "real_mobility"
        assert clock["uses_build_world"] is False
        assert clock["current_slot"] == 0
        exa = next(person for person in clock["participants"] if person["name"] == "exa")
        assert (exa["x"], exa["y"]) == (0, 0)

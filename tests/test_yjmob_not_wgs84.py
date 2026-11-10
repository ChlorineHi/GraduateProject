import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from urbannoise.api import create_app
from urbannoise.dataio import read_yjmob_csv
from urbannoise.errors import AppError
from urbannoise.scenarios import ScenarioUnavailable, cell_id, open_scenario, trajectory_from_frame
from urbannoise.services import select_scenario_mode
from urbannoise.settings import Settings


def _forbid_build_world(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("fully_real called build_world")

    monkeypatch.setattr("urbannoise.world.build_world", boom)
    monkeypatch.setattr("urbannoise.services.build_world", boom)


def _yjmob_frame(tmp_path):
    path = tmp_path / "yj.csv"
    path.write_text("uid,day,timeslot,x,y\n7,1,10,12,8\n7,1,11,15,8\n", encoding="utf-8")
    return read_yjmob_csv(path)


def _wgs84_noise():
    return pd.DataFrame(
        [
            {
                "latitude": 35.6,
                "longitude": 139.7,
                "time": "2020-01-01T00:00:00",
                "db": 55.0,
                "indicator": "laeq",
                "source": "unit_test_noise",
                "coordinate_system": "WGS84",
            }
        ]
    )


def test_fixture_schema_examples_are_not_yjmob_extracts():
    fixture_dir = Path(__file__).parent / "fixtures"
    mobility = (fixture_dir / "real_mobility_schema_example.csv").read_text(encoding="utf-8").lower()
    noise = (fixture_dir / "real_noise_schema_example.csv").read_text(encoding="utf-8").lower()
    assert "yjmob" not in mobility
    assert "yjmob" not in noise
    assert "synthetic_shaped_real_schema_example" in mobility
    assert "fixture_virtual_grid" in mobility
    assert "not_a_city" in noise


def test_yjmob_adapter_keeps_virtual_grid_coordinates(tmp_path):
    frame = _yjmob_frame(tmp_path)
    assert frame.loc[0, "coordinate_system"] == "yjmob_virtual_500m"
    assert pd.isna(frame.loc[0, "latitude"])
    assert pd.isna(frame.loc[0, "longitude"])
    table = trajectory_from_frame(frame, slots_per_day=48)
    assert table.yjmob is True
    assert table.has_geographic_coordinates is False
    assert table.coordinate_system == "yjmob_virtual_500m"
    assert table.read_cell("7", 48 + 10, purpose="execution") == cell_id(12, 8)
    summary = table.to_summary()
    assert summary["latitude_assigned"] is False
    assert summary["longitude_assigned"] is False
    assert summary["georegistered_yjmob"] is False


def test_yjmob_rows_with_latitude_are_rejected(tmp_path):
    frame = _yjmob_frame(tmp_path)
    frame["latitude"] = 35.6
    frame["longitude"] = 139.7
    with pytest.raises(ScenarioUnavailable, match="WGS84"):
        trajectory_from_frame(frame, slots_per_day=48)


def test_fully_real_requires_an_overlap_manifest(monkeypatch):
    _forbid_build_world(monkeypatch)
    with pytest.raises(ScenarioUnavailable, match="overlap"):
        open_scenario("fully_real")
    with pytest.raises(ScenarioUnavailable, match="boolean"):
        open_scenario("fully_real", manifest={"geography_overlap": "true", "time_overlap": "true"})
    with pytest.raises(ScenarioUnavailable, match="georegister"):
        open_scenario(
            "fully_real",
            manifest={"geography_overlap": True, "time_overlap": True, "georegister_yjmob_to_wgs84": True},
        )
    with pytest.raises(AppError, match="overlap") as caught:
        select_scenario_mode("fully_real")
    assert caught.value.status == 409
    assert "WGS84" in caught.value.message


def test_manifest_file_without_overlap_is_rejected(tmp_path, monkeypatch):
    _forbid_build_world(monkeypatch)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"geography_overlap": False, "time_overlap": False}), encoding="utf-8")
    with pytest.raises(ScenarioUnavailable, match="geography_overlap=False"):
        open_scenario("fully_real", manifest_path=path)


def test_yjmob_is_not_joined_onto_wgs84_even_if_manifest_claims_overlap(tmp_path, monkeypatch):
    _forbid_build_world(monkeypatch)
    mobility = _yjmob_frame(tmp_path)
    with pytest.raises(ScenarioUnavailable, match="not converted") as caught:
        open_scenario(
            "fully_real",
            mobility_frame=mobility,
            noise_frame=_wgs84_noise(),
            manifest={
                "geography_overlap": True,
                "time_overlap": True,
                "mobility_coordinate_system": "yjmob_virtual_500m",
                "noise_coordinate_system": "WGS84",
            },
            slots_per_day=48,
        )
    message = str(caught.value)
    assert "georegister" in message
    assert "WGS84" in message
    assert "not converted" in message


def test_default_fixtures_are_not_forced_into_one_map(monkeypatch):
    _forbid_build_world(monkeypatch)
    with pytest.raises(ScenarioUnavailable, match="coordinate systems differ"):
        open_scenario(
            "fully_real",
            manifest={"geography_overlap": True, "time_overlap": True},
        )


def test_matching_manifest_does_not_invent_coordinates(monkeypatch):
    _forbid_build_world(monkeypatch)
    mobility = pd.DataFrame(
        [
            {
                "participant_id": "p",
                "day": 0,
                "timeslot": 0,
                "x": 1,
                "y": 1,
                "data_source": "synthetic_shaped_real_schema_example",
                "coordinate_system": "fixture_virtual_grid",
                "slots_per_day": 4,
                "schema_example": "not_a_city_extract",
            },
            {
                "participant_id": "p",
                "day": 0,
                "timeslot": 1,
                "x": 2,
                "y": 1,
                "data_source": "synthetic_shaped_real_schema_example",
                "coordinate_system": "fixture_virtual_grid",
                "slots_per_day": 4,
                "schema_example": "not_a_city_extract",
            },
        ]
    )
    noise = pd.DataFrame(
        [
            {
                "grid_id": 1,
                "x": 1,
                "y": 1,
                "time": "2020-01-01T00:00:00",
                "db": 50.0,
                "indicator": "laeq",
                "source": "synthetic_shaped_real_schema_example",
                "coordinate_system": "fixture_virtual_grid",
            }
        ]
    )
    session = open_scenario(
        "fully_real",
        mobility_frame=mobility,
        noise_frame=noise,
        manifest={"geography_overlap": True, "time_overlap": True},
    )
    summary = session.to_summary()
    assert summary["mode"] == "fully_real"
    assert summary["uses_build_world"] is False
    assert summary["geography_overlap"] is True
    assert summary["time_overlap"] is True
    assert summary["georegistered_yjmob"] is False
    assert summary["real_city"] is False
    assert summary["full_city_truth"] is False
    assert summary["mobility"]["latitude_assigned"] is False
    assert summary["mobility"]["longitude_assigned"] is False
    assert "latitude" not in summary["mobility"]
    assert session.table.has_geographic_coordinates is False
    assert session.noise["latitude"].isna().all()
    assert session.noise["longitude"].isna().all()
    blob = json.dumps(summary)
    assert "wgs84" not in blob.lower()


def test_http_fully_real_without_manifest_returns_the_refusal(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        data_dir=str(tmp_path / "data"),
        jwt_secret="test-secret-not-production-32bytes!!",
        auto_seed=True,
        cors_origins="http://localhost:5173",
    )
    with TestClient(create_app(settings)) as client:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "DemoAdmin#2026"})
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        selected = client.post("/api/simulation/control", headers=headers, json={"action": "select_scenario", "mode": "fully_real"})
        assert selected.status_code == 409, selected.text
        message = selected.json()["error"]["message"]
        assert "overlap" in message
        assert "WGS84" in message
        reset = client.post("/api/simulation/control", headers=headers, json={"action": "reset", "scenario": "fully_real"})
        assert reset.status_code == 409, reset.text
        assert "georegister" in reset.json()["error"]["message"]
        state = client.get("/api/simulation", headers=headers)
        assert state.status_code == 200
        assert state.json()["scenario"] == "complex"
        assert state.json()["config"].get("scenario_mode") not in {"fully_real", "real_mobility", "real_noise"}

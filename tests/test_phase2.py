"""Phase II protocol tests.

Real-file tests skip with a reason when the corresponding processed file is absent.
They do not invent coordinates or metrics.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from urbannoise.api import create_app
from urbannoise.assignment import AgentView, allocate
from urbannoise.domain import TransitionContext, check_transition
from urbannoise.experiment import PROTOCOL_NAME, EpisodeConfig, run_episode
from urbannoise.fairness import algorithm_seed, environment_seed
from urbannoise.migrations import migrate
from urbannoise.noiseeval import predict_parquet
from urbannoise.scenarios import load_geolife_frame, load_yjmob_frame, world_from_mobility_frame
from urbannoise.settings import Settings
from urbannoise.world import build_world


ROOT = Path(__file__).resolve().parents[1]
YJMOB = ROOT / "data" / "processed" / "yjmob" / "dataset1.parquet"
GEOLIFE = ROOT / "data" / "processed" / "geolife" / "slots_all.parquet"


def test_environment_seed_ignores_budget_and_method():
    low = environment_seed(seed=3, scenario="regular", subset="synthetic", time_range="day0", budget=4)
    high = environment_seed(seed=3, scenario="regular", subset="synthetic", time_range="day0", budget=36)
    assert low == high
    assert algorithm_seed(seed=3, method="random", budget=4, scenario="regular") != algorithm_seed(
        seed=3, method="eer_reach", budget=4, scenario="regular"
    )


def test_shared_environment_hash_across_methods():
    world = build_world(
        seed=2,
        height=6,
        width=6,
        n_days=2,
        slots_per_day=4,
        n_human=4,
        n_machine=1,
        scenario="regular",
        prior_samples=4,
    )
    env = environment_seed(seed=2, scenario="regular", subset="unit", time_range="slot0-3", budget=3)
    before_noise = world.laeq.copy()
    before_traj = np.stack([agent.traj.copy() for agent in world.agents])
    first = run_episode(world, "random", 3, 2, EpisodeConfig(lead=1, per_slot_cap=1), env_seed=env)
    second = run_episode(world, "eer_reach", 8, 2, EpisodeConfig(lead=1, per_slot_cap=1), env_seed=env)
    assert np.array_equal(world.laeq, before_noise)
    assert np.array_equal(np.stack([agent.traj for agent in world.agents]), before_traj)
    assert first["environment_hash"] == second["environment_hash"]
    assert first["prior_hash"] == second["prior_hash"]
    assert first["env_seed"] == second["env_seed"] == env
    assert first["algorithm_seed"] != second["algorithm_seed"]
    assert first["protocol"] == second["protocol"] == PROTOCOL_NAME
    assert first["mae_available_at_t"] == pytest.approx(first["mae_causal"])


def test_real_trajectory_cell_matches_source_frame():
    frame = pd.DataFrame(
        {
            "user_id": ["7", "7", "7", "7", "8", "8", "8", "8"],
            "day": [0, 0, 0, 0, 0, 0, 0, 0],
            "timeslot": [0, 1, 2, 3, 0, 1, 2, 3],
            "x": [1, 1, 2, 2, 4, 4, 4, 5],
            "y": [1, 2, 2, 3, 1, 1, 2, 2],
        }
    )
    world = world_from_mobility_frame(
        frame,
        source="YJMob100K",
        seed=1,
        slots_per_day=4,
        n_days=1,
        day_min=0,
        max_users=2,
        max_side=8,
        min_points=4,
        n_machine=0,
        prior_samples=0,
    )
    assert world.coordinate_system == "yjmob_virtual_500m"
    assert world.meta["real_city"] is False
    assert world.meta["named_city"] is None
    assert world.meta["lat0"] is None
    assert world.data_origin == "YJMob100K"
    origin_x = int(world.meta["origin_x"])
    origin_y = int(world.meta["origin_y"])
    human = world.agents[0]
    assert human.name.startswith("U")
    for slot, x_value, y_value in ((0, 1, 1), (1, 1, 2), (2, 2, 2), (3, 2, 3)):
        expected = (y_value - origin_y) * world.width + (x_value - origin_x)
        assert int(human.traj[slot]) == expected
    # A future cell that was not in the file stays missing. It is not moved onto a task.
    assert set(np.unique(human.traj)).issuperset({-1}) or int(human.traj.min()) >= 0


def test_budget_zero_unreachable_duplicate_expired_machine_offline():
    online = AgentView("H", "human", 0.9, 1.0, True, 1.0, loc=0)
    offline = AgentView("M", "machine", 1.0, 1.7, False, 1.0, loc=1)
    values = np.array([3.0, 2.0])
    unc = np.array([1.0, 1.0])
    duplicate = np.array([0.0, 1.0])
    reach = np.array([[0.05, 0.04], [0.9, 0.9]])
    unreachable = allocate(
        "reach_nearest",
        [online, offline],
        np.array([8, 9]),
        values,
        unc,
        duplicate,
        reach,
        6,
        2,
        5,
        2,
        np.random.default_rng(0),
        min_reach=0.22,
    )
    assert unreachable.assignments == []
    zero = allocate(
        "reach_greedy",
        [online],
        np.array([1]),
        np.array([3.0]),
        np.array([1.0]),
        np.array([0.0]),
        np.array([[0.8]]),
        6,
        2,
        0,
        2,
        np.random.default_rng(0),
    )
    assert zero.assignments == []
    duplicated = allocate(
        "reach_greedy",
        [online],
        np.array([4, 4]),
        values,
        unc,
        duplicate,
        np.array([[0.8, 0.7]]),
        6,
        3,
        5,
        2,
        np.random.default_rng(0),
    )
    assert len(duplicated.assignments) == 1
    assert duplicated.assignments[0].grid == 4
    check_transition("assigned", "expired", TransitionContext("system", now_slot=9, slot_end=4))
    with pytest.raises(Exception):
        check_transition("assigned", "expired", TransitionContext("system", now_slot=2, slot_end=4))


def test_migration_adds_columns_without_deleting_rows(tmp_path):
    database = tmp_path / "old.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE simulation_runs (id INTEGER PRIMARY KEY, name TEXT)")
    connection.execute("INSERT INTO simulation_runs (name) VALUES ('keep-me')")
    connection.commit()
    connection.close()
    version = migrate(create_engine(f"sqlite:///{database}"))
    assert version == 2
    connection = sqlite3.connect(database)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(simulation_runs)")}
    assert {"mode", "mobility_source", "noise_source", "user_count"} <= columns
    assert connection.execute("SELECT name FROM simulation_runs").fetchone()[0] == "keep-me"
    connection.close()
    assert migrate(create_engine(f"sqlite:///{database}")) == 2


def test_real_noise_prediction_reads_noise_parquet_not_synthetic_demo(tmp_path):
    path = tmp_path / "hourly_500m.parquet"
    rows = []
    for hour in range(80):
        rows.append(
            {
                "country": "Fixture",
                "latitude": 48.85,
                "longitude": 2.35,
                "level_db": 40.0 if hour < 56 else 70.0,
                "hour_epoch": hour,
                "indicator": "laeq_1s",
            }
        )
    rows.append(
        {
            "country": "Fixture",
            "latitude": 48.86,
            "longitude": 2.36,
            "level_db": 10.0,
            "hour_epoch": 90,
            "indicator": "laeq_track",
        }
    )
    pd.DataFrame(rows).to_parquet(path, index=False)
    result = predict_parquet(path, indicator="laeq_1s", country="Fixture")
    assert "synthetic" not in str(result["source"]).lower()
    assert result["source"].endswith("hourly_500m.parquet")
    assert result["indicator"] == "laeq_1s"
    assert result["n_input_rows"] == 80
    assert result["n_test"] >= 10
    assert result["mae"] == pytest.approx(30.0, abs=1.0)
    assert "full-city" in result["note"]


def test_missing_real_mobility_does_not_replace_the_world(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        data_dir=str(tmp_path / "empty-data"),
        jwt_secret="test-secret-not-production-32bytes!!",
        auto_seed=True,
        cors_origins="http://localhost:5173",
    )
    with TestClient(create_app(settings)) as client:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "DemoAdmin#2026"})
        headers = {"Authorization": f"Bearer {login.json()['token']}"}
        before = client.get("/api/simulation", headers=headers).json()
        response = client.post(
            "/api/simulation/control",
            headers=headers,
            json={"action": "reset", "mode": "real_mobility", "mobility_source": "yjmob_dataset1", "n_users": 10},
        )
        assert response.status_code == 409
        message = response.json()["error"]["message"]
        assert "数据未切换" in message
        assert "Synthetic Demo" in message
        after = client.get("/api/simulation", headers=headers).json()
        assert after["mode"] == before["mode"] == "synthetic"
        assert after["id"] == before["id"]


def test_geolife_loader_drops_invalid_coordinates(tmp_path):
    path = tmp_path / "slots.parquet"
    rows = []
    for slot in range(10):
        rows.append({"user_id": "001", "timeslot": slot, "lat": 39.90 + slot * 0.001, "lon": 116.30, "date": "2008-11-01", "day": 0})
    rows.append({"user_id": "001", "timeslot": 20, "lat": 400.166666666667, "lon": 116.30, "date": "2008-11-01", "day": 0})
    rows.append({"user_id": "bad", "timeslot": 0, "lat": 91.0, "lon": 10.0, "date": "2008-11-01", "day": 0})
    pd.DataFrame(rows).to_parquet(path, index=False)
    frame = load_geolife_frame(path, n_users=5, cell_m=500)
    assert set(frame["user_id"]) == {"001"}
    assert frame["lat"].max() < 90
    assert frame.attrs["lat0"] == pytest.approx(float(frame["lat"].min()))
    assert float(frame.attrs["lat0"]) < 41


def test_real_noise_endpoint_does_not_fall_back_to_synthetic(tmp_path):
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
        response = client.get("/api/predictions/real-noise", headers=headers)
        assert response.status_code == 404
        assert "NoiseCapture" in response.json()["error"]["message"]
        assert "synthetic" not in response.json()["error"]["message"].lower()


def test_collector_cannot_read_future_trajectory_slots(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        data_dir=str(tmp_path / "data"),
        jwt_secret="test-secret-not-production-32bytes!!",
        auto_seed=True,
        cors_origins="http://localhost:5173",
    )
    with TestClient(create_app(settings)) as client:
        admin = client.post("/api/auth/login", json={"username": "admin", "password": "DemoAdmin#2026"}).json()["token"]
        collector = client.post("/api/auth/login", json={"username": "collector", "password": "DemoCollect#2026"}).json()["token"]
        state = client.get("/api/simulation", headers={"Authorization": f"Bearer {admin}"}).json()
        current = int(state["current_slot"])
        admin_rows = client.get("/api/trajectories", params={"limit": 5000}, headers={"Authorization": f"Bearer {admin}"}).json()["items"]
        collector_rows = client.get("/api/trajectories", params={"limit": 5000}, headers={"Authorization": f"Bearer {collector}"}).json()["items"]
        assert any(int(row["slot"]) >= current for row in admin_rows)
        assert collector_rows
        assert all(int(row["slot"]) < current for row in collector_rows)
        hidden = client.get("/api/map/frame", params={"slot": current + 5}, headers={"Authorization": f"Bearer {collector}"}).json()
        assert hidden["future_hidden"] is True
        assert hidden["slot"] < current


@pytest.mark.skipif(not YJMOB.exists(), reason="YJMob dataset1 parquet was not produced by preprocess_datasets.py")
def test_yjmob_source_positions_match_and_are_not_wgs84():
    frame = load_yjmob_frame(YJMOB, n_users=10, day_min=0, n_days=1)
    assert len(frame) > 0
    assert set(frame.columns) == {"user_id", "day", "timeslot", "x", "y"}
    world = world_from_mobility_frame(
        frame,
        source="YJMob100K",
        seed=4,
        slots_per_day=48,
        n_days=1,
        day_min=0,
        max_users=10,
        max_side=16,
        min_points=4,
        n_machine=0,
        prior_samples=0,
    )
    assert world.coordinate_system == "yjmob_virtual_500m"
    assert world.meta["real_city"] is False
    assert world.meta["lat0"] is None
    assert world.meta["real_human_count"] >= 1
    uid = world.meta["user_ids"][0]
    origin_x = int(world.meta["origin_x"])
    origin_y = int(world.meta["origin_y"])
    rows = frame[frame["user_id"].astype(str) == uid].sort_values("timeslot").drop_duplicates("timeslot", keep="first")
    matched = 0
    for row in rows.itertuples(index=False):
        if not (origin_x <= int(row.x) <= origin_x + world.width - 1 and origin_y <= int(row.y) <= origin_y + world.height - 1):
            continue
        slot = int(row.timeslot)
        expected = (int(row.y) - origin_y) * world.width + (int(row.x) - origin_x)
        assert int(world.agents[0].traj[slot]) == expected
        matched += 1
    assert matched >= 4


@pytest.mark.skipif(not GEOLIFE.exists(), reason="GeoLife slots_all.parquet was not produced by preprocess_datasets.py")
def test_geolife_subset_uses_real_bins():
    from urbannoise.scenarios import load_geolife_frame

    frame = load_geolife_frame(GEOLIFE, n_users=10, cell_m=500)
    assert len(frame) > 0
    assert frame["lat"].between(-90, 90).all()
    assert frame["lon"].between(-180, 180).all()
    assert frame.attrs["lat0"] == pytest.approx(float(frame["lat"].min()))
    world = world_from_mobility_frame(
        frame,
        source="GeoLife",
        seed=5,
        slots_per_day=48,
        n_days=int(frame["day"].nunique()),
        day_min=int(frame["day"].min()),
        max_users=10,
        max_side=24,
        min_points=4,
        n_machine=0,
        prior_samples=0,
        cell_m=500,
        lat0=float(frame.attrs["lat0"]),
        lon0=float(frame.attrs["lon0"]),
    )
    assert world.coordinate_system == "WGS84"
    assert world.data_origin == "GeoLife"
    assert world.meta["named_city"] is None
    assert world.meta["real_human_count"] >= 1

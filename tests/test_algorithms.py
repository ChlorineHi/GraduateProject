import numpy as np
import pytest

from urbannoise.acoustics import arithmetic_mean_db, energy_mean_db, validate_distribution
from urbannoise.assignment import AgentView, allocate
from urbannoise.dataio import (
    deduplicate_trajectories,
    quality_report,
    read_geolife_plt,
    read_noisecapture_geojson,
    read_yjmob_csv,
)
from urbannoise.domain import TaskStateError, TransitionContext, check_transition
from urbannoise.experiment import EpisodeConfig, decision_context, run_episode
from urbannoise.predictors import ObsSet, fit_mobility, predict_idw
from urbannoise.world import build_world, sample_measurement


def test_energy_mean_is_not_arithmetic_mean():
    levels = np.array([40.0, 60.0])
    assert energy_mean_db(levels) == pytest.approx(57.033, abs=0.01)
    assert arithmetic_mean_db(levels) == pytest.approx(50.0)


def test_illegal_probability_is_rejected():
    with pytest.raises(ValueError):
        validate_distribution(np.array([0.2, 0.2, 0.2]))
    with pytest.raises(ValueError):
        validate_distribution(np.array([1.2, -0.2]))
    with pytest.raises(ValueError):
        validate_distribution(np.array([np.nan, 1.0]))


def test_noise_field_is_finite_and_spatially_structured():
    world = build_world(seed=3, height=12, width=12, n_days=2, slots_per_day=12, n_human=6, n_machine=2, scenario="complex", prior_samples=8)
    assert np.isfinite(world.laeq).all()
    assert world.laeq.shape == (24, 12, 12)
    assert world.coordinate_system == "synthetic_virtual_grid"
    center = world.laeq[:, 6, 6]
    neighbor = world.laeq[:, 6, 7]
    far = world.laeq[:, 0, 11]
    near_corr = np.corrcoef(center, neighbor)[0, 1]
    far_corr = np.corrcoef(center, far)[0, 1]
    assert near_corr > far_corr


def test_assignment_constraints():
    agents = [
        AgentView("H01", "human", 0.9, 1.0, True, 1.0, loc=0),
        AgentView("H02", "human", 0.9, 1.0, True, 1.0, loc=15),
    ]
    grids = np.array([1, 2])
    values = np.array([2.0, 1.5])
    unc = np.array([1.2, 0.4])
    dup = np.array([0.0, 0.0])
    reach = np.array([[0.8, 0.1], [0.0, 0.0]])
    only = allocate("mupsa", agents[:1], grids[:1], values[:1], unc[:1], dup[:1], reach[:1, :1], 4, 1, 5, 2, np.random.default_rng(0))
    assert len(only.assignments) == 1 and only.assignments[0].agent == 0
    blocked = allocate("mupsa_constrained", agents, np.array([3]), np.array([2.0]), np.array([1.0]), np.array([0.0]), np.zeros((2, 1)), 4, 1, 5, 2, np.random.default_rng(0), min_reach=0.22)
    assert blocked.assignments == []
    broke = allocate("mupsa", agents, grids, values, unc, dup, reach, 4, 2, 0, 2, np.random.default_rng(0))
    assert broke.assignments == []
    contended = allocate("mupsa", agents[:1], grids, values, unc, dup, reach[:1], 4, 2, 5, 2, np.random.default_rng(0))
    assert len(contended.assignments) == 1


def test_decision_does_not_read_future_truth_or_future_tracks():
    world = build_world(seed=11, height=8, width=8, n_days=2, slots_per_day=8, n_human=4, n_machine=1, scenario="regular", prior_samples=6)
    obs = ObsSet.empty()
    obs.add(1, 1, 50.0, 0, world.grid_id(1, 1))
    first = decision_context(world, obs, visible_until=7, target_slot=9, lead=2)
    world.laeq[9:] += 25
    future = world.agents[0].traj.copy()
    world.agents[0].traj[9:] = 0
    second = decision_context(world, obs, visible_until=7, target_slot=9, lead=2)
    assert np.allclose(first["mu"], second["mu"])
    assert np.allclose(first["reach"], second["reach"])
    world.agents[0].traj[:] = future
    changed = sample_measurement(world, 10, world.grid_id(0, 0), np.random.default_rng(0))
    world.laeq[10, 0, 0] -= 25
    changed_again = sample_measurement(world, 10, world.grid_id(0, 0), np.random.default_rng(0))
    assert changed != pytest.approx(changed_again)


def test_mobility_fit_ignores_future_and_idw_skips_nan():
    traj = np.array([[0, 1, 1, 4, 4]], dtype=np.int32)
    early = fit_mobility(traj, 2, slots_per_day=4, n_grids=5)
    late = fit_mobility(traj, 4, slots_per_day=4, n_grids=5)
    assert early.transitions[0, 1, 4] == 0
    assert late.transitions[0, 1, 4] == 1
    obs = {"x": np.array([0.0, 1.0]), "y": np.array([0.0, 0.0]), "db": np.array([np.nan, 40.0]), "slot": np.array([0, 0]), "grid": np.array([0, 1])}
    # The public ObsSet drops non-finite values. The raw predictor must also survive a NaN if one is passed.
    mu, std = predict_idw({"x": np.array([0.0]), "y": np.array([0.0]), "db": np.array([50.0]), "slot": np.array([0]), "grid": np.array([0])}, np.array([[0.0, 0.0], [3.0, 3.0]]), 1)
    assert mu.shape == (2,)
    assert std[1] > std[0]


def test_episode_is_deterministic_and_respects_budget():
    world = build_world(seed=5, height=8, width=8, n_days=2, slots_per_day=8, n_human=6, n_machine=2, scenario="regular", prior_samples=10)
    a = run_episode(world, "mupsa", 6, 123, EpisodeConfig(lead=2, per_slot_cap=3))
    b = run_episode(world, "mupsa", 6, 123, EpisodeConfig(lead=2, per_slot_cap=3))
    assert a["mae_causal"] == pytest.approx(b["mae_causal"])
    assert a["sampling_cost"] <= 6 + 1e-6
    zero = run_episode(world, "greedy", 0, 1, EpisodeConfig(lead=1, per_slot_cap=2))
    assert zero["successful_tasks"] == 0


def test_state_machine_guards():
    ok = TransitionContext(role="publisher", has_measurement=False, assignee_matches=True)
    check_transition("draft", "published", ok)
    with pytest.raises(TaskStateError):
        check_transition("draft", "completed", ok)
    with pytest.raises(TaskStateError):
        check_transition("submitted", "submitted", TransitionContext("collector", has_measurement=True))
    with pytest.raises(TaskStateError):
        check_transition("in_progress", "submitted", TransitionContext("collector", has_measurement=False, assignee_matches=True))
    with pytest.raises(TaskStateError):
        check_transition("published", "expired", TransitionContext("system", now_slot=3, slot_end=5))
    check_transition("published", "expired", TransitionContext("system", now_slot=6, slot_end=5))
    with pytest.raises(TaskStateError):
        check_transition("assigned", "accepted", TransitionContext("collector", assignee_matches=False))
    with pytest.raises(TaskStateError):
        check_transition("completed", "published", TransitionContext("admin"))


def test_dataset_adapters(tmp_path):
    yjmob = tmp_path / "yj.csv"
    yjmob.write_text("uid,day,timeslot,x,y\n3,0,13,2,4\n3,0,13,2,4\n3,1,10,201,4\n", encoding="utf-8")
    frame = read_yjmob_csv(yjmob)
    assert frame.loc[0, "coordinate_system"] == "yjmob_virtual_500m"
    assert np.isnan(frame.loc[0, "latitude"])
    deduped, removed = deduplicate_trajectories(frame, ["participant_id", "day", "timeslot", "x", "y"])
    assert removed == 1
    assert "virtual grid" in quality_report(deduped, "mobility")["spatial_reference"]
    plt = tmp_path / "demo.plt"
    plt.write_text(
        "Geolife trajectory\nWGS 84\nAltitude is in feet\nReserved 3\n0,2,255,My Track,0,0,2,8421376\n0\n"
        "39.9,116.3,0,100,39744.1,2008-10-23,02:53:04\n39.91,116.31,0,100,39744.2,2008-10-23,02:54:04\n",
        encoding="utf-8",
    )
    geo = read_geolife_plt(plt, participant_id="fixture-user")
    assert geo.iloc[0]["coordinate_system"] == "WGS84"
    assert geo.iloc[0]["grid_id"] is None
    geojson = tmp_path / "noise.geojson"
    geojson.write_text(
        '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Point","coordinates":[116.3,39.9]},"properties":{"leq":68.5,"time":"2020-01-01T08:00:00"}},{"type":"Feature","geometry":{"type":"Point","coordinates":[116.4,39.91]},"properties":{"noise_level":42}}]}',
        encoding="utf-8",
    )
    noise = read_noisecapture_geojson(geojson)
    assert set(noise["indicator"]) == {"leq", "noise_level"}
    report = quality_report(noise, "noise")
    assert report["energy_mean_db"] > report["arithmetic_mean_db"]

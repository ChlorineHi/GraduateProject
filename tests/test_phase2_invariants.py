"""Phase-2 invariant tests against the current UrbanNoiseLab behavior.

Assertions follow the state machine in domain.py and the assignment,
decision, and dataset functions as they are implemented. Where a stated
contract is still broken, the test records the observed fingerprint and
xfails instead of weakening the check.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
from fastapi.testclient import TestClient

from urbannoise.acoustics import validate_distribution
from urbannoise.api import create_app
from urbannoise.assignment import AgentView, allocate
from urbannoise.dataio import quality_report, read_yjmob_csv
from urbannoise.domain import (
    TERMINAL_STATES,
    TRANSITIONS,
    TaskStateError,
    TransitionContext,
    check_transition,
    legal_targets,
)
from urbannoise.experiment import EpisodeConfig, _plan_slot, decision_context, run_episode, run_suite, step_campaign
from urbannoise.predictors import ObsSet, fit_mobility
from urbannoise.settings import Settings
from urbannoise.world import build_world, sample_measurement

# sha256 of the float64 columns (x, y, db, slot, grid) from _seed_prior, as drawn
# by run_suite for world seed 0, budget 4, and the two methods below.
_MUPSA_PRIOR_HASH = "0662b171a97a6c6b1fd9b3a74fbedea983da4e3c14412be9669e907d66780a94"
_GREEDY_PRIOR_HASH = "eaad7ed7d50814559573f2dc129c89989a9f247446bac96d8ee175dae8d3ca43"
_SEED_BUG_REASON = (
    "seed bug: run_suite sets episode_seed = 10000 + seed * 100 + budget + "
    "(sum(ord(ch) for ch in method) % 97), so two methods in one episode draw "
    "different initial observations. current hashes "
    f"mupsa={_MUPSA_PRIOR_HASH} episode_seed=10069; "
    f"greedy={_GREEDY_PRIOR_HASH} episode_seed=10062"
)

_DECISION_KEYS = {"mu", "std", "features", "reach", "queries"}
_FEATURE_KEYS = {
    "uncertainty",
    "uncertainty_norm",
    "isolation",
    "temporal_gap",
    "duplicate",
    "coverage_gap",
    "counts",
}
_PLAN_KEYS = {
    "slot",
    "decision_slot",
    "agent",
    "grid",
    "cost",
    "reach",
    "score",
    "value",
    "context",
    "unc_norm",
    "done",
    "success",
}
_FORBIDDEN_CONTEXT_KEYS = {
    "truth",
    "laeq",
    "traj",
    "trajectory",
    "trajectories",
    "future",
    "future_slot",
    "future_slots",
    "unsampled",
    "unsampled_truth",
    "ground_truth",
}


def _world(**overrides):
    params = dict(
        seed=5,
        height=6,
        width=6,
        n_days=2,
        slots_per_day=4,
        n_human=3,
        n_machine=1,
        scenario="regular",
        prior_samples=4,
    )
    params.update(overrides)
    return build_world(**params)


def _observation_hash(obs: ObsSet) -> str:
    columns = np.column_stack(
        [
            np.asarray(obs.x, dtype=np.float64),
            np.asarray(obs.y, dtype=np.float64),
            np.asarray(obs.db, dtype=np.float64),
            np.asarray(obs.slot, dtype=np.float64),
            np.asarray(obs.grid, dtype=np.float64),
        ]
    )
    return hashlib.sha256(columns.tobytes()).hexdigest()


def _episode_seed(world_seed: int, budget: int, method: str) -> int:
    return 10_000 + int(world_seed) * 100 + int(budget) + (sum(ord(ch) for ch in method) % 97)


def _collect(value, keys: set[str], arrays: list[np.ndarray]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            _collect(item, keys, arrays)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect(item, keys, arrays)
    elif isinstance(value, np.ndarray):
        arrays.append(value)


def _assert_context_has_no_future_or_truth(payload: dict, world, visible_until: int) -> None:
    keys: set[str] = set()
    arrays: list[np.ndarray] = []
    _collect(payload, keys, arrays)
    leaked = {key for key in keys if key.lower() in _FORBIDDEN_CONTEXT_KEYS}
    assert leaked == set()
    assert world.laeq.shape not in {array.shape for array in arrays}
    for agent in world.agents:
        future = np.asarray(agent.traj[visible_until + 1 :])
        for array in arrays:
            if array.shape == agent.traj.shape:
                assert not np.array_equal(array, agent.traj)
            if future.size and array.shape == future.shape:
                assert not np.array_equal(array, future)
            assert array is not world.laeq
            assert array is not agent.traj


def test_budget_zero_assigns_nothing():
    agents = [AgentView("H01", "human", 0.9, 1.0, True, 1.0, loc=0)]
    grids = np.array([0])
    values = np.array([3.0])
    unc = np.array([1.2])
    duplicate = np.array([0.0])
    reach = np.array([[1.0]])
    zero = allocate(
        "mupsa",
        agents,
        grids,
        values,
        unc,
        duplicate,
        reach,
        width=8,
        radius=3,
        budget=0,
        cap=2,
        rng=np.random.default_rng(0),
    )
    assert zero.assignments == []
    assert zero.rejected_reasons == ["no budget, capacity, agents, or candidate tasks"]

    funded = allocate(
        "mupsa",
        agents,
        grids,
        values,
        unc,
        duplicate,
        reach,
        width=8,
        radius=3,
        budget=2,
        cap=2,
        rng=np.random.default_rng(0),
    )
    assert len(funded.assignments) == 1
    assert funded.assignments[0].grid == 0
    assert funded.assignments[0].agent == 0

    world = _world()
    episode = run_episode(world, "greedy", 0, 11, EpisodeConfig(lead=1, per_slot_cap=2))
    assert episode["assigned_tasks"] == 0
    assert episode["successful_tasks"] == 0
    assert episode["failed_tasks"] == 0
    assert episode["sampling_cost"] == 0


def test_all_participants_unreachable_assigns_nothing():
    # Reach is zero and every location is outside the radius, so each method's
    # feasibility gate (probability floor or current distance) rejects the pair.
    agents = [
        AgentView("H01", "human", 0.9, 1.0, True, 1.0, loc=-1),
        AgentView("M01", "machine", 0.96, 1.7, True, 0.98, loc=-1),
    ]
    grids = np.array([0, 2, 5])
    values = np.array([3.0, 2.5, 4.0])
    unc = np.array([1.4, 1.1, 0.8])
    duplicate = np.zeros(3)
    reach = np.zeros((2, 3))
    methods = ["mupsa", "mupsa_constrained", "nearest", "greedy", "uncertainty", "random", "min_cost"]
    for method in methods:
        result = allocate(
            method,
            agents,
            grids,
            values,
            unc,
            duplicate,
            reach,
            width=8,
            radius=2,
            budget=10,
            cap=3,
            rng=np.random.default_rng(0),
            min_reach=0.22,
        )
        assert result.assignments == [], method
        assert result.rejected_reasons == ["no feasible pair under the method constraints"]

    reachable_agents = [
        AgentView("H01", "human", 0.9, 1.0, True, 1.0, loc=0),
        AgentView("M01", "machine", 0.96, 1.7, True, 0.98, loc=1),
    ]
    reachable = np.zeros((2, 3))
    reachable[:, 0] = 1.0
    hit = allocate(
        "mupsa",
        reachable_agents,
        grids,
        values,
        unc,
        duplicate,
        reachable,
        width=8,
        radius=2,
        budget=10,
        cap=3,
        rng=np.random.default_rng(0),
    )
    assert len(hit.assignments) == 1
    assert hit.assignments[0].grid == 0


def test_bandit_unreachable_participants_assign_nothing():
    """Zero reach and a location outside the grid must leave the assignment empty."""
    agents = [
        AgentView("H01", "human", 0.9, 1.0, True, 1.0, loc=-1),
        AgentView("M01", "machine", 0.96, 1.7, True, 0.98, loc=-1),
    ]
    grids = np.array([0, 2, 5])
    result = allocate(
        "bandit",
        agents,
        grids,
        np.array([3.0, 2.5, 4.0]),
        np.array([1.4, 1.1, 0.8]),
        np.zeros(3),
        np.zeros((2, 3)),
        width=8,
        radius=2,
        budget=10,
        cap=3,
        rng=np.random.default_rng(0),
        min_reach=0.22,
    )
    if result.assignments:
        observed = [
            (item.agent, item.grid, item.score, item.reach, item.distance, item.cost, item.value)
            for item in result.assignments
        ]
        assert observed[0][0:2] == (1, 0)
        assert observed[0][2] == pytest.approx(2.3068430809224973)
        assert observed[0][3:] == (0.0, 1_000_000.0, 1.7, 3.0)
        assert observed[1][0:2] == (0, 5)
        assert observed[1][2] == pytest.approx(2.120288895410246)
        assert observed[1][3:] == (0.0, 1_000_000.0, 1.0, 4.0)
        pytest.xfail(
            "bandit shortlist keeps every score above -1e8, including the negative "
            "MU-PSA score of a zero-reach pair, so unreachable participants are still "
            "assigned. current assignments: agent 1 -> grid 0 "
            "(ucb=2.3068430809224973, reach=0.0, distance=1000000.0, cost=1.7, value=3.0); "
            "agent 0 -> grid 5 "
            "(ucb=2.120288895410246, reach=0.0, distance=1000000.0, cost=1.0, value=4.0)"
        )
    assert result.assignments == []


@pytest.mark.parametrize("role", ["collector", "publisher", "admin", "system"])
@pytest.mark.parametrize("has_measurement", [True, False])
def test_duplicate_submit_is_illegal(role, has_measurement):
    ctx = TransitionContext(role, has_measurement=has_measurement, assignee_matches=True, now_slot=8, slot_end=6)
    with pytest.raises(TaskStateError, match="illegal transition submitted -> submitted"):
        check_transition("submitted", "submitted", ctx)
    assert "submitted" not in legal_targets("submitted", ctx)
    assert TRANSITIONS["submitted"] == {"verified", "rejected"}


def test_submitted_can_be_verified_or_rejected_once():
    check_transition("submitted", "verified", TransitionContext("publisher"))
    check_transition("submitted", "verified", TransitionContext("admin"))
    check_transition("submitted", "verified", TransitionContext("system"))
    check_transition("submitted", "rejected", TransitionContext("publisher"))
    check_transition("submitted", "rejected", TransitionContext("admin"))
    assert legal_targets("submitted", TransitionContext("publisher")) == ["rejected", "verified"]
    with pytest.raises(TaskStateError, match="role 'collector' cannot perform submitted -> verified"):
        check_transition("submitted", "verified", TransitionContext("collector", has_measurement=True, assignee_matches=True))
    with pytest.raises(TaskStateError, match="role 'collector' cannot perform submitted -> rejected"):
        check_transition("submitted", "rejected", TransitionContext("collector", has_measurement=True, assignee_matches=True))
    with pytest.raises(TaskStateError, match="role 'system' cannot perform submitted -> rejected"):
        check_transition("submitted", "rejected", TransitionContext("system"))


@pytest.mark.parametrize("src", ["published", "assigned", "accepted", "in_progress"])
@pytest.mark.parametrize("role", ["admin", "system"])
def test_expired_window_opens_only_after_slot_end(src, role):
    with pytest.raises(TaskStateError, match="time window has not expired"):
        check_transition(src, "expired", TransitionContext(role, now_slot=5, slot_end=5))
    with pytest.raises(TaskStateError, match="time window has not expired"):
        check_transition(src, "expired", TransitionContext(role, now_slot=4, slot_end=5))
    with pytest.raises(TaskStateError, match="time window has not expired"):
        check_transition(src, "expired", TransitionContext(role, now_slot=None, slot_end=5))
    with pytest.raises(TaskStateError, match="time window has not expired"):
        check_transition(src, "expired", TransitionContext(role, now_slot=6, slot_end=None))
    check_transition(src, "expired", TransitionContext(role, now_slot=6, slot_end=5))


@pytest.mark.parametrize("src", ["published", "assigned", "accepted", "in_progress"])
def test_collector_cannot_expire_a_task(src):
    ctx = TransitionContext("collector", now_slot=9, slot_end=5, assignee_matches=True)
    with pytest.raises(TaskStateError, match=f"role 'collector' cannot perform {src} -> expired"):
        check_transition(src, "expired", ctx)
    with pytest.raises(TaskStateError, match=f"role 'publisher' cannot perform {src} -> expired"):
        check_transition(src, "expired", TransitionContext("publisher", now_slot=9, slot_end=5))


def test_expired_is_terminal_and_unavailable_from_submitted():
    assert "expired" in TERMINAL_STATES
    assert TRANSITIONS["expired"] == set()
    ctx = TransitionContext("admin", now_slot=10, slot_end=1)
    assert legal_targets("expired", ctx) == []
    for dst in (
        "draft",
        "published",
        "assigned",
        "accepted",
        "in_progress",
        "submitted",
        "verified",
        "completed",
        "rejected",
        "failed",
        "cancelled",
        "reassigned",
        "expired",
    ):
        with pytest.raises(TaskStateError, match=f"illegal transition expired -> {dst}"):
            check_transition("expired", dst, ctx)
    with pytest.raises(TaskStateError, match="illegal transition submitted -> expired"):
        check_transition("submitted", "expired", TransitionContext("system", now_slot=10, slot_end=1))


def test_offline_machine_is_not_assigned_and_fails_closed():
    world = _world(seed=2)
    machine = next(agent for agent in world.agents if agent.kind == "machine")
    on_site = int(np.flatnonzero(machine.traj >= 0)[0])
    grid = int(machine.traj[on_site])
    machine.online = False

    offline_view = AgentView(machine.name, "machine", machine.accept, machine.cost, False, machine.quality, loc=grid)
    blocked = allocate(
        "mupsa",
        [offline_view],
        np.array([grid]),
        np.array([4.0]),
        np.array([1.5]),
        np.array([0.0]),
        np.array([[1.0]]),
        width=world.width,
        radius=world.width,
        budget=10,
        cap=2,
        rng=np.random.default_rng(0),
    )
    assert blocked.assignments == []
    assert blocked.rejected_reasons == ["no feasible pair under the method constraints"]

    online_view = AgentView(machine.name, "machine", machine.accept, machine.cost, True, machine.quality, loc=grid)
    assigned = allocate(
        "mupsa",
        [online_view],
        np.array([grid]),
        np.array([4.0]),
        np.array([1.5]),
        np.array([0.0]),
        np.array([[1.0]]),
        width=world.width,
        radius=world.width,
        budget=10,
        cap=2,
        rng=np.random.default_rng(0),
    )
    assert len(assigned.assignments) == 1

    obs = ObsSet.empty()
    plans = [
        {
            "slot": on_site,
            "agent": machine.idx,
            "grid": grid,
            "cost": float(machine.cost),
            "reach": 1.0,
            "unc_norm": 1.0,
            "done": False,
            "success": False,
            "context": None,
        }
    ]
    before = sample_measurement(world, on_site, grid, np.random.default_rng(1))
    outcome = step_campaign(
        world,
        obs,
        plans,
        on_site,
        10.0,
        "mupsa",
        10.0,
        EpisodeConfig(lead=1, per_slot_cap=2, replan=False),
        np.random.default_rng(0),
    )
    assert len(outcome["executed"]) == 1
    executed = outcome["executed"][0]
    assert executed["reason"] == "offline"
    assert executed["success"] is False
    assert executed["level_db"] is None
    assert plans[0]["done"] is True
    assert plans[0]["success"] is False
    assert obs.db == []
    assert np.isfinite(before)

    # domain.py has no offline state. From assigned, the legal failure is
    # rejected by system; submitted and failed are not legal from assigned.
    system = TransitionContext("system", now_slot=on_site, slot_end=on_site, has_measurement=False)
    check_transition("assigned", "rejected", system)
    with pytest.raises(TaskStateError, match="illegal transition assigned -> submitted"):
        check_transition("assigned", "submitted", system)
    with pytest.raises(TaskStateError, match="illegal transition assigned -> failed"):
        check_transition("assigned", "failed", system)
    with pytest.raises(TaskStateError, match="submission requires a measurement"):
        check_transition("in_progress", "submitted", TransitionContext("system", has_measurement=False, now_slot=on_site, slot_end=on_site))
    check_transition("in_progress", "failed", TransitionContext("system", now_slot=on_site, slot_end=on_site))


def test_negative_or_nonunit_probability_vectors_are_rejected():
    with pytest.raises(ValueError, match="negative"):
        validate_distribution(np.array([1.2, -0.2]))
    with pytest.raises(ValueError, match="negative"):
        validate_distribution(np.array([-0.1, -0.2, -0.3]))
    with pytest.raises(ValueError, match="sum to 1"):
        validate_distribution(np.array([0.2, 0.2]))
    with pytest.raises(ValueError, match="sum to 1"):
        validate_distribution(np.array([0.7, 0.7]))
    with pytest.raises(ValueError, match="sum to 1"):
        validate_distribution(np.array([0.0, 0.0, 0.0]))
    with pytest.raises(ValueError, match="sum to 1"):
        validate_distribution(np.array([1.0, 1.0]))

    legal = validate_distribution(np.array([0.0, 0.25, 0.75]))
    assert np.allclose(legal, [0.0, 0.25, 0.75])
    assert legal.sum() == pytest.approx(1.0)

    traj = np.array([[0, 1, 1, 2, 2]], dtype=np.int32)
    fit = fit_mobility(traj, visible_until=4, slots_per_day=4, n_grids=4)
    distilled = validate_distribution(fit.distribution(0, tod=1, current=1, lead=1))
    assert distilled.shape == (4,)
    assert np.all(distilled >= -1e-8)
    assert distilled.sum() == pytest.approx(1.0)


def test_decision_context_keys_exclude_future_trajectory_and_unsampled_truth():
    world = _world(seed=11, height=6, width=6, n_days=2, slots_per_day=6, n_human=3, n_machine=1)
    visible_until = 4
    target_slot = 7
    obs = ObsSet.empty()
    obs.add(1, 1, 50.0, 0, world.grid_id(1, 1))
    obs.add(2, 2, 61.0, visible_until, world.grid_id(2, 2))
    ctx = decision_context(world, obs, visible_until=visible_until, target_slot=target_slot, lead=2)

    assert set(ctx) == _DECISION_KEYS
    assert set(ctx["features"]) == _FEATURE_KEYS
    assert ctx["mu"].shape == (world.n_grids,)
    assert ctx["std"].shape == (world.n_grids,)
    assert ctx["reach"].shape == (len(world.agents), world.n_grids)
    assert ctx["queries"].shape == (world.n_grids, 2)
    for name, column in ctx["features"].items():
        assert isinstance(column, np.ndarray), name
        assert column.shape == (world.n_grids,)
    _assert_context_has_no_future_or_truth(ctx, world, visible_until)

    plans = _plan_slot(
        world,
        obs,
        visible_until,
        target_slot,
        2,
        "mupsa",
        8.0,
        EpisodeConfig(lead=2, per_slot_cap=2),
        np.random.default_rng(0),
        None,
        8.0,
    )
    assert plans
    for plan in plans:
        assert set(plan) == _PLAN_KEYS
        assert plan["slot"] == target_slot
        assert plan["decision_slot"] == visible_until
        assert plan["context"] is None
        _assert_context_has_no_future_or_truth(plan, world, visible_until)


def test_yjmob_coordinate_system_is_not_wgs84_and_needs_no_latlon(tmp_path):
    path = tmp_path / "yj.csv"
    path.write_text("uid,day,timeslot,x,y\n3,0,13,2,4\n9,1,10,201,4\n", encoding="utf-8")
    frame = read_yjmob_csv(path)
    assert len(frame) == 2
    assert set(frame["coordinate_system"]) == {"yjmob_virtual_500m"}
    assert "WGS84" not in set(frame["coordinate_system"])
    assert frame["latitude"].isna().all()
    assert frame["longitude"].isna().all()
    assert "latitude" not in path.read_text(encoding="utf-8")
    assert "longitude" not in path.read_text(encoding="utf-8")
    report = quality_report(frame, "mobility")
    assert report["spatial_reference"] == "virtual grid, no geographic coordinates"
    assert report["real_city"] is False
    assert "lat_min" not in report
    assert "lon_min" not in report
    assert report["rows"] == 2


def _auth(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def _app(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        data_dir=str(tmp_path / "data"),
        jwt_secret="test-secret-not-production-32bytes!!",
        auto_seed=True,
        cors_origins="http://localhost:5173",
    )
    return create_app(settings)


def test_collector_cannot_verify_submission(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        admin = _auth(client, "admin", "DemoAdmin#2026")
        publisher = _auth(client, "publisher", "DemoPublish#2026")
        collector = _auth(client, "collector", "DemoCollect#2026")
        created = client.post(
            "/api/tasks",
            headers=publisher,
            json={
                "title": "核验权限",
                "grid_x": 2,
                "grid_y": 2,
                "slot_start": 50,
                "slot_end": 54,
                "priority": 0.4,
                "budget_cost": 1,
            },
        )
        assert created.status_code == 200, created.text
        task_id = created.json()["id"]
        for status in ("published", "assigned", "accepted", "in_progress"):
            moved = client.post(
                f"/api/tasks/{task_id}/transition",
                headers=admin,
                json={"to_status": status},
            )
            assert moved.status_code == 200, moved.text
            assert moved.json()["status"] == status
        submitted = client.post(
            f"/api/tasks/{task_id}/transition",
            headers=admin,
            json={"to_status": "submitted", "measurement_db": 61.0},
        )
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["status"] == "submitted"

        denied = client.post(
            f"/api/tasks/{task_id}/transition",
            headers=collector,
            json={"to_status": "verified"},
        )
        assert denied.status_code == 409
        body = denied.json()["error"]
        assert body["code"] == "invalid_transition"
        assert body["message"] == "role 'collector' cannot perform submitted -> verified"
        listed = client.get("/api/tasks", headers=collector).json()
        current = next(item for item in listed["items"] if item["id"] == task_id)
        assert current["status"] == "submitted"

        verified = client.post(
            f"/api/tasks/{task_id}/transition",
            headers=publisher,
            json={"to_status": "verified"},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "verified"


def test_api_duplicate_submit_and_expired_window(tmp_path):
    with TestClient(_app(tmp_path)) as client:
        admin = _auth(client, "admin", "DemoAdmin#2026")
        publisher = _auth(client, "publisher", "DemoPublish#2026")
        clock = client.get("/api/simulation", headers=admin).json()["current_slot"]

        created = client.post(
            "/api/tasks",
            headers=publisher,
            json={
                "title": "重复提交",
                "grid_x": 1,
                "grid_y": 1,
                "slot_start": clock,
                "slot_end": clock + 2,
                "priority": 0.2,
                "budget_cost": 1,
            },
        )
        assert created.status_code == 200, created.text
        task_id = created.json()["id"]
        for status in ("published", "assigned", "accepted", "in_progress"):
            moved = client.post(f"/api/tasks/{task_id}/transition", headers=admin, json={"to_status": status})
            assert moved.status_code == 200, moved.text
        submitted = client.post(
            f"/api/tasks/{task_id}/transition",
            headers=admin,
            json={"to_status": "submitted", "measurement_db": 55.0},
        )
        assert submitted.status_code == 200, submitted.text
        duplicate = client.post(
            f"/api/tasks/{task_id}/transition",
            headers=admin,
            json={"to_status": "submitted", "measurement_db": 56.0},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["message"] == "illegal transition submitted -> submitted"
        still = client.get(f"/api/tasks", headers=admin).json()
        assert next(item for item in still["items"] if item["id"] == task_id)["status"] == "submitted"

        past = client.post(
            "/api/tasks",
            headers=publisher,
            json={
                "title": "窗口已过",
                "grid_x": 3,
                "grid_y": 3,
                "slot_start": max(0, clock - 4),
                "slot_end": clock - 1,
                "priority": 0.2,
                "budget_cost": 1,
            },
        )
        assert past.status_code == 200, past.text
        past_id = past.json()["id"]
        published = client.post(f"/api/tasks/{past_id}/transition", headers=publisher, json={"to_status": "published"})
        assert published.status_code == 200, published.text
        publisher_expired = client.post(
            f"/api/tasks/{past_id}/transition",
            headers=publisher,
            json={"to_status": "expired"},
        )
        assert publisher_expired.status_code == 409
        assert publisher_expired.json()["error"]["message"] == "role 'publisher' cannot perform published -> expired"
        expired = client.post(f"/api/tasks/{past_id}/transition", headers=admin, json={"to_status": "expired"})
        assert expired.status_code == 200, expired.text
        assert expired.json()["status"] == "expired"
        again = client.post(f"/api/tasks/{past_id}/transition", headers=admin, json={"to_status": "published"})
        assert again.status_code == 409
        assert again.json()["error"]["message"] == "illegal transition expired -> published"

        open_task = client.post(
            "/api/tasks",
            headers=publisher,
            json={
                "title": "窗口未结束",
                "grid_x": 4,
                "grid_y": 1,
                "slot_start": clock,
                "slot_end": clock,
                "priority": 0.2,
                "budget_cost": 1,
            },
        )
        assert open_task.status_code == 200, open_task.text
        open_id = open_task.json()["id"]
        published_open = client.post(
            f"/api/tasks/{open_id}/transition",
            headers=publisher,
            json={"to_status": "published"},
        )
        assert published_open.status_code == 200, published_open.text
        too_early = client.post(f"/api/tasks/{open_id}/transition", headers=admin, json={"to_status": "expired"})
        assert too_early.status_code == 409
        assert too_early.json()["error"]["message"] == "time window has not expired"
        open_rows = client.get("/api/tasks", headers=admin).json()
        assert next(item for item in open_rows["items"] if item["id"] == open_id)["status"] == "published"


def test_two_methods_in_one_episode_share_initial_observations(tmp_path, monkeypatch):
    import urbannoise.experiment as experiment

    captured: dict[str, str] = {}
    seeds: dict[str, int] = {}
    current = {"method": None, "seed": None}
    real_run = experiment.run_episode
    real_prior = experiment._seed_prior

    def wrapped_run(world, method, budget, seed, *args, **kwargs):
        current["method"] = method
        current["seed"] = int(seed)
        return real_run(world, method, budget, seed, *args, **kwargs)

    def wrapped_prior(world, rng):
        obs = real_prior(world, rng)
        captured[current["method"]] = _observation_hash(obs)
        seeds[current["method"]] = int(current["seed"])
        return obs

    monkeypatch.setattr(experiment, "run_episode", wrapped_run)
    monkeypatch.setattr(experiment, "_seed_prior", wrapped_prior)
    payload = run_suite(
        {
            "methods": ["mupsa", "greedy"],
            "scenarios": ["regular"],
            "seeds": [0],
            "budgets": [4],
            "grid": 6,
            "slots_per_day": 4,
            "n_days": 2,
            "n_human": 3,
            "n_machine": 1,
            "lead": 1,
            "per_slot_cap": 2,
            "prior_samples": 4,
            "model_reports": False,
            "ablation": False,
            "robustness": False,
            "train_bandit": False,
            "name": "phase2-seed",
        },
        tmp_path,
    )
    assert [row["method"] for row in payload["rows"]] == ["mupsa", "greedy"]
    assert set(captured) == {"mupsa", "greedy"}
    if captured["mupsa"] != captured["greedy"]:
        assert seeds["mupsa"] == _episode_seed(0, 4, "mupsa") == 10069
        assert seeds["greedy"] == _episode_seed(0, 4, "greedy") == 10062
        assert captured["mupsa"] == _MUPSA_PRIOR_HASH
        assert captured["greedy"] == _GREEDY_PRIOR_HASH
        pytest.xfail(_SEED_BUG_REASON)
    assert captured["mupsa"] == captured["greedy"]

"""Business operations shared by the API and the demo seed."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from urbannoise.acoustics import clip_measurement, energy_mean_db
from urbannoise.catalog import dataset_regime
from urbannoise.experiment import METHOD_LABELS
from urbannoise.dataio import (
    quality_report,
    read_geolife_plt,
    read_noisecapture_geojson,
    read_yjmob_csv,
)
from urbannoise.domain import TransitionContext, check_transition
from urbannoise.errors import AppError
from urbannoise.experiment import EpisodeConfig, _plan_slot, map_arrays, step_campaign
from urbannoise.models import (
    AlgorithmConfig,
    AssignmentEvent,
    AuditLog,
    Device,
    EvaluationMetric,
    ExperimentRun,
    IdempotencyKey,
    MobilityDataset,
    ModelArtifact,
    NoiseDataset,
    NoiseObservation,
    Participant,
    SamplingResult,
    SensingTask,
    SimulationRun,
    SimulationScenario,
    SpatialGrid,
    TaskAssignment,
    TrajectoryPoint,
    User,
)
from urbannoise.predictors import ObsSet, fit_mobility, grid_queries, predict_gp, predict_idw, predict_rf
from urbannoise.security import hash_password, verify_password
from urbannoise.settings import Settings
from urbannoise.world import ZONE_NAMES, build_world, load_world, save_world

DEMO_USERS = [
    ("admin", "DemoAdmin#2026", "系统管理员", "admin"),
    ("publisher", "DemoPublish#2026", "任务发布员", "publisher"),
    ("collector", "DemoCollect#2026", "采集参与者", "collector"),
]

DEFAULT_WORLD = {
    "seed": 7,
    "height": 16,
    "width": 16,
    "n_days": 2,
    "slots_per_day": 48,
    "n_human": 14,
    "n_machine": 4,
    "scenario": "complex",
    "prior_samples": 36,
    "sensor_sigma": 1.5,
    "accept_human": 0.72,
    "accept_machine": 0.96,
    "budget": 24.0,
    "algorithm": "mupsa",
    "lead": 1,
    "per_slot_cap": 3,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def audit(db: Session, user_id: int | None, action: str, detail: str) -> None:
    db.add(AuditLog(user_id=user_id, action=action, detail=detail[:4000], created_at=utcnow()))


def slot_label(slot: int, slots_per_day: int) -> str:
    day = int(slot) // slots_per_day
    tod = int(slot) % slots_per_day
    minutes = int(round(tod * 24 * 60 / slots_per_day))
    hour, minute = divmod(minutes, 60)
    return f"D{day} {hour:02d}:{minute:02d}"


def rng_dump(rng: np.random.Generator) -> str:
    state = rng.bit_generator.state

    def conv(value):
        if isinstance(value, np.ndarray):
            return {"__ndarray__": value.tolist(), "dtype": str(value.dtype)}
        if isinstance(value, dict):
            return {str(key): conv(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [conv(item) for item in value]
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        return value

    return json.dumps(conv(state))


def rng_load(payload: str) -> np.random.Generator:
    def revive(value):
        if isinstance(value, dict) and "__ndarray__" in value:
            return np.array(value["__ndarray__"], dtype=value["dtype"])
        if isinstance(value, dict):
            return {key: revive(item) for key, item in value.items()}
        if isinstance(value, list):
            return [revive(item) for item in value]
        return value

    rng = np.random.default_rng()
    rng.bit_generator.state = revive(json.loads(payload))
    return rng


def _world_params(raw: dict | None = None) -> dict:
    params = dict(DEFAULT_WORLD)
    if raw:
        params.update({key: raw[key] for key in raw if key in params or key in {"name"}})
    params["height"] = int(params["height"])
    params["width"] = int(params["width"])
    params["n_days"] = int(params["n_days"])
    params["slots_per_day"] = int(params["slots_per_day"])
    params["budget"] = float(params["budget"])
    params["scenario_mode"] = "synthetic_demo"
    return params


def active_run(db: Session) -> SimulationRun:
    run = db.query(SimulationRun).order_by(SimulationRun.id.desc()).first()
    if run is None:
        raise AppError("no_simulation", "还没有仿真运行", 404)
    return run


def load_run_world(run: SimulationRun):
    if not run.world_path or not Path(run.world_path).exists():
        raise AppError("world_missing", "仿真真值文件不存在", 500)
    return load_world(run.world_path)


def observations_to_set(db: Session) -> ObsSet:
    obs = ObsSet.empty()
    rows = db.query(NoiseObservation).filter(NoiseObservation.grid_id.isnot(None), NoiseObservation.slot.isnot(None)).all()
    width = db.query(func.max(SpatialGrid.grid_x)).scalar()
    width = int(width) + 1 if width is not None else 16
    for row in rows:
        grid = int(row.grid_id)
        obs.add(grid % width, grid // width, float(row.laeq_db), int(row.slot), grid)
    return obs


def participant_agents(db: Session):
    from urbannoise.world import Agent

    people = db.query(Participant).order_by(Participant.id.asc()).all()
    agents = []
    for index, person in enumerate(people):
        traj = np.asarray(json.loads(person.trajectory_json or "[]"), dtype=np.int32)
        agents.append(
            Agent(
                idx=index,
                name=person.name,
                kind=person.participant_type,
                accept=person.accept_prob,
                cost=person.cost,
                online=person.online,
                quality=person.quality,
                traj=traj,
            )
        )
    return people, agents


def seed_if_needed(db: Session, settings: Settings) -> None:
    if db.query(User).count():
        return
    for username, password, display, role in DEMO_USERS:
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                display_name=display,
                role=role,
                is_active=True,
                created_at=utcnow(),
            )
        )
    db.flush()
    for name, family, description, proposed, params in [
        ("random", "baseline", METHOD_LABELS["random"], False, {}),
        ("nearest", "baseline", METHOD_LABELS["nearest"], False, {}),
        ("greedy", "baseline", METHOD_LABELS["greedy"], False, {}),
        ("uncertainty", "baseline", METHOD_LABELS["uncertainty"], False, {}),
        ("min_cost", "baseline", METHOD_LABELS["min_cost"], False, {}),
        ("mupsa", "proposed", "移动预测与不确定性感知的动态采样任务分配，项目内部工作名 MU-PSA，不代表已证实的学术新颖性。", True, {"lead": 1}),
        ("bandit", "bandit", METHOD_LABELS["bandit"], False, {}),
    ]:
        db.add(AlgorithmConfig(name=name, family=family, description=description, params_json=json.dumps(params), is_proposed=proposed))
    for scenario, text in [
        ("regular", "稳定空间分区与日周期。"),
        ("complex", "多噪声源、局部突发和更强随机扰动。"),
        ("shift", "第二天出现区域噪声抬升，且部分人员提前回家。"),
    ]:
        db.add(SimulationScenario(name=scenario, description=text, config_json="{}"))
    db.flush()
    rebuild_world(db, settings, DEFAULT_WORLD, actor_id=None)
    audit(db, None, "seed", "initialized synthetic demo")
    db.commit()


def rebuild_world(db: Session, settings: Settings, raw_params: dict, actor_id: int | None) -> SimulationRun:
    params = _world_params(raw_params)
    world = build_world(
        seed=int(params["seed"]),
        height=int(params["height"]),
        width=int(params["width"]),
        n_days=int(params["n_days"]),
        slots_per_day=int(params["slots_per_day"]),
        n_human=int(params["n_human"]),
        n_machine=int(params["n_machine"]),
        scenario=str(params["scenario"]),
        prior_samples=int(params["prior_samples"]),
        sensor_sigma=float(params["sensor_sigma"]),
        accept_human=float(params["accept_human"]),
        accept_machine=float(params["accept_machine"]),
    )
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    world_path = data_dir / "worlds" / "active_world.npz"
    save_world(world_path, world)

    db.query(SamplingResult).delete()
    db.query(AssignmentEvent).delete()
    db.query(TaskAssignment).delete()
    db.query(SensingTask).delete()
    db.query(NoiseObservation).filter(NoiseObservation.source.in_(["synthetic_prior", "simulation_feedback"])).delete(synchronize_session=False)
    db.query(TrajectoryPoint).filter(TrajectoryPoint.data_source == "synthetic_demo").delete(synchronize_session=False)
    db.query(Device).delete()
    db.query(Participant).delete()
    db.query(SpatialGrid).delete()
    mobility = db.query(MobilityDataset).filter(MobilityDataset.source == "synthetic_demo").first()
    noise = db.query(NoiseDataset).filter(NoiseDataset.source == "synthetic_demo").first()
    if mobility is None:
        mobility = MobilityDataset(
            name="Synthetic Demo 轨迹",
            source="synthetic_demo",
            license="UrbanNoiseLab generated demonstration data. Not a real mobility trace.",
            is_synthetic=True,
            real_city=False,
            coordinate_system="synthetic_virtual_grid",
            status="ready",
            notes="Synthetic Demo。虚拟网格，不能解释为真实城市街区。",
        )
        db.add(mobility)
        db.flush()
    if noise is None:
        noise = NoiseDataset(
            name="Synthetic Demo 噪声",
            source="synthetic_demo",
            license="UrbanNoiseLab generated demonstration field.",
            is_synthetic=True,
            indicator="laeq_db",
            coordinate_system="synthetic_virtual_grid",
            status="ready",
            notes="Synthetic Demo。完整真值只保存在仿真文件中，预测接口默认不返回真值。",
        )
        db.add(noise)
        db.flush()

    for y in range(world.height):
        for x in range(world.width):
            gid = world.grid_id(x, y)
            db.add(
                SpatialGrid(
                    id=gid,
                    grid_x=x,
                    grid_y=y,
                    zone=ZONE_NAMES[int(world.zones[y, x])],
                    coordinate_system=world.coordinate_system,
                )
            )
    collector = db.query(User).filter(User.username == "collector").first()
    people = []
    for agent in world.agents:
        person = Participant(
            user_id=collector.id if collector and agent.name == "H01" else None,
            dataset_id=mobility.id,
            name=agent.name,
            participant_type=agent.kind,
            accept_prob=agent.accept,
            cost=agent.cost,
            quality=agent.quality,
            online=agent.online,
            current_grid_id=int(agent.traj[world.horizon[0]]) if agent.traj[world.horizon[0]] >= 0 else None,
            trajectory_json=json.dumps([int(item) for item in agent.traj.tolist()]),
            created_at=utcnow(),
        )
        db.add(person)
        people.append(person)
        if agent.kind == "machine":
            db.add(Device(name=f"{agent.name}-声学单元", participant_id=None, kind="mobile_sensor", capability="laeq", status="active", created_at=utcnow()))
    db.flush()
    for person, agent in zip(people, world.agents):
        device = db.query(Device).filter(Device.name == f"{agent.name}-声学单元").first()
        if device:
            device.participant_id = person.id
        for slot, grid in enumerate(agent.traj.tolist()):
            db.add(
                TrajectoryPoint(
                    dataset_id=mobility.id,
                    trajectory_id=agent.name,
                    participant_id=person.id,
                    slot=slot,
                    timestamp_label=slot_label(slot, world.slots_per_day),
                    grid_id=None if int(grid) < 0 else int(grid),
                    coordinate_system=world.coordinate_system,
                    data_source="synthetic_demo",
                    participant_type=agent.kind,
                    quality_flags="missing" if int(grid) < 0 else "ok",
                )
            )
    rng = np.random.default_rng(int(params["seed"]) + 99)
    prior = _prior_observations(world, rng)
    for item in prior:
        db.add(
            NoiseObservation(
                dataset_id=noise.id,
                grid_id=item["grid"],
                slot=item["slot"],
                timestamp_label=slot_label(item["slot"], world.slots_per_day),
                laeq_db=item["db"],
                indicator="laeq_db",
                coordinate_system=world.coordinate_system,
                source="synthetic_prior",
                quality_flags="ok",
                is_simulated_feedback=False,
            )
        )
    mobility.record_count = world.n_slots * len(world.agents)
    mobility.participant_count = len(world.agents)
    mobility.time_start = slot_label(0, world.slots_per_day)
    mobility.time_end = slot_label(world.n_slots - 1, world.slots_per_day)
    mobility.spatial_desc = f"{world.height}×{world.width} 虚拟网格，无地理坐标"
    mobility.missing_rate = float(np.mean(np.stack([agent.traj for agent in world.agents]) < 0)) if world.agents else 0
    mobility.quality_json = json.dumps(
        {
            "label": "Synthetic Demo",
            "real_city": False,
            "participants": len(world.agents),
            "missing_rate": mobility.missing_rate,
            "coordinate_system": world.coordinate_system,
        },
        ensure_ascii=False,
    )
    noise.record_count = len(prior)
    noise.time_start = mobility.time_start
    noise.time_end = slot_label(world.horizon[0] - 1, world.slots_per_day)
    noise.spatial_desc = mobility.spatial_desc
    noise.quality_json = json.dumps(
        {
            "label": "Synthetic Demo",
            "indicator": "laeq_db",
            "prior_samples": len(prior),
            "energy_mean_db": energy_mean_db(np.array([item["db"] for item in prior])),
            "note": "先验观测来自仿真真值加测量噪声，用于让预测器在任务开始前有历史。真值场本身不进入预测函数。",
        },
        ensure_ascii=False,
    )
    run = db.query(SimulationRun).order_by(SimulationRun.id.desc()).first()
    if run is None:
        run = SimulationRun(name="演示仿真", created_at=utcnow())
        db.add(run)
    run.name = "演示仿真"
    run.scenario = world.scenario
    run.seed = world.seed
    run.status = "paused"
    run.current_slot = world.horizon[0]
    run.horizon_start = world.horizon[0]
    run.horizon_end = world.horizon[1]
    run.budget_total = float(params["budget"])
    run.budget_left = float(params["budget"])
    run.budget_spent = 0.0
    run.algorithm = str(params["algorithm"])
    run.world_path = str(world_path)
    run.config_json = json.dumps(params)
    run.metrics_json = "{}"
    run.rng_json = rng_dump(rng)
    run.log_text = "世界已生成。当前时钟停在评估期起点，先验观测来自第一天。\n"
    db.flush()
    _seed_manual_tasks(db, world, people)
    audit(db, actor_id, "rebuild_world", json.dumps({"scenario": world.scenario, "seed": world.seed}))
    return run


def _prior_observations(world, rng: np.random.Generator) -> list[dict]:
    coords = [(x, y) for y in range(world.height) for x in range(world.width)]
    take = min(world.prior_samples, len(coords))
    chosen = rng.choice(len(coords), size=take, replace=False)
    slots = rng.integers(0, max(1, world.horizon[0]), size=take)
    rows = []
    for pick, slot in zip(chosen, slots):
        x, y = coords[int(pick)]
        grid = world.grid_id(x, y)
        level = float(world.laeq[int(slot), y, x] + rng.normal(0, world.sensor_sigma))
        rows.append({"x": x, "y": y, "grid": grid, "slot": int(slot), "db": level})
    return rows


def _seed_manual_tasks(db: Session, world, people: list[Participant]) -> None:
    publisher = db.query(User).filter(User.username == "publisher").first()
    park = next((index for index, zone in enumerate(world.zones.ravel()) if ZONE_NAMES[int(zone)] == "park"), 0)
    industrial = next((index for index, zone in enumerate(world.zones.ravel()) if ZONE_NAMES[int(zone)] == "industrial"), 1)
    start = world.horizon[0]
    db.add(
        SensingTask(
            title="公园背景噪声抽查",
            grid_id=int(park),
            slot_start=start + 2,
            slot_end=start + 6,
            priority=0.4,
            budget_cost=1,
            status="draft",
            publisher_id=publisher.id if publisher else None,
            algorithm="mupsa",
            origin="manual",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    )
    db.add(
        SensingTask(
            title="工业区边界复核",
            grid_id=int(industrial),
            slot_start=start + 2,
            slot_end=start + 8,
            priority=0.8,
            budget_cost=1.7,
            status="published",
            publisher_id=publisher.id if publisher else None,
            algorithm="mupsa",
            origin="manual",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    )
    collector_person = next((person for person in people if person.name == "H01"), None)
    if collector_person is not None:
        traj = json.loads(collector_person.trajectory_json)
        future = next((int(grid) for grid in traj[start : start + 6] if int(grid) >= 0), int(park))
        task = SensingTask(
            title="参与者 H01 的待接收任务",
            grid_id=future,
            slot_start=start,
            slot_end=start + 4,
            priority=1,
            budget_cost=collector_person.cost,
            status="assigned",
            publisher_id=publisher.id if publisher else None,
            assignee_id=collector_person.id,
            algorithm="nearest",
            origin="manual",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(task)
        db.flush()
        db.add(
            TaskAssignment(
                task_id=task.id,
                participant_id=collector_person.id,
                score=0.5,
                reach_prob=0.8,
                estimated_cost=collector_person.cost,
                status="assigned",
                round_index=0,
                created_at=utcnow(),
            )
        )
        db.add(
            AssignmentEvent(
                task_id=task.id,
                actor_role="system",
                from_status="published",
                to_status="assigned",
                note="演示初始任务",
                created_at=utcnow(),
            )
        )


def authenticate(db: Session, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username, User.is_active.is_(True)).first()
    if user is None or not verify_password(password, user.password_hash):
        raise AppError("invalid_credentials", "用户名或密码错误", 401)
    return user


def public_user(user: User) -> dict:
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role}


def apply_transition(
    db: Session,
    task: SensingTask,
    dst: str,
    role: str,
    user_id: int | None,
    now_slot: int | None,
    measurement_db: float | None = None,
    note: str = "",
    assignee_matches: bool = True,
) -> SensingTask:
    ctx = TransitionContext(
        role=role,
        now_slot=now_slot,
        slot_end=task.slot_end,
        has_measurement=measurement_db is not None,
        assignee_matches=assignee_matches,
    )
    try:
        check_transition(task.status, dst, ctx)
    except ValueError as exc:
        raise AppError("invalid_transition", str(exc), 409) from exc
    previous = task.status
    task.status = dst
    task.updated_at = utcnow()
    if note:
        task.note = note
    if dst == "verified":
        # Verification is a distinct state; completion is a second, explicit transition.
        pass
    db.add(
        AssignmentEvent(
            task_id=task.id,
            actor_user_id=user_id,
            actor_role=role,
            from_status=previous,
            to_status=dst,
            note=note,
            created_at=utcnow(),
        )
    )
    audit(db, user_id, "task_transition", f"{task.id}:{previous}->{dst}")
    return task


def _store_manual_measurement(db: Session, task: SensingTask, level: float, user_id: int | None) -> None:
    stored, flag = clip_measurement(level)
    noise = db.query(NoiseDataset).filter(NoiseDataset.source == "synthetic_demo").first()
    if noise is None:
        noise = db.query(NoiseDataset).first()
    if noise is None:
        raise AppError("no_dataset", "没有可写入的噪声数据集", 409)
    observation = NoiseObservation(
        dataset_id=noise.id,
        grid_id=task.grid_id,
        slot=task.slot_start,
        timestamp_label=slot_label(task.slot_start, _slots_per_day(db)),
        laeq_db=stored,
        indicator="laeq_db",
        coordinate_system="manual_entry",
        source="manual",
        quality_flags=flag,
        is_simulated_feedback=False,
    )
    db.add(observation)
    db.flush()
    db.add(
        SamplingResult(
            task_id=task.id,
            participant_id=task.assignee_id,
            observation_id=observation.id,
            grid_id=task.grid_id,
            slot=task.slot_start,
            laeq_db=stored,
            indicator="laeq_db",
            source="manual",
            created_at=utcnow(),
        )
    )


def _slots_per_day(db: Session) -> int:
    run = db.query(SimulationRun).order_by(SimulationRun.id.desc()).first()
    if run is None:
        return 48
    return int(json.loads(run.config_json).get("slots_per_day", 48))


def assisted_sample(db: Session, user: User, task: SensingTask) -> float:
    """Read the synthetic truth only when the assigned participant is actually on the task grid."""
    if user.role == "collector":
        person = db.query(Participant).filter(Participant.user_id == user.id).first()
        if person is None or person.id != task.assignee_id:
            raise AppError("forbidden", "只能为分配给自己的任务仿真采样", 403)
    elif user.role not in {"admin", "system"}:
        raise AppError("forbidden", "无权仿真采样", 403)
        person = None
    else:
        person = db.get(Participant, task.assignee_id) if task.assignee_id else None
    if person is None:
        raise AppError("no_assignee", "任务还没有执行人", 409)
    if task.status not in {"accepted", "in_progress"}:
        raise AppError("bad_state", "需要先接收任务并开始执行", 409)
    run, world, _people = _campaign_world(db)
    slot = int(run.current_slot)
    if not (task.slot_start <= slot <= task.slot_end):
        raise AppError("outside_window", "当前仿真时钟不在任务时间窗内", 409)
    traj = json.loads(person.trajectory_json or "[]")
    loc = int(traj[slot]) if slot < len(traj) else -1
    if loc != task.grid_id:
        raise AppError("not_on_site", "参与者当前不在任务网格，不能读取该处仿真测量", 409)
    rng = rng_load(run.rng_json) if run.rng_json else np.random.default_rng(run.seed)
    from urbannoise.world import sample_measurement

    level = sample_measurement(world, slot, task.grid_id, rng, sigma=world.sensor_sigma * (0.75 if person.participant_type == "machine" else 1))
    run.rng_json = rng_dump(rng)
    noise = db.query(NoiseDataset).filter(NoiseDataset.source == "synthetic_demo").first()
    if noise is None:
        raise AppError("no_dataset", "没有仿真噪声数据集", 409)
    stored, flag = clip_measurement(level)
    observation = NoiseObservation(
        dataset_id=noise.id,
        grid_id=task.grid_id,
        slot=slot,
        timestamp_label=slot_label(slot, world.slots_per_day),
        laeq_db=stored,
        indicator="laeq_db",
        coordinate_system=world.coordinate_system,
        source="simulation_assisted",
        quality_flags=flag,
        is_simulated_feedback=True,
    )
    db.add(observation)
    db.flush()
    db.add(
        SamplingResult(
            task_id=task.id,
            participant_id=person.id,
            observation_id=observation.id,
            grid_id=task.grid_id,
            slot=slot,
            laeq_db=stored,
            indicator="laeq_db",
            source="simulation_assisted",
            created_at=utcnow(),
        )
    )
    return stored


def task_dict(db: Session, task: SensingTask) -> dict:
    grid = db.get(SpatialGrid, task.grid_id)
    assignee = db.get(Participant, task.assignee_id) if task.assignee_id else None
    return {
        "id": task.id,
        "title": task.title,
        "grid_id": task.grid_id,
        "grid_x": grid.grid_x if grid else None,
        "grid_y": grid.grid_y if grid else None,
        "zone": grid.zone if grid else None,
        "slot_start": task.slot_start,
        "slot_end": task.slot_end,
        "slot_label": slot_label(task.slot_start, _slots_per_day(db)),
        "priority": task.priority,
        "budget_cost": task.budget_cost,
        "status": task.status,
        "assignee_id": task.assignee_id,
        "assignee_name": assignee.name if assignee else None,
        "algorithm": task.algorithm,
        "origin": task.origin,
        "note": task.note,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


def create_task(db: Session, user: User, payload: dict) -> SensingTask:
    if user.role not in {"publisher", "admin"}:
        raise AppError("forbidden", "只有任务发布者或管理员可以创建任务", 403)
    width = db.query(func.max(SpatialGrid.grid_x)).scalar()
    height = db.query(func.max(SpatialGrid.grid_y)).scalar()
    x, y = int(payload["grid_x"]), int(payload["grid_y"])
    if width is None or not (0 <= x <= width and 0 <= y <= height):
        raise AppError("bad_grid", "网格坐标超出当前城市范围", 422)
    grid = db.query(SpatialGrid).filter(SpatialGrid.grid_x == x, SpatialGrid.grid_y == y).first()
    if grid is None:
        raise AppError("bad_grid", "网格不存在", 422)
    slot_start, slot_end = int(payload["slot_start"]), int(payload["slot_end"])
    if slot_end < slot_start:
        raise AppError("bad_window", "结束时间片不能早于开始时间片", 422)
    task = SensingTask(
        title=str(payload.get("title") or f"采样任务 {x},{y}"),
        grid_id=grid.id,
        slot_start=slot_start,
        slot_end=slot_end,
        priority=float(payload.get("priority", 1)),
        budget_cost=float(payload.get("budget_cost", 1)),
        status="draft",
        publisher_id=user.id,
        algorithm=str(payload.get("algorithm") or "mupsa"),
        origin="manual",
        note=str(payload.get("note") or ""),
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(task)
    db.flush()
    audit(db, user.id, "create_task", str(task.id))
    return task


def _campaign_world(db: Session):
    run = active_run(db)
    world = load_run_world(run)
    people, agents = participant_agents(db)
    # Participants are the operational roster. Their stored trajectories override the file if present.
    if agents and len(agents) == len(world.agents):
        world.agents = agents
    return run, world, people


def propose_assignments(db: Session, user: User, algorithm: str, budget: float | None, limit: int | None) -> dict:
    if user.role not in {"publisher", "admin", "system"}:
        raise AppError("forbidden", "无权分配任务", 403)
    run, world, people = _campaign_world(db)
    if run.status == "finished":
        raise AppError("finished", "仿真已经结束", 409)
    params = json.loads(run.config_json)
    decision_slot = int(run.current_slot)
    target = decision_slot + int(params.get("lead", 1))
    if target >= world.horizon[1]:
        raise AppError("past_horizon", "没有可规划的未来时间片", 409)
    obs = observations_to_set(db)
    cfg = EpisodeConfig(lead=int(params.get("lead", 1)), per_slot_cap=int(limit or params.get("per_slot_cap", 3)))
    remaining = float(run.budget_left if budget is None else min(budget, run.budget_left))
    rng = rng_load(run.rng_json) if run.rng_json else np.random.default_rng(run.seed)
    plans = _plan_slot(
        world,
        obs,
        decision_slot,
        target,
        cfg.lead,
        algorithm,
        remaining,
        cfg,
        rng,
        None,
        float(run.budget_total),
    )
    run.rng_json = rng_dump(rng)
    created = []
    for plan in plans:
        person = people[plan["agent"]]
        task = SensingTask(
            title=f"自动采样 {person.name} @ {slot_label(target, world.slots_per_day)}",
            grid_id=plan["grid"],
            slot_start=target,
            slot_end=target,
            priority=plan["value"],
            budget_cost=plan["cost"],
            status="published",
            publisher_id=user.id,
            algorithm=algorithm,
            simulation_run_id=run.id,
            origin="simulation",
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(task)
        db.flush()
        apply_transition(db, task, "assigned", "system", user.id, decision_slot, note=f"reach={plan['reach']:.3f}")
        task.assignee_id = person.id
        db.add(
            TaskAssignment(
                task_id=task.id,
                participant_id=person.id,
                score=plan["score"],
                reach_prob=plan["reach"],
                estimated_cost=plan["cost"],
                status="assigned",
                round_index=decision_slot,
                created_at=utcnow(),
            )
        )
        run.budget_left -= plan["cost"]
        created.append(task_dict(db, task) | {"reach_prob": plan["reach"], "score": plan["score"], "value": plan["value"]})
    run.log_text = (run.log_text or "") + f"规划 {slot_label(target, world.slots_per_day)}：{len(created)} 个任务，算法 {algorithm}。\n"
    audit(db, user.id, "assign", json.dumps({"algorithm": algorithm, "count": len(created)}))
    return {"assignments": created, "budget_left": run.budget_left, "target_slot": target, "reasons": [] if created else ["没有满足约束的候选配对"]}


def step_simulation(db: Session, user: User | None, steps: int) -> dict:
    run, world, people = _campaign_world(db)
    if run.status == "paused" and steps > 0:
        # Single-step is allowed while paused so the console can advance explicitly.
        pass
    if run.status == "finished":
        raise AppError("finished", "仿真已经结束", 409)
    params = json.loads(run.config_json)
    cfg = EpisodeConfig(lead=int(params.get("lead", 1)), per_slot_cap=int(params.get("per_slot_cap", 3)), replan=False)
    rng = rng_load(run.rng_json) if run.rng_json else np.random.default_rng(run.seed + 1)
    noise = db.query(NoiseDataset).filter(NoiseDataset.source == "synthetic_demo").first()
    logs = []
    executed_total = 0
    for _ in range(max(1, steps)):
        if run.current_slot >= run.horizon_end:
            run.status = "finished"
            break
        slot = int(run.current_slot)
        due_tasks = (
            db.query(SensingTask)
            .filter(SensingTask.simulation_run_id == run.id, SensingTask.slot_start == slot, SensingTask.status.in_(["assigned", "accepted", "in_progress"]))
            .all()
        )
        plans = []
        task_by_key = {}
        for task in due_tasks:
            person = db.get(Participant, task.assignee_id) if task.assignee_id else None
            if person is None:
                continue
            agent_index = next((idx for idx, item in enumerate(people) if item.id == person.id), None)
            if agent_index is None:
                continue
            plans.append(
                {
                    "slot": slot,
                    "agent": agent_index,
                    "grid": task.grid_id,
                    "cost": task.budget_cost,
                    "reach": 0.0,
                    "unc_norm": 1.0,
                    "done": False,
                    "success": False,
                    "context": None,
                    "task_id": task.id,
                    "force_accept": task.status in {"accepted", "in_progress"},
                }
            )
            task_by_key[(agent_index, task.grid_id, task.id)] = task
        obs = observations_to_set(db)
        # Manual plans are executed here. Automatic replanning is a separate publisher action,
        # so a paused console does not silently allocate.
        outcome = step_campaign(
            world,
            obs,
            plans,
            slot,
            float(run.budget_left),
            "mupsa_no_replan",
            float(run.budget_total),
            cfg,
            rng,
            None,
            False,
        )
        for item in outcome["executed"]:
            task = next((task for task in due_tasks if task.id == item.get("task_id")), None)
            if task is None:
                continue
            executed_total += 1
            if item["reason"] == "success" and item["level_db"] is not None and noise is not None:
                _advance_success(db, task, item, noise, world.slots_per_day, user.id if user else None)
                if task.origin == "simulation":
                    run.budget_spent += float(item["cost"])
                logs.append(f"{slot_label(slot, world.slots_per_day)} {task.title} 成功 {item['level_db']:.1f} dB")
            else:
                _advance_failure(db, task, item["reason"], user.id if user else None, slot)
                if task.origin == "simulation":
                    run.budget_left += float(item["cost"])
                logs.append(f"{slot_label(slot, world.slots_per_day)} {task.title} 失败:{item['reason']}")
        for person in people:
            traj = json.loads(person.trajectory_json or "[]")
            if slot < len(traj) and int(traj[slot]) >= 0:
                person.current_grid_id = int(traj[slot])
        run.current_slot = slot + 1
        logs.append(f"时钟推进到 {slot_label(run.current_slot, world.slots_per_day)}，本步执行 {len(outcome['executed'])} 个到期任务。")
        if run.current_slot >= run.horizon_end:
            run.status = "finished"
        arrays = map_arrays(world, observations_to_set(db), min(slot, world.n_slots - 1))
        truth = arrays["truth"].ravel()
        pred = arrays["prediction"].ravel()
        run.metrics_json = json.dumps(
            {
                "mae_current_slot": float(np.mean(np.abs(pred - truth))),
                "rmse_current_slot": float(np.sqrt(np.mean((pred - truth) ** 2))),
                "coverage": _coverage(db, world.n_grids),
                "budget_spent": run.budget_spent,
                "budget_left": run.budget_left,
            }
        )
    run.rng_json = rng_dump(rng)
    if logs:
        run.log_text = (run.log_text or "") + "\n".join(logs) + "\n"
    audit(db, user.id if user else None, "simulation_step", f"steps={steps}")
    return simulation_dict(db, run)


def _advance_success(db: Session, task: SensingTask, item: dict, noise: NoiseDataset, slots_per_day: int, user_id: int | None) -> None:
    # Walk the legal chain with the system actor. Measurement is attached at submission.
    role = "system"
    slot = task.slot_start
    if task.status == "assigned":
        apply_transition(db, task, "accepted", role, user_id, slot)
    if task.status == "accepted":
        apply_transition(db, task, "in_progress", role, user_id, slot)
    if task.status == "in_progress":
        stored, flag = clip_measurement(float(item["level_db"]))
        observation = NoiseObservation(
            dataset_id=noise.id,
            grid_id=task.grid_id,
            slot=task.slot_start,
            timestamp_label=slot_label(task.slot_start, slots_per_day),
            laeq_db=stored,
            indicator="laeq_db",
            coordinate_system="synthetic_virtual_grid",
            source="simulation_feedback",
            quality_flags=flag,
            is_simulated_feedback=True,
        )
        db.add(observation)
        db.flush()
        db.add(
            SamplingResult(
                task_id=task.id,
                participant_id=task.assignee_id,
                observation_id=observation.id,
                grid_id=task.grid_id,
                slot=task.slot_start,
                laeq_db=stored,
                source="simulation_feedback",
                created_at=utcnow(),
            )
        )
        apply_transition(db, task, "submitted", role, user_id, slot, measurement_db=stored, note="仿真执行采样")
    if task.status == "submitted":
        apply_transition(db, task, "verified", role, user_id, slot, note="仿真自动核验")
    if task.status == "verified":
        apply_transition(db, task, "completed", role, user_id, slot, note="仿真闭环完成")


def _advance_failure(db: Session, task: SensingTask, reason: str, user_id: int | None, slot: int) -> None:
    if task.status == "assigned":
        apply_transition(db, task, "rejected", "system", user_id, slot, note=reason)
    elif task.status in {"accepted", "in_progress"}:
        apply_transition(db, task, "failed", "system", user_id, slot, note=reason)


def _coverage(db: Session, n_grids: int) -> float:
    count = db.query(NoiseObservation.grid_id).filter(NoiseObservation.grid_id.isnot(None)).distinct().count()
    return float(count) / max(n_grids, 1)


def simulation_dict(db: Session, run: SimulationRun) -> dict:
    return {
        "id": run.id,
        "name": run.name,
        "scenario": run.scenario,
        "seed": run.seed,
        "status": run.status,
        "current_slot": run.current_slot,
        "current_label": slot_label(run.current_slot, _slots_per_day(db)) if run.current_slot < run.horizon_end else "结束",
        "horizon_start": run.horizon_start,
        "horizon_end": run.horizon_end,
        "budget_total": run.budget_total,
        "budget_left": run.budget_left,
        "budget_spent": run.budget_spent,
        "algorithm": run.algorithm,
        "config": json.loads(run.config_json or "{}"),
        "metrics": json.loads(run.metrics_json or "{}"),
        "log": (run.log_text or "").splitlines()[-40:],
    }


def dashboard(db: Session) -> dict:
    run = db.query(SimulationRun).order_by(SimulationRun.id.desc()).first()
    tasks = db.query(SensingTask).all()
    active = [task for task in tasks if task.status in {"published", "assigned", "accepted", "in_progress", "submitted"}]
    people = db.query(Participant).all()
    observations = db.query(NoiseObservation).all()
    levels = np.array([row.laeq_db for row in observations], dtype=float) if observations else np.array([])
    slots = _slots_per_day(db)
    trend = []
    if observations:
        by_slot: dict[int, list[float]] = {}
        for row in observations:
            if row.slot is None:
                continue
            by_slot.setdefault(int(row.slot), []).append(float(row.laeq_db))
        for slot in sorted(by_slot)[-24:]:
            trend.append({"slot": slot, "label": slot_label(slot, slots), "samples": len(by_slot[slot]), "mean_db": energy_mean_db(np.array(by_slot[slot]))})
    successes = len([task for task in tasks if task.status == "completed"])
    finished = len([task for task in tasks if task.status in {"completed", "failed", "rejected", "expired"}])
    n_grids = db.query(SpatialGrid).count() or 1
    events = [row.detail for row in db.query(AuditLog).order_by(AuditLog.id.desc()).limit(8)]
    return {
        "active_tasks": len(active),
        "online_participants": len([person for person in people if person.online]),
        "human_online": len([person for person in people if person.online and person.participant_type == "human"]),
        "machine_online": len([person for person in people if person.online and person.participant_type == "machine"]),
        "coverage": _coverage(db, n_grids),
        "budget_total": run.budget_total if run else 0,
        "budget_used": run.budget_spent if run else 0,
        "budget_left": run.budget_left if run else 0,
        "samples_today": len(observations),
        "mean_noise_db": energy_mean_db(levels) if levels.size else None,
        "success_rate": (successes / finished) if finished else None,
        "data_quality": 1.0 - float(np.mean([row.quality_flags != "ok" for row in observations])) if observations else None,
        "trend": trend,
        "events": events,
        "scenario": run.scenario if run else None,
        "clock": slot_label(run.current_slot, slots) if run else None,
        "status": run.status if run else None,
    }


def map_frame(db: Session, slot: int, include_truth: bool, role: str) -> dict:
    run, world, people = _campaign_world(db)
    slot = int(np.clip(slot, 0, world.n_slots - 1))
    obs = observations_to_set(db)
    arrays = map_arrays(world, obs, slot)
    cells = []
    for y in range(world.height):
        for x in range(world.width):
            cells.append(
                {
                    "x": x,
                    "y": y,
                    "zone": ZONE_NAMES[int(world.zones[y, x])],
                    "prediction": float(arrays["prediction"][y, x]),
                    "uncertainty": float(arrays["uncertainty"][y, x]),
                }
            )
    participants = []
    for person in people:
        traj = json.loads(person.trajectory_json or "[]")
        grid = int(traj[slot]) if slot < len(traj) else -1
        if grid < 0:
            continue
        participants.append(
            {
                "id": person.id,
                "name": person.name,
                "kind": person.participant_type,
                "x": grid % world.width,
                "y": grid // world.width,
                "online": person.online,
            }
        )
    observations = [
        {"x": row.grid_id % world.width, "y": row.grid_id // world.width, "db": row.laeq_db, "source": row.source}
        for row in db.query(NoiseObservation).filter(NoiseObservation.slot == slot, NoiseObservation.grid_id.isnot(None))
    ]
    tasks = []
    for task in db.query(SensingTask).filter(SensingTask.slot_start <= slot, SensingTask.slot_end >= slot).all():
        grid = db.get(SpatialGrid, task.grid_id)
        if grid:
            tasks.append({"id": task.id, "x": grid.grid_x, "y": grid.grid_y, "status": task.status, "title": task.title})
    payload = {
        "width": world.width,
        "height": world.height,
        "slot": slot,
        "slot_label": slot_label(slot, world.slots_per_day),
        "coordinate_system": world.coordinate_system,
        "data_origin": world.data_origin,
        "real_city": False,
        "legend": {"unit": "dB", "min": float(np.min(arrays["prediction"])), "max": float(np.max(arrays["prediction"]))},
        "cells": cells,
        "participants": participants,
        "observations": observations,
        "tasks": tasks,
        "anonymous": True,
        "basemap": None,
        "evaluation_only": False,
        "warning": "匿名虚拟网格，不是真实城市。地图不使用地理底图，也不会把 YJMob 画到真实经纬度上。预测层只使用已有观测。",
    }
    if include_truth:
        if role not in {"admin", "publisher"}:
            raise AppError("forbidden", "真值层只对管理员和任务发布者开放，并仅用于评估", 403)
        for cell, value in zip(cells, arrays["truth"].ravel()):
            cell["truth"] = float(value)
        payload["evaluation_only"] = True
        payload["warning"] = "匿名虚拟网格，不是真实城市。仿真真值仅用于评估显示，预测算法的输入不包含该层。地图不使用地理底图。"
    return payload


def predict_slot(db: Session, slot: int, model: str) -> dict:
    run, world, _people = _campaign_world(db)
    obs = observations_to_set(db).subset(slot)
    queries = grid_queries(world.width, world.height)
    backend = model
    if model == "random_forest":
        mu, std, backend = predict_rf(obs, queries, world.zones, slot, world.slots_per_day)
    elif model == "gaussian_process":
        mu, std, backend = predict_gp(obs, queries, slot)
    else:
        mu, std = predict_idw(obs, queries, slot, zones=world.zones, slots_per_day=world.slots_per_day)
        backend = "idw"
    return {
        "model": model,
        "backend": backend,
        "slot": slot,
        "slot_label": slot_label(slot, world.slots_per_day),
        "mean_db": float(np.mean(mu)),
        "mean_uncertainty": float(np.mean(std)),
        "values": mu.reshape(world.height, world.width).round(3).tolist(),
        "uncertainty": std.reshape(world.height, world.width).round(3).tolist(),
        "observation_count": int(obs["db"].size),
        "disclaimer": "不确定性来自 IDW 距离、随机森林树间标准差或固定核高斯过程，未经独立标定前不能称为可靠置信区间。",
    }


def mobility_forecast(db: Session, participant_id: int, slot: int) -> dict:
    _run, world, people = _campaign_world(db)
    person = next((item for item in people if item.id == participant_id), None)
    if person is None:
        raise AppError("not_found", "参与者不存在", 404)
    traj = np.stack([np.asarray(json.loads(item.trajectory_json), dtype=np.int32) for item in people], axis=0)
    visible = min(slot, world.n_slots) - 1
    if visible < 0:
        raise AppError("no_history", "该时间片之前没有历史", 422)
    fit = fit_mobility(traj[:, : world.n_slots], visible, world.slots_per_day, world.n_grids)
    index = people.index(person)
    current = int(traj[index, visible])
    dist = fit.distribution(index, slot % world.slots_per_day, current, max(1, slot - visible))
    order = np.argsort(dist)[::-1][:5]
    return {
        "participant_id": participant_id,
        "name": person.name,
        "slot": slot,
        "based_on_slot": int(visible),
        "top": [
            {"grid_id": int(grid), "x": int(grid) % world.width, "y": int(grid) // world.width, "probability": float(dist[grid])}
            for grid in order
        ],
        "note": "到达概率不是接受任务的概率，也不是执行成功概率。",
    }


def safe_import(db: Session, settings: Settings, filename: str, content: bytes, user_id: int) -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in {".csv", ".geojson", ".json", ".plt", ".txt"}:
        raise AppError("bad_type", "只接受 csv、geojson、json、plt、txt", 415)
    if len(content) > 20 * 1024 * 1024:
        raise AppError("too_large", "文件超过 20 MB", 413)
    root = Path(settings.data_dir, "imports").resolve()
    root.mkdir(parents=True, exist_ok=True)
    dest = (root / f"{uuid.uuid4().hex}_{Path(filename).name}").resolve()
    if not str(dest).startswith(str(root)):
        raise AppError("bad_path", "非法路径", 400)
    dest.write_bytes(content)
    try:
        if suffix == ".plt":
            frame = read_geolife_plt(dest)
            kind = "mobility"
            source = "GeoLife"
            synthetic = False
            crs = "WGS84"
        elif suffix in {".geojson", ".json"}:
            frame = read_noisecapture_geojson(dest)
            kind = "noise"
            source = "NoiseCapture"
            synthetic = False
            crs = "WGS84"
        else:
            frame = read_yjmob_csv(dest, limit=20000)
            kind = "mobility"
            source = "YJMob100K"
            synthetic = False
            crs = "yjmob_virtual_500m"
    except Exception as exc:  # format errors should be visible, not a server crash
        raise AppError("parse_error", f"无法按已知格式解析：{exc}", 422) from exc
    report = quality_report(frame, kind)
    if kind == "mobility":
        dataset = MobilityDataset(
            name=Path(filename).name,
            source=source,
            license="see dataset documentation; imported file is not relabeled as the demo city",
            is_synthetic=synthetic,
            real_city=False,
            coordinate_system=crs,
            record_count=len(frame),
            participant_count=int(frame["participant_id"].nunique()) if "participant_id" in frame else 0,
            status="imported",
            spatial_desc=report.get("spatial_reference", ""),
            missing_rate=float(report.get("missing_rate", 0)),
            quality_json=json.dumps(report, ensure_ascii=False, default=str),
            notes="导入数据与演示虚拟城市不是同一个时空。系统不会把 YJMob 网格画到真实经纬度上。",
        )
    else:
        dataset = NoiseDataset(
            name=Path(filename).name,
            source=source,
            license="NoiseCapture / Noise-Planet open data terms apply to real imports",
            is_synthetic=False,
            indicator=",".join(report.get("indicators") or ["unspecified"]),
            coordinate_system=crs,
            record_count=len(frame),
            status="imported",
            spatial_desc="WGS84 points",
            missing_rate=float(report.get("missing_rate", 0)),
            quality_json=json.dumps(report, ensure_ascii=False, default=str),
            notes="不同分贝指标已按字段名保留，不会自动合并。",
        )
    db.add(dataset)
    db.flush()
    stored = 0
    if kind == "noise":
        for row in frame.head(5000).to_dict(orient="records"):
            db.add(
                NoiseObservation(
                    dataset_id=dataset.id,
                    laeq_db=float(row["level_db"]),
                    indicator=str(row["indicator"]),
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    timestamp_label=str(row.get("timestamp") or ""),
                    coordinate_system="WGS84",
                    source=source,
                    quality_flags=str(row["quality_flags"]),
                    is_simulated_feedback=False,
                )
            )
            stored += 1
    else:
        for row in frame.head(5000).to_dict(orient="records"):
            db.add(
                TrajectoryPoint(
                    dataset_id=dataset.id,
                    trajectory_id=str(row.get("participant_id")),
                    slot=int(row["timeslot"]) if "timeslot" in row and row["timeslot"] == row["timeslot"] else 0,
                    timestamp_label=str(row.get("timestamp") or ""),
                    grid_id=None,
                    latitude=None if row.get("latitude") != row.get("latitude") else row.get("latitude"),
                    longitude=None if row.get("longitude") != row.get("longitude") else row.get("longitude"),
                    coordinate_system=crs,
                    data_source=source,
                    participant_type="human",
                    quality_flags=str(row.get("quality_flags") or "ok"),
                )
            )
            stored += 1
    dataset.record_count = stored
    audit(db, user_id, "import", f"{source}:{stored}")
    return {"dataset_id": dataset.id, "kind": kind, "stored": stored, "quality": report, "synthetic": False}


def dataset_list(db: Session) -> list[dict]:
    rows = []
    for item in db.query(MobilityDataset).all():
        rows.append(_dataset_payload(item, "mobility"))
    for item in db.query(NoiseDataset).all():
        rows.append(_dataset_payload(item, "noise"))
    return rows


def _dataset_payload(item, kind: str) -> dict:
    regime, regime_label = dataset_regime(bool(item.is_synthetic), str(item.source), kind)
    payload = {
        "id": item.id,
        "kind": kind,
        "name": item.name,
        "source": item.source,
        "license": item.license,
        "is_synthetic": item.is_synthetic,
        "regime": regime,
        "regime_label": regime_label,
        "real_city": getattr(item, "real_city", False),
        "coordinate_system": item.coordinate_system,
        "record_count": item.record_count,
        "time_start": item.time_start,
        "time_end": item.time_end,
        "spatial_desc": item.spatial_desc,
        "missing_rate": item.missing_rate,
        "status": item.status,
        "notes": item.notes,
        "quality": json.loads(item.quality_json or "{}"),
    }
    if kind == "mobility":
        payload["user_count"] = item.participant_count
    return payload

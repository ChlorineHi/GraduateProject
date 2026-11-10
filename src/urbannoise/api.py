"""HTTP API. Every mutating route writes the database; buttons in the UI call these routes."""

from __future__ import annotations

import csv
import io
import json
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, File, Header, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from urbannoise.db import healthcheck, init_db, make_engine, make_session_factory
from urbannoise.errors import AppError
from urbannoise.experiment import run_suite
from urbannoise.models import (
    AuditLog,
    Device,
    EvaluationMetric,
    ExperimentRun,
    IdempotencyKey,
    Participant,
    SensingTask,
    SimulationRun,
    User,
    utcnow,
)
from urbannoise.security import create_token, decode_token
from urbannoise.services import (
    active_run,
    apply_transition,
    assisted_sample,
    authenticate,
    create_task,
    dashboard,
    dataset_list,
    map_frame,
    mobility_forecast,
    propose_assignments,
    public_user,
    rebuild_world,
    safe_import,
    seed_if_needed,
    simulation_dict,
    step_simulation,
    task_dict,
    _store_manual_measurement,
)
from urbannoise.settings import Settings

LOGGER = logging.getLogger("urbannoise")
EXPERIMENT_LOCK = threading.Lock()


class LoginBody(BaseModel):
    username: str
    password: str


class TaskBody(BaseModel):
    title: str = ""
    grid_x: int
    grid_y: int
    slot_start: int
    slot_end: int
    priority: float = 1
    budget_cost: float = 1
    algorithm: str = "mupsa"
    note: str = ""


class TransitionBody(BaseModel):
    to_status: str
    note: str = ""
    measurement_db: float | None = None


class AssignBody(BaseModel):
    algorithm: str = "mupsa"
    budget: float | None = None
    limit: int | None = Field(default=3, ge=1, le=12)


class SimulationBody(BaseModel):
    action: str
    steps: int = Field(default=1, ge=1, le=48)
    scenario: str | None = None
    seed: int | None = None
    algorithm: str | None = None
    budget: float | None = None
    n_human: int | None = None
    n_machine: int | None = None
    accept_human: float | None = None
    mode: str | None = None
    mobility_source: str | None = None
    noise_source: str | None = None
    n_users: int | None = None
    grid_m: int | None = None
    noise_country: str | None = None
    day_min: int | None = None


class UserBody(BaseModel):
    username: str
    password: str
    display_name: str
    role: str


class ParticipantBody(BaseModel):
    online: bool | None = None
    accept_prob: float | None = None
    cost: float | None = None


class DeviceBody(BaseModel):
    name: str
    kind: str = "mobile_sensor"
    participant_id: int | None = None
    capability: str = "laeq"


class ExperimentBody(BaseModel):
    profile: str = "smoke"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    engine = make_engine(settings)
    factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_db(engine)
        if settings.auto_seed:
            db = factory()
            try:
                seed_if_needed(db, settings)
            finally:
                db.close()
        yield

    app = FastAPI(
        title="UrbanNoiseLab API",
        version="1.0.0",
        description="人机混合城市噪音预测采样与智能任务分配系统。演示环境，不可作为生产部署。",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.factory = factory

    def get_db():
        db = factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise AppError("unauthorized", "需要登录", 401)
        token = authorization.split(" ", 1)[1]
        try:
            payload = decode_token(token, settings.jwt_secret)
        except jwt.PyJWTError as exc:
            raise AppError("unauthorized", "登录已失效", 401) from exc
        user = db.get(User, int(payload["sub"]))
        if user is None or not user.is_active:
            raise AppError("unauthorized", "账号不可用", 401)
        return user

    def require(*roles: str):
        def dependency(user: User = Depends(current_user)) -> User:
            if user.role not in roles and user.role != "admin":
                raise AppError("forbidden", "权限不足", 403)
            return user

        return dependency

    @app.exception_handler(AppError)
    def _app_error(_request, exc: AppError):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}})

    @app.get("/api/health")
    def health():
        healthcheck(engine)
        return {"status": "ok", "service": "urbannoise", "database": "up"}

    @app.post("/api/auth/login")
    def login(body: LoginBody, db: Session = Depends(get_db)):
        user = authenticate(db, body.username.strip(), body.password)
        token = create_token(user.id, user.role, settings.jwt_secret, settings.jwt_exp_minutes)
        return {"token": token, "user": public_user(user), "demo_only": True}

    @app.get("/api/auth/me")
    def me(user: User = Depends(current_user)):
        return public_user(user)

    @app.get("/api/dashboard")
    def dash(db: Session = Depends(get_db), _user: User = Depends(current_user)):
        return dashboard(db)

    @app.get("/api/map/frame")
    def frame(
        slot: int = 0,
        include_truth: bool = False,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        return map_frame(db, slot, include_truth, user.role)

    @app.get("/api/predictions/noise")
    def noise_prediction(slot: int, model: str = "idw", db: Session = Depends(get_db), _user: User = Depends(current_user)):
        if model not in {"idw", "random_forest", "gaussian_process"}:
            raise AppError("bad_model", "未知预测模型", 422)
        return predict_noise(db, slot, model)

    @app.get("/api/predictions/mobility")
    def mobility_prediction(participant_id: int, slot: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
        return mobility_forecast(db, participant_id, slot)

    @app.get("/api/algorithms")
    def algorithms(db: Session = Depends(get_db), _user: User = Depends(current_user)):
        from urbannoise.models import AlgorithmConfig

        return {
            "items": [
                {
                    "name": row.name,
                    "family": row.family,
                    "description": row.description,
                    "is_proposed": row.is_proposed,
                    "params": json.loads(row.params_json or "{}"),
                }
                for row in db.query(AlgorithmConfig).all()
            ]
        }

    @app.get("/api/datasets")
    def datasets(db: Session = Depends(get_db), _user: User = Depends(current_user)):
        return {"items": dataset_list(db)}

    @app.get("/api/datasets/{kind}/{dataset_id}/quality")
    def dataset_quality(kind: str, dataset_id: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
        items = [item for item in dataset_list(db) if item["kind"] == kind and item["id"] == dataset_id]
        if not items:
            raise AppError("not_found", "数据集不存在", 404)
        return items[0]["quality"]

    @app.post("/api/datasets/import")
    def import_dataset(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        user: User = Depends(require("admin", "publisher")),
    ):
        content = file.file.read()
        return safe_import(db, settings, file.filename or "upload.csv", content, user.id)

    @app.get("/api/grids")
    def grids(db: Session = Depends(get_db), _user: User = Depends(current_user)):
        from urbannoise.models import SpatialGrid

        rows = db.query(SpatialGrid).order_by(SpatialGrid.id.asc()).all()
        return {"items": [{"id": row.id, "x": row.grid_x, "y": row.grid_y, "zone": row.zone, "coordinate_system": row.coordinate_system} for row in rows]}

    @app.get("/api/participants")
    def participants(db: Session = Depends(get_db), _user: User = Depends(current_user)):
        rows = db.query(Participant).order_by(Participant.id.asc()).all()
        return {"items": [_participant(row) for row in rows]}

    @app.patch("/api/participants/{participant_id}")
    def patch_participant(participant_id: int, body: ParticipantBody, db: Session = Depends(get_db), user: User = Depends(require("admin"))):
        person = db.get(Participant, participant_id)
        if person is None:
            raise AppError("not_found", "参与者不存在", 404)
        if body.online is not None:
            person.online = body.online
        if body.accept_prob is not None:
            person.accept_prob = body.accept_prob
        if body.cost is not None:
            person.cost = body.cost
        return _participant(person)

    @app.get("/api/devices")
    def devices(db: Session = Depends(get_db), _user: User = Depends(current_user)):
        return {"items": [_device(row) for row in db.query(Device).all()]}

    @app.post("/api/devices")
    def create_device(body: DeviceBody, db: Session = Depends(get_db), user: User = Depends(require("admin"))):
        row = Device(name=body.name, kind=body.kind, participant_id=body.participant_id, capability=body.capability, status="active")
        db.add(row)
        db.flush()
        return _device(row)

    @app.get("/api/trajectories")
    def trajectories(participant_id: int | None = None, limit: int = Query(default=500, le=5000), db: Session = Depends(get_db), user: User = Depends(current_user)):
        from urbannoise.models import TrajectoryPoint

        query = db.query(TrajectoryPoint).order_by(TrajectoryPoint.slot.asc())
        if participant_id:
            query = query.filter(TrajectoryPoint.participant_id == participant_id)
        if user.role == "collector":
            run = active_run(db)
            query = query.filter(TrajectoryPoint.slot < int(run.current_slot))
        rows = query.limit(limit).all()
        return {
            "items": [
                {
                    "participant_id": row.participant_id,
                    "trajectory_id": row.trajectory_id,
                    "slot": row.slot,
                    "timestamp": row.timestamp_label,
                    "grid_id": row.grid_id,
                    "latitude": row.latitude,
                    "longitude": row.longitude,
                    "coordinate_system": row.coordinate_system,
                    "data_source": row.data_source,
                    "quality_flags": row.quality_flags,
                }
                for row in rows
            ]
        }

    @app.get("/api/mobility/stats")
    def mobility_stats(db: Session = Depends(get_db), _user: User = Depends(current_user)):
        from urbannoise.models import TrajectoryPoint
        from urbannoise.services import _slots_per_day

        slots = _slots_per_day(db)
        rows = db.query(TrajectoryPoint).filter(TrajectoryPoint.data_source == "synthetic_demo", TrajectoryPoint.grid_id.isnot(None)).all()
        hist = [0] * slots
        hot: dict[int, int] = {}
        for row in rows:
            hist[int(row.slot) % slots] += 1
            hot[int(row.grid_id)] = hot.get(int(row.grid_id), 0) + 1
        top = sorted(hot.items(), key=lambda item: item[1], reverse=True)[:8]
        return {"by_timeslot": hist, "hot_grids": [{"grid_id": grid, "count": count} for grid, count in top], "points": len(rows)}

    @app.get("/api/observations")
    def observations(limit: int = Query(default=200, le=2000), db: Session = Depends(get_db), _user: User = Depends(current_user)):
        from urbannoise.models import NoiseObservation

        rows = db.query(NoiseObservation).order_by(NoiseObservation.id.desc()).limit(limit).all()
        return {
            "items": [
                {
                    "id": row.id,
                    "grid_id": row.grid_id,
                    "slot": row.slot,
                    "laeq_db": row.laeq_db,
                    "indicator": row.indicator,
                    "source": row.source,
                    "latitude": row.latitude,
                    "longitude": row.longitude,
                    "coordinate_system": row.coordinate_system,
                    "quality_flags": row.quality_flags,
                    "is_simulated_feedback": row.is_simulated_feedback,
                }
                for row in rows
            ]
        }

    @app.get("/api/tasks")
    def tasks(
        status: str | None = None,
        mine: bool = False,
        limit: int = Query(default=100, le=500),
        offset: int = 0,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        query = db.query(SensingTask).order_by(SensingTask.id.desc())
        if status:
            query = query.filter(SensingTask.status == status)
        if mine:
            person = db.query(Participant).filter(Participant.user_id == user.id).first()
            query = query.filter(SensingTask.assignee_id == (person.id if person else -1))
        total = query.count()
        rows = query.offset(offset).limit(limit).all()
        return {"items": [task_dict(db, row) for row in rows], "total": total}

    @app.post("/api/tasks")
    def post_task(body: TaskBody, db: Session = Depends(get_db), user: User = Depends(require("publisher", "admin"))):
        task = create_task(db, user, body.model_dump())
        return task_dict(db, task)

    @app.post("/api/tasks/{task_id}/transition")
    def transition(
        task_id: int,
        body: TransitionBody,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
        idempotency_key: str | None = Header(default=None),
    ):
        if idempotency_key:
            existing = db.query(IdempotencyKey).filter(IdempotencyKey.key == idempotency_key).first()
            if existing:
                return json.loads(existing.response_json)
        task = db.get(SensingTask, task_id)
        if task is None:
            raise AppError("not_found", "任务不存在", 404)
        run = db.query(SimulationRun).order_by(SimulationRun.id.desc()).first()
        matches = True
        if user.role == "collector":
            person = db.query(Participant).filter(Participant.user_id == user.id).first()
            matches = bool(person and person.id == task.assignee_id)
        if body.to_status == "submitted":
            if body.measurement_db is None:
                raise AppError("measurement_required", "提交任务需要填写测量值", 422)
            _store_manual_measurement(db, task, float(body.measurement_db), user.id)
        apply_transition(
            db,
            task,
            body.to_status,
            user.role,
            user.id,
            run.current_slot if run else None,
            measurement_db=body.measurement_db,
            note=body.note,
            assignee_matches=matches,
        )
        payload = task_dict(db, task)
        if idempotency_key:
            db.add(IdempotencyKey(key=idempotency_key, response_json=json.dumps(payload), created_at=utcnow()))
        return payload

    @app.post("/api/tasks/{task_id}/simulate-sample")
    def simulate_sample(task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
        task = db.get(SensingTask, task_id)
        if task is None:
            raise AppError("not_found", "任务不存在", 404)
        level = assisted_sample(db, user, task)
        run = active_run(db)
        if task.status == "accepted":
            apply_transition(db, task, "in_progress", user.role if user.role == "collector" else "system", user.id, run.current_slot, assignee_matches=True)
        apply_transition(db, task, "submitted", "system", user.id, run.current_slot, measurement_db=level, note="仿真辅助采样")
        apply_transition(db, task, "verified", "system", user.id, run.current_slot, note="仿真辅助核验")
        apply_transition(db, task, "completed", "system", user.id, run.current_slot, note="仿真辅助完成")
        return task_dict(db, task) | {"laeq_db": level, "source": "simulation_assisted"}

    @app.post("/api/assignments/run")
    def run_assignment(body: AssignBody, db: Session = Depends(get_db), user: User = Depends(require("publisher", "admin"))):
        return propose_assignments(db, user, body.algorithm, body.budget, body.limit)

    @app.get("/api/assignments")
    def assignments(limit: int = 100, db: Session = Depends(get_db), _user: User = Depends(current_user)):
        from urbannoise.models import TaskAssignment

        rows = db.query(TaskAssignment).order_by(TaskAssignment.id.desc()).limit(limit).all()
        names = {person.id: person.name for person in db.query(Participant).all()}
        return {
            "items": [
                {
                    "id": row.id,
                    "task_id": row.task_id,
                    "participant_id": row.participant_id,
                    "participant_name": names.get(row.participant_id),
                    "score": row.score,
                    "reach_prob": row.reach_prob,
                    "estimated_cost": row.estimated_cost,
                    "status": row.status,
                }
                for row in rows
            ]
        }

    @app.get("/api/simulation")
    def get_simulation(db: Session = Depends(get_db), _user: User = Depends(current_user)):
        return simulation_dict(db, active_run(db))

    @app.post("/api/simulation/control")
    def control_simulation(body: SimulationBody, db: Session = Depends(get_db), user: User = Depends(require("admin", "publisher"))):
        run = active_run(db)
        if body.action == "pause":
            run.status = "paused"
        elif body.action == "resume":
            if run.current_slot >= run.horizon_end:
                raise AppError("finished", "仿真已经结束", 409)
            run.status = "running"
        elif body.action == "step":
            return step_simulation(db, user, body.steps)
        elif body.action == "reset":
            params = json.loads(run.config_json)
            for field in (
                "scenario",
                "seed",
                "algorithm",
                "budget",
                "n_human",
                "n_machine",
                "accept_human",
                "mode",
                "mobility_source",
                "noise_source",
                "n_users",
                "grid_m",
                "noise_country",
                "day_min",
            ):
                value = getattr(body, field)
                if value is not None:
                    params[field] = value
            rebuilt = rebuild_world(db, settings, params, user.id)
            return simulation_dict(db, rebuilt)
        else:
            raise AppError("bad_action", "不支持的仿真操作", 422)
        return simulation_dict(db, run)

    @app.get("/api/data/platform")
    def data_platform(_user: User = Depends(current_user)):
        return _platform_status(settings)

    @app.get("/api/predictions/real-noise")
    def real_noise(country: str | None = None, _user: User = Depends(current_user)):
        from urbannoise.noiseeval import predict_parquet

        hourly = Path(settings.data_dir) / "processed" / "noisecapture" / "hourly_500m.parquet"
        if not hourly.exists():
            raise AppError("noise_missing", f"没有 NoiseCapture 小时聚合表：{hourly}", 404)
        try:
            result = predict_parquet(hourly, indicator="laeq_1s", country=country)
        except Exception as exc:
            raise AppError("noise_predict_failed", str(exc), 422) from exc
        result["synthetic_demo_used"] = False
        return result

    @app.get("/api/experiments")
    def experiments(db: Session = Depends(get_db), _user: User = Depends(current_user)):
        rows = db.query(ExperimentRun).order_by(ExperimentRun.id.desc()).limit(20).all()
        legacy = _load_archived("experiments/results/main/summary.json", "legacy_protocol")
        phase2 = _load_archived("experiments/results/phase2/fair_main/summary.json", "mae_available_at_t")
        return {"items": [_experiment(row) for row in rows], "archived": legacy, "legacy": legacy, "phase2": phase2}

    @app.post("/api/experiments")
    def start_experiment(body: ExperimentBody, db: Session = Depends(get_db), user: User = Depends(require("admin", "publisher"))):
        profiles = {"smoke": "experiments/configs/smoke.json", "phase2": "experiments/configs/phase2_fair.json"}
        if body.profile == "main":
            raise AppError("legacy_profile", "main 是旧协议归档，不会覆盖 experiments/results/main。请运行 phase2。", 409)
        if body.profile not in profiles:
            raise AppError("bad_profile", "只提供 smoke 与 phase2 两种新运行配置", 422)
        config_path = Path(profiles[body.profile])
        if not config_path.exists():
            raise AppError("missing_config", "实验配置文件不存在", 500)
        if not EXPERIMENT_LOCK.acquire(blocking=False):
            raise AppError("busy", "已有实验在运行", 409)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        row = ExperimentRun(
            name=config.get("name", body.profile),
            profile=body.profile,
            status="running",
            config_json=json.dumps(config),
            output_dir=config.get("output_dir", f"experiments/results/{body.profile}"),
            created_at=utcnow(),
        )
        db.add(row)
        db.flush()
        db.commit()
        run_id = row.id
        thread = threading.Thread(target=_experiment_worker, args=(settings, run_id, config), daemon=True)
        thread.start()
        return _experiment(row)

    @app.get("/api/experiments/{run_id}")
    def experiment_detail(run_id: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
        row = db.get(ExperimentRun, run_id)
        if row is None:
            raise AppError("not_found", "实验不存在", 404)
        metrics = db.query(EvaluationMetric).filter(EvaluationMetric.experiment_run_id == run_id).limit(400).all()
        payload = _experiment(row)
        payload["metrics"] = [
            {
                "scenario": item.scenario,
                "method": item.method,
                "budget": item.budget,
                "seed": item.seed,
                "family": item.family,
                "mae": item.mae,
                "rmse": item.rmse,
                "coverage": item.coverage,
                "successful_tasks": item.successful_tasks,
                "sampling_cost": item.sampling_cost,
            }
            for item in metrics
        ]
        return payload

    @app.get("/api/experiments/{run_id}/export")
    def export_experiment(run_id: int, db: Session = Depends(get_db), _user: User = Depends(current_user)):
        row = db.get(ExperimentRun, run_id)
        if row is None:
            raise AppError("not_found", "实验不存在", 404)
        path = Path(row.output_dir) / "results.csv"
        if path.exists():
            return StreamingResponse(iter([path.read_text(encoding="utf-8")]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=experiment-{run_id}.csv"})
        metrics = db.query(EvaluationMetric).filter(EvaluationMetric.experiment_run_id == run_id).all()
        return _csv_response([
            {
                "method": item.method,
                "scenario": item.scenario,
                "budget": item.budget,
                "seed": item.seed,
                "mae": item.mae,
                "rmse": item.rmse,
                "coverage": item.coverage,
                "successful_tasks": item.successful_tasks,
                "sampling_cost": item.sampling_cost,
            }
            for item in metrics
        ], f"experiment-{run_id}.csv")

    @app.get("/api/exports/tasks")
    def export_tasks(db: Session = Depends(get_db), _user: User = Depends(current_user)):
        rows = [task_dict(db, task) for task in db.query(SensingTask).all()]
        return _csv_response(rows, "tasks.csv")

    @app.get("/api/users")
    def users(db: Session = Depends(get_db), _user: User = Depends(require("admin"))):
        return {"items": [public_user(row) for row in db.query(User).all()]}

    @app.post("/api/users")
    def create_user(body: UserBody, db: Session = Depends(get_db), user: User = Depends(require("admin"))):
        from urbannoise.security import hash_password

        if body.role not in {"admin", "publisher", "collector"}:
            raise AppError("bad_role", "未知角色", 422)
        if db.query(User).filter(User.username == body.username).first():
            raise AppError("duplicate", "用户名已存在", 409)
        row = User(username=body.username, password_hash=hash_password(body.password), display_name=body.display_name, role=body.role, is_active=True, created_at=utcnow())
        db.add(row)
        db.flush()
        return public_user(row)

    @app.get("/api/audit")
    def audit(limit: int = 50, db: Session = Depends(get_db), _user: User = Depends(require("admin"))):
        rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
        return {"items": [{"id": row.id, "user_id": row.user_id, "action": row.action, "detail": row.detail, "created_at": row.created_at.isoformat()} for row in rows]}

    return app


def predict_noise(db: Session, slot: int, model: str):
    from urbannoise.services import predict_slot

    return predict_slot(db, slot, model)


def _participant(row: Participant) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "participant_type": row.participant_type,
        "online": row.online,
        "accept_prob": row.accept_prob,
        "cost": row.cost,
        "quality": row.quality,
        "current_grid_id": row.current_grid_id,
        "user_id": row.user_id,
    }


def _device(row: Device) -> dict:
    return {"id": row.id, "name": row.name, "kind": row.kind, "participant_id": row.participant_id, "capability": row.capability, "status": row.status}


def _experiment(row: ExperimentRun) -> dict:
    summary = json.loads(row.summary_json) if row.summary_json else None
    return {
        "id": row.id,
        "name": row.name,
        "profile": row.profile,
        "status": row.status,
        "output_dir": row.output_dir,
        "summary": summary,
        "log": (row.log_text or "").splitlines()[-30:],
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _load_archived(path_text: str, protocol: str) -> dict | None:
    path = Path(path_text)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", [])
    return {
        "path": str(path),
        "protocol": payload.get("protocol") or protocol,
        "summary": summary,
        "mobility": payload.get("mobility"),
        "noise_models": payload.get("noise_models"),
        "metric_definitions": payload.get("metric_definitions"),
    }


def _platform_status(settings: Settings) -> dict:
    root = Path(settings.data_dir)
    manifest_path = root / "manifests" / "download_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    blocks = {}
    for name in ("yjmob", "geolife", "noisecapture"):
        summary = root / "processed" / name / "summary.json"
        if name == "yjmob":
            summary = root / "processed" / "yjmob" / "dataset1_stats.json"
        blocks[name] = json.loads(summary.read_text(encoding="utf-8")) if summary.exists() else {"status": "not_processed"}
    dataset2 = root / "processed" / "yjmob" / "dataset2_stats.json"
    if dataset2.exists():
        blocks["yjmob_dataset2"] = json.loads(dataset2.read_text(encoding="utf-8"))
    return {
        "data_dir": str(root),
        "download_manifest": str(manifest_path) if manifest_path.exists() else None,
        "downloads": None
        if manifest is None
        else [
            {
                "dataset": item.get("dataset"),
                "name": item.get("name"),
                "status": item.get("status"),
                "bytes": item.get("bytes"),
                "sha256": item.get("sha256"),
                "md5": item.get("md5"),
                "error": item.get("error"),
                "license": item.get("license"),
            }
            for item in manifest.get("items", [])
        ],
        "processed": blocks,
    }


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    buffer = io.StringIO()
    if not rows:
        buffer.write("")
    else:
        keys: list[str] = []
        for row in rows:
            for key, value in row.items():
                if key not in keys and not isinstance(value, (dict, list)):
                    keys.append(key)
        writer = csv.DictWriter(buffer, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in keys})
    return StreamingResponse(iter([buffer.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


def _experiment_worker(settings: Settings, run_id: int, config: dict) -> None:
    engine = make_engine(settings)
    factory = make_session_factory(engine)
    db = factory()
    try:
        row = db.get(ExperimentRun, run_id)
        output = Path(config.get("output_dir", f"experiments/results/{config.get('name', 'run')}"))
        try:
            payload = run_suite(config, output)
            from urbannoise.experiment import plot_results

            plot_results(payload, Path(config.get("figure_dir", f"experiments/figures/{config.get('name', 'run')}")))
            slim = {
                "summary": payload.get("summary"),
                "mobility": payload.get("mobility"),
                "noise_models": payload.get("noise_models"),
                "bandit_curve": payload.get("bandit_curve"),
                "metric_definitions": payload.get("metric_definitions"),
            }
            (output / "summary.json").write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
            for item in payload.get("rows", []):
                db.add(
                    EvaluationMetric(
                        experiment_run_id=run_id,
                        scenario=str(item.get("scenario", "")),
                        method=str(item.get("method", "")),
                        budget=float(item.get("budget", 0)),
                        seed=int(item.get("seed", 0)),
                        family=str(item.get("family", "")),
                        mae=float(item.get("mae_causal", 0)),
                        rmse=float(item.get("rmse_causal", 0)),
                        coverage=float(item.get("coverage", 0)),
                        successful_tasks=int(item.get("successful_tasks", 0)),
                        sampling_cost=float(item.get("sampling_cost", 0)),
                        payload_json=json.dumps({key: item[key] for key in item if not isinstance(item[key], (dict, list))}),
                    )
                )
            row.status = "succeeded"
            row.summary_json = json.dumps(slim, ensure_ascii=False)
            row.log_text = f"rows={len(payload.get('rows', []))}\n"
            row.finished_at = utcnow()
        except Exception as exc:  # keep the failure visible in the experiment record
            LOGGER.exception("experiment failed")
            row.status = "failed"
            row.log_text = str(exc)
            row.finished_at = utcnow()
        db.commit()
    finally:
        db.close()
        EXPERIMENT_LOCK.release()


app = create_app()

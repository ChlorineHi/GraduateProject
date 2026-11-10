"""Relational schema. Names here are the ones used by the UML and the API."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from urbannoise.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("mobility_datasets.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    participant_type: Mapped[str] = mapped_column(String(16), index=True)
    accept_prob: Mapped[float] = mapped_column(Float, default=0.7)
    cost: Mapped[float] = mapped_column(Float, default=1.0)
    quality: Mapped[float] = mapped_column(Float, default=1.0)
    online: Mapped[bool] = mapped_column(Boolean, default=True)
    current_grid_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trajectory_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(32))
    capability: Mapped[str] = mapped_column(String(120), default="laeq")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MobilityDataset(Base):
    __tablename__ = "mobility_datasets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(80))
    license: Mapped[str] = mapped_column(Text, default="")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    real_city: Mapped[bool] = mapped_column(Boolean, default=False)
    coordinate_system: Mapped[str] = mapped_column(String(64))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    participant_count: Mapped[int] = mapped_column(Integer, default=0)
    time_start: Mapped[str] = mapped_column(String(64), default="")
    time_end: Mapped[str] = mapped_column(String(64), default="")
    spatial_desc: Mapped[str] = mapped_column(Text, default="")
    missing_rate: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    quality_json: Mapped[str] = mapped_column(Text, default="{}")
    notes: Mapped[str] = mapped_column(Text, default="")
    storage_uri: Mapped[str] = mapped_column(String(255), default="")


class TrajectoryPoint(Base):
    __tablename__ = "trajectory_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("mobility_datasets.id"), index=True)
    trajectory_id: Mapped[str] = mapped_column(String(64), index=True)
    participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"), nullable=True, index=True)
    slot: Mapped[int] = mapped_column(Integer, index=True)
    timestamp_label: Mapped[str] = mapped_column(String(64), default="")
    grid_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    coordinate_system: Mapped[str] = mapped_column(String(64))
    data_source: Mapped[str] = mapped_column(String(64))
    participant_type: Mapped[str] = mapped_column(String(16), default="human")
    quality_flags: Mapped[str] = mapped_column(String(64), default="ok")

    __table_args__ = (Index("ix_traj_participant_slot", "participant_id", "slot"),)


class NoiseDataset(Base):
    __tablename__ = "noise_datasets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(80))
    license: Mapped[str] = mapped_column(Text, default="")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    indicator: Mapped[str] = mapped_column(String(32), default="laeq_db")
    coordinate_system: Mapped[str] = mapped_column(String(64))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    time_start: Mapped[str] = mapped_column(String(64), default="")
    time_end: Mapped[str] = mapped_column(String(64), default="")
    spatial_desc: Mapped[str] = mapped_column(Text, default="")
    missing_rate: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    quality_json: Mapped[str] = mapped_column(Text, default="{}")
    notes: Mapped[str] = mapped_column(Text, default="")
    storage_uri: Mapped[str] = mapped_column(String(255), default="")


class NoiseObservation(Base):
    __tablename__ = "noise_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("noise_datasets.id"), index=True)
    grid_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    slot: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    timestamp_label: Mapped[str] = mapped_column(String(64), default="")
    laeq_db: Mapped[float] = mapped_column(Float)
    indicator: Mapped[str] = mapped_column(String(32), default="laeq_db")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    coordinate_system: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(64))
    quality_flags: Mapped[str] = mapped_column(String(64), default="ok")
    is_simulated_feedback: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_noise_slot_grid", "slot", "grid_id"),)


class SpatialGrid(Base):
    __tablename__ = "spatial_grids"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grid_x: Mapped[int] = mapped_column(Integer)
    grid_y: Mapped[int] = mapped_column(Integer)
    zone: Mapped[str] = mapped_column(String(32), index=True)
    coordinate_system: Mapped[str] = mapped_column(String(64))
    center_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    center_lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (UniqueConstraint("grid_x", "grid_y", "coordinate_system", name="uq_grid_xy_crs"),)


class SensingTask(Base):
    __tablename__ = "sensing_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    grid_id: Mapped[int] = mapped_column(Integer, index=True)
    slot_start: Mapped[int] = mapped_column(Integer, index=True)
    slot_end: Mapped[int] = mapped_column(Integer)
    priority: Mapped[float] = mapped_column(Float, default=1.0)
    budget_cost: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(32), index=True, default="draft")
    publisher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"), nullable=True)
    algorithm: Mapped[str] = mapped_column(String(64), default="mupsa")
    simulation_run_id: Mapped[int | None] = mapped_column(ForeignKey("simulation_runs.id"), nullable=True)
    origin: Mapped[str] = mapped_column(String(32), default="manual")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("sensing_tasks.id"), index=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reach_prob: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="assigned")
    round_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssignmentEvent(Base):
    __tablename__ = "assignment_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("sensing_tasks.id"), index=True)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("task_assignments.id"), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[str] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SamplingResult(Base):
    __tablename__ = "sampling_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("sensing_tasks.id"), index=True)
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("task_assignments.id"), nullable=True)
    participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"), nullable=True)
    observation_id: Mapped[int | None] = mapped_column(ForeignKey("noise_observations.id"), nullable=True)
    grid_id: Mapped[int] = mapped_column(Integer)
    slot: Mapped[int] = mapped_column(Integer)
    laeq_db: Mapped[float] = mapped_column(Float)
    indicator: Mapped[str] = mapped_column(String(32), default="laeq_db")
    source: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SimulationScenario(Base):
    __tablename__ = "simulation_scenarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}")


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    scenario: Mapped[str] = mapped_column(String(32))
    seed: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="paused", index=True)
    current_slot: Mapped[int] = mapped_column(Integer, default=0)
    horizon_start: Mapped[int] = mapped_column(Integer, default=0)
    horizon_end: Mapped[int] = mapped_column(Integer, default=0)
    budget_total: Mapped[float] = mapped_column(Float, default=20)
    budget_left: Mapped[float] = mapped_column(Float, default=20)
    budget_spent: Mapped[float] = mapped_column(Float, default=0)
    algorithm: Mapped[str] = mapped_column(String(64), default="mupsa")
    world_path: Mapped[str] = mapped_column(String(255), default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    rng_json: Mapped[str] = mapped_column(Text, default="")
    log_text: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(32), default="synthetic")
    mobility_source: Mapped[str] = mapped_column(String(80), default="synthetic")
    noise_source: Mapped[str] = mapped_column(String(80), default="synthetic")
    user_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AlgorithmConfig(Base):
    __tablename__ = "algorithm_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    family: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text, default="")
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    is_proposed: Mapped[bool] = mapped_column(Boolean, default=False)


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(255))
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    profile: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    summary_json: Mapped[str] = mapped_column(Text, default="")
    log_text: Mapped[str] = mapped_column(Text, default="")
    output_dir: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    experiment_run_id: Mapped[int] = mapped_column(ForeignKey("experiment_runs.id"), index=True)
    scenario: Mapped[str] = mapped_column(String(32), default="")
    method: Mapped[str] = mapped_column(String(64))
    budget: Mapped[float] = mapped_column(Float, default=0)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    family: Mapped[str] = mapped_column(String(32), default="main")
    mae: Mapped[float] = mapped_column(Float, default=0)
    rmse: Mapped[float] = mapped_column(Float, default=0)
    coverage: Mapped[float] = mapped_column(Float, default=0)
    successful_tasks: Mapped[int] = mapped_column(Integer, default=0)
    sampling_cost: Mapped[float] = mapped_column(Float, default=0)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Relationship attributes are declared for ORM navigation in a few services.
User.participants = relationship(Participant, backref="user")

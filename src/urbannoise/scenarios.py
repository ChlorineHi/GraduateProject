"""Scenario modes for synthetic worlds and real-schema tables.

Modes
-----
synthetic
    Builds the existing synthetic world. This is the only mode that calls ``build_world``.
real_mobility
    Loads a trajectory table and scores task success from that track. A synthetic noise
    value is drawn only after the later slot is on the task cell, and it is labeled synthetic.
real_noise
    Loads noise observations and evaluates a time/space holdout. The score is not a full-city field.
fully_real
    Returns an error unless a manifest states geography overlap and time overlap.
    YJMob x/y are never written out as WGS84 latitude/longitude.

Decision reads use a lock that rejects locations after the decision slot. The trajectory
rows themselves are not updated.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from urbannoise.predictors import fit_mobility, predict_idw

SCENARIO_MODES = ("synthetic", "real_mobility", "real_noise", "fully_real")
CELL_STRIDE = 100_000
EXAMPLE_SOURCE = "synthetic_shaped_real_schema_example"
FULLY_REAL_REFUSAL = (
    "fully_real requires a manifest that says geography and time overlap. "
    "Refusing to georegister YJMob x/y onto WGS84."
)
HOLDOUT_DISCLAIMER = (
    "Held-out observations only. This is not a full-city noise field and is not citywide ground truth."
)
_CONVERSION_KEYS = (
    "georegister",
    "georegister_yjmob_to_wgs84",
    "project_yjmob",
    "origin_lat",
    "origin_lon",
    "anchor_lat",
    "anchor_lon",
)
_WORLD_KEYS = {
    "height",
    "width",
    "n_days",
    "slots_per_day",
    "n_human",
    "n_machine",
    "scenario",
    "missing_rate",
    "sensor_sigma",
    "accept_human",
    "accept_machine",
    "cost_human",
    "cost_machine",
    "offline_fraction",
    "prior_samples",
    "horizon",
}


class ScenarioUnavailable(RuntimeError):
    """The requested mode cannot be opened without inventing data or a join."""

    def __init__(self, message: str, *, code: str = "scenario_unavailable", detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


class FutureLeakError(RuntimeError):
    """A decision read asked for a location after the locked decision slot."""


def cell_id(x: int, y: int) -> int:
    """Stable cell key for non-negative grid coordinates. This is not a longitude or latitude."""
    xi, yi = int(x), int(y)
    if xi < 0 or yi < 0 or xi >= CELL_STRIDE:
        raise ScenarioUnavailable("cell coordinates must be non-negative and x must be below 100000")
    return yi * CELL_STRIDE + xi


def decode_cell(cell: int) -> tuple[int, int]:
    value = int(cell)
    if value < 0:
        raise ScenarioUnavailable("cell id is negative")
    return value % CELL_STRIDE, value // CELL_STRIDE


def task_succeeded(actual_cell: int | None, task_cell: int) -> bool:
    """True only when the recorded later cell is the task cell."""
    return actual_cell is not None and int(actual_cell) == int(task_cell)


def fixture_dir() -> Path:
    root = Path(__file__).resolve().parents[2]
    path = root / "tests" / "fixtures"
    if path.is_dir():
        return path
    return Path.cwd() / "tests" / "fixtures"


def default_mobility_fixture() -> Path:
    path = fixture_dir() / "real_mobility_schema_example.csv"
    if not path.is_file():
        raise ScenarioUnavailable(f"mobility schema fixture is missing: {path}")
    return path


def default_noise_fixture() -> Path:
    path = fixture_dir() / "real_noise_schema_example.csv"
    if not path.is_file():
        raise ScenarioUnavailable(f"noise schema fixture is missing: {path}")
    return path


def _rename(frame: pd.DataFrame) -> pd.DataFrame:
    mapping = {column: str(column).strip().lower().replace(" ", "_") for column in frame.columns}
    return frame.rename(columns=mapping)


def _read_table(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.is_file():
        raise ScenarioUnavailable(f"table file does not exist: {file_path}")
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".parquet", ".pq"}:
        try:
            return pd.read_parquet(file_path)
        except ImportError as exc:
            raise ScenarioUnavailable("Reading parquet requires pyarrow or fastparquet.") from exc
        except Exception as exc:  # format errors should stay on the scenario boundary
            raise ScenarioUnavailable(f"Could not read parquet: {exc}") from exc
    raise ScenarioUnavailable(f"Unsupported table type {suffix or '(none)'}. Use csv or parquet.")


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], kind: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ScenarioUnavailable(f"{kind} table is missing {missing}. Columns are {list(frame.columns)}.")


def _integer_column(frame: pd.DataFrame, name: str) -> pd.Series:
    values = pd.to_numeric(frame[name], errors="coerce")
    if values.isna().any() or ((values % 1) != 0).any():
        raise ScenarioUnavailable(f"{name} must be integers")
    return values.astype(int)


def _is_yjmob(coordinate_system: str, data_source: str) -> bool:
    text = f"{coordinate_system} {data_source}".lower()
    return "yjmob" in text


def _crs_key(coordinate_system: str) -> str:
    text = coordinate_system.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    if "yjmob" in text:
        return "yjmob_virtual"
    if "wgs84" in text or text in {"epsg:4326", "epsg4326"}:
        return "wgs84"
    return text


def _time_sort_key(value: str) -> tuple:
    try:
        return (0, float(value))
    except (TypeError, ValueError):
        return (1, str(value))


def _as_bool(payload: dict, key: str) -> bool:
    if key not in payload:
        raise ScenarioUnavailable(FULLY_REAL_REFUSAL + f" Manifest is missing {key}.")
    value = payload[key]
    if not isinstance(value, bool):
        raise ScenarioUnavailable(FULLY_REAL_REFUSAL + f" Manifest field {key} must be a boolean.")
    return value


def _fingerprint(payload: list) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _example_marker(values: list[str]) -> bool:
    text = " ".join(values).lower()
    return "synthetic_shaped" in text or "schema_example" in text or "not_yjmob" in text or "not_a_city" in text


@dataclass(frozen=True)
class MobilityRecord:
    participant_id: str
    day: int
    timeslot: int
    x: int
    y: int
    data_source: str
    coordinate_system: str
    slot: int
    cell: int
    schema_example: str


class TrajectoryTable:
    """Immutable trajectory rows. Cell values leave this object only through ``read_cell``."""

    def __init__(self, records: tuple[MobilityRecord, ...], slots_per_day: int, slots_inferred: bool):
        if not records:
            raise ScenarioUnavailable("trajectory table has no rows")
        keys = [(row.participant_id, row.slot) for row in records]
        if len(keys) != len(set(keys)):
            raise ScenarioUnavailable("duplicate participant_id and slot rows are not allowed")
        systems = {row.coordinate_system for row in records}
        if len(systems) != 1:
            raise ScenarioUnavailable(f"a trajectory table cannot mix coordinate systems: {sorted(systems)}")
        sources = {row.data_source for row in records}
        if any(_is_yjmob(row.coordinate_system, row.data_source) for row in records) and any(
            not _is_yjmob(row.coordinate_system, row.data_source) for row in records
        ):
            raise ScenarioUnavailable("YJMob rows cannot be mixed with another mobility source")
        self._records = records
        self._cells = {(row.participant_id, row.slot): row.cell for row in records}
        self._keys = tuple((row.participant_id, row.slot) for row in records)
        self.slots_per_day = int(slots_per_day)
        self.slots_inferred = bool(slots_inferred)
        self.coordinate_system = records[0].coordinate_system
        self.data_sources = tuple(sorted(sources))
        self.schema_examples = tuple(sorted({row.schema_example for row in records if row.schema_example}))
        self.access_log: list[tuple[int, str]] = []
        self._decision_lock: int | None = None
        self._fingerprint = _fingerprint(
            [
                [
                    row.participant_id,
                    row.day,
                    row.timeslot,
                    row.x,
                    row.y,
                    row.data_source,
                    row.coordinate_system,
                    row.slot,
                    row.cell,
                ]
                for row in records
            ]
        )

    @property
    def has_geographic_coordinates(self) -> bool:
        return False

    @property
    def yjmob(self) -> bool:
        return _is_yjmob(self.coordinate_system, " ".join(self.data_sources))

    def fingerprint(self) -> str:
        return self._fingerprint

    def participants(self) -> list[str]:
        return sorted({pid for pid, _slot in self._keys})

    def max_slot(self) -> int:
        return max(slot for _pid, slot in self._keys)

    def participants_visible(self, decision_slot: int) -> list[str]:
        """Participant ids that already have a row at or before the decision. Future-only ids stay hidden."""
        limit = int(decision_slot)
        return sorted({pid for pid, slot in self._keys if slot <= limit})

    @contextmanager
    def lock_decisions(self, decision_slot: int):
        if self._decision_lock is not None:
            raise FutureLeakError("a decision lock is already active")
        self._decision_lock = int(decision_slot)
        try:
            yield
        finally:
            self._decision_lock = None

    def read_cell(self, participant_id: str, slot: int, *, purpose: str) -> int | None:
        """Return one stored cell.

        Decision reads are refused when ``slot`` is after the active decision lock.
        Execution reads are how task success sees the later slot, and they are refused
        while a decision lock is held.
        """
        slot = int(slot)
        if purpose not in {"decision", "execution"}:
            raise FutureLeakError(f"unknown location read purpose: {purpose}")
        if purpose == "decision" and self._decision_lock is None:
            raise FutureLeakError("decision location reads require a decision lock")
        if self._decision_lock is not None and slot > self._decision_lock:
            raise FutureLeakError(
                f"refusing to read a location at slot {slot} while decisions are locked at slot {self._decision_lock}"
            )
        self.access_log.append((slot, purpose))
        return self._cells.get((str(participant_id), slot))

    def to_summary(self) -> dict:
        return {
            "rows": len(self._records),
            "participants": self.participants(),
            "coordinate_system": self.coordinate_system,
            "data_source": list(self.data_sources),
            "schema_example": list(self.schema_examples),
            "slots_per_day": self.slots_per_day,
            "slots_inferred": self.slots_inferred,
            "yjmob": self.yjmob,
            "latitude_assigned": False,
            "longitude_assigned": False,
            "georegistered_yjmob": False,
            "example_schema": _example_marker(list(self.data_sources) + list(self.schema_examples) + [self.coordinate_system]),
        }


def trajectory_from_frame(frame: pd.DataFrame, *, slots_per_day: int | None = None) -> TrajectoryTable:
    renamed = _rename(frame)
    if _is_yjmob(
        " ".join(renamed["coordinate_system"].astype(str)) if "coordinate_system" in renamed else "",
        " ".join(renamed["data_source"].astype(str)) if "data_source" in renamed else "",
    ):
        for geographic in ("latitude", "lat", "longitude", "lon", "lng"):
            if geographic in renamed.columns and pd.to_numeric(renamed[geographic], errors="coerce").notna().any():
                raise ScenarioUnavailable(
                    "Refusing to georegister YJMob x/y onto WGS84. YJMob rows must not carry latitude or longitude."
                )
    _require_columns(
        renamed,
        ("participant_id", "day", "timeslot", "x", "y", "data_source", "coordinate_system"),
        "mobility",
    )
    day = _integer_column(renamed, "day")
    timeslot = _integer_column(renamed, "timeslot")
    x_values = _integer_column(renamed, "x")
    y_values = _integer_column(renamed, "y")
    if (day < 0).any() or (timeslot < 0).any() or (x_values < 0).any() or (y_values < 0).any():
        raise ScenarioUnavailable("day, timeslot, x, and y must be non-negative")
    if slots_per_day is None and "slots_per_day" in renamed.columns:
        declared = _integer_column(renamed, "slots_per_day")
        if declared.nunique() != 1:
            raise ScenarioUnavailable("slots_per_day must be a single value")
        slots_per_day = int(declared.iloc[0])
        inferred = False
    elif slots_per_day is None:
        slots_per_day = int(timeslot.max()) + 1
        inferred = True
    else:
        slots_per_day = int(slots_per_day)
        inferred = False
    if slots_per_day <= 0:
        raise ScenarioUnavailable("slots_per_day must be positive")
    if (timeslot >= slots_per_day).any():
        raise ScenarioUnavailable("timeslot must be smaller than slots_per_day")
    schema = renamed["schema_example"].astype(str) if "schema_example" in renamed.columns else pd.Series([""] * len(renamed))
    records = []
    for idx in range(len(renamed)):
        records.append(
            MobilityRecord(
                participant_id=str(renamed["participant_id"].iloc[idx]),
                day=int(day.iloc[idx]),
                timeslot=int(timeslot.iloc[idx]),
                x=int(x_values.iloc[idx]),
                y=int(y_values.iloc[idx]),
                data_source=str(renamed["data_source"].iloc[idx]),
                coordinate_system=str(renamed["coordinate_system"].iloc[idx]),
                slot=int(day.iloc[idx]) * slots_per_day + int(timeslot.iloc[idx]),
                cell=cell_id(int(x_values.iloc[idx]), int(y_values.iloc[idx])),
                schema_example="" if schema.iloc[idx] in {"", "nan"} else str(schema.iloc[idx]),
            )
        )
    return TrajectoryTable(tuple(records), slots_per_day, inferred)


def load_mobility_table(path: str | Path, *, slots_per_day: int | None = None) -> TrajectoryTable:
    return trajectory_from_frame(_read_table(path), slots_per_day=slots_per_day)


def _synthetic_base(slot: int, x: int, y: int, seed: int) -> float:
    phase = (int(seed) % 97) * 0.01
    return float(42.0 + 4.0 * np.sin(0.7 * x + phase) + 2.5 * np.cos(0.5 * y) + 0.15 * (int(slot) % 48))


class RealMobilityScenario:
    mode = "real_mobility"

    def __init__(self, table: TrajectoryTable, *, seed: int = 7, fixture_fallback: bool = False):
        self.table = table
        self.seed = int(seed)
        self.fixture_fallback = bool(fixture_fallback)
        self.synthetic_sample_count = 0

    def decide(self, decision_slot: int, target_slot: int) -> dict:
        """Reach features from locations at or before ``decision_slot`` only."""
        decision_slot = int(decision_slot)
        target_slot = int(target_slot)
        if decision_slot < 0:
            raise ScenarioUnavailable("decision slot must be non-negative")
        if target_slot <= decision_slot:
            raise ScenarioUnavailable("target slot must be later than the decision slot")
        before = self.table.fingerprint()
        self.table.access_log = []
        with self.table.lock_decisions(decision_slot):
            participants = self.table.participants_visible(decision_slot)
            observed: list[tuple[str, int, int]] = []
            for participant_id in participants:
                for slot in range(decision_slot + 1):
                    cell = self.table.read_cell(participant_id, slot, purpose="decision")
                    if cell is not None:
                        observed.append((participant_id, slot, int(cell)))
            cells = sorted({cell for _pid, _slot, cell in observed})
            index = {cell: position for position, cell in enumerate(cells)}
            traj = np.full((len(participants), decision_slot + 1), -1, dtype=np.int32)
            for participant_id, slot, cell in observed:
                traj[participants.index(participant_id), slot] = index[cell]
            reach = np.zeros((len(participants), len(cells)), dtype=np.float64)
            if cells:
                fit = fit_mobility(traj, decision_slot, self.table.slots_per_day, len(cells))
                lead = target_slot - decision_slot
                tod = target_slot % self.table.slots_per_day
                for position in range(len(participants)):
                    current = int(traj[position, decision_slot])
                    dist = fit.distribution(position, tod, current, lead)
                    reach[position, : dist.size] = dist
        if self.table.fingerprint() != before:
            raise ScenarioUnavailable("decision code edited the trajectory")
        if any(slot > decision_slot for slot, _purpose in self.table.access_log):
            raise FutureLeakError("decision log contains a location after the decision slot")
        return {
            "mode": self.mode,
            "decision_slot": decision_slot,
            "target_slot": target_slot,
            "participants": participants,
            "cells": cells,
            "reach": reach,
            "slots_visible": decision_slot + 1,
        }

    def sample_synthetic_noise(self, *, slot: int, cell: int, rng: np.random.Generator | None, sigma: float) -> dict:
        """Read the synthetic field. Callers may do this only after success is already true."""
        self.synthetic_sample_count += 1
        x_coord, y_coord = decode_cell(cell)
        generator = rng if rng is not None else np.random.default_rng(self.seed)
        level = float(_synthetic_base(slot, x_coord, y_coord, self.seed) + generator.normal(0.0, float(sigma)))
        return {
            "db": level,
            "label": "synthetic",
            "is_synthetic": True,
            "data_origin": "synthetic_noise_field",
            "indicator": "synthetic_laeq_db",
            "source": "synthetic",
            "real_city": False,
            "full_city_truth": False,
            "coordinate_system": "synthetic_virtual_grid",
        }

    def execute_task(
        self,
        participant_id: str,
        task_cell: int,
        task_slot: int,
        decision_slot: int,
        rng: np.random.Generator | None = None,
        sigma: float = 0.0,
    ) -> dict:
        """Success follows the stored later cell. The future track is not rewritten."""
        task_slot = int(task_slot)
        decision_slot = int(decision_slot)
        task_cell = int(task_cell)
        if task_slot <= decision_slot:
            raise ScenarioUnavailable("task success is decided on a slot later than the decision")
        before = self.table.fingerprint()
        actual = self.table.read_cell(str(participant_id), task_slot, purpose="execution")
        success = task_succeeded(actual, task_cell)
        if actual is None:
            reason = "no_location"
        elif success:
            reason = "on_task_cell"
        else:
            reason = "off_task_cell"
        noise = None
        if success:
            noise = self.sample_synthetic_noise(slot=task_slot, cell=task_cell, rng=rng, sigma=sigma)
        if self.table.fingerprint() != before:
            raise ScenarioUnavailable("task execution edited the trajectory")
        return {
            "success": success,
            "reason": reason,
            "participant_id": str(participant_id),
            "task_cell": task_cell,
            "task_slot": task_slot,
            "decision_slot": decision_slot,
            "actual_cell": actual,
            "noise": noise,
            "success_rule": "later_slot_on_task_cell",
        }

    def to_summary(self) -> dict:
        mobility = self.table.to_summary()
        return {
            "mode": self.mode,
            "uses_build_world": False,
            "fixture_fallback": self.fixture_fallback,
            "real_city": False,
            "full_city_truth": False,
            "georegistered_yjmob": False,
            "coordinate_system": mobility["coordinate_system"],
            "data_source": mobility["data_source"],
            "schema_example": mobility["schema_example"],
            "example_schema": mobility["example_schema"],
            "participants": mobility["participants"],
            "n_rows": mobility["rows"],
            "slots_per_day": mobility["slots_per_day"],
            "mobility": mobility,
            "noise_field": {
                "label": "synthetic",
                "is_synthetic": True,
                "data_origin": "synthetic_noise_field",
                "real_city": False,
                "sampled_only_after_success": True,
                "samples_drawn": self.synthetic_sample_count,
            },
            "success_rule": "A task succeeds only when the supplied trajectory at the later task slot is on the task cell.",
        }


def _alias_column(frame: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in frame.columns:
            return name
    return None


def noise_from_frame(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = _rename(frame).copy()
    db_col = _alias_column(renamed, ("db", "laeq", "laeq_db", "level_db", "noise_level", "leq"))
    indicator_col = _alias_column(renamed, ("indicator",))
    source_col = _alias_column(renamed, ("source", "data_source"))
    time_col = _alias_column(renamed, ("time", "timestamp", "timestamp_label", "datetime"))
    slot_col = _alias_column(renamed, ("slot", "timeslot", "time_slot"))
    lat_col = _alias_column(renamed, ("latitude", "lat"))
    lon_col = _alias_column(renamed, ("longitude", "lon", "lng"))
    grid_col = _alias_column(renamed, ("grid_id", "grid", "cell"))
    x_col = _alias_column(renamed, ("x", "grid_x"))
    y_col = _alias_column(renamed, ("y", "grid_y"))
    if db_col is None or indicator_col is None or source_col is None:
        raise ScenarioUnavailable("noise table needs db, indicator, and source columns")
    if time_col is None and slot_col is None:
        raise ScenarioUnavailable("noise table needs a time or slot column")
    has_geo = lat_col is not None and lon_col is not None
    has_grid = grid_col is not None
    has_xy = x_col is not None and y_col is not None
    if not (has_geo or has_grid or has_xy):
        raise ScenarioUnavailable("noise table needs lat/lon, a grid id, or x/y")
    out = pd.DataFrame(
        {
            "db": pd.to_numeric(renamed[db_col], errors="coerce"),
            "indicator": renamed[indicator_col].astype(str),
            "source": renamed[source_col].astype(str),
        }
    )
    if out["db"].isna().any() or not np.isfinite(out["db"].to_numpy(dtype=float)).all():
        raise ScenarioUnavailable("noise db values must be finite numbers")
    if out["indicator"].str.strip().eq("").any() or out["indicator"].str.lower().eq("nan").any():
        raise ScenarioUnavailable("noise indicator must be named on every row")
    if time_col is not None:
        out["time"] = renamed[time_col].astype(str)
    else:
        out["time"] = _integer_column(renamed, slot_col).astype(str)
    if slot_col is not None:
        out["slot"] = _integer_column(renamed, slot_col)
    else:
        ordered = sorted(set(out["time"]), key=_time_sort_key)
        mapping = {value: position for position, value in enumerate(ordered)}
        out["slot"] = out["time"].map(mapping).astype(int)
    out["latitude"] = pd.to_numeric(renamed[lat_col], errors="coerce") if lat_col else np.nan
    out["longitude"] = pd.to_numeric(renamed[lon_col], errors="coerce") if lon_col else np.nan
    out["grid_id"] = pd.to_numeric(renamed[grid_col], errors="coerce") if grid_col else np.nan
    out["x"] = pd.to_numeric(renamed[x_col], errors="coerce") if x_col else np.nan
    out["y"] = pd.to_numeric(renamed[y_col], errors="coerce") if y_col else np.nan
    if "coordinate_system" in renamed.columns:
        out["coordinate_system"] = renamed["coordinate_system"].astype(str)
    elif out["latitude"].notna().any() or out["longitude"].notna().any():
        out["coordinate_system"] = "unspecified_geographic"
    else:
        out["coordinate_system"] = "unspecified_grid"
    if "schema_example" in renamed.columns:
        out["schema_example"] = renamed["schema_example"].astype(str)
    else:
        out["schema_example"] = ""
    spatial_ok = (
        (out["latitude"].notna() & out["longitude"].notna())
        | out["grid_id"].notna()
        | (out["x"].notna() & out["y"].notna())
    )
    if not bool(spatial_ok.all()):
        raise ScenarioUnavailable("every noise row needs lat/lon, a grid id, or x/y")
    out["row_id"] = np.arange(len(out), dtype=int)
    out["space_bin"] = [_space_bin(out.iloc[idx]) for idx in range(len(out))]
    return out.reset_index(drop=True)


def _space_bin(row: pd.Series) -> str:
    if pd.notna(row["grid_id"]):
        return f"grid:{int(row['grid_id'])}"
    if pd.notna(row["x"]) and pd.notna(row["y"]):
        return f"xy:{int(row['x'])}:{int(row['y'])}"
    return f"ll:{round(float(row['latitude']), 2)}:{round(float(row['longitude']), 2)}"


def load_noise_table(path: str | Path) -> pd.DataFrame:
    return noise_from_frame(_read_table(path))


class NoiseHoldout:
    """Time holdout plus spatial-bin holdout. Locked rows stay out of active reveal."""

    def __init__(
        self,
        frame: pd.DataFrame,
        *,
        train_ids: tuple[int, ...],
        hidden_ids: tuple[int, ...],
        locked_ids: tuple[int, ...],
        time_holdout: tuple[str, ...],
        space_holdout: tuple[str, ...],
        seed: int,
    ):
        self.frame = frame
        self.train_ids = train_ids
        self.hidden_ids = hidden_ids
        self.locked_ids = locked_ids
        self.time_holdout = time_holdout
        self.space_holdout = space_holdout
        self.seed = int(seed)
        self.full_city_truth = False

    def evaluate(self, training_ids: tuple[int, ...] | None = None) -> dict:
        """Score locked observations with a model fit only on the supplied revealed rows.

        The default training rows are the time/space training split. Locked test ids are
        refused, so a hidden point can enter the fit only after it has been revealed.
        """
        train_ids = self.train_ids if training_ids is None else tuple(int(row_id) for row_id in training_ids)
        if set(train_ids) & set(self.locked_ids):
            raise ScenarioUnavailable("Refusing to fit the holdout on locked test observations.")
        by_indicator: dict[str, dict] = {}
        for indicator in sorted(self.frame["indicator"].unique()):
            subset = self.frame[self.frame["indicator"] == indicator]
            train = subset[subset["row_id"].isin(train_ids)]
            locked = subset[subset["row_id"].isin(self.locked_ids)].sort_values("row_id")
            prediction = _predict_rows(train, locked)
            observed = locked["db"].to_numpy(dtype=float)
            if len(locked) == 0:
                block = {
                    "mae": None,
                    "rmse": None,
                    "n_train": int(len(train)),
                    "n_locked_test": 0,
                    "prediction": [],
                    "observed": [],
                    "row_id": [],
                    "empty_train": len(train) == 0,
                }
            else:
                error = prediction - observed
                block = {
                    "mae": float(np.mean(np.abs(error))),
                    "rmse": float(np.sqrt(np.mean(error**2))),
                    "n_train": int(len(train)),
                    "n_locked_test": int(len(locked)),
                    "prediction": prediction.tolist(),
                    "observed": observed.tolist(),
                    "row_id": locked["row_id"].astype(int).tolist(),
                    "empty_train": len(train) == 0,
                }
            by_indicator[str(indicator)] = block
        single = next(iter(by_indicator.values())) if len(by_indicator) == 1 else None
        return {
            "protocol": "time_space_holdout",
            "full_city_truth": False,
            "citywide_field": None,
            "indicators_pooled": False,
            "disclaimer": HOLDOUT_DISCLAIMER,
            "n_train": len(train_ids),
            "n_hidden_pool": len(self.hidden_ids),
            "n_locked_test": len(self.locked_ids),
            "time_holdout": list(self.time_holdout),
            "space_holdout": list(self.space_holdout),
            "by_indicator": by_indicator,
            "mae": None if single is None else single["mae"],
            "rmse": None if single is None else single["rmse"],
            "model": "idw_on_revealed_observations_of_the_same_indicator",
            "trained_on": "revealed_observations",
            "trained_row_ids": [int(row_id) for row_id in train_ids],
        }

    def reveal(
        self,
        *,
        time: str,
        grid_id: int | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        x: int | None = None,
        y: int | None = None,
        indicator: str | None = None,
    ) -> dict:
        """Return one hidden-pool observation. Locked test rows stay sealed."""
        mask = self.frame["time"].astype(str) == str(time)
        if indicator is not None:
            mask &= self.frame["indicator"].astype(str) == str(indicator)
        if grid_id is not None:
            grids = pd.to_numeric(self.frame["grid_id"], errors="coerce")
            mask &= grids.notna() & grids.eq(int(grid_id))
        elif x is not None and y is not None:
            mask &= self.frame["x"].eq(float(x)) & self.frame["y"].eq(float(y))
        elif latitude is not None and longitude is not None:
            mask &= self.frame["latitude"].sub(float(latitude)).abs().le(1e-6)
            mask &= self.frame["longitude"].sub(float(longitude)).abs().le(1e-6)
        else:
            raise ScenarioUnavailable("active sampling needs a grid id, x/y, or lat/lon")
        ids = self.frame.loc[mask, "row_id"].astype(int).tolist()
        hidden_set = set(self.hidden_ids)
        locked_set = set(self.locked_ids)
        hidden_hits = [row_id for row_id in ids if row_id in hidden_set]
        locked_hits = [row_id for row_id in ids if row_id in locked_set]
        sealed = {"revealed": False, "db": None, "full_city_truth": False, "added_to_training": False}
        if locked_hits:
            return sealed | {"reason": "locked_test"}
        if not hidden_hits:
            return sealed | {"reason": "not_in_hidden_pool"}
        if len(hidden_hits) > 1:
            return sealed | {"reason": "ambiguous"}
        row = self.frame.loc[self.frame["row_id"] == hidden_hits[0]].iloc[0]
        grid_value = None if pd.isna(row["grid_id"]) else int(row["grid_id"])
        return {
            "revealed": True,
            "reason": "hidden_pool",
            "db": float(row["db"]),
            "indicator": str(row["indicator"]),
            "source": str(row["source"]),
            "time": str(row["time"]),
            "grid_id": grid_value,
            "row_id": int(hidden_hits[0]),
            "full_city_truth": False,
            "added_to_training": False,
        }


def _predict_rows(train: pd.DataFrame, locked: pd.DataFrame) -> np.ndarray:
    if len(locked) == 0:
        return np.zeros(0, dtype=np.float64)
    train_x, train_y = _observation_xy(train) if len(train) else (np.zeros(0), np.zeros(0))
    obs = {
        "x": train_x,
        "y": train_y,
        "db": train["db"].to_numpy(dtype=float) if len(train) else np.zeros(0),
        "slot": train["slot"].to_numpy(dtype=int) if len(train) else np.zeros(0, dtype=int),
        "grid": np.zeros(len(train), dtype=int),
    }
    query_x, query_y = _observation_xy(locked)
    predictions = np.empty(len(locked), dtype=np.float64)
    slots = locked["slot"].to_numpy(dtype=int)
    for position in range(len(locked)):
        mu, _std = predict_idw(obs, np.array([[query_x[position], query_y[position]]], dtype=float), int(slots[position]))
        predictions[position] = float(mu[0])
    return predictions


def _observation_xy(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    if len(frame) == 0:
        return np.zeros(0, dtype=float), np.zeros(0, dtype=float)
    if frame["x"].notna().all() and frame["y"].notna().all():
        return frame["x"].to_numpy(dtype=float), frame["y"].to_numpy(dtype=float)
    if frame["longitude"].notna().all() and frame["latitude"].notna().all():
        return frame["longitude"].to_numpy(dtype=float), frame["latitude"].to_numpy(dtype=float)
    if frame["grid_id"].notna().all():
        return frame["grid_id"].to_numpy(dtype=float), np.zeros(len(frame), dtype=float)
    raise ScenarioUnavailable("observations need coordinates before they can be scored")


def split_time_space_holdout(
    frame: pd.DataFrame,
    *,
    time_fraction: float = 0.25,
    space_fraction: float = 0.25,
    lock_fraction: float = 0.5,
    seed: int = 0,
) -> NoiseHoldout:
    """Hold out the latest times and a seeded subset of spatial bins.

    Training rows are in neither holdout. The complement is split into a hidden pool
    that active sampling may read and a locked test set that it may not.
    """
    data = frame.copy().reset_index(drop=True)
    if "row_id" not in data.columns or "space_bin" not in data.columns:
        data = noise_from_frame(data)
    if not 0 < float(lock_fraction) < 1:
        raise ScenarioUnavailable("lock_fraction must be between 0 and 1")
    times = sorted(set(data["time"].astype(str)), key=_time_sort_key)
    if len(times) <= 1:
        time_hold: set[str] = set()
    else:
        n_hold = min(max(int(len(times) * float(time_fraction)), 1), len(times) - 1)
        time_hold = set(times[-n_hold:])
    bins = sorted(set(data["space_bin"].astype(str)))
    rng = np.random.default_rng(int(seed))
    if len(bins) <= 1:
        space_hold: set[str] = set()
    else:
        n_space = min(max(int(len(bins) * float(space_fraction)), 1), len(bins) - 1)
        order = np.array(bins, dtype=object)
        rng.shuffle(order)
        space_hold = set(order[:n_space].tolist())
    time_mask = data["time"].astype(str).isin(time_hold)
    space_mask = data["space_bin"].astype(str).isin(space_hold)
    complement = data.loc[time_mask | space_mask, "row_id"].astype(int).to_numpy()
    train_ids = tuple(int(row_id) for row_id in data.loc[~(time_mask | space_mask), "row_id"].tolist())
    if len(complement) == 0:
        hidden_ids: tuple[int, ...] = ()
        locked_ids: tuple[int, ...] = ()
    else:
        perm = rng.permutation(len(complement))
        n_lock = int(len(complement) * float(lock_fraction))
        if len(complement) >= 2:
            n_lock = min(max(n_lock, 1), len(complement) - 1)
        else:
            n_lock = 1
        ordered = complement[perm]
        locked_ids = tuple(int(row_id) for row_id in ordered[:n_lock].tolist())
        hidden_ids = tuple(int(row_id) for row_id in ordered[n_lock:].tolist())
    return NoiseHoldout(
        data,
        train_ids=train_ids,
        hidden_ids=hidden_ids,
        locked_ids=locked_ids,
        time_holdout=tuple(sorted(time_hold, key=_time_sort_key)),
        space_holdout=tuple(sorted(space_hold)),
        seed=int(seed),
    )


class RealNoiseScenario:
    mode = "real_noise"

    def __init__(self, frame: pd.DataFrame, *, fixture_fallback: bool = False):
        self.frame = frame
        self.fixture_fallback = bool(fixture_fallback)

    def make_holdout(self, **kwargs) -> NoiseHoldout:
        return split_time_space_holdout(self.frame, **kwargs)

    def to_summary(self) -> dict:
        systems = sorted(set(self.frame["coordinate_system"].astype(str)))
        sources = sorted(set(self.frame["source"].astype(str)))
        indicators = sorted(set(self.frame["indicator"].astype(str)))
        return {
            "mode": self.mode,
            "uses_build_world": False,
            "fixture_fallback": self.fixture_fallback,
            "real_city": False,
            "full_city_truth": False,
            "citywide_field": None,
            "disclaimer": HOLDOUT_DISCLAIMER,
            "n_rows": int(len(self.frame)),
            "indicators": indicators,
            "sources": sources,
            "coordinate_system": systems,
            "example_schema": _example_marker(sources + systems + self.frame["schema_example"].astype(str).tolist()),
            "spatial": "observation coordinates only",
        }


def _load_manifest(manifest: dict | None, manifest_path: str | Path | None) -> dict:
    if manifest is not None and manifest_path is not None:
        raise ScenarioUnavailable(FULLY_REAL_REFUSAL + " Pass either a manifest dict or a manifest path.")
    if manifest is None and manifest_path is None:
        raise ScenarioUnavailable(FULLY_REAL_REFUSAL + " No manifest was provided.")
    if manifest is None:
        file_path = Path(manifest_path)
        if not file_path.is_file():
            raise ScenarioUnavailable(FULLY_REAL_REFUSAL + f" Manifest file does not exist: {file_path}")
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    else:
        payload = manifest
    if not isinstance(payload, dict):
        raise ScenarioUnavailable(FULLY_REAL_REFUSAL + " Manifest must be a JSON object.")
    return payload


def _reject_conversion(payload: dict) -> None:
    for key in _CONVERSION_KEYS:
        if key in payload and payload[key] not in (None, False):
            raise ScenarioUnavailable(FULLY_REAL_REFUSAL + " The manifest asks for a coordinate conversion.")


class FullyRealScenario:
    mode = "fully_real"

    def __init__(self, table: TrajectoryTable, noise: pd.DataFrame, manifest: dict):
        self.table = table
        self.noise = noise
        self.manifest = {
            "geography_overlap": bool(manifest["geography_overlap"]),
            "time_overlap": bool(manifest["time_overlap"]),
        }

    def to_summary(self) -> dict:
        mobility = self.table.to_summary()
        noise_systems = sorted(set(self.noise["coordinate_system"].astype(str)))
        return {
            "mode": self.mode,
            "uses_build_world": False,
            "geography_overlap": self.manifest["geography_overlap"],
            "time_overlap": self.manifest["time_overlap"],
            "georegistered_yjmob": False,
            "real_city": False,
            "full_city_truth": False,
            "citywide_field": None,
            "mobility_coordinate_system": mobility["coordinate_system"],
            "noise_coordinate_system": noise_systems,
            "mobility": mobility,
            "n_noise_rows": int(len(self.noise)),
            "disclaimer": "Overlap flags come from the manifest. Coordinates were not transformed.",
        }


def _open_fully_real(
    *,
    mobility_path: str | Path | None,
    noise_path: str | Path | None,
    manifest_path: str | Path | None,
    mobility_frame: pd.DataFrame | None,
    noise_frame: pd.DataFrame | None,
    manifest: dict | None,
    slots_per_day: int | None,
) -> FullyRealScenario:
    payload = _load_manifest(manifest, manifest_path)
    _reject_conversion(payload)
    geography = _as_bool(payload, "geography_overlap")
    time_overlap = _as_bool(payload, "time_overlap")
    if not geography or not time_overlap:
        raise ScenarioUnavailable(
            FULLY_REAL_REFUSAL + f" Manifest geography_overlap={geography} time_overlap={time_overlap}."
        )
    table, _fallback = _load_mobility(mobility_path, mobility_frame, slots_per_day)
    noise, _noise_fallback = _load_noise(noise_path, noise_frame)
    file_mobility = _crs_key(table.coordinate_system)
    noise_keys = {_crs_key(value) for value in noise["coordinate_system"].astype(str)}
    if len(noise_keys) != 1:
        raise ScenarioUnavailable(FULLY_REAL_REFUSAL + " Noise observations mix coordinate systems.")
    noise_key = next(iter(noise_keys))
    manifest_mobility = payload.get("mobility_coordinate_system")
    manifest_noise = payload.get("noise_coordinate_system")
    if manifest_mobility is not None and _crs_key(str(manifest_mobility)) != file_mobility:
        raise ScenarioUnavailable(FULLY_REAL_REFUSAL + " Manifest mobility coordinate system does not match the file.")
    if manifest_noise is not None and _crs_key(str(manifest_noise)) != noise_key:
        raise ScenarioUnavailable(FULLY_REAL_REFUSAL + " Manifest noise coordinate system does not match the file.")
    noise_has_latlon = bool(noise["latitude"].notna().any() or noise["longitude"].notna().any())
    if file_mobility == "yjmob_virtual" and (noise_key == "wgs84" or noise_has_latlon):
        raise ScenarioUnavailable(
            FULLY_REAL_REFUSAL
            + " The mobility table is a YJMob virtual grid and the noise table has geographic coordinates. Those x/y values were not converted."
        )
    if noise_key == "yjmob_virtual" and (file_mobility == "wgs84" or noise_has_latlon):
        raise ScenarioUnavailable(FULLY_REAL_REFUSAL + " YJMob coordinates were not placed on WGS84.")
    if file_mobility != noise_key:
        raise ScenarioUnavailable(
            FULLY_REAL_REFUSAL + " The mobility and noise coordinate systems differ, so geography overlap is not accepted."
        )
    return FullyRealScenario(table, noise, payload)


class SyntheticScenario:
    mode = "synthetic"

    def __init__(self, world):
        self.world = world

    def to_summary(self) -> dict:
        return {
            "mode": self.mode,
            "uses_build_world": True,
            "scenario": self.world.scenario,
            "coordinate_system": self.world.coordinate_system,
            "data_origin": self.world.data_origin,
            "real_city": False,
            "full_city_truth": False,
            "height": self.world.height,
            "width": self.world.width,
            "n_slots": self.world.n_slots,
            "n_agents": len(self.world.agents),
        }


def _open_synthetic(seed: int, world_kwargs: dict) -> SyntheticScenario:
    # Imported here so real-data modes do not bind or call the synthetic world builder.
    from urbannoise.world import build_world

    params = {key: world_kwargs[key] for key in _WORLD_KEYS if key in world_kwargs}
    params["seed"] = int(seed)
    return SyntheticScenario(build_world(**params))


def _load_mobility(
    path: str | Path | None,
    frame: pd.DataFrame | None,
    slots_per_day: int | None,
) -> tuple[TrajectoryTable, bool]:
    if frame is not None:
        return trajectory_from_frame(frame, slots_per_day=slots_per_day), False
    if path:
        return load_mobility_table(path, slots_per_day=slots_per_day), False
    return load_mobility_table(default_mobility_fixture(), slots_per_day=slots_per_day), True


def _load_noise(path: str | Path | None, frame: pd.DataFrame | None) -> tuple[pd.DataFrame, bool]:
    if frame is not None:
        return noise_from_frame(frame), False
    if path:
        return load_noise_table(path), False
    return load_noise_table(default_noise_fixture()), True


def open_scenario(
    mode: str,
    *,
    mobility_path: str | Path | None = None,
    noise_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    mobility_frame: pd.DataFrame | None = None,
    noise_frame: pd.DataFrame | None = None,
    manifest: dict | None = None,
    seed: int = 7,
    slots_per_day: int | None = None,
    **world_kwargs,
) -> SyntheticScenario | RealMobilityScenario | RealNoiseScenario | FullyRealScenario:
    """Open one scenario mode.

    Missing real mobility or noise files fall back to the committed schema fixtures.
    Those fixtures are synthetic-shaped examples of the column layout, not YJMob extracts.
    """
    selected = str(mode).strip().lower()
    if selected not in SCENARIO_MODES:
        known = ", ".join(SCENARIO_MODES)
        raise ScenarioUnavailable(f"Unknown scenario mode {mode!r}. Expected one of: {known}.")
    if selected == "synthetic":
        if slots_per_day is not None:
            world_kwargs["slots_per_day"] = slots_per_day
        return _open_synthetic(seed, world_kwargs)
    if selected == "real_mobility":
        table, fallback = _load_mobility(mobility_path, mobility_frame, slots_per_day)
        return RealMobilityScenario(table, seed=seed, fixture_fallback=fallback)
    if selected == "real_noise":
        frame, fallback = _load_noise(noise_path, noise_frame)
        return RealNoiseScenario(frame, fixture_fallback=fallback)
    return _open_fully_real(
        mobility_path=mobility_path,
        noise_path=noise_path,
        manifest_path=manifest_path,
        mobility_frame=mobility_frame,
        noise_frame=noise_frame,
        manifest=manifest,
        slots_per_day=slots_per_day,
    )

#!/usr/bin/env python3
"""Stream YJMob100K, GeoLife, and NoiseCapture into gitignored processed tables.

YJMob stays on its anonymous grid columns. No latitude or longitude is created.
GeoLife keeps WGS84 points from .plt records after the 6-line header.
NoiseCapture keeps raw property names. noise_level, laeq, la50, and lden are
never averaged together. Decibel summaries report an energy mean and an
arithmetic mean separately.

Examples
--------
python scripts/preprocess_datasets.py --dataset all --data-dir data --resume
python scripts/preprocess_datasets.py --dataset yjmob100k --data-dir data --recheck
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

try:
    import orjson
except ImportError:  # pragma: no cover
    orjson = None

DATASETS = ("all", "yjmob100k", "geolife", "noisecapture")
EARTH_RADIUS_M = 6_371_008.8
METERS_PER_DEG_LAT = 111_132.92
IMPOSSIBLE_SPEED_M_S = 1000.0 / 3.6
ROOT = Path(__file__).resolve().parents[1]

GEOLIFE_RULES = {
    "header_lines_skipped": 6,
    "coordinate_system": "WGS84",
    "distance": "haversine, Earth radius 6371008.8 m",
    "impossible_jump": "After the last accepted point, reject the candidate when delta_t<=0 and separation>1 m, or when delta_t>0 and speed>1000 km/h.",
    "duplicate_timestamp": "Reject the candidate when delta_t<=0 and separation<=1 m.",
    "null_island": "Reject latitude==0 and longitude==0 before the jump test.",
    "bad_coordinate": "Reject latitude outside [-90, 90] or longitude outside [-180, 180].",
    "grids": (
        "Equirectangular bins at 250, 500, and 1000 m. "
        "grid_y = floor(latitude * 111132.92 / meters). "
        "grid_x = floor(longitude * 111132.92 * cos(latitude) / meters). "
        "These bins are not YJMob indices and are not a projected CRS."
    ),
}

POINT_FIELDS = {
    "pk_track",
    "time_ISO8601",
    "time_epoch",
    "time_gps_ISO8601",
    "time_gps_epoch",
    "noise_level",
    "speed",
    "orientation",
    "accuracy",
}
TRACK_FIELDS = {
    "pleasantness",
    "pk_track",
    "track_uuid",
    "gain_calibration",
    "time_ISO8601",
    "time_epoch",
    "noise_level",
    "time_length",
    "tags",
    "party_tag",
}
AREA_FIELDS = {
    "cell_q",
    "cell_r",
    "la50",
    "laeq",
    "lden",
    "mean_pleasantness",
    "measure_count",
    "first_measure_ISO_8601",
    "first_measure_epoch",
    "last_measure_ISO_8601",
    "last_measure_epoch",
    "leq_profile",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def loads(payload: bytes | str):
    if orjson is not None:
        return orjson.loads(payload)
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return json.loads(payload)


def dumps(payload) -> str:
    if orjson is not None:
        return orjson.dumps(payload).decode("utf-8")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def atomic_write_json(path: Path, payload) -> None:
    atomic_write_text(path, json.dumps(sanitize(payload), indent=2, ensure_ascii=False) + "\n")


def sanitize(value):
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    if hasattr(value, "item"):
        return sanitize(value.item())
    return str(value)


def sql_path(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def connect(temp_dir: Path) -> duckdb.DuckDBPyConnection:
    temp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET memory_limit='5GB'")
    con.execute("SET threads=2")
    con.execute(f"SET temp_directory={sql_path(temp_dir)}")
    return con


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def grid_xy(lat: float, lon: float, meters: int) -> tuple[int, int]:
    gy = math.floor(lat * METERS_PER_DEG_LAT / meters)
    gx = math.floor(lon * METERS_PER_DEG_LAT * math.cos(math.radians(lat)) / meters)
    return int(gx), int(gy)


def manifest_entries(data_dir: Path, dataset: str) -> list[dict]:
    path = data_dir / "manifests" / "download_manifest.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in payload.get("files", []) if item.get("dataset") == dataset]


def new_bucket() -> dict:
    return {
        "count": 0,
        "nulls": 0,
        "nonfinite": 0,
        "overflow": 0,
        "zeros": 0,
        "energy_sum": 0.0,
        "arith_sum": 0.0,
        "min": None,
        "max": None,
    }


def add_bucket(bucket: dict, value) -> None:
    if value is None:
        bucket["nulls"] += 1
        return
    try:
        level = float(value)
    except (TypeError, ValueError):
        bucket["nonfinite"] += 1
        return
    if not math.isfinite(level):
        bucket["nonfinite"] += 1
        return
    bucket["min"] = level if bucket["min"] is None else min(bucket["min"], level)
    bucket["max"] = level if bucket["max"] is None else max(bucket["max"], level)
    if level == 0.0:
        bucket["zeros"] += 1
    try:
        energy = 10.0 ** (level / 10.0)
    except OverflowError:
        energy = math.inf
    if not math.isfinite(energy):
        bucket["overflow"] += 1
        return
    bucket["count"] += 1
    bucket["energy_sum"] += energy
    bucket["arith_sum"] += level


def merge_bucket(dst: dict, src: dict) -> None:
    dst["count"] += src["count"]
    dst["nulls"] += src["nulls"]
    dst["nonfinite"] += src["nonfinite"]
    dst["overflow"] += src["overflow"]
    dst["zeros"] += src["zeros"]
    dst["energy_sum"] += src["energy_sum"]
    dst["arith_sum"] += src["arith_sum"]
    if src["min"] is not None:
        dst["min"] = src["min"] if dst["min"] is None else min(dst["min"], src["min"])
    if src["max"] is not None:
        dst["max"] = src["max"] if dst["max"] is None else max(dst["max"], src["max"])


def bucket_means(bucket: dict) -> dict:
    if bucket["count"] <= 0:
        return {"energy_mean_db": None, "arithmetic_mean_db": None}
    return {
        "energy_mean_db": 10.0 * math.log10(bucket["energy_sum"] / bucket["count"]),
        "arithmetic_mean_db": bucket["arith_sum"] / bucket["count"],
    }


def as_float(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def as_int(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value)
    return None


def extra_json(properties: dict, known: set[str]) -> str | None:
    extra = {key: value for key, value in properties.items() if key not in known}
    if not extra:
        return None
    return dumps(extra)


def json_cell(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return dumps(value)


class BatchWriter:
    def __init__(self, path: Path, schema: pa.Schema):
        self.path = path
        self.schema = schema
        self.columns = {field.name: [] for field in schema}
        self.writer = None
        self.rows = 0
        self._closed = False

    def append(self, row: dict) -> None:
        for name, values in self.columns.items():
            values.append(row.get(name))
        if len(self.columns[self.schema.names[0]]) >= 20000:
            self.flush()

    def flush(self) -> None:
        size = len(self.columns[self.schema.names[0]])
        if size == 0:
            return
        table = pa.Table.from_pydict(self.columns, schema=self.schema)
        if self.writer is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.writer = pq.ParquetWriter(self.path, self.schema, compression="zstd")
        self.writer.write_table(table)
        self.rows += size
        for values in self.columns.values():
            values.clear()

    def close(self) -> int:
        if self._closed:
            return self.rows
        self._closed = True
        self.flush()
        if self.writer is not None:
            self.writer.close()
        elif self.path.exists() and self.rows == 0:
            self.path.unlink()
        return self.rows


def gzip_first_line(path: Path) -> str:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return handle.readline().rstrip("\r\n")


def resolve_yjmob(columns: list[str]) -> dict:
    lookup = {column.lower(): column for column in columns}
    def pick(options: tuple[str, ...]) -> str | None:
        for option in options:
            if option in lookup:
                return lookup[option]
        return None
    return {
        "uid": pick(("uid", "user_id", "userid")),
        "day": pick(("d", "day")),
        "timeslot": pick(("t", "timeslot", "time_slot", "slot")),
        "x": pick(("x",)),
        "y": pick(("y",)),
    }


def yjmob_reader(path: Path, physical: dict[str, str]) -> str:
    columns = ", ".join(f"'{physical[name]}': '{dtype}'" for name, dtype in (
        ("uid", "BIGINT"),
        ("day", "INTEGER"),
        ("timeslot", "INTEGER"),
        ("x", "INTEGER"),
        ("y", "INTEGER"),
    ))
    return f"read_csv({sql_path(path)}, header=true, columns={{{columns}}})"


def query_one(con: duckdb.DuckDBPyConnection, sql: str) -> dict:
    relation = con.execute(sql)
    row = relation.fetchone()
    names = [item[0] for item in relation.description]
    return {name: sanitize(value) for name, value in zip(names, row)}


def query_all(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict]:
    relation = con.execute(sql)
    names = [item[0] for item in relation.description]
    return [{name: sanitize(value) for name, value in zip(names, row)} for row in relation.fetchall()]


def profile_trajectory(con: duckdb.DuckDBPyConnection, path: Path, out_dir: Path) -> dict:
    started = time.time()
    header = gzip_first_line(path)
    columns = [column.strip() for column in header.split(",")]
    physical = resolve_yjmob(columns)
    missing = [name for name, column in physical.items() if column is None]
    result = {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "header": header,
        "physical_columns": physical,
        "latitude_column_created": False,
        "longitude_column_created": False,
    }
    if missing:
        result["status"] = "schema_mismatch"
        result["error"] = f"Could not resolve {missing} from header {header!r}"
        return result
    reader = yjmob_reader(path, physical)
    uid, day, slot, xcol, ycol = physical["uid"], physical["day"], physical["timeslot"], physical["x"], physical["y"]
    print(f"yjmob aggregate {path.name}", flush=True)
    stats = query_one(
        con,
        f"""
        SELECT
          count(*)::BIGINT AS n_rows,
          count(DISTINCT {uid})::BIGINT AS n_users,
          min({uid}) AS uid_min,
          max({uid}) AS uid_max,
          count(DISTINCT {day})::BIGINT AS n_distinct_days,
          min({day}) AS day_min,
          max({day}) AS day_max,
          count(DISTINCT {slot})::BIGINT AS n_distinct_timeslots,
          min({slot}) AS timeslot_min,
          max({slot}) AS timeslot_max,
          min({xcol}) AS x_min,
          max({xcol}) AS x_max,
          min({ycol}) AS y_min,
          max({ycol}) AS y_max,
          count(*) FILTER (WHERE {uid} IS NULL) AS uid_null,
          count(*) FILTER (WHERE {day} IS NULL) AS day_null,
          count(*) FILTER (WHERE {slot} IS NULL) AS timeslot_null,
          count(*) FILTER (WHERE {xcol} IS NULL) AS x_null,
          count(*) FILTER (WHERE {ycol} IS NULL) AS y_null,
          count(*) FILTER (WHERE {xcol} IS NULL OR {ycol} IS NULL) AS null_coordinate_rows,
          count(*) FILTER (WHERE {xcol} = 0 OR {ycol} = 0) AS zero_xy_rows,
          count(*) FILTER (WHERE {xcol} < 1 OR {xcol} > 200 OR {ycol} < 1 OR {ycol} > 200) AS outside_1_200
        FROM {reader}
        """,
    )
    print(f"yjmob histogram {path.name}", flush=True)
    day_hist = query_all(con, f"SELECT {day} AS day, count(*)::BIGINT AS rows FROM {reader} GROUP BY 1 ORDER BY 1")
    slot_hist = query_all(con, f"SELECT {slot} AS timeslot, count(*)::BIGINT AS rows FROM {reader} GROUP BY 1 ORDER BY 1")
    print(f"yjmob user-days {path.name}", flush=True)
    buckets = 10 if int(stats["n_users"] or 0) > 30000 else 1
    user_days = {
        "user_days": 0,
        "sum_rows": 0,
        "unique_user_day_slots": 0,
        "duplicate_slot_rows": 0,
        "min_slots_in_user_day": None,
        "max_slots_in_user_day": None,
        "uid_buckets": buckets,
    }
    for bucket in range(buckets):
        where = "" if buckets == 1 else f"WHERE {uid} % {buckets} = {bucket}"
        print(f"yjmob user-days {path.name} bucket {bucket + 1}/{buckets}", flush=True)
        part = query_one(
            con,
            f"""
            WITH per AS (
              SELECT {uid} AS uid, {day} AS day, count(*)::BIGINT AS n_rows, count(DISTINCT {slot})::BIGINT AS n_slots
              FROM {reader}
              {where}
              GROUP BY 1, 2
            )
            SELECT
              count(*)::BIGINT AS user_days,
              coalesce(sum(n_rows), 0)::BIGINT AS sum_rows,
              coalesce(sum(n_slots), 0)::BIGINT AS unique_user_day_slots,
              coalesce(sum(n_rows - n_slots), 0)::BIGINT AS duplicate_slot_rows,
              min(n_slots) AS min_slots_in_user_day,
              max(n_slots) AS max_slots_in_user_day
            FROM per
            """,
        )
        user_days["user_days"] += int(part["user_days"] or 0)
        user_days["sum_rows"] += int(part["sum_rows"] or 0)
        user_days["unique_user_day_slots"] += int(part["unique_user_day_slots"] or 0)
        user_days["duplicate_slot_rows"] += int(part["duplicate_slot_rows"] or 0)
        if part["min_slots_in_user_day"] is not None:
            current = user_days["min_slots_in_user_day"]
            user_days["min_slots_in_user_day"] = part["min_slots_in_user_day"] if current is None else min(current, part["min_slots_in_user_day"])
        if part["max_slots_in_user_day"] is not None:
            current = user_days["max_slots_in_user_day"]
            user_days["max_slots_in_user_day"] = part["max_slots_in_user_day"] if current is None else max(current, part["max_slots_in_user_day"])
    user_days["avg_slots_in_user_day"] = (
        user_days["unique_user_day_slots"] / user_days["user_days"] if user_days["user_days"] else None
    )
    n_users = int(stats["n_users"] or 0)
    n_days = int(stats["n_distinct_days"] or 0)
    n_slots = int(stats["n_distinct_timeslots"] or 0)
    unique_keys = int(user_days["unique_user_day_slots"] or 0)
    user_day_count = int(user_days["user_days"] or 0)
    day_span = None
    slot_span = None
    if stats["day_min"] is not None and stats["day_max"] is not None:
        day_span = int(stats["day_max"]) - int(stats["day_min"]) + 1
    if stats["timeslot_min"] is not None and stats["timeslot_max"] is not None:
        slot_span = int(stats["timeslot_max"]) - int(stats["timeslot_min"]) + 1
    gaps = {
        "null_coordinate_rows": stats["null_coordinate_rows"],
        "x_null": stats["x_null"],
        "y_null": stats["y_null"],
        "unique_observed_keys": unique_keys,
        "absent_slots_within_observed_user_days": user_day_count * n_slots - unique_keys,
        "absent_vs_cartesian_of_observed_uid_day_timeslot": n_users * n_days * n_slots - unique_keys,
        "day_index_span": day_span,
        "missing_day_values_inside_min_max": None if day_span is None else day_span - n_days,
        "timeslot_index_span": slot_span,
        "missing_timeslot_values_inside_min_max": None if slot_span is None else slot_span - n_slots,
        "definition": (
            "Null coordinate counts are computed only on stored rows. "
            "Absent combinations are scalar differences. No dense user-day-timeslot tensor is allocated and no missing row is inserted. "
            "absent_slots_within_observed_user_days uses the global set of observed timeslot values for every user-day that has at least one row. "
            "The cartesian figure uses the observed sets of uid, day, and timeslot values."
        ),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    subset_counts = {}
    print(f"yjmob subsets {path.name}", flush=True)
    stem = path.name.replace(".csv.gz", "").replace(".gz", "")
    subset_1000 = out_dir / f"{stem}_subset_1000users.parquet"
    subset_100 = out_dir / f"{stem}_subset_100users.parquet"
    subset_10 = out_dir / f"{stem}_subset_10users.parquet"
    con.execute(
        f"""
        COPY (
          SELECT * FROM {reader}
          WHERE {uid} IN (
            SELECT {uid} FROM (SELECT DISTINCT {uid} FROM {reader}) ORDER BY {uid} LIMIT 1000
          )
        ) TO {sql_path(subset_1000)} (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    con.execute(
        f"""
        COPY (
          SELECT * FROM read_parquet({sql_path(subset_1000)})
          WHERE {uid} IN (SELECT {uid} FROM read_parquet({sql_path(subset_1000)}) GROUP BY 1 ORDER BY 1 LIMIT 100)
        ) TO {sql_path(subset_100)} (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    con.execute(
        f"""
        COPY (
          SELECT * FROM read_parquet({sql_path(subset_100)})
          WHERE {uid} IN (SELECT {uid} FROM read_parquet({sql_path(subset_100)}) GROUP BY 1 ORDER BY 1 LIMIT 10)
        ) TO {sql_path(subset_10)} (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    for label, subset_path in (("10", subset_10), ("100", subset_100), ("1000", subset_1000)):
        counts = query_one(
            con,
            f"""
            SELECT count(*)::BIGINT AS n_rows, count(DISTINCT {uid})::BIGINT AS n_users,
                   min({day}) AS day_min, max({day}) AS day_max,
                   min({slot}) AS timeslot_min, max({slot}) AS timeslot_max
            FROM read_parquet({sql_path(subset_path)})
            """,
        )
        schema_names = list(pq.read_schema(subset_path).names)
        forbidden = [name for name in schema_names if name.lower() in {"lat", "lon", "latitude", "longitude"}]
        counts.update(
            {
                "path": str(subset_path),
                "bytes": subset_path.stat().st_size,
                "columns": schema_names,
                "forbidden_coordinate_columns": forbidden,
                "selection": f"lowest {label} {uid} values present in {path.name}, all of their stored rows",
            }
        )
        subset_counts[label] = counts
    result.update(
        {
            "status": "ok",
            "stats": stats,
            "day_histogram": day_hist,
            "timeslot_histogram": slot_hist,
            "user_days": user_days,
            "gaps": gaps,
            "subsets": subset_counts,
            "elapsed_seconds": round(time.time() - started, 3),
        }
    )
    print(
        "YJMob {name} rows={rows} users={users} distinct_days={days} day_min={dmin} day_max={dmax} "
        "distinct_timeslots={slots} timeslot_min={tmin} timeslot_max={tmax} x_null={xnull} y_null={ynull} "
        "subset10_users={u10} subset10_rows={r10} subset100_users={u100} subset100_rows={r100} "
        "subset1000_users={u1000} subset1000_rows={r1000}".format(
            name=path.name,
            rows=stats["n_rows"],
            users=stats["n_users"],
            days=stats["n_distinct_days"],
            dmin=stats["day_min"],
            dmax=stats["day_max"],
            slots=stats["n_distinct_timeslots"],
            tmin=stats["timeslot_min"],
            tmax=stats["timeslot_max"],
            xnull=stats["x_null"],
            ynull=stats["y_null"],
            u10=subset_counts["10"]["n_users"],
            r10=subset_counts["10"]["n_rows"],
            u100=subset_counts["100"]["n_users"],
            r100=subset_counts["100"]["n_rows"],
            u1000=subset_counts["1000"]["n_users"],
            r1000=subset_counts["1000"]["n_rows"],
        ),
        flush=True,
    )
    return result


def profile_poi_categories(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    nonempty = [line for line in lines if line.strip()]
    return {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "line_count": len(lines),
        "nonempty_lines": len(nonempty),
        "header_detected": False,
        "notes": "The file is a list of category names, one per line, with no header and no coordinates.",
        "first_line": nonempty[0] if nonempty else None,
        "last_line": nonempty[-1] if nonempty else None,
    }


def profile_cell_poi(con: duckdb.DuckDBPyConnection, path: Path) -> dict:
    header = gzip_first_line(path)
    tokens = header.split(",")
    numeric = True
    for token in tokens:
        try:
            float(token)
        except ValueError:
            numeric = False
            break
    if numeric:
        reader = f"read_csv({sql_path(path)}, header=false, auto_detect=true, sample_size=-1)"
        header_mode = "no header; first line is numeric"
    else:
        reader = f"read_csv({sql_path(path)}, header=true, auto_detect=true, sample_size=-1)"
        header_mode = "header row"
    description = query_all(con, f"DESCRIBE SELECT * FROM {reader}")
    stats = query_one(con, f"SELECT count(*)::BIGINT AS n_rows FROM {reader}")
    columns = [row.get("column_name") for row in description]
    result = {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "first_line": header[:500],
        "header_mode": header_mode,
        "columns": columns,
        "column_count": len(columns),
        "n_rows": stats["n_rows"],
        "renamed_to_latitude_longitude": False,
    }
    lower = {column.lower(): column for column in columns}
    if "x" in lower and "y" in lower:
        xcol, ycol = lower["x"], lower["y"]
        result["grid_range"] = query_one(
            con,
            f"SELECT min({xcol}) AS x_min, max({xcol}) AS x_max, min({ycol}) AS y_min, max({ycol}) AS y_max, count(DISTINCT {xcol}) AS n_x, count(DISTINCT {ycol}) AS n_y FROM {reader}",
        )
        result["grid_columns"] = {"x": xcol, "y": ycol}
        names = {column.lower(): column for column in columns}
        if "poicategory" in names and "poi_count" in names:
            category = '"' + names["poicategory"].replace('"', '""') + '"'
            count_column = '"' + names["poi_count"].replace('"', '""') + '"'
            try:
                result["category_summary"] = query_one(
                    con,
                    f"SELECT count(DISTINCT {category})::BIGINT AS categories, sum({count_column})::BIGINT AS poi_count_sum FROM {reader}",
                )
            except Exception as exc:  # noqa: BLE001
                result["category_summary_error"] = f"{type(exc).__name__}: {exc}"
    elif numeric and len(columns) >= 2:
        c0, c1 = columns[0], columns[1]
        result["first_two_column_ranges"] = query_one(
            con,
            f"SELECT min({c0}) AS column_1_min, max({c0}) AS column_1_max, min({c1}) AS column_2_min, max({c1}) AS column_2_max FROM {reader}",
        )
        result["notes"] = "No header names the first columns x and y. Ranges are reported under column positions and were not renamed to longitude or latitude."
    return result


def preprocess_yjmob(data_dir: Path, resume: bool, recheck: bool) -> dict:
    raw_dir = data_dir / "raw" / "yjmob100k"
    out_dir = data_dir / "processed" / "yjmob100k"
    summary_path = out_dir / "summary.json"
    if resume and summary_path.exists() and not recheck:
        cached = json.loads(summary_path.read_text(encoding="utf-8"))
        files_ok = bool(cached.get("files")) and all(item.get("status") == "ok" for item in cached["files"])
        if files_ok:
            print(f"yjmob resume {summary_path}", flush=True)
            return cached
    summary = {"status": "ok", "files": [], "errors": []}
    if not raw_dir.exists():
        summary["status"] = "not_downloaded"
        summary["error"] = f"missing directory {raw_dir}"
        return summary
    con = connect(data_dir / "processed" / "duckdb_tmp")
    trajectories = sorted(raw_dir.glob("yjmob100k-dataset*.csv.gz"))
    for path in trajectories:
        try:
            summary["files"].append(profile_trajectory(con, path, out_dir))
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            summary["files"].append({"filename": path.name, "status": "failed", "error": error})
            summary["errors"].append(error)
            print(f"YJMob failed {path.name}: {error}", flush=True)
    categories = raw_dir / "POI_datacategories.csv"
    if categories.exists():
        try:
            summary["poi_categories"] = profile_poi_categories(categories)
            print(
                f"YJMob POI_datacategories.csv nonempty_lines={summary['poi_categories']['nonempty_lines']}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            summary["poi_categories"] = {"filename": categories.name, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    cell = raw_dir / "cell_POIcat.csv.gz"
    if cell.exists():
        try:
            summary["cell_poi"] = profile_cell_poi(con, cell)
            print(
                f"YJMob cell_POIcat.csv.gz rows={summary['cell_poi'].get('n_rows')} columns={summary['cell_poi'].get('column_count')}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            summary["cell_poi"] = {"filename": cell.name, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
    ok_files = [item for item in summary["files"] if item.get("status") == "ok"]
    if len(ok_files) >= 2:
        left, right = ok_files[0], ok_files[1]
        left_uid = left["physical_columns"]["uid"]
        right_uid = right["physical_columns"]["uid"]
        try:
            overlap = query_one(
                con,
                f"""
                SELECT count(*)::BIGINT AS overlapping_uids
                FROM (
                  SELECT {left_uid} AS uid FROM {yjmob_reader(raw_dir / left['filename'], left['physical_columns'])}
                  INTERSECT
                  SELECT {right_uid} AS uid FROM {yjmob_reader(raw_dir / right['filename'], right['physical_columns'])}
                )
                """,
            )
            summary["uid_overlap_first_two_files"] = {"left": left["filename"], "right": right["filename"], **overlap}
            print(
                f"YJMob uid overlap {left['filename']} ∩ {right['filename']} = {overlap['overlapping_uids']}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            summary["uid_overlap_first_two_files"] = {"error": f"{type(exc).__name__}: {exc}"}
    con.close()
    if summary["errors"]:
        summary["status"] = "partial"
    atomic_write_json(summary_path, summary)
    return summary


def parse_timestamp(date_text: str, time_text: str) -> datetime | None:
    text = f"{date_text} {time_text}"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def pdf_literal_text(data: bytes) -> str:
    """Recover parenthesized PDF text operators from FlateDecode streams.

    This is not a PDF layout engine. It is used only to find short guide
    statements such as a license heading or a timezone sentence.
    """
    import re
    import zlib

    pieces: list[str] = []
    for part in re.split(br"stream\r?\n", data)[1:]:
        blob = part.split(br"endstream", 1)[0]
        decoded = None
        for candidate in (blob, blob.strip(b"\r\n")):
            try:
                decoded = zlib.decompress(candidate)
                break
            except zlib.error:
                continue
        if decoded is None:
            continue
        for raw in re.findall(br"\((?:\\.|[^\\)]){1,300}\)", decoded):
            inner = raw[1:-1].decode("latin-1", "replace")
            inner = inner.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\").replace("\\n", " ")
            pieces.append(inner)
    return "".join(pieces)


def text_windows(text: str, keywords: tuple[str, ...], limit: int = 6, radius: int = 280) -> list[str]:
    found: list[str] = []
    lower = text.lower()
    for keyword in keywords:
        start = 0
        needle = keyword.lower()
        while len(found) < limit:
            index = lower.find(needle, start)
            if index < 0:
                break
            found.append(" ".join(text[max(0, index - radius) : index + radius].split()))
            start = index + len(needle)
    return found


def printable_snippets(data: bytes, keywords: tuple[str, ...], limit: int = 8) -> list[str]:
    pieces = []
    current = bytearray()
    for byte in data:
        if 32 <= byte <= 126:
            current.append(byte)
        else:
            if len(current) >= 12:
                pieces.append(current.decode("ascii"))
            current = bytearray()
    if len(current) >= 12:
        pieces.append(current.decode("ascii"))
    text = "\n".join(pieces)
    found = []
    lower = text.lower()
    for keyword in keywords:
        start = 0
        needle = keyword.lower()
        while len(found) < limit:
            index = lower.find(needle, start)
            if index < 0:
                break
            snippet = text[max(0, index - 140) : index + 220].replace("\n", " ")
            found.append(snippet)
            start = index + len(needle)
    return found


def preprocess_geolife(data_dir: Path, resume: bool, recheck: bool) -> dict:
    raw_dir = data_dir / "raw" / "geolife"
    out_dir = data_dir / "processed" / "geolife"
    summary_path = out_dir / "summary.json"
    if resume and summary_path.exists() and not recheck:
        print(f"geolife resume {summary_path}", flush=True)
        return json.loads(summary_path.read_text(encoding="utf-8"))
    zips = sorted(raw_dir.glob("*.zip")) if raw_dir.exists() else []
    if not zips:
        return {"status": "not_downloaded", "error": f"no zip in {raw_dir}"}
    self_check = {
        "zero_distance_m": haversine_m(0.0, 0.0, 0.0, 0.0),
        "one_degree_latitude_m": haversine_m(0.0, 0.0, 1.0, 0.0),
    }
    if abs(self_check["zero_distance_m"]) > 1e-6:
        raise RuntimeError(f"haversine self-check failed: {self_check}")
    out_dir.mkdir(parents=True, exist_ok=True)
    points_path = out_dir / "accepted_points.parquet"
    trajectories_path = out_dir / "trajectories.parquet"
    if points_path.exists():
        points_path.unlink()
    if trajectories_path.exists():
        trajectories_path.unlink()
    point_schema = pa.schema(
        [
            ("participant_id", pa.string()),
            ("trajectory_file", pa.string()),
            ("latitude", pa.float64()),
            ("longitude", pa.float64()),
            ("altitude", pa.float64()),
            ("unused_field", pa.string()),
            ("excel_serial", pa.string()),
            ("date", pa.string()),
            ("time", pa.string()),
            ("timestamp", pa.string()),
            ("step_distance_m", pa.float64()),
            ("speed_m_s", pa.float64()),
            ("grid_250_x", pa.int64()),
            ("grid_250_y", pa.int64()),
            ("grid_500_x", pa.int64()),
            ("grid_500_y", pa.int64()),
            ("grid_1000_x", pa.int64()),
            ("grid_1000_y", pa.int64()),
        ]
    )
    trajectory_schema = pa.schema(
        [
            ("participant_id", pa.string()),
            ("trajectory_file", pa.string()),
            ("raw_points", pa.int64()),
            ("accepted_points", pa.int64()),
            ("rejected_points", pa.int64()),
            ("distance_m", pa.float64()),
            ("timestamp_min", pa.string()),
            ("timestamp_max", pa.string()),
            ("latitude_min", pa.float64()),
            ("latitude_max", pa.float64()),
            ("longitude_min", pa.float64()),
            ("longitude_max", pa.float64()),
        ]
    )
    point_writer = BatchWriter(points_path, point_schema)
    trajectory_writer = BatchWriter(trajectories_path, trajectory_schema)
    reasons: Counter[str] = Counter()
    users: set[str] = set()
    header_feet = 0
    header_not_feet = 0
    header_wgs = 0
    header_not_wgs = 0
    first_header = None
    sidecar_snippets: list[dict] = []
    sidecar_count = 0
    label_files = 0
    altitude_sentinel_neg777 = 0
    rejected_samples = []
    grid_sets = {250: set(), 500: set(), 1000: set()}
    grid_truncated = {250: False, 500: False, 1000: False}
    distance_parts: list[float] = []
    raw_points = 0
    accepted_points = 0
    files_parsed = 0
    unsafe_members = []
    started = time.time()
    for zip_path in zips:
        with zipfile.ZipFile(zip_path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                parts = Path(info.filename).parts
                if info.filename.startswith("/") or ".." in parts:
                    unsafe_members.append(info.filename)
                    continue
                lower = info.filename.lower()
                if lower.endswith(".plt"):
                    continue
                sidecar_count += 1
                if lower.endswith("labels.txt"):
                    label_files += 1
                    continue
                record = {"zip": zip_path.name, "name": info.filename, "bytes": info.file_size}
                if info.file_size <= 30_000_000:
                    data = archive.read(info)
                    if lower.endswith(".pdf"):
                        extracted = pdf_literal_text(data)
                        record["pdf_literal_chars"] = len(extracted)
                        snippets = text_windows(
                            extracted,
                            ("license agreement", "non-commercial", "we use gmt", "time zone", "altitude in feet"),
                        )
                    else:
                        snippets = printable_snippets(data, ("license", "licence", "gmt", "utc", "copyright", "wgs", "time zone", "timezone"))
                    if snippets:
                        record["snippets"] = snippets[:6]
                sidecar_snippets.append(record)
            plt_infos = [info for info in archive.infolist() if info.filename.lower().endswith(".plt") and not info.is_dir()]
            for index, info in enumerate(plt_infos, start=1):
                parts = Path(info.filename).parts
                if "Trajectory" in parts:
                    position = parts.index("Trajectory")
                    participant = parts[position - 1] if position else Path(info.filename).stem
                else:
                    participant = Path(info.filename).parent.name or Path(info.filename).stem
                users.add(participant)
                text = archive.read(info).decode("utf-8", "replace")
                lines = text.splitlines()
                header = lines[:6]
                if first_header is None and header:
                    first_header = header
                header_text = "\n".join(header).lower()
                if "feet" in header_text:
                    header_feet += 1
                else:
                    header_not_feet += 1
                if "wgs" in header_text:
                    header_wgs += 1
                else:
                    header_not_wgs += 1
                parsed = []
                file_raw = 0
                for line_number, line in enumerate(lines[6:], start=7):
                    if not line.strip():
                        continue
                    file_raw += 1
                    raw_points += 1
                    pieces = [item.strip() for item in line.split(",")]
                    if len(pieces) < 7:
                        reasons["short_row"] += 1
                        continue
                    try:
                        lat = float(pieces[0])
                        lon = float(pieces[1])
                        altitude = float(pieces[3])
                    except ValueError:
                        reasons["bad_number"] += 1
                        continue
                    timestamp = parse_timestamp(pieces[5], pieces[6])
                    if timestamp is None:
                        reasons["bad_time"] += 1
                        continue
                    if altitude == -777:
                        altitude_sentinel_neg777 += 1
                    parsed.append(
                        {
                            "lat": lat,
                            "lon": lon,
                            "altitude": altitude,
                            "unused": pieces[2],
                            "excel": pieces[4],
                            "date": pieces[5],
                            "time": pieces[6],
                            "timestamp": timestamp,
                            "line": line_number,
                        }
                    )
                parsed.sort(key=lambda item: (item["timestamp"], item["line"]))
                accepted_rows = []
                previous = None
                file_rejected = 0
                distance = 0.0
                for point in parsed:
                    reason = None
                    step = None
                    speed = None
                    if not (-90 <= point["lat"] <= 90 and -180 <= point["lon"] <= 180):
                        reason = "bad_coordinate"
                    elif point["lat"] == 0.0 and point["lon"] == 0.0:
                        reason = "null_island"
                    elif previous is not None:
                        step = haversine_m(previous["lat"], previous["lon"], point["lat"], point["lon"])
                        delta = (point["timestamp"] - previous["timestamp"]).total_seconds()
                        if delta <= 0 and step > 1.0:
                            reason = "impossible_jump"
                            speed = None
                        elif delta <= 0:
                            reason = "duplicate_timestamp"
                        else:
                            speed = step / delta
                            if speed > IMPOSSIBLE_SPEED_M_S:
                                reason = "impossible_jump"
                    if reason is not None:
                        reasons[reason] += 1
                        file_rejected += 1
                        if len(rejected_samples) < 30:
                            rejected_samples.append(
                                {
                                    "participant_id": participant,
                                    "trajectory_file": info.filename,
                                    "line": point["line"],
                                    "latitude": point["lat"],
                                    "longitude": point["lon"],
                                    "timestamp": point["timestamp"].isoformat(),
                                    "reason": reason,
                                    "step_distance_m": step,
                                    "speed_m_s": speed,
                                }
                            )
                        continue
                    grid_250 = grid_xy(point["lat"], point["lon"], 250)
                    grid_500 = grid_xy(point["lat"], point["lon"], 500)
                    grid_1000 = grid_xy(point["lat"], point["lon"], 1000)
                    for meters, cell in ((250, grid_250), (500, grid_500), (1000, grid_1000)):
                        if not grid_truncated[meters]:
                            grid_sets[meters].add(cell)
                            if len(grid_sets[meters]) > 3_000_000:
                                grid_truncated[meters] = True
                    if step is not None:
                        distance += step
                    accepted_rows.append(
                        {
                            "participant_id": participant,
                            "trajectory_file": info.filename,
                            "latitude": point["lat"],
                            "longitude": point["lon"],
                            "altitude": point["altitude"],
                            "unused_field": point["unused"],
                            "excel_serial": point["excel"],
                            "date": point["date"],
                            "time": point["time"],
                            "timestamp": point["timestamp"].isoformat(),
                            "step_distance_m": step,
                            "speed_m_s": speed,
                            "grid_250_x": grid_250[0],
                            "grid_250_y": grid_250[1],
                            "grid_500_x": grid_500[0],
                            "grid_500_y": grid_500[1],
                            "grid_1000_x": grid_1000[0],
                            "grid_1000_y": grid_1000[1],
                        }
                    )
                    previous = point
                for row in accepted_rows:
                    point_writer.append(row)
                accepted_points += len(accepted_rows)
                distance_parts.append(distance)
                timestamps = [row["timestamp"] for row in accepted_rows]
                lats = [row["latitude"] for row in accepted_rows]
                lons = [row["longitude"] for row in accepted_rows]
                trajectory_writer.append(
                    {
                        "participant_id": participant,
                        "trajectory_file": info.filename,
                        "raw_points": file_raw,
                        "accepted_points": len(accepted_rows),
                        "rejected_points": file_rejected,
                        "distance_m": distance,
                        "timestamp_min": min(timestamps) if timestamps else None,
                        "timestamp_max": max(timestamps) if timestamps else None,
                        "latitude_min": min(lats) if lats else None,
                        "latitude_max": max(lats) if lats else None,
                        "longitude_min": min(lons) if lons else None,
                        "longitude_max": max(lons) if lons else None,
                    }
                )
                files_parsed += 1
                if files_parsed % 1000 == 0:
                    print(f"geolife trajectories={files_parsed} accepted_points={accepted_points} raw_points={raw_points}", flush=True)
    point_rows = point_writer.close()
    trajectory_rows = trajectory_writer.close()
    rejected_points = sum(reasons.values())
    total_distance = math.fsum(distance_parts)
    timestamp_timezone = "unspecified"
    timestamp_timezone_evidence = None
    for record in sidecar_snippets:
        for snippet in record.get("snippets") or []:
            if "gmt" in snippet.lower():
                timestamp_timezone = "GMT"
                timestamp_timezone_evidence = snippet
                break
        if timestamp_timezone_evidence:
            break
    summary = {
        "status": "ok",
        "rules": GEOLIFE_RULES,
        "haversine_self_check": self_check,
        "zips": [path.name for path in zips],
        "users": len(users),
        "trajectories": files_parsed,
        "trajectory_rows_written": trajectory_rows,
        "raw_points": raw_points,
        "accepted_points": accepted_points,
        "accepted_rows_written": point_rows,
        "rejected_points": rejected_points,
        "rejected_reasons": dict(reasons),
        "balance_raw_equals_accepted_plus_rejected": raw_points == accepted_points + rejected_points,
        "distance_m": total_distance,
        "distance_km": total_distance / 1000.0,
        "grid_cell_counts": {str(key): len(value) for key, value in grid_sets.items()},
        "grid_cell_count_truncated": {str(key): value for key, value in grid_truncated.items()},
        "header_feet_files": header_feet,
        "header_not_feet_files": header_not_feet,
        "header_wgs_files": header_wgs,
        "header_not_wgs_files": header_not_wgs,
        "label_files": label_files,
        "altitude_sentinel_neg777": altitude_sentinel_neg777,
        "timestamp_timezone": timestamp_timezone,
        "timestamp_timezone_evidence": timestamp_timezone_evidence,
        "first_plt_header": first_header,
        "sidecar_files": sidecar_count,
        "sidecar_snippets": sidecar_snippets,
        "rejected_samples": rejected_samples,
        "unsafe_members": unsafe_members,
        "elapsed_seconds": round(time.time() - started, 3),
        "points_parquet": str(points_path),
        "points_parquet_bytes": points_path.stat().st_size if points_path.exists() else 0,
        "trajectories_parquet": str(trajectories_path),
        "trajectories_parquet_bytes": trajectories_path.stat().st_size if trajectories_path.exists() else 0,
    }
    atomic_write_json(summary_path, summary)
    print(
        "GeoLife users={users} trajectories={trajectories} raw_points={raw_points} accepted_points={accepted} "
        "rejected_points={rejected} rejected_impossible_jump={jumps} distance_m={distance}".format(
            users=summary["users"],
            trajectories=summary["trajectories"],
            raw_points=summary["raw_points"],
            accepted=summary["accepted_points"],
            rejected=summary["rejected_points"],
            jumps=reasons.get("impossible_jump", 0),
            distance=summary["distance_m"],
        ),
        flush=True,
    )
    return summary


def member_kind(name: str) -> str:
    lower = name.lower()
    if ".points.geojson" in lower:
        return "points"
    if ".tracks.geojson" in lower:
        return "tracks"
    if ".areas.geojson" in lower:
        return "areas"
    if lower.endswith(".geojson"):
        return "geojson_other"
    if lower.endswith("readme.html"):
        return "readme"
    return "other"


def iter_feature_lines(handle):
    for raw in handle:
        line = raw.strip()
        if line.endswith(b","):
            line = line[:-1].rstrip()
        if line.endswith(b"]"):
            line = line.rstrip(b"]").rstrip()
        if not (line.startswith(b'{"type":"Feature"') or line.startswith(b'{"type": "Feature"')):
            continue
        try:
            yield loads(line), None
        except Exception as exc:  # noqa: BLE001
            yield None, f"{type(exc).__name__}: {exc}"


def bbox_of(geometry: dict) -> tuple[list[float] | None, int]:
    coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
    invalid = 0
    bounds = None

    def visit(node):
        nonlocal invalid, bounds
        if isinstance(node, (list, tuple)):
            if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
                lon = float(node[0])
                lat = float(node[1])
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    if bounds is None:
                        bounds = [lon, lat, lon, lat]
                    else:
                        bounds[0] = min(bounds[0], lon)
                        bounds[1] = min(bounds[1], lat)
                        bounds[2] = max(bounds[2], lon)
                        bounds[3] = max(bounds[3], lat)
                else:
                    invalid += 1
            else:
                for item in node:
                    visit(item)

    visit(coords)
    return bounds, invalid


def observe_time(state: dict, epoch, iso) -> None:
    number = as_int(epoch)
    if number is None:
        return
    if state["min_epoch"] is None or number < state["min_epoch"]:
        state["min_epoch"] = number
        state["min_iso"] = iso if isinstance(iso, str) else None
    if state["max_epoch"] is None or number > state["max_epoch"]:
        state["max_epoch"] = number
        state["max_iso"] = iso if isinstance(iso, str) else None


def new_time_state() -> dict:
    return {"min_epoch": None, "max_epoch": None, "min_iso": None, "max_iso": None}


def point_schema() -> pa.Schema:
    return pa.schema(
        [
            ("archive", pa.string()),
            ("member", pa.string()),
            ("geometry_type", pa.string()),
            ("longitude", pa.float64()),
            ("latitude", pa.float64()),
            ("pk_track", pa.int64()),
            ("time_ISO8601", pa.string()),
            ("time_epoch", pa.int64()),
            ("time_gps_ISO8601", pa.string()),
            ("time_gps_epoch", pa.int64()),
            ("noise_level", pa.float64()),
            ("speed", pa.float64()),
            ("orientation", pa.float64()),
            ("accuracy", pa.float64()),
            ("extra_json", pa.string()),
        ]
    )


def track_schema() -> pa.Schema:
    return pa.schema(
        [
            ("archive", pa.string()),
            ("member", pa.string()),
            ("geometry_type", pa.string()),
            ("bbox_min_lon", pa.float64()),
            ("bbox_min_lat", pa.float64()),
            ("bbox_max_lon", pa.float64()),
            ("bbox_max_lat", pa.float64()),
            ("pk_track", pa.int64()),
            ("track_uuid", pa.string()),
            ("gain_calibration", pa.float64()),
            ("time_ISO8601", pa.string()),
            ("time_epoch", pa.int64()),
            ("noise_level", pa.float64()),
            ("time_length", pa.float64()),
            ("pleasantness", pa.float64()),
            ("tags", pa.string()),
            ("party_tag", pa.string()),
            ("extra_json", pa.string()),
        ]
    )


def area_schema() -> pa.Schema:
    return pa.schema(
        [
            ("archive", pa.string()),
            ("member", pa.string()),
            ("geometry_type", pa.string()),
            ("bbox_min_lon", pa.float64()),
            ("bbox_min_lat", pa.float64()),
            ("bbox_max_lon", pa.float64()),
            ("bbox_max_lat", pa.float64()),
            ("cell_q", pa.int64()),
            ("cell_r", pa.int64()),
            ("la50", pa.float64()),
            ("laeq", pa.float64()),
            ("lden", pa.float64()),
            ("mean_pleasantness", pa.float64()),
            ("measure_count", pa.int64()),
            ("first_measure_ISO_8601", pa.string()),
            ("first_measure_epoch", pa.int64()),
            ("last_measure_ISO_8601", pa.string()),
            ("last_measure_epoch", pa.int64()),
            ("leq_profile", pa.string()),
            ("extra_json", pa.string()),
        ]
    )


def merge_bbox(dst: list[float] | None, src: list[float] | None) -> list[float] | None:
    if src is None:
        return dst
    if dst is None:
        return list(src)
    return [min(dst[0], src[0]), min(dst[1], src[1]), max(dst[2], src[2]), max(dst[3], src[3])]


def process_noisecapture_zip(path: Path, out_dir: Path) -> dict:
    started = time.time()
    result = {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "status": "ok",
        "members": [],
        "indicators": {},
        "geometry_types": Counter(),
        "parse_errors": 0,
        "parse_error_samples": [],
        "invalid_coordinates": 0,
        "bbox": None,
        "times": {},
        "track_vs_points": {
            "tracks": 0,
            "tracks_with_points": 0,
            "tracks_without_points": 0,
            "points_with_unknown_track": 0,
            "sum_abs_diff_db": 0.0,
            "max_abs_diff_db": None,
        },
        "area_laeq_equals_la50": 0,
        "area_pairs": 0,
        "readme_sha256": None,
        "readme_has_odbl": None,
        "readme_defines_lden": None,
        "readme_excerpt": None,
    }
    slug = hashlib.sha1(path.name.encode("utf-8")).hexdigest()[:16]
    writers = {
        "points": BatchWriter(out_dir / "points" / f"{slug}.parquet", point_schema()),
        "tracks": BatchWriter(out_dir / "tracks" / f"{slug}.parquet", track_schema()),
        "areas": BatchWriter(out_dir / "areas" / f"{slug}.parquet", area_schema()),
    }
    indicators = {
        "points.noise_level": new_bucket(),
        "tracks.noise_level": new_bucket(),
        "areas.la50": new_bucket(),
        "areas.laeq": new_bucket(),
        "areas.lden": new_bucket(),
    }
    weighted = {"weight_sum": 0.0, "weighted_energy_sum": 0.0, "count_weighted": 0, "count_missing_weight": 0, "overflow": 0}
    times = {"points": new_time_state(), "tracks": new_time_state(), "areas": new_time_state()}
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        result["status"] = "failed"
        result["error"] = f"BadZipFile: {exc}"
        return result
    try:
        with archive:
            names = archive.namelist()
            readme_name = next((name for name in names if member_kind(name) == "readme"), None)
            if readme_name:
                data = archive.read(readme_name)
                result["readme_sha256"] = hashlib.sha256(data).hexdigest()
                text = data.decode("utf-8", "replace")
                result["readme_has_odbl"] = "opendatacommons.org/licenses/odbl" in text.lower() or "open database license" in text.lower()
                result["readme_defines_lden"] = "lden" in text.lower()
                excerpt_at = text.lower().find("open database")
                if excerpt_at >= 0:
                    result["readme_excerpt"] = re_space(text[excerpt_at : excerpt_at + 500])
            track_levels: dict[int, float] = {}
            for name in names:
                kind = member_kind(name)
                if kind not in {"tracks", "areas"}:
                    continue
                features = 0
                errors = 0
                geometries = Counter()
                with archive.open(name) as handle:
                    for feature, error in iter_feature_lines(handle):
                        if error or feature is None:
                            errors += 1
                            if len(result["parse_error_samples"]) < 5:
                                result["parse_error_samples"].append({"member": name, "error": error})
                            continue
                        features += 1
                        properties = feature.get("properties") or {}
                        geometry = feature.get("geometry") or {}
                        geometries[geometry.get("type") or "none"] += 1
                        bounds, invalid = bbox_of(geometry)
                        result["invalid_coordinates"] += invalid
                        result["bbox"] = merge_bbox(result["bbox"], bounds)
                        if kind == "tracks":
                            add_bucket(indicators["tracks.noise_level"], properties.get("noise_level"))
                            observe_time(times["tracks"], properties.get("time_epoch"), properties.get("time_ISO8601"))
                            level = as_float(properties.get("noise_level"))
                            weight = as_float(properties.get("time_length"))
                            pk = as_int(properties.get("pk_track"))
                            if pk is not None and level is not None:
                                track_levels[pk] = level
                            if level is None or weight is None or weight <= 0:
                                weighted["count_missing_weight"] += 1
                            else:
                                try:
                                    term = weight * (10.0 ** (level / 10.0))
                                except OverflowError:
                                    term = math.inf
                                if math.isfinite(term):
                                    weighted["weighted_energy_sum"] += term
                                    weighted["weight_sum"] += weight
                                    weighted["count_weighted"] += 1
                                else:
                                    weighted["overflow"] += 1
                            writers["tracks"].append(
                                {
                                    "archive": path.name,
                                    "member": name,
                                    "geometry_type": geometry.get("type"),
                                    "bbox_min_lon": None if bounds is None else bounds[0],
                                    "bbox_min_lat": None if bounds is None else bounds[1],
                                    "bbox_max_lon": None if bounds is None else bounds[2],
                                    "bbox_max_lat": None if bounds is None else bounds[3],
                                    "pk_track": pk,
                                    "track_uuid": properties.get("track_uuid") if isinstance(properties.get("track_uuid"), str) else json_cell(properties.get("track_uuid")),
                                    "gain_calibration": as_float(properties.get("gain_calibration")),
                                    "time_ISO8601": properties.get("time_ISO8601") if isinstance(properties.get("time_ISO8601"), str) else None,
                                    "time_epoch": as_int(properties.get("time_epoch")),
                                    "noise_level": level,
                                    "time_length": weight,
                                    "pleasantness": as_float(properties.get("pleasantness")),
                                    "tags": json_cell(properties.get("tags")),
                                    "party_tag": json_cell(properties.get("party_tag")),
                                    "extra_json": extra_json(properties, TRACK_FIELDS),
                                }
                            )
                        else:
                            add_bucket(indicators["areas.la50"], properties.get("la50"))
                            add_bucket(indicators["areas.laeq"], properties.get("laeq"))
                            add_bucket(indicators["areas.lden"], properties.get("lden"))
                            la50 = as_float(properties.get("la50"))
                            laeq = as_float(properties.get("laeq"))
                            if la50 is not None and laeq is not None:
                                result["area_pairs"] += 1
                                if abs(la50 - laeq) <= 1e-6:
                                    result["area_laeq_equals_la50"] += 1
                            observe_time(times["areas"], properties.get("first_measure_epoch"), properties.get("first_measure_ISO_8601"))
                            writers["areas"].append(
                                {
                                    "archive": path.name,
                                    "member": name,
                                    "geometry_type": geometry.get("type"),
                                    "bbox_min_lon": None if bounds is None else bounds[0],
                                    "bbox_min_lat": None if bounds is None else bounds[1],
                                    "bbox_max_lon": None if bounds is None else bounds[2],
                                    "bbox_max_lat": None if bounds is None else bounds[3],
                                    "cell_q": as_int(properties.get("cell_q")),
                                    "cell_r": as_int(properties.get("cell_r")),
                                    "la50": la50,
                                    "laeq": laeq,
                                    "lden": as_float(properties.get("lden")),
                                    "mean_pleasantness": as_float(properties.get("mean_pleasantness")),
                                    "measure_count": as_int(properties.get("measure_count")),
                                    "first_measure_ISO_8601": properties.get("first_measure_ISO_8601") if isinstance(properties.get("first_measure_ISO_8601"), str) else None,
                                    "first_measure_epoch": as_int(properties.get("first_measure_epoch")),
                                    "last_measure_ISO_8601": properties.get("last_measure_ISO_8601") if isinstance(properties.get("last_measure_ISO_8601"), str) else None,
                                    "last_measure_epoch": as_int(properties.get("last_measure_epoch")),
                                    "leq_profile": json_cell(properties.get("leq_profile")),
                                    "extra_json": extra_json(properties, AREA_FIELDS),
                                }
                            )
                result["parse_errors"] += errors
                result["geometry_types"].update(geometries)
                result["members"].append({"name": name, "kind": kind, "features": features, "parse_errors": errors, "geometry_types": dict(geometries)})
            point_acc: dict[int, list[float]] = {}
            for name in names:
                if member_kind(name) != "points":
                    continue
                features = 0
                errors = 0
                geometries = Counter()
                seen = 0
                with archive.open(name) as handle:
                    for feature, error in iter_feature_lines(handle):
                        if error or feature is None:
                            errors += 1
                            if len(result["parse_error_samples"]) < 5:
                                result["parse_error_samples"].append({"member": name, "error": error})
                            continue
                        features += 1
                        seen += 1
                        properties = feature.get("properties") or {}
                        geometry = feature.get("geometry") or {}
                        geometries[geometry.get("type") or "none"] += 1
                        bounds, invalid = bbox_of(geometry)
                        result["invalid_coordinates"] += invalid
                        result["bbox"] = merge_bbox(result["bbox"], bounds)
                        level = as_float(properties.get("noise_level"))
                        add_bucket(indicators["points.noise_level"], properties.get("noise_level"))
                        observe_time(times["points"], properties.get("time_epoch"), properties.get("time_ISO8601"))
                        pk = as_int(properties.get("pk_track"))
                        if pk is None or pk not in track_levels:
                            result["track_vs_points"]["points_with_unknown_track"] += 1
                        elif level is not None:
                            slot = point_acc.setdefault(pk, [0.0, 0])
                            try:
                                energy = 10.0 ** (level / 10.0)
                            except OverflowError:
                                energy = math.inf
                            if math.isfinite(energy):
                                slot[0] += energy
                                slot[1] += 1
                        coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
                        lon = lat = None
                        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                            lon = as_float(coords[0])
                            lat = as_float(coords[1])
                        writers["points"].append(
                            {
                                "archive": path.name,
                                "member": name,
                                "geometry_type": geometry.get("type"),
                                "longitude": lon,
                                "latitude": lat,
                                "pk_track": pk,
                                "time_ISO8601": properties.get("time_ISO8601") if isinstance(properties.get("time_ISO8601"), str) else None,
                                "time_epoch": as_int(properties.get("time_epoch")),
                                "time_gps_ISO8601": properties.get("time_gps_ISO8601") if isinstance(properties.get("time_gps_ISO8601"), str) else None,
                                "time_gps_epoch": as_int(properties.get("time_gps_epoch")),
                                "noise_level": level,
                                "speed": as_float(properties.get("speed")),
                                "orientation": as_float(properties.get("orientation")),
                                "accuracy": as_float(properties.get("accuracy")),
                                "extra_json": extra_json(properties, POINT_FIELDS),
                            }
                        )
                        if seen % 1_000_000 == 0:
                            print(f"noisecapture {path.name} {name} features={seen}", flush=True)
                result["parse_errors"] += errors
                result["geometry_types"].update(geometries)
                result["members"].append({"name": name, "kind": "points", "features": features, "parse_errors": errors, "geometry_types": dict(geometries)})
        compared = 0
        missing = 0
        sum_abs = 0.0
        max_abs = None
        for pk, level in track_levels.items():
            slot = point_acc.get(pk)
            if not slot or slot[1] <= 0:
                missing += 1
                continue
            mean = 10.0 * math.log10(slot[0] / slot[1])
            diff = abs(mean - level)
            sum_abs += diff
            max_abs = diff if max_abs is None else max(max_abs, diff)
            compared += 1
        result["track_vs_points"].update(
            {
                "tracks": len(track_levels),
                "tracks_with_points": compared,
                "tracks_without_points": missing,
                "sum_abs_diff_db": sum_abs,
                "max_abs_diff_db": max_abs,
                "mean_abs_diff_db": (sum_abs / compared) if compared else None,
            }
        )
        result["indicators"] = indicators
        result["track_duration_weighted"] = weighted
        if weighted["weight_sum"] > 0:
            result["track_duration_weighted"]["energy_mean_db"] = 10.0 * math.log10(weighted["weighted_energy_sum"] / weighted["weight_sum"])
        else:
            result["track_duration_weighted"]["energy_mean_db"] = None
        result["times"] = times
        result["geometry_types"] = dict(result["geometry_types"])
        result["elapsed_seconds"] = round(time.time() - started, 3)
    finally:
        result["rows_written"] = {kind: writer.close() for kind, writer in writers.items()}
    return result


def re_space(text: str) -> str:
    return " ".join(text.split())


def archive_cache_path(out_dir: Path, filename: str) -> Path:
    slug = hashlib.sha1(filename.encode("utf-8")).hexdigest()[:16]
    return out_dir / "by_archive" / f"{slug}.json"


def preprocess_noisecapture(data_dir: Path, resume: bool, recheck: bool) -> dict:
    raw_dir = data_dir / "raw" / "noisecapture"
    out_dir = data_dir / "processed" / "noisecapture"
    summary_path = out_dir / "summary.json"
    if resume and summary_path.exists() and not recheck:
        cached = json.loads(summary_path.read_text(encoding="utf-8"))
        if cached.get("status") in {"ok", "partial"} and cached.get("archives"):
            print(f"noisecapture resume summary {summary_path}", flush=True)
            return cached
    entries = manifest_entries(data_dir, "noisecapture")
    by_name = {entry.get("filename"): entry for entry in entries}
    paths = sorted(raw_dir.glob("*.zip"), key=lambda item: item.stat().st_size, reverse=True) if raw_dir.exists() else []
    if not paths:
        return {"status": "not_downloaded", "error": f"no zip in {raw_dir}", "recorded_failures": [entry for entry in entries if entry.get("status") == "failed"]}
    archives = []
    failures = []
    for path in paths:
        entry = by_name.get(path.name)
        if entry and entry.get("status") in {"failed", "checksum_mismatch"}:
            failures.append({"filename": path.name, "status": entry.get("status"), "error": entry.get("error")})
            continue
        if entry and entry.get("bytes") is not None and path.stat().st_size != entry.get("bytes"):
            failures.append(
                {
                    "filename": path.name,
                    "status": "incomplete",
                    "error": f"on-disk bytes {path.stat().st_size} != manifest bytes {entry.get('bytes')}",
                }
            )
            continue
        cache = archive_cache_path(out_dir, path.name)
        if resume and cache.exists() and not recheck:
            loaded = json.loads(cache.read_text(encoding="utf-8"))
            archives.append(loaded)
            print(f"noisecapture cached {path.name} points={sum(m.get('features', 0) for m in loaded.get('members', []) if m.get('kind')=='points')}", flush=True)
            continue
        print(f"noisecapture parse {path.name} bytes={path.stat().st_size}", flush=True)
        try:
            parsed = process_noisecapture_zip(path, out_dir)
        except Exception as exc:  # noqa: BLE001
            parsed = {"filename": path.name, "bytes": path.stat().st_size, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        atomic_write_json(cache, parsed)
        archives.append(parsed)
        point_features = sum(member.get("features", 0) for member in parsed.get("members", []) if member.get("kind") == "points")
        print(
            f"NoiseCapture {path.name} status={parsed.get('status')} point_features={point_features} error={parsed.get('error')}",
            flush=True,
        )
    for entry in entries:
        if entry.get("status") == "failed" and entry.get("filename") not in {path.name for path in paths}:
            failures.append({"filename": entry.get("filename"), "status": "failed", "error": entry.get("error"), "url": entry.get("url")})
    summary = combine_noisecapture(archives, failures)
    atomic_write_json(summary_path, summary)
    points = summary["totals"]["point_features"]
    tracks = summary["totals"]["track_features"]
    areas = summary["totals"]["area_features"]
    print(f"NoiseCapture archives_ok={summary['archives_ok']} point_features={points} track_features={tracks} area_features={areas}", flush=True)
    return summary


def combine_noisecapture(archives: list[dict], failures: list[dict]) -> dict:
    indicators = {key: new_bucket() for key in ("points.noise_level", "tracks.noise_level", "areas.la50", "areas.laeq", "areas.lden")}
    weighted = {"weight_sum": 0.0, "weighted_energy_sum": 0.0, "count_weighted": 0, "count_missing_weight": 0, "overflow": 0}
    totals = {"point_features": 0, "track_features": 0, "area_features": 0, "other_features": 0, "parse_errors": 0, "invalid_coordinates": 0}
    readme_hashes: Counter[str] = Counter()
    top_regions = []
    compact = []
    bbox = None
    compared = 0
    sum_abs = 0.0
    max_abs = None
    area_equal = 0
    area_pairs = 0
    for archive in archives:
        if archive.get("status") != "ok":
            compact.append(
                {
                    "filename": archive.get("filename"),
                    "bytes": archive.get("bytes"),
                    "status": archive.get("status"),
                    "error": archive.get("error"),
                }
            )
            continue
        for key, bucket in indicators.items():
            if key in (archive.get("indicators") or {}):
                merge_bucket(bucket, archive["indicators"][key])
        weight = archive.get("track_duration_weighted") or {}
        for field in ("weight_sum", "weighted_energy_sum", "count_weighted", "count_missing_weight", "overflow"):
            weighted[field] += weight.get(field) or 0
        totals["parse_errors"] += archive.get("parse_errors") or 0
        totals["invalid_coordinates"] += archive.get("invalid_coordinates") or 0
        bbox = merge_bbox(bbox, archive.get("bbox"))
        area_equal += archive.get("area_laeq_equals_la50") or 0
        area_pairs += archive.get("area_pairs") or 0
        diff = archive.get("track_vs_points") or {}
        compared += diff.get("tracks_with_points") or 0
        sum_abs += diff.get("sum_abs_diff_db") or 0
        if diff.get("max_abs_diff_db") is not None:
            max_abs = diff["max_abs_diff_db"] if max_abs is None else max(max_abs, diff["max_abs_diff_db"])
        if archive.get("readme_sha256"):
            readme_hashes[archive["readme_sha256"]] += 1
        counts = {"points": 0, "tracks": 0, "areas": 0}
        for member in archive.get("members") or []:
            kind = member.get("kind")
            counts[kind] = counts.get(kind, 0) + member.get("features", 0)
            if kind == "points":
                top_regions.append({"archive": archive.get("filename"), "member": member.get("name"), "point_features": member.get("features", 0)})
        totals["point_features"] += counts.get("points", 0)
        totals["track_features"] += counts.get("tracks", 0)
        totals["area_features"] += counts.get("areas", 0)
        totals["other_features"] += counts.get("geojson_other", 0)
        compact.append(
            {
                "filename": archive.get("filename"),
                "bytes": archive.get("bytes"),
                "status": "ok",
                "point_features": counts.get("points", 0),
                "track_features": counts.get("tracks", 0),
                "area_features": counts.get("areas", 0),
                "parse_errors": archive.get("parse_errors"),
                "invalid_coordinates": archive.get("invalid_coordinates"),
                "readme_sha256": archive.get("readme_sha256"),
                "readme_has_odbl": archive.get("readme_has_odbl"),
                "readme_defines_lden": archive.get("readme_defines_lden"),
                "bbox": archive.get("bbox"),
                "times": archive.get("times"),
                "rows_written": archive.get("rows_written"),
                "track_vs_points": archive.get("track_vs_points"),
                "elapsed_seconds": archive.get("elapsed_seconds"),
            }
        )
    indicator_report = {}
    for key, bucket in indicators.items():
        indicator_report[key] = {**bucket, **bucket_means(bucket)}
    if weighted["weight_sum"] > 0:
        weighted["energy_mean_db"] = 10.0 * math.log10(weighted["weighted_energy_sum"] / weighted["weight_sum"])
    else:
        weighted["energy_mean_db"] = None
    top_regions.sort(key=lambda item: item["point_features"], reverse=True)
    ok = sum(1 for item in compact if item.get("status") == "ok")
    return {
        "status": "ok" if not failures and all(item.get("status") == "ok" for item in compact) else "partial",
        "archives_ok": ok,
        "archives_seen": len(archives),
        "totals": totals,
        "indicators": indicator_report,
        "track_duration_weighted_noise_level": weighted,
        "track_vs_points": {
            "tracks_with_points": compared,
            "sum_abs_diff_db": sum_abs,
            "mean_abs_diff_db": (sum_abs / compared) if compared else None,
            "max_abs_diff_db": max_abs,
            "definition": "For each track pk_track, compare the track property noise_level with the energy mean of point properties named noise_level. The two are not averaged into one series.",
        },
        "area_laeq_equals_la50": area_equal,
        "area_pairs": area_pairs,
        "bbox": bbox,
        "readme_hash_counts": dict(readme_hashes),
        "top_point_members": top_regions[:40],
        "archives": compact,
        "failures": failures,
        "indicator_policy": (
            "points.noise_level, tracks.noise_level, areas.laeq, areas.la50, and areas.lden are accumulated separately. "
            "leq_profile arrays are stored as JSON text and are not reduced to a mean. "
            "The energy mean is 10*log10(mean(10^(L/10))). The arithmetic mean is the mean of the decibel numbers. "
            "Track duration-weighted energy mean uses time_length as the weight and is separate from the unweighted energy mean."
        ),
    }


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def render_quality(summary: dict, path: Path) -> None:
    lines = [
        "# Dataset quality report",
        "",
        f"Generated at {summary.get('generated_at')} by `scripts/preprocess_datasets.py`.",
        "",
        "Every count in this file is taken from the preprocess summary written by that run. Upstream web pages are not used as row counts.",
        "",
        f"Command: `{' '.join(summary.get('command') or [])}`",
        "",
        "No YJMob latitude or longitude column is created. NoiseCapture `noise_level`, `laeq`, `la50`, and `lden` stay in separate accumulators. An arithmetic mean of decibel numbers is never stored as an energy-equivalent level.",
        "",
    ]
    yj = summary.get("datasets", {}).get("yjmob100k") or {}
    lines.append("## YJMob100K")
    lines.append("")
    if yj.get("status") == "not_downloaded":
        lines.append(f"Not preprocessed: `{yj.get('error')}`")
    else:
        lines.append("Physical trajectory columns are whatever the gzip header contains. The released files use `uid,d,t,x,y`. `d` is the day index and `t` is the timeslot index named by the Zenodo description; this script does not rename them and does not turn them into clock times or geographic coordinates.")
        lines.append("")
        for item in yj.get("files") or []:
            lines.append(f"### {item.get('filename')}")
            lines.append("")
            if item.get("status") != "ok":
                lines.append(f"Status `{item.get('status')}`. Error: `{item.get('error')}`")
                lines.append("")
                continue
            stats = item["stats"]
            lines.append(f"- Rows: {stats['n_rows']}")
            lines.append(f"- Users: {stats['n_users']}")
            lines.append(f"- Distinct day values: {stats['n_distinct_days']} (min {stats['day_min']}, max {stats['day_max']})")
            lines.append(f"- Distinct timeslot values: {stats['n_distinct_timeslots']} (min {stats['timeslot_min']}, max {stats['timeslot_max']})")
            lines.append(f"- x range: {stats['x_min']} to {stats['x_max']}; y range: {stats['y_min']} to {stats['y_max']}")
            lines.append(f"- Null uid/day/timeslot/x/y: {stats['uid_null']}, {stats['day_null']}, {stats['timeslot_null']}, {stats['x_null']}, {stats['y_null']}")
            lines.append(f"- Rows with x=0 or y=0: {stats['zero_xy_rows']}")
            lines.append(f"- Rows outside the 1..200 grid mentioned in the Zenodo challenge text: {stats['outside_1_200']}")
            gaps = item["gaps"]
            lines.append(f"- Unique (user, day, timeslot) keys: {gaps['unique_observed_keys']}")
            lines.append(f"- Duplicate extra rows inside those keys: {item['user_days']['duplicate_slot_rows']}")
            lines.append(f"- User-days with at least one row: {item['user_days']['user_days']}")
            lines.append(f"- Absent timeslots inside those user-days, using the global observed timeslot set: {gaps['absent_slots_within_observed_user_days']}")
            lines.append(f"- Absent combinations of the observed uid, day, and timeslot sets: {gaps['absent_vs_cartesian_of_observed_uid_day_timeslot']}")
            lines.append(f"- Missing day indices inside min..max: {gaps['missing_day_values_inside_min_max']}")
            lines.append(f"- Missing timeslot indices inside min..max: {gaps['missing_timeslot_values_inside_min_max']}")
            lines.append("")
            lines.append("Subsets keep every stored row for the lowest uid values. They are not a dense 75 by 48 grid.")
            lines.append("")
            lines.append("| users requested | users written | rows | day min | day max | columns |")
            lines.append("| ---: | ---: | ---: | ---: | ---: | --- |")
            for label in ("10", "100", "1000"):
                subset = item["subsets"][label]
                lines.append(
                    f"| {label} | {subset['n_users']} | {subset['n_rows']} | {subset['day_min']} | {subset['day_max']} | `{','.join(subset['columns'])}` |"
                )
            lines.append("")
        if yj.get("uid_overlap_first_two_files"):
            overlap = yj["uid_overlap_first_two_files"]
            lines.append(f"Uid overlap between `{overlap.get('left')}` and `{overlap.get('right')}`: {overlap.get('overlapping_uids', overlap.get('error'))}.")
            lines.append("")
        if yj.get("poi_categories"):
            poi = yj["poi_categories"]
            lines.append(f"POI category file `{poi.get('filename')}` nonempty lines: {poi.get('nonempty_lines')}. {poi.get('notes') or poi.get('error')}")
            lines.append("")
        if yj.get("cell_poi"):
            cell = yj["cell_poi"]
            lines.append(f"Cell POI file `{cell.get('filename')}` rows: {cell.get('n_rows')}, columns: {cell.get('column_count')}, header mode: {cell.get('header_mode')}.")
            if cell.get("notes"):
                lines.append(cell["notes"])
            lines.append("")
    geo = summary.get("datasets", {}).get("geolife") or {}
    lines.append("## GeoLife")
    lines.append("")
    if geo.get("status") == "not_downloaded":
        lines.append(f"Not preprocessed: `{geo.get('error')}`")
    elif geo:
        lines.append(f"- Users: {geo.get('users')}")
        lines.append(f"- Trajectory files: {geo.get('trajectories')}")
        lines.append(f"- Raw points after the 6-line header: {geo.get('raw_points')}")
        lines.append(f"- Accepted points: {geo.get('accepted_points')}")
        lines.append(f"- Rejected points: {geo.get('rejected_points')}")
        lines.append(f"- raw == accepted + rejected: {geo.get('balance_raw_equals_accepted_plus_rejected')}")
        lines.append(f"- Rejected reasons: `{geo.get('rejected_reasons')}`")
        lines.append(f"- Accepted distance, haversine sum: {fmt(geo.get('distance_m'))} m ({fmt(geo.get('distance_km'))} km)")
        lines.append(f"- Distinct grid cells 250/500/1000 m: `{geo.get('grid_cell_counts')}` truncated=`{geo.get('grid_cell_count_truncated')}`")
        lines.append(f"- Header lines containing feet: {geo.get('header_feet_files')} files; without feet: {geo.get('header_not_feet_files')}")
        lines.append(f"- Header lines containing WGS: {geo.get('header_wgs_files')} files; without WGS: {geo.get('header_not_wgs_files')}")
        lines.append(f"- Parsed points whose altitude field is -777: {geo.get('altitude_sentinel_neg777')}. The point is kept. This sentinel is counted because the user-guide text, when recovered, describes -777 as an invalid altitude.")
        lines.append(f"- Timestamp timezone label: {geo.get('timestamp_timezone')}")
        if geo.get("timestamp_timezone_evidence"):
            lines.append(f"- Timezone evidence excerpt: `{geo.get('timestamp_timezone_evidence')}`")
        lines.append(f"- `labels.txt` files left unread: {geo.get('label_files')}")
        lines.append(f"- Haversine self-check, 0 m and one degree of latitude: `{geo.get('haversine_self_check')}`")
        lines.append("")
        lines.append("Rules applied:")
        lines.append("")
        for key, value in (geo.get("rules") or {}).items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        if geo.get("first_plt_header"):
            lines.append("First parsed `.plt` header, the six lines that are skipped:")
            lines.append("")
            lines.append("```")
            lines.extend(geo["first_plt_header"])
            lines.append("```")
            lines.append("")
    nc = summary.get("datasets", {}).get("noisecapture") or {}
    lines.append("## NoiseCapture")
    lines.append("")
    if nc.get("status") == "not_downloaded":
        lines.append(f"Not preprocessed: `{nc.get('error')}`")
    elif nc:
        totals = nc.get("totals") or {}
        lines.append(f"- Archives parsed successfully: {nc.get('archives_ok')} of {nc.get('archives_seen')}")
        lines.append(f"- Point features: {totals.get('point_features')}")
        lines.append(f"- Track features: {totals.get('track_features')}")
        lines.append(f"- Area features: {totals.get('area_features')}")
        lines.append(f"- Parse errors: {totals.get('parse_errors')}")
        lines.append(f"- Invalid coordinates excluded from the bbox only: {totals.get('invalid_coordinates')}")
        lines.append(f"- Bbox [min lon, min lat, max lon, max lat]: `{nc.get('bbox')}`")
        lines.append("")
        lines.append(nc.get("indicator_policy") or "")
        lines.append("")
        lines.append("| indicator | count | nulls | zeros | overflow excluded | min | max | energy mean dB | arithmetic mean dB |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for key, bucket in (nc.get("indicators") or {}).items():
            lines.append(
                "| {key} | {count} | {nulls} | {zeros} | {overflow} | {min} | {max} | {energy} | {arith} |".format(
                    key=key,
                    count=bucket.get("count"),
                    nulls=bucket.get("nulls"),
                    zeros=bucket.get("zeros"),
                    overflow=bucket.get("overflow"),
                    min=fmt(bucket.get("min")),
                    max=fmt(bucket.get("max")),
                    energy=fmt(bucket.get("energy_mean_db")),
                    arith=fmt(bucket.get("arithmetic_mean_db")),
                )
            )
        lines.append("")
        weighted = nc.get("track_duration_weighted_noise_level") or {}
        lines.append(
            f"Track `noise_level` duration-weighted energy mean, weights `time_length`: {fmt(weighted.get('energy_mean_db'))} dB "
            f"over {weighted.get('count_weighted')} tracks with positive duration. "
            f"Tracks missing a usable weight: {weighted.get('count_missing_weight')}."
        )
        lines.append("")
        comparison = nc.get("track_vs_points") or {}
        lines.append(
            f"Tracks whose point-level energy mean was compared with the track `noise_level`: {comparison.get('tracks_with_points')}. "
            f"Mean absolute difference: {fmt(comparison.get('mean_abs_diff_db'))} dB. "
            f"Max absolute difference: {fmt(comparison.get('max_abs_diff_db'))} dB."
        )
        lines.append("")
        lines.append(
            f"Area features with both la50 and laeq: {nc.get('area_pairs')}. "
            f"Pairs equal within 1e-6: {nc.get('area_laeq_equals_la50')}."
        )
        lines.append("")
        lines.append("Largest point files:")
        lines.append("")
        lines.append("| archive | member | point features |")
        lines.append("| --- | --- | ---: |")
        for item in nc.get("top_point_members") or []:
            lines.append(f"| {item.get('archive')} | {item.get('member')} | {item.get('point_features')} |")
        lines.append("")
        if nc.get("failures"):
            lines.append("Recorded archive failures:")
            lines.append("")
            for item in nc["failures"]:
                lines.append(f"- `{item.get('filename')}` status `{item.get('status')}` error `{item.get('error')}`")
            lines.append("")
    lines.append("Machine-readable copy: `data/reports/preprocess_summary.json`.")
    lines.append("")
    atomic_write_text(path, "\n".join(lines))


def license_notes(summary: dict) -> str:
    lines = ["## In-archive notes from this preprocess run", ""]
    geo = summary.get("datasets", {}).get("geolife") or {}
    snippets = geo.get("sidecar_snippets") or []
    if not snippets:
        lines.append("GeoLife sidecar scan did not run or found no non-`.plt` members.")
    else:
        lines.append(f"GeoLife non-`.plt` members inspected: {len(snippets)}.")
        for item in snippets:
            lines.append(f"- `{item.get('name')}` bytes {item.get('bytes')}")
            for snippet in item.get("snippets") or []:
                lines.append(f"  - printable-string hit: `{snippet}`")
    lines.append("")
    nc = summary.get("datasets", {}).get("noisecapture") or {}
    hashes = nc.get("readme_hash_counts") or {}
    if hashes:
        lines.append("NoiseCapture `README.html` SHA-256 counts:")
        for digest, count in hashes.items():
            lines.append(f"- `{digest}`: {count} archives")
        defines = [item for item in nc.get("archives") or [] if item.get("status") == "ok"]
        odbl = sum(1 for item in defines if item.get("readme_has_odbl") is True)
        lden = sum(1 for item in defines if item.get("readme_defines_lden") is True)
        lines.append(f"Archives whose README mentions the ODbL: {odbl}. Archives whose README contains the text `lden`: {lden}.")
        lines.append("A README that does not define `lden` is why area `lden` stays separate from `laeq` even when both are numeric.")
    else:
        lines.append("No NoiseCapture README hash was recorded.")
    lines.append("")
    return "\n".join(lines)


def update_license_doc(summary: dict) -> None:
    path = ROOT / "docs" / "data" / "dataset_licenses.md"
    block = license_notes(summary)
    start = "<!-- IN_ARCHIVE_NOTES_START -->"
    end = "<!-- IN_ARCHIVE_NOTES_END -->"
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Dataset licenses\n\n"
    replacement = f"{start}\n{block}{end}"
    if start in existing and end in existing:
        prefix = existing.split(start)[0]
        suffix = existing.split(end, 1)[1]
        text = prefix + replacement + suffix
    else:
        text = existing.rstrip() + "\n\n" + replacement + "\n"
    atomic_write_text(path, text)


def run_preprocess(dataset: str, data_dir: Path, resume: bool, recheck: bool, command: list[str] | None = None) -> dict:
    data_dir = Path(data_dir)
    selected = ("yjmob100k", "geolife", "noisecapture") if dataset == "all" else (dataset,)
    summary = {
        "generated_at": utcnow(),
        "command": command or sys.argv,
        "data_dir": str(data_dir),
        "datasets": {},
    }
    if "yjmob100k" in selected:
        summary["datasets"]["yjmob100k"] = preprocess_yjmob(data_dir, resume, recheck)
    if "geolife" in selected:
        summary["datasets"]["geolife"] = preprocess_geolife(data_dir, resume, recheck)
    if "noisecapture" in selected:
        summary["datasets"]["noisecapture"] = preprocess_noisecapture(data_dir, resume, recheck)
    report_dir = data_dir / "reports"
    atomic_write_json(report_dir / "preprocess_summary.json", summary)
    render_quality(summary, ROOT / "docs" / "data" / "dataset_quality_report.md")
    update_license_doc(summary)
    print(json.dumps({"event": "preprocess_done", "datasets": list(summary["datasets"])}), flush=True)
    return summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess downloaded UrbanNoiseLab datasets.")
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--recheck", action="store_true")
    parser.add_argument("--preprocess", action="store_true", help="Accepted for a consistent CLI. This script always preprocesses.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    run_preprocess(args.dataset, Path(args.data_dir).resolve(), args.resume, args.recheck)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

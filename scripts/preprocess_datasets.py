#!/usr/bin/env python3
"""Turn downloaded archives into gitignored Parquet tables and summary JSON.

Row counts in the summary are whatever this process counted. The script does
not fill missing archives with invented rows.
"""

from __future__ import annotations

import json
import math
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from urbannoise.geo import EARTH_RADIUS_M, grid_indices


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def data_root() -> Path:
    return Path(os.environ.get("UNLAB_DATA_DIR", "data")).resolve()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def preprocess_yjmob(root: Path) -> dict:
    raw = root / "raw" / "yjmob100k"
    out = root / "processed" / "yjmob"
    out.mkdir(parents=True, exist_ok=True)
    reports = {}
    files = {
        "dataset1": raw / "yjmob100k-dataset1.csv.gz",
        "dataset2": raw / "yjmob100k-dataset2.csv.gz",
    }
    for name, path in files.items():
        if not path.exists():
            reports[name] = {"status": "missing", "path": str(path)}
            continue
        dest = out / f"{name}.parquet"
        writer = None
        rows = 0
        try:
            for chunk in pd.read_csv(path, compression="gzip", chunksize=1_000_000):
                renamed = chunk.rename(columns={"uid": "user_id", "d": "day", "t": "timeslot"})
                keep = renamed.loc[:, ["user_id", "day", "timeslot", "x", "y"]].copy()
                keep["user_id"] = keep["user_id"].astype("int64")
                keep["day"] = keep["day"].astype("int16")
                keep["timeslot"] = keep["timeslot"].astype("int16")
                keep["x"] = keep["x"].astype("int16")
                keep["y"] = keep["y"].astype("int16")
                table = pa.Table.from_pandas(keep, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(dest, table.schema)
                writer.write_table(table)
                rows += len(keep)
                print(json.dumps({"dataset": name, "rows_so_far": rows}), flush=True)
        finally:
            if writer is not None:
                writer.close()
        import duckdb

        stats = duckdb.execute(
            """
            SELECT count(*) AS rows,
                   count(DISTINCT user_id) AS users,
                   min(day) AS day_min, max(day) AS day_max,
                   count(DISTINCT day) AS days,
                   min(timeslot) AS slot_min, max(timeslot) AS slot_max,
                   min(x) AS x_min, max(x) AS x_max,
                   min(y) AS y_min, max(y) AS y_max
            FROM read_parquet(?)
            """,
            [str(dest)],
        ).fetchdf().iloc[0].to_dict()
        stats = {key: (int(value) if pd.notna(value) else None) for key, value in stats.items()}
        stats.update(
            {
                "status": "processed",
                "source_bytes": path.stat().st_size,
                "parquet": str(dest),
                "columns": ["user_id", "day", "timeslot", "x", "y"],
                "latitude_assigned": False,
                "coordinate_system": "yjmob_virtual_500m",
                "real_city": False,
            }
        )
        reports[name] = stats
        write_json(out / f"{name}_stats.json", stats)
        print(json.dumps({"done": name, **stats}), flush=True)
    poi = raw / "cell_POIcat.csv.gz"
    categories = raw / "POI_datacategories.csv"
    reports["poi"] = {
        "cell_POIcat_bytes": poi.stat().st_size if poi.exists() else None,
        "categories_bytes": categories.stat().st_size if categories.exists() else None,
        "used_as_noise_truth": False,
        "note": "POI categories are not converted into longitude, latitude, or a noise field.",
    }
    return reports


def _plt_points(text: str):
    lines = text.splitlines()
    for line in lines[6:]:
        parts = [item.strip() for item in line.split(",")]
        if len(parts) < 7:
            continue
        try:
            lat = float(parts[0])
            lon = float(parts[1])
        except ValueError:
            continue
        yield lat, lon, parts[5], parts[6]


def preprocess_geolife(root: Path) -> dict:
    archive = root / "raw" / "geolife" / "Geolife Trajectories 1.3.zip"
    out = root / "processed" / "geolife"
    out.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        report = {"status": "missing", "path": str(archive)}
        write_json(out / "summary.json", report)
        return report
    bins: dict[tuple[str, str, int], list[float]] = {}
    point_rows = 0
    plt_files = 0
    users: set[str] = set()
    lat_min = math.inf
    lat_max = -math.inf
    lon_min = math.inf
    lon_max = -math.inf
    time_min = None
    time_max = None
    with zipfile.ZipFile(archive) as bundle:
        names = [name for name in bundle.namelist() if name.lower().endswith(".plt")]
        plt_files = len(names)
        for index, name in enumerate(names):
            parts = name.split("/")
            user = parts[parts.index("Trajectory") - 1] if "Trajectory" in parts else Path(name).stem
            users.add(user)
            text = bundle.read(name).decode("utf-8", errors="replace")
            for lat, lon, date, clock in _plt_points(text):
                point_rows += 1
                lat_min = min(lat_min, lat)
                lat_max = max(lat_max, lat)
                lon_min = min(lon_min, lon)
                lon_max = max(lon_max, lon)
                stamp = f"{date}T{clock}"
                time_min = stamp if time_min is None or stamp < time_min else time_min
                time_max = stamp if time_max is None or stamp > time_max else time_max
                hour, minute, _second = clock.split(":")
                slot = (int(hour) * 60 + int(minute)) // 30
                key = (user, date, slot)
                acc = bins.get(key)
                if acc is None:
                    bins[key] = [lat, lon, 1.0]
                else:
                    acc[0] += lat
                    acc[1] += lon
                    acc[2] += 1.0
            if index % 2000 == 0:
                print(json.dumps({"geolife_files": index, "points": point_rows, "bins": len(bins)}), flush=True)
    if not bins:
        report = {"status": "empty", "plt_files": plt_files}
        write_json(out / "summary.json", report)
        return report
    lat0 = float(lat_min)
    lon0 = float(lon_min)
    records = []
    dates = sorted({key[1] for key in bins})
    # Episode file keeps the calendar date with the most bins and the next date that exists.
    per_date: dict[str, int] = {}
    for (_user, date, _slot), acc in bins.items():
        per_date[date] = per_date.get(date, 0) + 1
    busiest = max(per_date, key=lambda item: (per_date[item], item))
    later = [date for date in dates if date > busiest]
    second = later[0] if later else None
    episode_dates = {busiest: 0}
    if second:
        episode_dates[second] = 1
    for (user, date, slot), acc in bins.items():
        lat = acc[0] / acc[2]
        lon = acc[1] / acc[2]
        g250x, g250y = grid_indices([lat], [lon], lat0, lon0, 250)
        g500x, g500y = grid_indices([lat], [lon], lat0, lon0, 500)
        g1000x, g1000y = grid_indices([lat], [lon], lat0, lon0, 1000)
        records.append(
            {
                "user_id": user,
                "date": date,
                "day": episode_dates.get(date, -1),
                "timeslot": int(slot),
                "lat": lat,
                "lon": lon,
                "n_points": int(acc[2]),
                "grid250_x": int(g250x[0]),
                "grid250_y": int(g250y[0]),
                "grid500_x": int(g500x[0]),
                "grid500_y": int(g500y[0]),
                "grid1000_x": int(g1000x[0]),
                "grid1000_y": int(g1000y[0]),
            }
        )
    frame = pd.DataFrame.from_records(records)
    all_path = out / "slots_all.parquet"
    frame.to_parquet(all_path, index=False)
    episode = frame[frame["day"] >= 0].copy()
    episode_path = out / "slots.parquet"
    episode.to_parquet(episode_path, index=False)
    report = {
        "status": "processed",
        "plt_files": plt_files,
        "user_folders": len(users),
        "point_rows": point_rows,
        "bin_rows": int(len(frame)),
        "episode_rows": int(len(episode)),
        "episode_users": int(episode["user_id"].nunique()) if len(episode) else 0,
        "episode_dates": {("day0" if day == 0 else "day1"): date for date, day in episode_dates.items()},
        "time_min": time_min,
        "time_max": time_max,
        "bbox": {"lat_min": lat_min, "lat_max": lat_max, "lon_min": lon_min, "lon_max": lon_max},
        "lat0": lat0,
        "lon0": lon0,
        "projection": "equirectangular meters, radius 6371000, origin at minimum latitude/longitude of the parsed points",
        "binning": "mean latitude/longitude of points inside each user, calendar date, and 30-minute slot",
        "parquet": str(episode_path),
        "parquet_all": str(all_path),
        "coordinate_system": "WGS84",
    }
    write_json(out / "summary.json", report)
    print(json.dumps({"geolife_done": True, "points": point_rows, "users": len(users), "episode_rows": int(len(episode))}), flush=True)
    return report


def _iter_point_features(handle):
    for raw in handle:
        line = raw.decode("utf-8", errors="replace").strip().rstrip(",")
        if not line.startswith('{"type":"Feature"'):
            continue
        try:
            feature = json.loads(line)
        except json.JSONDecodeError:
            continue
        yield feature


def _country_from_zip(path: Path) -> str:
    return path.stem


def preprocess_noise(root: Path) -> dict:
    raw = root / "raw" / "noisecapture"
    out = root / "processed" / "noisecapture"
    out.mkdir(parents=True, exist_ok=True)
    if not raw.exists():
        report = {"status": "missing", "path": str(raw)}
        write_json(out / "summary.json", report)
        return report
    zips = sorted(raw.glob("*.zip"), key=lambda item: item.stat().st_size)
    schema = pa.schema(
        [
            ("country", pa.string()),
            ("region", pa.string()),
            ("latitude", pa.float64()),
            ("longitude", pa.float64()),
            ("level_db", pa.float64()),
            ("time_epoch", pa.int64()),
            ("accuracy", pa.float64()),
            ("indicator", pa.string()),
            ("pk_track", pa.int64()),
        ]
    )
    points_path = out / "points_laeq_1s.parquet"
    if points_path.exists():
        points_path.unlink()
    writer = pq.ParquetWriter(points_path, schema)
    countries: dict[str, dict] = {}
    buffer: dict[str, list] = {name: [] for name in schema.names}
    pending = 0

    def flush() -> None:
        nonlocal pending
        if pending == 0:
            return
        writer.write_table(pa.table(buffer, schema=schema))
        for values in buffer.values():
            values.clear()
        pending = 0

    try:
        for archive in zips:
            country = _country_from_zip(archive)
            stats = {
                "point_rows": 0,
                "track_rows": 0,
                "point_files": 0,
                "parse_errors": 0,
                "time_min": None,
                "time_max": None,
                "lat_min": None,
                "lat_max": None,
                "lon_min": None,
                "lon_max": None,
                "indicator": "laeq_1s",
                "zip_bytes": archive.stat().st_size,
            }
            try:
                with zipfile.ZipFile(archive) as bundle:
                    for name in bundle.namelist():
                        if name.endswith(".points.geojson"):
                            stats["point_files"] += 1
                            region = Path(name).name
                            with bundle.open(name) as handle:
                                for feature in _iter_point_features(handle):
                                    geometry = feature.get("geometry") or {}
                                    if geometry.get("type") != "Point":
                                        continue
                                    coords = geometry.get("coordinates") or []
                                    props = feature.get("properties") or {}
                                    if len(coords) < 2 or props.get("noise_level") is None:
                                        stats["parse_errors"] += 1
                                        continue
                                    try:
                                        lon = float(coords[0])
                                        lat = float(coords[1])
                                        level = float(props["noise_level"])
                                        epoch = int(props.get("time_epoch") or 0)
                                    except (TypeError, ValueError):
                                        stats["parse_errors"] += 1
                                        continue
                                    buffer["country"].append(country)
                                    buffer["region"].append(region)
                                    buffer["latitude"].append(lat)
                                    buffer["longitude"].append(lon)
                                    buffer["level_db"].append(level)
                                    buffer["time_epoch"].append(epoch)
                                    accuracy = props.get("accuracy")
                                    buffer["accuracy"].append(float(accuracy) if accuracy is not None else None)
                                    buffer["indicator"].append("laeq_1s")
                                    buffer["pk_track"].append(int(props.get("pk_track") or 0))
                                    pending += 1
                                    stats["point_rows"] += 1
                                    if stats["lat_min"] is None:
                                        stats["lat_min"] = stats["lat_max"] = lat
                                        stats["lon_min"] = stats["lon_max"] = lon
                                    else:
                                        stats["lat_min"] = min(stats["lat_min"], lat)
                                        stats["lat_max"] = max(stats["lat_max"], lat)
                                        stats["lon_min"] = min(stats["lon_min"], lon)
                                        stats["lon_max"] = max(stats["lon_max"], lon)
                                    stamp = str(props.get("time_ISO8601") or "")
                                    if stamp:
                                        stats["time_min"] = stamp if stats["time_min"] is None or stamp < stats["time_min"] else stats["time_min"]
                                        stats["time_max"] = stamp if stats["time_max"] is None or stamp > stats["time_max"] else stats["time_max"]
                                    if pending >= 50_000:
                                        flush()
                        elif name.endswith(".tracks.geojson"):
                            with bundle.open(name) as handle:
                                for feature in _iter_point_features(handle):
                                    props = feature.get("properties") or {}
                                    if props.get("noise_level") is not None:
                                        stats["track_rows"] += 1
            except zipfile.BadZipFile as exc:
                stats["status"] = "failed"
                stats["error"] = f"BadZipFile: {exc}"
                countries[country] = stats
                print(json.dumps({"country": country, "status": "failed", "error": stats["error"]}), flush=True)
                continue
            flush()
            if stats["lat_min"] is not None:
                stats["bbox"] = {
                    "lat_min": stats["lat_min"],
                    "lat_max": stats["lat_max"],
                    "lon_min": stats["lon_min"],
                    "lon_max": stats["lon_max"],
                }
                mean_lat = (stats["lat_min"] + stats["lat_max"]) / 2
                height_m = math.radians(stats["lat_max"] - stats["lat_min"]) * EARTH_RADIUS_M
                width_m = math.radians(stats["lon_max"] - stats["lon_min"]) * EARTH_RADIUS_M * math.cos(math.radians(mean_lat))
                stats["grid_height"] = int(height_m // 500) + 1
                stats["grid_width"] = int(max(width_m, 0) // 500) + 1
            stats["status"] = "processed"
            stats["note"] = "points noise_level stored as laeq_1s (README: LAeq, 1 s). tracks noise_level counted separately as laeq_track and not pooled."
            countries[country] = stats
            print(json.dumps({"country": country, "point_rows": stats["point_rows"], "track_rows": stats["track_rows"]}), flush=True)
    finally:
        writer.close()
    # Hourly 500 m energy means per country, for prediction. Raw 1 s rows stay in the points file.
    hourly_path = out / "hourly_500m.parquet"
    import duckdb

    duckdb.execute(
        f"""
        COPY (
            WITH bounds AS (
                SELECT country, min(latitude) AS lat0, min(longitude) AS lon0
                FROM read_parquet('{points_path.as_posix()}')
                GROUP BY country
            )
            SELECT p.country,
                   'laeq_1s' AS indicator,
                   CAST(floor((radians(p.longitude - b.lon0) * 6371000.0 * cos(radians(b.lat0))) / 500.0) AS INTEGER) AS grid_x,
                   CAST(floor((radians(p.latitude - b.lat0) * 6371000.0) / 500.0) AS INTEGER) AS grid_y,
                   CAST(p.time_epoch / 3600000 AS BIGINT) * 3600000 AS hour_epoch,
                   10 * log10(avg(power(10, p.level_db / 10.0))) AS level_db,
                   count(*) AS n_points,
                   avg(p.latitude) AS latitude,
                   avg(p.longitude) AS longitude
            FROM read_parquet('{points_path.as_posix()}') p
            JOIN bounds b ON p.country = b.country
            WHERE p.indicator = 'laeq_1s' AND isfinite(p.level_db)
            GROUP BY 1, 2, 3, 4, 5
        ) TO '{hourly_path.as_posix()}' (FORMAT PARQUET)
        """
    )
    hourly_rows = int(duckdb.execute(f"SELECT count(*) FROM read_parquet('{hourly_path.as_posix()}')").fetchone()[0])
    # Prefer a dense country for the default prediction target, but only if it was processed.
    prediction_country = None
    for candidate in ("France", "Germany", "United Kingdom", "China", "Japan", "Luxembourg"):
        if countries.get(candidate, {}).get("point_rows", 0) > 0:
            prediction_country = candidate
            break
    report = {
        "status": "processed",
        "generated_at": utcnow(),
        "points_parquet": str(points_path),
        "hourly_parquet": str(hourly_path),
        "hourly_rows": hourly_rows,
        "point_rows": int(sum(item.get("point_rows", 0) for item in countries.values())),
        "track_rows": int(sum(item.get("track_rows", 0) for item in countries.values())),
        "prediction_country": prediction_country,
        "countries": countries,
        "indicator_policy": "laeq_1s from *.points.geojson only. laeq_track from *.tracks.geojson is counted and not pooled.",
    }
    write_json(out / "summary.json", report)
    print(json.dumps({"noise_done": True, "point_rows": report["point_rows"], "hourly_rows": hourly_rows}), flush=True)
    return report


def main() -> int:
    root = data_root()
    summary = {"generated_at": utcnow(), "data_dir": str(root)}
    which = set(sys.argv[1:]) or {"yjmob", "geolife", "noise"}
    if "yjmob" in which:
        summary["yjmob"] = preprocess_yjmob(root)
    if "geolife" in which:
        summary["geolife"] = preprocess_geolife(root)
    if "noise" in which:
        summary["noise"] = {"status": "see processed/noisecapture/summary.json"}
        preprocess_noise(root)
    write_json(root / "manifests" / "preprocess_summary.json", summary)
    print(json.dumps({"preprocess_summary": str(root / "manifests" / "preprocess_summary.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

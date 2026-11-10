"""Dataset adapters.

YJMob100K rows stay on the virtual 500 m grid and never receive fabricated longitude or latitude.
GeoLife rows keep WGS84 coordinates and are not assigned a YJMob grid.
NoiseCapture indicators are preserved by name so different decibel definitions are not silently merged.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from urbannoise.acoustics import DB_MAX, DB_MIN, arithmetic_mean_db, energy_mean_db


class DataFormatError(ValueError):
    pass


def _rename(frame: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for column in frame.columns:
        key = str(column).strip().lower().replace(" ", "_")
        mapping[column] = key
    return frame.rename(columns=mapping)


def read_yjmob_csv(path: str | Path, limit: int | None = None) -> pd.DataFrame:
    frame = pd.read_csv(path, nrows=limit)
    frame = _rename(frame)
    aliases = {
        "user_id": ["user_id", "uid", "userid", "user"],
        "day": ["day", "d"],
        "timeslot": ["timeslot", "time_slot", "t", "slot"],
        "x": ["x"],
        "y": ["y"],
    }
    resolved = {}
    for target, options in aliases.items():
        found = next((item for item in options if item in frame.columns), None)
        if found is None:
            raise DataFormatError(f"YJMob100K file is missing column {target}; columns={list(frame.columns)}")
        resolved[target] = found
    out = pd.DataFrame(
        {
            "participant_id": frame[resolved["user_id"]].astype(str),
            "day": frame[resolved["day"]].astype(int),
            "timeslot": frame[resolved["timeslot"]].astype(int),
            "x": frame[resolved["x"]].astype(int),
            "y": frame[resolved["y"]].astype(int),
        }
    )
    out["grid_id"] = out["y"].astype(str) + ":" + out["x"].astype(str)
    out["latitude"] = np.nan
    out["longitude"] = np.nan
    out["coordinate_system"] = "yjmob_virtual_500m"
    out["data_source"] = "YJMob100K"
    out["participant_type"] = "human"
    out["real_city"] = False
    out["quality_flags"] = "ok"
    bad = ~out["timeslot"].between(0, 47) | ~out["x"].between(1, 200) | ~out["y"].between(1, 200)
    out.loc[bad, "quality_flags"] = "out_of_spec"
    return out


def read_geolife_plt(path: str | Path, participant_id: str | None = None) -> pd.DataFrame:
    raw = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    if len(raw) < 7:
        raise DataFormatError("GeoLife plt file does not contain the 6-line header plus points")
    rows = []
    for line in raw[6:]:
        parts = [item.strip() for item in line.split(",")]
        if len(parts) < 7:
            continue
        try:
            lat, lon = float(parts[0]), float(parts[1])
            altitude = float(parts[3])
        except ValueError:
            continue
        rows.append(
            {
                "participant_id": participant_id or Path(path).stem,
                "latitude": lat,
                "longitude": lon,
                "altitude_feet": altitude,
                "date": parts[5],
                "time": parts[6],
                "timestamp": f"{parts[5]}T{parts[6]}",
                "coordinate_system": "WGS84",
                "data_source": "GeoLife",
                "participant_type": "human",
                "grid_id": None,
                "quality_flags": "ok" if -90 <= lat <= 90 and -180 <= lon <= 180 else "bad_coordinate",
            }
        )
    if not rows:
        raise DataFormatError("GeoLife plt file contains no points")
    return pd.DataFrame(rows)


def _indicator(properties: dict) -> tuple[str, float] | None:
    for key in ("laeq", "leq", "noise_level", "noiselevel", "mean", "value"):
        if key in properties and properties[key] is not None:
            try:
                return key, float(properties[key])
            except (TypeError, ValueError):
                continue
    return None


def read_noisecapture_geojson(path: str | Path) -> pd.DataFrame:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    features = payload.get("features", payload if isinstance(payload, list) else None)
    if not isinstance(features, list):
        raise DataFormatError("NoiseCapture input is not a GeoJSON FeatureCollection")
    rows = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        properties = feature.get("properties") or {}
        if geometry.get("type") != "Point":
            continue
        coords = geometry.get("coordinates") or []
        if len(coords) < 2:
            continue
        found = _indicator(properties)
        if found is None:
            continue
        indicator, level = found
        lon, lat = float(coords[0]), float(coords[1])
        flag = "ok"
        if level < DB_MIN or level > DB_MAX:
            flag = "out_of_range"
        rows.append(
            {
                "longitude": lon,
                "latitude": lat,
                "level_db": level,
                "indicator": indicator,
                "timestamp": properties.get("time") or properties.get("timestamp") or properties.get("date"),
                "coordinate_system": "WGS84",
                "data_source": "NoiseCapture",
                "quality_flags": flag,
                "accuracy_m": properties.get("accuracy"),
            }
        )
    if not rows:
        raise DataFormatError("NoiseCapture file has no point features with a recognized level field")
    return pd.DataFrame(rows)


def deduplicate_trajectories(frame: pd.DataFrame, keys: list[str]) -> tuple[pd.DataFrame, int]:
    before = len(frame)
    ordered = frame.sort_values(keys).drop_duplicates(keys, keep="first")
    return ordered.reset_index(drop=True), before - len(ordered)


def quality_report(frame: pd.DataFrame, kind: str) -> dict:
    report: dict = {
        "kind": kind,
        "rows": int(len(frame)),
        "columns": list(frame.columns),
    }
    if kind == "mobility":
        missing_loc = 0
        if "grid_id" in frame and "latitude" in frame:
            missing_loc = int((frame["grid_id"].isna() & frame["latitude"].isna()).sum()) if "grid_id" in frame else 0
        report["participants"] = int(frame["participant_id"].nunique()) if "participant_id" in frame else 0
        report["missing_location_rows"] = missing_loc
        if "quality_flags" in frame:
            report["flag_counts"] = frame["quality_flags"].value_counts().to_dict()
        if "timestamp" in frame:
            stamps = frame["timestamp"].dropna().astype(str)
            report["time_min"] = stamps.min() if len(stamps) else None
            report["time_max"] = stamps.max() if len(stamps) else None
        if "day" in frame:
            report["day_min"] = int(frame["day"].min())
            report["day_max"] = int(frame["day"].max())
        if "latitude" in frame and frame["latitude"].notna().any():
            report["lat_min"] = float(frame["latitude"].min())
            report["lat_max"] = float(frame["latitude"].max())
            report["lon_min"] = float(frame["longitude"].min())
            report["lon_max"] = float(frame["longitude"].max())
            report["spatial_reference"] = "WGS84 longitude/latitude"
        else:
            report["spatial_reference"] = "virtual grid, no geographic coordinates"
            report["real_city"] = False
    elif kind == "noise":
        levels = frame["level_db"].to_numpy(dtype=float) if "level_db" in frame else np.array([])
        report["indicators"] = sorted(frame["indicator"].dropna().unique().tolist()) if "indicator" in frame else []
        report["energy_mean_db"] = energy_mean_db(levels)
        report["arithmetic_mean_db"] = arithmetic_mean_db(levels)
        report["out_of_range"] = int((frame["quality_flags"] == "out_of_range").sum()) if "quality_flags" in frame else 0
        report["missing_timestamp"] = int(frame["timestamp"].isna().sum()) if "timestamp" in frame else int(len(frame))
        if "latitude" in frame and len(frame):
            report["lat_min"] = float(frame["latitude"].min())
            report["lat_max"] = float(frame["latitude"].max())
            report["lon_min"] = float(frame["longitude"].min())
            report["lon_max"] = float(frame["longitude"].max())
        report["note"] = "Different indicator names are retained. Do not pool laeq with an unspecified 'mean' as if they were the same acoustic index."
    report["missing_rate"] = float(frame.isna().mean().mean()) if len(frame) else 1.0
    return report

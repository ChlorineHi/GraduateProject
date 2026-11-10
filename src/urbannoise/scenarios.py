"""Scenario worlds.

Synthetic keeps the controlled generator. Real-mobility copies recorded cells
into the trajectory array and does not move future points onto tasks. The noise
field in that mode is synthetic and labeled as such. Real-noise and fully-real
are separate and are not drawn on top of the synthetic demo city.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from urbannoise.world import ZONE_NAMES, Agent, World, build_world, generate_agents, generate_noise_field, make_zones


class ScenarioDataError(FileNotFoundError):
    pass


def densest_window(x: np.ndarray, y: np.ndarray, max_side: int) -> tuple[int, int, int, int, str]:
    x = np.asarray(x, dtype=np.int32)
    y = np.asarray(y, dtype=np.int32)
    if x.size == 0:
        raise ScenarioDataError("no coordinates to place a study window")
    x0, x1 = int(x.min()), int(x.max())
    y0, y1 = int(y.min()), int(y.max())
    width = x1 - x0 + 1
    height = y1 - y0 + 1
    if width <= max_side and height <= max_side:
        return x0, y0, x1, y1, "bbox"
    side_x = min(max_side, width)
    side_y = min(max_side, height)
    hist = np.zeros((height, width), dtype=np.int32)
    np.add.at(hist, (y - y0, x - x0), 1)
    integral = np.pad(hist, ((1, 0), (1, 0))).cumsum(axis=0).cumsum(axis=1)
    best_count = -1
    best = (x0, y0, x0 + side_x - 1, y0 + side_y - 1)
    stride = 1 if max(width, height) <= 400 else max(1, max(width, height) // 200)
    for yy in range(0, height - side_y + 1, stride):
        for xx in range(0, width - side_x + 1, stride):
            total = (
                integral[yy + side_y, xx + side_x]
                - integral[yy, xx + side_x]
                - integral[yy + side_y, xx]
                + integral[yy, xx]
            )
            if int(total) > best_count:
                best_count = int(total)
                best = (x0 + xx, y0 + yy, x0 + xx + side_x - 1, y0 + yy + side_y - 1)
    rule = "densest_window" if stride == 1 else f"densest_window_stride_{stride}"
    return best[0], best[1], best[2], best[3], rule


def _timeslot_index(timeslot: pd.Series, slots_per_day: int) -> np.ndarray:
    values = timeslot.to_numpy(dtype=np.int32)
    tmin = int(values.min())
    tmax = int(values.max())
    if 0 <= tmin and tmax < slots_per_day:
        return values
    if 1 <= tmin and tmax <= slots_per_day:
        return values - 1
    raise ScenarioDataError(f"timeslot range {tmin}..{tmax} does not fit {slots_per_day} slots")


def world_from_mobility_frame(
    frame: pd.DataFrame,
    *,
    source: str,
    seed: int,
    scenario: str = "regular",
    slots_per_day: int = 48,
    n_days: int | None = None,
    day_min: int | None = None,
    max_users: int = 10,
    max_side: int = 32,
    min_points: int = 4,
    n_machine: int = 2,
    sensor_sigma: float = 1.5,
    accept_human: float = 0.72,
    accept_machine: float = 0.96,
    cost_human: float = 1.0,
    cost_machine: float = 1.7,
    prior_samples: int = 24,
    dataset_variant: str = "",
    cell_m: int | None = None,
    lat0: float | None = None,
    lon0: float | None = None,
) -> World:
    """Build a world whose human trajectories are copied from `frame`.

    Required columns: user_id, day, timeslot, x, y. Points outside the study
    window stay missing. They are not moved onto a task cell.
    """
    required = {"user_id", "day", "timeslot", "x", "y"}
    missing = required - set(frame.columns)
    if missing:
        raise ScenarioDataError(f"mobility frame missing columns {sorted(missing)}")
    if source not in {"YJMob100K", "GeoLife"}:
        raise ScenarioDataError(f"unsupported mobility source {source}")
    work = frame.loc[:, ["user_id", "day", "timeslot", "x", "y"]].copy()
    work["user_id"] = work["user_id"].astype(str)
    work["day"] = work["day"].astype(int)
    work["x"] = work["x"].astype(int)
    work["y"] = work["y"].astype(int)
    if day_min is None:
        day_min = int(work["day"].min())
    if n_days is None:
        n_days = int(work["day"].max()) - day_min + 1
    day_max = day_min + int(n_days) - 1
    work = work[(work["day"] >= day_min) & (work["day"] <= day_max)]
    if work.empty:
        raise ScenarioDataError(f"no rows in days {day_min}..{day_max}")
    work["slot_in_day"] = _timeslot_index(work["timeslot"], slots_per_day)
    work["slot"] = (work["day"] - day_min) * slots_per_day + work["slot_in_day"]
    wx0, wy0, wx1, wy1, window_rule = densest_window(work["x"].to_numpy(), work["y"].to_numpy(), max_side)
    inside = (work["x"] >= wx0) & (work["x"] <= wx1) & (work["y"] >= wy0) & (work["y"] <= wy1)
    dropped = int((~inside).sum())
    kept = work.loc[inside].sort_values(["user_id", "slot"]).drop_duplicates(["user_id", "slot"], keep="first")
    duplicate_slots = int(len(work.loc[inside]) - len(kept))
    counts = kept.groupby("user_id").size()
    eligible = sorted(user for user, count in counts.items() if int(count) >= min_points)
    if not eligible:
        raise ScenarioDataError("no participant has enough points inside the study window")
    chosen = eligible[: int(max_users)]
    kept = kept[kept["user_id"].isin(chosen)]
    height = wy1 - wy0 + 1
    width = wx1 - wx0 + 1
    n_slots = int(n_days) * slots_per_day
    rng = np.random.default_rng(int(seed))
    zones = make_zones(height, width)
    laeq, energy = generate_noise_field(zones, n_slots, slots_per_day, scenario, rng)
    agents: list[Agent] = []
    for index, user_id in enumerate(chosen):
        traj = np.full(n_slots, -1, dtype=np.int32)
        rows = kept[kept["user_id"] == user_id]
        for slot, gx, gy in zip(rows["slot"].to_numpy(), rows["x"].to_numpy(), rows["y"].to_numpy()):
            if 0 <= int(slot) < n_slots:
                local_x = int(gx) - wx0
                local_y = int(gy) - wy0
                traj[int(slot)] = local_y * width + local_x
        agents.append(
            Agent(
                idx=index,
                name=f"U{index+1:03d}",
                kind="human",
                accept=float(accept_human),
                cost=float(cost_human),
                online=True,
                quality=1.0,
                traj=traj,
            )
        )
    if n_machine:
        machines = generate_agents(
            zones,
            n_slots,
            slots_per_day,
            n_human=0,
            n_machine=int(n_machine),
            rng=rng,
            scenario=scenario,
            missing_rate=0.0,
            accept_human=accept_human,
            accept_machine=accept_machine,
            cost_human=cost_human,
            cost_machine=cost_machine,
            offline_fraction=0.0,
        )
        for offset, machine in enumerate(machines):
            machine.idx = len(agents) + offset
            machine.name = f"M{offset+1:02d}"
            agents.append(machine)
    real_city = source == "GeoLife"
    if source == "YJMob100K":
        coordinate_system = "yjmob_virtual_500m"
        note = "Anonymous virtual 500 m grid copied from YJMob100K. No longitude or latitude is assigned. Not Beijing and not Tokyo."
        label = "Real YJMob mobility + synthetic noise"
    else:
        coordinate_system = "WGS84"
        note = "GeoLife WGS84 points binned onto a local equirectangular grid. Not combined with an unmatched noise archive."
        label = "Real GeoLife mobility + synthetic noise"
    meta = {
        "mode": "real_mobility",
        "label": label,
        "real_city": real_city,
        "named_city": None,
        "mobility_source": source,
        "noise_source": "synthetic_field",
        "dataset_variant": dataset_variant,
        "user_ids": chosen,
        "real_human_count": len(chosen),
        "synthetic_machine_count": int(n_machine),
        "source_rows_in_window": int(len(kept)),
        "rows_dropped_outside_window": dropped,
        "duplicate_slots_removed": duplicate_slots,
        "origin_x": int(wx0),
        "origin_y": int(wy0),
        "window_rule": window_rule,
        "day_min": int(day_min),
        "day_max": int(day_max),
        "cell_m": cell_m,
        "lat0": lat0,
        "lon0": lon0,
        "success_rule": "A task succeeds only when the recorded trajectory cell at that slot equals the assigned cell. Future tracks are not edited.",
        "study_dates": list(frame.attrs.get("study_dates", [])) if hasattr(frame, "attrs") else [],
        "coordinate_note": note,
        "zones_are": "synthetic land-use labels used only to shape the synthetic noise field",
    }
    return World(
        seed=int(seed),
        scenario=scenario,
        height=height,
        width=width,
        slots_per_day=slots_per_day,
        n_days=int(n_days),
        zones=zones,
        laeq=laeq,
        energy=energy,
        agents=agents,
        sensor_sigma=float(sensor_sigma),
        prior_samples=min(int(prior_samples), height * width),
        horizon=(slots_per_day if n_days > 1 else 0, n_slots),
        coordinate_system=coordinate_system,
        data_origin=source,
        meta=meta,
    )


def load_yjmob_frame(parquet_path: str | Path, n_users: int, day_min: int, n_days: int) -> pd.DataFrame:
    path = Path(parquet_path)
    if not path.exists():
        raise ScenarioDataError(f"YJMob parquet not found: {path}")
    import duckdb

    day_max = int(day_min) + int(n_days) - 1
    con = duckdb.connect()
    users = con.execute(
        """
        SELECT user_id FROM (
            SELECT CAST(user_id AS VARCHAR) AS user_id,
                   TRY_CAST(user_id AS BIGINT) AS user_num,
                   count(*) AS c
            FROM read_parquet(?)
            WHERE day BETWEEN ? AND ?
            GROUP BY 1, 2
            HAVING c >= 8
            ORDER BY user_num, user_id
            LIMIT ?
        )
        """,
        [str(path), int(day_min), int(day_max), int(n_users)],
    ).fetchall()
    if not users:
        raise ScenarioDataError(f"no YJMob users in {path} for days {day_min}..{day_max}")
    ids = [row[0] for row in users]
    con.execute("CREATE TEMP TABLE wanted(user_id VARCHAR)")
    con.executemany("INSERT INTO wanted VALUES (?)", [(item,) for item in ids])
    frame = con.execute(
        """
        SELECT CAST(user_id AS VARCHAR) AS user_id, day, timeslot, x, y
        FROM read_parquet(?)
        WHERE day BETWEEN ? AND ?
          AND CAST(user_id AS VARCHAR) IN (SELECT user_id FROM wanted)
        """,
        [str(path), int(day_min), int(day_max)],
    ).df()
    con.close()
    return frame


def load_geolife_frame(parquet_path: str | Path, n_users: int, cell_m: int = 500) -> pd.DataFrame:
    """Load a real GeoLife subset and bin it on a local grid.

    `slots_all.parquet` is preferred when it sits next to the episode file.
    Users are the first ids, in sorted order, that have at least eight bins.
    The two calendar dates with the most bins among those users become day 0
    and day 1. Coordinates are not edited. Bins outside valid WGS84 ranges
    are dropped. Grid indices are recomputed from the selected points so a
    worldwide travel bbox does not become the map origin.
    """
    path = Path(parquet_path)
    all_path = path.with_name("slots_all.parquet")
    use = all_path if all_path.exists() else path
    if not use.exists():
        raise ScenarioDataError(f"GeoLife parquet not found: {path}")
    if cell_m not in (250, 500, 1000):
        raise ScenarioDataError("GeoLife grid must be 250, 500, or 1000 meters")
    frame = pd.read_parquet(use)
    if not {"user_id", "timeslot", "lat", "lon"}.issubset(frame.columns):
        raise ScenarioDataError(f"{use} is missing lat/lon columns needed to rebuild the grid")
    valid = frame["lat"].between(-90, 90) & frame["lon"].between(-180, 180)
    frame = frame.loc[valid].copy()
    if frame.empty:
        raise ScenarioDataError(f"no valid WGS84 bins in {use}")
    frame["user_id"] = frame["user_id"].astype(str)
    counts = frame.groupby("user_id").size()
    eligible = sorted(user for user, count in counts.items() if int(count) >= 8)
    if not eligible:
        raise ScenarioDataError("no GeoLife user has 8 bins inside the valid range")
    chosen = eligible[: int(n_users)]
    subset = frame[frame["user_id"].isin(chosen)].copy()
    date_col = "date" if "date" in subset.columns else None
    if date_col:
        per_date = subset.groupby(date_col).size()
        busiest = str(per_date.idxmax())
        later = sorted(str(item) for item in per_date.index if str(item) > busiest)
        dates = [busiest] + ([later[0]] if later else [])
        subset = subset[subset[date_col].astype(str).isin(dates)].copy()
        subset["day"] = subset[date_col].astype(str).map({item: index for index, item in enumerate(dates)})
        subset.attrs["study_dates"] = dates
    elif "day" not in subset.columns:
        raise ScenarioDataError("GeoLife frame has neither date nor day")
    lat0 = float(subset["lat"].min())
    lon0 = float(subset["lon"].min())
    from urbannoise.geo import grid_indices

    xs, ys = grid_indices(subset["lat"].to_numpy(), subset["lon"].to_numpy(), lat0, lon0, cell_m)
    subset["x"] = np.asarray(xs).astype(int)
    subset["y"] = np.asarray(ys).astype(int)
    out = subset.reset_index(drop=True)
    out.attrs["lat0"] = lat0
    out.attrs["lon0"] = lon0
    out.attrs["source_parquet"] = str(use)
    out.attrs["users_selected"] = chosen
    out.attrs["study_dates"] = list(subset.attrs.get("study_dates", []))
    return out


def synthetic_world(params: dict) -> World:
    return build_world(
        seed=int(params.get("seed", 7)),
        height=int(params.get("height", 16)),
        width=int(params.get("width", 16)),
        n_days=int(params.get("n_days", 2)),
        slots_per_day=int(params.get("slots_per_day", 48)),
        n_human=int(params.get("n_human", 14)),
        n_machine=int(params.get("n_machine", 4)),
        scenario=str(params.get("scenario", "complex")),
        prior_samples=int(params.get("prior_samples", 36)),
        sensor_sigma=float(params.get("sensor_sigma", 1.5)),
        accept_human=float(params.get("accept_human", 0.72)),
        accept_machine=float(params.get("accept_machine", 0.96)),
        missing_rate=float(params.get("missing_rate", 0.04)),
        offline_fraction=float(params.get("offline_fraction", 0.0)),
    )


def resolve_world(params: dict, data_dir: Path | None = None) -> World:
    mode = str(params.get("mode") or "synthetic")
    if mode == "synthetic":
        world = synthetic_world(params)
        world.meta["mode"] = "synthetic"
        world.meta["mobility_source"] = "synthetic"
        world.meta["noise_source"] = "synthetic_field"
        world.meta["real_human_count"] = int(params.get("n_human", 0))
        return world
    root = Path(data_dir or params.get("data_dir") or "data")
    if mode == "real_mobility":
        source = str(params.get("mobility_source") or "yjmob_dataset1")
        if source in {"yjmob_dataset1", "yjmob_dataset2", "YJMob100K"}:
            variant = "dataset2" if "dataset2" in source else "dataset1"
            parquet = root / "processed" / "yjmob" / f"{variant}.parquet"
            day_min = int(params.get("day_min", 0))
            n_days = int(params.get("n_days", 2))
            requested = int(params.get("n_users", params.get("n_human", 10)))
            # Scan a larger id-ordered pool, then keep up to `requested` people inside the study window.
            candidates = int(params.get("candidate_users") or max(requested, 400))
            frame = load_yjmob_frame(parquet, candidates, day_min, n_days)
            return world_from_mobility_frame(
                frame,
                source="YJMob100K",
                seed=int(params.get("seed", 7)),
                scenario=str(params.get("scenario", "regular")),
                slots_per_day=int(params.get("slots_per_day", 48)),
                n_days=n_days,
                day_min=day_min,
                max_users=requested,
                max_side=int(params.get("max_side", 32)),
                n_machine=int(params.get("n_machine", 2)),
                sensor_sigma=float(params.get("sensor_sigma", 1.5)),
                accept_human=float(params.get("accept_human", 0.72)),
                dataset_variant=variant,
                cell_m=500,
            )
        if source in {"geolife", "GeoLife"}:
            cell_m = int(params.get("grid_m", 500))
            frame = load_geolife_frame(root / "processed" / "geolife" / "slots.parquet", int(params.get("n_users", 10)), cell_m)
            lat0 = frame.attrs.get("lat0", params.get("lat0"))
            lon0 = frame.attrs.get("lon0", params.get("lon0"))
            n_days = int(frame["day"].nunique()) if len(frame) else int(params.get("n_days", 2))
            return world_from_mobility_frame(
                frame,
                source="GeoLife",
                seed=int(params.get("seed", 7)),
                scenario=str(params.get("scenario", "regular")),
                slots_per_day=int(params.get("slots_per_day", 48)),
                n_days=n_days,
                day_min=int(frame["day"].min()) if len(frame) else 0,
                max_users=int(params.get("n_users", 10)),
                max_side=int(params.get("max_side", 32)),
                n_machine=int(params.get("n_machine", 2)),
                sensor_sigma=float(params.get("sensor_sigma", 1.5)),
                accept_human=float(params.get("accept_human", 0.72)),
                dataset_variant=f"grid_{cell_m}m",
                cell_m=cell_m,
                lat0=float(lat0) if lat0 is not None else None,
                lon0=float(lon0) if lon0 is not None else None,
            )
        raise ScenarioDataError(f"unknown mobility source {source}")
    if mode == "real_noise":
        world, _frame = prepare_real_noise(root, params.get("noise_country") or None, int(params.get("max_side", 24)))
        return world
    if mode == "fully_real":
        return fully_real_world(params, root)
    raise ScenarioDataError(f"unknown scenario mode {mode}")


def prepare_real_noise(root: Path, country: str | None = None, max_side: int = 24) -> tuple[World, pd.DataFrame]:
    """Load one country's hourly bins and a study window. Truth stays unknown."""
    import json

    import duckdb

    summary_path = root / "processed" / "noisecapture" / "summary.json"
    hourly = root / "processed" / "noisecapture" / "hourly_500m.parquet"
    if not summary_path.exists() or not hourly.exists():
        raise ScenarioDataError(f"NoiseCapture processed files missing under {root / 'processed' / 'noisecapture'}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    chosen = country or summary.get("prediction_country")
    countries = summary.get("countries") or {}
    if not chosen or chosen not in countries:
        raise ScenarioDataError(f"NoiseCapture country {chosen!r} is not in the processed summary")
    cells = duckdb.execute(
        """
        SELECT grid_x, grid_y, sum(n_points) AS n_points
        FROM read_parquet(?)
        WHERE country = ? AND indicator = 'laeq_1s'
        GROUP BY 1, 2
        """,
        [str(hourly), chosen],
    ).df()
    if cells.empty:
        raise ScenarioDataError(f"no laeq_1s hourly bins for {chosen}")
    # Weight the histogram by repeating is unnecessary: densest_window counts rows.
    # Expand is too heavy, so jitter is avoided by passing one row per cell and
    # then re-ranking the window by the stored n_points after a geometric search.
    wx0, wy0, wx1, wy1, rule = densest_window(cells["grid_x"].to_numpy(), cells["grid_y"].to_numpy(), max_side)
    frame = duckdb.execute(
        """
        SELECT grid_x, grid_y, level_db, hour_epoch, latitude, longitude, indicator, n_points
        FROM read_parquet(?)
        WHERE country = ? AND indicator = 'laeq_1s'
          AND grid_x BETWEEN ? AND ? AND grid_y BETWEEN ? AND ?
        """,
        [str(hourly), chosen, int(wx0), int(wx1), int(wy0), int(wy1)],
    ).df()
    inside = frame.copy()
    hours = sorted(int(value) for value in inside["hour_epoch"].unique())[:24]
    inside = inside[inside["hour_epoch"].isin(hours)].copy()
    hour_to_slot = {hour: index for index, hour in enumerate(hours)}
    inside["slot"] = inside["hour_epoch"].map(lambda value: hour_to_slot[int(value)])
    inside["x"] = inside["grid_x"].astype(int) - wx0
    inside["y"] = inside["grid_y"].astype(int) - wy0
    height = wy1 - wy0 + 1
    width = wx1 - wx0 + 1
    slots = max(len(hours), 1)
    zones = np.zeros((height, width), dtype=np.int8)
    laeq = np.full((slots, height, width), np.nan, dtype=np.float64)
    info = countries[chosen]
    world = World(
        seed=0,
        scenario="real_noise",
        height=height,
        width=width,
        slots_per_day=slots,
        n_days=1,
        zones=zones,
        laeq=laeq,
        energy=np.full_like(laeq, np.nan),
        agents=[],
        sensor_sigma=float("nan"),
        prior_samples=0,
        horizon=(0, slots),
        coordinate_system="WGS84",
        data_origin="NoiseCapture",
        meta={
            "mode": "real_noise",
            "label": f"NoiseCapture {chosen} 手机测量",
            "real_city": True,
            "named_city": None,
            "mobility_source": "none",
            "noise_source": "NoiseCapture",
            "noise_country": chosen,
            "indicator": "laeq_1s",
            "real_human_count": 0,
            "synthetic_machine_count": 0,
            "point_rows": info.get("point_rows"),
            "hourly_rows_in_window": int(len(inside)),
            "window_rule": rule,
            "origin_x": int(wx0),
            "origin_y": int(wy0),
            "coordinate_note": "WGS84 phone measurements. Not a complete noise field and not overlaid on YJMob or an unmatched mobility trace.",
            "truth_available": False,
        },
    )
    return world, inside


def fully_real_world(params: dict, root: Path) -> World:
    report = overlap_report(root)
    if not report.get("feasible"):
        raise ScenarioDataError(
            "Fully-real mode is refused: " + str(report.get("reason"))
        )
    raise ScenarioDataError("Fully-real overlap exists in the report but no joint episode was constructed.")


def overlap_report(root: Path) -> dict:
    import json

    geo_path = root / "processed" / "geolife" / "summary.json"
    noise_path = root / "processed" / "noisecapture" / "summary.json"
    if not geo_path.exists() or not noise_path.exists():
        return {
            "feasible": False,
            "reason": f"missing summary geo={geo_path.exists()} noise={noise_path.exists()}",
        }
    geo = json.loads(geo_path.read_text(encoding="utf-8"))
    noise = json.loads(noise_path.read_text(encoding="utf-8"))
    g0, g1 = geo.get("time_min"), geo.get("time_max")
    reason = "no NoiseCapture country intersects the GeoLife time range and bounding box"
    feasible = False
    matches = []
    for country, info in (noise.get("countries") or {}).items():
        n0, n1 = info.get("time_min"), info.get("time_max")
        time_ok = bool(g0 and g1 and n0 and n1 and not (g1 < n0 or n1 < g0))
        space_ok = _bbox_overlap(geo.get("bbox"), info.get("bbox"))
        matches.append({"country": country, "time_overlap": time_ok, "space_overlap": space_ok, "time_min": n0, "time_max": n1})
        if time_ok and space_ok:
            feasible = True
            reason = f"{country} overlaps GeoLife in time and bounding box"
    bbox = geo.get("bbox") or {}
    try:
        span_lat = float(bbox.get("lat_max", 0)) - float(bbox.get("lat_min", 0))
        span_lon = float(bbox.get("lon_max", 0)) - float(bbox.get("lon_min", 0))
        invalid_lat = float(bbox.get("lat_max", 0)) > 90 or float(bbox.get("lat_min", 0)) < -90
    except (TypeError, ValueError):
        span_lat, span_lon, invalid_lat = 0.0, 0.0, False
    if feasible and (invalid_lat or span_lat > 20 or span_lon > 20):
        feasible = False
        reason = (
            "A country bounding box meets the raw GeoLife bbox, but that bbox is wider than 20 degrees "
            "or contains a latitude outside [-90, 90]. That intersection is not a joint city experiment, "
            "and no point-level episode was built."
        )
    return {
        "feasible": feasible,
        "reason": reason,
        "geolife_time": [g0, g1],
        "geolife_bbox": geo.get("bbox"),
        "countries": matches,
    }


def _bbox_overlap(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    try:
        return not (
            a["lon_max"] < b["lon_min"]
            or b["lon_max"] < a["lon_min"]
            or a["lat_max"] < b["lat_min"]
            or b["lat_max"] < a["lat_min"]
        )
    except KeyError:
        return False


# Re-exported for callers that want the zone names next to a scenario world.
__all__ = ["ZONE_NAMES", "resolve_world", "world_from_mobility_frame", "overlap_report"]

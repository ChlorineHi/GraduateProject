"""Holdout prediction on NoiseCapture measurements.

Phone samples are not a continuous city field. Metrics are computed only on
held-out measurements of one indicator. Track-level Laeq is never pooled with
1-second LAeq.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from urbannoise.acoustics import energy_mean_db
from urbannoise.geo import local_xy_m
from urbannoise.predictors import predict_idw, prediction_metrics


def holdout_predict(
    frame: pd.DataFrame,
    indicator: str = "laeq_1s",
    seed: int = 0,
    max_train: int = 4000,
    max_test: int = 1500,
) -> dict:
    if "indicator" not in frame.columns or "level_db" not in frame.columns:
        raise ValueError("noise frame needs indicator and level_db")
    work = frame.loc[frame["indicator"] == indicator].dropna(subset=["level_db", "latitude", "longitude"])
    if "time_epoch" in work.columns:
        work = work.sort_values("time_epoch")
    n_input = int(len(work))
    if n_input < 40:
        raise ValueError(f"need at least 40 {indicator} rows, found {n_input}")
    cut = int(n_input * 0.7)
    cut = min(max(cut, 20), n_input - 10)
    train = work.iloc[:cut]
    test = work.iloc[cut:]
    rng = np.random.default_rng(seed)
    if len(train) > max_train:
        take = np.sort(rng.choice(len(train), size=max_train, replace=False))
        train = train.iloc[take]
    if len(test) > max_test:
        take = np.sort(rng.choice(len(test), size=max_test, replace=False))
        test = test.iloc[take]
    lat0 = float(work["latitude"].min())
    lon0 = float(work["longitude"].min())
    train_x, train_y = local_xy_m(train["latitude"], train["longitude"], lat0, lon0)
    test_x, test_y = local_xy_m(test["latitude"], test["longitude"], lat0, lon0)
    # IDW in this codebase uses cell-sized coordinates. Scale meters to 500 m cells
    # so the existing distance weights stay in the range they were written for.
    obs = {
        "x": np.asarray(train_x) / 500.0,
        "y": np.asarray(train_y) / 500.0,
        "db": train["level_db"].to_numpy(dtype=np.float64),
        "slot": np.zeros(len(train), dtype=np.int32),
        "grid": np.zeros(len(train), dtype=np.int32),
    }
    queries = np.column_stack([np.asarray(test_x) / 500.0, np.asarray(test_y) / 500.0])
    mu, std = predict_idw(obs, queries, 0)
    metrics = prediction_metrics(test["level_db"].to_numpy(dtype=np.float64), mu)
    return {
        "indicator": indicator,
        "protocol": "time_holdout_last_30_percent",
        "n_input_rows": n_input,
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "mae": metrics["mae"],
        "rmse": metrics["rmse"],
        "r2": metrics["r2"],
        "energy_mean_train_db": energy_mean_db(train["level_db"].to_numpy(dtype=np.float64)),
        "mean_predictive_std": float(np.mean(std)),
        "note": "Held-out phone measurements of one indicator. This is not a full-city field MAE.",
        "source": "noisecapture_frame",
    }


def predict_parquet(path: str | Path, indicator: str = "laeq_1s", country: str | None = None, seed: int = 0) -> dict:
    """Time holdout inside SQL so a national archive is not loaded as one table.

    Train rows are a deterministic sample of the earlier 70 percent of hours.
    Test rows are a deterministic sample of the later 30 percent. The metric is
    therefore on that sample, not on a continuous city field.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"noise parquet not found: {file_path}")
    import duckdb

    con = duckdb.connect()
    country_clause = "AND country = ?" if country else ""
    count_params: list = [str(file_path), indicator]
    if country:
        count_params.append(country)
    n_input = int(
        con.execute(
            f"SELECT count(*) FROM read_parquet(?) WHERE indicator = ? {country_clause}",
            count_params,
        ).fetchone()[0]
    )
    if n_input < 40:
        con.close()
        raise ValueError(f"need at least 40 {indicator} rows, found {n_input}")
    time_col = "hour_epoch" if "hour" in file_path.name else "time_epoch"
    params = list(count_params)
    frame = con.execute(
        f"""
        WITH base AS (
            SELECT latitude, longitude, level_db, {time_col} AS time_epoch, indicator, country
            FROM read_parquet(?)
            WHERE indicator = ? {country_clause}
        ),
        cut AS (
            SELECT quantile_cont(time_epoch, 0.7) AS boundary FROM base
        )
        SELECT * FROM (
            SELECT latitude, longitude, level_db, time_epoch, indicator, country, 'train' AS split
            FROM base, cut
            WHERE time_epoch < boundary
            ORDER BY time_epoch
            LIMIT 4000
        )
        UNION ALL
        SELECT * FROM (
            SELECT latitude, longitude, level_db, time_epoch, indicator, country, 'test' AS split
            FROM base, cut
            WHERE time_epoch >= boundary
            ORDER BY time_epoch
            LIMIT 1500
        )
        """,
        params,
    ).df()
    con.close()
    train = frame[frame["split"] == "train"]
    test = frame[frame["split"] == "test"]
    if len(train) < 20 or len(test) < 10:
        raise ValueError(f"holdout split too small: train={len(train)} test={len(test)}")
    lat0 = float(frame["latitude"].min())
    lon0 = float(frame["longitude"].min())
    train_x, train_y = local_xy_m(train["latitude"], train["longitude"], lat0, lon0)
    test_x, test_y = local_xy_m(test["latitude"], test["longitude"], lat0, lon0)
    obs = {
        "x": np.asarray(train_x) / 500.0,
        "y": np.asarray(train_y) / 500.0,
        "db": train["level_db"].to_numpy(dtype=np.float64),
        "slot": np.zeros(len(train), dtype=np.int32),
        "grid": np.zeros(len(train), dtype=np.int32),
    }
    queries = np.column_stack([np.asarray(test_x) / 500.0, np.asarray(test_y) / 500.0])
    mu, _std = predict_idw(obs, queries, 0)
    metrics = prediction_metrics(test["level_db"].to_numpy(dtype=np.float64), mu)
    return {
        "indicator": indicator,
        "protocol": "time_holdout_quantile_0.7_sql_sample",
        "n_input_rows": n_input,
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "mae": metrics["mae"],
        "rmse": metrics["rmse"],
        "r2": metrics["r2"],
        "source": str(file_path),
        "country": country,
        "parquet_rows_read": int(len(frame)),
        "note": "Held-out phone measurements of one indicator, sampled in SQL. This is not a full-city field MAE.",
    }

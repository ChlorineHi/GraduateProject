"""Decibel and relative sound-energy conversions.

Energy values are proportional to 10^(L/10) with a reference of 1 (0 dB).
Uncorrelated sources are combined by summing energy, then converting back to level.
An arithmetic mean of decibel readings is reported separately and is not treated as a sound level.
"""

from __future__ import annotations

import numpy as np

DB_MIN = 20.0
DB_MAX = 130.0
LN10 = float(np.log(10.0))


def db_to_energy(level_db: np.ndarray | float) -> np.ndarray | float:
    return np.power(10.0, np.asarray(level_db, dtype=np.float64) / 10.0)


def energy_to_db(energy: np.ndarray | float) -> np.ndarray | float:
    arr = np.maximum(np.asarray(energy, dtype=np.float64), 1e-12)
    return 10.0 * np.log10(arr)


def energy_mean_db(levels_db: np.ndarray) -> float:
    """Energy-equivalent mean level. Appropriate for averaging uncorrelated exposure."""
    values = np.asarray(levels_db, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    return float(energy_to_db(np.mean(db_to_energy(values))))


def arithmetic_mean_db(levels_db: np.ndarray) -> float:
    """Arithmetic mean of decibel numbers. Not a physical equivalent level."""
    values = np.asarray(levels_db, dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    return float(np.mean(values))


def delta_method_std_db(energy: np.ndarray, energy_var: np.ndarray) -> np.ndarray:
    """Approximate std of L = 10 log10(E) from Var(E)."""
    energy = np.maximum(np.asarray(energy, dtype=np.float64), 1e-12)
    var = np.maximum(np.asarray(energy_var, dtype=np.float64), 0.0)
    return (10.0 / LN10) * np.sqrt(var) / energy


def validate_distribution(probabilities: np.ndarray, tol: float = 1e-5) -> np.ndarray:
    """Reject illegal categorical distributions. Predictors must call this before returning."""
    probs = np.asarray(probabilities, dtype=np.float64)
    if probs.ndim != 1 or probs.size == 0:
        raise ValueError("probability vector must be one-dimensional and non-empty")
    if not np.all(np.isfinite(probs)):
        raise ValueError("probability vector contains non-finite values")
    if np.any(probs < -tol):
        raise ValueError("probability vector contains negative values")
    total = float(probs.sum())
    if abs(total - 1.0) > tol:
        raise ValueError(f"probabilities must sum to 1, got {total}")
    return probs


def clip_measurement(level_db: float) -> tuple[float, str]:
    """Return the stored level and a quality flag. Values outside the physical gate are kept but flagged."""
    if not np.isfinite(level_db):
        raise ValueError("measurement is not finite")
    if level_db < DB_MIN or level_db > DB_MAX:
        return float(level_db), "out_of_range"
    return float(level_db), "ok"

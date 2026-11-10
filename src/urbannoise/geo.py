"""Distances and local grids for real GPS.

Equirectangular meters use the WGS84 spherical radius 6371000 m. This is a
real projection, not a fabricated city coordinate. YJMob virtual cells are
never passed through these functions.
"""

from __future__ import annotations

import math

import numpy as np

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = map(lambda value: np.radians(np.asarray(value, dtype=np.float64)), (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(a)))


def local_xy_m(lat, lon, lat0: float, lon0: float) -> tuple[np.ndarray, np.ndarray]:
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    dy = np.radians(lat - lat0) * EARTH_RADIUS_M
    dx = np.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    return dx, dy


def grid_indices(lat, lon, lat0: float, lon0: float, cell_m: float) -> tuple[np.ndarray, np.ndarray]:
    if cell_m not in (250, 500, 1000) and cell_m <= 0:
        raise ValueError(f"cell size must be positive meters, got {cell_m}")
    dx, dy = local_xy_m(lat, lon, lat0, lon0)
    return np.floor(dx / cell_m).astype(np.int32), np.floor(dy / cell_m).astype(np.int32)


def cell_center(x: int, y: int, lat0: float, lon0: float, cell_m: float) -> tuple[float, float]:
    north = (y + 0.5) * cell_m
    east = (x + 0.5) * cell_m
    lat = lat0 + (north / EARTH_RADIUS_M) * (180.0 / math.pi)
    lon = lon0 + (east / (EARTH_RADIUS_M * math.cos(math.radians(lat0)))) * (180.0 / math.pi)
    return float(lat), float(lon)

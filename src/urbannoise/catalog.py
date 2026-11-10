"""Read-only data regimes and on-disk catalogs.

Counts are copied from a file only when that file actually contains them.
"""

from __future__ import annotations

import json
from pathlib import Path

SCENARIO_MODES = (
    "synthetic_demo",
    "real_mobility",
    "real_noise",
    "mixed_experiment",
    "fully_real",
)

SCENARIO_MODE_LABELS = {
    "synthetic_demo": "Synthetic Demo",
    "real_mobility": "Real Mobility",
    "real_noise": "Real Noise",
    "mixed_experiment": "Mixed Experiment",
    "fully_real": "Fully Real",
}

EXECUTABLE_SCENARIO_MODES = frozenset({"synthetic_demo"})

MANIFEST_PUBLIC_PATH = "data/manifests/download_manifest.json"
PHASE2_PUBLIC_PATH = "experiments/results/phase2"

_REGIME_ALIASES = {
    "synthetic_demo": "synthetic_demo",
    "synthetic": "synthetic_demo",
    "demo": "synthetic_demo",
    "real_mobility": "real_mobility",
    "real_noise": "real_noise",
    "mixed_experiment": "mixed_experiment",
    "mixed": "mixed_experiment",
    "fully_real": "fully_real",
    "full_real": "fully_real",
}

_FIELD_ALIASES = {
    "id": ("id", "key"),
    "name": ("name", "dataset", "title", "id"),
    "kind": ("kind", "type"),
    "regime": ("regime", "data_regime", "scenario_mode"),
    "download_status": ("download_status", "download"),
    "preprocess_status": ("preprocess_status", "preprocess", "preprocessing_status"),
    "license": ("license", "licence"),
    "user_count": ("user_count", "users", "n_users", "participant_count"),
    "station_count": ("station_count", "stations", "n_stations", "sensor_count"),
    "time_start": ("time_start", "start_time"),
    "time_end": ("time_end", "end_time"),
    "time_span": ("time_span",),
    "spatial_span": ("spatial_span", "spatial", "spatial_desc", "bbox"),
    "quality_flags": ("quality_flags", "quality", "flags"),
}


def dataset_regime(is_synthetic: bool, source: str, kind: str) -> tuple[str, str]:
    """A stored table is never promoted to a joint real experiment by itself."""
    if is_synthetic or source == "synthetic_demo":
        regime = "synthetic_demo"
    elif kind == "mobility":
        regime = "real_mobility"
    else:
        regime = "real_noise"
    return regime, SCENARIO_MODE_LABELS[regime]


def annotate_scenario_mode(payload: dict, requested: str | None) -> dict:
    """The runnable world is synthetic. A requested real mode stays a request."""
    actual = "synthetic_demo"
    label = SCENARIO_MODE_LABELS[actual]
    payload["scenario_mode"] = actual
    payload["mode_label"] = label
    payload["data_origin"] = "synthetic_demo"
    payload["real_city"] = False
    payload["real_run"] = False
    if requested and requested != actual:
        payload["requested_scenario_mode"] = requested
        payload["mode_honored"] = False
        payload["mode_note"] = (
            f"请求的数据模式是 {SCENARIO_MODE_LABELS.get(requested, requested)}。"
            f"服务器实际执行的是 {label}，这次运行不会被记成真实数据。"
        )
    else:
        payload["requested_scenario_mode"] = actual
        payload["mode_honored"] = True
        payload["mode_note"] = f"服务器实际模式是 {label}。"
    return payload


def read_download_manifest(path: Path, view: str) -> dict:
    if view not in {"download", "preprocess"}:
        raise ValueError(f"unknown manifest view: {view}")
    base = {
        "present": False,
        "path": MANIFEST_PUBLIC_PATH,
        "view": view,
        "items": [],
        "parse_error": False,
    }
    if not path.is_file():
        base["message"] = f"未找到 {MANIFEST_PUBLIC_PATH}，没有下载或预处理记录。"
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        base["present"] = True
        base["parse_error"] = True
        base["message"] = f"{MANIFEST_PUBLIC_PATH} 存在，但不是合法 JSON，因此没有可展示的计数。"
        return base
    items = [_project_manifest_row(row) for row in _manifest_rows(raw, view)]
    base["present"] = True
    base["items"] = items
    base["message"] = None if items else "清单里没有数据集条目。"
    return base


def read_phase2(root: Path) -> dict:
    payload = {
        "present": False,
        "path": PHASE2_PUBLIC_PATH,
        "files": [],
        "message": f"未找到 {PHASE2_PUBLIC_PATH}，没有第二阶段结果。",
    }
    if not root.exists():
        return payload
    if not root.is_dir():
        payload["message"] = f"{PHASE2_PUBLIC_PATH} 不是目录，没有可读取的结果。"
        return payload
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and item.suffix.lower() == ".json"):
        relative = path.relative_to(root).as_posix()
        if path.stat().st_size > 512_000:
            files.append({"name": relative, "skipped": True, "bytes": path.stat().st_size})
            continue
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            files.append({"name": relative, "parse_error": True})
            continue
        files.append({"name": relative, "payload": parsed})
    payload["present"] = True
    payload["files"] = files
    payload["message"] = None if files else f"{PHASE2_PUBLIC_PATH} 存在，但里面没有结果 JSON。"
    return payload


def _manifest_rows(raw: object, view: str) -> list[dict]:
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if not isinstance(raw, dict):
        return []
    preferred = ("downloads", "download") if view == "download" else ("preprocess", "preprocessing")
    for key in preferred:
        rows = raw.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    for key in ("items", "datasets", "sources"):
        rows = raw.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _project_manifest_row(row: dict) -> dict:
    projected: dict = {}
    for dest, keys in _FIELD_ALIASES.items():
        for key in keys:
            if key in row:
                value = row[key]
                if dest == "regime" and isinstance(value, str):
                    value = _REGIME_ALIASES.get(value.strip(), value)
                projected[dest] = value
                break
    return projected

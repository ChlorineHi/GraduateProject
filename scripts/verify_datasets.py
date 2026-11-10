#!/usr/bin/env python3
"""Check download manifests and preprocess summaries against files on disk.

Examples
--------
python scripts/verify_datasets.py --dataset all --data-dir data --recheck
python scripts/verify_datasets.py --dataset yjmob100k --data-dir data --resume
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

DATASETS = ("all", "yjmob100k", "geolife", "noisecapture")
ROOT = Path(__file__).resolve().parents[1]
CHUNK = 1024 * 1024


def check(results: list[dict], name: str, ok: bool, detail: str) -> None:
    results.append({"check": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}", flush=True)


def hash_file(path: Path) -> dict:
    md5 = hashlib.md5()
    sha = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            md5.update(block)
            sha.update(block)
            size += len(block)
    return {"bytes": size, "md5": md5.hexdigest(), "sha256": sha.hexdigest()}


def verify(dataset: str, data_dir: Path, recheck: bool) -> dict:
    results: list[dict] = []
    manifest_path = data_dir / "manifests" / "download_manifest.json"
    check(results, "manifest_exists", manifest_path.exists(), str(manifest_path))
    if not manifest_path.exists():
        return {"ok": False, "checks": results}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = {"yjmob100k", "geolife", "noisecapture"} if dataset == "all" else {dataset}
    files = [item for item in manifest.get("files", []) if item.get("dataset") in selected]
    ok_status = {"downloaded", "skipped_existing", "skipped_duplicate"}
    for entry in files:
        name = f"{entry.get('dataset')}:{entry.get('filename')}"
        status = entry.get("status")
        if status not in ok_status:
            check(results, f"recorded_non_success:{name}", bool(entry.get("error")), entry.get("error") or "missing error text")
            continue
        path = Path(entry.get("path") or "")
        exists = path.exists()
        check(results, f"exists:{name}", exists, str(path))
        if not exists:
            continue
        size_ok = path.stat().st_size == entry.get("bytes")
        check(results, f"size:{name}", size_ok, f"disk={path.stat().st_size} manifest={entry.get('bytes')}")
        official = entry.get("official_checksum") or {}
        if official.get("algorithm") == "md5":
            check(results, f"official_md5_flag:{name}", official.get("match") is True, str(official))
        if recheck:
            hashed = hash_file(path)
            recorded_sha = ((entry.get("hashes") or {}).get("sha256") or {}).get("value")
            recorded_md5 = ((entry.get("hashes") or {}).get("md5") or {}).get("value")
            check(results, f"sha256:{name}", hashed["sha256"] == recorded_sha, hashed["sha256"])
            check(results, f"md5:{name}", hashed["md5"] == recorded_md5, hashed["md5"])
            if official.get("algorithm") == "md5":
                check(results, f"official_md5_bytes:{name}", hashed["md5"] == official.get("value"), hashed["md5"])
    summary_path = data_dir / "reports" / "preprocess_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else None
    check(results, "preprocess_summary", summary is not None, str(summary_path))
    if summary is None:
        payload = {"ok": False, "checks": results}
        write_report(data_dir, payload)
        return payload
    if "yjmob100k" in selected:
        verify_yjmob(results, summary.get("datasets", {}).get("yjmob100k") or {}, data_dir)
    if "geolife" in selected:
        verify_geolife(results, summary.get("datasets", {}).get("geolife") or {})
    if "noisecapture" in selected:
        verify_noise(results, summary.get("datasets", {}).get("noisecapture") or {})
    quality = ROOT / "docs" / "data" / "dataset_quality_report.md"
    check(results, "quality_report", quality.exists(), str(quality))
    if quality.exists() and summary:
        text = quality.read_text(encoding="utf-8")
        for item in (summary.get("datasets", {}).get("yjmob100k") or {}).get("files") or []:
            if item.get("status") == "ok":
                needle = f"Rows: {item['stats']['n_rows']}"
                check(results, f"quality_mentions:{item.get('filename')}", needle in text, needle)
    failed = [item for item in results if not item["ok"]]
    payload = {"ok": not failed, "failed": len(failed), "checks": results}
    write_report(data_dir, payload)
    print(json.dumps({"event": "verify", "ok": payload["ok"], "failed": payload["failed"]}), flush=True)
    return payload


def verify_yjmob(results: list[dict], summary: dict, data_dir: Path) -> None:
    if summary.get("status") == "not_downloaded":
        check(results, "yjmob_present", False, summary.get("error") or "not downloaded")
        return
    for item in summary.get("files") or []:
        if item.get("status") != "ok":
            check(results, f"yjmob_file:{item.get('filename')}", False, item.get("error") or item.get("status"))
            continue
        for label, expected in (("10", 10), ("100", 100), ("1000", 1000)):
            subset = item["subsets"][label]
            path = Path(subset["path"])
            schema = pq.read_schema(path)
            forbidden = [name for name in schema.names if name.lower() in {"lat", "lon", "latitude", "longitude"}]
            check(results, f"yjmob_no_latlon:{item.get('filename')}:{label}", not forbidden, str(schema.names))
            import duckdb

            frame = duckdb.query(
                f"SELECT count(*)::BIGINT AS n_rows, count(DISTINCT uid)::BIGINT AS n_users FROM read_parquet('{path.as_posix()}')"
            ).fetchone()
            check(
                results,
                f"yjmob_subset_count:{item.get('filename')}:{label}",
                frame[0] == subset["n_rows"] and frame[1] == subset["n_users"] == expected,
                f"parquet rows={frame[0]} users={frame[1]} summary rows={subset['n_rows']} users={subset['n_users']}",
            )


def verify_geolife(results: list[dict], summary: dict) -> None:
    if summary.get("status") != "ok":
        check(results, "geolife_status", False, str(summary.get("status") or summary.get("error")))
        return
    balance = summary.get("raw_points") == summary.get("accepted_points", 0) + summary.get("rejected_points", 0)
    check(results, "geolife_balance", bool(summary.get("balance_raw_equals_accepted_plus_rejected")) and balance, str(summary.get("raw_points")))
    check(results, "geolife_grids", set((summary.get("grid_cell_counts") or {})) == {"250", "500", "1000"}, str(summary.get("grid_cell_counts")))
    points = Path(summary.get("points_parquet") or "")
    if points.exists():
        schema = pq.read_schema(points)
        check(results, "geolife_wgs_columns", "latitude" in schema.names and "longitude" in schema.names, str(schema.names))
        check(results, "geolife_row_count", summary.get("accepted_rows_written") == summary.get("accepted_points"), f"written={summary.get('accepted_rows_written')} accepted={summary.get('accepted_points')}")
    else:
        check(results, "geolife_points_parquet", False, str(points))


def verify_noise(results: list[dict], summary: dict) -> None:
    if summary.get("status") not in {"ok", "partial"}:
        check(results, "noise_status", False, str(summary.get("status") or summary.get("error")))
        return
    indicators = summary.get("indicators") or {}
    required = ["points.noise_level", "tracks.noise_level", "areas.laeq", "areas.la50", "areas.lden"]
    check(results, "noise_indicators_separate", all(name in indicators for name in required), ",".join(indicators))
    for name in required:
        bucket = indicators.get(name) or {}
        has_both = "energy_mean_db" in bucket and "arithmetic_mean_db" in bucket
        check(results, f"noise_means:{name}", has_both, f"energy={bucket.get('energy_mean_db')} arithmetic={bucket.get('arithmetic_mean_db')}")
    totals = summary.get("totals") or {}
    check(results, "noise_point_count_recorded", "point_features" in totals, str(totals))


def write_report(data_dir: Path, payload: dict) -> None:
    path = data_dir / "reports" / "verify_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify downloaded and preprocessed datasets.")
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--resume", action="store_true", help="Accepted for a consistent CLI.")
    parser.add_argument("--recheck", action="store_true", help="Recompute MD5 and SHA-256 for every successful file.")
    parser.add_argument("--preprocess", action="store_true", help="Run preprocessing before verification.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    data_dir = Path(args.data_dir).resolve()
    if args.preprocess:
        from preprocess_datasets import run_preprocess

        run_preprocess(args.dataset, data_dir, args.resume, args.recheck)
    payload = verify(args.dataset, data_dir, args.recheck)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

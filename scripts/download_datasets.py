#!/usr/bin/env python3
"""Download YJMob100K, GeoLife, and NoiseCapture archives into UNLAB_DATA_DIR.

The script records only what the network actually returned. A failed transfer
is written to the manifest with the error text. It does not invent file sizes,
hashes, or row counts.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "UrbanNoiseLab-research/1.0 (graduate project; dataset reproduction)"
ZENODO_API = "https://zenodo.org/api/records/10836269"
GEOLIFE_PAGE = "https://www.microsoft.com/en-us/download/details.aspx?id=52367"
GEOLIFE_URL = "https://download.microsoft.com/download/f/4/8/f4894aa5-fdbc-481e-9285-d5f8c4c4f039/Geolife%20Trajectories%201.3.zip"
NOISE_PAGE = "https://noise-planet.org/noisecapture_data.html"
# Country archives confirmed with HTTP HEAD against https://data.noise-planet.org/dump/
# before this script was written. The script still records the live status.
NOISE_COUNTRIES = [
    "France",
    "Germany",
    "United Kingdom",
    "Spain",
    "Italy",
    "Belgium",
    "Netherlands",
    "Switzerland",
    "Austria",
    "Portugal",
    "Luxembourg",
    "China",
    "Japan",
    "Canada",
    "Brazil",
    "Australia",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def data_root() -> Path:
    return Path(os.environ.get("UNLAB_DATA_DIR", "data")).resolve()


def fetch_bytes(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_one(url: str, dest: Path, retries: int = 4) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    if dest.exists() and dest.stat().st_size > 0 and not partial.exists():
        return
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            existing = partial.stat().st_size if partial.exists() else 0
            headers = {"User-Agent": USER_AGENT}
            if existing:
                headers["Range"] = f"bytes={existing}-"
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=180) as response:
                status = getattr(response, "status", 200)
                mode = "ab" if status == 206 and existing else "wb"
                if status == 200 and existing:
                    # Server ignored Range. Restart.
                    mode = "wb"
                with partial.open(mode) as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
            partial.replace(dest)
            return
        except Exception as exc:  # network errors are recorded by the caller
            last_error = exc
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f"download failed after {retries} attempts: {last_error}")


def zenodo_plan() -> list[dict]:
    payload = json.loads(fetch_bytes(ZENODO_API).decode("utf-8"))
    meta = payload.get("metadata") or {}
    license_id = (meta.get("license") or {}).get("id", "")
    items = []
    for record in payload.get("files") or []:
        links = record.get("links") or {}
        url = links.get("self") or ""
        items.append(
            {
                "dataset": "YJMob100K",
                "name": record.get("key"),
                "url": url,
                "expected_bytes": record.get("size"),
                "expected_md5": (record.get("checksum") or "").replace("md5:", ""),
                "license": license_id or "cc-by-4.0",
                "source_page": "https://zenodo.org/records/10836269",
                "doi": payload.get("doi") or meta.get("doi"),
                "dest": str(data_root() / "raw" / "yjmob100k" / record.get("key")),
            }
        )
    if not items:
        raise RuntimeError("Zenodo record 10836269 returned no files")
    return items


def geolife_plan() -> dict:
    return {
        "dataset": "GeoLife",
        "name": "Geolife Trajectories 1.3.zip",
        "url": GEOLIFE_URL,
        "expected_bytes": 313164406,
        "expected_md5": "",
        "license": "Microsoft Research GeoLife GPS Trajectories; see the download page terms",
        "source_page": GEOLIFE_PAGE,
        "doi": "",
        "dest": str(data_root() / "raw" / "geolife" / "Geolife Trajectories 1.3.zip"),
        "note": "Direct file URL was read from the official Microsoft download details page (downloadFile.url). The page states 182 users from April 2007 to August 2012; user counts in reports come from the archive itself.",
    }


def noise_plan() -> list[dict]:
    items = []
    for country in NOISE_COUNTRIES:
        filename = f"{country}.zip"
        url = "https://data.noise-planet.org/dump/" + urllib.parse.quote(filename)
        items.append(
            {
                "dataset": "NoiseCapture",
                "name": filename,
                "url": url,
                "expected_bytes": None,
                "expected_md5": "",
                "license": "ODbL (Open Database License), as stated on https://noise-planet.org/noisecapture_data.html",
                "source_page": NOISE_PAGE,
                "doi": "",
                "dest": str(data_root() / "raw" / "noisecapture" / filename),
                "country": country,
                "note": "Phone measurements. Not a complete city noise field. Do not pool different dB indicators.",
            }
        )
    return items


def run_item(item: dict) -> dict:
    started = utcnow()
    t0 = time.time()
    dest = Path(item["dest"])
    record = {
        **{key: item.get(key) for key in ("dataset", "name", "url", "license", "source_page", "doi", "expected_bytes", "expected_md5", "country", "note")},
        "path": str(dest),
        "started_at": started,
        "status": "failed",
        "bytes": None,
        "sha256": None,
        "md5": None,
        "error": None,
        "md5_matches_expected": None,
    }
    try:
        download_one(item["url"], dest)
        record["bytes"] = dest.stat().st_size
        record["sha256"] = sha256_file(dest)
        record["md5"] = md5_file(dest)
        expected = item.get("expected_md5") or ""
        if expected:
            record["md5_matches_expected"] = record["md5"] == expected
            if record["md5"] != expected:
                record["status"] = "checksum_mismatch"
                record["error"] = f"md5 {record['md5']} != expected {expected}"
            else:
                record["status"] = "downloaded"
        else:
            record["status"] = "downloaded"
        if item.get("expected_bytes") and record["bytes"] != item["expected_bytes"] and record["status"] == "downloaded":
            record["status"] = "size_mismatch"
            record["error"] = f"bytes {record['bytes']} != expected {item['expected_bytes']}"
    except Exception as exc:
        record["status"] = "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["traceback"] = traceback.format_exc(limit=3)
        if dest.exists():
            record["bytes"] = dest.stat().st_size
    record["finished_at"] = utcnow()
    record["elapsed_sec"] = round(time.time() - t0, 3)
    return record


def write_manifest(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": utcnow(),
        "data_dir": str(data_root()),
        "unlab_data_dir_env": os.environ.get("UNLAB_DATA_DIR"),
        "items": items,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    root = data_root()
    manifest_path = root / "manifests" / "download_manifest.json"
    plans: list[dict] = []
    errors = []
    try:
        plans.extend(zenodo_plan())
    except Exception as exc:
        errors.append({"dataset": "YJMob100K", "status": "failed", "error": f"{type(exc).__name__}: {exc}", "started_at": utcnow(), "finished_at": utcnow()})
    plans.append(geolife_plan())
    plans.extend(noise_plan())
    results: list[dict] = list(errors)
    write_manifest(manifest_path, results)
    workers = int(os.environ.get("UNLAB_DOWNLOAD_WORKERS", "4"))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_item, item) for item in plans]
        for future in as_completed(futures):
            record = future.result()
            results.append(record)
            write_manifest(manifest_path, results)
            print(json.dumps({"name": record.get("name"), "status": record.get("status"), "bytes": record.get("bytes"), "error": record.get("error")}, ensure_ascii=False), flush=True)
    failed = [item for item in results if item.get("status") not in {"downloaded"}]
    print(json.dumps({"manifest": str(manifest_path), "items": len(results), "failed": len(failed)}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

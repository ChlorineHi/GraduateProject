#!/usr/bin/env python3
"""Download YJMob100K, GeoLife, and NoiseCapture into a local data directory.

The script records every attempt in data/manifests/download_manifest.json.
It does not invent filenames, checksums, or byte counts: those come from the
upstream record or from the bytes written to disk.

Examples
--------
python scripts/download_datasets.py --dataset all --data-dir data --resume
python scripts/download_datasets.py --dataset yjmob100k --data-dir data --recheck
python scripts/download_datasets.py --dataset noisecapture --data-dir data --resume --preprocess
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

USER_AGENT = "UrbanNoiseLab-data/1.0 (local research preprocessing)"
ZENODO_RECORD_API = "https://zenodo.org/api/records/10836269"
ZENODO_RECORD_HTML = "https://zenodo.org/records/10836269"
YJMOB_CANDIDATES = (
    "yjmob100k-dataset1.csv.gz",
    "yjmob100k-dataset2.csv.gz",
    "cell_POIcat.csv.gz",
    "POI_datacategories.csv",
)
GEOLIFE_PAGE = "https://www.microsoft.com/en-us/download/details.aspx?id=52367"
NOISECAPTURE_DATA_PAGE = "https://noise-planet.org/noisecapture_data.html"
NOISECAPTURE_EXPLOIT_PAGE = "https://noise-planet.org/noisecapture_exploit_data.html"
NOISECAPTURE_HTTP_DUMP = "http://data.noise-planet.org/dump/"
NOISECAPTURE_HTTPS_DUMP = "https://data.noise-planet.org/dump/"
DATASETS = ("all", "yjmob100k", "geolife", "noisecapture")
CHUNK = 1024 * 1024


class DownloadError(RuntimeError):
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def quote_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/%")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def atomic_write_json(path: Path, payload: object) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def manifest_path(data_dir: Path) -> Path:
    return data_dir / "manifests" / "download_manifest.json"


def load_manifest(path: Path, command: list[str]) -> dict:
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        payload = {
            "schema_version": 1,
            "created_at": utcnow(),
            "command": command,
            "sources": {},
            "files": [],
        }
    payload["updated_at"] = utcnow()
    payload["command"] = command
    payload.setdefault("sources", {})
    payload.setdefault("files", [])
    return payload


def upsert_file(manifest: dict, entry: dict) -> None:
    files = manifest["files"]
    for index, existing in enumerate(files):
        if existing.get("dataset") == entry.get("dataset") and existing.get("url") == entry.get("url") and existing.get("filename") == entry.get("filename"):
            files[index] = entry
            return
    files.append(entry)


class ManifestStore:
    def __init__(self, path: Path, manifest: dict):
        self.path = path
        self.manifest = manifest
        self.lock = threading.Lock()

    def add(self, entry: dict) -> None:
        with self.lock:
            upsert_file(self.manifest, entry)
            self.manifest["updated_at"] = utcnow()
            atomic_write_json(self.path, self.manifest)

    def set_source(self, key: str, value: dict) -> None:
        with self.lock:
            self.manifest["sources"][key] = value
            self.manifest["updated_at"] = utcnow()
            atomic_write_json(self.path, self.manifest)


def hash_file(path: Path) -> dict:
    md5 = hashlib.md5()
    sha = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            md5.update(chunk)
            sha.update(chunk)
            size += len(chunk)
    return {"bytes": size, "md5": md5.hexdigest(), "sha256": sha.hexdigest()}


def _request(url: str, method: str, headers: dict | None, timeout: int):
    merged = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    if headers:
        merged.update(headers)
    request = urllib.request.Request(quote_url(url), headers=merged, method=method)
    return urllib.request.urlopen(request, timeout=timeout)


def read_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read(2000)
    except Exception as read_exc:  # noqa: BLE001
        body = f"<failed to read body: {type(read_exc).__name__}: {read_exc}>".encode()
    text = body.decode("utf-8", "replace")
    return f"HTTPError {exc.code} for {exc.geturl()}: {text}"


def fetch_bytes(url: str, timeout: int = 120, max_bytes: int | None = None) -> dict:
    try:
        with _request(url, "GET", None, timeout) as response:
            chunks = []
            total = 0
            while True:
                block = response.read(CHUNK if max_bytes is None else min(CHUNK, max_bytes - total))
                if not block:
                    break
                chunks.append(block)
                total += len(block)
                if max_bytes is not None and total >= max_bytes:
                    break
            return {
                "status": getattr(response, "status", None),
                "final_url": response.geturl(),
                "headers": {key: response.headers.get(key) for key in response.headers.keys()},
                "body": b"".join(chunks),
            }
    except urllib.error.HTTPError as exc:
        raise DownloadError(read_http_error(exc)) from exc


def fetch_text(url: str, timeout: int = 120) -> dict:
    payload = fetch_bytes(url, timeout=timeout)
    payload["text"] = payload["body"].decode("utf-8", "replace")
    return payload


def head_info(url: str, timeout: int = 60) -> dict:
    try:
        with _request(url, "HEAD", None, timeout) as response:
            length = response.headers.get("Content-Length")
            return {
                "status": getattr(response, "status", None),
                "final_url": response.geturl(),
                "content_length": int(length) if length and length.isdigit() else None,
                "headers": {
                    "Content-Length": response.headers.get("Content-Length"),
                    "Content-Type": response.headers.get("Content-Type"),
                    "ETag": response.headers.get("ETag"),
                    "Last-Modified": response.headers.get("Last-Modified"),
                    "Accept-Ranges": response.headers.get("Accept-Ranges"),
                    "Server": response.headers.get("Server"),
                    "Content-Disposition": response.headers.get("Content-Disposition"),
                },
            }
    except urllib.error.HTTPError as exc:
        raise DownloadError(read_http_error(exc)) from exc


def with_retries(action, label: str, attempts: int = 5):
    errors: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            return action()
        except Exception as exc:  # noqa: BLE001
            message = f"{type(exc).__name__}: {exc}"
            errors.append(f"attempt {attempt}/{attempts} {label}: {message}")
            retryable = True
            if isinstance(exc, DownloadError) and "HTTPError 404" in str(exc):
                retryable = False
            if isinstance(exc, urllib.error.HTTPError) and exc.code in {400, 401, 403, 404}:
                retryable = False
            if attempt == attempts or not retryable:
                raise DownloadError(" | ".join(errors)) from exc
            delay = min(32, 2**attempt)
            print(f"retry {label} in {delay}s after {message}", flush=True)
            time.sleep(delay)
    raise DownloadError(" | ".join(errors))


def download_to(url: str, dest: Path, resume: bool, expected_size: int | None) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()

    def once():
        existing = dest.stat().st_size if dest.exists() else 0
        headers: dict[str, str] = {}
        if resume and existing > 0 and (expected_size is None or existing < expected_size):
            headers["Range"] = f"bytes={existing}-"
        elif existing > 0:
            existing = 0
        try:
            response = _request(url, "GET", headers, 180)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and expected_size is not None and dest.exists() and dest.stat().st_size == expected_size:
                return {
                    "status": 416,
                    "final_url": exc.geturl(),
                    "headers": {"Content-Length": str(expected_size)},
                    "note": "HTTP 416; local file already matches content length",
                }
            raise DownloadError(read_http_error(exc)) from exc
        status = getattr(response, "status", None)
        final_url = response.geturl()
        response_headers = {
            "Content-Length": response.headers.get("Content-Length"),
            "Content-Range": response.headers.get("Content-Range"),
            "Content-Type": response.headers.get("Content-Type"),
            "ETag": response.headers.get("ETag"),
            "Last-Modified": response.headers.get("Last-Modified"),
            "Accept-Ranges": response.headers.get("Accept-Ranges"),
            "Server": response.headers.get("Server"),
        }
        if status == 200:
            mode = "wb"
            written = 0
        elif status == 206:
            mode = "ab"
            written = existing
        else:
            response.close()
            raise DownloadError(f"unexpected HTTP status {status} for {url}")
        last_mark = written
        with dest.open(mode) as handle:
            while True:
                block = response.read(CHUNK)
                if not block:
                    break
                handle.write(block)
                written += len(block)
                if written - last_mark >= 50 * CHUNK:
                    print(f"progress {dest.name} {written} bytes", flush=True)
                    last_mark = written
        response.close()
        if expected_size is not None and written != expected_size:
            raise DownloadError(
                f"incomplete download for {dest.name}: bytes_on_disk={written} content_length={expected_size} http_status={status}"
            )
        return {"status": status, "final_url": final_url, "headers": response_headers, "bytes_on_disk": written}

    result = with_retries(once, dest.name)
    result["elapsed_seconds"] = round(time.time() - started, 3)
    result["bytes_on_disk"] = dest.stat().st_size if dest.exists() else 0
    return result


def parse_size_label(label: str) -> int | None:
    match = re.match(r"^\s*([\d.]+)\s*([KMGT]?)", label.strip(), re.I)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2).upper()
    scale = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}[unit]
    return int(number * scale)


class DumpIndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[dict] = []
        self._cell = None
        self._cells: list[str] = []
        self._href = None
        self._in_td = False

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag == "tr":
            self._cells = []
            self._href = None
        elif tag == "td":
            self._in_td = True
            self._cell = []
        elif tag == "a" and self._in_td:
            self._href = attr.get("href")

    def handle_endtag(self, tag):
        if tag == "td" and self._in_td:
            self._cells.append(("".join(self._cell or [])).strip())
            self._in_td = False
            self._cell = None
        elif tag == "tr" and self._cells:
            name = self._cells[0] if self._cells else ""
            modified = self._cells[1] if len(self._cells) > 1 else ""
            size_label = self._cells[2] if len(self._cells) > 2 else ""
            if self._href and self._href.lower().split("?")[0].endswith(".zip"):
                self.rows.append(
                    {
                        "href": self._href,
                        "name": name,
                        "modified_label": modified,
                        "size_label": size_label,
                        "size_label_bytes": parse_size_label(size_label),
                    }
                )

    def handle_data(self, data):
        if self._in_td and self._cell is not None:
            self._cell.append(data)


def parse_geolife_details(html: str) -> dict:
    marker = "window.__DLCDetails__="
    index = html.find(marker)
    if index < 0:
        title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        excerpt = re.sub(r"\s+", " ", html[:500])
        raise DownloadError(
            "GeoLife download page has no window.__DLCDetails__ JSON. "
            f"title={title.group(1).strip() if title else None!r} excerpt={excerpt!r}"
        )
    try:
        payload, _end = json.JSONDecoder().raw_decode(html[index + len(marker) :])
    except json.JSONDecodeError as exc:
        raise DownloadError(f"GeoLife download page JSON could not be parsed: {exc}") from exc
    view = payload.get("dlcDetailsView") or {}
    files = view.get("downloadFile") or []
    if not isinstance(files, list) or not files:
        raise DownloadError(
            "GeoLife download page JSON has no downloadFile entries. "
            f"dlcDetailsView.error={view.get('error')!r} keys={list(view.keys())}"
        )
    return {
        "download_title": view.get("downloadTitle"),
        "download_description": view.get("downloadDescription"),
        "details_section": view.get("detailsSection"),
        "page_error_field": view.get("error"),
        "files": files,
        "details_file_version": view.get("detailsSection_file_version"),
        "details_file_size": view.get("detailsSection_file_size"),
        "details_file_date": view.get("detailsSection_file_date"),
    }


def license_block(dataset: str, extra: dict | None = None) -> dict:
    extra = extra or {}
    if dataset == "yjmob100k":
        return {
            "id": extra.get("id"),
            "name": "Creative Commons Attribution 4.0 International",
            "source": "Zenodo record metadata license.id",
            "url": "https://creativecommons.org/licenses/by/4.0/" if extra.get("id") == "cc-by-4.0" else None,
            "record_url": ZENODO_RECORD_HTML,
            "notes": extra.get("notes"),
        }
    if dataset == "geolife":
        return {
            "id": None,
            "source": "Microsoft Download Center details page",
            "page_url": GEOLIFE_PAGE,
            "notes": extra.get("notes"),
        }
    return {
        "id": "ODbL-1.0",
        "name": "Open Database License",
        "source": extra.get("source") or "Noise-Planet data page and in-archive README.html",
        "url": "https://opendatacommons.org/licenses/odbl/1-0/",
        "notes": extra.get("notes"),
    }


def base_entry(**kwargs) -> dict:
    entry = {
        "downloaded_at": utcnow(),
        "elapsed_seconds": None,
        "http_status": None,
        "requested_url": None,
        "final_url": None,
        "bytes": None,
        "hashes": None,
        "official_checksum": None,
        "etag": None,
        "etag_matches_sha256": None,
        "license": None,
        "status": None,
        "error": None,
        "notes": None,
    }
    entry.update(kwargs)
    return entry


def finish_hashes(path: Path, official_md5: str | None, etag: str | None) -> dict:
    hashes = hash_file(path)
    official = None
    match = None
    if official_md5:
        match = hashes["md5"] == official_md5
        official = {
            "algorithm": "md5",
            "value": official_md5,
            "source": "zenodo file checksum field",
            "match": match,
        }
    etag_hex = None
    if etag:
        etag_hex = etag.strip().strip('"')
        if etag_hex.lower().startswith("0x"):
            etag_hex = etag_hex[2:]
    return {
        "hashes": {
            "md5": {"algorithm": "md5", "value": hashes["md5"], "source": "computed locally over the file bytes"},
            "sha256": {"algorithm": "sha256", "value": hashes["sha256"], "source": "computed locally over the file bytes"},
        },
        "bytes": hashes["bytes"],
        "official_checksum": official,
        "etag": etag,
        "etag_matches_sha256": (etag_hex.lower() == hashes["sha256"]) if etag_hex else None,
        "official_match": match,
    }


def seen_hash(manifest: dict, sha256: str, filename: str) -> str | None:
    for entry in manifest["files"]:
        hashes = entry.get("hashes") or {}
        sha = (hashes.get("sha256") or {}).get("value")
        if sha == sha256 and entry.get("filename") != filename and entry.get("status") in {"downloaded", "skipped_existing"}:
            return entry.get("filename")
    return None


def acquire_file(
    store: ManifestStore,
    *,
    dataset: str,
    filename: str,
    url: str,
    dest: Path,
    resume: bool,
    recheck: bool,
    license_info: dict,
    official_md5: str | None = None,
    expected_size: int | None = None,
    notes: str | None = None,
    min_free_bytes: int = 0,
) -> dict:
    started = time.time()
    entry = base_entry(
        dataset=dataset,
        filename=filename,
        path=str(dest),
        url=url,
        requested_url=url,
        license=license_info,
        notes=notes,
    )
    try:
        try:
            info = with_retries(lambda: head_info(url), f"HEAD {filename}")
        except DownloadError as exc:
            info = {
                "status": None,
                "final_url": url,
                "content_length": expected_size,
                "headers": {},
                "head_error": str(exc),
            }
        remote_size = info.get("content_length")
        if expected_size is not None and remote_size is not None and remote_size != expected_size:
            entry["notes"] = (
                (notes + " " if notes else "")
                + f"HEAD Content-Length {remote_size} differs from metadata size {expected_size}."
            )
        expected = remote_size if remote_size is not None else expected_size
        entry["head"] = info
        local_size = dest.stat().st_size if dest.exists() else 0
        use_existing = dest.exists() and expected is not None and local_size == expected
        if use_existing and not recheck:
            prior = next(
                (
                    item
                    for item in store.manifest["files"]
                    if item.get("url") == url and item.get("filename") == filename and (item.get("hashes") or {}).get("sha256")
                ),
                None,
            )
            if prior and prior.get("bytes") == local_size and (prior.get("official_checksum") or {}).get("match") is not False:
                entry.update(
                    {
                        "status": "skipped_existing",
                        "bytes": local_size,
                        "hashes": prior.get("hashes"),
                        "official_checksum": prior.get("official_checksum"),
                        "etag": (info.get("headers") or {}).get("ETag"),
                        "etag_matches_sha256": prior.get("etag_matches_sha256"),
                        "elapsed_seconds": round(time.time() - started, 3),
                        "http_status": info.get("status"),
                        "final_url": info.get("final_url"),
                        "error": None,
                    }
                )
                store.add(entry)
                print(json.dumps({"event": "file", "filename": filename, "bytes": local_size, "sha256": entry["hashes"]["sha256"]["value"], "md5": entry["hashes"]["md5"]["value"], "status": entry["status"], "error": None}), flush=True)
                return entry
        if use_existing:
            hashed = finish_hashes(dest, official_md5, (info.get("headers") or {}).get("ETag"))
            if official_md5 and hashed["official_match"] is False:
                use_existing = False
                entry["notes"] = ((entry.get("notes") or "") + " Existing file failed the official MD5 check and will be downloaded again.").strip()
            else:
                duplicate_of = seen_hash(store.manifest, hashed["hashes"]["sha256"]["value"], filename)
                status = "skipped_existing"
                if duplicate_of:
                    status = "skipped_duplicate"
                    entry["duplicate_of"] = duplicate_of
                entry.update(hashed)
                entry.update(
                    {
                        "status": status,
                        "elapsed_seconds": round(time.time() - started, 3),
                        "http_status": info.get("status"),
                        "final_url": info.get("final_url"),
                        "error": None,
                    }
                )
                store.add(entry)
                print(json.dumps({"event": "file", "filename": filename, "bytes": entry["bytes"], "sha256": entry["hashes"]["sha256"]["value"], "md5": entry["hashes"]["md5"]["value"], "status": status, "error": None}), flush=True)
                return entry

        dest.parent.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(dest.parent).free
        need = expected or 0
        if min_free_bytes and free - need < min_free_bytes:
            message = f"skipped because free bytes {free} minus object bytes {need} is below the reserved free-space floor {min_free_bytes}"
            entry.update({"status": "skipped_disk_budget", "error": message, "bytes": local_size or None, "elapsed_seconds": round(time.time() - started, 3)})
            store.add(entry)
            print(json.dumps({"event": "file", "filename": filename, "bytes": None, "sha256": None, "md5": None, "status": entry["status"], "error": message}), flush=True)
            return entry

        if dest.exists() and not resume:
            dest.unlink()
        transfer = download_to(url, dest, resume=resume, expected_size=expected)
        hashed = finish_hashes(dest, official_md5, (transfer.get("headers") or {}).get("ETag") or (info.get("headers") or {}).get("ETag"))
        status = "downloaded"
        error = None
        if official_md5 and hashed["official_match"] is False:
            status = "checksum_mismatch"
            error = f"official md5 {official_md5} != computed md5 {hashed['hashes']['md5']['value']}"
        duplicate_of = seen_hash(store.manifest, hashed["hashes"]["sha256"]["value"], filename)
        if duplicate_of and status == "downloaded":
            entry["duplicate_of"] = duplicate_of
            entry["notes"] = ((entry.get("notes") or "") + f" Byte-identical to already stored file {duplicate_of}.").strip()
        entry.update(hashed)
        entry.update(
            {
                "status": status,
                "error": error,
                "elapsed_seconds": round(time.time() - started + transfer.get("elapsed_seconds", 0), 3),
                "http_status": transfer.get("status"),
                "final_url": transfer.get("final_url"),
                "response_headers": transfer.get("headers"),
            }
        )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        entry.update(
            {
                "status": "failed",
                "error": error,
                "traceback": traceback.format_exc(limit=8),
                "elapsed_seconds": round(time.time() - started, 3),
                "bytes": dest.stat().st_size if dest.exists() else None,
            }
        )
    store.add(entry)
    hashes = entry.get("hashes") or {}
    print(
        json.dumps(
            {
                "event": "file",
                "filename": filename,
                "bytes": entry.get("bytes"),
                "sha256": (hashes.get("sha256") or {}).get("value"),
                "md5": (hashes.get("md5") or {}).get("value"),
                "status": entry.get("status"),
                "error": entry.get("error"),
            }
        ),
        flush=True,
    )
    return entry


def download_yjmob(store: ManifestStore, raw_root: Path, resume: bool, recheck: bool, min_free_bytes: int) -> None:
    fetched = with_retries(lambda: fetch_text(ZENODO_RECORD_API), "zenodo record")
    record = json.loads(fetched["text"])
    metadata = record.get("metadata") or {}
    files = record.get("files") or []
    listed = []
    for item in files:
        checksum = item.get("checksum") or ""
        algorithm, _, value = checksum.partition(":")
        listed.append(
            {
                "key": item.get("key"),
                "size": item.get("size"),
                "checksum": checksum,
                "checksum_algorithm": algorithm or None,
                "checksum_value": value or None,
                "links": item.get("links"),
            }
        )
    found_names = [item.get("key") for item in listed]
    missing = [name for name in YJMOB_CANDIDATES if name not in found_names]
    license_id = (metadata.get("license") or {}).get("id") if isinstance(metadata.get("license"), dict) else metadata.get("license")
    source = {
        "fetched_at": utcnow(),
        "api_url": ZENODO_RECORD_API,
        "html_url": ZENODO_RECORD_HTML,
        "final_url": fetched.get("final_url"),
        "http_status": fetched.get("status"),
        "doi": record.get("doi") or metadata.get("doi"),
        "title": metadata.get("title") or record.get("title"),
        "license_id": license_id,
        "access_right": metadata.get("access_right"),
        "description_text_present": bool(metadata.get("description")),
        "files": listed,
        "candidate_filenames": list(YJMOB_CANDIDATES),
        "missing_candidates": missing,
        "official_hash_algorithms": sorted({item.get("checksum_algorithm") for item in listed if item.get("checksum_algorithm")}),
    }
    store.set_source("yjmob100k", source)
    lic = license_block(
        "yjmob100k",
        {
            "id": license_id,
            "notes": "Zenodo file records on this fetch expose MD5 checksums and do not include a SHA-256 field. SHA-256 in the manifest is computed locally.",
        },
    )
    dest_dir = raw_root / "yjmob100k"
    if missing:
        for name in missing:
            entry = base_entry(
                dataset="yjmob100k",
                filename=name,
                url=None,
                path=str(dest_dir / name),
                license=lic,
                status="failed",
                error=f"Zenodo record {ZENODO_RECORD_API} file list does not contain candidate {name}. files={found_names}",
            )
            store.add(entry)
            print(json.dumps({"event": "file", "filename": name, "bytes": None, "sha256": None, "md5": None, "status": "failed", "error": entry["error"]}), flush=True)
    for item in listed:
        key = item.get("key")
        if not key:
            continue
        link = ((item.get("links") or {}).get("self")) or f"{ZENODO_RECORD_API}/files/{urllib.parse.quote(key)}/content"
        official = item.get("checksum_value") if item.get("checksum_algorithm") == "md5" else None
        note = None
        if item.get("checksum_algorithm") and item.get("checksum_algorithm") != "md5":
            note = f"Zenodo checksum algorithm was {item.get('checksum_algorithm')}, value {item.get('checksum_value')}"
            official = None
        acquire_file(
            store,
            dataset="yjmob100k",
            filename=key,
            url=link,
            dest=dest_dir / key,
            resume=resume,
            recheck=recheck,
            license_info=lic,
            official_md5=official,
            expected_size=item.get("size"),
            notes=note,
            min_free_bytes=min_free_bytes,
        )


def download_geolife(store: ManifestStore, raw_root: Path, resume: bool, recheck: bool, min_free_bytes: int) -> None:
    try:
        page = with_retries(lambda: fetch_text(GEOLIFE_PAGE), "geolife page")
        parsed = parse_geolife_details(page["text"])
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        store.set_source(
            "geolife",
            {"fetched_at": utcnow(), "page_url": GEOLIFE_PAGE, "status": "failed", "error": error},
        )
        entry = base_entry(
            dataset="geolife",
            filename=None,
            url=GEOLIFE_PAGE,
            license=license_block("geolife", {"notes": "Page fetch or parse failed before a file URL was found."}),
            status="failed",
            error=error,
        )
        store.add(entry)
        print(json.dumps({"event": "file", "filename": None, "bytes": None, "sha256": None, "md5": None, "status": "failed", "error": error}), flush=True)
        return
    details = parsed.get("details_section") or ""
    description = parsed.get("download_description") or ""
    has_license_word = "license" in details.lower() or "license" in description.lower()
    notes = (
        "The Download Center details JSON includes size and URL but no checksum field. "
        "SHA-256 and MD5 below are computed locally. "
        + (
            "The details text contains the word license."
            if has_license_word
            else "The details JSON has no license field and the fetched details text does not contain the word license."
        )
    )
    store.set_source(
        "geolife",
        {
            "fetched_at": utcnow(),
            "page_url": GEOLIFE_PAGE,
            "final_url": page.get("final_url"),
            "http_status": page.get("status"),
            "download_title": parsed.get("download_title"),
            "download_description": parsed.get("download_description"),
            "details_section": parsed.get("details_section"),
            "page_error_field": parsed.get("page_error_field"),
            "files": parsed.get("files"),
            "details_file_version": parsed.get("details_file_version"),
            "details_file_size": parsed.get("details_file_size"),
            "details_file_date": parsed.get("details_file_date"),
            "license_word_in_details": has_license_word,
        },
    )
    lic = license_block("geolife", {"notes": notes})
    for item in parsed["files"]:
        name = item.get("name") or "geolife.zip"
        url = item.get("url")
        size = item.get("size")
        expected = int(size) if isinstance(size, str) and size.isdigit() else (int(size) if isinstance(size, int) else None)
        if not url:
            error = f"GeoLife file entry has no url: {item!r}"
            entry = base_entry(dataset="geolife", filename=name, url=None, license=lic, status="failed", error=error)
            store.add(entry)
            print(json.dumps({"event": "file", "filename": name, "bytes": None, "sha256": None, "md5": None, "status": "failed", "error": error}), flush=True)
            continue
        acquire_file(
            store,
            dataset="geolife",
            filename=name,
            url=url,
            dest=raw_root / "geolife" / name,
            resume=resume,
            recheck=recheck,
            license_info=lic,
            expected_size=expected,
            notes=f"version={item.get('version')} datePublished={item.get('datePublished')} isPrimary={item.get('isPrimary')}",
            min_free_bytes=min_free_bytes,
        )


def record_page_failure(store: ManifestStore, dataset: str, filename: str, url: str, error: str, license_info: dict) -> None:
    entry = base_entry(
        dataset=dataset,
        filename=filename,
        url=url,
        requested_url=url,
        license=license_info,
        status="failed",
        error=error,
    )
    store.add(entry)
    print(json.dumps({"event": "file", "filename": filename, "bytes": None, "sha256": None, "md5": None, "status": "failed", "error": error}), flush=True)


def download_noisecapture(store: ManifestStore, raw_root: Path, resume: bool, recheck: bool, min_free_bytes: int, workers: int) -> None:
    lic = license_block(
        "noisecapture",
        {
            "source": "https://noise-planet.org/noisecapture_data.html states the community data are delivered under the ODbL and links to the dump directory",
            "notes": "Per-archive README.html is hashed during preprocessing. HTTP and HTTPS dump URLs are both requested.",
        },
    )
    pages = {}
    for key, url in {
        "data_page": NOISECAPTURE_DATA_PAGE,
        "exploit_page": NOISECAPTURE_EXPLOIT_PAGE,
    }.items():
        try:
            fetched = with_retries(lambda url=url: fetch_text(url), key)
            hrefs = re.findall(r'href="([^"]+)"', fetched["text"], flags=re.I)
            title = re.search(r"<title>(.*?)</title>", fetched["text"], re.I | re.S)
            pages[key] = {
                "url": url,
                "final_url": fetched.get("final_url"),
                "http_status": fetched.get("status"),
                "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else None,
                "hrefs": hrefs,
                "mentions_odbl": "opendatacommons.org/licenses/odbl" in fetched["text"],
                "status": "fetched",
            }
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            pages[key] = {"url": url, "status": "failed", "error": error}
            record_page_failure(store, "noisecapture", key, url, error, lic)

    try:
        http_dump = with_retries(lambda: fetch_bytes(NOISECAPTURE_HTTP_DUMP, max_bytes=20000), "http dump")
        body = http_dump["body"].decode("utf-8", "replace")
        hrefs = re.findall(r'href="([^"]+\.zip)"', body, flags=re.I)
        title = re.search(r"<title>(.*?)</title>", body, re.I | re.S)
        title_text = re.sub(r"\s+", " ", title.group(1)).strip() if title else None
        if hrefs:
            pages["http_dump"] = {
                "url": NOISECAPTURE_HTTP_DUMP,
                "final_url": http_dump.get("final_url"),
                "http_status": http_dump.get("status"),
                "title": title_text,
                "zip_links": len(hrefs),
                "status": "fetched",
            }
        else:
            excerpt = body[:500]
            error = (
                f"HTTP {http_dump.get('status')} from {http_dump.get('final_url')} returned no .zip links. "
                f"title={title_text!r} content_type={http_dump.get('headers', {}).get('Content-Type')!r} "
                f"server={http_dump.get('headers', {}).get('Server')!r} excerpt={excerpt!r}"
            )
            pages["http_dump"] = {
                "url": NOISECAPTURE_HTTP_DUMP,
                "final_url": http_dump.get("final_url"),
                "http_status": http_dump.get("status"),
                "title": title_text,
                "status": "failed",
                "error": error,
                "excerpt": excerpt,
            }
            record_page_failure(store, "noisecapture", "http-dump-index", NOISECAPTURE_HTTP_DUMP, error, lic)
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        pages["http_dump"] = {"url": NOISECAPTURE_HTTP_DUMP, "status": "failed", "error": error}
        record_page_failure(store, "noisecapture", "http-dump-index", NOISECAPTURE_HTTP_DUMP, error, lic)

    index_url = NOISECAPTURE_HTTPS_DUMP
    try:
        index = with_retries(lambda: fetch_text(index_url), "https dump index")
        parser = DumpIndexParser()
        parser.feed(index["text"])
        archives = []
        for row in parser.rows:
            name = urllib.parse.unquote(row["name"])
            url = urllib.parse.urljoin(index.get("final_url") or index_url, row["href"])
            archives.append({**row, "filename": name, "url": url})
        archives.sort(key=lambda item: item.get("size_label_bytes") or 0, reverse=True)
        pages["https_dump"] = {
            "url": index_url,
            "final_url": index.get("final_url"),
            "http_status": index.get("status"),
            "archive_count": len(archives),
            "status": "fetched",
            "preference": "Archives are requested largest-label first. The dump is one zip per country or territory; regional geojson files are inside the zip. Larger archives are preferred as the available proxy for denser measurement coverage.",
        }
        store.set_source("noisecapture", {"fetched_at": utcnow(), "pages": pages, "archive_count": len(archives)})
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        pages["https_dump"] = {"url": index_url, "status": "failed", "error": error}
        store.set_source("noisecapture", {"fetched_at": utcnow(), "pages": pages})
        record_page_failure(store, "noisecapture", "https-dump-index", index_url, error, lic)
        return

    if not archives:
        error = f"HTTPS dump index {index.get('final_url')} parsed zero zip rows"
        record_page_failure(store, "noisecapture", "https-dump-index", index_url, error, lic)
        return

    dest_dir = raw_root / "noisecapture"

    def one(archive: dict) -> dict:
        return acquire_file(
            store,
            dataset="noisecapture",
            filename=archive["filename"],
            url=archive["url"],
            dest=dest_dir / archive["filename"],
            resume=resume,
            recheck=recheck,
            license_info=lic,
            notes=f"index modified={archive.get('modified_label')} index size label={archive.get('size_label')}",
            min_free_bytes=min_free_bytes,
        )

    workers = max(1, workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, archive) for archive in archives]
        for future in as_completed(futures):
            future.result()


def render_download_report(manifest: dict, path: Path) -> None:
    lines = [
        "# Dataset download report",
        "",
        f"Generated at {manifest.get('updated_at')} by `scripts/download_datasets.py`.",
        "",
        "Counts, byte sizes, and hashes in this file are copied from `data/manifests/download_manifest.json`. They are the values measured for this run, not figures taken from papers.",
        "",
        f"Command: `{' '.join(manifest.get('command') or [])}`",
        "",
    ]
    files = manifest.get("files") or []
    counts: dict[str, int] = {}
    for entry in files:
        counts[entry.get("status") or "unknown"] = counts.get(entry.get("status") or "unknown", 0) + 1
    lines.append("## Status counts")
    lines.append("")
    for key in sorted(counts):
        lines.append(f"- {key}: {counts[key]}")
    lines.append("")
    failures = [entry for entry in files if entry.get("status") in {"failed", "checksum_mismatch", "skipped_disk_budget"}]
    lines.append("## Failures")
    lines.append("")
    if not failures:
        lines.append("No download attempt was recorded with status failed, checksum_mismatch, or skipped_disk_budget.")
    else:
        for entry in failures:
            lines.append(f"### {entry.get('dataset')} / {entry.get('filename')}")
            lines.append("")
            lines.append(f"- URL: `{entry.get('url')}`")
            lines.append(f"- Status: `{entry.get('status')}`")
            lines.append(f"- Error: `{entry.get('error')}`")
            lines.append("")
    lines.append("## Files")
    lines.append("")
    lines.append("| dataset | filename | bytes | md5 | sha256 | status | elapsed_s |")
    lines.append("| --- | --- | ---: | --- | --- | --- | ---: |")
    for entry in files:
        hashes = entry.get("hashes") or {}
        md5 = (hashes.get("md5") or {}).get("value") or ""
        sha = (hashes.get("sha256") or {}).get("value") or ""
        lines.append(
            "| {dataset} | {filename} | {bytes} | `{md5}` | `{sha}` | {status} | {elapsed} |".format(
                dataset=entry.get("dataset") or "",
                filename=(entry.get("filename") or "").replace("|", "\\|"),
                bytes="" if entry.get("bytes") is None else entry.get("bytes"),
                md5=md5,
                sha=sha,
                status=entry.get("status") or "",
                elapsed="" if entry.get("elapsed_seconds") is None else entry.get("elapsed_seconds"),
            )
        )
    lines.append("")
    lines.append("Per-file URL, license, official checksum comparison, ETag, and error text are in `data/manifests/download_manifest.json`.")
    lines.append("")
    atomic_write_text(path, "\n".join(lines))


def render_license_doc(manifest: dict, path: Path) -> None:
    sources = manifest.get("sources") or {}
    yj = sources.get("yjmob100k") or {}
    geo = sources.get("geolife") or {}
    nc = sources.get("noisecapture") or {}
    lines = [
        "# Dataset licenses",
        "",
        f"Generated at {manifest.get('updated_at')} by `scripts/download_datasets.py`.",
        "",
        "This note records the license statements returned by the upstream pages and records. It is not a legal opinion. Redistribution of the raw archives is not part of this repository; `data/raw/` is gitignored.",
        "",
        "## YJMob100K",
        "",
        f"- Record: {yj.get('html_url') or ZENODO_RECORD_HTML}",
        f"- API: {yj.get('api_url') or ZENODO_RECORD_API}",
        f"- DOI: `{yj.get('doi')}`",
        f"- Title: {yj.get('title')}",
        f"- Zenodo `metadata.license.id`: `{yj.get('license_id')}`",
        f"- Zenodo access right: `{yj.get('access_right')}`",
        "- When `license.id` is `cc-by-4.0`, the license URL used here is https://creativecommons.org/licenses/by/4.0/.",
        f"- Official file checksum algorithms present on the record: `{yj.get('official_hash_algorithms')}`",
        "- Local SHA-256 values are not Zenodo checksums. The manifest marks an official MD5 as a match only when the locally computed MD5 equals the Zenodo checksum field.",
        "",
        "The Zenodo description names the Scientific Data paper Yabe et al. 2024, DOI `10.1038/s41597-024-03237-9`, as the data descriptor. This repository does not copy that paper.",
        "",
        "## GeoLife GPS Trajectories",
        "",
        f"- Page: {geo.get('page_url') or GEOLIFE_PAGE}",
        f"- HTTP status: `{geo.get('http_status')}`",
        f"- Title: {geo.get('download_title')}",
        f"- Page error field: `{geo.get('page_error_field')}`",
        f"- The fetched details text contains the word license: `{geo.get('license_word_in_details')}`",
        "- The file entry parsed from the page has a name, URL, size, version, and publication time. It has no checksum field.",
        "- Any license statement found inside the zip is added by preprocessing when a readable text file contains one. Until that scan runs, no in-zip license is claimed.",
        "",
        "Microsoft’s own page description is stored in the manifest under `sources.geolife`. That description is Microsoft’s account of the collection. Counts used in the quality report come from parsing the zip, not from that paragraph.",
        "",
        "## NoiseCapture",
        "",
        f"- Data page: {NOISECAPTURE_DATA_PAGE}",
        f"- Exploit page: {NOISECAPTURE_EXPLOIT_PAGE}",
        "- The data page links the dump and the Open Database License at https://opendatacommons.org/licenses/odbl/.",
        "- The exploit page also links `https://data.noise-planet.org/dump/` and the ODbL.",
        "- `http://data.noise-planet.org/dump/` is the URL printed on the data page. The result of requesting it is recorded as its own manifest entry and is not treated as a successful archive listing unless the body contains zip links.",
        "- Each country zip’s `README.html` is the in-archive license statement. Preprocessing records the README hash and whether the ODbL wording is present. Raw geojson is not committed.",
        "",
        "NoiseCapture indicators are not relicensed or redefined here. `noise_level`, `laeq`, `la50`, and `lden` stay separate fields because the README and the files do not define them as one indicator.",
        "",
        "<!-- IN_ARCHIVE_NOTES_START -->",
        "In-archive notes are filled by `scripts/preprocess_datasets.py` after it reads README and guide files from the downloaded archives.",
        "<!-- IN_ARCHIVE_NOTES_END -->",
        "",
    ]
    http_dump = ((nc.get("pages") or {}).get("http_dump") or {})
    if http_dump.get("error"):
        lines.extend(["## Recorded HTTP dump error", "", "```", str(http_dump.get("error")), "```", ""])
    atomic_write_text(path, "\n".join(lines))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download UrbanNoiseLab source datasets.")
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--resume", action="store_true", help="Continue partial files with HTTP Range when the server allows it.")
    parser.add_argument("--recheck", action="store_true", help="Recompute hashes for files that already match the remote size.")
    parser.add_argument("--preprocess", action="store_true", help="Run preprocessing after downloads finish.")
    parser.add_argument("--min-free-gb", type=float, default=20.0)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    path = manifest_path(data_dir)
    manifest = load_manifest(path, sys.argv if argv is None else ["download_datasets.py", *argv])
    store = ManifestStore(path, manifest)
    raw_root = data_dir / "raw"
    min_free = int(args.min_free_gb * (1024**3))
    selected = ("yjmob100k", "geolife", "noisecapture") if args.dataset == "all" else (args.dataset,)
    if "yjmob100k" in selected:
        download_yjmob(store, raw_root, args.resume, args.recheck, min_free)
    if "geolife" in selected:
        download_geolife(store, raw_root, args.resume, args.recheck, min_free)
    if "noisecapture" in selected:
        download_noisecapture(store, raw_root, args.resume, args.recheck, min_free, args.workers)
    docs = Path("docs/data")
    if not docs.is_absolute():
        docs = Path.cwd() / docs
    render_download_report(store.manifest, docs / "dataset_download_report.md")
    render_license_doc(store.manifest, docs / "dataset_licenses.md")
    print(json.dumps({"event": "manifest", "path": str(path), "files": len(store.manifest["files"])}), flush=True)
    if args.preprocess:
        from preprocess_datasets import run_preprocess

        run_preprocess(args.dataset, data_dir, args.resume, args.recheck)
    failed = [item for item in store.manifest["files"] if item.get("status") in {"failed", "checksum_mismatch"}]
    print(json.dumps({"event": "done", "failed": len(failed)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

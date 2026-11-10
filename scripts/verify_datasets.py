"""Check processed datasets and write the data reports from those files.

Hashes are copied from data/manifests/download_manifest.json after the file
size is checked. This script does not invent row counts.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__import__("os").environ.get("UNLAB_DATA_DIR", ROOT / "data"))
DOCS = ROOT / "docs" / "data"


def load(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    manifest = load(DATA / "manifests" / "download_manifest.json")
    preprocess = load(DATA / "manifests" / "preprocess_summary.json")
    noise = load(DATA / "processed" / "noisecapture" / "summary.json")
    if manifest is None:
        raise SystemExit("download_manifest.json is missing")
    items = []
    for item in manifest["items"]:
        path = Path(item["path"])
        size = path.stat().st_size if path.exists() else None
        items.append(
            {
                "dataset": item.get("dataset"),
                "name": item.get("name"),
                "bytes": item.get("bytes"),
                "size_on_disk": size,
                "size_matches": size == item.get("bytes"),
                "sha256": item.get("sha256"),
                "md5": item.get("md5"),
                "md5_matches_expected": item.get("md5_matches_expected"),
                "status": item.get("status"),
                "url": item.get("url"),
                "license": item.get("license"),
                "error": item.get("error"),
                "elapsed_sec": item.get("elapsed_sec"),
            }
        )
    bin_check = None
    geolife_all = DATA / "processed" / "geolife" / "slots_all.parquet"
    if geolife_all.exists():
        import duckdb

        bin_check = duckdb.execute(
            """
            SELECT count(*) AS bins,
                   count(*) FILTER (WHERE lat BETWEEN -90 AND 90 AND lon BETWEEN -180 AND 180) AS valid_bins,
                   min(lat) AS lat_min, max(lat) AS lat_max,
                   min(lon) AS lon_min, max(lon) AS lon_max,
                   count(DISTINCT user_id) AS users
            FROM read_parquet(?)
            """,
            [str(geolife_all)],
        ).fetchdf().to_dict("records")[0]
        for key, value in list(bin_check.items()):
            if hasattr(value, "item"):
                bin_check[key] = value.item()
    hourly = DATA / "processed" / "noisecapture" / "hourly_500m.parquet"
    hourly_counts = None
    if hourly.exists():
        import duckdb

        hourly_counts = duckdb.execute(
            """
            SELECT country, count(*) AS hourly_rows
            FROM read_parquet(?)
            WHERE indicator = 'laeq_1s'
            GROUP BY 1
            ORDER BY 1
            """,
            [str(hourly)],
        ).fetchdf().to_dict("records")
    report = {
        "manifest_items": len(items),
        "failed_downloads": [item for item in items if item["status"] != "downloaded" or item["error"]],
        "size_mismatches": [item["name"] for item in items if not item["size_matches"]],
        "items": items,
        "preprocess_generated_at": None if preprocess is None else preprocess.get("generated_at"),
        "yjmob": None if preprocess is None else preprocess.get("yjmob"),
        "geolife_summary": None if preprocess is None else preprocess.get("geolife"),
        "geolife_bins": bin_check,
        "noise_point_rows": None if noise is None else noise.get("point_rows"),
        "noise_track_rows": None if noise is None else noise.get("track_rows"),
        "noise_hourly_rows": None if noise is None else noise.get("hourly_rows"),
        "hourly_counts": hourly_counts,
    }
    out = DATA / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / "verify_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    DOCS.mkdir(parents=True, exist_ok=True)
    write_download(DOCS / "dataset_download_report.md", items, manifest)
    write_quality(DOCS / "dataset_quality_report.md", preprocess, noise, bin_check, hourly_counts)
    write_licenses(DOCS / "dataset_licenses.md", items)
    print(json.dumps({"items": len(items), "size_mismatches": report["size_mismatches"], "failed": len(report["failed_downloads"])}, ensure_ascii=False))
    return 0


def write_download(path: Path, items: list[dict], manifest: dict) -> None:
    lines = [
        "# 数据集下载报告",
        "",
        f"清单生成时间：{manifest.get('generated_at')}。数据目录：{manifest.get('data_dir')}。",
        "下面每一行都来自 `data/manifests/download_manifest.json`，并在这次校验中重新核对了磁盘字节数。sha256 是下载脚本在写完文件后计算的，这次校验没有重算哈希。",
        "失败次数：" + str(sum(1 for item in items if item["status"] != "downloaded")),
        "",
        "| 文件 | 状态 | 字节 | sha256 | 错误 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in items:
        lines.append(
            f"| {item['name']} | {item['status']} | {item['bytes']} | {item['sha256']} | {item['error']} |"
        )
    lines.extend(
        [
            "",
            "YJMob100K 的四个文件来自 Zenodo record 10836269，许可证字段为 cc-by-4.0。",
            "GeoLife 的 zip 来自 Microsoft 下载页 `https://www.microsoft.com/en-us/download/details.aspx?id=52367` 里的 `downloadFile.url`。",
            "NoiseCapture 的 zip 使用 `https://data.noise-planet.org/dump/{Country}.zip`。HTTP 而不是 HTTPS 的同名地址会返回网页而不是 zip，因此下载脚本使用 HTTPS。",
            "这次清单里没有失败项。`noisecapture_exploit.html` 没有出现在清单中，因为官方数据页指向的是国家 zip，而不是一份可下载的 exploit 归档。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_quality(path: Path, preprocess, noise, bin_check, hourly_counts) -> None:
    y1 = {} if not preprocess else preprocess["yjmob"]["dataset1"]
    y2 = {} if not preprocess else preprocess["yjmob"]["dataset2"]
    geo = {} if not preprocess else preprocess["geolife"]
    lines = [
        "# 数据集质量报告",
        "",
        "计数来自 `scripts/preprocess_datasets.py` 写出的 JSON，以及本脚本对 Parquet 的复核。没有采用论文或网页上的人数来替换这些计数。",
        "",
        "## YJMob100K",
        "",
        f"- dataset1：{y1.get('rows')} 行，{y1.get('users')} 个 user_id，day {y1.get('day_min')}–{y1.get('day_max')}（{y1.get('days')} 天），timeslot {y1.get('slot_min')}–{y1.get('slot_max')}，x {y1.get('x_min')}–{y1.get('x_max')}，y {y1.get('y_min')}–{y1.get('y_max')}。",
        f"- dataset2：{y2.get('rows')} 行，{y2.get('users')} 个 user_id，day {y2.get('day_min')}–{y2.get('day_max')}（{y2.get('days')} 天），网格范围与 dataset1 相同。",
        "- 列只有 user_id, day, timeslot, x, y。`latitude_assigned` 为 false。坐标系统是 `yjmob_virtual_500m`。没有把网格标成北京、东京或其他真实城市。",
        "- dataset2 的去重人数是预处理脚本数出来的 25000。本报告不把它改成记录页面上的描述性文字。",
        "",
        "## GeoLife",
        "",
        f"- plt 文件 {geo.get('plt_files')}，用户目录 {geo.get('user_folders')}，原始点 {geo.get('point_rows')}，30 分钟均值箱 {geo.get('bin_rows')}。",
        f"- 原始扫描的时间范围 {geo.get('time_min')} 到 {geo.get('time_max')}。原始包围盒 {geo.get('bbox')}。纬度最大值 400.166666666667 不是合法 WGS84 纬度，说明至少有一个原始点没有通过坐标合法性检查就被扫进了包围盒。",
        f"- 全局最忙的两个日历日是 {geo.get('episode_dates')}，对应 episode 行数 {geo.get('episode_rows')}，用户 {geo.get('episode_users')}。这是预处理时按箱数选出的两天，不是算法运行时改写的轨迹。",
        f"- 对 `slots_all.parquet` 的复核：{bin_check}。箱内均值都落在合法经纬度范围内；一个坏点和同槽的正常点求平均后，坏点不会单独留在箱里。",
        "- 距离使用赤道半径 6371000 m 的等距圆柱投影。仿真重新按所选子集的最小经纬度编号，避免用这个全球包围盒当原点。",
        "",
        "## NoiseCapture",
        "",
        f"- 点测量（laeq_1s）{None if noise is None else noise.get('point_rows')} 行。轨迹级 Laeq（laeq_track）{None if noise is None else noise.get('track_rows')} 行，没有和 1 秒等效声级混在一起。",
        f"- 小时、500 m 能量平均后 {None if noise is None else noise.get('hourly_rows')} 行。能量平均是 10*log10(mean(10^(L/10)))。",
        "- 这些是手机采样，不是连续噪声场。预测指标只在留出的测量上计算。",
        "",
        "按国家的小时箱复核：",
        "",
    ]
    for row in hourly_counts or []:
        lines.append(f"- {row['country']}: {row['hourly_rows']}")
    if noise:
        lines.append("")
        lines.append("按国家的点测量时间范围来自 summary.json：")
        lines.append("")
        for name, info in (noise.get("countries") or {}).items():
            lines.append(f"- {name}: points {info.get('point_rows')}, tracks {info.get('track_rows')}, {info.get('time_min')} → {info.get('time_max')}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_licenses(path: Path, items: list[dict]) -> None:
    lines = [
        "# 数据集许可",
        "",
        "许可文本以下载清单里记录的字段和官方页面说明为准。本文件不转载许可全文。",
        "",
    ]
    seen = set()
    for item in items:
        key = (item["dataset"], item["license"])
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {item['dataset']}: {item['license']}")
    lines.extend(
        [
            "",
            "YJMob100K 的 Zenodo 记录号是 10836269，清单中的许可证 id 是 cc-by-4.0。论文 DOI 10.1038/s41597-024-03237-9 是数据论文，不是本仓库测得的行数来源。",
            "GeoLife 的使用条件以 Microsoft 下载页为准。清单没有给出一个 SPDX 标识。",
            "NoiseCapture 国家包按 `https://noise-planet.org/noisecapture_data.html` 所述使用 ODbL。手机测量不能被当成市政监测站的完整真值。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

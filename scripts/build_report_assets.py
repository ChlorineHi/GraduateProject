"""Figures for the full system report. Numbers come from local parquet and JSON."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/final-report/assets"
OUT.mkdir(parents=True, exist_ok=True)
font_manager.fontManager.addfont("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc")
plt.rcParams["font.family"] = "WenQuanYi Micro Hei"
plt.rcParams["axes.unicode_minus"] = False

manifest = []


def save(fig, name: str, source: str, caption: str) -> None:
    path = OUT / name
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    manifest.append({"file": f"docs/final-report/assets/{name}", "source": source, "caption": caption})
    print("wrote", name)


def yjmob() -> None:
    con = duckdb.connect()
    rows = con.execute(
        """
        select x, y, count(*) n
        from read_parquet('data/processed/yjmob/dataset1.parquet')
        where day = 0
        group by 1, 2
        """
    ).fetchall()
    grid = np.zeros((201, 201), dtype=np.float64)
    for x, y, n in rows:
        grid[int(y), int(x)] = n
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    im = ax.imshow(np.log10(grid + 1), origin="lower", cmap="YlOrBr")
    ax.set_title("YJMob100K Dataset 1，第 0 天到访次数（log10）")
    ax.set_xlabel("匿名网格 x（1–200，不是经纬度）")
    ax.set_ylabel("匿名网格 y")
    fig.colorbar(im, ax=ax, label="log10(次数+1)")
    save(fig, "fig_yjmob_day0_heatmap.png", "data/processed/yjmob/dataset1.parquet", "Dataset 1 第 0 天网格到访")

    tod = con.execute(
        """
        select timeslot, count(*) n
        from read_parquet('data/processed/yjmob/dataset1.parquet')
        group by 1 order by 1
        """
    ).fetchall()
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.bar([t for t, _ in tod], [n / 1e6 for _, n in tod], color="#3d6b58")
    ax.set_title("YJMob100K Dataset 1，全部 75 天的时间片记录数")
    ax.set_xlabel("30 分钟时间片编号")
    ax.set_ylabel("百万条")
    save(fig, "fig_yjmob_timeslot.png", "data/processed/yjmob/dataset1.parquet", "Dataset 1 时间片直方图")


def geolife() -> None:
    con = duckdb.connect()
    pts = con.execute(
        """
        select lon, lat, user_id
        from read_parquet('data/processed/geolife/slots_all.parquet')
        where lat between 39.4 and 40.6 and lon between 115.7 and 117.2
        """
    ).fetchall()
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    if pts:
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=4, c="#1f4e79", alpha=0.35, linewidths=0)
    ax.set_title(f"GeoLife 北京附近半小时箱（{len(pts)} 个，已去掉纬度>90 的坏点）")
    ax.set_xlabel("经度 WGS84")
    ax.set_ylabel("纬度 WGS84")
    ax.set_aspect("equal", adjustable="box")
    save(fig, "fig_geolife_beijing.png", "data/processed/geolife/slots_all.parquet", "GeoLife 北京附近轨迹箱")


def noise() -> None:
    con = duckdb.connect()
    countries = con.execute(
        """
        select country, count(*) n, median(level_db) med
        from read_parquet('data/processed/noisecapture/hourly_500m.parquet')
        group by 1 order by n desc
        """
    ).fetchall()
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    ax.barh([c[0] for c in countries][::-1], [c[1] for c in countries][::-1], color="#8c4a32")
    ax.set_title("本分支小时箱中的 NoiseCapture 国家（不是 227 国全量）")
    ax.set_xlabel("500 米小时箱数量")
    save(fig, "fig_noise_countries.png", "data/processed/noisecapture/hourly_500m.parquet", "进入本分支处理结果的国家")

    sample = con.execute(
        """
        select longitude, latitude, level_db
        from read_parquet('data/processed/noisecapture/hourly_500m.parquet')
        where country = 'France' and level_db between 35 and 95
        using sample 8000
        """
    ).fetchall()
    fig, ax = plt.subplots(figsize=(7.2, 6.0))
    sc = ax.scatter(
        [p[0] for p in sample],
        [p[1] for p in sample],
        c=[p[2] for p in sample],
        s=6,
        cmap="magma",
        alpha=0.8,
        linewidths=0,
    )
    fig.colorbar(sc, ax=ax, label="laeq_1s 能量平均，dB")
    ax.set_title(f"法国 NoiseCapture 小时箱抽样（{len(sample)}，只画 35–95 dB）")
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    save(fig, "fig_noise_france.png", "data/processed/noisecapture/hourly_500m.parquet", "法国小时箱空间分布")

    hours = con.execute(
        """
        select (hour_epoch % 24) h, median(level_db) med, count(*) n
        from read_parquet('data/processed/noisecapture/hourly_500m.parquet')
        where country = 'France' and level_db between 20 and 110
        group by 1 order by 1
        """
    ).fetchall()
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.plot([h for h, _, _ in hours], [m for _, m, _ in hours], marker="o", color="#8c4a32")
    ax.set_title("法国小时箱的小时中位数（20–110 dB，不是城市全域真值）")
    ax.set_xlabel("UTC 小时取模，未做时区校正")
    ax.set_ylabel("中位数 dB")
    save(fig, "fig_noise_france_hour.png", "data/processed/noisecapture/hourly_500m.parquet", "法国小时变化")


def synthetic() -> None:
    from urbannoise.world import build_world

    world = build_world(seed=7, height=16, width=16, n_days=1, slots_per_day=24, n_human=4, n_machine=1, scenario="complex", prior_samples=8)
    field = world.laeq[8].reshape(world.height, world.width)
    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    im = ax.imshow(field, origin="lower", cmap="YlOrRd", vmin=32, vmax=80)
    ax.set_title("合成复杂场景，第 8 个时间片的干净真值")
    ax.set_xlabel("网格 x")
    ax.set_ylabel("网格 y")
    fig.colorbar(im, ax=ax, label="dB")
    save(fig, "fig_synthetic_truth.png", "urbannoise.world.build_world seed=7 scenario=complex", "合成真值，只用于评估")


def experiments() -> None:
    payload = json.loads((ROOT / "experiments/results/phase2/real_runs.json").read_text())
    labels = []
    series = {m: [] for m in ["nearest", "min_cost", "mupsa", "eer_reach", "reach_random"]}
    for block in payload["mobility"]:
        labels.append(block["subset"].replace("yjmob_", "").replace("dataset", "d"))
        for m in series:
            series[m].append(block["mae_available_at_t"][m]["mean"])
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    x = np.arange(len(labels))
    width = 0.15
    for i, (m, vals) in enumerate(series.items()):
        ax.bar(x + (i - 2) * width, vals, width, label=m)
    ax.set_xticks(x, labels, rotation=15)
    ax.set_ylabel("mae_available_at_t")
    ax.set_title("真实轨迹子集，预算 8，两种子平均（合成噪声场）")
    ax.legend(fontsize=8, ncol=3)
    save(fig, "fig_real_mobility_mae.png", "experiments/results/phase2/real_runs.json", "真实移动子集误差")

    noise = payload["noise_holdout"]
    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    names = list(noise)
    ax.bar(names, [noise[n]["mae"] for n in names], color="#3d6b58", label="MAE")
    ax.plot(names, [noise[n]["rmse"] for n in names], "o-", color="#8c4a32", label="RMSE")
    ax.set_title("NoiseCapture 时间留出，IDW，不是全域真值")
    ax.set_ylabel("dB")
    ax.legend()
    save(fig, "fig_noise_holdout.png", "experiments/results/phase2/real_runs.json", "真实噪声留出误差")


def copy_existing() -> None:
    pairs = [
        ("docs/uml/png/05_系统总体架构图.png", "uml_architecture.png", "docs/uml/diagrams.puml", "总体架构"),
        ("docs/uml/png/01_系统用例图.png", "uml_usecase.png", "docs/uml/diagrams.puml", "系统用例"),
        ("docs/uml/png/07_核心类图.png", "uml_class.png", "docs/uml/diagrams.puml", "核心类"),
        ("docs/uml/png/10_采样执行时序图.png", "uml_sequence.png", "docs/uml/diagrams.puml", "采样时序"),
        ("docs/uml/png/11_动态重规划时序图.png", "uml_replan.png", "docs/uml/diagrams.puml", "重规划"),
        ("docs/uml/png/12_数据库ER图.png", "uml_er.png", "docs/uml/diagrams.puml", "ER"),
        ("docs/uml/png/13_系统部署图.png", "uml_deploy.png", "docs/uml/diagrams.puml", "部署"),
        ("docs/uml/png/14_数据处理流程图.png", "uml_dataflow.png", "docs/uml/diagrams.puml", "数据流"),
        ("docs/uml/png/15_算法工作流程图.png", "uml_algorithm.png", "docs/uml/diagrams.puml", "算法流程"),
        ("docs/uml/png/08_任务发布活动图.png", "uml_publish.png", "docs/uml/diagrams.puml", "任务发布"),
        ("docs/uml/png/09_自动任务分配活动图.png", "uml_assign.png", "docs/uml/diagrams.puml", "自动分配"),
        ("docs/screenshots/phase2/round1-login.png", "ui_login.png", "浏览器 phase2 第一轮", "登录"),
        ("docs/screenshots/phase2/round1-data.png", "ui_data.png", "浏览器 phase2 第一轮", "数据页"),
        ("docs/screenshots/phase2/round1-map-yjmob.png", "ui_map_yjmob.png", "浏览器 phase2 第一轮", "YJMob 地图"),
        ("docs/screenshots/phase2/round1-sim-yjmob.png", "ui_sim_yjmob.png", "浏览器 phase2 第一轮", "YJMob 仿真"),
        ("docs/screenshots/phase2/round1-experiments.png", "ui_experiments.png", "浏览器 phase2 第一轮", "实验页"),
        ("docs/screenshots/05-tasks.png", "ui_tasks.png", "docs/screenshots 浏览器走查", "任务发布"),
        ("docs/screenshots/06-assign.png", "ui_assign.png", "docs/screenshots 浏览器走查", "分配"),
        ("docs/screenshots/02-dashboard.png", "ui_dashboard.png", "docs/screenshots 浏览器走查", "总览"),
        ("docs/screenshots/phase2/round2-collector-map.png", "ui_collector.png", "浏览器 phase2 第二轮", "采集者"),
        ("docs/screenshots/phase2/round2-data-mobile.png", "ui_mobile.png", "浏览器 phase2 第二轮", "移动端数据页"),
        ("docs/screenshots/phase2/sim-real-mobility.png", "ui_select_real.png", "cursor/phase2-simcheck 浏览器", "选择 real_mobility"),
        ("docs/screenshots/phase2/sim-fully-real-409.png", "ui_fully_real_409.png", "cursor/phase2-simcheck 浏览器", "fully_real 被拒绝"),
        ("experiments/figures/phase2/fair_main/main_regular.png", "exp_regular_mae.png", "experiments/results/phase2/fair_main/summary.json", "regular MAE"),
        ("experiments/figures/phase2/fair_main/main_complex.png", "exp_complex_mae.png", "experiments/results/phase2/fair_main/summary.json", "complex MAE"),
        ("experiments/figures/phase2/fair_main/ablation_mae.png", "exp_ablation.png", "experiments/results/phase2/fair_main/summary.json", "消融"),
        ("experiments/figures/phase2/fair_main/cost_mae_regular.png", "exp_cost.png", "experiments/results/phase2/fair_main/summary.json", "成本与误差"),
        ("experiments/figures/phase2/fair_main/bandit_reward.png", "exp_bandit.png", "experiments/results/phase2/fair_main/summary.json", "LinUCB 回报"),
        ("experiments/figures/main/robustness_mupsa.png", "exp_legacy_robust.png", "experiments/results/main 旧协议", "旧协议鲁棒性，不可与新协议直接比"),
    ]
    for src, name, source, caption in pairs:
        path = ROOT / src
        if not path.exists():
            print("missing", src)
            continue
        shutil.copyfile(path, OUT / name)
        manifest.append({"file": f"docs/final-report/assets/{name}", "source": source, "caption": caption})


def main() -> None:
    yjmob()
    geolife()
    noise()
    synthetic()
    experiments()
    copy_existing()
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("assets", len(manifest))


if __name__ == "__main__":
    main()

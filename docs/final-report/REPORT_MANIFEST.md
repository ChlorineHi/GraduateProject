# 报告索引

报告名称：人机混合城市噪音预测采样与智能任务分配系统——完整系统设计、算法研究与实验验证报告。

| 文件 | 作用 |
| --- | --- |
| docs/final-report/UrbanNoiseLab_完整系统报告.md | Markdown 源 |
| docs/final-report/UrbanNoiseLab_完整系统报告.pdf | 排版 PDF，文泉驿微米黑。2026-11-10 终稿复核渲染为 55 页 |
| docs/final-report/UrbanNoiseLab_完整系统报告.docx | 可编辑 Word。终稿复核嵌入 44 张图，13 张表 |
| docs/final-report/assets/ | 正文引用的图 |
| scripts/render_report.py | Markdown 到 PDF |
| scripts/render_docx.py | Markdown 到 DOCX |
| scripts/build_report_assets.py | 从 parquet 和已有图生成 assets |

PDF 页数以渲染脚本打印的 `pages=` 为准。2026-11-10 终稿复核是 55 页。正文图片标记 44 处，DOCX 嵌入 44 张。新增的 4 张是当前系统的浏览器复核，不是为了凑页数。页数不是目标。

## 图与来源

热力图、国家分布、法国地图、小时曲线、合成真值、真实轨迹 MAE、噪声留出、鲁棒性和耗时图由 `scripts/build_report_assets.py` 在本机 parquet 或结果 JSON 上现算。任务状态图读取 `domain.TRANSITIONS`。UML 与界面截图是仓库里已有文件的副本，不是重新摆拍。

| 资源 | 追溯 |
| --- | --- |
| fig_yjmob_day0_heatmap.png、fig_yjmob_timeslot.png | data/processed/yjmob/dataset1.parquet |
| fig_geolife_beijing.png | data/processed/geolife/slots_all.parquet，纬度 39.4–40.6、经度 115.7–117.2 |
| fig_noise_*.png | data/processed/noisecapture/hourly_500m.parquet |
| fig_synthetic_truth.png | urbannoise.world.build_world，seed 7，complex，只作示意 |
| exp_regular_mae.png 等 fair 图 | experiments/figures/phase2/fair_main，数字在 summary.json |
| fig_real_mobility_mae.png、fig_noise_holdout.png | experiments/results/phase2/real_runs.json |
| fig_robust_fair.png | experiments/results/phase2/robust_fair/results.json |
| fig_runtime.png | experiments/results/phase2/timing.json |
| ui_sim_yjmob.png、ui_map_yjmob.png、ui_data.png、ui_login.png、ui_experiments.png | scripts/shoot_phase2.mjs 对活动 API 的第一轮，10 个 YJMob 用户 |
| ui_select_real.png、ui_fully_real_409.png | simcheck 分支。real_mobility 那次是夹具回退，不是全量 YJMob。fully_real 是 409 |
| ui_final_refused.png、ui_final_yjmob.png、ui_final_assign.png、ui_final_step.png | 2026-11-10 `scripts/shoot_final_demo.mjs`，本机 YJMob parquet 的 10 人窗口，不是夹具 |
| uml_*.png | docs/uml/png |

simcheck 的截图不能当作 PR #2 已经跑完下载数据的证据。YJMob 界面证据是 round1 的两张图。

## 数字

| 数字 | 文件 |
| --- | --- |
| 合成 MAE、成功次数、消融逐种子 | experiments/results/phase2/fair_main/summary.json。其中 bandit 行是到达门控修订前 |
| 修订后的 LinUCB | experiments/results/phase2/bandit_reach_gate/results.json。不覆盖 fair_main |
| 协议名称 mae_available_at_t，列名仍为 mae_causal | 同文件的 protocol |
| 真实窗口的用户、行数、坐标系统 | experiments/results/phase2/real_runs.json 的 worlds |
| 法国 MAE 18.260、R² −0.352；卢森堡 MAE 15.524、R² −0.432 | 同文件 noise_holdout |
| YJMob 111535175 / 100000 与 29389749 / 25000 | docs/data/full_archive/dataset_quality_report.md |
| GeoLife 18670 plt、182 用户、24876978 点 | data/processed/geolife/summary.json |
| 接受 24173770、拒绝 703208 | 同上质量报告，属于那一次全量预处理 |
| NoiseCapture 227 国点要素 158222603，lden 全 0 | 同上质量报告 |
| 本机 16 国点表 62293431，法国点 29116920 | 本机 points_laeq_1s.parquet 的 DuckDB 计数 |
| 小时箱 204121，level 最小 −5.162、最大 147.359 | hourly_500m.parquet |
| 鲁棒性 135 回合，墙钟 0.980 秒 | robust_fair/results.json |
| 小网格回合约 7.6–11.0 毫秒 | timing.json |
| 测试 25 passed，1 warning，5.00 秒 | 2026-11-10 终稿复核。新增 LinUCB 不可达、GeoLife 非法坐标、缺失数据不切换世界、重置恢复预算 |

公平主实验没有打开 robustness。第 9.8 节是 sidecar，不覆盖 fair_main。

## 公式与代码

| 公式 | 代码 |
| --- | --- |
| 0.55 时段频率 + 0.45 转移滚动 | predictors.py MobilityFit.distribution |
| IDW 能量域，k=8，幂 2，时间 0.55，用地 3.5，标准差裁剪 0.35–15 | predictors.py predict_idw |
| 方差下降 v²/(v+r) | predictors.py expected_error_reduction |
| MU-PSA 权重 1.0、0.65、0.25、0.8 | predictors.py combine_value |
| eer_reach 分数与 0.22 到达阈值、0.35 成本 | assignment.py |
| 成功条件是轨迹格相等且接受 | experiment.py step_campaign |
| 状态机 | domain.py TRANSITIONS |

## 没有写进正文的图

assets 里如果有 exp_legacy_robust.png，它来自第一阶段的不公平种子，正文没有引用。不要把它和第 9.8 节放在一起比较。

## 测试与未验证

本次 pytest：25 passed。`npm run build` 成功。浏览器脚本 `scripts/shoot_final_demo.mjs` 退出码 0，截图在 `docs/screenshots/final/`。Windows ps1 没有执行，本环境也没有 PowerShell 解析器。

# Phase II 完成度审计

这份审计只记录本分支上已经核对过的事实。它不表示论文获奖，也没有把任何一项写成“已获优秀论文”。

评级只用这四档：Passed、Partially Passed、Failed、Not Verified。

| 项目 | 评级 | 依据 |
| --- | --- | --- |
| PR #1 以普通合并进入 main | Passed | `gh pr merge 1 --repo ChlorineHi/GraduateProject --merge` 退出码 0。随后 `gh pr view` 状态为 MERGED，merge commit `db54ad6ed66a780971d46fd1148286d9bd1a4cd5`。没有 force-push。 |
| 真实下载与清单 | Passed | `data/manifests/download_manifest.json` 有 21 个文件，状态都是 downloaded。`scripts/verify_datasets.py` 复核字节数，`size_mismatches` 为空，`failed` 为 0。原始压缩包和 Parquet 没有进 git。 |
| YJMob 不标成真实城市、不赋 WGS84 | Passed | 预处理标记 `latitude_assigned=false`、`coordinate_system=yjmob_virtual_500m`。测试 `test_yjmob_source_positions_match_and_are_not_wgs84` 通过。地图图例写匿名虚拟网格。 |
| 公平协议与共享环境 | Passed | `environment_seed` 忽略预算和方法。测试 `test_shared_environment_hash_across_methods` 与 `test_environment_seed_ignores_budget_and_method` 通过。旧结果目录没有被覆盖。 |
| 未来信息隔离 | Passed | `test_decision_does_not_read_future_truth_or_future_tracks` 与 `test_collector_cannot_read_future_trajectory_slots` 通过。采集者地图截图没有“评估真值”开关。 |
| 真实轨迹进入仿真 | Passed | `test_real_trajectory_cell_matches_source_frame`、`test_yjmob_source_positions_match_and_are_not_wgs84`、`test_geolife_subset_uses_real_bins` 通过。浏览器重置后状态行是 `real_mobility` / `YJMob100K` / 用户 10。 |
| 真实噪声预测 | Passed | `test_real_noise_prediction_reads_noise_parquet_not_synthetic_demo` 与 `test_real_noise_endpoint_does_not_fall_back_to_synthetic` 通过。France 小时箱留出 MAE 18.2598、RMSE 22.4131、R² -0.3516。这不是全城场误差。 |
| MU-PSA 在每个预算都赢 | Failed | 公平协议 complex 预算 4 和 12 的最低是 reach_random。regular 三个预算的最低是 eer_reach，不是 mupsa。旧协议 regular 预算 8 上 uncertainty 低于 mupsa。 |
| eer_reach 在每个设定都赢 | Failed | 合成 complex 预算 4 和 12 没有赢。YJMob dataset1 最低是 min_cost。dataset2 早期最低是 random，eer_reach 最高。dataset2 第 60–61 天最低是 nearest，eer_reach 最高。GeoLife 最低是 min_cost。消融里 `eer_no_accept` 低于完整式子，`eer_no_cost` 与完整式子相同。这些负结果保留着，没有再调 λ。 |
| 空间协方差形式的误差下降 | Failed | 没有实现。在线预测是 IDW 加启发式标准差，不是高斯过程协方差。`eer_reach` 只更新被选中的一格。 |
| Fully-Real 联合回合 | Failed | `overlap_report` 的 feasible 为 false：NoiseCapture 各国时间都晚于 GeoLife 的 2012-07-27，而且原始包围盒跨度过大并含纬度 400.17。没有拼接。 |
| 文献 | Partially Passed | CDRI landscape `20261110-013339-joint-sampling-location-and-pa` 退出码 0，537 条去重书目。四篇书目来自本地节点且标为 Verified Fact。全局阅读账本是空的，摘录没有升成全文方法证明。 |
| 非 Docker 的 Linux 运行 | Passed | 已执行 `scripts/setup_linux.sh`、`scripts/test_linux.sh`、修补后的 `scripts/start_linux.sh`（`/dev/tcp` 探测）和带 `pkill` 回退的 `scripts/stop_linux.sh`。没有安装 Docker。compose 与 Dockerfile 标为 UNUSED。 |
| Windows 脚本 | Not Verified | `scripts/setup_windows.ps1`、`start_windows.ps1`、`test_windows.ps1`、`stop_windows.ps1` 已写入。这台机器没有 PowerShell，没有执行，也没有用 PowerShell 解析器做语法检查。 |
| 界面切换数据源 | Passed | 两轮浏览器操作写在 `docs/screenshots/phase2/`。数据页列出清单中的文件名和字节。仿真重置切换到 YJMob 再回到 Synthetic。实验页读取 phase2 的 summary，不画旧协议曲线。390×844 视口下数据页不再把整页撑到 1105 px。 |
| 测试 | Passed | 最后一次 `PYTHONPATH=src .venv/bin/python -m pytest -q --tb=line` 是 21 passed、1 个 Starlette/httpx 弃用警告，用时 4.04s。没有为了凑数跳过已存在的 YJMob 或 GeoLife 文件。 |
| Phase II 报告与 PDF | Passed | Markdown 在 `docs/final-report/UrbanNoiseLab_系统完整报告_PhaseII.md`，数字与 `summary.json`、`real_runs.json` 一致。PDF 由 `scripts/render_report.py` 写出，10 页。抽查见文末。这不是获奖材料。 |
| DOCX | Not Verified | 没有运行可用的 DOCX 转换器，因此没有 DOCX。 |
| 获奖 | Not Verified | 没有申报，也没有结果。本文件不把系统写成获奖论文。 |

## 仍然不完整的部分

- Fully-Real 没有联合回合，因为时间和地理不重叠。
- `eer_reach` 没有空间更新，而且在真实移动子集上没有赢。
- GeoLife 没有用合法性过滤重解析全部 plt。坏点只在原始包围盒里被记下来。
- NoiseCapture 的 exploit 页面没有进入清单。HTTP 的 dump 地址返回的是 HTML，实际文件来自 HTTPS。
- Windows 脚本没有在 Windows 上执行。
- 阅读账本为空。

## PDF 抽查

命令：`PYTHONPATH=src .venv/bin/python scripts/render_report.py docs/final-report/UrbanNoiseLab_系统完整报告_PhaseII.md docs/final-report/UrbanNoiseLab_系统完整报告_PhaseII.pdf`

字体是 `/usr/share/fonts/truetype/wqy/wqy-microhei.ttc`。最后一次输出 10 页、863766 字节。`pdftotext -layout` 按出现顺序读到图 1 至图 8，以及 `10.3730±1.9314`、`9.2482±1.6678`、`18.2598`、`111535175`、`21 passed`。没有“缺少图片”。`pdftoppm` 抽查了重排图号之前的第 1、2、5、6、7、10 页：中文没有成方框，图和表落在版心内，图注在图下方。重排图号后只改了图注编号，版式参数没变，并再次用 `pdftotext` 核对了数字。没有生成 DOCX。

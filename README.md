# UrbanNoiseLab

人机混合城市噪音预测采样与智能任务分配系统。这是北京邮电大学软件工程毕业设计的可运行实现。

系统把移动参与者的可达性、噪声预测的信息价值和采样成本放进同一次动态任务分配。它不是新的理论最优算法，也没有使用 Docker。

## 主要功能

- 管理员、任务发布者、采集参与者三种角色，任务从草稿走到完成。
- 合成城市、YJMob100K、GeoLife、NoiseCapture 的数据模式。真实文件缺失时返回 409，不把当前世界改成合成轨迹。
- 噪声地图、轨迹、任务发布、分配、仿真步进和实验曲线。
- 分配方法：random、nearest、greedy、uncertainty、min_cost、MU-PSA、EER-Reach、LinUCB。

## 系统架构

浏览器是 React + TypeScript + Vite。接口是 FastAPI。数据库是本机 SQLite。预测、可达性和分配在 `src/urbannoise/`。原始数据放在 `data/raw` 与 `data/processed`，这两处被 Git 忽略。

## 核心算法

分配在每个决策时点只看当时已经可见的轨迹和观测，为下一个时间片选择参与者。

- 最近距离只看当前位置，下一片到不了的人仍可能接到任务。
- 移动预测给出到达概率。到达概率为 0 的配对不会被分配。
- EER-Reach 用的是被选中格子自己的一步方差下降，再乘到达概率和接受概率，并减去成本。它不是整张地图的期望误差下降，也没有格子之间的协方差。
- LinUCB 在到达概率大于 0 的配对上做上下文选择。它不是 PPO。
- 预算在分配时扣下。仿真任务失败后退回剩余预算，成功才计入已花费。

较高的任务完成率不等于较低的地图误差。多采到的点如果落在已经比较确定的区域，全局 MAE 可以不变，甚至变差。

## 数据来源

| 数据 | 坐标 | 在系统里扮演什么 |
| --- | --- | --- |
| Synthetic Demo | 虚拟网格，无经纬度 | 可控合成轨迹和合成噪声真值。只有用户选择这一模式时才使用。 |
| YJMob100K | 匿名虚拟 500 m 网格 | 真实人类移动。不能标成北京或东京。实验窗口是 10 人，不是全部 10 万用户。 |
| GeoLife | WGS84 | 真实 GPS 轨迹。非法纬度和超速跳跃在预处理和加载时丢弃。 |
| NoiseCapture | WGS84 | 真实手机噪声观测。`lden` 全为 0，预测使用能量平均后的小时箱。 |

真实轨迹和真实噪声没有重叠到同一时间、同一地点。Fully-Real 会返回 409。这是数据事实，不是演示故障。

原始 parquet 和 zip 不在 GitHub 上。克隆仓库只能阅读清单、报告和实验结果。要切换真实数据，需要本机已经有 `data/processed`，或按下面的恢复命令重新得到它。代理工作区里的大文件会随环境结束消失。

## 项目截图

终稿浏览器复核在 `docs/screenshots/final/`。下面四张也放进了系统报告：

- `docs/screenshots/final/04-fully-real-refused.png`：Fully-Real 被拒绝，世界没有被换掉。
- `docs/screenshots/final/05-sim-yjmob.png`：YJMob100K 的 10 人子集，噪声仍是合成场。
- `docs/screenshots/final/09-assign-eer.png`：EER-Reach 分配，到达概率来自接口。
- `docs/screenshots/final/10-sim-stepped.png`：推进后的预算、失败退款和成功测量。

`docs/screenshots/` 里更早的 simcheck 图片如果出现夹具回退，只能说明当时的失败提示，不能当作全量数据。

## Windows 启动

不使用 Docker。这些脚本在 Linux 上只做过阅读和路径审查，没有在 Windows 11 上执行。

```powershell
powershell -NoProfile -Command "Get-Command py, python, npm"
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
$env:UNLAB_DATA_DIR = "D:\data\urbannoise"   # 可选，默认是仓库下的 data
powershell -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1
```

浏览器打开脚本打印的地址，默认是 http://127.0.0.1:5173 。API 默认是 http://127.0.0.1:8000 。

停止：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop_windows.ps1
```

若网页仍开着，说明 npm 拉起的 node 还在。查看端口后结束对应进程：

```powershell
Get-NetTCPConnection -LocalPort 5173,8000 -State Listen
```

测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_windows.ps1
```

语法检查可以在真正启动之前做：

```powershell
$errors = $null
[void][System.Management.Automation.Language.Parser]::ParseFile("$pwd\scripts\start_windows.ps1", [ref]$null, [ref]$errors)
$errors
```

对 `setup_windows.ps1`、`stop_windows.ps1`、`test_windows.ps1` 重复一次。

## Linux 启动

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
npm ci --prefix apps/web
bash scripts/setup_linux.sh
UNLAB_DATA_DIR="$PWD/data" bash scripts/start_linux.sh
```

或不用脚本：

```bash
make demo
make api
```

另一个终端：

```bash
npm run dev --prefix apps/web -- --host 127.0.0.1 --port 5173
```

打开 http://127.0.0.1:5173 。停止使用 `bash scripts/stop_linux.sh`。

## 演示账号

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | admin | DemoAdmin#2026 |
| 发布者 | publisher | DemoPublish#2026 |
| 采集者 | collector | DemoCollect#2026 |

只用于本机演示。

答辩时的点击顺序、讲解词和检查表在 `docs/demo/`。建议使用 YJMob dataset1 的 10 人子集加合成噪声，算法选 eer_reach。不要现场依赖完整 NoiseCapture 库。

## 测试

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q --tb=line
npm run build --prefix apps/web
```

Windows 上对应 `scripts/test_windows.ps1`。Linux 通过不能写成 Windows 已经通过。

## 实验复现

已有结果不要重跑覆盖：

- `experiments/results/phase2/fair_main/summary.json`：公平主实验和消融。
- `experiments/results/phase2/real_runs.json`：真实轨迹。
- `experiments/results/phase2/robust_fair/results.json`：鲁棒性。
- 法国和卢森堡噪声留出数字在 `real_runs.json` 的 `noise_holdout`。

LinUCB 到达门控之后的复核是旁路文件 `experiments/results/phase2/bandit_reach_gate/results.json`。它不替换主表。主表里的 bandit 行是修订前的数字。

小规模冒烟：

```bash
make experiment-smoke
```

它写入 `experiments/results/phase2/smoke`，不覆盖主表。

## 报告

正式入口：

- `docs/final-report/UrbanNoiseLab_完整系统报告.md`
- `docs/final-report/UrbanNoiseLab_完整系统报告.pdf`
- `docs/final-report/UrbanNoiseLab_完整系统报告.docx`

`make report` 渲染的就是这三份里的 Markdown，并写出 PDF 和 DOCX。

毕业论文怎么从这份报告里取材：`docs/final-report/本科毕业论文写作指南.md`。

本轮验收结论：`docs/final-report/最终系统验收报告.md`。

下面两份是历史版本，不作为答辩入口：

- `docs/final-report/UrbanNoiseLab_系统完整报告.md`（第一阶段）
- `docs/final-report/UrbanNoiseLab_系统完整报告_PhaseII.md`（第二阶段）

## 数据恢复

已经校验通过的文件不要重复下载。清单在 `docs/data/full_archive/` 和 `data/manifests`（若本机保存过）。

```bash
python scripts/download_datasets.py --help
python scripts/preprocess_datasets.py --help
python scripts/verify_datasets.py --help
```

`.gitignore` 忽略 `data/raw/`、`data/processed/` 和 `data/external/`。不要把大型原始轨迹提交到公开仓库。

文件不在时，页面应出现“数据未切换”。此时不要把画面上的旧世界说成新选择的数据源。

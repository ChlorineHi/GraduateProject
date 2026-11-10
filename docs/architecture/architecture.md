# 架构说明

浏览器中的 React 应用通过 Vite 把 `/api` 代理到 FastAPI。业务写在 `services.py`，状态规则在 `domain.py`，算法不依赖 HTTP。

默认数据库是 SQLite 文件 `data/urbannoise.db`。新库由 SQLAlchemy `metadata.create_all` 创建。已经存在的库由 `urbannoise.migrations` 增加列，版本号写在 `schema_migrations`，不删除旧行。这不是 Alembic。大规模轨迹放在 Parquet 里，用 DuckDB 查询，不装进 SQLite。

活动仿真世界保存在 `data/worlds/active_world.npz`。其中的 `laeq` 是评估和采样用的真值。预测函数不接收这个数组。离线实验自己生成世界，不改演示数据库。

一次交互闭环是：

1. 发布者或仿真器调用分配。分配读取当前时钟 t 和 lead，只看已有观测与历史轨迹。
2. 新任务以 `origin=simulation` 写入，状态从 published 走到 assigned，预算预扣。
3. `step` 只执行 `simulation_run_id` 等于当前轮、且时间片已到的任务。
4. 人必须真的位于该网格并且接受抽签成功，才调用 `sample_measurement`。
5. 成功观测以 `simulation_feedback` 入库。失败则拒绝或失败，并在仿真来源上退款。
6. 时钟加一。下一次分配看到新观测。

手工任务走采集者接口，不会被仿真器自动执行。采集者的仿真采样同样检查人是否在格子上。

实验进程读取 `experiments/configs/*.json`。`experiments/results/main` 是旧协议归档，`run_suite` 拒绝覆盖它。公平协议写入 `experiments/results/phase2/`。页面上的曲线读 phase2 的 `summary.json`，不是写死的分数。

`resolve_world` 决定位置、预测和任务成功用哪一份数据。Synthetic 仍调用 `build_world`。Real-Mobility 把 YJMob 或 GeoLife 的已记录格子抄进轨迹。Real-Noise 只放入 NoiseCapture 观测，没有连续真值。Fully-Real 在时间和范围不能对齐时直接拒绝。

Linux 部署不使用 Docker。入口是 `scripts/start_linux.sh`。

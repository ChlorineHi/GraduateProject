# 架构说明

浏览器中的 React 应用通过 Vite 把 `/api` 代理到 FastAPI。业务写在 `services.py`，状态规则在 `domain.py`，算法不依赖 HTTP。

默认数据库是 SQLite 文件 `data/urbannoise.db`。表由 SQLAlchemy `metadata.create_all` 创建，没有单独的 Alembic 修订。这是当前的迁移方式，不是漏记的 Alembic 版本。

活动仿真世界保存在 `data/worlds/active_world.npz`。其中的 `laeq` 是评估和采样用的真值。预测函数不接收这个数组。离线实验自己生成世界，不改演示数据库。

一次交互闭环是：

1. 发布者或仿真器调用分配。分配读取当前时钟 t 和 lead，只看已有观测与历史轨迹。
2. 新任务以 `origin=simulation` 写入，状态从 published 走到 assigned，预算预扣。
3. `step` 只执行 `simulation_run_id` 等于当前轮、且时间片已到的任务。
4. 人必须真的位于该网格并且接受抽签成功，才调用 `sample_measurement`。
5. 成功观测以 `simulation_feedback` 入库。失败则拒绝或失败，并在仿真来源上退款。
6. 时钟加一。下一次分配看到新观测。

手工任务走采集者接口，不会被仿真器自动执行。采集者的仿真采样同样检查人是否在格子上。

实验进程读取 `experiments/configs/*.json`，把汇总写到 `experiments/results`，图写到 `experiments/figures`。页面上的“运行 smoke”会再启动这个进程，而不是返回写死的曲线。曲线图默认读已经生成的 main 汇总。

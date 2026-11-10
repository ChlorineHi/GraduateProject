# Phase II 初始审计

审计对象是合并进 main 的系统，提交 `db54ad6ed66a780971d46fd1148286d9bd1a4cd5`（PR #1，head 为 `1868fc3cd18766d2c576565556de00b994bdaf81`）。分类依据是阅读当时的代码，不是后来的修复。修复写在最后一节，避免把修复说成合并时就已经存在。

| 模块 | 合并时的判断 | 依据 |
| --- | --- | --- |
| dataio.py | verified | YJMob 适配器把经纬度写成空，坐标系统是虚拟 500 m。测试拒绝把它当成 WGS84。 |
| world.py | partial | `build_world` 能生成有空间相关的合成场，测试通过。它不读取外部轨迹。 |
| predictors.py | verified | `fit_mobility` 只用 `visible_until` 之前的轨迹。`predict_idw` 不接收真值数组。 |
| assignment.py | partial | 有 random、nearest、greedy、uncertainty、min_cost、mupsa、LinUCB。nearest 是当前位置最近，没有单独的可达性最近、可达性随机和可达性贪心。 |
| experiment.py | defective | `episode_seed` 含有预算和方法名的字符和。同一对比里各方法的初始观测和随机事件可以不同。指标名叫 `mae_causal`，但决策路径本身不把未来真值放进预测。 |
| services.py | defective | `rebuild_world` 固定调用 `build_world`。`safe_import` 把外部行写入数据集表，不驱动回合。 |
| api.py | partial | 登录、任务、地图和实验接口能跑通。实验归档只读 `experiments/results/main`。仿真请求没有数据源字段。采集者可以读到当前时钟之后的轨迹。 |
| apps/web | partial | 页面能完成演示闭环。仿真页不能切换真实数据源。实验曲线读旧汇总。数据页不读下载清单。 |
| tests | partial | 合并时 11 个测试通过，覆盖能量平均、状态机、未来信息隔离和 API 闭环。没有共享环境哈希测试。 |
| docs | partial | 有架构、需求和一份系统报告。报告描述的是合成演示和旧协议。 |
| experiments | verified | `experiments/results/main/summary.json` 存在。预算 8 的 regular 上 uncertainty 的 MAE 低于 mupsa，所以 MU-PSA 不是每个预算的赢家。这些文件必须保留为旧协议。 |

## 本分支上的修复

这些修复在写这份审计时已经进入工作区，并用测试或结果文件核对过：

- 环境种子不再包含方法和预算。测试名 `test_shared_environment_hash_across_methods`。
- 增加 `reach_nearest`、`reach_random`、`reach_greedy`，保留 `nearest` 作为弱基线。
- `mae_available_at_t` 与 `mae_causal` 是同一个数，协议文本写明真值不进入决策。
- `resolve_world` 让 Real-Mobility 和 Real-Noise 替换 `build_world` 的输出。Fully-Real 在不重叠时拒绝。
- 新结果目录是 `experiments/results/phase2/`。旧目录有覆盖保护。

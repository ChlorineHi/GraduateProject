# 需求说明

## 角色

| 角色 | 账号（仅演示） | 能做的事 |
| --- | --- | --- |
| 管理员 | admin / DemoAdmin#2026 | 用户、设备、参与者在线状态、导入、审计、真值层、仿真和实验 |
| 任务发布者 | publisher / DemoPublish#2026 | 创建、发布、取消、分配、仿真、核验、完成 |
| 采集参与者 | collector / DemoCollect#2026 | 只操作分配给自己的任务：接收、拒绝、开始、仿真采样或手工提交 |

密码只用于本地演示。

## 功能需求与实现

| 编号 | 需求 | 实现 |
| --- | --- | --- |
| F1 | 登录并按角色进入 | `POST /api/auth/login`，采集者进入 `/app/mine` |
| F2 | 总览使用数据库记录 | `GET /api/dashboard` |
| F3 | 虚拟网格地图，真值默认关闭 | `GET /api/map/frame` |
| F4 | 任务状态机 | `domain.py` 与 `POST /api/tasks/{id}/transition` |
| F5 | 分配算法可选 | `POST /api/assignments/run` |
| F6 | 仿真单步、暂停、重置 | `POST /api/simulation/control` |
| F7 | 预测不读未采样真值 | `predict_*` 与测试 |
| F8 | 数据源标注 Synthetic Demo | 数据集页面 |
| F9 | 实验曲线来自结果文件 | `GET /api/experiments` 读取 `experiments/results/main/summary.json` |
| F10 | 外部轨迹和噪声可导入但不相配 | `safe_import` |

## 非功能

- 演示不调用付费地图。
- 密码使用 PBKDF2-HMAC-SHA256，20 万次。
- 令牌是 HS256 JWT。开发默认密钥只用于演示，已写在 `.env.example`。
- 上传限制 20 MB，路径限制在 `data/imports`。
- 耗时实验在守护线程中运行，接口先提交数据库行再启动线程。

## 明确不做或未完成

- 不把 YJMob 网格画到真实经纬度上。
- 不把 Docker 当作支持的部署方式。
- 不把手机采样说成整座城市的连续噪声场误差。

## Phase II 补充

| 编号 | 要求 | 实现 |
| --- | --- | --- |
| P1 | 同一场景、子集、时间范围和种子共享环境 | `environment_seed` 不含方法和预算 |
| P2 | 决策只用 t 时刻已有信息 | `mae_available_at_t`，历史列名仍是 `mae_causal` |
| P3 | 真实移动驱动任务成功 | 成功条件仍是记录轨迹落在任务格 |
| P4 | 真实噪声只做留出预测 | `predict_parquet`，不回退到 Synthetic Demo |
| P5 | 不能拼接不重叠的数据 | `fully_real` 在重叠报告为否时拒绝 |

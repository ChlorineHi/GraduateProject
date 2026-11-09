# 图示说明

源文件：`docs/uml/diagrams.puml`。PNG 在 `docs/uml/png`，SVG 在 `docs/uml/svg`。字体为 WenQuanYi Micro Hei。渲染命令：

```bash
java -jar plantuml.jar -charset UTF-8 -tpng -o docs/uml/png docs/uml/diagrams.puml
```

| 图 | 对应代码 |
| --- | --- |
| 01 系统用例图 | 登录、地图、任务、分配、仿真、实验页面 |
| 02 管理员用例图 | `/api/users`、`/api/audit`、参与者 PATCH、真值层 |
| 03 任务发布者用例图 | `POST /api/tasks`、分配、仿真、核验 |
| 04 采集参与者用例图 | `mine=true`、接收、仿真采样 |
| 05 总体架构图 | `apps/web`、`urbannoise.api`、SQLite、npz |
| 06 模块组件图 | dataio、world、predictors、assignment、experiment |
| 07 核心类图 | `models.py` 与 `LinUCB`、`MobilityFit`、`World` |
| 08 任务发布活动图 | `create_task`、`check_transition` |
| 09 自动分配活动图 | `propose_assignments` |
| 10 采样时序图 | `assisted_sample` |
| 11 重规划时序图 | `step_simulation` 与再次分配 |
| 12 ER 图 | `models.py` 的表名 |
| 13 部署图 | 已验证的 uvicorn + Vite；Docker 未执行 |
| 14 数据处理图 | `safe_import` |
| 15 算法流程图 | `distribution`、`predict_idw`、`combine_value`、`allocate` |
| 16 LinUCB 图 | `LinUCB.score` / `update`，不是 Gymnasium |

类图和 ER 图只画了说明关系所需的字段，不是数据库的全部列。

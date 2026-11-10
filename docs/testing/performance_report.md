# 性能记录

来源：`experiments/results/performance.json`，由 `PYTHONPATH=src .venv/bin/python scripts/benchmark.py` 在 2026-11-09 生成。

平台：`Linux-6.12.113+-x86_64`，Python 3.12.3，4 个 CPU，无 GPU。`peak_bytes` 是 `tracemalloc` 峰值，不是进程 RSS。

## 一次 MU-PSA 回合

场景 regular，2 天，每天 12 个时间片。

| 网格 | 人 / 机 | 预算 | 秒 | tracemalloc 峰值 | 因果 MAE | 成功任务 |
| --- | --- | --- | --- | --- | --- | --- |
| 8×8 | 8 / 2 | 8 | 0.098 | 0.55 MB | 6.73 | 7 |
| 12×12 | 12 / 3 | 12 | 0.213 | 3.11 MB | 6.78 | 9 |
| 16×16 | 16 / 4 | 16 | 0.433 | 11.80 MB | 7.44 | 13 |

这些 MAE 是性能探针自己的世界，不能和主实验表混比。

## 接口

TestClient，新建的演示库。

| 调用 | 状态 | 毫秒 |
| --- | --- | --- |
| GET /api/health | 200 | 4.58 |
| GET /api/dashboard | 200 | 12.32 |
| GET /api/map/frame?slot=20 | 200 | 14.56 |
| GET /api/tasks | 200 | 8.63 |
| GET /api/predictions/noise?slot=20&model=idw | 200 | 8.21 |
| POST /api/assignments/run | 200 | 22.27 |

主实验配置（14×14，5 个种子，两个场景，多种方法和消融）在开发时约 49 秒完成 351 行。该数字来自当时的运行记录，不是这次性能脚本重复跑 main 的结果。

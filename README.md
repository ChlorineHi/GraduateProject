# UrbanNoiseLab

人机混合城市噪音预测采样与智能任务分配系统。这是北京邮电大学软件工程毕业设计的可运行实现，不是方案草稿。

演示数据是合成的虚拟网格，标记为 Synthetic Demo。它不是北京或东京的真实街区。YJMob100K 的网格是匿名虚拟 500 m 网格，不标成任何真实城市。GeoLife 与 NoiseCapture 的原始文件在 `data/raw/`，该目录被 git 忽略。统计以 `docs/data/` 里这次运行写出的报告为准。

## 已验证的启动

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cd apps/web && npm install && cd ../..
make demo
make api
```

另一个终端：

```bash
cd apps/web && npm run dev -- --host 127.0.0.1 --port 5173
```

打开 http://127.0.0.1:5173 。

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | admin | DemoAdmin#2026 |
| 发布者 | publisher | DemoPublish#2026 |
| 采集者 | collector | DemoCollect#2026 |

密码只用于本地演示。

## 其他命令

- `make test`：pytest。
- `make experiment-smoke`：小规模实验，写入 `experiments/results/phase2/smoke`。它不会覆盖 `experiments/results/smoke`。
- `bash scripts/setup_linux.sh`、`start_linux.sh`、`test_linux.sh`、`stop_linux.sh`：不使用 Docker 的 Linux 路径。
- `make report`：由旧版 `docs/final-report/UrbanNoiseLab_系统完整报告.md` 生成 PDF。Phase II 报告是另一个文件。

`experiments/results/main` 是旧协议归档。MU-PSA 不是那份结果里每个预算的 MAE 赢家，也不是 Phase II 公平协议的赢家。新结果在 `experiments/results/phase2/`。

不要用 Docker Compose 启动。见 `deploy/README.md`。

中文报告：`docs/final-report/UrbanNoiseLab_系统完整报告_PhaseII.md`。

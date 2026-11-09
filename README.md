# UrbanNoiseLab

人机混合城市噪音预测采样与智能任务分配系统。这是北京邮电大学软件工程毕业设计的可运行实现，不是方案草稿。

演示数据是合成的虚拟网格，标记为 Synthetic Demo。它不是北京或东京的真实街区。YJMob100K、GeoLife 和 NoiseCapture 只有格式适配器和很小的夹具，完整数据包没有下载。

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
- `make experiment-smoke`：小规模实验，会覆盖 `experiments/results/smoke`。
- `make report`：由 `docs/final-report/UrbanNoiseLab_系统完整报告.md` 生成 PDF。

主实验已经生成在 `experiments/results/main`。MU-PSA 不是所有预算上误差最低的方法，数字以该目录的 `summary.json` 为准。

`docker compose` 没有在本环境执行，原因见 `deploy/README.md`。

中文报告：`docs/final-report/UrbanNoiseLab_系统完整报告.md`。

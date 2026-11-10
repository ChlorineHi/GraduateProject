# UrbanNoiseLab

人机混合城市噪音预测采样与智能任务分配系统。这是北京邮电大学软件工程毕业设计的可运行实现，不是方案草稿。

演示数据是合成的虚拟网格，标记为 Synthetic Demo。它不是北京或东京的真实街区。YJMob100K、GeoLife 和 NoiseCapture 只有格式适配器和很小的夹具，完整数据包没有下载。

## 支持的启动方式

支持的路径是仓库里的虚拟环境 `.venv` 和 `apps/web` 的 npm。`deploy/unused/` 里的 Compose 文件和 Dockerfile 未使用，发布时没有安装或执行 Docker。

Linux：

```bash
bash scripts/setup_linux.sh
bash scripts/start_linux.sh
bash scripts/test_linux.sh
bash scripts/stop_linux.sh
```

打开 http://127.0.0.1:5173 。API 在 http://127.0.0.1:8000 。两者只绑定 127.0.0.1。日志和 pid 文件在 `logs/`。`stop_linux.sh` 只结束 pid 文件里、命令行属于本应用的进程。所选端口已有进程时，启动脚本会退出并留下那个进程。

端口可以用本次命令的环境变量改掉，例如 8000 和 5173 已被占用时：

```bash
UNLAB_API_PORT=8010 UNLAB_WEB_PORT=5174 bash scripts/start_linux.sh
```

Vite 的 `/api` 代理读取 `UNLAB_API_PORT`。这些变量只存在于该次进程，脚本不改系统配置。

Windows 脚本不调用 `Set-ExecutionPolicy`。用进程内绕过执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop_windows.ps1
```

`make setup`、`make start`、`make stop`、`make test` 调用 Linux 脚本。`make api` 在前台运行 API。`make web` 在前台运行 Vite。`make demo` 只在空库时写入演示数据。

## 演示账号与环境变量

| 角色 | 用户名 | 密码 |
| --- | --- | --- |
| 管理员 | admin | DemoAdmin#2026 |
| 发布者 | publisher | DemoPublish#2026 |
| 采集者 | collector | DemoCollect#2026 |

这些密码只用于本地演示。

`UNLAB_DATA_DIR` 是本地数据目录，默认 `./data`，里面是 SQLite、导入文件和生成的世界。`UNLAB_JWT_SECRET` 用来签演示登录令牌。`.env.example` 里的密钥只用于本地演示，不能拿到演示之外使用。没有 `.env` 时，`setup` 会把 `.env.example` 复制到仓库内的 `.env`。

## 其他命令

- `make test`：pytest。
- `make experiment-smoke`：小规模实验，会覆盖 `experiments/results/smoke`。
- `make report`：由 `docs/final-report/UrbanNoiseLab_系统完整报告.md` 生成 PDF。

主实验已经生成在 `experiments/results/main`。MU-PSA 不是所有预算上误差最低的方法，数字以该目录的 `summary.json` 为准。

中文报告：`docs/final-report/UrbanNoiseLab_系统完整报告.md`。

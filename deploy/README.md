# 部署

支持的运行方式是仓库内的虚拟环境 `.venv` 和 `apps/web` 的 npm。

Linux：

```bash
bash scripts/setup_linux.sh
bash scripts/start_linux.sh
```

Windows 不修改系统执行策略，只对当前进程放宽：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start_windows.ps1
```

API 与 Vite 都只监听 `127.0.0.1`。`UNLAB_DATA_DIR` 是本地数据目录，默认 `./data`。`UNLAB_JWT_SECRET` 和 README 里的演示口令只用于本地演示。

`deploy/unused/` 中的 Compose 文件和 Dockerfile 未使用。这次发布没有安装 Docker，也没有执行那些文件。

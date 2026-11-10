# 部署说明

Docker、Docker Compose 和 Kubernetes 不是本系统的支持路径。`deploy/Dockerfile.api`、`deploy/Dockerfile.web` 和仓库根目录的 `docker-compose.yml` 保留为未使用文件，没有在本环境执行，也不要安装 Docker 来运行它们。

在 Linux 上：

```bash
bash scripts/setup_linux.sh
bash scripts/start_linux.sh
bash scripts/test_linux.sh
bash scripts/stop_linux.sh
```

Windows 脚本在 `scripts/*_windows.ps1`。它们在这台 Linux 机器上没有执行。

已经用过的手工命令：

```bash
PYTHONPATH=src .venv/bin/python -m uvicorn urbannoise.api:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd apps/web && npm run dev -- --host 127.0.0.1 --port 5173
```

Compose 文件使用 SQLite 卷，不启动 PostgreSQL 或 Redis。Vite 开发服务器里的 `/api` 代理指向 `127.0.0.1:8000`。若 API 在另一个容器网络里，需要改 `apps/web/vite.config.ts` 后再构建。这一点在未执行的 Compose 里尚未处理。

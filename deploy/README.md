# 部署说明

2026-11-09 的开发机没有 Docker 命令，`docker compose up` 没有执行。不要把本目录当成已经通过的部署证明。

已经启动并返回健康检查的方式：

```bash
PYTHONPATH=src .venv/bin/python -m uvicorn urbannoise.api:app --host 127.0.0.1 --port 8000
```

前端：

```bash
cd apps/web && npm run dev -- --host 127.0.0.1 --port 5173
```

Compose 文件使用 SQLite 卷，不启动 PostgreSQL 或 Redis。Vite 开发服务器里的 `/api` 代理指向 `127.0.0.1:8000`。若 API 在另一个容器网络里，需要改 `apps/web/vite.config.ts` 后再构建。这一点在未执行的 Compose 里尚未处理。

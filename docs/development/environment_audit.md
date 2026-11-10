# 环境审计

审计时间：2026-11-09。以下内容来自当时在这台云代理机器上执行的命令，不是规划假设。

## 已确认

- 仓库起点只有 `README.md`（内容为 GraduateProject）和一次初始提交。工作分支为 `cursor/urbannoise-lab-63b5`。
- Python 3.12.3，Node.js 22，npm 10。虚拟环境在 `.venv`，`PYTHONPATH=src`。
- 已安装并可导入：FastAPI、SQLAlchemy、Pydantic、PyJWT、NumPy、Pandas、scikit-learn、SciPy、Matplotlib、HTTPX、pytest。
- Java 与 Graphviz 可用。PlantUML 1.2024.7 由本机下载的 jar 渲染 `docs/uml/diagrams.puml`。
- 中文字体：WenQuanYi Micro Hei（`/usr/share/fonts/truetype/wqy/wqy-microhei.ttc`）、Droid Sans Fallback。
- CPU：性能测试脚本读到 `os.cpu_count() == 4`。没有可用 GPU。
- 磁盘在开始时约有 200 GB 以上空闲。
- 浏览器：系统已有 Google Chrome。端到端脚本使用 Playwright 的 `channel: "chrome"`。
- CDRI 已安装到 `.cursor/skills/cdri`，规则在 `.cursor/rules/cdri.mdc`。`config check` 显示没有 OpenAlex 邮箱、Semantic Scholar key、Unpaywall 邮箱，也没有 pymupdf。检索仍通过 OpenAlex、Crossref 和 arXiv 完成了两次 landscape 运行。

## 未具备

- 没有 Docker 守护进程。`docker` 命令不存在。Compose 与 Dockerfile 在 `deploy/unused/`，标记为未使用，没有执行。支持的路径是虚拟环境与 npm（`scripts/setup_linux.sh`）。
- 没有 PostgreSQL/PostGIS 客户端服务。默认数据库是 SQLite。
- 没有下载 YJMob100K、GeoLife 或 NoiseCapture 的完整数据包。适配器只用夹具和上传接口验证格式。
- 没有安装 Gymnasium 或 Stable-Baselines3。强化学习部分是自写的 LinUCB，不是 PPO。
- `npx skills add` 安装 frontend-design 与 Vercel skills 的步骤没有执行成功记录。界面按任务书中的市政测站方向直接实现，并用两轮浏览器截图检查。

## 已验证的启动方式

```bash
cd /workspace
PYTHONPATH=src .venv/bin/python -m uvicorn urbannoise.api:app --host 127.0.0.1 --port 8000
cd apps/web && npm run dev -- --host 127.0.0.1 --port 5173
```

`GET /api/health` 返回 `{"status":"ok","service":"urbannoise","database":"up"}`。Vite 开发服务器返回 200。

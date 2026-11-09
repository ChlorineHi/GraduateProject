# 测试计划

## 单元与算法

`tests/test_algorithms.py` 覆盖声能平均、非法概率、噪声场有限且近处相关高于远处、分配约束、决策不读未来真值和未来轨迹、移动拟合不使用未来、IDW 远处标准差大于近处、回合预算、状态机、YJMob / GeoLife / NoiseCapture 夹具。

## 接口

`tests/test_api.py` 使用临时 SQLite。覆盖健康检查、错误登录、三角色、地图默认不返回真值、采集者不能看真值、创建和发布、分配、采集者提交、缺测量 422、重复提交 409、仿真步进、CSV、采集者不能列用户、幂等键。

## 浏览器

`apps/web/e2e/walkthrough.mjs` 用系统 Chrome 打开 `http://127.0.0.1:5173`。检查错误密码、管理员各页面、创建并发布任务、分配、轨迹预测、噪声预测、仿真步进、实验曲线、深色主题、采集者任务按钮、移动宽度 390。截图在 `docs/screenshots`。

## 性能

`scripts/benchmark.py` 记录 8、12、16 宽度网格上一次 MU-PSA 回合的耗时，以及 TestClient 上若干接口的毫秒数。

## 不在本次自动化里的项

- Docker Compose 实际启动。
- 全量 YJMob100K 或 GeoLife 导入。
- 多小时正式训练以外的 GPU 实验。

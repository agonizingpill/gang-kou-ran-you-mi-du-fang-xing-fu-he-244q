# V4 同盘贴签复核 · 测试证据

四个测试脚本覆盖算法、服务、API、前端渲染四层，全部通过（2026-11-18，本机 Python3.11 + SQLite + 真依赖，Node22）。

## 运行方式

```bash
# 1. 纯算法（无任何第三方依赖，直接跑）
python3 test_tray_assignment.py

# 2/3. 服务与API集成（需 pip 安装 backend/requirements.txt 中 sqlalchemy/fastapi/numpy/scikit-learn/redis/PyJWT 及 httpx；用 SQLite 代替 Postgres，FakeRedis 代替 Redis）
python3 test_label_service.py
python3 test_label_api.py

# 4. 前端页面渲染冒烟（Node，覆盖 draft/suggested/review/adopted/failed/viewer 六种状态）
node test_trays_render.mjs
```

## 覆盖要点

- test_tray_assignment.py（17项）：整盘一一对应全局最优（含8×8暴力枚举对拍）、次优方案（4×4暴力对拍）、低于阈值不归属、不逐瓶强配、并列确定性。
- test_label_service.py（38项）：受理即固定瓶样与60条/级参考快照；错签瓶 FS-B 整盘改归 TK-M01；采纳同事务撤回未放行调拨 TR-PEND；重试采纳幂等；已采纳冻结；改候选罐旧建议失效且瓶样仍固定；同等级双候选并列→review→必须人工核签（选方案+≥8字依据）；离群瓶样保留原签；任一瓶已放行则整盘拒绝且他瓶不变；参考样/一瓶多盘/空盘拦截；failed 从原盘恢复重算。
- test_label_api.py（20项）：登录/RBAC（viewer 只读、chemist 登记与分析、admin 采纳）、编号唯一约束、队列受理、worker 核算、采纳幂等、审计轨迹。
- test_trays_render.mjs（7组）：页面核签区、候选分数矩阵、原罐签、并列核签单选、冻结快照、失败恢复入口、viewer 禁用。

## 留待 docker 环境复核

本机无 Docker/Postgres，以下两点需在 `docker compose up` 后复核：并发互斥（采纳与调拨放行同事务行锁，只接受符合当时归属的一方——本机已分别验证两个方向的顺序拒绝）；worker 长循环对 tray-analysis 队列的实际消费（本机以服务内联调用等价验证）。

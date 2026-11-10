# 系统稳定性审查整合方案（v1 · 2026-10-24）

## 1. 现状盘点（22 个体检/监控类定时任务）
高频（保留，不并入）：frequent-checks-5m、proc-watch(7/37)、io-watch(11/41)、io-stuck(每 5 分)、ds-burn-watch(10m)、session-health-watch(10m)、health-alert(13/33/53)、自检 selfcheck(每 5h)、project-monitor、model-econ。
日/周汇总（重叠最重）：
- 每日系统自检 03:45 daily-selfcheck.sh
- 盘位体检 07:15 disk-health-all.sh
- 体检采集 07:40 / 体检日报 08:10
- 四查督察 08:25 / 周三深度 08:30 inspector.py
- selfcheck-weekly 周一 07:45 / 信息窗周体检 周一 09:20 / 备份管线自检 周二 19:50 / 排期体检 周三 07:29 / token-diet 月 1 日

## 2. 方案主体
工具：`tools/stability-check.sh`（三环 17 项）
- A 硬件 6：CPU 负载 / 内存+swap / GPU 温度与显存 / SMART(deep) / 四盘容量 / vhdx 落盘比(deep)
- B 系统 6：WSL 内核+interop / 9p 写探活 / 时钟漂移 / dmesg IO 错误 / Windows 更新与待重启(deep) / Defender(deep)
- C OpenClaw 6：网关 RSS+端口 / 定时任务连续失败与超期 / 渠道行 / 今日花费环比 / 最新备份龄 / 明文密钥计数
输出：`state/stability/latest.json`（机器读）+ `latest.md`（人读）+ 逐项 TSV 增量落盘。
告警：脚本自身 `notify.sh`（timeout 30），按「结论行 md5」6 小时去重。

## 3. 双模型评审结论（2026-10-24 20:2x）
- deepseek/deepseek-v4-pro：4096B，完成
- zai/glm-5.3：3880B，完成
共识致命点（均已处理或列入过渡）：
1. 单脚本单点 → 每项独立 timeout + TSV 增量落盘；报告阶段失败保留 failed-*.tsv 并 exit 3。
2. 退出码会与 cron 失败告警叠加 → **改为：判定 WARN/FAIL 时进程 exit 0（结论写进 JSON/告警），仅内部错误 exit 3**；已实测 rc=0、rc 字段=1。
3. 告警与被监控对象同域（C 环故障时告警发不出）→ 现状仍走 notify.sh（经网关）。**待主公拍板**是否加一条独立出口（飞书自定义机器人 webhook 直发 curl）。
4. 17 项不得重复高频任务已覆盖的瞬时指标 → A1/A2 标注为"快照"，不进告警主因。
5. 禁用文本匹配口径 → 已改结构化：WSL rc 不信、看「失败 N>0」；E/H 看故障词；NAS rc=2 权威。

## 4. 落地顺序（灰度，每步可回滚）
1. ✅ 工具已建、基线已跑：PASS 8 / WARN 5 / FAIL 0 / SKIP 5
2. ⏳ 新增 2 个任务：每日 07:00（常规）、周日 07:30（--deep）
3. ⏳ 观察 3 天后再停用 8 个重叠任务（先停 03:45 系统自检与 07:40/08:10 采集日报，再停四查督察）
4. 回滚：任务只 disable 不删；脚本 `git checkout tools/stability-check.sh`

## 5. 需主公拍板
- 是否新增独立告警出口（不依赖网关）？
- 是否同意先新增 2 任务、暂不停旧任务（观察 3 天）？

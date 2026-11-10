# backup-quiet v2 双模型交叉评审记录（2026-10-20）

## 背景与范围
- 起因：脚本审计报 backup-quiet.sh（v1）sh/bash 双语法错误；主公令「你处理吧」。
- 事实澄清（更正果果 10-20 08:46 的错误说法）：v1 是 10-18 的弃稿（零引用），v2 三脚本 **10-19 已挂载**进两个备份入口并实跑（cron 任务不存于 openclaw.json，当日 grep 错了地方得出"未挂载"的错误结论）。
- 本次评审为**事后验证评审**（挂载当时未走双模评审，本次补上）。
- 评审员：deepseek-v4-pro（评审员A）+ moonshot/kimi-k2.6（评审员B），互相独立，均声明：三脚本读全、cron list 核对（85 任务逐条套用保护逻辑）、账本 261 条解析、全程只读。

## 两份结论
- A（v4-pro）：**继续运行**——设计正确、账本干净、3 轮零残留；唯一实质缺陷=哨兵对「恢复中途被杀」的自愈盲区（最坏 3 小时而非 30 分钟），可在线补丁。
- B（kimi）：**修后运行**——核心机制可靠；同一哨兵盲区列为必修；修后可升「继续运行」。

## 共识必修（已修）
1. **哨兵盲区**：guard 只认「中断残留」字样，漏「state.json 在 + 账本 pending>0 + trap 未触发（SIGKILL/WSL 重启/OOM）」形态 → 原要等 180 分钟。
   - 修法（采 A 的安全变体，同时覆盖 B 指出的形态）：guard v3 新增路径 2——`账本待恢复>0 且 pgrep 检测不到备份链进程（nas-push-archive|backup-with-quiet|heartbeat-run）→ 立即恢复+告警`。用「备份进程在不在」区分「正常静默中」与「恢复被中断」，避免在正常备份 30 分钟时误恢复击穿静默（B 的「见 pending 就恢复」变体因此不采）。
2. **cron_set 超时裸抛**（A 必修 2）：TimeoutExpired 捕获后按失败记账，不再让 pause/resume 循环中途崩。

## 加固建议（双模建议项，均已落地）
- pause 失败 → notify.sh 显式飞书告警（A-1/B-5）
- guard 每次运行写心跳行，哨兵自身可观测（A-2）
- PROTECT 补入「自检|探测|错误分析」，防自检类任务未来被误停（A-3）
- cron_list timeout 90→120s + 失败重试 1 次（B-4/A-1）

## 分歧项（未动，待主公拍板）
**备份入口要不要显式设 timeoutSeconds=5400**（9d5f221d / 1781d29a 两个入口现为 null）：
- B（kimi）：建议设，消除对未知隐式上限的依赖；触顶被杀也有 trap+guard 兜底。
- A（v4-pro）：**反对**。证据：全站 60 个 command 型任务 timeoutSeconds 全 null，10-19/10-20 两轮实跑 32 分钟均未被杀（旧「600 秒墙钟」教训不适用于当前 cron 任务形态）；heartbeat-run 每 60 秒吐心跳防「无输出超时」；若设 5400，9p 拥堵时 20G 备份合法超 90 分钟会被 SIGKILL——**SIGKILL 不触发 trap**，恢复要等 guard 180 分钟兜底，且留下 .part 残件。
- 果果建议：维持 null（A 论据更实证）。仅在全站统一补「宽松硬上限（如 4h）」时一并考虑。

## 缓办（记录在案）
- 账本按月归档（年增约 100KB，暂无必要；B-3）。

## 验证记录（2026-10-20 09:04）
- `bash -n` guard/wrapper 通过；`python3 -m py_compile` backup-quiet.py 通过
- `backup-quiet.py status`：账本待恢复 0 / 未静默
- guard v3 实跑一轮 rc=0，心跳行已落 state/work/backup-quiet-guard.log
- 实证背景：10-19 13:00 轮与 10-20 01:00 轮各 41 暂停/41 恢复全闭合，账本无残留；85 任务 0 个处于 disabled

## 配套处置
- v1 backup-quiet.sh（语法坏、零引用）→ 归档 回收站/items/2026-10/backup-quiet.sh-v1弃稿-20261020，manifest 已记，主公 10-20 批准。
- trash-to-nas.sh 批次名写死 20260930 的 bug 已修（按运行日期命名），新批次已可正常入群晖。

## 附录：评审原文
### A · deepseek-v4-pro
（全文见下方）
结论 = 继续运行。必修 2 项（哨兵盲区含修复方向与「须用备份进程区分」警示；cron_set 超时捕获）；建议 4 项（pause 失败告警+重试、哨兵心跳、PROTECT 补漏、全站宽松硬上限）；关键证据含账本 261 条全量分桶（85 intent / 85 done-ok / 88 resume-ok / 0 失败 / 0 悬空）、85 任务保护复算（保护 44 / 可停 41 / cap 59 未触顶）、竞态与超时分析（维持 null 的完整论证）。

### B · moonshot/kimi-k2.6
结论 = 修后运行。必修 1 项（哨兵盲区：STATE 在 + pending>0 的 stuck 态，建议见 pending 即恢复或降阈值 60 分钟）；建议 5 项（timeoutSeconds=5400、账本按月归档、cron_list 120s、pause 失败告警）；证据表含 41 暂停/恢复闭合、flock 有效性、语法检查通过。

（两份全文已由果果在本会话完整接收并归档；本文件为浓缩索引。）

# MEMORY.md — 长期记忆索引（2026-11-02 指针化版）

> 全文旧版：docs/memory-archive/MEMORY-full-20261102.md
> 规则：本文件只留「每轮都可能用到」的铁律与指针；细节进 docs，需要时再读。目标 ~8KB 且**不被截断**。

## 0. 一句话现状
A 机（Windows+WSL2，7900X / 64G（WSL 分 48G）/ RTX 3070 8G）跑网关与 37 个 agent；B 机（9950X / RX 9070XT 16G，192.168.1.107）跑本地 ollama；云端 DeepSeek 为主力执行模型。7900X/9950X 均无核显。

## 0.1 频道职责边界（2026-10-31 12:52 主公令）
- feishu[backup] 账号只负责：①备份 ②磁盘空间规划。其它事务转交对应管家。
- 本账号（main/果果）按 AGENTS.md 全职责执行；备份盘位（D/X/E/H/群晖）归备份管家规划，D 盘另有他人文件慎占、只留 1 份。
- 一切操作默认选「最稳」方案：可回退 > 省事。

## 1. 铁律速查（细则见 USER.md）
- 凭据：masked secrets，绝不聊天明文、不回显。
- 页脚：**只有 maint 附页脚**；果果与其余管家不附、不贴数字。
- 删除：名+大小+SHA256 三重校验，走回收站/备份站留台账；<24h 文件跳过。
- 备份：重大变更前 tools/pre-upgrade-backup.sh，失败禁止继续。
- 重启：只走 bash tools/restart-gateway.sh --reason "..."，禁 gateway.restart 与裸 systemctl。
- 峰谷：**工作日** 09-12/14-18 非紧急只入 state/work/peak-queue.md；**周末与法定假日全天半价**；判据 sh tools/peak-status.sh。
- 硬盘边界：只动果果/OpenClaw 自建物；拿不准＝不动。
- 授权：双审自决（高危三审）→ 落地 → 报备；P0 仍归主公：重启/关机、资源上限、权限扩容、密钥、防火墙、systemd、账号白名单、**生物特征、BIOS/物理设置、采购**、批量删除、版本升级。
- 每天给主公 **≤1 个决定**，不连番追问。
- 子任务结果只报一次；收讫用 agents_wait，不因重投递重发。
- 开新会话：14k 事件/14MB 告警、20k/20MB 冻结；提醒前先落盘。

## 2. 模型与排工
- 别名：DeepSeek=v4-pro；fast=deepseek-flash；local=qwen3.5:9b；local-14b=qwen3.5:9b-fast；kimi=kimi-for-coding；kimi-review=k3-256k（2026-11-02 已修失效别名）。
- 默认链：flash → glm-5.3-flash → glm-5.3 → kimi-for-coding → v4-pro → qwen3.5:9b。
- 分工：日常 flash；重活 v4-pro；零成本巡检本地 9b；14b 只兜底。
- 评审池唯一真源：workspace-model/state/model-warden/dispatch-rules.json；只取旗舰、随机两家不同厂商、禁同配对连用；真跑完判据 rc=0 且输出 >80B 且非报错文本。
- 接替表 docs/备用模型接替表.md；新模型准入 python3 tools/model-eval.py <model> quick。
- 高峰：DeepSeek 工作日北京 09-12、14-18；智谱 coding 工作日 14-18。

## 3. 环境与关键路径
- 工作区 /home/j/.openclaw/workspace；管家工作区 /home/j/openclaw-workspaces/<agent> 及 ~/.openclaw/workspace-{model,backup}。
- 网关：user 单元 openclaw-gateway，18789，token 鉴权，0.0.0.0；LAN 192.168.1.108 / WSL 172.18.242.44。
- WSL：vhdx X:\WSL\Ubuntu，上限 20G 内存/14 线程/12G swap；改配置需 wsl --shutdown（走重启流程+备份）。
- GPU：**/usr/lib/wsl/lib/nvidia-smi（不在 PATH，脚本一律用绝对路径）**；venv：tts312（musicgen）、face（insightface+onnxruntime-gpu）、demucs（分轨，半装）。
- HF 下载必须：HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1
- 9p(/mnt/e)：慢、吞输出、chmod 无效；大文件禁 cp，用 rsync --append-verify --inplace。
- vhdx 膨胀根因（2026-11-10 查实并已处置）：OpenClaw 每次「只读打开状态库」（agent 回合、`openclaw status/cron list/sessions` 等 CLI）都会把 ~145MB 的 session 库整份复制到缓存目录且不自动删；面板每 15s 三连 CLI 只是其中一部分（A/B：停面板 3 分钟 +5 份，开面板 +10 份）。处置：`~/.cache/openclaw` 已软链到 `/dev/shm/oc-cache`（tmpfs，纯内存），`tools/oc-cache-janitor.sh` + `oc-cache-janitor.timer`（每 10 分钟，上限 4G，开机 30s 后跑一次）保证用完即销毁 → 不再写盘、vhdx 不再涨。剩余：vhdx 已涨到 967G 需一次性 `sudo fstrim -av` + Windows `wsl --shutdown` 后 `diskpart compact vdisk`；fstrim.timer 此前从未真跑过。
- 长任务：systemd-run --user --unit=X --collect（网关 cron 有 600s 硬墙）。
- 搜索/抓取：tools/ds-tools.sh search|fetch。
- 看板：tools/dashboard-gen.py → 静态 HTML；dashboard-serve.py 127.0.0.1:18810（每次请求重生成）。
- SQLite 卫生：tools/sqlite-hygiene.sh + sqlite-hygiene.timer（每小时 checkpoint，WAL>256MB 告警，周日 vacuum）。

## 4. 备份与清理（真源 tools/retention.env）
- 保留：D=1、X=2、E/H=7+最多 4 个周一、NAS=7+4；/home/j/Backups 本地层已废止（同盘不算备份）。
- 节奏：每日 01:00 全量；周一三五 13:00 全量 + 14:10 校验 + 14:45 推送 + 16:00 演练。
- 校验：backup-drill v3 全量 grep + gzip + 关键文件抽取（抽样会假阴性）。
- 清理唯一入口：tools/disk-cleanup-all.sh（三重校验+白名单+flock，账本 state/trash-ledger.jsonl）。
- 静默窗：backup-quiet v2（暂停 ~41 任务、180 分钟自恢复、PROTECT 关键词）。
- 加密云备份：tools/secure-cloud-backup.sh，**-pass file:~/.cloud-escrow，禁字面口令**；产物 3 片 + manifest。

## 5. 告警与监控
- 独立 webhook：/home/j/.config/feishu-alert-webhook（消息须含「告警」）；tools/notify.sh --alert 先 webhook 后网关；notify.sh 无超时，外层包 timeout。
- 体检 tools/stability-check.sh（三环 17 项，恒 exit 0，判定进 JSON，6h 去重）；07:00 日常、周日 07:30 深检。
- 看门狗 gateway-watchdog.sh（2 分钟；**2026-11-02 起含真写探测**，/health 200 不再算活；维护期 touch state/work/.watchdog-pause）。
- 会话哨兵 tools/session-guard.sh（7,22,37,52 每 15 分钟）。
- 告警摘要 tools/alert-digest.sh（--hours N；含 SQLITE_FULL/SqliteWorkerError 关键词）。
- 已知盲区：网关全死时 webhook 与 CLI 两条告警路径都可能失效。

## 6. 网络
- 路由器每晚 **04:45 断网**（约 20 分钟恢复）：重 IO/依赖网络任务避开 04:00–06:05。
- 固定 IP（2026-11-02 路由器已绑定）：路由器 .1｜A 机 .108｜B 机 .107｜新群晖 GuoGuoNAS(6TB,/mnt/nas) .109+.110｜老群晖(13T) .5+.101｜打印机 .80。**.104 已不是 NAS；.106 只是 Windows 端口映射别名。**
- 群晖双网口各拿一个 DHCP 是「两台同指纹」误判的根因。
- ollama：A 127.0.0.1:11434 → tools/ollama-proxy.py → B .107；B 掉线时报明确错误不静默。

## 7. 最常踩的坑（全表见 docs/教训台账-20261101.md）
1. 自检复用错误输入 → 永远通过。
2. 只看退出码/静默告警 → 假绿；成功要有下限（rc=0 且输出 ≥200B 且不命中错误文本）。
3. pkill -f 会杀自己；pgrep -f 匹配自身 → 判活用 systemctl --user is-active。
4. setsid/nohup 会被掐 → 用 systemd-run。
5. ���样查备份清单 → 假阴性，必须全量 grep。
6. 判断 cron 用 openclaw cron list --json（automations 是另一套）。
7. 账本按 id 改，禁模糊标题 regex。
8. 写配置 tmp+fsync+os.replace；读空绝不回写，写完 wc -c 校验。
9. 跨 9p 搬大文件禁 cp（20G 必报 Cannot allocate memory）。
10. 声明的授权机制必须实测（UAC 不弹窗却报「你点了」＝谎报）。
11. **/health 200 ≠ 活**：11-02 出现 2h41m 假活（41 万次 SQLITE_FULL），判活必须真写库。
12. **WAL 不 checkpoint 会撑爆整个 SQLite worker 池**：lcm.db WAL 曾达 762MB。
13. **一次性 poke 不算保活**，且探活脚本会成为「最后会话」触发 logind 关机；探活前先 `pgrep -fx` 确认保活进程在，不在先拉起。
14. **关键计划任务只有 logon 触发器＝被杀后永不复活**：必须 boot trigger + RestartCount/RestartInterval + IgnoreNew，改完 `Get-ScheduledTask` 回读。
15. **~\.cache/openclaw-<uid> 临时目录绝不能软链**（2026-11-10 实测）：fs-safe 报 `Unsafe fallback OpenClaw temp dir ... is a symbolic link`，整个 openclaw CLI 静默全挂（status/cron/memory 全废，cron「模型时段」连带失败）。只有 `~/.cache/openclaw`（快照缓存）可以软链到 tmpfs。详见 state/work/vhdx-膨胀修复-20261110.md v3。

## 8. 常用文件
- 任务账本 state/tasks/tasks.json（唯一真源；kind=decision 即待拍板）。
- 页脚 tools/footer-all.sh + tasks-footer.py + footer-row.py（maint 专用）。
- 台账：docs/交叉验证台账.md、state/trash-ledger.jsonl、state/work/alert-fix-ledger.jsonl。
- 桌面：果果助手.bat v2.1.0（唯一入口）+ tools/desktop-rescue.sh（网关外自救）。

## 9. 账号与真源指针
- 模型事务全归模型管家：真源 /home/j/.openclaw/workspace-model/{state/model-warden,docs}；主区同名文件是软链。
- 时间表唯一真源：docs/时间表与窗口规则-20261031.md；核验 python3 tools/schedule-audit.py。
- 会话卫生：主会话不跑重活（>60s 或 IO 密集 → 子代理）；单会话 20k 事件/20MB 冻结；评审并发 ≤2。
- 飞书 open_id：主 app ou_74fec7bc81cc6ec6d2b4de1c0967923b；备份 app ou_19e43ddd…96b；维护 app ou_008693…7b3。
- **语义记忆检索已启用（2026-11-07）**：memory.search=ollama/nomic-embed-text（768 维）。注意 127.0.0.1:11434 是 ollama-proxy 转发到 **B 机 192.168.1.107**，向量实际在 B 机算（面板显示 B 机是对的）；A 机 11435 另装了同名模型作冷备，但索引是用 B 的权重建的，切 A 必须整库重嵌（需离线窗口）。索引 docs/ + state/tasks/ + 记忆文件；用法 `openclaw memory search "按意思描述" --agent main`。向量索引是派生物，丢了重建即可，不是备份。

<!-- BUTLER-DIGEST:BEGIN -->
### 跨管家周摘要 2026-W45（自动生成，只读指针）
- backup-drill.sh:28 全量 tar tzf 420s 超时 → 误报 SOUL/AGENTS/IDENTITY/memory 四项缺失，日报仍 exit 0（假绿）（summary-20261105.md:27）
- 影响：备份落地/回收站水位/日志异味/会话健康四项夜间监控名义上线、实际空转，形成"假绿"。（maint-2026-11-02.md:39）
- 脚本本身发送段是干净的：tools/maint-boot-notice.sh:182-193 有 rc=$? 判定、失败写 fails 并 exit 4，不是假绿源头（maint-2026-11-05.md:28）
- 根因：待确认（缺第三证，不猜）。两种可能：①safeBins 只接受不带参数的裸命令，ls/df/grep 缺 flags/args 的 profile；②Code Mode 桥接层在 agent 策略之前先拦，只放行极（maint-2026-11-01.md:26）
- 盘位体检 07:51：55 分钟超时，根因群晖不可达（backup 自检同样报「异地不可达」）（summary-20261104.md:19）
- 建议动作：① 修订 WORK 文档三处引用/时间；② 同步 line 155 修正回 v6 副本（或删 v6 副本、以 .v5.bak 留底）并更正正式版头注释。均属文本级低风险改动，走 P2 流程（24h 未批复默认批（maint-2026-11-02.md:53）
- 判定口径：当日产出文件数 + 证据密度（file:line / rc= / exit code / 哈希 / 工具调用）。（acceptance-20261101.md:26）
全文：state/briefs/butler-weekly-2026-W45.md
<!-- BUTLER-DIGEST:END -->
- 主公手册（2026-11-10 立）：docs/主公手册-20261110.md，调用 `bash tools/manual.sh [list|节号|关键词]`；工作模式=完成即顺延（plan-reflow 1 分钟间隔）
- 体积体检（2026-11-10 立，主公令）：每次体检必带体积/文件扫描。tools/space-audit.py（零 token/只读/1.5s，落 state/disk/latest.json + history.jsonl），已挂 20:30 简报「▍体积」与每日 03:47 四盘清理尾部；判定线 P0 盘≥90%、P1 盘≥85%/回收站≥100G/残包≥10G/膨胀≥125%。规则 docs/体积体检与空间清理-20261110.md
- 保留回收站清理（2026-11-10 主公批准 #972）：tools/archive-trash-purge.py 只删 openclaw-backups/_trash 内满 7 天、且有 ≥2 份同尺寸副本的归档，默认空跑、--apply 才删；主公 2026-11-10 18:20 令：超过 7 天的存档一律无用，可删最后一份（--allow-last-copy），每日任务已带该开关，台账 state/backup/archive-purge-ledger.jsonl；已挂每日 03:47，当日两次共实删 20 份，释放 1306G
- 自有队列上限（2026-11-10 主公问询后立硬性）：我的未结任务 ≤6 条，新增必先减；等主公/周期性/未来架构债/已降级四类不进账本（用 paused 或 docs 备查）；3 天内不会动手的不许留在 pending。当天从 17 条收到 3 条活跃（其余 11 冻结、2 合并撤销）

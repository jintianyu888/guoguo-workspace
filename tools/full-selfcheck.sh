#!/bin/bash
# full-selfcheck.sh —— OpenClaw 全栈自检 v1（2026-10-29 主公令）
# 覆盖：基础环境 / 运行时网关 / 任务脚本 / 管家渠道 / 备份安全 / 监控自愈
# 用法: bash tools/full-selfcheck.sh [--json]
set -u
export PATH=/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace; cd "$W" || exit 3
P=0; A=0; F=0; JSON=0; [ "${1:-}" = "--json" ] && JSON=1
OUT=""
ok(){ P=$((P+1)); OUT="$OUT$1
"; [ $JSON = 1 ] || printf '  ✅ %s\n' "$1"; }
wn(){ A=$((A+1)); OUT="$OUT$1
"; [ $JSON = 1 ] || printf '  ⚠️ %s\n' "$1"; }
ng(){ F=$((F+1)); OUT="$OUT$1
"; [ $JSON = 1 ] || printf '  ❌ %s\n' "$1"; }
sec(){ [ $JSON = 1 ] || { printf '\n【%s】\n' "$1"; }; }
H(){ timeout 6 curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/health 2>/dev/null || echo 000; }
uact(){ systemctl --user is-active "$1" >/dev/null 2>&1 && echo yes || echo no; }
uexp(){ [ "$(systemctl --user is-enabled "$1" 2>/dev/null)" = "enabled" ] && echo yes || echo no; }

sec "一、基础环境"
# 1 时区时间
TZOK=$(date +%Z); [ "$TZOK" = "CST" ] && ok "时区/时间正常 ($(date '+%F %T %Z'))" || wn "时区为 $TZOK（预期 CST）"
# 2 WSL 内存配置 vs 实际
WM=$(grep -i '^memory=' /mnt/c/Users/J/.wslconfig 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
MT=$(free -g | awk '/Mem:/{print $2}')
if [ -n "$WM" ]; then
  WMG=$(echo "$WM" | tr -dc '0-9')
  [ "$MT" -ge $((WMG - 6)) ] 2>/dev/null && ok "WSL 内存配置 $WM / 实际可用 ${MT}G" || wn "WSL 内存配置 $WM 但实际只有 ${MT}G"
else wn "未读到 .wslconfig 的 memory 配置"; fi
# 3 CPU 线程
NP=$(nproc); [ "$NP" -ge 12 ] && ok "CPU 线程 $NP" || wn "CPU 线程仅 $NP"
# 4 磁盘
ROOTU=$(df / | awk 'NR==2{gsub("%","",$5); print $5}')
[ "$ROOTU" -lt 80 ] && ok "根分区 使用 $ROOTU%" || { [ "$ROOTU" -lt 92 ] && wn "根分区 使用 $ROOTU%" || ng "根分区 使用 $ROOTU% 偏高"; }
DISKBAD=""
for d in /mnt/d /mnt/e /mnt/h /mnt/x; do
  if ! timeout 5 ls "$d" >/dev/null 2>&1; then DISKBAD="$DISKBAD $d"; fi
done
[ -z "$DISKBAD" ] && ok "盘符挂载正常 (d/e/h/x)" || ng "盘符不可访问:$DISKBAD"
# 5 swap
SW=$(free -m | awk '/Swap:/{printf "%d", ($2>0?$3*100/$2:0)}')
[ "$SW" -lt 50 ] && ok "Swap 使用 $SW%" || { [ "$SW" -lt 80 ] && wn "Swap 使用 $SW%" || ng "Swap 使用 $SW% 内存吃紧"; }
# 6 负载
L1=$(awk '{print $1}' /proc/loadavg); LOK=$(awk -v l="$L1" -v n="$NP" 'BEGIN{print (l < n*1.5)?"1":"0"}')
[ "$LOK" = "1" ] && ok "1分钟负载 $L1 / $NP 核" || wn "1分钟负载 $L1 / $NP 核偏高"
# 7 GPU
GS=$(timeout 8 /usr/lib/wsl/lib/nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader 2>/dev/null | head -1)
[ -n "$GS" ] && ok "GPU 可见: $GS" || wn "GPU 未取到（nvidia-smi 无输出）"

sec "二、运行时与网关"
# 8 服务
[ "$(uact openclaw-gateway)" = "yes" ] && ok "网关服务 active" || ng "网关服务未运行"
[ "$(uexp openclaw-gateway)" = "yes" ] && ok "网关开机自启 enabled" || ng "网关未设开机自启（重启后不自恢复）"
# 9 健康
H1=$(H); [ "$H1" = "200" ] && ok "健康端点 200" || ng "健康端点 $H1"
# 10 响应时延
MS=$(timeout 8 curl -s -o /dev/null -w '%{time_total}' http://127.0.0.1:18789/health 2>/dev/null | awk '{printf "%d", $1*1000}')
[ -n "$MS" ] && { [ "$MS" -lt 1500 ] && ok "健康响应 ${MS}ms" || wn "健康响应 ${MS}ms 偏慢"; }
# 11 内存
RSSM=$(systemctl --user show -p MemoryCurrent --value openclaw-gateway 2>/dev/null)
if [ -n "${RSSM:-}" ] && [ "$RSSM" != "[not set]" ] && [ "$RSSM" -gt 0 ] 2>/dev/null; then
  G=$((RSSM/1024/1024/1024))
  [ "$G" -lt 20 ] && ok "网关内存 ${G}G / 上限 36G" || { [ "$G" -lt 30 ] && wn "网关内存 ${G}G 偏高" || ng "网关内存 ${G}G 接近上限"; }
else wn "网关内存未取到"; fi
# 12 OOM / 重启
OOM=$(journalctl --user -u openclaw-gateway --since "24 hours ago" --no-pager 2>/dev/null | grep -ci "out of memory\|heap out of memory" || true)
[ "${OOM:-0}" -eq 0 ] && ok "近 24h 无 OOM" || ng "近 24h OOM $OOM 次"
RS=$(systemctl --user show -p NRestarts --value openclaw-gateway 2>/dev/null); RS=${RS:-0}
[ "$RS" -le 4 ] && ok "systemd 自动重启计数 $RS" || wn "systemd 自动重启计数 $RS（偏多）"
# 13-15 定时器
[ "$(uact oc-gateway-watchdog.timer)" = "yes" ] && ok "看门狗定时器 运行中" || ng "看门狗定时器 未运行"
[ "$(uact oc-restart-daily.timer)" = "yes" ] && ok "09:00 重启窗口 已启用" || wn "09:00 重启窗口 未启用"
[ "$(uact oc-landing-gate.timer)" = "yes" ] && ok "双审闸门巡检 运行中" || wn "双审闸门巡检 未运行"
# 16 版本
VN=$(timeout 25 openclaw --version 2>/dev/null | tail -1); NV=$(node -v 2>/dev/null)
[ -n "$VN" ] && ok "版本 $VN / Node $NV" || wn "版本未取到"
# 17 配置
CFG=$(timeout 40 openclaw config get agents --json 2>&1 | head -c 40)
case "$CFG" in {*) ok "配置文件可读取（agents 段）";; *) ng "配置读取异常: $(echo "$CFG" | head -c 50)";; esac

sec "三、任务与脚本"
# 18 cron 总量
CJ=$(timeout 40 openclaw cron list --json 2>/dev/null)
if [ -n "$CJ" ]; then
  TN=$(printf '%s' "$CJ" | python3 -c "import json,sys;d=json.load(sys.stdin);j=d if isinstance(d,list) else d.get('jobs',[]);print(len(j))" 2>/dev/null || echo 0)
  EN=$(printf '%s' "$CJ" | python3 -c "import json,sys;d=json.load(sys.stdin);j=d if isinstance(d,list) else d.get('jobs',[]);print(sum(1 for x in j if x.get('enabled')))" 2>/dev/null || echo 0)
  [ "${TN:-0}" -gt 50 ] && ok "定时任务 ${EN}/${TN} 启用" || ng "定时任务异常（${EN}/${TN}）"
else ng "定时任务列表读取失败"; fi
# 19 近期任务错误
ER=$(timeout 40 openclaw cron list --json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin); j=d if isinstance(d,list) else d.get('jobs',[])
bad=[x.get('name') for x in j if str(x.get('lastStatus','')).lower() in ('error','failed')]
print(len(bad)); print(','.join([b for b in bad[:3] if b]))" 2>/dev/null)
ERN=$(echo "$ER" | head -1); ERN=${ERN:-0}
[ "$ERN" -eq 0 ] && ok "无处于错误状态的任务" || wn "错误状态任务 $ERN 个（$(echo "$ER" | tail -1)）"
# 20 脚本语法
BADSH=0; BADPY=0
while IFS= read -r f; do bash -n "$f" >/dev/null 2>&1 || { BADSH=$((BADSH+1)); }; done < <(find tools -maxdepth 1 -name "*.sh" -type f 2>/dev/null)
while IFS= read -r f; do python3 -m py_compile "$f" >/dev/null 2>&1 || { BADPY=$((BADPY+1)); }; done < <(find tools -maxdepth 1 -name "*.py" -type f 2>/dev/null)
[ "$BADSH" -eq 0 ] && [ "$BADPY" -eq 0 ] && ok "脚本语法全通过（sh/py）" || ng "脚本语法错误：sh $BADSH 个 / py $BADPY 个"
# 21 关键脚本
MISS=""
for f in tools/restart-gateway.sh tools/safe-restart-gateway.sh tools/notify.sh tools/autofix.sh tools/full-selfcheck.sh tools/landing-gate.py tools/console-cmd.sh tools/backup-quiet.py; do
  [ -x "$f" ] || [ -f "$f" ] || MISS="$MISS $(basename $f)"
done
[ -z "$MISS" ] && ok "关键脚本齐全（8 项）" || ng "关键脚本缺失:$MISS"
# 22 双审合规
LG=$(timeout 120 python3 tools/landing-gate.py check 2>&1 | head -1)
case "$LG" in OK*) ok "敏感脚本双审回执匹配";; *) wn "敏感脚本存在未审改动（$(echo "$LG" | head -c 40)）";; esac

sec "四、管家与渠道"
# 23 渠道
CH=$(timeout 30 openclaw channels list --json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
if isinstance(d,list): print(len(d))
elif isinstance(d,dict):
    for k in ('channels','accounts','items','data'):
        if isinstance(d.get(k),list): print(len(d[k])); break
    else: print(len(d))
" 2>/dev/null || echo 0)
[ "${CH:-0}" -ge 1 ] && ok "已配置渠道 ${CH} 个" || wn "渠道数 ${CH}"
# 24 管家数量与工作区
AG=$(timeout 30 openclaw agents list --json 2>/dev/null | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d if isinstance(d,list) else d.get('agents',[])))" 2>/dev/null || echo 0)
[ "${AG:-0}" -ge 10 ] && ok "管家 agent ${AG} 个" || wn "管家 agent 仅 ${AG} 个"
# 25 渠道连通性（最近探测）
PB=$(ls -t state/*butler*probe* state/*channel*probe* 2>/dev/null | head -1)
if [ -n "$PB" ]; then
  AGEH=$(( ( $(date +%s) - $(stat -c %Y "$PB") ) / 3600 ))
  [ "$AGEH" -lt 30 ] && ok "管家连通性探测 ${AGEH}h 内有记录" || wn "管家连通性探测 ${AGEH}h 未更新"
else wn "未见管家连通性探测记录"; fi
# 26 ASR 链路
if [ -x tools/asr ] && [ -d tools/asr-venv ]; then
  if [ -f /home/j/.cache/asr.lock ]; then
    LK=$(( ( $(date +%s) - $(stat -c %Y /home/j/.cache/asr.lock) ) / 60 ))
    [ "$LK" -lt 30 ] && ok "语音转写链路就绪（锁 ${LK} 分钟）" || ng "语音锁卡住 ${LK} 分钟（语音会转不出）"
  else ok "语音转写链路就绪"; fi
else ng "语音转写链路缺失（asr 或 venv）"; fi

sec "五、备份与安全"
# 27 最近全量备份
BA=$(ls -t /mnt/e/openclaw-backups/*openclaw-backup.tar.gz 2>/dev/null | head -1)
if [ -n "$BA" ]; then
  AGEH=$(( ( $(date +%s) - $(stat -c %Y "$BA") ) / 3600 )); SZ=$(du -h "$BA" 2>/dev/null | cut -f1)
  [ "$AGEH" -lt 30 ] && ok "全量备份 ${AGEH}h 前，${SZ}" || wn "全量备份已 ${AGEH}h（>30h）"
else ng "找不到全量备份"; fi
# 28 三副本
CNT=0
for p in "/mnt/e/openclaw-backups/$(basename ${BA:-x})" "/mnt/h/openclaw-backups/$(basename ${BA:-x})"; do [ -f "$p" ] && CNT=$((CNT+1)); done
[ -n "$BA" ] && CNT=$((CNT+1))
[ "$CNT" -ge 3 ] && ok "备份副本 $CNT 份（E/H/本地）" || wn "备份副本仅 $CNT 份"
# 29 镜像一致性
MV=$(timeout 60 bash tools/backup-mirror-verify.sh 2>&1 | tail -1)
case "$MV" in *OK*|*一致*|*rc=0*) ok "E/H 镜像校验通过";; *) wn "镜像校验: $(echo "$MV" | head -c 50)";; esac
# 30 保留策略
RB=$(grep -c . tools/retention.env 2>/dev/null || echo 0)
[ "${RB:-0}" -ge 3 ] && ok "保留策略已配置" || wn "保留策略缺失"
# 31 明文密钥（只报）
SK=$(grep -c '"apiKey"[[:space:]]*:[[:space:]]*"' /home/j/.openclaw/openclaw.json 2>/dev/null || echo 0)
[ "${SK:-0}" -eq 0 ] && ok "配置内无明文 apiKey" || wn "存在 ${SK} 处明文 apiKey（需主公决定迁移）"
# 32 告警通道
[ -f /home/j/.config/feishu-alert-webhook ] && ok "告警 webhook 已配置" || wn "告警 webhook 缺失（告警可能发不出）"

sec "六、监控与自愈"
# 33 自检记录
[ -f state/work/selfcheck-history.log ] && ok "自检历史可追溯" || wn "自检历史空缺"
# 34 通知队列
NQ=$(ls state/notify-queue/*.json 2>/dev/null | wc -l)
[ "${NQ:-0}" -lt 50 ] && ok "通知队列积压 ${NQ}" || wn "通知队列积压 ${NQ}（可能发不出）"
# 35 崩溃自愈能力
[ -f tools/desktop-rescue.sh ] && [ -f tools/oneclick-rescue.sh ] && ok "网关卡死可自救（脚本齐全）" || ng "自救脚本缺失"
# 36 磁盘清理/回收站
[ -f state/trash-ledger.jsonl ] && ok "回收站台账存在（删除可追溯）" || wn "回收站台账缺失"

echo
if [ $JSON = 1 ]; then
  printf '%s' "$OUT"
else
  echo "----------------------------------------------"
  printf '结论：PASS %s / WARN %s / FAIL %s\n' "$P" "$A" "$F"
fi
mkdir -p state/work
printf '%s PASS=%s WARN=%s FAIL=%s\n' "$(date '+%F %T')" "$P" "$A" "$F" >> state/work/selfcheck-history.log
[ $F -eq 0 ] && exit 0 || exit 1

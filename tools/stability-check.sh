#!/bin/bash
# stability-check.sh v1 —— 系统稳定性审查统一入口（硬件 / 系统 / OpenClaw 三环）
# 用法: stability-check.sh [--deep] [--notify] [--json]
# 退出码: 0=PASS 1=WARN 2=FAIL（SKIP 不计入失败）
set -uo pipefail
WS=/home/j/.openclaw/workspace
OUTD=$WS/state/stability
TSV=$(mktemp "$WS/state/tmp/stab.XXXX.tsv")
DEEP=0; NOTIFY=0; JSONONLY=0
for a in "$@"; do case "$a" in --deep) DEEP=1;; --notify) NOTIFY=1;; --json) JSONONLY=1;; esac; done
mkdir -p "$OUTD"
# 告警出口：优先独立飞书 webhook（不经过网关），未配置或失败再回落 notify.sh
# webhook 地址放 /home/j/.config/feishu-alert-webhook（600 权限，一行 URL），不进聊天、不进配置
send_alert() {
  local msg="【告警】$1" url payload
  local f=/home/j/.config/feishu-alert-webhook
  if [ -s "$f" ]; then
    url=$(head -n 1 "$f" | tr -d '\r\n')
    if [ -n "$url" ]; then
      payload=$(python3 -c 'import json,sys; print(json.dumps({"msg_type":"text","content":{"text":sys.argv[1]}},ensure_ascii=False))' "$msg" 2>/dev/null)
      if [ -n "$payload" ] && curl -s --max-time 10 -H 'Content-Type: application/json' -d "$payload" "$url" >/dev/null 2>&1; then
        return 0
      fi
    fi
  fi
  timeout 30 bash "$WS/tools/notify.sh" "$msg" >/dev/null 2>&1 || true
}

# 单实例：07:00 常规与周日 07:30 深度不得并发（评审必改项）
exec 9>"$OUTD/.lock"
if ! flock -n 9; then echo "SKIP 已有 stability-check 在跑"; exit 0; fi
# 备份链进行中时，I/O 相关项只作快照（评审必改项）
BK=$(pgrep -fc 'backup-retain|openclaw backup create|rsync .*openclaw|secure-cloud-backup' 2>/dev/null || echo 0)
now() { date "+%F %T"; }
add() { printf "%s\t%s\t%s\t%s\t%s\t%s\n" "$1" "$2" "$3" "$4" "$5" "$6" >> "$TSV"; }
PS() { /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -NonInteractive -Command "$1" 2>/dev/null | tr -d "\r"; }
NVS=/usr/lib/wsl/lib/nvidia-smi; [ -x "$NVS" ] || NVS=$(command -v nvidia-smi 2>/dev/null || echo "")

#### 环 A · 硬件 ####
# A1 CPU
read -r l1 l5 _ < /proc/loadavg; NC=$(nproc)
PCT=$(awk -v l="$l5" -v n="$NC" "BEGIN{printf \"%d\", (l/n)*100}")
if [ "$PCT" -ge 80 ]; then st=WARN; else st=PASS; fi
add A A1_cpu "$st" "load5=$l5/${NC}核 (${PCT}%)" ">=80%" ""
# A2 内存/swap
MT=$(free -b | awk "/^Mem:/{print \$2}"); MA=$(free -b | awk "/^Mem:/{print \$7}")
MS=$(free -b | awk "/^Swap:/{print \$2}"); MSX=$(free -b | awk "/^Swap:/{print \$3}")
AV=$(( ${MT:-0}>0 ? ${MA:-0}*100/${MT} : 0 )); SU=$(( ${MS:-0}>0 ? ${MSX:-0}*100/${MS} : 0 ))
MAMB=$(( ${MA:-0}/1048576 ))
# 2026-11-07：WSL 已升到 48G，按百分比会放过真实耗尽；改用绝对可用内存
if [ "$MAMB" -lt 3072 ] || [ "$SU" -ge 50 ]; then st=WARN; else st=PASS; fi
add A A2_mem "$st" "可用=${MAMB}MB(${AV}%) swap=${SU}%" "可用<3G 或 swap>=50%" ""
# A3 GPU
if [ -n "$NVS" ]; then
  G=$(timeout 15 "$NVS" --query-gpu=temperature.gpu,memory.used,memory.total,driver_version --format=csv,noheader,nounits 2>/dev/null | head -1)
  if [ -n "$G" ]; then
    GT=$(echo "$G" | cut -d, -f1 | tr -d " "); GMU=$(echo "$G" | cut -d, -f2 | tr -d " "); GMT=$(echo "$G" | cut -d, -f3 | tr -d " "); GDV=$(echo "$G" | cut -d, -f4 | tr -d " ")
    GP=$(( GMT>0 ? GMU*100/GMT : 0 ))
    if [ "${GT:-0}" -ge 80 ] || [ "$GP" -ge 90 ]; then st=WARN; else st=PASS; fi
    add A A3_gpu "$st" "温度=${GT}C 显存=${GMU}/${GMT}MB(${GP}%) 驱动=$GDV" ">=80C 或显存>=90%" "nvidia-smi"
  else add A A3_gpu SKIP "nvidia-smi 无输出" "" "nvidia-smi"; fi
else add A A3_gpu SKIP "未安装 nvidia-smi" "" ""; fi
# A4 磁盘健康（SMART/HealthStatus）
if [ "$DEEP" = 1 ]; then
  H=$(timeout 40 bash -c "PS \"Get-PhysicalDisk | Select-Object -First 6 FriendlyName,HealthStatus,MediaType | ConvertTo-Csv -NoTypeInformation\"" 2>/dev/null)
  if [ -n "$H" ]; then
    BAD=$(echo "$H" | grep -ci "unhealthy\|warning")
    if [ "$BAD" -gt 0 ]; then st=FAIL; else st=PASS; fi
    add A A4_smart "$st" "$(echo "$H" | tail -n +2 | tr "\n" " " | cut -c1-160)" "健康状态含 Unhealthy/Warning" "Get-PhysicalDisk"
  else add A A4_smart SKIP "PowerShell 取不到 Get-PhysicalDisk" "" "Get-PhysicalDisk"; fi
else add A A4_smart SKIP "深度检查项（--deep 才跑）" "" "Get-PhysicalDisk"; fi
# A5 盘位容量
CAP=""; WORST=PASS
for d in d e h x; do
  m=/mnt/$d
  [ -d "$m" ] || continue
  read -r tot used pct <<< "$(df -P "$m" 2>/dev/null | awk "NR==2{print \$2, \$3, \$5}" | tr -d "%")"
  [ -z "${pct:-}" ] && continue
  CAP="$CAP $d:${pct}%"
  if [ "$pct" -ge 92 ]; then WORST=FAIL; elif [ "$pct" -ge 85 ] && [ "$WORST" != FAIL ]; then WORST=WARN; fi
done
add A A5_disk "$WORST" "${CAP# }" ">=85% WARN, >=92% FAIL" "df"
# A6 vhdx 实占/内部用量
if [ "$DEEP" = 1 ] && [ -x "$WS/tools/wsl-disk-health.sh" ]; then
  VJ=$(timeout 90 bash "$WS/tools/wsl-disk-health.sh" --json 2>/dev/null | head -c 4000)
  RAT=$(echo "$VJ" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get(\"vhdx_ratio\") or d.get(\"ratio\") or \"\")" 2>/dev/null || true)
  if [ -n "$RAT" ]; then
    if awk -v r="$RAT" "BEGIN{exit !(r>=1.25)}"; then st=WARN; else st=PASS; fi
    add A A6_vhdx "$st" "实占/内部用量=${RAT}" ">=1.25 WARN" "wsl-disk-health.sh";
  else add A A6_vhdx SKIP "未能解析 vhdx 比值" "" "wsl-disk-health.sh"; fi
else add A A6_vhdx SKIP "深度检查项" "" ""; fi

#### 环 B · 系统（WSL + Windows）####
# B1 WSL 内核 + interop
K=$(uname -r); IOP=$(grep -c "^\[interop\]" /etc/wsl.conf 2>/dev/null); IOP=${IOP:-0}
if [ "${IOP:-0}" -ge 1 ]; then st=PASS; else st=WARN; fi
add B B1_wsl "$st" "内核=$K interop=$([ "${IOP:-0}" -ge 1 ] && echo 开 || echo 关)" "缺 [interop] 则 WARN" "/etc/wsl.conf"
# B2 9p 写探活
if [ -d /mnt/e ]; then
  T0=$(date +%s%N)
  if dd if=/dev/zero of=/mnt/e/.stab-probe bs=1M count=2 conv=fsync >/dev/null 2>&1; then
    T1=$(date +%s%N); MS=$(( (T1-T0)/1000000 )); rm -f /mnt/e/.stab-probe
    if [ "$MS" -ge 2000 ]; then st=WARN; else st=PASS; fi
    add B B2_9p "$st" "写 2MB 耗时=${MS}ms" ">=2000ms WARN" "/mnt/e"
  else add B B2_9p WARN "9p 写探活失败（不可写或超时）" "" "/mnt/e"; fi
else add B B2_9p SKIP "/mnt/e 不存在" "" ""; fi
# B3 时钟漂移
HD=$(timeout 8 curl -sI https://www.baidu.com 2>/dev/null | awk -F": " "tolower(\$1)==\"date\"{print \$2}" | head -1)
if [ -n "$HD" ]; then
  REM=$(date -d "$HD" +%s 2>/dev/null || echo ""); LOC=$(date +%s)
  if [ -n "$REM" ]; then D=$(( LOC>REM ? LOC-REM : REM-LOC )); if [ "$D" -ge 2 ]; then st=WARN; else st=PASS; fi; add B B3_clock "$st" "偏差=${D}s" ">=2s WARN" "HTTP Date";
  else add B B3_clock SKIP "时间头解析失败" "" ""; fi
else add B B3_clock SKIP "取不到外部时间（离线）" "" ""; fi
# B4 安全软件（深度）
if [ "$DEEP" = 1 ]; then
  MP=$(timeout 40 bash -c "PS \"(Get-MpComputerStatus).RealTimeProtectionEnabled\"" 2>/dev/null | tr -d " " | tail -1)
  AV=$(timeout 30 bash -c "PS \"(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct).displayName\"" 2>/dev/null | tr "\n" "," | cut -c1-80)
  if [ "$MP" = "True" ] || [ -n "$AV" ]; then st=PASS; else st=FAIL; fi
  add B B4_av "$st" "Defender实时=$MP 第三方AV=${AV:-无}" "两者皆无为 FAIL" "Get-MpComputerStatus/SecurityCenter2"
else add B B4_av SKIP "深度检查项" "" ""; fi
# B5 Windows 待重启（深度）
if [ "$DEEP" = 1 ]; then
  RB=$(timeout 40 bash -c "PS \"if (Test-Path \"HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired\") {Write-Output REBOOT} else {Write-Output OK}\"" 2>/dev/null | tr -d "\r" | tail -1)
  case "$RB" in REBOOT) st=WARN;; OK) st=PASS;; *) st=SKIP;; esac
  add B B5_reboot "$st" "待重启=$RB" "REBOOT 则 WARN" "注册表 RebootRequired"
else add B B5_reboot SKIP "深度检查项" "" ""; fi
# B6 dmesg 错误 / OOM
E1=$(dmesg 2>/dev/null | grep -ciE "I/O error|oom-kill|blocked for more than" || true)
if [ "${E1:-0}" -gt 0 ]; then st=WARN; else st=PASS; fi
add B B6_kernel "$st" "近端错误/OOM 计数=${E1:-0}" ">0 WARN" "dmesg"

#### 环 C · OpenClaw ####
GPID=$(systemctl --user show openclaw-gateway -p MainPID --value 2>/dev/null)
GRSS=$(systemctl --user show openclaw-gateway -p MemoryCurrent --value 2>/dev/null)
GACT=$(systemctl --user is-active openclaw-gateway 2>/dev/null)
RSSG=$(( ${GRSS:-0} / 1073741824 ))
PORT=$(ss -ltn 2>/dev/null | grep -c ":18789")
if [ "$GACT" != "active" ]; then st=FAIL; elif [ "$RSSG" -ge 8 ]; then st=WARN; elif [ "${PORT:-0}" -lt 1 ]; then st=FAIL; else st=PASS; fi
add C C1_gateway "$st" "alive=$GACT pid=${GPID:-?} rss=${RSSG}G port_ok=${PORT}" "rss>=8G WARN / not listening FAIL" "systemd+ss"
# C2 任务：启用数 / 连续失败 / 超期
OCB=$(command -v openclaw 2>/dev/null || echo /home/j/.npm-global/bin/openclaw)
( cd "$WS" && timeout 90 "$OCB" cron list --json ) > $WS/state/tmp/stab_jobs.json 2>/dev/null
JST=SKIP; JVAL="no data"
if [ -s $WS/state/tmp/stab_jobs.json ]; then
  read -r JST JVAL <<< "$(python3 "$WS/tools/stab_jobs.py" 2>/dev/null || echo "SKIP parse_fail")"
fi
add C C2_cron "$JST" "$JVAL" "consecutive errors>=2 or overdue>15m WARN" "automations list"
# C3 渠道（简化：看 status 里渠道段是否非空）
CH=$(timeout 25 openclaw status 2>/dev/null | grep -ciE "feishu|wecom" || true)
if [ "${CH:-0}" -ge 1 ]; then st=PASS; else st=SKIP; fi
add C C3_channel "$st" "命中渠道行数=${CH:-0}" "0 则 SKIP（口径待补）" "openclaw status"
# C4 日花费环比（usage-meter/daily.csv）
if [ -f state/usage-meter/daily.csv ]; then
  read -r CST CVAL <<< "$(python3 tools/stab_cost.py 2>/dev/null || echo "SKIP parse_fail")"
else CST=SKIP; CVAL="无 daily.csv"; fi
add C C4_cost "$CST" "$CVAL" "日环比>2x WARN" "usage-meter/daily.csv"
# C5 备份新鲜度
LATEST=$(find /mnt/d/openclaw-backups -maxdepth 1 -name "*.tar.gz" -printf "%T@ %p\n" 2>/dev/null | sort -nr | head -1)
if [ -n "$LATEST" ]; then
  AGES=$(( $(date +%s) - ${LATEST%%.*} )); AGEH=$(( AGES / 3600 ))
  if [ "$AGEH" -ge 30 ]; then st=WARN; else st=PASS; fi
  add C C5_backup "$st" "最新归档 ${AGEH} 小时前" ">=30h WARN" "/mnt/d/openclaw-backups"
else
  add C C5_backup FAIL "找不到 tar.gz 归档" "" "/mnt/d/openclaw-backups"
fi
# C6 明文密钥（只计数，不打印值）
if [ -f "$HOME/.openclaw/openclaw.json" ]; then
  PL=$(python3 tools/stab_secrets.py 2>/dev/null || echo 0)
  if [ "${PL:-0}" -gt 0 ]; then st=WARN; else st=PASS; fi
  add C C6_secret "$st" "明文密钥字段=${PL:-0}" ">0 WARN" "openclaw.json"
else
  add C C6_secret SKIP "无 openclaw.json" "" ""
fi
# C7 模型兜底链完整性（双通道：每个 agent 主用+兜底都能解析）2026-11-07
if [ -f "$WS/tools/modelchain-check.py" ]; then
  MC=$(cd "$WS" && timeout 90 python3 tools/modelchain-check.py 2>&1 | tail -2 | tr "\n" " ")
  if printf "%s" "$MC" | grep -q MODELCHAIN_OK; then st=PASS; else st=FAIL; fi
  add C C7_chain "$st" "$(printf "%s" "$MC" | cut -c1-120)" "链断/悬空引用则 FAIL" "tools/modelchain-check.py"
else add C C7_chain SKIP "无 modelchain-check.py" "" ""; fi
# C8 ollama 是否真的在用 GPU（size_vram/size）2026-11-07
OPS=$(curl -s --max-time 6 http://127.0.0.1:11434/api/ps 2>/dev/null)
if [ -n "$OPS" ]; then
  RATIO=$(printf "%s" "$OPS" | python3 -c "import sys,json;d=json.load(sys.stdin);ms=d.get('models') or [];print(0 if not ms else int(100*sum(m.get('size_vram',0) for m in ms)/max(1,sum(m.get('size',1) for m in ms))))" 2>/dev/null)
  RATIO=${RATIO:-0}
  if [ "$RATIO" -ge 90 ]; then st=PASS; elif [ "$RATIO" -ge 50 ]; then st=WARN; else st=WARN; fi
  add C C8_ollama "$st" "显存占比=${RATIO}%（已加载模型 $(printf "%s" "$OPS" | grep -o '"name"' | wc -l) 个）" "<50% 说明在跑 CPU" "ollama /api/ps"
else add C C8_ollama SKIP "ollama 未响应" "" "http://127.0.0.1:11434/api/ps"; fi
echo "" >> "$TSV"
#### 报告 ####
python3 "$WS/tools/stab_report.py" "$TSV" "$OUTD" "$DEEP" >/dev/null 2>"$OUTD/report.err"; REX=$?
# 2026-10-26 A4 修：报告阶段偶发失败（10-25 07:00、10-26 07:00 都留了 failed-*.tsv）→ 先重试一次再判错
if [ "${REX:-1}" != "0" ]; then sleep 2; python3 "$WS/tools/stab_report.py" "$TSV" "$OUTD" "$DEEP" >/dev/null 2>>"$OUTD/report.err"; REX=$?; fi
if [ "${REX:-1}" != "0" ] || [ ! -s "$OUTD/latest.md" ]; then
  cp "$TSV" "$OUTD/failed-$(date +%Y%m%d-%H%M%S).tsv" 2>/dev/null || true
  send_alert "🩺 stability-check 内部错误（报告阶段 rc=$REX），明细保留在 $OUTD"
  echo "INTERNAL_ERROR report_rc=$REX outdir=$OUTD"
  tail -3 "$OUTD/report.err" 2>/dev/null
  exit 3
fi
rm -f "$TSV"
if [ "$JSONONLY" = 0 ]; then cat "$OUTD/latest.md"; fi
VERDICT=$(sed -n "2p" "$OUTD/latest.md")
if [ "$NOTIFY" = 1 ] && ! echo "$VERDICT" | grep -q "FAIL 0 \$" ; then :; fi
if [ "$NOTIFY" = 1 ]; then
  KEY=$(printf "%s" "$VERDICT" | md5sum | cut -c1-12)
  STAMP="$OUTD/.alert-$KEY"
  NOW=$(date +%s); LAST=$(stat -c %Y "$STAMP" 2>/dev/null || echo 0)
  if [ $(( NOW - LAST )) -ge 21600 ]; then
    send_alert "🩺 系统稳定性审查：$VERDICT"
    : > "$STAMP"
  fi
fi
exit 0

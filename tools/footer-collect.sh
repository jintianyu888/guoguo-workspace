#!/usr/bin/env bash
# footer-collect.sh v2 - 角标数据预采集（零 token）。取不到写「未采集」，绝不编造。
W=/home/j/.openclaw/workspace; OUT=$W/state/footer.json; mkdir -p "$W/state"
TS=$(date '+%F %T')
BAL=$(timeout 20 bash $W/tools/ds-balance.sh 2>/dev/null | head -1); [ -n "$BAL" ] || BAL="未采集"
PEAK=$(timeout 20 bash $W/tools/peak-status.sh 2>/dev/null | tr "\n" "|"); [ -n "$PEAK" ] || PEAK="未采集"
CORES=$(nproc); L1=$(cut -d" " -f1 /proc/loadavg)
MEM=$(awk "/MemTotal/{t=\$2}/MemAvailable/{a=\$2}END{printf \"%.0f%%(%.1f/%.1fGB)\",(t-a)*100/t,(t-a)/1048576,t/1048576}" /proc/meminfo)
DISK=$(df -h / /mnt/c 2>/dev/null | awk "NR>1{printf \"%s %s \", \$6, \$5}")
NVS="/usr/lib/wsl/lib/nvidia-smi"; [ -x "$NVS" ] || NVS=$(command -v nvidia-smi 2>/dev/null)
if [ -x "$NVS" ]; then GPU=$("$NVS" --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader 2>/dev/null | head -1); [ -n "$GPU" ] || GPU="未采集"; else GPU="无独显(3070未装)"; fi
GW=$(systemctl --user show openclaw-gateway -p ActiveEnterTimestamp -p MemoryCurrent 2>/dev/null | tr "\n" " "); [ -n "$GW" ] || GW="未采集"
JOBERR=$(timeout 25 openclaw automations list 2>/dev/null | grep -ciE "error|failed")
TODO=$(grep -c "^- \[" $W/state/pending-tasks.md 2>/dev/null); [ -n "$TODO" ] || TODO=0
ALERT=$(grep -cE "🔴|待处理|open" $W/state/security-alerts.md 2>/dev/null); [ -n "$ALERT" ] || ALERT=0
BK=$(cat $W/state/backup-report.md 2>/dev/null | head -1); [ -n "$BK" ] || BK="未采集"
mountpoint -q /mnt/nas 2>/dev/null && [ -d /mnt/nas/archive ] && NAS="通" || NAS="不通"
curl -s -m 6 -o /dev/null https://api.deepseek.com 2>/dev/null && DS="通" || DS="不通"
python3 - "$OUT" "$TS" "$BAL" "$PEAK" "$CORES" "$L1" "$MEM" "$DISK" "$GPU" "$GW" "$JOBERR" "$TODO" "$ALERT" "$BK" "$NAS" "$DS" << "PY"
import json,sys
a=sys.argv[1:]
out,ts,bal,peak,cores,l1,mem,disk,gpu,gw,joberr,todo,alert,bk,nas,ds=a
json.dump({'ts':ts,'balance':bal,'peak':peak,'cpu':{'cores':cores,'load1':l1},'mem':mem,'disk':disk,'gpu':gpu,'gateway':gw.strip(),'jobErrors':joberr,'todos':todo,'alerts':alert,'backup':bk,'nas':nas,'deepseekApi':ds},open(out,'w'),ensure_ascii=False,indent=1)
# 2026-09-28 18:3x 主公令：本脚本输出仅内部用，不再打印（避免被投递成刷屏消息）
# print(open(out).read())
PY
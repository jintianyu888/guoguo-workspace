#!/bin/bash
# backup-watchdog.sh v1.0 —— 备份链看门狗（零 token，只读取证 + 告警）
# 2026-11-15 立：此前 11-07 起无任何 backup 定时器，失败全靠人发现
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
LOG=$W/state/work/backup-watchdog.log
STAGE=/home/j/backup-stage
D=/mnt/d/openclaw-backups
X=/mnt/x/openclaw-backups
. $W/tools/nas-config.sh 2>/dev/null || true
NAS=${NAS_ARCHIVES:-/mnt/nas/archive/jinyu/openclaw-archives}
now=$(date +%s)
say() { echo "[$(date "+%F %T")] $*" >> "$LOG"; }
alert() { say "ALERT $1"; bash $W/tools/notify.sh "$1" "$2" >/dev/null 2>&1 || true; }
fail=0

# 1 最新全量归档年龄（D 盘为准，>30h 视为断档）
newest=$(ls -t $D/*.tar.gz 2>/dev/null | head -1)
if [ -z "$newest" ]; then alert "备份断档：D 盘无归档" "openclaw-backups 目录为空，检查备份任务"; fail=1
else age=$(( (now - $(stat -c %Y "$newest")) / 3600 )); say "最新归档 $(basename "$newest") ${age}h 前"; [ "$age" -gt 30 ] && { alert "备份断档：最新归档 ${age}h 前" "超过 30h 无新归档，检查 01:00 任务"; fail=1; }; fi

# 2 暂存泄漏（tar.gz 超过 6h 未清）
leak=$(find $STAGE -maxdepth 1 -name "*.tar.gz" -mmin +360 2>/dev/null | wc -l)
[ "$leak" -gt 0 ] && { alert "暂存泄漏：$leak 个归档滞留 >6h" "backup-stage 未清理，vhdx 会被撑大"; fail=1; } || say "暂存无滞留"

# 3 当日 NAS 副本（10:00 后检查；含 .part 视为未完成）
hh=$(date +%H)
if [ "$hh" -ge 10 ]; then
  today=$(date +%Y-%m-%d)
  if mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
    done_n=$(ls $NAS/*"$today"*.tar.gz 2>/dev/null | wc -l)
    part_n=$(ls $NAS/*"$today"*.tar.gz.part 2>/dev/null | wc -l)
    say "NAS 当日副本 完整=$done_n 残片=$part_n"
    [ "$done_n" -eq 0 ] && { alert "NAS 当日无完整副本" "今日归档未推到 NAS（残片 $part_n 个），检查 nas-push 日志"; fail=1; }
  else say "NAS 未挂载，跳过检查"; fi
fi

# 4 备份类 cron 连续报错（每 2 小时查一次，避免频繁拉 CLI）
if [ $(( $(date +%H) % 2 )) -eq 0 ] && [ "$(date +%M)" -lt 30 ]; then
  tmp=$(mktemp)
  timeout 120 openclaw cron list --json --timeout 60000 > "$tmp" 2>/dev/null || true
  bad=$(python3 - "$tmp" <<PYEOF
import json,sys
try:
    d=json.load(open(sys.argv[1]))
except Exception:
    print(""); raise SystemExit
jobs=d if isinstance(d,list) else d.get("jobs",d)
names=[]
for x in jobs:
    n=x.get("name") or ""
    st=(x.get("state") or {})
    if any(w in n for w in ["备份","归档","镜像"]) and int(st.get("consecutiveErrors") or 0)>=2:
        names.append(n+"("+str(st.get("consecutiveErrors"))+"次)")
print(", ".join(names))
PYEOF
  )
  rm -f "$tmp"
  [ -n "$bad" ] && { alert "备份任务连续报错：$bad" "openclaw cron list 显示备份类任务连续失败，检查日志"; fail=1; } || say "备份类 cron 无连续报错"
fi


# 2026-11-15 追加：保留策略预演回执（zhipu 硬条件4）
M=/home/j/.openclaw/workspace/state/work/retention-receipt-needed
if [ -f "$M" ]; then
  d=$(cat "$M" 2>/dev/null)
  age=$(( ( $(date +%s) - $(date -d "$d" +%s 2>/dev/null || date +%s) ) / 86400 ))
  if [ "$age" -ge 3 ]; then alert "保留策略预演 $d 未回执（${age}天）" "已超过 3 天未确认，本期不算已验证；回执：bash tools/retention-ack.sh"; fail=1; else say "保留策略预演 $d 待回执（${age}天）"; fi
else
  say "保留策略回执：无待确认项"
fi

if [ "$fail" -eq 0 ]; then say "OK 全绿"; fi
exit 0
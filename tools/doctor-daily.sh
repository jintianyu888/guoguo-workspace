#!/usr/bin/env bash
# doctor-daily.sh v1 —— 每日只读体检（2026-11-02 主公问"doctor 要不要定期跑"）
# 定位：openclaw doctor 的「只读」用法。**绝对不带 --fix**：
#   --fix 会真改配置/迁移权限/清 scratch/删失效 grant，不适合无人值守自动执行。
# 做法：跑 doctor -> 落全量日志 -> 剥掉 clean-close 噪声 -> 提取问题行 -> 与昨日对比只报新增。
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
OUT=$W/state/doctor-daily
mkdir -p "$OUT"
RAW=$OUT/doctor-$(date +%Y%m%d).log
SUM=$OUT/last-summary.txt
PREV=$OUT/prev-issues.txt
CUR=$OUT/cur-issues.txt
LOCK=$W/state/.doctor-daily.lock
log(){ echo "[$(date '+%F %T')] $*" >> "$OUT/run.log"; }

exec 9>"$LOCK"
flock -w 60 9 || { log "上一轮仍在运行，跳过本轮"; exit 0; }

# 清理 7 天前的历史日志/问题集，防目录无限增长
find "$OUT" -maxdepth 1 -type f \( -name 'doctor-*.log' -o -name 'doctor-*.log.clean' \) -mtime +7 -delete 2>/dev/null || true

# 1) 跑只读诊断（不传 --fix/--repair/--force）
timeout 600 openclaw doctor > "$RAW" 2>&1
rc=$?

# 2) 剥噪声：clean-close receipt 等逐代理刷屏行
grep -vE 'clean-close receipt|active-leases' "$RAW" > "$RAW.clean" 2>/dev/null || true

# 3) 提取问题行（warn/error/fail/缺失/损坏/过期/stale/fix 建议）
grep -iE '\b(error|fail|failed|warn|warning|missing|corrupt|stale|refus|blocked|invalid)\b|建议运行|recommend|should run' "$RAW.clean" \
  | sed 's/[[:space:]]\+/ /g' | sort -u > "$CUR" 2>/dev/null || : > "$CUR"

# 4) 与昨日问题集对比，只对新出现的告警
NEW=$(comm -13 <(sort -u "$PREV" 2>/dev/null) <(sort -u "$CUR") 2>/dev/null | head -20)
cp -f "$CUR" "$PREV" 2>/dev/null || true

{
  echo "doctor rc=$rc | 问题行 $(wc -l < "$CUR") | 新增 $(echo -n "$NEW" | grep -c . )"
  head -15 "$CUR"
} > "$SUM"

log "rc=$rc issues=$(wc -l < "$CUR") new=$(echo -n "$NEW" | grep -c .)"

# 5) 只在「rc!=0」或「出现新增问题」时告警，避免天天刷屏
if [ "$rc" -ne 0 ] || [ -n "$NEW" ]; then
  MSG="doctor 体检：rc=$rc，问题 $(wc -l < "$CUR") 条，新增：
$(echo "$NEW" | head -10)"
  [ -f "$W/tools/notify.sh" ] && timeout 90 bash "$W/tools/notify.sh" --alert "$MSG" >/dev/null 2>&1 || true
fi
exit 0

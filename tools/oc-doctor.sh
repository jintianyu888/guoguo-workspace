#!/usr/bin/env bash
# oc-doctor.sh v1.0 — OpenClaw 一键体检（零 token，只读）
# 用法: bash tools/oc-doctor.sh [--json] [--quiet]  退出码 0=绿/仅WARN, 1=有FAIL
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
OUT=$W/state/health
mkdir -p "$OUT"
TS=$(date +%Y%m%d-%H%M%S)
JSON=0; QUIET=0
for a in "$@"; do case "$a" in --json) JSON=1;; --quiet) QUIET=1;; esac; done
P=0; WA=0; F=0; LINES=""
say() { LINES="$LINES$1"$'\n'; [ "$QUIET" = "1" ] || echo "$1"; }
ok()   { P=$((P+1)); say "✅ $1"; }
warn() { WA=$((WA+1)); say "⚠️  $1"; }
bad()  { F=$((F+1)); say "❌ $1"; }
info() { say "   $1"; }
T0=$(date +%s)
code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:18789/health || echo 000)
pid=$(pgrep -f "openclaw.*gateway" | head -1)
if [ "$code" = "200" ]; then ok "网关 HTTP 200 (pid ${pid:-none})"; else bad "网关异常 http=$code"; fi
pcode=$(curl -s -o /dev/null -w "%{http_code}" --max-time 6 http://127.0.0.1:8899/ || echo 000)
if [ "$pcode" = "200" ]; then ok "果果助手 8899 200"; else bad "果果助手异常 http=$pcode"; fi
for u in openclaw-gateway guoguo oc-face-guard oc-sms-inbox; do
  st=$(systemctl --user is-active "$u" 2>/dev/null)
  if [ "$st" = "active" ]; then ok "服务 $u active"; else warn "服务 $u ${st:-unknown}"; fi
done
failed=$(systemctl --user list-units --failed --no-legend 2>/dev/null | wc -l)
if [ "$failed" -eq 0 ]; then ok "无 failed 单元"; else warn "failed 单元 $failed 个"; fi
for p in 18789 8899; do
  if ss -ltn 2>/dev/null | grep -q ":$p "; then ok "端口 $p 监听"; else bad "端口 $p 未监听"; fi
done
avail=$(free -m | awk '/^Mem:/{print $7}')
if [ -n "$avail" ] && [ "$avail" -ge 4000 ]; then ok "可用内存 ${avail}MB"; else warn "可用内存 ${avail:-?}MB"; fi
sw=$(free -m | awk '/^Swap:/{if($2>0) print int($3*100/$2); else print 0}')
if [ -n "$sw" ] && [ "$sw" -lt 30 ]; then ok "swap 使用 ${sw}%"; else warn "swap 使用 ${sw:-?}%"; fi
chk_disk() {
  mnt=$1; label=$2; warnp=$3
  avail=$(df -Pm "$mnt" 2>/dev/null | awk 'NR==2{print $4}')
  if [ -z "$avail" ]; then warn "$label 未挂载"; return; fi
  use=$(df -Pm "$mnt" 2>/dev/null | awk 'NR==2{gsub("%","",$5); print $5}')
  if [ "$use" -ge 95 ]; then bad "$label 使用 ${use}% 剩 $((avail/1024))G"
  elif [ "$use" -ge "$warnp" ]; then warn "$label 使用 ${use}% 剩 $((avail/1024))G"
  else ok "$label 使用 ${use}% 剩 $((avail/1024))G"; fi
}
chk_disk / "根分区" 85
chk_disk /mnt/x "X盘(镜像)" 85
chk_disk /mnt/d "D盘(备份)" 90
chk_disk /mnt/e "E盘" 95
chk_disk /mnt/h "H盘" 95
if [ -f /mnt/x/WSL/Ubuntu/ext4.vhdx ]; then
  vhdx=$(stat -c %s /mnt/x/WSL/Ubuntu/ext4.vhdx 2>/dev/null)
  used=$(df -B1 / 2>/dev/null | awk 'NR==2{print $3}')
  if [ -n "$vhdx" ] && [ -n "$used" ] && [ "$used" -gt 0 ]; then
    bloat=$(( (vhdx - used) / 1024 / 1024 / 1024 ))
    if [ "$bloat" -ge 150 ]; then warn "vhdx 冗余 ${bloat}G（建议压缩）"
    elif [ "$bloat" -ge 80 ]; then info "vhdx 冗余 ${bloat}G（可压不急）"
    else ok "vhdx 冗余 ${bloat}G"; fi
  fi
fi
stage=$(du -sm /home/j/backup-stage 2>/dev/null | awk '{print $1}')
if [ -n "$stage" ] && [ "$stage" -ge 20000 ]; then warn "backup-stage 残留 $((stage/1024))G（推完未删）"
elif [ -n "$stage" ] && [ "$stage" -gt 0 ]; then ok "backup-stage $((stage/1024))G"; fi
archsz=$(du -sm /home/j/.openclaw-archives 2>/dev/null | awk '{print $1}')
if [ -n "$archsz" ] && [ "$archsz" -gt 1024 ]; then warn "归档躺在 ext4: .openclaw-archives $((archsz/1024))G（应迁 NAS）"; else ok "ext4 无滞留归档"; fi
open=$(python3 $W/tools/tasks-db.py list 2>/dev/null | grep -c -E "\[pending|\[in_progress")
if [ -n "$open" ] && [ "$open" -gt 6 ]; then warn "未结任务 ${open} 条（上限 6）"; else ok "未结任务 ${open:-0} 条"; fi
cron_out=$(timeout 45 openclaw cron list 2>/dev/null)
if [ -n "$cron_out" ]; then
  en=$(( $(echo "$cron_out" | wc -l) - 1 ))
  if [ "$en" -le 100 ]; then ok "cron 启用 ${en} 条"; else warn "cron 启用 ${en} 条（超 100）"; fi
  err=$(echo "$cron_out" | grep -c " error")
  if [ "$err" -eq 0 ]; then ok "cron 无报错任务"; else warn "cron 报错 ${err} 个"; fi
else warn "cron 列表取不到"; fi
newest=$(ls -t /mnt/d/openclaw-backups/*tar.gz 2>/dev/null | head -1)
if [ -n "$newest" ]; then
  age=$(( ( $(date +%s) - $(stat -c %Y "$newest") ) / 3600 ))
  sz=$(( $(stat -c %s "$newest") / 1024 / 1024 / 1024 ))
  if [ "$age" -le 30 ]; then ok "最新全量 ${age}h 前 (${sz}G)"; else warn "最新全量 ${age}h 前（>30h）"; fi
else bad "D 盘无备份归档"; fi
xfree=$(df -Pm /mnt/x | awk 'NR==2{print int($4/1024)}')
if [ -n "$xfree" ] && [ "$xfree" -ge 150 ]; then ok "X 盘可用 ${xfree}G（够镜像）"; else warn "X 盘可用 ${xfree:-?}G（镜像可能失败）"; fi
nline=$(timeout 20 openclaw nodes list 2>/dev/null | head -1)
paired=$(printf "%s" "$nline" | awk -F'Paired: ' '{print $2}' | tr -dc '0-9')
online=$(timeout 20 openclaw nodes list 2>/dev/null | awk '/ago/ && !/d ago/ {c++} END{print c+0}')
if [ -n "$paired" ] && [ "$paired" -ge 1 ]; then
  if [ "$online" -ge 1 ]; then ok "节点 $paired 个，$online 个近期在线"; else warn "节点 $paired 个但全部离线"; fi
else info "节点状态未取到"; fi
errs=$(journalctl --user -u openclaw-gateway --since "-24h" --no-pager 2>/dev/null | grep -c ERROR)
if [ -n "$errs" ] && [ "$errs" -lt 200 ]; then ok "网关 24h 错误行 ${errs}"; else warn "网关 24h 错误行 ${errs:-?}"; fi
tm=$(systemctl --user list-timers --no-legend 2>/dev/null | grep -c "oc-")
if [ -n "$tm" ] && [ "$tm" -ge 8 ]; then ok "oc-* 定时器 ${tm} 个"; else warn "oc-* 定时器仅 ${tm:-0} 个"; fi
T1=$(date +%s); dur=$((T1-T0))
say ""
say "── 体检汇总: PASS $P / WARN $WA / FAIL $F  (${dur}s) ──"
LOG=$OUT/oc-doctor-$TS.log
printf "%s" "$LINES" > "$LOG"
ln -sf "$LOG" "$OUT/latest.log"
if [ "$JSON" = "1" ]; then
  printf '{"ts":"%s","pass":%d,"warn":%d,"fail":%d,"duration":%d,"log":"%s"}\n' "$(date -Iseconds)" "$P" "$WA" "$F" "$dur" "$LOG" > "$OUT/latest.json"
  cat "$OUT/latest.json"
fi
if [ "$F" -eq 0 ]; then exit 0; else exit 1; fi
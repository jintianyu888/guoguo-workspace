#!/usr/bin/env bash
# 2026-11-03 22:48 主公令：插件补齐（v2：修 v1 的 PATH 问题，systemd 单元里找不到 openclaw）
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/plugin-update-20261103.log
OC=/home/j/.npm-global/bin/openclaw
export PATH="/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"
exec >>"$LOG" 2>&1
log(){ echo "[$(date '+%F %T')] $*"; }

log "=== 插件补齐 v2 开始（核心 2026.10.10） ==="
log "OC=$OC 可用=$(command -v openclaw || echo NO) 版本=$($OC --version 2>&1 | head -1)"
PLUGINS="duckduckgo memory-lancedb tavily tokenjuice volcengine zai openshell diffs"

touch "$W/state/work/.watchdog-pause"
log "watchdog 已暂停"

systemctl --user stop openclaw-gateway
sleep 5
if systemctl --user is-active --quiet openclaw-gateway; then
  log "STOP 失败，放弃"
  rm -f "$W/state/work/.watchdog-pause"
  bash "$W/tools/notify.sh" --to-owner "插件补齐 v2 中止：网关停不下来，未做改动。"
  exit 1
fi
log "网关已停止"

FAIL=""; OK=""
for p in $PLUGINS; do
  out=$(timeout 300 "$OC" plugins update "$p" --accept-capabilities --acknowledge-install-policy-warning 2>&1); rc=$?
  echo "----- $p rc=$rc -----"; echo "$out"
  if [ $rc -eq 0 ] && ! echo "$out" | grep -qiE "Cannot admit|No local mutation|rror:"; then
    OK="$OK $p"
  else
    FAIL="$FAIL $p(rc=$rc)"
  fi
done
log "更新完成 OK=[$OK] FAIL=[$FAIL]"

rm -f "$W/state/work/.watchdog-pause"
log "提交重启程序"
bash "$W/tools/restart-gateway.sh" --reason "插件补齐 v2 后重启（主公 11-03 22:26 令）"

H=000
for i in $(seq 1 42); do
  sleep 10
  H=$(curl -s -o /dev/null -w '%{http_code}' -m 4 http://127.0.0.1:18789/health 2>/dev/null || echo 000)
  [ "$H" = "200" ] && break
done
sleep 8

V=$($OC --version 2>&1 | head -1)
LIST=$($OC plugins list 2>/dev/null)
CNT=$(printf '%s\n' "$LIST" | grep -c "2026\.10\.10")
STILL=$(printf '%s\n' "$LIST" | grep -E "openshell|duckduckgo|memory-lancedb|tavily|tokenjuice|volcengine|zai|diffs" | grep -c "2026\.10\.9")
RESULT=$(cat "$W/state/work/safe-restart-result.json" 2>/dev/null)
log "健康=$H 版本=$V 2026.10.10计数=$CNT 仍为10.9=$STILL"

MSG="插件补齐 v2 完成
· 核心：$V
· 网关健康：HTTP $H
· 插件版本：2026.10.10=$CNT，仍停留 2026.10.9=$STILL
· 更新成功：${OK:-无}
· 更新失败：${FAIL:-无}
· 重启：$RESULT
· 日志：state/work/plugin-update-20261103.log"
bash "$W/tools/notify.sh" --to-owner "$MSG" || true
log "=== 结束 ==="

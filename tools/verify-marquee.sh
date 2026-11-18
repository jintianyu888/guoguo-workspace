#!/usr/bin/env bash
# 等备份结束 -> 验跑马灯恢复 -> 落结果（一次性，不写告警）
LOG=/home/j/.openclaw/workspace/state/panelshots/verify-marquee.log
: > "$LOG"
for i in $(seq 1 240); do
  pct=$(curl -s http://127.0.0.1:8899/api/ticker | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('backupPct') if d.get('backupPct') is not None else 'none')" 2>/dev/null)
  jobs=$(curl -s http://127.0.0.1:8899/api/ticker | python3 -c "import json,sys;d=json.load(sys.stdin);print(','.join(d.get('runningJobs') or []))" 2>/dev/null)
  echo "$(date '+%F %T') pct=$pct jobs=$jobs" >> "$LOG"
  case "$jobs" in *备份*) sleep 60; continue;; esac
  echo "$(date '+%F %T') == 备份已结束，开始验证 ==" >> "$LOG"
  cd /home/j/openclaw-workspaces/work/果果助手 && node tools/panel-assert.mjs 2>&1 | grep -E "INFO|状态行颜色|FAIL|结论" >> "$LOG"
  python3 - <<'PY' >> "$LOG" 2>&1
import json,urllib.request
d=json.load(urllib.request.urlopen('http://127.0.0.1:8899/api/ticker'))
print('ticker nextJob=', d.get('nextJob'), 'running=', d.get('runningJobs'))
PY
  echo "$(date '+%F %T') == 验证结束 ==" >> "$LOG"
  bash /home/j/.openclaw/workspace/tools/agent-msg.sh send main "跑马灯恢复验证结果见 state/panelshots/verify-marquee.log（$(grep -c FAIL "$LOG") 条 FAIL）" >/dev/null 2>&1 || true
  exit 0
done
echo "$(date '+%F %T') 超时未等到备份结束" >> "$LOG"

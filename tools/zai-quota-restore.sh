#!/bin/bash
# zai-quota-restore.sh —— zai 周额度恢复后把 11-25 临时改道的四个任务还原（2026-11-25 立）
set -uo pipefail
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
LOG=$W/state/work/zai-restore.log
say(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }
# 先探活：额度真回来了才还原，否则顺延一天
probe=$(timeout 90 openclaw run --model zai/glm-5.3 --no-tools "回复 OK" 2>&1 | tail -3)
if ! echo "$probe" | grep -qi "ok"; then
  say "zai 探活未通过，顺延：$(echo "$probe"|tr '\n' ' '|cut -c1-160)"
  echo "$probe" | grep -qi "上限\|quota\|limit" && { say "仍限额，明天再试"; exit 0; }
  exit 1
fi
openclaw cron edit ed4c9481-a255-495d-b856-77620658bd5e --model zai/glm-5.3 --fallbacks zai/glm-5.3 >/dev/null 2>&1
openclaw cron edit 330261ca-5dcf-42fc-b2a1-c625a5cf4f69 --model zai/glm-5.3 --fallbacks zai/glm-5.3 >/dev/null 2>&1
openclaw cron edit 1d8033de-5b53-4c74-86af-272721df006e --model zai/glm-5.3-flash >/dev/null 2>&1
openclaw cron edit 37ca4c60-c0bb-41da-8149-ce8d691b81e3 --model zai/glm-5.3 --fallbacks deepseek/deepseek-flash >/dev/null 2>&1
chk=$(openclaw cron list --json 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin);j=d if isinstance(d,list) else d.get('jobs',[])
print(sum(1 for y in j if y.get('id','')[:8] in ('ed4c9481','37ca4c60','1d8033de','330261ca') and str((y.get('payload') or {}).get('model','')).startswith('zai/')))
")
say "还原完成 zai 任务数=$chk/4"
[ "$chk" = "4" ] && bash "$W/tools/notify.sh" "【模型还原】zai 额度已恢复，4 个评审/双审任务已还原到 glm-5.3" >/dev/null 2>&1

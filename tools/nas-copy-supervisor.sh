#!/bin/bash
# nas-copy-supervisor.sh —— 顺序执行：H盘孤本归档 → 老NAS归档迁移，完成后飞书通知
LOG=/home/j/.openclaw/workspace/state/nas-copy-supervisor.log
log(){ printf "%s %s\n" "$(date "+%F %T")" "$*" | tee -a "$LOG"; }
log "SUPERVISOR 启动"
bash /home/j/.openclaw/workspace/tools/nas-archive-legacy.sh >> /home/j/.openclaw/workspace/state/nas-archive-legacy.log 2>&1
A=$(cat /home/j/.openclaw/workspace/state/nas-archive-legacy.result 2>/dev/null || echo NONE)
log "归档阶段结束 result=$A"
bash /home/j/.openclaw/workspace/tools/migrate-old-nas.sh >> /home/j/.openclaw/workspace/state/migrate-old-nas.log 2>&1
B=$(cat /home/j/.openclaw/workspace/state/migrate-old-nas.result 2>/dev/null || echo NONE)
log "迁移阶段结束 result=$B"
bash /home/j/.openclaw/workspace/tools/notify.sh "NAS搬迁完成：H盘归档=$A，老NAS迁移=$B" >/dev/null 2>&1
log "SUPERVISOR 结束"

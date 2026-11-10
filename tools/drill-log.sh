#!/bin/bash
# 恢复演练台账: tools/drill-log.sh "结果描述"
LED=/home/j/.openclaw/workspace/state/restore-drills.md
[ -f "$LED" ] || echo "# 恢复演练台账" > "$LED"
echo "- $(date '+%F %H:%M') $*" >> "$LED"
echo "logged"

#!/bin/bash
OUT=/home/j/.openclaw/workspace/state/work/956-verify2.txt
N=$(journalctl --user -u openclaw-gateway --since "2026-11-10 22:15:00" --no-pager 2>/dev/null | grep -c "99991672")
{ echo "check_at=$(date '+%F %T')"; echo "err_since_2215=$N"; if [ "$N" -eq 0 ]; then echo "VERDICT=FIXED"; else echo "VERDICT=STILL"; fi; } > "$OUT"
bash /home/j/.openclaw/workspace/tools/notify.sh "飞书权限复核（22:15 后）：99991672 出现 ${N} 次" || true

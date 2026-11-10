#!/bin/bash
OUT=/home/j/.openclaw/workspace/state/work/965-verify.txt
N=$(journalctl --user -u openclaw-gateway --since "2026-11-10 21:48:30" --no-pager 2>/dev/null | grep -c "pairing changed")
{ echo "check_at=$(date '+%F %T')"; echo "pairing_err_since_2148=$N"; if [ "$N" -eq 0 ]; then echo "VERDICT=FIXED"; else echo "VERDICT=STILL"; fi; } > "$OUT"
bash /home/j/.openclaw/workspace/tools/notify.sh "#965 复核：21:48 杀掉 B 机陈旧 node 进程后，pairing changed 报错 ${N} 次（此前约 1 次/分钟）" || true

#!/bin/bash
SINCE="2026-11-10 21:45:00"
OUT=/home/j/.openclaw/workspace/state/work/956-verify.txt
N=$(journalctl --user -u openclaw-gateway --since "$SINCE" --no-pager 2>/dev/null | grep -c "99991672")
TOT=$(journalctl --user -u openclaw-gateway --since "$SINCE" --no-pager 2>/dev/null | grep -c "feishu\[print\]")
{
  echo "check_at=$(date '+%F %T')"
  echo "since=$SINCE"
  echo "err_99991672=$N"
  echo "print_lines=$TOT"
  if [ "$N" -eq 0 ]; then echo "VERDICT=FIXED"; else echo "VERDICT=STILL_FAILING"; fi
} > "$OUT"
if [ "$N" -eq 0 ]; then
  bash /home/j/.openclaw/workspace/tools/notify.sh "#956 验证通过：飞书 print 应用通讯录权限已生效，21:45 后 99991672 出现 $N 次" || true
else
  bash /home/j/.openclaw/workspace/tools/notify.sh "#956 仍未通过：21:45 后 99991672 出现 $N 次" || true
fi

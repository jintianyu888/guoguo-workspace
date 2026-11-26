#!/bin/bash
# r43-downgrade-stamp.sh —— 检查回滚/降级路径是否先改 config 版本戳
set -uo pipefail
W=/home/j/.openclaw/workspace
ok=1
for f in "$W/tools/upgrade-openclaw.sh" "$W/tools/upgrade-panel.sh"; do
  if ! grep -q "stamp-config-version.py" "$f"; then
    echo "BAD $(basename "$f") 回滚路径缺少 stamp-config-version.py（旧版会被降级保护挡住）"
    ok=0
  fi
done
if [ ! -x "$W/tools/stamp-config-version.py" ]; then
  echo "BAD stamp-config-version.py 缺失或不可执行"; ok=0
fi
[ "$ok" = 1 ] && echo "GREEN 回滚路径已含版本戳改写（R43）"
exit $((1-ok))

#!/bin/bash
# R45: 备份策略引擎必须在跑，计划新鲜，自动删除有授权凭据
set -uo pipefail
cd /home/j/.openclaw/workspace || exit 1
fail=0
systemctl --user is-active --quiet oc-backup-policy.timer || { echo "FAIL timer 未运行"; fail=1; }
last=$(ls -1t state/backup/plan-*.json 2>/dev/null | head -1)
if [ -z "$last" ]; then echo "FAIL 无计划文件"; fail=1; else
  age=$(( ( $(date +%s) - $(stat -c %Y "$last") ) / 3600 ))
  [ "$age" -gt 26 ] && { echo "FAIL 计划过期 ${age}h"; fail=1; }
fi
if [ -f state/work/backup-policy-allow-delete ]; then
  grep -q approved_by state/work/backup-policy-allow-delete || { echo "FAIL 删除授权缺凭据"; fail=1; }
fi
[ "$fail" = 0 ] && { echo "GREEN 策略引擎正常"; exit 0; }
echo "RED 见上"; exit 1

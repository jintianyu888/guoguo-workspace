#!/usr/bin/env bash
# footer.sh v2 — 页脚取真实配置模型，杜绝管家自报模型名
# 用法: footer.sh <管家id>  或  footer.sh <provider/model>
set -uo pipefail
X="${1:-main}"
case "$X" in
  */*) M="$X" ;;
  *) M=$(/usr/bin/python3 - "$X" <<'PY'
import json,sys
aid=sys.argv[1]
d=json.load(open('/home/j/.openclaw/openclaw.json'))
a=d.get('agents',{})
e=(a.get('entries') or {}).get(aid) or {}
m=e.get('model') or a.get('defaults',{}).get('model') or {}
if isinstance(m,str): print(m)
else: print(m.get('primary') or '未采集')
PY
) ;;
esac
exec /usr/bin/python3 /home/j/.openclaw/workspace/tools/model-footer.py "$M"

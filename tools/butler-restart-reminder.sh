#!/bin/bash
# butler-restart-reminder.sh —— 10 个新管家飞书通道上线提醒（2026-10-21）
# 每 30 分钟：若 feishu 账号 < 32 且未提醒超 3 次 → 提醒主公跑 修复系统.bat（顺带重启网关）
set -u
W=/home/j/.openclaw/workspace
ST=$W/state/butler-restart-reminder.json
OUT=$(timeout 90 openclaw channels status --json 2>/dev/null)
N=$(printf '%s' "$OUT" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin); print(len((d.get('channelAccounts') or {}).get('feishu',{})))
except Exception: print(-1)
")
[ "$N" = "-1" ] && exit 0          # 取不到就静默，不误报
[ "$N" -ge 32 ] && {
  python3 - "$ST" <<'PY'
import json,sys,os
p=sys.argv[1]
d=json.load(open(p)) if os.path.exists(p) else {}
if not d.get('done'):
    d['done']=True; json.dump(d,open(p,'w'))
PY
  exit 0                            # 已上线，不再提醒
}
python3 - "$ST" <<'PY'
import json,os,sys,time,subprocess
p=sys.argv[1]; now=int(time.time())
d=json.load(open(p)) if os.path.exists(p) else {}
if d.get('done'): sys.exit(0)
if now - d.get('last',0) < 1800: sys.exit(0)
if d.get('count',0) >= 3: sys.exit(0)
d['last']=now; d['count']=d.get('count',0)+1
json.dump(d,open(p,'w'))
try:
    subprocess.run(['bash','/home/j/.openclaw/workspace/tools/notify.sh',
      '10 个新管家飞书通道还没上线（第 %d 次提醒）。等您活干完，双击桌面「修复系统.bat」即可：它会重启网关，顺带解掉启动迁移未完成 + 升到 2026.10.5，约 2-5 分钟，果果会短暂离线。' % d['count']], timeout=120)
except Exception:
    pass
PY

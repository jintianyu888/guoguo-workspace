#!/usr/bin/env bash
# node-version-check.sh —— 校验所有已配对且在线节点与主控（A 机）OpenClaw 版本一致
# 用法: bash tools/node-version-check.sh             rc=0 全部一致；rc=1 有漂移；rc=2 取不到数据
#       LAG_ONLY=1 bash tools/node-version-check.sh   rc=0 无节点落后主控（允许节点更新）；rc=1 有节点落后；rc=2 取不到数据
set -u
export PATH=/home/j/.npm-global/bin:/usr/bin:/bin:/usr/sbin:/sbin
NEED=$(openclaw --version 2>/dev/null | awk '{print $2}')
if [ -z "${NEED}" ]; then echo "无法读取主控版本"; exit 2; fi
JSON=$(timeout 40 openclaw nodes list --json 2>/dev/null)
if [ -z "$JSON" ]; then echo "无法读取节点列表"; exit 2; fi
printf '%s' "$JSON" | python3 -c '
import json,sys
need=sys.argv[1]
d=json.load(sys.stdin)
bad=[]
print("主控版本:",need)
for n in d.get("paired",[]):
    name=n.get("displayName") or n.get("nodeId","")[:8]
    ver=n.get("version") or "未知"
    def _t(v):
        try: return tuple(int(x) for x in v.split("."))
        except Exception: return None
    lag_only = __import__("os").environ.get("LAG_ONLY")=="1"
    if lag_only and not n.get("connected"):
        print("  SKIP  %-12s %s (离线，版本为上次上报)"%(name,ver)); continue
    if ver=="未知":
        ok = False
    elif lag_only:
        ok = _t(ver) is not None and _t(need) is not None and _t(ver) >= _t(need)
    else:
        ok = (ver==need)
    print(("  OK   " if ok else "  DRIFT")+" %-12s %s"%(name,ver))
    if not ok: bad.append(name+":"+ver)
if bad:
    print("版本漂移:", ", ".join(bad)); sys.exit(1)
print("全部节点与主控版本一致" if not lag_only else "无节点落后主控")
' "$NEED"

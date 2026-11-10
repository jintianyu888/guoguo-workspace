#!/usr/bin/env python3
# 定时任务体检（只读）—— 绝不修改/删除/启停任何任务
import json, subprocess, datetime
from collections import Counter
out = subprocess.run(["openclaw","automations","list","--all","--json"], capture_output=True, text=True, timeout=90).stdout
try:
    d = json.loads(out)
except Exception as e:
    print("❌ 无法解析任务清单:", e); raise SystemExit(1)
js = d.get("jobs", d if isinstance(d, list) else [])
print("🧭 定时任务体检 ·", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"))
print("【只读】只报告，不修改 / 不删除 / 不启停任何任务")
k = lambda j: (j.get("payload") or {}).get("kind","?")
cmd = [j for j in js if k(j)=="command"]; turn = [j for j in js if k(j)=="agentTurn"]
print("· 任务总数：%d（command %d 个=零token · agentTurn %d 个=耗token）" % (len(js), len(cmd), len(turn)))
print("· 会发消息的：%d 个" % len([j for j in js if (j.get("delivery") or {}).get("mode")=="announce"]))
def peak(j):
    s = j.get("schedule") or {}
    if s.get("kind") != "cron": return False
    e = (s.get("expr") or "").split()
    if len(e) < 5: return False
    h, dow = e[1], e[4]
    if dow not in ("*","1-5"): return False
    try:
        if h.startswith("*/"):
            st = int(h[2:]); return any(9 <= v < 12 or 14 <= v < 18 for v in range(0,24,st))
        v = int(h); return (9 <= v < 12) or (14 <= v < 18)
    except Exception: return False
pk = [j for j in js if peak(j)]
print("· 高峰排期：%s" % ("⚠️ "+", ".join(j.get("name","?") for j in pk[:8]) if pk else "✅ 无（都排闲时，符合纪律）"))
fd = [j for j in js if (j.get("lastDeliveryStatus") in ("not-delivered","failed"))]
if fd: print("· ⚠️ 投递失败过：%s" % ", ".join(j.get("name","?") for j in fd[:8]))
fe = [j for j in js if ((j.get("state") or {}).get("consecutiveErrors") or 0) > 0]
if fe: print("· ⚠️ 连续报错：%s" % ", ".join("%s(x%d)" % (j.get("name","?"), (j.get("state") or {}).get("consecutiveErrors")) for j in fe[:8]))
stale = [j for j in js if not j.get("lastRunAtMs")]
if stale: print("· 从建到现在还没跑过：%d 个 → %s" % (len(stale), ", ".join(j.get("name","?") for j in stale[:10])))
dis = [j for j in js if j.get("enabled") is False]
if dis: print("· 已停用：%s" % ", ".join(j.get("name","?") for j in dis[:8]))
nm = Counter(j.get("name","?") for j in js); dup=[x for x,v in nm.items() if v>1]
if dup: print("· ⚠️ 重名：%s" % ", ".join(dup))
print("· 按管家：main %d 个，其余 %d 个管家各 1-2 个" % (Counter(j.get("agentId","?") for j in js).get("main",0), len(set(j.get("agentId","?") for j in js))-1))
print("【说明】只读体检；发现的问题只报告，改任务一律先问老板。")

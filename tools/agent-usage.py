#!/usr/bin/env python3
"""按【每个管家】汇总用量：tokens / 花费 / 缓存命中率。
用法: python3 agent-usage.py [--days N] [--all]
默认只列有用量的管家，按花费降序；--all 列出全部（含 0）。
数据源: openclaw gateway usage-cost --agent <id> --days N --json
"""
import json, subprocess, sys, argparse

AGENTS = ["main","mom-health","tax","fitness","wealth","piano-app","health-wang","health-jin",
          "health-wife","health-self","calendar","doll-brand","piano-room","cooking",
          "sheet-music","print","class-schedule","script-mystery","health-doudou",
          "schedule-doudou","doudou-apply"]
LABEL = {"main":"🎙️麦克","mom-health":"🩺妈妈健康","tax":"🧾税务","fitness":"🏃运动","wealth":"💰理财",
         "piano-app":"🎹钢琴APP","health-wang":"🩺王爸爸","health-jin":"🩺靳爸爸","health-wife":"🩺媳妇",
         "health-self":"🩺本人","calendar":"📅日程","doll-brand":"🧸玩偶品牌","piano-room":"🎹琴房",
         "cooking":"🍳做饭","sheet-music":"🎼乐谱","print":"🖨️打印","class-schedule":"🗓️排课",
         "script-mystery":"🎭剧本杀","health-doudou":"🩺豆豆健康","schedule-doudou":"📅豆豆日程",
         "doudou-apply":"🎓豆豆申请"}

def get(agent, days):
    try:
        out = subprocess.run(["openclaw","gateway","usage-cost","--agent",agent,"--days",str(days),"--json"],
                             capture_output=True, text=True, timeout=90)
        d = json.loads(out.stdout or "{}")
        t = d.get("totals") or {}
        inp = t.get("input",0) or 0; cr = t.get("cacheRead",0) or 0
        tot = t.get("totalTokens",0) or 0; cost = t.get("totalCost",0) or 0
        hit = (cr/(inp+cr)*100) if (inp+cr) else 0
        return tot, cost, hit
    except Exception:
        return 0, 0, 0

p = argparse.ArgumentParser()
p.add_argument("--days", type=int, default=7)
p.add_argument("--all", action="store_true")
a = p.parse_args()

rows = []
for ag in AGENTS:
    tot, cost, hit = get(ag, a.days)
    rows.append((ag, tot, cost, hit))
rows.sort(key=lambda r: r[2], reverse=True)

print(f"【按管家用量 · 近 {a.days} 天】")
shown = 0
for ag, tot, cost, hit in rows:
    if not a.all and cost == 0 and tot == 0: continue
    shown += 1
    print(f"{LABEL.get(ag,ag)} ({ag}) · {tot/1000:.1f}k tokens · ${cost:.2f} · 缓存命中 {hit:.0f}%")
if shown == 0:
    print("（近 " + str(a.days) + " 天无管家用量记录）")

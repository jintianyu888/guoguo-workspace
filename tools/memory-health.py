#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""memory-health.py v1.0 — 记忆健康体检（零 token）
检查：lcm 新鲜度 / MEMORY.md 年龄 / 索引新鲜度 / 嵌入服务 / 金标检索命中 / 事实库更新 / 重复
用法: memory-health.py [--json]
"""
import json, os, sqlite3, subprocess, sys, time, datetime

W = "/home/j/.openclaw/workspace"
LDB = "/home/j/.openclaw/lcm.db"
rows = []

def add(name, ok, detail):
    rows.append({"check": name, "ok": bool(ok), "detail": detail})

# 1 lcm 新鲜度
try:
    c = sqlite3.connect("file:%s?mode=ro" % LDB, uri=True)
    n_msg = c.execute("select count(*) from messages").fetchone()[0]
    n_sum = c.execute("select count(*) from summaries").fetchone()[0]
    last = c.execute("select max(created_at) from messages").fetchone()[0]
    age_h = None
    try:
        ts = str(last)
        if ts.isdigit():
            age_h = round((time.time() - int(ts) / (1000 if int(ts) > 1e11 else 1)) / 3600, 1)
    except Exception:
        pass
    add("lcm_db", n_msg > 1000, "%d 消息 / %d 摘要，最后消息 %s（%s 小时前）" % (n_msg, n_sum, last, age_h))
except Exception as e:
    add("lcm_db", False, "打不开: %s" % str(e)[:60])

# 2 MEMORY.md 年龄与体量
try:
    st = os.stat(os.path.join(W, "MEMORY.md"))
    age_d = round((time.time() - st.st_mtime) / 86400, 1)
    add("MEMORY.md", age_d <= 3, "%.1fKB，%.1f 天未更新" % (st.st_size / 1024, age_d))
except Exception as e:
    add("MEMORY.md", False, str(e)[:60])

# 3 事实库
try:
    f = os.path.join(W, "state/memory/facts-%s.md" % time.strftime("%Y-%m"))
    st = os.stat(f)
    age_h = round((time.time() - st.st_mtime) / 3600, 1)
    add("facts", age_h <= 30, "%.1fKB，%.1f 小时前更新" % (st.st_size / 1024, age_h))
except Exception as e:
    add("facts", False, "本月事实库缺失: %s" % str(e)[:50])

# 4 嵌入服务
try:
    import urllib.request
    body = json.dumps({"model": "nomic-embed-text", "input": "health"}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/embed", data=body, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=20)
    ok = r.status == 200
    add("embed", ok, "ollama nomic-embed-text %s" % ("OK" if ok else "FAIL"))
except Exception as e:
    add("embed", False, "嵌入服务不可用（语义检索会退化）: %s" % str(e)[:50])

# 5 金标检索（命中率）
GOLD = [
    ("剧本杀周边 版权 牌位", "市场评估-剧本杀周边"),
    ("备份 9p ENOMEM 反复故障", "反复故障清单"),
    ("GLM-5.4 顾问槽 切换", "计划-模型用度"),
    ("互审 死锁 顺延 交换", "butler-peer-review-exchange"),
]
hits = 0; miss = []
for q, want in GOLD:
    try:
        p = subprocess.run(["openclaw", "memory", "search", q, "--agent", "main", "--json", "--max-results", "6"],
                           capture_output=True, text=True, timeout=90)
        d = json.loads(p.stdout)
        rs = d.get("results") or d.get("hits") or []
        paths = " ".join(str(x.get("path") or x.get("source") or "") for x in rs)
        if want in paths: hits += 1
        else: miss.append(q)
    except Exception:
        miss.append(q + "(err)")
add("golden_recall", hits >= 3, "%d/%d 命中；漏: %s" % (hits, len(GOLD), "; ".join(miss)[:120]))

# 6 重复行（MEMORY.md 自身）
try:
    lines = [l.strip() for l in open(os.path.join(W, "MEMORY.md"), encoding="utf-8") if len(l.strip()) > 40]
    dup = len(lines) - len(set(lines))
    add("dedupe", dup <= 5, "长行重复 %d 条" % dup)
except Exception as e:
    add("dedupe", False, str(e)[:50])

res = {"ts": time.strftime("%F %T"), "ok": all(r["ok"] for r in rows), "checks": rows}
os.makedirs(os.path.join(W, "state/verify"), exist_ok=True)
json.dump(res, open(os.path.join(W, "state/verify/memory-health.json"), "w"), ensure_ascii=False, indent=1)
if "--json" in sys.argv:
    print(json.dumps(res, ensure_ascii=False, indent=1))
else:
    for r in rows:
        print("%s %-14s %s" % ("✅" if r["ok"] else "❌", r["check"], r["detail"]))
    print("GREEN 记忆健康" if res["ok"] else "RED 有项目不健康")
sys.exit(0 if res["ok"] else 1)

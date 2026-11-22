# -*- coding: utf-8 -*-
"""bench10-qwen4.py —— 用 2026-11-07 那套 10 题口径评 qwen4-max（补千问4 无评测数据的缺口）
复用 bench10-runner.py 的题库与判分函数（切到 def call_or 之前），只换调用端。
输出：workspace-model/state/model-warden/bench10-20261122-qwen4.jsonl + 屏显
"""
import json, os, re, sqlite3, ssl, sys, time, urllib.request, threading

SRC = "/home/j/.openclaw/workspace-model/tools/bench10-runner.py"
src = open(SRC, encoding="utf-8").read()
prefix = src[: src.index("def call_or(")]
ns = {}
exec(compile(prefix, SRC, "exec"), ns)
Q, check = ns["Q"], ns["check"]
print("题目数", len(Q), flush=True)

DB = "/home/j/.openclaw/state/openclaw.sqlite"
def secret(name):
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    r = con.execute("select value from secret_store_entries where name=? and deleted_at_ms is null order by updated_at_ms desc limit 1", (name,)).fetchone()
    return r[0] if r else None

CFG = json.load(open("/home/j/.openclaw/workspace/state/advice/advisors.json", encoding="utf-8"))["advisors"]["qwen"]
KEY = secret(CFG["secret"])
assert KEY, "no key"
URL = CFG["url"]; MODEL = CFG["model"]
ctx = ssl.create_default_context()

def ask(prompt, max_tokens=6000):
    body = {"model": MODEL, "max_tokens": max_tokens, "temperature": 0,
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300, context=ctx) as r:
        d = json.loads(r.read().decode())
    txt = "".join(b.get("text", "") for b in (d.get("content") or []) if isinstance(b, dict))
    return txt.strip(), time.time() - t0

ROUND = os.environ.get("ROUND", "1")
OUT = "/home/j/.openclaw/workspace-model/state/model-warden/bench10-20261122-qwen4.jsonl"
res = []
lock = threading.Lock()

def work(item):
    qid, title, prompt, groups = item
    for attempt in range(3):
        try:
            txt, dt = ask(prompt); break
        except Exception as e:
            txt, dt = "", 0; err = str(e)[:120]
            time.sleep(3)
    sc, got = check(txt, groups, qid) if txt else (0.0, [])
    rec = {"model": MODEL, "round": ROUND, "qid": qid, "title": title, "score": sc,
           "miss": [n for n, ok in got if not ok], "secs": round(dt, 1),
           "len": len(txt), "answer": txt[:3000], "err": "" if txt else err}
    with lock:
        res.append(rec)
        open(OUT, "a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("%-22s %.2f  %5.1fs  %d字  漏:%s" % (title, sc, dt, len(txt), ",".join(rec["miss"]) or "-"), flush=True)

if ROUND == "1":
    open(OUT, "w").close()
ths = [threading.Thread(target=work, args=(q,)) for q in Q]
for t in ths: t.start(); time.sleep(1.5)
for t in ths: t.join()
avg = sum(r["score"] for r in res) / len(res) * 10
print("\n== %s 十题均分 %.2f / 10（%d 题）" % (MODEL, avg, len(res)), flush=True)
allrows=[json.loads(l) for l in open(OUT,encoding="utf-8") if l.strip()]
per_round={}
for r_ in allrows:
    per_round.setdefault(r_.get("round","1"),[]).append(r_["score"])
avgs={k:round(sum(v)/len(v)*10,2) for k,v in per_round.items()}
json.dump({"model": MODEL, "round_avgs": avgs, "avg_3round": round(sum(avgs.values())/len(avgs),2),
           "n": len(allrows), "ts": time.strftime("%F %T")},
          open("/home/j/.openclaw/workspace-model/state/model-warden/bench10-20261122-qwen4-summary.json", "w"), ensure_ascii=False, indent=1)

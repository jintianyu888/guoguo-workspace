#!/usr/bin/env python3
# needle-test.py —— 自有"针在草堆"长上下文检索测试（2026-10-21）
# 自建实验，不依赖第三方结论：随机填充文档 + 唯一口令 + 指定深度 + 指定长度
import argparse, csv, json, os, random, subprocess, sys, time

NEEDLE_KEY = "紫铜鲸鱼-7391"
NEEDLE = "【重要记录】本次文档的验证口令为：紫铜鲸鱼-7391。该口令全文只出现一次，请记住。"
QUESTION = "上面这份长文档中，唯一一次出现的验证口令是什么？只输出口令本身（形如 XXXX-0000），如果确实没有就输出：未找到"

WORDS = ["项目","节点","记录","批次","样本","配置","日志","接口","指标","模块",
         "校验","版本","缓存","队列","分区","索引","会话","任务","产物","阈值"]

def make_filler(seed, chars):
    rnd = random.Random(seed)
    out, i = [], 0
    while i < chars:
        s = "第%d条：%s" % (rnd.randint(3, 12),
              "，".join(rnd.choice(WORDS) + str(rnd.randint(100, 9999)) for _ in range(rnd.randint(2, 5))))
        out.append(s); i += len(s) + 1
    return "\n".join(out)[:chars].replace(NEEDLE_KEY, "紫铜鲸鱼-0000")

def build(chars, depth, seed):
    f = make_filler(seed, chars)
    pos = max(0, min(len(f) - 1, int(len(f) * depth)))
    nl = f.rfind("\n", 0, pos)
    if nl > 0: pos = nl
    return f[:pos] + "\n" + NEEDLE + "\n" + f[pos:] + "\n\n" + QUESTION

def call(model, prompt, timeout=600):
    t0 = time.time()
    try:
        p = subprocess.run(["openclaw","infer","model","run","--agent","main","--gateway",
                            "--model",model,"--json","--prompt",prompt],
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT", time.time()-t0, {}, 124
    dt = time.time() - t0
    j = None
    try:
        j = json.loads(p.stdout.strip())
    except Exception:
        s = (p.stdout or "").strip()
        i = s.find("{")
        if i >= 0:
            try: j = json.loads(s[i:])
            except Exception: j = None
    txt, usage, ok = "", {}, False
    if isinstance(j, dict):
        ok = bool(j.get("ok"))
        outs = j.get("outputs") or []
        txt = ((outs[0].get("text") if outs else "") or "").strip()
        usage = j.get("usage") or {}
    if not txt:
        txt = "ERR:" + ((p.stderr or p.stdout or "")[-160:].replace("\n"," "))
    return ok, txt, dt, usage, p.returncode

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="deepseek/deepseek-flash,deepseek/deepseek-v4-pro")
    ap.add_argument("--chars", default="12000,60000")
    ap.add_argument("--depths", default="0.05,0.5,0.95")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--tag", default=time.strftime("%Y%m%d-%H%M"))
    ap.add_argument("--call-timeout", type=int, default=180)
    a = ap.parse_args()
    rows = []
    od = "/home/j/.openclaw/workspace/state/needle"
    os.makedirs(od, exist_ok=True)
    for m in [x.strip() for x in a.models.split(",") if x.strip()]:
        for chars in [int(x) for x in a.chars.split(",")]:
            for d in [float(x) for x in a.depths.split(",")]:
                for rep in range(a.repeat):
                    pr = build(chars, d, seed=(chars*97 + int(d*100) + rep))
                    ok, txt, dt, usage, rc = call(m, pr, timeout=a.call_timeout)
                    hit = NEEDLE_KEY in txt.replace(" ", "")
                    rows.append({"model": m, "chars": chars, "depth": d, "rep": rep,
                                 "ok": ok, "rc": rc, "hit": hit, "sec": round(dt,1),
                                 "in_tok": usage.get("inputTokens") or usage.get("prompt_tokens") or "",
                                 "out_tok": usage.get("outputTokens") or usage.get("completion_tokens") or "",
                                 "answer": txt.replace("\n"," ")[:100]})
                    line = "%-26s %6d d=%.2f r%d ok=%s hit=%s %5.1fs | %s" % (m, chars, d, rep, ok, hit, dt, rows[-1]["answer"][:50])
                    print(line, flush=True)
                    open("/home/j/.openclaw/workspace/state/needle/run.log","a").write(line+"\n")
    path = os.path.join(od, a.tag + ".csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("CSV:", path)
    agg = {}
    for r in rows:
        k = (r["model"], r["chars"])
        v = agg.setdefault(k, [0,0]); v[1] += 1; v[0] += 1 if r["hit"] else 0
    for (m,c),(h,n) in sorted(agg.items()):
        print("SUMMARY %-26s %6d chars  hit %d/%d" % (m,c,h,n))

if __name__ == "__main__":
    main()

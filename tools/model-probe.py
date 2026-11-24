#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""model-probe.py v1.0 — 真实探活：配置写什么不重要，看请求实际落到哪个模型
用法: model-probe.py [--json]
判定：返回的 model 与 policy 期望一致才算通；任何 chain 成员不可用也报红。
"""
import json, os, sqlite3, sys, time, urllib.request

W = "/home/j/.openclaw/workspace"
P = json.load(open(os.path.join(W, "state/model/policy.json"), encoding="utf-8"))
DB = "/home/j/.openclaw/state/openclaw.sqlite"

def secret_exact(sid):
    """按 provider 配置里的 secret id 精确取，不靠名字模糊匹配（旧键会误命中）"""
    try:
        c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        row = c.execute("select value from secret_store_entries where name=?", (sid,)).fetchone()
        return row[0] if row else None
    except Exception:
        return None

def provider_key(pid, fallback_hint=None):
    try:
        cfg = json.load(open("/home/j/.openclaw/openclaw.json", encoding="utf-8"))
        prov = (cfg.get("providers") or {}).get(pid) or {}
        k = prov.get("apiKey") or {}
        sid = k.get("id") if isinstance(k, dict) else None
        if sid:
            v = secret_exact(sid)
            if v: return v, sid
    except Exception:
        pass
    if fallback_hint:
        return secret_exact(fallback_hint), fallback_hint
    return None, None

def call(url, key, model, extra=None, retries=2):
    last=None
    for i in range(retries+1):
        r=_call_once(url,key,model,extra)
        if r.get("ok"): r["attempts"]=i+1; return r
        last=r
        if i<retries: time.sleep(6)
    last["attempts"]=retries+1
    last["status"]="fail" if "429" not in str(last.get("err")) else "degraded_429"
    return last

def _call_once(url, key, model, extra=None):
    body = {"model": model, "max_tokens": 8, "messages": [{"role": "user", "content": "ping"}]}
    if extra: body.update(extra)
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + (key or ""), "Content-Type": "application/json"})
    t = time.time()
    try:
        r = urllib.request.urlopen(req, timeout=45)
        raw = r.read().decode("utf-8", "ignore")
        d = json.loads(raw)
        return {"ok": True, "http": r.status, "model_returned": d.get("model"),
                "body": raw[:300], "ms": int((time.time() - t) * 1000)}
    except Exception as e:
        return {"ok": False, "err": str(e)[:160], "ms": int((time.time() - t) * 1000)}

targets = []
ds_key, ds_sid = provider_key("deepseek", "DEEPSEEK_API_KEY")
targets.append(("primary", P["primary"], "https://api.deepseek.com/chat/completions", ds_key, ds_sid))
for f in P["fallbacks"]:
    if f.startswith("zai/"):
        zk, zsid = provider_key("zai", "ZAI_API_KEY_NEW")
        targets.append(("fallback", f, "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions", zk, zsid))
    elif f.startswith("ollama/"):
        targets.append(("fallback", f, "http://127.0.0.1:11434/v1/chat/completions", "ollama", "local"))

out = []
for kind, mid, url, key, sid in targets:
    model = mid.split("/", 1)[1]
    r = call(url, key, model)
    r.update({"kind": kind, "policy_model": mid, "secret_id": sid, "base_url": url})
    out.append(r)

bad = [x for x in out if not x.get("ok") or (x.get("model_returned") and x["policy_model"].split("/")[-1] not in str(x["model_returned"]) and not x["policy_model"].startswith("ollama"))]
res = {"ts": time.strftime("%F %T"), "ok": not bad, "results": out}
open(os.path.join(W, "state/model/probe-latest.json"), "w").write(json.dumps(res, ensure_ascii=False, indent=1))
if "--json" in sys.argv:
    print(json.dumps(res, ensure_ascii=False, indent=1))
else:
    for x in out:
        print("%-8s %-28s %s" % (x["kind"], x["policy_model"],
              ("OK rc=%s 实际=%s %sms" % (x.get("http"), x.get("model_returned"), x.get("ms"))) if x.get("ok")
              else ("FAIL %s" % x.get("err"))))
    print("GREEN 真实链路与策略一致" if not bad else "RED 有探活失败/不一致")
sys.exit(0 if not bad else 1)

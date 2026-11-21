#!/usr/bin/env python3
"""model-refresh-check.py v1.0 (2026-11-21 主公令)
检查各厂"顶级模型"是否有更新版本上线，配置里的顾问模型是否落后。
零 token（只做列举/探测，不跑生成）。出口：0=无更新 1=发现更新 2=探测失败
用法：python3 tools/model-refresh-check.py [--json] [--notify]
"""
import json, re, sqlite3, ssl, sys, urllib.request, datetime, os

WS = "/home/j/.openclaw/workspace"
DB = "/home/j/.openclaw/state/openclaw.sqlite"
CFG = "/home/j/.openclaw/openclaw.json"
OUT = os.path.join(WS, "state/model-econ/refresh.json")
CTX = ssl.create_default_context()

def key(name):
    try:
        con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        r = con.execute("select value from secret_store_entries where name=? and deleted_at_ms is null order by updated_at_ms desc limit 1", (name,)).fetchone()
        return r[0] if r else None
    except Exception:
        return None

def req(url, hdr=None, body=None, timeout=25):
    h = hdr or {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h = dict(h, **{"content-type": "application/json"})
    r = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(r, timeout=timeout, context=CTX) as resp:
            return resp.status, resp.read(20000).decode("utf8", "ignore")
    except Exception as e:
        t = ""
        if hasattr(e, "read"):
            try: t = e.read(400).decode("utf8", "ignore")
            except Exception: pass
        return getattr(e, "code", 0), (str(e)[:80] + " | " + t)

def ver(s):
    m = re.search(r"(\d+)(?:\.(\d+))?", s)
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)

def flagship(ids, exclude=("-flash", "-air", "-turbo", "-lite", "-small")):
    cand = [i for i in ids if not any(x in i for x in exclude)]
    return sorted(cand, key=ver)[-1] if cand else None

res = {"checked_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "providers": {}}

# 智谱 zai：官方 /models 可列举
zk = key("ZAI_API_KEY_NEW") or key("ZAI_API_KEY")
s, t = req("https://open.bigmodel.cn/api/coding/paas/v4/models", {"Authorization": "Bearer " + (zk or "")})
if s == 200:
    ids = [m["id"] for m in json.loads(t).get("data", [])]
    res["providers"]["zai"] = {"method": "list", "count": len(ids), "flagship": flagship(ids), "full": sorted(ids, key=ver)[-6:]}
else:
    res["providers"]["zai"] = {"method": "list", "error": s}

# DeepSeek：官方 /models
dk = key("DEEPSEEK_APP_KEY") or key("DEEPSEEK_API_KEY")
s, t = req("https://api.deepseek.com/models", {"Authorization": "Bearer " + (dk or "")})
if s == 200:
    ids = [m["id"] for m in json.loads(t).get("data", [])]
    res["providers"]["deepseek"] = {"method": "list", "count": len(ids), "flagship": flagship(ids), "full": sorted(ids, key=ver)[-6:]}
else:
    res["providers"]["deepseek"] = {"method": "list", "error": s}

# 千问 token-plan：无 /models 接口，探测候选旗舰名
qk = key("QIANWEN_PLAN_KEY")
probes = ["qwen6-max", "qwen5-max", "qwen4.5-max", "qwen4.1-max", "qwen4.2-max", "qwen4-max", "qwen3.8-max"]
alive = []
for m in probes:
    s, _ = req("https://token-plan.maas.qianwenaiapi.com/apps/anthropic/v1/messages",
               {"x-api-key": qk or "", "anthropic-version": "2023-06-01"},
               {"model": m, "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]})
    if s == 200:
        alive.append(m)
res["providers"]["qianwen"] = {"method": "probe", "alive": alive, "flagship": flagship(alive) if alive else None}

# OpenRouter：文本侧可用性 + 余额
ok = key("OPENROUTER_API_KEY")
s, t = req("https://openrouter.ai/api/v1/key", {"Authorization": "Bearer " + (ok or "")})
if s == 200:
    d = json.loads(t).get("data", {})
    res["providers"]["openrouter"] = {"method": "key", "text_ok": True,
                                      "limit": d.get("limit"), "remaining": d.get("limit_remaining")}
else:
    res["providers"]["openrouter"] = {"method": "key", "error": s}

# 对照配置
cfg = json.load(open(CFG))
buf = json.dumps(cfg, ensure_ascii=False)
stale = []
for prov, info in res["providers"].items():
    fl = info.get("flagship")
    if not fl:
        continue
    if '"%s"' % fl not in buf:
        stale.append("%s 最新旗舰 %s 不在配置里" % (prov, fl))
    elif fl not in ("qwen4-max", "glm-5.3", "deepseek-flash", "deepseek-v4-pro"):
        pass
res["stale"] = stale
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)

if "--json" in sys.argv:
    print(json.dumps(res, ensure_ascii=False, indent=1))
else:
    for p, i in res["providers"].items():
        print("%-10s 旗舰=%-16s %s" % (p, i.get("flagship") or "-", i.get("full") or i.get("alive") or i.get("remaining") or ""))
    print("落盘：" + OUT)
    if stale:
        print("⚠️ " + "；".join(stale))

if "--notify" in sys.argv and stale:
    os.system("cd %s && bash tools/notify.sh --p0 '模型更新提醒' '%s' >/dev/null 2>&1" % (WS, "；".join(stale).replace("'", "")))
sys.exit(1 if stale else 0)

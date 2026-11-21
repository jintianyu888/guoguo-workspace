#!/usr/bin/env python3
"""img-gen.py v1.0 (2026-11-21) —— 智谱图像生成（国内直连，现成 key，零代理）
用法：python3 tools/img-gen.py "提示词" [--size 1024x1024] [--model cogview-4|cogview-3-flash|glm-image] [--out 路径]
输出：本地文件路径（默认 workspace/data/images/gen-<时间>.png）
"""
import argparse, datetime, json, os, sqlite3, ssl, sys, urllib.request

DB = "/home/j/.openclaw/state/openclaw.sqlite"
OUTDIR = "/home/j/.openclaw/workspace/data/images"
API = "https://open.bigmodel.cn/api/paas/v4/images/generations"

def key():
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    r = con.execute("select value from secret_store_entries where name='ZHIPU_API_KEY' and deleted_at_ms is null order by updated_at_ms desc limit 1").fetchone()
    return r[0] if r else None

ap = argparse.ArgumentParser()
ap.add_argument("prompt")
ap.add_argument("--size", default="1024x1024")
ap.add_argument("--model", default="cogview-4")
ap.add_argument("--out", default="")
a = ap.parse_args()
k = key()
if not k:
    print("FAIL 找不到 ZHIPU_API_KEY"); sys.exit(1)
ctx = ssl.create_default_context()
body = {"model": a.model, "prompt": a.prompt, "size": a.size}
req = urllib.request.Request(API, data=json.dumps(body).encode(),
                            headers={"Authorization": "Bearer " + k, "content-type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=180, context=ctx) as r:
        d = json.loads(r.read())
except Exception as e:
    t = ""
    if hasattr(e, "read"):
        try: t = e.read(300).decode("utf8", "ignore")
        except Exception: pass
    print("FAIL", getattr(e, "code", 0), str(e)[:120], t[:200]); sys.exit(2)
url = d["data"][0]["url"]
out = a.out or os.path.join(OUTDIR, "gen-%s.png" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
os.makedirs(os.path.dirname(out), exist_ok=True)
with urllib.request.urlopen(url, timeout=120, context=ctx) as r:
    open(out, "wb").write(r.read())
print(out)
print("model=%s size=%s bytes=%d" % (a.model, a.size, os.path.getsize(out)))
print("注意：智谱输出带右下角「AI生成」水印（国内合规要求）")

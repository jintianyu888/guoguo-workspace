#!/usr/bin/env python3
# model-radar.py v1.1 (2026-11-17) —— 零 token 模型雷达：发现新模型/价格变动，对比在役清单
import json, os, re, sys, time, urllib.request, datetime

ROOT = "/home/j/.openclaw/workspace"
OUTDIR = os.path.join(ROOT, "state/model-radar")
CFG = "/home/j/.openclaw/openclaw.json"
PROXY = os.environ.get("HTTPS_PROXY") or "http://172.18.240.1:7891"
WATCH = ("deepseek", "qwen", "z-ai", "moonshotai", "minimax", "openai", "anthropic", "google", "x-ai", "meta-llama", "mistralai")

def fetch(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": "model-radar/1.1"})
    for opener in (None, PROXY):
        try:
            if opener:
                h = urllib.request.ProxyHandler({"https": opener, "http": opener})
                o = urllib.request.build_opener(h)
            else:
                o = urllib.request.build_opener()
            with o.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            err = e
    raise err

def configured_models():
    d = json.load(open(CFG, encoding="utf-8"))
    refs = set()
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("primary", "fallbacks", "model", "utility"):
                    s = json.dumps(v, ensure_ascii=False)
                    for t in re.findall(r"[a-z0-9][a-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:-]{2,}", s):
                        refs.add(t)
                walk(v)
        elif isinstance(o, list):
            for i in o: walk(i)
    walk(d)
    return sorted(x for x in refs if not x.startswith(("openclaw/", "agents/", "api.")))

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    today = datetime.date.today().isoformat()
    path = os.path.join(OUTDIR, f"{today}.md")
    lines = [f"# 模型雷达 {today}", ""]
    try:
        data = fetch("https://openrouter.ai/api/v1/models")["data"]
    except Exception as e:
        lines.append(f"抓取失败：{e}")
        open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print("RADAR_FAIL", e); return 2
    now = time.time()
    fresh = []
    for m in data:
        mid = m.get("id", "")
        vendor = mid.split("/")[0]
        if vendor not in WATCH: continue
        created = m.get("created") or 0
        age = (now - created) / 86400 if created else 999
        if age <= 30:
            pr = m.get("pricing") or {}
            pin, pout = pr.get("prompt"), pr.get("completion")
            fresh.append((age, mid, m.get("name"), pin, pout))
    fresh.sort()
    lines.append(f"近 30 天新上架/新建（{len(fresh)} 个）：")
    for age, mid, name, pin, pout in fresh[:40]:
        lines.append(f"- {mid} | {name} | {age:.1f}天 | in={pin} out={pout}")
    cfg = configured_models()
    lines += ["", f"在役引用（{len(cfg)} 个）："]
    for c in cfg: lines.append(f"- {c}")
    # 在役型号是否已从 OpenRouter 列表消失（仅对 openrouter 可见的厂商做提示）
    ids = {m.get("id") for m in data}
    gone = [c for c in cfg if c.split("/")[0] in WATCH and c not in ids and not c.startswith(("zai/", "kimi-coding/", "qianwen", "ollama/", "deepseek/", "minimax/"))]
    if gone:
        lines += ["", "⚠ 可能已下架（需人工核）："] + [f"- {g}" for g in gone]
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"RADAR_OK fresh={len(fresh)} configured={len(cfg)} file={path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

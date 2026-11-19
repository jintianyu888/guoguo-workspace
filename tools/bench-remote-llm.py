#!/usr/bin/env python3
# B 机（ollama）实测：速度 + 是否上 GPU
import json, sys, time, urllib.request

BASE = "http://127.0.0.1:11434"
PROMPT = "请用中文列出三条家庭备份的最佳实践，每条不超过20字。"

def call(path, payload=None, timeout=600):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def bench(model):
    try:
        t0 = time.time()
        d = call("/api/generate", {"model": model, "prompt": PROMPT, "stream": False,
                                   "options": {"num_predict": 128, "temperature": 0.6}})
        wall = time.time() - t0
        ec = d.get("eval_count", 0)
        ed = d.get("eval_duration", 1) / 1e9
        pc = d.get("prompt_eval_count", 0)
        pd = d.get("prompt_eval_duration", 1) / 1e9
        ps = call("/api/ps", None, 30)
        vram = ""
        for m in ps.get("models", []):
            if m.get("name", "").startswith(model.split(":")[0]):
                total = m.get("size", 1)
                v = m.get("size_vram", 0)
                vram = "VRAM %.1f/%.1fG (%.0f%%)" % (v/1e9, total/1e9, 100.0*v/total)
        print("%-42s 生成 %5.1f tok/s | 预填充 %6.1f tok/s | 首字 %.1fs | 总 %.1fs | %s" % (
            model, ec/ed if ed else 0, pc/pd if pd else 0, wall - ed, wall, vram or "未加载"))
        print("   回复:", (d.get("response") or "").strip().replace("\n", " ")[:90])
    except Exception as e:
        print("%-42s 失败: %s" % (model, str(e)[:80]))

if __name__ == "__main__":
    models = sys.argv[1:] or ["qwen3:14b"]
    for m in models:
        bench(m)

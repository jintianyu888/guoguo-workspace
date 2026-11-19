#!/usr/bin/env python3
"""B 机模型评测套件：速度/显存/中文/视觉。结果落 JSONL + Markdown。"""
import base64, json, os, sys, time, urllib.request

BASE = os.environ.get("OLLAMA_BASE", "http://127.0.0.1:11434")
WS = "/home/j/.openclaw/workspace"
JSONL = os.path.join(WS, "state/work/bench-b-results.jsonl")
MD = os.path.join(WS, "state/work/model-bench-b.md")
PROMPT = "请用中文列出三条家庭数据备份的最佳实践，每条不超过20字，直接给答案。"
IMG = os.path.join(WS, "state/work/bench-img.png")


def post(path, payload, timeout=900):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def get(path, timeout=60):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode())


def vram_of(model):
    try:
        for m in get("/api/ps").get("models", []):
            if m.get("name", "").split(":")[0] == model.split(":")[0]:
                return round(m.get("size_vram", 0) / 1e9, 1), round(m.get("size", 0) / 1e9, 1)
    except Exception:
        pass
    return 0.0, 0.0


def run(model, prompt, images=None, npred=128):
    p = {"model": model, "prompt": prompt, "stream": False,
         "options": {"num_predict": npred, "temperature": 0.5}}
    if images:
        p["images"] = images
    t0 = time.time()
    d = post("/api/generate", p)
    wall = time.time() - t0
    ec, ed = d.get("eval_count", 0), d.get("eval_duration", 1) / 1e9
    pc, pd = d.get("prompt_eval_count", 0), d.get("prompt_eval_duration", 1) / 1e9
    return {"gen_tps": round(ec / ed, 1) if ed else 0,
            "prefill_tps": round(pc / pd, 1) if pd else 0,
            "load_s": round(d.get("load_duration", 0) / 1e9, 1),
            "first_token_s": round(wall - ed, 2),
            "total_s": round(wall, 1), "tokens": ec,
            "text": (d.get("response") or "").strip()}


def bench(model):
    row = {"model": model, "at": time.strftime("%F %T")}
    try:
        tags = {m["name"]: m for m in get("/api/tags").get("models", [])}
        row["size_gb"] = round(tags[model]["size"] / 1e9, 1) if model in tags else None
        cold = run(model, PROMPT)
        warm = run(model, PROMPT)
        row.update({"gen_tps": warm["gen_tps"], "prefill_tps": warm["prefill_tps"],
                    "cold_load_s": cold["load_s"], "warm_first_token_s": warm["first_token_s"],
                    "warm_total_s": warm["total_s"],
                    "reply": warm["text"][:120].replace("\n", " ")})
        v, t = vram_of(model)
        row["vram_gb"], row["total_gb"] = v, t
        row["vram_pct"] = round(100.0 * v / t) if t else None
        if os.path.exists(IMG):
            try:
                b64 = base64.b64encode(open(IMG, "rb").read()).decode()
                vis = run(model, "这张图里有什么？用一句中文回答。", images=[b64], npred=64)
                txt = vis["text"].replace("\n", " ") if vis["text"] else "(空)"
                row["vision"] = "OK: " + txt[:70]
            except Exception as e:
                row["vision"] = "不支持/失败: " + str(e)[:60]
        else:
            row["vision"] = "无测试图"
        row["ok"] = True
    except Exception as e:
        row["ok"] = False
        row["error"] = str(e)[:160]
    with open(JSONL, "a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False))


def render_md():
    if not os.path.exists(JSONL):
        return
    rows = []
    for line in open(JSONL):
        try:
            r = json.loads(line)
        except Exception:
            continue
        rows = [x for x in rows if x.get("model") != r.get("model")]
        rows.append(r)
    header = "| 模型 | 体积 | 生成 tok/s | 预填充 tok/s | 显存 | 热首字 | 视觉 | 备注 |"
    sep = "|---|---|---|---|---|---|---|---|"
    out = ["# B 机本地模型实测台账", "",
           "更新：%s　条件：A机→代理→B机，中文提示，128 token 输出，取热态值" % time.strftime("%F %T"),
           "", header, sep]
    for r in rows:
        note = (r.get("reply") or r.get("error") or "")[:40]
        out.append("| %s | %sG | %s | %s | %s/%sG (%s%%) | %ss | %s | %s |" % (
            r.get("model"), r.get("size_gb") or "?", r.get("gen_tps") or "-",
            r.get("prefill_tps") or "-", r.get("vram_gb") or 0, r.get("total_gb") or 0,
            r.get("vram_pct") or "-", r.get("warm_first_token_s") or "-",
            (r.get("vision") or "-")[:22], note))
    open(MD, "w").write("\n".join(out) + "\n")


if __name__ == "__main__":
    for m in sys.argv[1:]:
        bench(m)
    render_md()

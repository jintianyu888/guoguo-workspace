#!/usr/bin/env python3
"""vision-ab.py v1.0 (2026-11-18) —— 视觉能力同图三厂回归
用同一张图跑多个模型，按关键词命中率打分，结果写进模型账本 evals。
用法: python3 tools/vision-ab.py --image PATH [--models a,b,c] [--json]
"""
import argparse, json, os, subprocess, sys, time

WS = "/home/j/.openclaw/workspace"
DEFAULT_MODELS = ["deepseek/deepseek-flash", "zai/glm-5.4", "zai/glm-5.3-flash"]
GT = ["auto", "qwen4-max", "qwen4-max-preview", "qwen3.8-max", "qwen3.8-flash",
      "qwen3.7-plus", "qwen3.7-max", "qwen3.6-flash"]
PROMPT = "只做一件事：把图中表格里的模型名称逐个列出，用英文逗号分隔，不要解释。"

def run(model, image):
    t0 = time.time()
    try:
        p = subprocess.run(["openclaw", "infer", "model", "run", "--agent", "model",
                            "--gateway", "--model", model, "--prompt", PROMPT,
                            "--file", image],
                           capture_output=True, text=True, timeout=180)
        out = (p.stdout or "").strip()
        err = (p.stderr or "")
        out = "\n".join(l for l in out.splitlines() if "[plugins]" not in l).strip()
        return out, err, int((time.time() - t0) * 1000)
    except subprocess.TimeoutExpired:
        return "", "timeout", 180000

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    rows = []
    for m in models:
        out, err, ms = run(m, a.image)
        low = out.lower().replace(" ", "")
        hit = [g for g in GT if g.lower() in low]
        score = len(hit) / len(GT)
        rows.append({"model": m, "score": round(score, 3), "hits": len(hit), "ms": ms,
                     "head": out[:160], "err": err[-120:] if not out else ""})
        print("%-42s score=%.2f (%d/%d) %6dms  %s" % (m, score, len(hit), len(GT), ms, out[:80].replace("\n", " ")))
    if a.json:
        print(json.dumps(rows, ensure_ascii=False))
    # 写进模型账本 evals
    for r in rows:
        if r["score"] > 0 or r["head"]:
            subprocess.run(["python3", os.path.join(WS, "tools/model-ledger.py"), "eval-add",
                            "--model", r["model"], "--task", "vision-table-read",
                            "--score", str(r["score"]), "--samples", "1",
                            "--latency", str(r["ms"]),
                            "--repro", "python3 tools/vision-ab.py --image " + a.image,
                            "--verdict", "pass" if r["score"] >= 0.75 else ("partial" if r["score"] > 0 else "fail")],
                           timeout=60, capture_output=True)

if __name__ == "__main__":
    main()


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aesthetic.py v1.0 —— 本地审美评分器（零 token）
用途：给生图/3D 渲染/视频抽帧打分排序；记录主公「好看/难看」反馈并据此校准。
用法：
  python3 tools/aesthetic.py score <图或目录>... [--top 5] [--json] [--ref 参考目录]
  python3 tools/aesthetic.py feedback <图> good|bad [--note "说明"]
  python3 tools/aesthetic.py calibrate        # 用已有反馈拟合个人偏好权重
  python3 tools/aesthetic.py stats
口径：base=通用分（LAION 美学 + 客观技术分）；personal=按主公反馈校准后的概率；无校准只看 base。
"""
import os, sys, json, math, hashlib, argparse, time
# 系统 python 没 numpy/PIL：自动切到带 torch 的 venv 重跑（避免每次手工指定解释器）
if not os.environ.get("AES_REEXEC"):
    try:
        import numpy  # noqa: F401
    except Exception:
        venv = "/home/j/.openclaw/venvs/tts312/bin/python"
        if os.path.exists(venv) and sys.executable != venv:
            os.environ["AES_REEXEC"] = "1"
            os.execv(venv, [venv, os.path.abspath(__file__)] + sys.argv[1:])
from pathlib import Path

WS = Path("/home/j/.openclaw/workspace")
STATE = WS / "state/aesthetic"
STATE.mkdir(parents=True, exist_ok=True)
SCORES = STATE / "scores.jsonl"
FEEDBACK = STATE / "feedback.jsonl"
WEIGHTS = STATE / "model.json"
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

def sha12(p):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:12]

# ---------- 客观指标（无模型也能跑） ----------
def objective(p):
    from PIL import Image
    import numpy as np
    im = Image.open(p).convert("RGB")
    w, h = im.size
    a = np.asarray(im, dtype=np.float32) / 255.0
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])
    # 清晰度：拉普拉斯方差（归一化到 0-1，经验上限 0.02）
    g = lum
    lap = (4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:])
    sharp = float(np.var(lap))
    sharp_n = min(1.0, sharp / 0.02)
    # 对比度：亮度标准差
    contrast = float(lum.std())
    # 色彩丰富度 Hasler-Süsstrunk
    rg = a[..., 0] - a[..., 1]; yb = 0.5 * (a[..., 0] + a[..., 1]) - a[..., 2]
    colorful = math.sqrt(float(rg.std()) ** 2 + float(yb.std()) ** 2) + 0.3 * math.sqrt(float(rg.mean()) ** 2 + float(yb.mean()) ** 2)
    color_n = min(1.0, colorful / 0.55)
    # 饱和度
    mx = a.max(axis=2); mn = a.min(axis=2)
    sat = float((mx - mn).mean())
    # 曝光缺陷：过曝/死黑比例
    hi = float((lum > 0.98).mean()); lo = float((lum < 0.02).mean())
    exposure_pen = min(1.0, (hi + lo) * 6)
    # 左右对称度（构图平衡代理）
    f = lum - lum.mean()
    sym = 0.0
    if w > 8:
        left = f[:, : w // 2]; right = f[:, w - w // 2:][:, ::-1]
        n = min(left.shape[1], right.shape[1])
        if n > 4:
            c = float(np.corrcoef(left[:, :n].ravel(), right[:, :n].ravel())[0, 1])
            sym = max(0.0, c)
    # 中心-边缘能量差（主体是否明确）
    hh, ww = lum.shape
    cy0, cy1 = int(hh * 0.2), int(hh * 0.8); cx0, cx1 = int(ww * 0.2), int(ww * 0.8)
    centre = lum[cy0:cy1, cx0:cx1]
    border = np.concatenate([lum[:cy0, :].ravel(), lum[cy1:, :].ravel(), lum[:, :cx0].ravel(), lum[:, cx1:].ravel()]) if cy0 > 0 else centre.ravel()
    subject = float(abs(centre.std() - border.std()))
    subject_n = min(1.0, subject / 0.12)
    # 分辨率
    res_n = min(1.0, math.log(max(w * h, 1), 2) / math.log(2_100_000, 2))
    return dict(w=w, h=h, aspect=round(w / h, 3), sharp=round(sharp_n, 4), contrast=round(contrast, 4),
                color=round(color_n, 4), sat=round(sat, 4), over=round(hi, 4), under=round(lo, 4),
                exposure_pen=round(exposure_pen, 4), sym=round(sym, 4), subject=round(subject_n, 4), res=round(res_n, 4))

# ---------- 模型分：LAION 美学 v2 + CLIP 参考相似度 ----------
_CACHE = {}
def _load():
    if _CACHE.get("tried"):
        return _CACHE
    _CACHE["tried"] = True
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor
        from huggingface_hub import snapshot_download
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        import glob as _glob
        _cands = _glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--openai--clip-vit-large-patch14/snapshots/*"))
        if not _cands:
            raise RuntimeError("CLIP 未下载")
        clip_dir = _cands[0]
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        _CACHE["torch"] = torch
        _CACHE["dev"] = dev
        _CACHE["model"] = CLIPModel.from_pretrained(clip_dir).to(dev).eval()
        _CACHE["proc"] = CLIPProcessor.from_pretrained(clip_dir)
        head = None
        try:
            import glob, torch.nn as nn
            _d2 = _glob.glob(os.path.expanduser("~/.cache/huggingface/hub/models--shunk031--aesthetics-predictor-v2-sac-logos-ava1-l14-linearMSE/snapshots/*"))
            if not _d2:
                raise RuntimeError("美学头未下载")
            d2 = _d2[0]
            wf = glob.glob(os.path.join(d2, "**", "model.safetensors"), recursive=True)
            sd = {}
            if wf:
                from safetensors.torch import load_file as _lf
                sd = _lf(wf[0])
            else:
                import torch as _t
                bf = glob.glob(os.path.join(d2, "**", "*.bin"), recursive=True)
                if bf:
                    sd = _t.load(bf[0], map_location="cpu")
                    if isinstance(sd, dict) and "state_dict" in sd:
                        sd = sd["state_dict"]
            keys = [k for k in sd if k.startswith("layers.")]
            if keys:
                import re as _re
                idx = sorted({int(_re.match(r"layers\.(\d+)\.", k).group(1)) for k in keys})
                ws = {}
                for i in idx:
                    wk = f"layers.{i}.weight"; bk = f"layers.{i}.bias"
                    if wk in sd and bk in sd:
                        ws[i] = (sd[wk].float().to(dev), sd[bk].float().to(dev))
                _CACHE["mlp"] = [ws[i] for i in sorted(ws)]
                head = True
            _CACHE["head"] = head
        except Exception as e:
            _CACHE["head"] = None
            _CACHE["head_err"] = f"{type(e).__name__}: {e}"
        _CACHE["ok"] = True
    except Exception as e:
        _CACHE["ok"] = False
        _CACHE["err"] = f"{type(e).__name__}: {e}"
    return _CACHE

def clip_embed(paths):
    c = _load()
    if not c.get("ok"):
        return None
    import torch
    from PIL import Image
    embs = []
    for p in paths:
        with torch.no_grad():
            im = Image.open(p).convert("RGB")
            inp = c["proc"](images=im, return_tensors="pt").to(c["dev"])
            feats = c["model"].get_image_features(**inp)
            v = feats if hasattr(feats, "norm") else getattr(feats, "pooler_output", None)
            if v is None:
                v = c["model"].visual_projection(c["model"].vision_model(pixel_values=inp["pixel_values"]).pooler_output)
            v = v / v.norm(dim=-1, keepdim=True)
            embs.append(v)
    return torch.cat(embs)

def laion_scores(paths):
    c = _load()
    if not c.get("ok") or not c.get("mlp"):
        return [None] * len(paths)
    import torch
    out = []
    embs = clip_embed(paths)
    if embs is None:
        return [None] * len(paths)
    with torch.no_grad():
        h = embs
        for i, (W, bb) in enumerate(c.get("mlp") or []):
            h = h @ W.T + bb
            if i < len(c.get("mlp") or []) - 1:
                h = torch.relu(h)
        raw = h.squeeze(-1).float().cpu().numpy().tolist()
    for r in raw:
        out.append(round(float(min(10.0, max(1.0, r))), 3))
    return out

def ref_similarity(paths, refdir):
    refs = [str(p) for p in sorted(Path(refdir).rglob("*")) if p.suffix.lower() in IMG_EXT][:40]
    if not refs:
        return [None] * len(paths)
    e = clip_embed(paths + refs)
    if e is None:
        return [None] * len(paths)
    n = len(paths)
    q = e[:n]; r = e[n:]
    sim = (q @ r.T).max(dim=1).values.cpu().numpy().tolist()
    return [round(float(s), 4) for s in sim]

def base_score(o, laion):
    tech = 0.35 * o["sharp"] + 0.25 * o["contrast"] / 0.3 + 0.20 * o["color"] + 0.20 * o["res"]
    tech = max(0.0, min(1.0, tech)) * (1 - 0.5 * o["exposure_pen"])
    comp = 0.5 * o["sym"] + 0.5 * o["subject"]
    # 无结构惩罚：纯噪声/纯渐变往往清晰度高但零构图，按比例折掉技术分
    if max(o["sym"], o["subject"]) < 0.10:
        tech *= 0.55
    if laion is not None:
        s = 0.55 * ((laion - 1) / 9.0) + 0.25 * tech + 0.20 * comp
    else:
        s = 0.62 * tech + 0.38 * comp
    return round(max(0.0, min(1.0, s)) * 100, 1)

# ---------- 个人偏好校准 ----------
def load_weights():
    if WEIGHTS.exists():
        try:
            return json.load(open(WEIGHTS, encoding="utf-8"))
        except Exception:
            return None
    return None

FEATS = ["laion_n", "sharp", "contrast_n", "color", "sym", "subject", "res", "exposure_pen", "satn"]
def feat_vec(rec):
    o = rec["obj"]; l = rec.get("laion")
    return [ (l - 1) / 9.0 if l else 0.5,
             o["sharp"], min(1.0, o["contrast"] / 0.3), o["color"], o["sym"], o["subject"], o["res"],
             o["exposure_pen"], min(1.0, o["sat"] / 0.5) ]

def personal_prob(rec, w):
    if not w:
        return None
    x = feat_vec(rec)
    z = w["bias"] + sum(wi * xi for wi, xi in zip(w["w"], x))
    return round(1 / (1 + math.exp(-max(-30, min(30, z)))), 4)

def cmd_calibrate(args):
    import numpy as np
    recs = {r["sha"]: r for r in map(json.loads, open(SCORES, encoding="utf-8"))} if SCORES.exists() else {}
    labels = [json.loads(l) for l in open(FEEDBACK, encoding="utf-8")] if FEEDBACK.exists() else []
    rows, ys = [], []
    for lb in labels:
        r = recs.get(lb["sha"])
        if not r:
            continue
        rows.append(feat_vec(r)); ys.append(1.0 if lb["verdict"] == "good" else 0.0)
    if len(rows) < 8:
        print(f"反馈样本不足（{len(rows)} 条，至少 8 条），先继续积累")
        return 1
    X = np.array(rows); y = np.array(ys)
    mu = X.mean(0); sd = X.std(0) + 1e-6
    Z = (X - mu) / sd
    w = np.zeros(Z.shape[1]); b = 0.0
    lr = 0.3
    for _ in range(3000):
        p = 1 / (1 + np.exp(-(Z @ w + b)))
        grad = Z.T @ (p - y) / len(y) + 0.01 * w
        w -= lr * grad; b -= lr * float((p - y).mean())
    p = 1 / (1 + np.exp(-(Z @ w + b)))
    acc = float(((p > 0.5) == y).mean())
    out = {"w": (w / sd).tolist(), "bias": float(b - float((mu * w / sd).sum())), "mu": mu.tolist(), "sd": sd.tolist(),
           "n": len(y), "acc": round(acc, 3), "fitted_at": time.strftime("%F %T"), "feats": FEATS}
    json.dump(out, open(WEIGHTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"校准完成：样本 {len(y)} 条，训练集准确率 {acc:.1%}，权重已存 {WEIGHTS}")
    return 0

def cmd_feedback(args):
    p = Path(args.path)
    if not p.exists():
        print("文件不存在:", p); return 2
    rec = {"ts": time.strftime("%F %T"), "sha": sha12(p), "path": str(p), "verdict": args.verdict, "note": args.note or ""}
    with open(FEEDBACK, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"已记反馈 {args.verdict}: {p.name}")
    return 0

def collect(targets):
    out = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            out += [str(x) for x in sorted(p.rglob("*")) if x.suffix.lower() in IMG_EXT]
        elif p.exists() and p.suffix.lower() in IMG_EXT:
            out.append(str(p))
    return out

def cmd_score(args):
    files = collect(args.paths)
    if not files:
        print("没有可评分的图片"); return 2
    ls = laion_scores(files)
    sims = ref_similarity(files, args.ref) if args.ref else [None] * len(files)
    w = load_weights()
    rows = []
    with open(SCORES, "a", encoding="utf-8") as sf:
        for f, l, sim in zip(files, ls, sims):
            try:
                o = objective(f)
            except Exception as e:
                print(f"跳过 {f}: {e}"); continue
            rec = {"sha": sha12(f), "path": f, "obj": o, "laion": l, "ref": sim, "ts": time.strftime("%F %T")}
            rec["base"] = base_score(o, l)
            pp = personal_prob(rec, w)
            rec["personal"] = pp
            rec["final"] = round(100 * (0.45 * rec["base"] / 100 + 0.55 * pp), 1) if pp is not None else rec["base"]
            sf.write(json.dumps(rec, ensure_ascii=False) + "\n")
            rows.append(rec)
    rows.sort(key=lambda r: -r["final"])
    if args.top:
        rows = rows[: args.top]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        mode = "含个人偏好" if w else "通用分（未校准）"
        print(f"评分模式：{mode}｜共 {len(rows)} 张")
        for r in rows:
            o = r["obj"]
            l = f"{r['laion']:.2f}" if r["laion"] is not None else "—"
            print(f"{r['final']:5.1f}  base {r['base']:5.1f}  美学 {l}  清晰 {o['sharp']:.2f} 对比 {min(1,o['contrast']/0.3):.2f} 色 {o['color']:.2f} 对称 {o['sym']:.2f} 主体 {o['subject']:.2f}  {Path(r['path']).name}")
    return 0

def cmd_stats(args):
    n = sum(1 for _ in open(SCORES, encoding="utf-8")) if SCORES.exists() else 0
    fb = [json.loads(l) for l in open(FEEDBACK, encoding="utf-8")] if FEEDBACK.exists() else []
    good = sum(1 for x in fb if x["verdict"] == "good")
    w = load_weights()
    print(f"已评分 {n} 张；反馈 {len(fb)} 条（好 {good} / 差 {len(fb) - good}）；校准 {'已启用 acc=%.2f' % w['acc'] if w else '未启用（≥8 条反馈后可 calibrate）'}")
    return 0

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score"); s.add_argument("paths", nargs="+"); s.add_argument("--top", type=int); s.add_argument("--json", action="store_true"); s.add_argument("--ref")
    f = sub.add_parser("feedback"); f.add_argument("path"); f.add_argument("verdict", choices=["good", "bad"]); f.add_argument("--note")
    sub.add_parser("calibrate"); sub.add_parser("stats")
    a = ap.parse_args()
    return {"score": cmd_score, "feedback": cmd_feedback, "calibrate": cmd_calibrate, "stats": cmd_stats}[a.cmd](a)

if __name__ == "__main__":
    sys.exit(main())

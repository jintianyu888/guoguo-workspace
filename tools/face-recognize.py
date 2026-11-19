#!/usr/bin/env python3
"""本地人脸识别（InsightFace antelopev2 + GPU，离线）。支持自动学习。
用法:
  register --name 张三 img1.jpg img2.jpg     # 录入
  recognize --img x.jpg                     # 识别单张
  watch --url rtsp://... [--autolearn 1]    # 实时识别（默认开自动学习）
  grab --url rtsp://... --out x.jpg
数据: state/faces/db.npz (多样本)  state/faces/autolearn.log
"""
import os as _os, site as _site, glob as _glob, ctypes as _ct
_libs = _glob.glob(_os.path.join(_site.getsitepackages()[0], "nvidia", "*", "lib"))
_os.environ["LD_LIBRARY_PATH"] = ":".join(_libs + ["/usr/lib/wsl/lib"]) + ":" + _os.environ.get("LD_LIBRARY_PATH", "")
for _d in _libs:
    for _f in sorted(_glob.glob(_os.path.join(_d, "lib*.so*"))):
        try: _ct.CDLL(_f)
        except Exception: pass

import argparse, json, os, sys, time
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(BASE, "state", "faces"); os.makedirs(FD, exist_ok=True)
_PROV = ["CPUExecutionProvider"] if os.environ.get("FACE_GPU","0") != "1" else ["CUDAExecutionProvider","CPUExecutionProvider"]
_DET = int(os.environ.get("FACE_DET_SIZE","640"))
DBP = os.path.join(FD, "db.npz"); AL = os.path.join(FD, "autolearn.log")
HITS = os.path.join(FD, "hits"); os.makedirs(HITS, exist_ok=True)

_app = None
def app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name="antelopev2", providers=(_PROV))
        _app.prepare(ctx_id=0 if _PROV[0].startswith("CUDA") else -1, det_size=(_DET, _DET))
    return _app

def load_db():
    if os.path.exists(DBP):
        d = np.load(DBP, allow_pickle=True)
        return list(d["labels"]), d["samples"]
    return [], np.zeros((0, 512), dtype=np.float32)

def save_db(labels, samples):
    np.savez(DBP, labels=np.array(labels), samples=samples)

def norm(v): return v / np.linalg.norm(v)

def best(labels, samples, v, thr):
    if not len(labels): return None, 0.0
    sims = samples @ v; i = int(np.argmax(sims))
    return (labels[i], float(sims[i])) if sims[i] >= thr else (None, float(sims[i]))

def alog(msg):
    open(AL, "a").write("[%s] %s\n" % (time.strftime("%F %T"), msg))

def add_sample(labels, samples, name, v, cap=50, learned=False):
    labels = labels + [name]
    samples = np.vstack([samples, v[None, :]]) if samples.size else v[None, :]
    own = [i for i, l in enumerate(labels) if l == name]
    if len(own) > cap:
        drop = set(own[:len(own)-cap])
        keep = [i for i in range(len(labels)) if i not in drop]
        labels = [labels[i] for i in keep]; samples = samples[keep]
    return labels, samples

def faces_of(p):
    import cv2
    img = cv2.imread(p)
    if img is None: raise SystemExit("读不到图片: "+p)
    return app().get(img)

def cmd_register(a):
    labels, samples = load_db(); n = 0
    for p in a.imgs:
        fs = faces_of(p)
        if not fs: print("  ! 没人脸:", p); continue
        f = max(fs, key=lambda x:(x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
        labels, samples = add_sample(labels, samples, a.name, norm(f.embedding), a.cap)
        n += 1; print("  + ", p)
    save_db(labels, samples)
    print("OK 录入 %s 共 %d 张 | 库总样本 %d" % (a.name, n, len(labels)))

def cmd_recognize(a):
    labels, samples = load_db()
    for f in faces_of(a.img):
        who, s = best(labels, samples, norm(f.embedding), a.threshold)
        print("人脸@%s -> %s (%.3f)" % ([int(x) for x in f.bbox], who or "未知", s))

def cmd_watch(a):
    import cv2
    labels, samples = load_db()
    cap = cv2.VideoCapture(a.url)
    if not cap.isOpened(): raise SystemExit("打不开流")
    print("监视中(投票3帧; 自动学习 %s, 阈值%.2f)" % ("开" if a.autolearn else "关", a.autolearn_thr))
    votes = []; last = {}
    while True:
        ok, fr = cap.read()
        if not ok:
            time.sleep(2); cap = cv2.VideoCapture(a.url); continue
        for f in app().get(fr):
            v = norm(f.embedding)
            who, s = best(labels, samples, v, a.threshold)
            key = who or "unknown"
            votes.append(key); del votes[:-5]
            if votes.count(key) < 3: continue
            now = time.time()
            if now - last.get(key, 0) <= a.cooldown: continue
            last[key] = now
            print("[%s] %s (%.3f)" % (time.strftime("%H:%M:%S"), who or "未知", s), flush=True)
            b = f.bbox.astype(int); x1,y1,x2,y2 = b
            cv2.imwrite(os.path.join(HITS, "%s-%d.jpg" % (key, int(now))), fr[max(0,y1):y2, max(0,x1):x2])
            if a.autolearn and who and s >= a.autolearn_thr:
                labels, samples = add_sample(labels, samples, who, v, a.cap, learned=True)
                save_db(labels, samples)
                alog("自动学习: %s <- 新样本(相似度 %.3f), 该人样本数=%d" % (who, s, sum(1 for l in labels if l==who)))
        time.sleep(a.interval)

def cmd_stats(a):
    labels, samples = load_db()
    from collections import Counter
    c = Counter(labels)
    print("库中人物 %d 位，样本 %d 张:" % (len(c), len(labels)))
    for k, n in c.most_common(): print("  %s: %d" % (k, n))

def cmd_grab(a):
    import cv2
    cap = cv2.VideoCapture(a.url); ok, fr = cap.read()
    if not ok: raise SystemExit("抓帧失败")
    cv2.imwrite(a.out, fr); print("已保存", a.out, fr.shape)

if __name__ == "__main__":
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register"); r.add_argument("--name", required=True); r.add_argument("imgs", nargs="+"); r.add_argument("--cap", type=int, default=50); r.set_defaults(f=cmd_register)
    c = sub.add_parser("recognize"); c.add_argument("--img", required=True); c.add_argument("--threshold", type=float, default=0.5); c.set_defaults(f=cmd_recognize)
    w_ = sub.add_parser("watch"); w_.add_argument("--url", required=True); w_.add_argument("--interval", type=float, default=2); w_.add_argument("--cooldown", type=float, default=60)
    w_.add_argument("--threshold", type=float, default=0.5); w_.add_argument("--autolearn", type=int, default=0); w_.add_argument("--autolearn-thr", type=float, default=0.55); w_.add_argument("--cap", type=int, default=50); w_.set_defaults(f=cmd_watch)
    s_ = sub.add_parser("stats"); s_.set_defaults(f=cmd_stats)
    g = sub.add_parser("grab"); g.add_argument("--url", required=True); g.add_argument("--out", required=True); g.set_defaults(f=cmd_grab)
    a = p.parse_args(); a.f(a)

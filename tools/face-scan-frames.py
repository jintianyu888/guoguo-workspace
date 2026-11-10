#!/usr/bin/env python3
"""扫一个目录下的帧图，抽人脸并按余弦阈值去重后入库（state/faces/collected + collected.npz）。
由 nvr-fetch-isapi.py 抽帧后调用；与 nvr-face-scan.py 的入库口径一致。
用法: venvs/face/bin/python tools/face-scan-frames.py <dir> [--dedup 0.55] [--minsize 60]
"""
import os as _os, site as _site, glob as _glob, ctypes as _ct
_libs = _glob.glob(_os.path.join(_site.getsitepackages()[0], "nvidia", "*", "lib"))
if _libs:
    _os.environ["LD_LIBRARY_PATH"] = ":".join(_libs + ["/usr/lib/wsl/lib"]) + ":" + _os.environ.get("LD_LIBRARY_PATH", "")
    for _d in _libs:
        for _f in sorted(_glob.glob(_os.path.join(_d, "lib*.so*"))):
            try: _ct.CDLL(_f)
            except Exception: pass
import argparse, datetime, os, sys
import numpy as np, cv2

BASE = "/home/j/.openclaw/workspace"
FD = os.path.join(BASE, "state", "faces")
COLL = os.path.join(FD, "collected")
NPZ = os.path.join(FD, "collected.npz")
LOGF = os.path.join(BASE, "state/work/nvr-face-scan.log")

_app = None
def app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name="antelopev2", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(1024, 1024))
    return _app

def log(m):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%F %T"), m)
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOGF), exist_ok=True)
        open(LOGF, "a").write(line + "\n")
    except Exception:
        pass

def load():
    if os.path.exists(NPZ):
        d = np.load(NPZ, allow_pickle=True)
        return list(d["files"]), d["emb"]
    return [], np.zeros((0, 512), dtype=np.float32)

def save(files, emb):
    np.savez(NPZ, files=np.array(files), emb=emb)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--dedup", type=float, default=0.55)
    ap.add_argument("--minsize", type=int, default=60)
    a = ap.parse_args()
    if not os.path.isdir(a.dir):
        log("目录不存在 %s" % a.dir); return 2
    os.makedirs(COLL, exist_ok=True)
    files, emb = load()
    imgs = sorted(f for f in os.listdir(a.dir) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    got = new = 0
    for name in imgs:
        p = os.path.join(a.dir, name)
        img = cv2.imread(p)
        if img is None:
            continue
        got += 1
        for f in app().get(img):
            v = f.embedding / np.linalg.norm(f.embedding)
            if len(emb) and float(np.max(emb @ v)) > a.dedup:
                continue
            x1, y1, x2, y2 = [int(x) for x in f.bbox]
            if (x2 - x1) < a.minsize or (y2 - y1) < a.minsize:
                continue
            crop = img[max(y1, 0):y2, max(x1, 0):x2]
            if crop.size == 0:
                continue
            ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            out = os.path.join(COLL, "isapi_%s.jpg" % ts)
            cv2.imwrite(out, crop)
            files.append(os.path.basename(out))
            emb = np.vstack([emb, v.reshape(1, -1)]) if len(emb) else v.reshape(1, -1)
            new += 1
    save(files, emb)
    log("目录 %s：帧 %d，新人脸 %d，库 %d" % (os.path.basename(a.dir), got, new, len(files)))
    return 0

if __name__ == "__main__":
    sys.exit(main())

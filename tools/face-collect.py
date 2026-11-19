#!/usr/bin/env python3
"""自动收集人脸 + 聚类，供人工标注。
用法:
  python face-collect.py collect --url rtsp://... --minutes 10   # 边看边存人脸小图
  python face-collect.py cluster                                  # 把收集到的人脸分组
  python face-collect.py sheet --group 0                          # 生成某组的拼图(供标注)
数据: state/faces/collected/*.jpg  +  state/faces/collected.npz (特征)
      state/faces/groups.json  +  state/faces/sheets/group_N.jpg
"""
import os as _os, site as _site, glob as _glob, ctypes as _ct
_libs = _glob.glob(_os.path.join(_site.getsitepackages()[0], "nvidia", "*", "lib"))
_os.environ["LD_LIBRARY_PATH"] = ":".join(_libs + ["/usr/lib/wsl/lib"]) + ":" + _os.environ.get("LD_LIBRARY_PATH", "")
for _d in _libs:
    for _f in sorted(_glob.glob(_os.path.join(_d, "lib*.so*"))):
        try: _ct.CDLL(_f)
        except Exception: pass

import argparse, json, os, time
import numpy as np, cv2

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(BASE, "state", "faces")
COLL = os.path.join(FD, "collected"); os.makedirs(COLL, exist_ok=True)
NPZ = os.path.join(FD, "collected.npz")
GJ = os.path.join(FD, "groups.json")
SHEETS = os.path.join(FD, "sheets"); os.makedirs(SHEETS, exist_ok=True)

_app = None
def app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name="antelopev2", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(1024, 1024))
    return _app

def load():
    if os.path.exists(NPZ):
        d = np.load(NPZ, allow_pickle=True)
        return list(d["files"]), d["emb"]
    return [], np.zeros((0, 512), dtype=np.float32)

def save(files, emb):
    np.savez(NPZ, files=np.array(files), emb=emb)

def cmd_collect(a):
    files, emb = load()
    cap = cv2.VideoCapture(a.url)
    if not cap.isOpened(): raise SystemExit("打不开流")
    print("开始收集", a.url, "时长", a.minutes, "分钟")
    t0 = time.time(); saved = 0; seen = 0
    while time.time() - t0 < a.minutes * 60:
        ok, fr = cap.read()
        if not ok:
            time.sleep(2); cap = cv2.VideoCapture(a.url); continue
        fs = app().get(fr)
        for f in fs:
            seen += 1
            v = f.embedding / np.linalg.norm(f.embedding)
            if len(emb) and float(np.max(emb @ v)) > a.dedup:
                continue  # 太像已有的，跳过
            b = f.bbox.astype(int); x1, y1, x2, y2 = b
            if (x2 - x1) < a.minsize or (y2 - y1) < a.minsize: continue
            pad = int(0.25 * max(x2 - x1, y2 - y1))
            y1 = max(0, y1 - pad); y2 = min(fr.shape[0], y2 + pad)
            x1 = max(0, x1 - pad); x2 = min(fr.shape[1], x2 + pad)
            crop = fr[y1:y2, x1:x2]
            name = time.strftime("%Y%m%d-%H%M%S") + "-%03d.jpg" % saved
            cv2.imwrite(os.path.join(COLL, name), crop)
            files.append(name); emb = np.vstack([emb, v[None, :]]) if emb.size else v[None, :]
            saved += 1
        if a.every: time.sleep(a.every)
    save(files, emb)
    print("完成：检出 %d 张脸，新增保存 %d 张，库共 %d 张" % (seen, saved, len(files)))
    print("小图目录:", COLL)

def cmd_cluster(a):
    files, emb = load()
    if not len(files): raise SystemExit("还没收集到人脸")
    groups = []
    for i, v in enumerate(emb):
        placed = False
        for g in groups:
            c = np.mean(emb[g["idx"]], axis=0); c = c / np.linalg.norm(c)
            if float(c @ v) >= a.threshold:
                g["idx"].append(i); placed = True; break
        if not placed:
            groups.append({"idx": [i]})
    groups = [g for g in groups if len(g["idx"]) >= a.mincount]
    out = []
    for n, g in enumerate(groups):
        fs_ = [files[i] for i in g["idx"]]
        out.append({"group": n, "count": len(fs_), "files": fs_})
        make_sheet(n, fs_)
    json.dump(out, open(GJ, "w"), ensure_ascii=False, indent=1)
    print("聚类完成：%d 人（组）" % len(out))
    for g in out: print("  组%d: %d 张" % (g["group"], g["count"]))
    print("拼图:", SHEETS); print("清单:", GJ)

def make_sheet(gn, fs, cols=6, cell=160):
    ims = []
    for f in fs[:36]:
        im = cv2.imread(os.path.join(COLL, f))
        if im is None: continue
        im = cv2.resize(im, (cell, cell)); ims.append(im)
    if not ims: return
    rows = (len(ims) + cols - 1) // cols
    sheet = np.zeros((rows * cell, cols * cell, 3), dtype=np.uint8)
    for i, im in enumerate(ims):
        r, c = divmod(i, cols); sheet[r*cell:(r+1)*cell, c*cell:(c+1)*cell] = im
    cv2.imwrite(os.path.join(SHEETS, "group_%d.jpg" % gn), sheet)

p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="cmd", required=True)
c = sub.add_parser("collect"); c.add_argument("--url", required=True); c.add_argument("--minutes", type=float, default=10)
c.add_argument("--every", type=float, default=1.0); c.add_argument("--dedup", type=float, default=0.55); c.add_argument("--minsize", type=int, default=80); c.set_defaults(f=cmd_collect)
k = sub.add_parser("cluster"); k.add_argument("--threshold", type=float, default=0.42); k.add_argument("--mincount", type=int, default=2); k.set_defaults(f=cmd_cluster)
a = p.parse_args(); a.f(a)

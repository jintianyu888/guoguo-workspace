#!/usr/bin/env python3
"""人脸库建库第一步：质量过滤 + 正脸聚类。
用法: python3 face-quality-index.py [--min-det 0.6] [--min-size 90] [--max-yaw 20] [--max-pitch 20] [--thr 0.5] [--mincount 3]
产出:
  state/faces/quality.json   每张图的 det/size/yaw/pitch/roll
  state/faces/emb2.npz       重算特征(files,emb)
  state/faces/groups2.json   正脸聚类结果
  state/faces/sheets2/*.jpg  各组拼图(供认人)
只读原图，不删除、不移动任何采集数据。
"""
import os, sys, glob, json, argparse
import numpy as np, cv2

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(BASE, "state", "faces")
COLL = os.path.join(FD, "collected")
SHEETS2 = os.path.join(FD, "sheets2"); os.makedirs(SHEETS2, exist_ok=True)

_models = {}
def app(det='640'):
    if "a" not in _models:
        import onnxruntime as ort
        from insightface.app import FaceAnalysis
        prov = ["CUDAExecutionProvider", "CPUExecutionProvider"] if "CUDAExecutionProvider" in ort.get_available_providers() else ["CPUExecutionProvider"]
        a = FaceAnalysis(name="antelopev2", providers=prov)
        ds=(int(det), int(det))
        a.prepare(ctx_id=0 if "CUDAExecutionProvider" in prov else -1, det_size=ds)
        _models["a"] = a
    return _models["a"]

def make_sheet(path, files, cols=6, cell=160, maxn=36):
    ims = []
    for f in files[:maxn]:
        im = cv2.imread(os.path.join(COLL, f))
        if im is None: continue
        ims.append(cv2.resize(im, (cell, cell)))
    if not ims: return
    rows = (len(ims) + cols - 1) // cols
    sheet = np.zeros((rows * cell, cols * cell, 3), np.uint8)
    for i, im in enumerate(ims):
        r, c = divmod(i, cols)
        sheet[r*cell:(r+1)*cell, c*cell:(c+1)*cell] = im
    cv2.imwrite(path, sheet)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-det", type=float, default=0.6)
    ap.add_argument("--min-size", type=int, default=90)
    ap.add_argument("--max-yaw", type=float, default=20)
    ap.add_argument("--max-pitch", type=float, default=20)
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--mincount", type=int, default=3)
    ap.add_argument("--det-size", default="640")
    a = ap.parse_args()

    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(COLL, "*.jpg")))
    print("采集图 %d 张" % len(files), flush=True)
    meta, keep_f, keep_e = [], [], []
    for i, fn in enumerate(files):
        img = cv2.imread(os.path.join(COLL, fn))
        if img is None: continue
        fs = app(a.det_size).get(img)
        if not fs:
            meta.append({"f": fn, "ok": False, "why": "noface"}); continue
        f = max(fs, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
        w = float(f.bbox[2]-f.bbox[0]); h = float(f.bbox[3]-f.bbox[1])
        pose = getattr(f, "pose", None)
        yaw = float(pose[1]) if pose is not None else 999.0
        pitch = float(pose[0]) if pose is not None else 999.0
        roll = float(pose[2]) if pose is not None else 999.0
        det = float(getattr(f, "det_score", 0.0))
        ok = (det >= a.min_det and min(w, h) >= a.min_size and abs(yaw) <= a.max_yaw and abs(pitch) <= a.max_pitch)
        meta.append({"f": fn, "ok": ok, "det": round(det,3), "size": int(min(w,h)), "yaw": round(yaw,1), "pitch": round(pitch,1), "roll": round(roll,1)})
        if ok:
            keep_f.append(fn); keep_e.append(f.normed_embedding.astype(np.float32))
        if (i+1) % 25 == 0: print("  已处理 %d/%d，正脸累计 %d" % (i+1, len(files), len(keep_f)), flush=True)

    json.dump(meta, open(os.path.join(FD, "quality.json"), "w"), ensure_ascii=False)
    print("质量过滤：%d 张合格 / %d 张总计" % (len(keep_f), len(files)), flush=True)
    if not keep_f:
        print("没有正脸样本，无法聚类"); return 2
    emb = np.vstack(keep_e)
    np.savez_compressed(os.path.join(FD, "emb2.npz"), files=np.array(keep_f), emb=emb)

    groups = []
    for i, v in enumerate(emb):
        placed = False
        for g in groups:
            c = np.mean(emb[g["idx"]], axis=0); c = c/np.linalg.norm(c)
            if float(c @ v) >= a.thr:
                g["idx"].append(i); placed = True; break
        if not placed: groups.append({"idx": [i]})
    groups = [g for g in groups if len(g["idx"]) >= a.mincount]
    groups.sort(key=lambda g: -len(g["idx"]))
    out = []
    for n, g in enumerate(groups):
        fs_ = [keep_f[i] for i in g["idx"]]
        out.append({"group": n, "count": len(fs_), "files": fs_})
        make_sheet(os.path.join(SHEETS2, "group_%d.jpg" % n), fs_)
    json.dump(out, open(os.path.join(FD, "groups2.json"), "w"), ensure_ascii=False, indent=1)
    print("正脸聚类：%d 组，覆盖 %d 张" % (len(out), sum(x['count'] for x in out)))
    for x in out[:12]: print("  组%d: %d 张" % (x["group"], x["count"]))
    print("拼图:", SHEETS2)
    return 0

if __name__ == "__main__":
    sys.exit(main())

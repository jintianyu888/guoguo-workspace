#!/usr/bin/env python3
"""常驻单路抓帧+人脸（用 ffmpeg 出帧，避开 OpenCV 对该 HEVC 流的解码问题）。
用法: cam-watch.py <通道号 101|102|301...> [间隔秒]
"""
import os as _os, site as _site, glob as _glob, ctypes as _ct
_libs = _glob.glob(_os.path.join(_site.getsitepackages()[0], "nvidia", "*", "lib"))
_os.environ["LD_LIBRARY_PATH"] = ":".join(_libs + ["/usr/lib/wsl/lib"]) + ":" + _os.environ.get("LD_LIBRARY_PATH", "")
for _d in _libs:
    for _f in sorted(_glob.glob(_os.path.join(_d, "lib*.so*"))):
        try: _ct.CDLL(_f)
        except Exception: pass

import glob, os, subprocess, sys, time
import numpy as np, cv2

BASE = "/home/j/.openclaw/workspace"
FD = os.path.join(BASE, "state", "faces"); COLL = os.path.join(FD, "collected")
NPZ = os.path.join(FD, "collected.npz"); LOG = os.path.join(BASE, "state", "work", "cam-watch.log")
HITS = os.path.join(FD, "hits")
for d in (COLL, HITS, os.path.dirname(LOG)): os.makedirs(d, exist_ok=True)

CH = sys.argv[1] if len(sys.argv) > 1 else "101"
EVERY = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
ENV = {}
for ln in open(os.path.expanduser("~/.config/hik-nvr.env")):
    if "=" in ln: k, v = ln.strip().split("=", 1); ENV[k] = v
URL = "rtsp://admin:%s@%s:554/Streaming/Channels/%s" % (ENV.get("HIK_NVR_PASS",""), ENV.get("HIK_NVR_IP","192.168.1.103"), CH)
TMP = "/home/j/.openclaw/workspace/state/tmp/cam-%s" % CH

def log(m):
    line = "[%s] ch%s %s" % (time.strftime("%F %T"), CH, m)
    print(line, flush=True); open(LOG, "a").write(line + "\n")

def spawn():
    os.makedirs(TMP, exist_ok=True)
    for f in glob.glob(TMP + "/*.jpg"):
        try: os.remove(f)
        except Exception: pass
    return subprocess.Popen(["ffmpeg","-hide_banner","-loglevel","error","-rtsp_transport","tcp",
        "-timeout","15000000","-i",URL,"-vf","fps=1/%g" % EVERY,"-f","image2","-y", TMP+"/f_%06d.jpg"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

_app = None
def app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name="antelopev2", providers=["CUDAExecutionProvider","CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(1024,1024))
    return _app

def load():
    if os.path.exists(NPZ):
        d = np.load(NPZ, allow_pickle=True); return list(d["files"]), d["emb"]
    return [], np.zeros((0,512), dtype=np.float32)
def save(files, emb): np.savez(NPZ, files=np.array(files), emb=emb)

log("启动 url=%s 每 %.0f 秒一帧" % (URL.replace(ENV.get("HIK_NVR_PASS",""), "***"), EVERY))
proc = spawn(); files, emb = load(); seen = set(); n = 0
while True:
    if proc.poll() is not None:
        log("ffmpeg 退出(%s)，10 秒后重启" % proc.returncode); time.sleep(10); proc = spawn(); seen = set()
    for p in sorted(glob.glob(TMP + "/*.jpg")):
        if p in seen: continue
        seen.add(p); n += 1
        if len(seen) > 200: seen = set(sorted(seen)[-50:])
        img = cv2.imread(p)
        if img is None: continue
        for f in app().get(img):
            v = f.embedding / np.linalg.norm(f.embedding)
            if len(emb) and float(np.max(emb @ v)) > 0.55: continue
            b = f.bbox.astype(int); x1,y1,x2,y2 = b
            if (x2-x1) < 60 or (y2-y1) < 60: continue
            pad = int(0.25*max(x2-x1,y2-y1))
            y1=max(0,y1-pad); y2=min(img.shape[0],y2+pad); x1=max(0,x1-pad); x2=min(img.shape[1],x2+pad)
            nm = "cam%s-%s-%03d.jpg" % (CH, time.strftime("%Y%m%d-%H%M%S"), n)
            cv2.imwrite(os.path.join(COLL, nm), img[y1:y2, x1:x2])
            files.append(nm); emb = np.vstack([emb, v[None,:]]) if emb.size else v[None,:]
            save(files, emb)
            log("新脸入库 %s (库%d)" % (nm, len(files)))
    time.sleep(0.5)

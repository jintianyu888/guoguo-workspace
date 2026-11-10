#!/usr/bin/env python3
"""扫描 NVR 录像收集人脸（本地、零 token）。
用法: python nvr-face-scan.py [--date 2026-10-11] [--channels 101,301,...] [--hours 0-23] [--fps 0.2]
"""
import os as _os, site as _site, glob as _glob, ctypes as _ct
_libs = _glob.glob(_os.path.join(_site.getsitepackages()[0], "nvidia", "*", "lib"))
if _libs:
    _os.environ["LD_LIBRARY_PATH"] = ":".join(_libs + ["/usr/lib/wsl/lib"]) + ":" + _os.environ.get("LD_LIBRARY_PATH", "")
for _d in _libs:
    for _f in sorted(_glob.glob(_os.path.join(_d, "lib*.so*"))):
        try: _ct.CDLL(_f)
        except Exception: pass

import argparse, os, subprocess, sys, time, datetime, shutil
import numpy as np, cv2

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD = os.path.join(BASE, "state", "faces"); COLL = os.path.join(FD, "collected")
NPZ = os.path.join(FD, "collected.npz")
WORK = os.path.join(BASE, "state", "work"); os.makedirs(WORK, exist_ok=True)
LOG = os.path.join(WORK, "nvr-face-scan.log")
os.makedirs(COLL, exist_ok=True)

def log(msg):
    line = "[%s] %s" % (time.strftime("%F %T"), msg)
    print(line, flush=True)
    open(LOG, "a").write(line + "\n")

ENV = {}
_ENVP = os.path.expanduser("~/.config/hik-nvr.env")
if not os.path.exists(_ENVP):
    log("❌ 缺少 NVR 凭据文件 %s（需含 HIK_NVR_PASS），本次跳过扫描" % _ENVP)
    sys.exit(2)
try:
    with open(_ENVP) as _f:
        for ln in _f:
            if "=" not in ln or ln.strip().startswith("#"):
                continue
            k, v = ln.strip().split("=", 1)
            ENV[k] = v
except Exception as e:
    log("❌ 读取 NVR 凭据失败：%s，本次跳过扫描" % e)
    sys.exit(2)
PASS = ENV.get("HIK_NVR_PASS", "")
if not PASS:
    log("❌ NVR 凭据缺 HIK_NVR_PASS（值为空），本次跳过扫描")
    sys.exit(2)
NVR_IP = ENV.get("HIK_NVR_IP", "192.168.1.103")

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
        d = np.load(NPZ, allow_pickle=True); return list(d["files"]), d["emb"]
    return [], np.zeros((0, 512), dtype=np.float32)

def save(files, emb):
    np.savez(NPZ, files=np.array(files), emb=emb)

# 2026-10-24 实测：window=20 秒的 playback 段在海康 HEVC 上基本拉不动（demuxing 超时 → 0 帧）；
# 同一通道改 300 秒窗口能稳定出帧。默认窗口提到 300 秒。
def scan_channel_hour(ch, day, hour, files, emb, fps, minsize, dedup, window=300):
    # 本地 hour -> UTC
    utc = datetime.datetime.combine(day, datetime.time(hour, 0)) - datetime.timedelta(hours=8)
    st = utc.strftime("%Y%m%dT%H%M%SZ")
    en = (utc + datetime.timedelta(seconds=window)).strftime("%Y%m%dT%H%M%SZ")
    url = "rtsp://admin:%s@%s:554/Streaming/tracks/%s?starttime=%s&endtime=%s" % (PASS, NVR_IP, ch, st, en)
    tmp = "/home/j/.openclaw/workspace/state/tmp/nvr_%s_%02d" % (ch, hour); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp, exist_ok=True)
    try:
        # 2026-10-24 修：海康 playback 是 HEVC 且 SDP 不带分辨率，默认 probesize 探不出参数
        # → "Could not find codec parameters ... Output file does not contain any stream" → 0 帧。
        # 加 analyzeduration/probesize，并把 ffmpeg 报错落到 LOG 便于下次排查（原来丢 /dev/null）。
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-rtsp_transport", "tcp",
                        "-analyzeduration", "10000000", "-probesize", "10000000",
                        # 2026-10-24：-timeout（15s/60s）都会让 HEVC 回放在中途
                        # "Error during demuxing: Connection timed out" → 0 帧。
                        # 手工验证：去掉 -timeout，同参数 5 分钟窗口能稳定出 15 帧，故移除，
                        # 由外层 subprocess timeout=180 兜底。
                        "-i", url, "-vf", "fps=%s" % fps,
                        "-frames:v", "900", "-y", os.path.join(tmp, "f_%05d.jpg")],
                       timeout=180, stdout=subprocess.DEVNULL,
                       stderr=open(LOG, "a"))
    except subprocess.TimeoutExpired:
        pass  # 拉流超时 → 当作该段无录像/结束，继续下一段
    got = 0; saved = 0
    for p in sorted(_glob.glob(os.path.join(tmp, "*.jpg"))):
        img = cv2.imread(p)
        if img is None: continue
        got += 1
        for f in app().get(img):
            v = f.embedding / np.linalg.norm(f.embedding)
            if len(emb) and float(np.max(emb @ v)) > dedup: continue
            b = f.bbox.astype(int); x1, y1, x2, y2 = b
            if (x2-x1) < minsize or (y2-y1) < minsize: continue
            pad = int(0.25*max(x2-x1, y2-y1))
            y1=max(0,y1-pad); y2=min(img.shape[0],y2+pad); x1=max(0,x1-pad); x2=min(img.shape[1],x2+pad)
            name = "%s-%s-h%02d-%03d.jpg" % (day.strftime("%Y%m%d"), ch, hour, saved)
            cv2.imwrite(os.path.join(COLL, name), img[y1:y2, x1:x2])
            files.append(name); emb = np.vstack([emb, v[None,:]]) if emb.size else v[None,:]
            saved += 1
    shutil.rmtree(tmp, ignore_errors=True)
    return got, saved, files, emb

ap = argparse.ArgumentParser()
ap.add_argument("--date", default=datetime.date.today().strftime("%Y-%m-%d"))
ap.add_argument("--channels", default="101,301,701,1001,1201")
ap.add_argument("--hours", default="0-23")
ap.add_argument("--fps", type=float, default=0.2)
ap.add_argument("--minsize", type=int, default=60)
ap.add_argument("--dedup", type=float, default=0.55)
ap.add_argument("--window", type=int, default=20, help="每小时采样秒数(回放1x,别整小时拉)")
ap.add_argument("--skip-hours", default="4", help="跳过的本地小时(静默窗口断网)，逗号分隔")
a = ap.parse_args()

day = datetime.datetime.strptime(a.date, "%Y-%m-%d").date()
h0, h1 = a.hours.split("-"); hours = list(range(int(h0), int(h1)+1))
skip = set(int(x) for x in a.skip_hours.split(",") if x.strip() != "")
hours = [h for h in hours if h not in skip]
files, emb = load()
log("=== NVR 人脸扫描开始 date=%s channels=%s hours=%s->%s fps=%s ===" % (a.date, a.channels, h0, h1, a.fps))
tot_f = tot_s = 0
for ch in a.channels.split(","):
    for h in hours:
        try:
            g, s, files, emb = scan_channel_hour(ch, day, h, files, emb, a.fps, a.minsize, a.dedup, a.window)
            save(files, emb)
            tot_f += g; tot_s += s
            log("ch%s %02d:00 帧%d 新增%d (库%d)" % (ch, h, g, s, len(files)))
        except Exception as e:
            log("ch%s %02d:00 失败: %r" % (ch, h, e))
log("=== 完成: 总帧%d 新增人脸%d 库共%d ===" % (tot_f, tot_s, len(files)))

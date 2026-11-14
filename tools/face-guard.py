#!/usr/bin/env python3
"""face-guard.py — 人脸在场守卫：主公不在且有陌生人/久空 → 锁 Windows 屏幕。
本地 GPU、零 token。摄像头=得力4K（tools/cam.sh）。数据 state/faces/db.npz。
用法:
  face-guard.py enroll --name 主公 --n 8     # 连拍 8 张并录入
  face-guard.py check                        # 单次判定，打印 JSON
  face-guard.py daemon                       # 常驻循环（systemd: oc-face-guard）
配置: state/face-guard/config.json
"""
import os, sys, json, time, subprocess, argparse, datetime
import os as _os, site as _site, glob as _glob, ctypes as _ct
_libs = _glob.glob(_os.path.join(_site.getsitepackages()[0], "nvidia", "*", "lib"))
_os.environ["LD_LIBRARY_PATH"] = ":".join(_libs + ["/usr/lib/wsl/lib"]) + ":" + _os.environ.get("LD_LIBRARY_PATH", "")
for _d in _libs:
    for _f in sorted(_glob.glob(_os.path.join(_d, "lib*.so*"))):
        try: _ct.CDLL(_f)
        except Exception: pass

WS = "/home/j/.openclaw/workspace"
TOOLS = os.path.join(WS, "tools")
SFDIR = os.path.join(WS, "state", "face-guard")
CFG = os.path.join(SFDIR, "config.json")
DBP = os.path.join(WS, "state", "faces", "db.npz")
TMPD = os.path.join(SFDIR, "frames")
os.makedirs(TMPD, exist_ok=True)

DEFAULT_CFG = {
    "interval": 20,
    "owner_thr": 0.45,
    "stranger_thr": 0.35,
    "min_face_px": 60,
    "grace_stranger": 30,
    "grace_empty": 900,
    "lock_enabled": True,
    "notify": True,
    "paused": False,
}

_app = None
_PROV = ("CUDAExecutionProvider", "CPUExecutionProvider")

def cfg():
    c = dict(DEFAULT_CFG)
    if os.path.exists(CFG):
        try:
            c.update(json.load(open(CFG)))
        except Exception:
            pass
    return c

def save_cfg(c):
    os.makedirs(SFDIR, exist_ok=True)
    json.dump(c, open(CFG, "w"), ensure_ascii=False, indent=1)

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "%s %s" % (ts, msg)
    print(line, flush=True)
    with open(os.path.join(SFDIR, "guard.log"), "a") as f:
        f.write(line + "\n")

def app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name="antelopev2", providers=_PROV)
        _app.prepare(ctx_id=0 if _PROV[0].startswith("CUDA") else -1, det_size=(640, 640))
    return _app

def load_db():
    import numpy as np
    if os.path.exists(DBP):
        d = np.load(DBP, allow_pickle=True)
        return list(d["labels"]), d["samples"]
    return [], np.zeros((0, 512), dtype="float32")

def save_db(labels, samples):
    import numpy as np
    os.makedirs(os.path.dirname(DBP), exist_ok=True)
    np.savez(DBP, labels=np.array(labels), samples=samples)

def grab(out=None):
    out = out or os.path.join(TMPD, "now.jpg")
    r = subprocess.run(["bash", os.path.join(TOOLS, "cam.sh"), "shot", out],
                       capture_output=True, text=True, timeout=30)
    return out if (r.returncode == 0 and os.path.exists(out)) else None

def analyze(path):
    """返回 {faces:[{box,sim,label,px}], owner:bool, stranger:bool, brightness:float}"""
    import cv2, numpy as np
    img = cv2.imread(path)
    if img is None:
        return {"err": "unreadable"}
    bright = float(img.mean())
    labels, samples = load_db()
    res = {"brightness": round(bright, 1), "faces": [], "owner": False, "stranger": False}
    if bright < 4:
        res["dark"] = True
        return res
    try:
        faces = app().get(img)
    except Exception as e:
        res["err"] = "detect:%s" % e
        return res
    for f in faces:
        box = [int(x) for x in f.bbox]
        px = min(box[2] - box[0], box[3] - box[1])
        det = float(f.det_score)
        name, sim = "未知", 0.0
        if samples.shape[0] > 0:
            v = f.normed_embedding
            sims = samples @ v
            best = {}
            for lb, s in zip(labels, sims):
                if s > best.get(lb, -1):
                    best[lb] = float(s)
            if best:
                name, sim = max(best.items(), key=lambda kv: kv[1])
        res["faces"].append({"box": box, "px": px, "det": round(det, 2),
                             "label": name, "sim": round(sim, 3)})
    c = cfg()
    for f in res["faces"]:
        if f["px"] < c["min_face_px"] or f["det"] < 0.5:
            continue
        if f["sim"] >= c["owner_thr"]:
            res["owner"] = True
        elif f["sim"] < c["stranger_thr"]:
            res["stranger"] = True
    return res

_LIVE = os.path.join(SFDIR, "live.jpg")
LIVE = _LIVE
_proc = None
_latest = {"bytes": None, "ts": 0.0}
_started = False
_thread = None

def _reader(proc):
    import time as _t
    buf = b""
    while True:
        try:
            chunk = proc.stdout.read(65536)
        except Exception:
            break
        if not chunk:
            break
        buf += chunk
        while True:
            i = buf.find(b"\xff\xd8\xff")
            j = buf.find(b"\xff\xd9", i + 3) if i >= 0 else -1
            if i < 0 or j < 0:
                if len(buf) > 4_000_000:
                    buf = buf[-1_000_000:]
                break
            _latest["bytes"] = buf[i:j + 2]
            _latest["ts"] = _t.time()
            buf = buf[j + 2:]

def _kill_strays():
    subprocess.run(["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe","-NoProfile","-Command","Stop-Process -Name ffmpeg -Force -ErrorAction SilentlyContinue"], capture_output=True, timeout=30)

def stream_start():
    global _proc, _thread
    import threading
    ff = "/mnt/c/Users/J/AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"
    try:
        if _proc is not None and _proc.poll() is None:
            return
    except Exception:
        pass
    _kill_strays()
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-f", "dshow",
           "-rtbufsize", "64M", "-i", "video=Deli-4K-Camera",
           "-r", "3", "-q:v", "4", "-f", "mjpeg", "pipe:1"]
    try:
        _proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        _thread = threading.Thread(target=_reader, args=(_proc,), daemon=True)
        _thread.start()
        log("stream start pid=%s" % _proc.pid)
    except Exception as e:
        log("stream start fail: %r" % e)
        _proc = None

def stream_frame(max_age=40):
    """最新一帧落成文件返回路径；超过 max_age 则重启流"""
    import time as _t
    stream_start()
    for _ in range(25):
        if _latest["bytes"] and (_t.time() - _latest["ts"]) <= max_age:
            tmp = os.path.join(TMPD, "live.jpg")
            with open(tmp, "wb") as f:
                f.write(_latest["bytes"])
            return tmp
        _t.sleep(0.4)
    try:
        if _proc is not None and _proc.poll() is not None:
            log("stream exited rc=%s，重启" % _proc.returncode)
            stream_start()
    except Exception:
        pass
    return None

def notify(text, img=None):
    c = cfg()
    if not c["notify"]:
        return
    script = os.path.join(TOOLS, "notify.sh")
    try:
        if os.path.exists(script):
            subprocess.run(["bash", script, text], timeout=30,
                           capture_output=True, text=True)
    except Exception as e:
        log("notify fail: %s" % e)

def lock_screen():
    r = subprocess.run(["/mnt/c/Windows/System32/rundll32.exe", "user32.dll,LockWorkStation"],
                       capture_output=True, text=True, timeout=20)
    return r.returncode

def cmd_check(a):
    import time as _t
    live = os.path.join(TMPD, "live.jpg")
    if os.path.exists(live) and (_t.time() - os.path.getmtime(live)) < 60:
        print(json.dumps(analyze(live), ensure_ascii=False))
        return 0
    p = grab()
    if not p:
        print(json.dumps({"err": "nocam"}, ensure_ascii=False))
        return 2
    print(json.dumps(analyze(p), ensure_ascii=False))
    return 0

def cmd_enroll(a):
    import shutil
    saved = []
    for i in range(a.n):
        p = grab(os.path.join(TMPD, "enroll-%02d.jpg" % i))
        if not p:
            log("enroll 第 %d 张抓帧失败" % (i + 1)); time.sleep(1); continue
        r = analyze(p)
        ok = [f for f in r.get("faces", []) if f["px"] >= cfg()["min_face_px"]]
        log("enroll %d/%d 亮度%.1f 人脸%d 合格%d" % (i + 1, a.n, r.get("brightness", 0),
                                                   len(r.get("faces", [])), len(ok)))
        if ok:
            saved.append(p)
        time.sleep(0.6)
    if not saved:
        print("没有可用照片，检查灯光/位置")
        return 3
    labels, samples = load_db()
    import cv2, numpy as np
    labels = list(labels)
    vecs = []
    for p in saved:
        res = app().get(cv2.imread(p))
        cand = [f for f in res if min(f.bbox[2] - f.bbox[0], f.bbox[3] - f.bbox[1]) >= cfg()["min_face_px"]]
        if not cand:
            continue
        f = max(cand, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
        vecs.append(f.normed_embedding.astype("float32"))
        labels.append(a.name)
    if not vecs:
        print("embedding 失败")
        return 4
    samples = np.vstack([samples, np.array(vecs)]) if samples.shape[0] else np.array(vecs)
    save_db(labels, samples)
    for i, p in enumerate(saved):
        shutil.copy(p, os.path.join(SFDIR, "enroll-%s-%02d.jpg" % (a.name, i)))
    print(json.dumps({"name": a.name, "added": len(vecs), "total": len(labels)}, ensure_ascii=False))
    log("enroll %s 新增 %d 样本，库共 %d" % (a.name, len(vecs), len(labels)))
    return 0

def cmd_daemon(a):
    log("daemon start interval=%ss" % cfg()["interval"])
    absent_since = None
    stranger_since = None
    locked = False
    last_ask = 0.0
    while True:
        c = cfg()
        if c.get("paused"):
            time.sleep(max(5, c["interval"]))
            continue
        try:
            p = stream_frame() if c.get("stream", True) else grab()
            if not p:
                log("抓帧失败，跳过（不锁，避免误锁）")
                time.sleep(c["interval"]); continue
            r = analyze(p)
            if r.get("err") or r.get("dark"):
                log("画面不可用 %s，跳过" % (r.get("err") or "dark"))
                time.sleep(c["interval"]); continue
            now = time.time()

            # 1) 主公在，无陌生人 → 一切正常
            if r["owner"] and not r["stranger"]:
                if absent_since is not None:
                    log("主公回来了（离开 %.0fs）" % (now - absent_since))
                absent_since = None; stranger_since = None; locked = False
                time.sleep(c["interval"]); continue

            # 2) 主公在 + 有陌生人 → 只咨询，不自动锁
            if r["owner"] and r["stranger"]:
                absent_since = None; stranger_since = None
                if now - last_ask >= c.get("ask_cooldown", 600):
                    last_ask = now
                    log("主公与陌生人同框 → 发咨询")
                    notify("【要不要锁屏？】画面里有你 + 一位没识别出的人。回「锁」我立刻锁，不回就不动。", p)
                time.sleep(c["interval"]); continue

            # 3) 主公不在
            if absent_since is None:
                absent_since = now
                log("检测不到主公")
            absent = now - absent_since
            if r["stranger"]:
                if stranger_since is None:
                    stranger_since = now
                    log("检测到陌生人（主公不在）")
            else:
                stranger_since = None
            stranger_for = (now - stranger_since) if stranger_since else 0
            should = False; why = ""
            if stranger_since and stranger_for >= c["grace_stranger"] and absent >= c["grace_stranger"]:
                should, why = True, "陌生人停留%.0fs且主公不在%.0fs" % (stranger_for, absent)
            elif absent >= c["grace_empty"]:
                should, why = True, "无人%.0fs" % absent
            if should and c["lock_enabled"] and not locked:
                rc = lock_screen()
                locked = True
                log("LOCK rc=%s 原因：%s" % (rc, why))
                notify("【屏幕已锁】%s。本地判定，图像未上传。" % why, p)
            elif should and not c["lock_enabled"] and not locked:
                locked = True
                log("本应锁屏（%s），但 lock_enabled=false" % why)
        except Exception as e:
            log("loop error: %r" % e)
        time.sleep(cfg()["interval"])

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enroll"); e.add_argument("--name", required=True); e.add_argument("--n", type=int, default=8)
    sub.add_parser("check")
    sub.add_parser("daemon")
    s = sub.add_parser("config"); s.add_argument("--set", nargs="*")
    a = ap.parse_args()
    if a.cmd == "enroll":
        return cmd_enroll(a)
    if a.cmd == "check":
        return cmd_check(a)
    if a.cmd == "daemon":
        return cmd_daemon(a)
    if a.cmd == "config":
        c = cfg()
        for kv in (a.set or []):
            k, v = kv.split("=", 1)
            try: v = json.loads(v)
            except Exception: pass
            c[k] = v
        save_cfg(c)
        print(json.dumps(c, ensure_ascii=False))
        return 0

if __name__ == "__main__":
    sys.exit(main() or 0)

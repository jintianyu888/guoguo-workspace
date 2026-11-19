#!/usr/bin/env python3
"""voiceprint.py — 本地声纹核验（ECAPA-TDNN / speechbrain）
用法:
  voiceprint.py enroll <label> <音频...>      # 注册模板（多文件取均值+逐条保存）
  voiceprint.py score <label> <音频...>       # 与模板比对，输出相似度
  voiceprint.py eval <label> <音频...>        # 批量评估：分布/阈值建议
"""
import sys, os, json, argparse, pathlib
import numpy as np
import torch, torchaudio
from speechbrain.inference.speaker import EncoderClassifier

FFMPEG = os.environ.get("FFMPEG_BIN", "/home/j/.local/bin/ffmpeg")
CACHE = os.path.expanduser("~/.cache/spk")
VDIR = os.path.expanduser("/home/j/.openclaw/workspace/state/voiceprint")
os.makedirs(VDIR, exist_ok=True)

_clf = None
def clf():
    global _clf
    if _clf is None:
        _clf = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir=CACHE, run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"})
    return _clf

def _load16k(path):
    """用 ffmpeg 转 16k 单声道，再用 soundfile 读（torchaudio 2.11 需要 torchcodec，绕开）"""
    import subprocess, tempfile, soundfile as sf
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as t:
        tmp = t.name
    try:
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", tmp], check=True)
        data, sr = sf.read(tmp, dtype="float32")
    finally:
        try: os.unlink(tmp)
        except OSError: pass
    wav = torch.from_numpy(data).unsqueeze(0)
    return wav

def emb(path):
    wav = _load16k(path)
    if wav.shape[1] < 16000 * 3.0:
        raise ValueError("too short (<3s): %s" % path)
    e = clf().encode_batch(wav).detach().cpu().numpy().reshape(-1)
    return e / (np.linalg.norm(e) + 1e-9)

def tpath(label):
    return os.path.join(VDIR, label + ".npz")

def cmd_enroll(a):
    es = []
    for f in a.files:
        try:
            es.append(emb(f)); print("ok", os.path.basename(f))
        except Exception as ex:
            print("skip", os.path.basename(f), ex)
    if not es:
        print("ERR 没有可用音频"); return 2
    E = np.stack(es)
    m = E.mean(0); m /= (np.linalg.norm(m) + 1e-9)
    np.savez(tpath(a.label), mean=m, all=E)
    print("enrolled", a.label, "n=", len(es), "->", tpath(a.label))
    return 0

def cmd_score(a):
    d = np.load(tpath(a.label)); m = d["mean"]
    for f in a.files:
        s = float(np.dot(emb(f), m))
        print("%.4f  %s" % (s, os.path.basename(f)))
    return 0

def cmd_eval(a):
    d = np.load(tpath(a.label)); m = d["mean"]
    ss = []
    for f in a.files:
        try:
            ss.append(float(np.dot(emb(f), m)))
        except Exception:
            pass
    ss = np.array(ss)
    if len(ss) == 0:
        print("ERR 无有效音频"); return 2
    q = lambda p: float(np.percentile(ss, p))
    print(json.dumps({"n": len(ss), "min": round(ss.min(),4), "p5": round(q(5),4),
                      "median": round(float(np.median(ss)),4), "p95": round(q(95),4),
                      "max": round(ss.max(),4), "mean": round(float(ss.mean()),4)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["enroll", "score", "eval"])
    p.add_argument("label")
    p.add_argument("files", nargs="+")
    a = p.parse_args()
    sys.exit({"enroll": cmd_enroll, "score": cmd_score, "eval": cmd_eval}[a.cmd](a))

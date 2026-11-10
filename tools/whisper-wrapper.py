#!/usr/bin/env python3
"""whisper 兼容包装（基于 faster-whisper，CPU/int8，无需 PyTorch）。"""
import argparse, os, sys
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

ap = argparse.ArgumentParser(prog="whisper")
ap.add_argument("audio")
ap.add_argument("--model", default="/home/j/.openclaw/workspace/tools/models/faster-whisper-medium")
ap.add_argument("--output_format", default="txt", choices=["txt", "srt", "vtt"])
ap.add_argument("--output_dir", default=".")
ap.add_argument("--task", default="transcribe", choices=["transcribe", "translate"])
ap.add_argument("--language", default=None)
a = ap.parse_args()

if not os.path.isfile(a.audio):
    print(f"文件不存在: {a.audio}", file=sys.stderr); sys.exit(1)

# --- CUDA 库路径引导（2026-10-17）：nvidia pip 包装在 site-packages，动态库需进 LD_LIBRARY_PATH
_sp = os.path.dirname(os.path.abspath(__file__)) + "/asr-venv/lib"
import glob as _glob
_cands = _glob.glob(_sp + "/python*/site-packages/nvidia/*/lib") + ["/usr/lib/wsl/lib"]
_cands = [c for c in _cands if os.path.isdir(c)]
_need = ":".join(_cands)
if _cands and os.environ.get("_ASR_LD_BOOT") != "1":
    os.environ["_ASR_LD_BOOT"] = "1"
    os.environ["LD_LIBRARY_PATH"] = _need + (":" + os.environ["LD_LIBRARY_PATH"] if os.environ.get("LD_LIBRARY_PATH") else "")
    os.execv(sys.executable, [sys.executable] + sys.argv)

def _preload_cuda_libs():
    """预加载 venv 内的 CUDA 库到全局符号表（LD_LIBRARY_PATH 在进程启动后不再生效）。"""
    import glob, ctypes, sys as _s
    roots = glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "asr-venv", "lib", "python*", "site-packages", "nvidia", "*", "lib"))
    loaded = []
    for root in roots:
        for name in ("libcublas.so.12", "libcublasLt.so.12", "libcudnn.so.9", "libcudnn_ops.so.9"):
            f = os.path.join(root, name)
            if os.path.exists(f):
                try:
                    ctypes.CDLL(f, mode=ctypes.RTLD_GLOBAL); loaded.append(name)
                except OSError as e:
                    print("[asr] 预加载失败 %s: %s" % (name, e), file=_s.stderr)
    return loaded


_preload_cuda_libs()
from faster_whisper import WhisperModel
# 有 CUDA 就用 GPU（int8_float16），失败自动回落 CPU/int8
import os as _os
_dev = "cuda" if _os.environ.get("ASR_FORCE_CPU") != "1" else "cpu"
try:
    if _dev == "cuda":
        model = WhisperModel(a.model, device="cuda", compute_type="float16")
    else:
        model = WhisperModel(a.model, device="cpu", compute_type="int8")
except Exception as _e:
    # 2026-10-29 评审要求：回退必须结构化留痕（不只 stderr）
    try:
        import time as _t2
        _lp = "/home/j/.openclaw/workspace/state/asr/device.log"
        _os.makedirs(_os.path.dirname(_lp), exist_ok=True)
        with open(_lp, "a") as _f:
            _f.write("%s fallback=exception device=cpu model=%s err=%s\n" % (_t2.strftime("%F %T"), a.model.split("/")[-1], str(_e)[:80]))
    except Exception:
        pass
    # 2026-10-18：回落到 CPU 必须留痕，不再静默
    print("[asr] CUDA 不可用，回落 CPU/int8：%s: %s" % (type(_e).__name__, _e), file=sys.stderr)
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
try:
    segments, info = model.transcribe(a.audio, task=a.task, language=a.language)
except Exception as _e:
    # GPU 推理期失败（如 cublas 加载不到）→ 立刻回退 CPU，绝不让整条语音失败
    print(f"[asr] GPU 失败，回退 CPU: {type(_e).__name__}", file=sys.stderr)
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    segments, info = model.transcribe(a.audio, task=a.task, language=a.language)
segments = list(segments)
segs = list(segments)

def ts(t, sep=","):
    h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", sep)

os.makedirs(a.output_dir, exist_ok=True)
base = os.path.splitext(os.path.basename(a.audio))[0]

if a.output_format == "txt":
    out = os.path.join(a.output_dir, base + ".txt")
    with open(out, "w", encoding="utf-8") as fh:
        for s in segs:
            fh.write(s.text.strip() + "\n")
    print("\n".join(s.text.strip() for s in segs if s.text.strip()))
else:
    sep = "," if a.output_format == "srt" else "."
    out = os.path.join(a.output_dir, base + "." + a.output_format)
    with open(out, "w", encoding="utf-8") as fh:
        for i, s in enumerate(segs, 1):
            fh.write(f"{i}\n{ts(s.start, sep)} --> {ts(s.end, sep)}\n{s.text.strip()}\n\n")
    # 2026-10-28 验证环节：空结果自动重试，绝不把空文本交给上层
    segs = list(segs)
    def _txt(_ss):
        return chr(10).join(x.text.strip() for x in _ss if x.text.strip())
    _t = _txt(segs)
    if not _t.strip():
        print('[asr] 首次为空，关闭 VAD 重试', file=sys.stderr)
        try:
            _s2, _ = model.transcribe(a.audio, task=a.task, language=a.language, vad_filter=False)
            segs = list(_s2); _t = _txt(segs)
        except Exception as _e2:
            print('[asr] 关 VAD 重试失败: %s' % _e2, file=sys.stderr)
    if not _t.strip():
        print('[asr] 二次为空，换 base 模型重试', file=sys.stderr)
        try:
            _m2 = WhisperModel('/home/j/.openclaw/workspace/tools/models/faster-whisper-base', device='cpu', compute_type='int8')
            _s3, _ = _m2.transcribe(a.audio, task=a.task, language=a.language, vad_filter=False)
            segs = list(_s3); _t = _txt(segs)
        except Exception as _e3:
            print('[asr] base 重试失败: %s' % _e3, file=sys.stderr)
    if not _t.strip():
        print('[ASR_EMPTY] 语音转不出内容（静音或损坏），已记录待复核')
    if a.output_format == "txt":
        print("\n".join(s.text.strip() for s in segs if s.text.strip()))
    else:
        print(f"已写入 {out} （{len(segs)} 段）")

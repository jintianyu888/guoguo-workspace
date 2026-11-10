p = "/home/j/.openclaw/workspace/tools/ocr.py"
s = open(p).read()
old = "        from rapidocr_onnxruntime import RapidOCR\n        _engine = RapidOCR()"
new = """        from rapidocr_onnxruntime import RapidOCR
        # 2026-09-28 23:4x 主公令「优先用 GPU」：能用 CUDA 就用，失败自动回落 CPU
        _engine = None
        try:
            import onnxruntime as _ort
            if "CUDAExecutionProvider" in _ort.get_available_providers():
                try:
                    _engine = RapidOCR(use_cuda=True)
                except Exception:
                    try:
                        _engine = RapidOCR(det_use_cuda=True, cls_use_cuda=True, rec_use_cuda=True)
                    except Exception:
                        _engine = RapidOCR()
        except Exception:
            _engine = None
        if _engine is None:
            _engine = RapidOCR()"""
if "优先用 GPU" in s:
    print("already patched")
elif old in s:
    open(p, "w").write(s.replace(old, new, 1))
    print("patched OK")
else:
    print("anchor not found")
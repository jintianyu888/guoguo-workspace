#!/usr/bin/env python3
"""中文/英文 OCR（本地离线，RapidOCR + onnxruntime，模型随包内置，不联网）

支持输入：
  · 图片：.jpg .jpeg .png .webp .bmp .tif .tiff
  · PDF ：先用 pypdfium2 把每页渲染成图片，再逐页 OCR

用法：
  python3 ocr.py FILE [FILE...]                 # 打印文字
  python3 ocr.py FILE --json                    # JSON 输出（含每行置信度/坐标）
  python3 ocr.py FILE --output out.txt          # 写入文件
  python3 ocr.py FILE --dpi 300                 # PDF 渲染精度（默认 200）
  python3 ocr.py FILE --min-score 0.5           # 过滤低置信度行（默认 0.0 全保留）

说明：
  · 纯离线：模型在 rapidocr_onnxruntime/models/ 内（PP-OCRv4 中英文通用）。
  · 识别 PP-OCRv4 rec 模型为中英文混合字典，中英数字可同时识别。
"""
import argparse
import json
import os
import sys

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
PDF_EXT = {".pdf"}

_engine = None


def _preload_cuda_libs():
    """随 venv 自带的 CUDA13 运行库用 ctypes 预加载（RTLD_GLOBAL），
    让 onnxruntime 真正能用 CUDAExecutionProvider；任何失败都不影响 CPU 回退。"""
    if os.environ.get("OCR_FORCE_CPU"):
        return False
    import ctypes
    import glob
    nvidia = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "ocr-venv", "lib", "python3.14", "site-packages", "nvidia",
    )
    ok = False
    for sub in ("cu13", "cudnn"):
        libdir = os.path.join(nvidia, sub, "lib")
        for so in sorted(glob.glob(os.path.join(libdir, "*.so*"))):
            try:
                ctypes.CDLL(so, mode=ctypes.RTLD_GLOBAL)
                ok = True
            except OSError:
                pass
    return ok


def get_engine():
    """返回 RapidOCR 引擎：默认优先 GPU（CUDAExecutionProvider），
    不可用自动回退 CPU，绝不失败。置环境变量 OCR_FORCE_CPU=1 可强制 CPU（对比测试用）。"""
    global _engine
    if _engine is None:
        _preload_cuda_libs()
        from rapidocr_onnxruntime import RapidOCR
        if os.environ.get("OCR_FORCE_CPU"):
            import rapidocr_onnxruntime.utils as _u
            _u.get_device = lambda: "CPU"
        try:
            _engine = RapidOCR()
        except Exception:
            _engine = None
        if _engine is None:
            # CUDA 初始化异常 → 强制 CPU 重建（保证有结果）
            import rapidocr_onnxruntime.utils as _u
            _u.get_device = lambda: "CPU"
            _engine = RapidOCR()
    return _engine


def engine_provider():
    """返回当前引擎实际使用的执行提供器（CUDAExecutionProvider / CPUExecutionProvider）。"""
    e = get_engine()
    for name in ("text_recognizer", "text_detector", "text_cls"):
        obj = getattr(e, name, None)
        sess = getattr(obj, "session", None)
        inner = getattr(sess, "session", None) if sess is not None else None
        if inner is not None:
            try:
                return inner.get_providers()[0]
            except Exception:
                pass
    return "unknown"


def ocr_image(path, min_score=0.0):
    """返回 (lines, text) ；lines = [{text, score, box}]"""
    global _engine
    engine = get_engine()
    try:
        res, _elapse = engine(str(path))
    except Exception:
        # 运行期 CUDA 推理失败（如缺 cudnn）→ 强制 CPU 重建并重试一次，保证出结果
        os.environ["OCR_FORCE_CPU"] = "1"
        _engine = None
        engine = get_engine()
        res, _elapse = engine(str(path))
    lines = []
    for item in res or []:
        box, text, score = item[0], item[1], float(item[2])
        if score < min_score:
            continue
        lines.append({"text": text, "score": round(score, 4), "box": box})
    return lines, "\n".join(l["text"] for l in lines)


def pdf_pages_to_pil(path, dpi=200):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(path))
    try:
        scale = dpi / 72.0
        for i in range(len(pdf)):
            page = pdf[i]
            bitmap = page.render(scale=scale)
            yield i + 1, bitmap.to_pil()
            bitmap.close()
            page.close()
    finally:
        pdf.close()


def ocr_pdf(path, dpi=200, min_score=0.0):
    import numpy as np
    engine = get_engine()
    parts, pages = [], []
    for pno, pil in pdf_pages_to_pil(path, dpi=dpi):
        arr = np.array(pil.convert("RGB"))
        res, _elapse = engine(arr)
        lines = []
        for item in res or []:
            box, text, score = item[0], item[1], float(item[2])
            if score < min_score:
                continue
            lines.append({"text": text, "score": round(score, 4), "box": box})
        pages.append({"page": pno, "lines": lines})
        parts.append(f"--- 第 {pno} 页 ---\n" + "\n".join(l["text"] for l in lines))
    return pages, "\n".join(parts)


def process(path, dpi=200, min_score=0.0):
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF_EXT:
        pages, text = ocr_pdf(path, dpi=dpi, min_score=min_score)
        return {"kind": "pdf", "pages": pages, "text": text, "chars": len(text)}
    if ext in IMG_EXT:
        lines, text = ocr_image(path, min_score=min_score)
        return {"kind": "image", "lines": lines, "text": text, "chars": len(text)}
    return {"error": f"不支持的格式 {ext}（支持图片 {sorted(IMG_EXT)} 与 PDF）"}


def main():
    ap = argparse.ArgumentParser(description="中文/英文离线 OCR（图片 + PDF）")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true", help="输出 JSON（含置信度与坐标）")
    ap.add_argument("--output", "-o", help="把识别文本写入指定文件")
    ap.add_argument("--dpi", type=int, default=200, help="PDF 渲染 DPI（默认 200）")
    ap.add_argument("--min-score", type=float, default=0.0, help="过滤低于此置信度的行")
    a = ap.parse_args()

    result = {}
    for path in a.files:
        if not os.path.isfile(path):
            result[path] = {"error": "文件不存在"}
            continue
        try:
            result[path] = process(path, dpi=a.dpi, min_score=a.min_score)
        except Exception as e:
            result[path] = {"error": f"{type(e).__name__}: {e}"}

    if a.output:
        with open(a.output, "w", encoding="utf-8") as fh:
            for path, v in result.items():
                fh.write(f"===== {os.path.basename(path)} =====\n")
                fh.write((v.get("text") or f"[错误] {v.get('error')}") + "\n\n")
        print(f"已写入 {a.output}", file=sys.stderr)

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not a.output:
        for path, v in result.items():
            print(f"===== {os.path.basename(path)} =====")
            print(v.get("text") or f"[错误] {v.get('error')}")
            print()


if __name__ == "__main__":
    main()

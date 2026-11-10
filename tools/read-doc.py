#!/usr/bin/env python3
"""读取文档正文（本地解析，不联网）：
  PDF · Word(.docx/.doc) · Excel(.xlsx/.xlsm/.xls) · PPT(.pptx/.ppt)
  · CSV · 纯文本(.txt/.md/.json)

用法：
  python3 read-doc.py FILE [FILE...] [--max-chars N] [--json]

说明：
  - PDF 优先用 pdfplumber（保留排版、支持表格），失败则退回 pypdf。
  - Word 读正文段落 + 表格；Excel 读所有工作表（公式取计算值）。
  - 老版 .doc/.xls/.ppt 先由用户级 LibreOffice 转成 .docx/.xlsx/.pptx
    再读（见 tools/soffice-lo），临时目录用完即删。
  - 扫描件（图片型 PDF）**读不出文字**，请改用 tools/ocr.py。
"""
import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
import re as _re


def read_pdf(path):
    try:
        import pdfplumber
        chunks = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                txt = (page.extract_text() or "").strip()
                tbls = []
                try:
                    for t in page.extract_tables() or []:
                        rows = [" | ".join((c or "").strip() for c in row) for row in t if row]
                        if rows:
                            tbls.append("\n".join(rows))
                except Exception:
                    pass
                body = txt
                if tbls:
                    body += "\n[表格]\n" + "\n".join(tbls)
                chunks.append(f"--- 第 {i} 页 ---\n{body}")
        return "\n".join(chunks)
    except Exception:
        from pypdf import PdfReader
        r = PdfReader(path)
        return "\n".join((pg.extract_text() or "") for pg in r.pages)


def read_docx(path):
    from docx import Document
    d = Document(path)
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for t in d.tables:
        for row in t.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(parts)


def read_xlsx(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"--- 工作表: {ws.title} ---")
        for row in ws.iter_rows(values_only=True):
            if any(c is not None and str(c).strip() for c in row):
                out.append(" | ".join("" if c is None else str(c) for c in row))
    return "\n".join(out)


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel
        return "\n".join(" | ".join(r) for r in csv.reader(fh, dialect))


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def read_pptx(path):
    """从 pptx/pptx-zip 里抽文字（无需 python-pptx 依赖）。"""
    out = []
    with zipfile.ZipFile(path) as z:
        slides = sorted(
            (n for n in z.namelist()
             if _re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=lambda n: int(_re.search(r"(\d+)", n.split("/")[-1]).group(1)),
        )
        for i, name in enumerate(slides, 1):
            xml = z.read(name).decode("utf-8", "replace")
            texts = _re.findall(r"<a:t>(.*?)</a:t>", xml, _re.S)
            texts = [t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()
                     for t in texts]
            body = "\n".join(t for t in texts if t)
            out.append(f"--- 第 {i} 张幻灯片 ---\n{body}")
    return "\n".join(out)


READERS = {
    ".pdf": read_pdf,
    ".docx": read_docx,
    ".xlsx": read_xlsx,
    ".xlsm": read_xlsx,
    ".pptx": read_pptx,
    ".csv": read_csv,
    ".tsv": read_csv,
    ".txt": read_text,
    ".md": read_text,
    ".json": read_text,
}

# 老版二进制格式 -> 目标现代格式（用用户级 LibreOffice 转换）
LEGACY = {".doc": ".docx", ".xls": ".xlsx", ".ppt": ".pptx"}
SOFFICE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soffice-lo")


def convert_legacy(path):
    """把 .doc/.xls/.ppt 转成现代格式，返回 (临时文件路径, 临时目录)。"""
    ext = os.path.splitext(path)[1].lower()
    target = LEGACY[ext].lstrip(".")
    if not os.path.isfile(SOFFICE):
        raise RuntimeError(f"缺少转换器 {SOFFICE}（用户级 LibreOffice）")
    tmpdir = tempfile.mkdtemp(prefix="read-doc-conv-")
    try:
        p = subprocess.run(
            [SOFFICE, "--headless", "--convert-to", target, "--outdir", tmpdir, path],
            capture_output=True, text=True, timeout=240,
        )
        out = os.path.join(tmpdir, os.path.splitext(os.path.basename(path))[0] + LEGACY[ext])
        if not os.path.isfile(out):
            msg = ((p.stdout or "") + (p.stderr or "")).strip().replace("\n", " ")[:400]
            raise RuntimeError(f"LibreOffice 转换失败: {msg or '无输出'}")
        return out, tmpdir
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def main():
    ap = argparse.ArgumentParser(description="读取文档正文")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--max-chars", type=int, default=0, help="截断长度（0=不截断）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    result = {}
    for args_path in a.files:
        path = args_path
        ext = os.path.splitext(path)[1].lower()
        if not os.path.isfile(path):
            result[args_path] = {"error": "文件不存在"}
            continue
        tmpdir = None
        try:
            if ext in LEGACY:
                path, tmpdir = convert_legacy(path)
                ext = os.path.splitext(path)[1].lower()
            fn = READERS.get(ext)
            if not fn:
                result[args_path] = {"error": f"不支持的格式 {ext}"}
                continue
            text = fn(path)
            if a.max_chars and len(text) > a.max_chars:
                text = text[:a.max_chars] + f"\n…（已截断，共 {len(text)} 字）"
            result[args_path] = {"text": text, "chars": len(text)}
        except Exception as e:
            result[args_path] = {"error": f"{type(e).__name__}: {e}"}
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for path, v in result.items():
            print(f"===== {os.path.basename(path)} =====")
            print(v.get("text") or f"[错误] {v.get('error')}")
            print()


if __name__ == "__main__":
    main()

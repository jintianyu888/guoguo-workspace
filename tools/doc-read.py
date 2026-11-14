#!/usr/bin/env python3
"""doc-read.py — 无依赖读取 Office/PDF 文本（零 token，所有管家可用）
用法:
  doc-read.py 文件 [--max-chars 20000] [--sheets all|0,2] [--tables]
支持: .docx .xlsx .pptx .odt .ods .pdf(走 pdftotext) .htm(l) .txt/.csv/.md
原理: docx/xlsx/pptx/odt 本质是 zip+XML，用标准库直接解析，不装第三方包。
"""
import sys, os, re, zipfile, subprocess, argparse
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def docx_text(path):
    out = []
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    root = ET.fromstring(xml)
    for p in root.iter(W + "p"):
        line = "".join(t.text or "" for t in p.iter(W + "t"))
        if line.strip():
            out.append(line)
        elif p.find(".//" + W + "br") is not None:
            out.append("")
    return "\n".join(out)


def xlsx_text(path, sheets=None):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            r = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in r.iter(S + "si"):
                shared.append("".join(t.text or "" for t in si.iter(S + "t")))
        book = ""
        try:
            wb = ET.fromstring(z.read("xl/workbook.xml"))
            book = ", ".join(x.get("name") or "" for x in wb.iter(S + "sheet"))
        except Exception:
            pass
        out = []
        if book:
            out.append("[工作表] " + book)
        sheet_files = sorted(n for n in names if re.match(r"^xl/worksheets/sheet[0-9]+\.xml$", n))
        if sheets and sheets != "all":
            keep = {int(x) - 1 for x in sheets.split(",") if x.strip().isdigit()}
            sheet_files = [f for i, f in enumerate(sheet_files) if i in keep]
        for f in sheet_files:
            out.append("")
            out.append("=== " + f.split("/")[-1] + " ===")
            root = ET.fromstring(z.read(f))
            for row in root.iter(S + "row"):
                cells = []
                for c in row.iter(S + "c"):
                    t = c.get("t")
                    v = c.find(S + "v")
                    if t == "s" and v is not None:
                        try:
                            cells.append(shared[int(v.text)])
                        except Exception:
                            cells.append("")
                    elif t == "inlineStr":
                        cells.append("".join(x.text or "" for x in c.iter(S + "t")))
                    else:
                        cells.append(v.text if v is not None else "")
                if any(x.strip() for x in cells if x):
                    out.append(" | ".join(cells))
    return "\n".join(out)


def pptx_text(path):
    out = []
    with zipfile.ZipFile(path) as z:
        slides = sorted(n for n in z.namelist() if re.match(r"^ppt/slides/slide[0-9]+\.xml$", n))
        for i, s in enumerate(slides, 1):
            root = ET.fromstring(z.read(s))
            txt = [t.text for t in root.iter(A + "t") if t.text and t.text.strip()]
            out.append("[第%d页] %s" % (i, " / ".join(txt)))
    return "\n".join(out)


def odf_text(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("content.xml"))
    return "\n".join(t.text or "" for t in root.iter() if t.tag.endswith("}p") and (t.text or "").strip())


def pdf_text(path):
    try:
        r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
        return "[pdftotext 无文本输出，可能是扫描件，需要 OCR]"
    except Exception as e:
        return "[PDF 读取失败: %s]" % e


def plain(path):
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return "[无法解码]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--max-chars", type=int, default=20000)
    ap.add_argument("--sheets", default="all")
    a = ap.parse_args()
    p = a.path
    if not os.path.exists(p):
        print("[文件不存在] " + p); sys.exit(2)
    ext = os.path.splitext(p)[1].lower()
    try:
        if ext == ".docx":
            txt = docx_text(p)
        elif ext in (".xlsx", ".xlsm"):
            txt = xlsx_text(p, a.sheets)
        elif ext == ".pptx":
            txt = pptx_text(p)
        elif ext in (".odt", ".ods", ".odp"):
            txt = odf_text(p)
        elif ext == ".pdf":
            txt = pdf_text(p)
        elif ext in (".doc", ".xls", ".ppt"):
            print("[老格式 %s] 请先转存为 docx/xlsx/pptx，或用 antiword/libreoffice" % ext); sys.exit(3)
        else:
            txt = plain(p)
    except zipfile.BadZipFile:
        print("[坏文件] 不是有效 zip 容器（可能损坏或改过后缀）"); sys.exit(4)
    except Exception as e:
        print("[解析失败] %s: %s" % (type(e).__name__, e)); sys.exit(5)
    txt = txt.strip()
    print("[字符数] %d" % len(txt))
    print(txt[: a.max_chars])


if __name__ == "__main__":
    main()

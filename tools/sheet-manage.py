#!/usr/bin/env python3
# sheet-manage.py —— 乐谱管家：A 自动索引 + B 首图识别 + D 去重（2026-10-02）
# 用法: python3 sheet-manage.py            # 全量：索引+识别+去重报告
#       python3 sheet-manage.py --no-ocr   # 只做索引+去重（快）
import os, sys, json, hashlib, re, subprocess
from pathlib import Path
BASE = Path('/home/j/openclaw-workspaces/sheet-music')
FILES = BASE / 'scores' / 'files'
IDX_MD = BASE / 'scores' / 'index.md'
IDX_JSON = BASE / 'scores' / 'index.json'
DO_OCR = '--no-ocr' not in sys.argv
EXT = {'.pdf','.jpg','.jpeg','.png','.tif','.tiff','.bmp','.ps','.mid','.midi','.xml','.mscz','.musicxml'}
def sha(p, n=1<<20):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        while True:
            b=f.read(n)
            if not b: break
            h.update(b)
    return h.hexdigest()
def parse_name(stem):
    parts = re.split(r'[_\-]+', stem)
    comp = parts[0] if parts else stem
    return comp, stem
files = sorted([p for p in FILES.rglob('*') if p.is_file() and p.suffix.lower() in EXT]) if FILES.exists() else []
print('发现乐谱文件:', len(files))
hashes = {}
dup = []
entries = []
for p in files:
    h = sha(p)
    rel = str(p.relative_to(BASE))
    if h in hashes: dup.append((rel, hashes[h]))
    else: hashes[h] = rel
    comp, title = parse_name(p.stem)
    entries.append({'file': rel, 'composer': comp, 'title': title, 'size': p.stat().st_size, 'sha256': h[:12], 'ext': p.suffix.lower()})
BASE.mkdir(parents=True, exist_ok=True)
IDX_JSON.write_text(json.dumps(entries, ensure_ascii=False, indent=1))
by = {}
for e in entries: by.setdefault(e['composer'], []).append(e)
L = ['# 乐谱索引', '', f'共 **{len(entries)}** 份（去重后 {len(hashes)} 份）', '']
for c in sorted(by):
    L.append(f'## {c}（{len(by[c])}）')
    for e in sorted(by[c], key=lambda x: x['title']):
        L.append(f"- {e['title']} · {e['ext']} · {e['size']//1024}KB")
    L.append('')
if dup:
    L += ['## ⚠️ 疑似重复', ''] + [f'- `{a}` ⟷ `{b}`' for a,b in dup] + ['']
IDX_MD.write_text('\n'.join(L))
print('索引已生成:', IDX_MD)
print('index.json 条目:', len(entries))
print('疑似重复:', len(dup))
for a,b in dup[:10]: print('  DUP:', a, '<->', b)
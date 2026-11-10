#!/usr/bin/env python3
"""打包交付给老板：zip 打包 + 超限自动分卷 + 清单
用法: pack.py --out <输出名> [--limit-mb 20] <文件或目录...>"""
import os, sys, zipfile, argparse
ap = argparse.ArgumentParser()
ap.add_argument('--out', required=True)
ap.add_argument('--limit-mb', type=float, default=20.0)
ap.add_argument('files', nargs='+')
a = ap.parse_args()
LIMIT = int(a.limit_mb * 1024 * 1024)
def collect(p):
    if os.path.isfile(p): return [p]
    out = []
    for root, _, fs in os.walk(p):
        for f in fs:
            if f.startswith('.'): continue
            out.append(os.path.join(root, f))
    return out
items = []
for p in a.files: items += collect(p)
total = sum(os.path.getsize(i) for i in items)
print(f'📦 待打包 {len(items)} 个文件 · 合计 {total/1024/1024:.1f} MB · 单包上限 {a.limit_mb} MB')
part = 1; cur = []; cursz = 0; made = []
def flush(part, cur, cursz):
    if not cur: return
    name = f'{a.out}.zip' if part == 1 else f'{a.out}.part{part}.zip'
    with zipfile.ZipFile(name, 'w', zipfile.ZIP_STORED) as z:  # 仅存储：图片/PDF 已压缩，再压无益
        for f, arc in cur: z.write(f, arc)
    print(f'   ✅ {os.path.basename(name)}  ({os.path.getsize(name)/1024/1024:.1f} MB, {len(cur)} 个文件)')
    made.append(name)
for f in items:
    s = os.path.getsize(f)
    if cur and cursz + s > LIMIT:
        flush(part, cur, cursz); part += 1; cur = []; cursz = 0
    base = os.path.basename(a.files[0]) if len(a.files) == 1 else ''
    arc = os.path.relpath(f, os.path.dirname(a.files[0])) if len(a.files) == 1 else os.path.basename(f)
    cur.append((f, arc)); cursz += s
flush(part, cur, cursz)
if len(made) > 1: print(f'⚠️ 超过单包上限 → 已分 {len(made)} 卷，逐个发即可')
print('交付文件:', ' '.join(os.path.basename(m) for m in made))

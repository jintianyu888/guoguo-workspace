#!/usr/bin/env python3
# unzip-zip.py —— 通用解压（自动修正中文文件名编码）2026-10-03
# 用法: unzip-zip.py <zip文件> <输出目录>
# 处理：ZIP 里「UTF-8 字节但未打 UTF-8 标记」的中文名（cp437→utf-8/gbk 回退）
import sys, os, zipfile, shutil
def main():
    if len(sys.argv) < 3:
        print('用法: unzip-zip.py <zip文件> <输出目录>'); return 2
    z, d = sys.argv[1], sys.argv[2]
    if not os.path.isfile(z): print('找不到文件:', z); return 1
    os.makedirs(d, exist_ok=True)
    n_ok = 0
    with zipfile.ZipFile(z) as zf:
        for i in zf.infolist():
            if i.is_dir(): continue
            n = i.filename
            if not (i.flag_bits & 0x800):
                for enc in ('utf-8','gbk'):
                    try: n = n.encode('cp437').decode(enc); break
                    except Exception: pass
            p = os.path.join(d, n)
            os.makedirs(os.path.dirname(p) or d, exist_ok=True)
            with zf.open(i) as s, open(p,'wb') as t: shutil.copyfileobj(s,t)
            print(f'{os.path.getsize(p)}\t{p}'); n_ok += 1
    print(f'共解出 {n_ok} 个文件 -> {d}')
    return 0
sys.exit(main())
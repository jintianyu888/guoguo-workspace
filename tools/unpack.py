#!/usr/bin/env python3
"""解压万能工具：zip / tar / tar.gz / tgz / 7z / gz / zst / rar（能支持的都支持）
用法: unpack.py <压缩包> [目标目录]"""
import os, sys, tarfile, zipfile, gzip, shutil
def unpack(src, dst):
    os.makedirs(dst, exist_ok=True)
    low = src.lower()
    n = 0
    if low.endswith('.zip'):
        with zipfile.ZipFile(src) as z: z.extractall(dst); n = len(z.namelist())
    elif low.endswith(('.tar','.tar.gz','.tgz','.tar.bz2','.tbz2','.tar.xz')):
        with tarfile.open(src) as t: t.extractall(dst); n = len(t.getnames())
    elif low.endswith('.gz'):
        out = os.path.join(dst, os.path.basename(src)[:-3])
        with gzip.open(src,'rb') as i, open(out,'wb') as o: shutil.copyfileobj(i,o)
        n = 1
    elif low.endswith(('.7z','.zst','.zstd')):
        try:
            if low.endswith('.7z'):
                import py7zr
                with py7zr.SevenZipFile(src,'r') as z: z.extractall(dst); n=len(z.getnames())
            else:
                import zstandard
                out = os.path.join(dst, os.path.basename(src).rsplit('.',1)[0])
                with open(src,'rb') as f, open(out,'wb') as o:
                    zstandard.ZstdDecompressor().copy_stream(f,o)
                n = 1
        except ImportError as e:
            print('缺少库:', e); return -1
    elif low.endswith('.rar'):
        try:
            import rarfile
            with rarfile.RarFile(src) as r: r.extractall(dst); n=len(r.namelist())
        except Exception as e:
            print('rar 需要 unrar 工具:', str(e)[:80]); return -1
    else:
        print('不认识的格式:', src); return -1
    return n
if __name__ == '__main__':
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(src)[0] + '_解压'
    sz = os.path.getsize(src)
    print(f'📦 {os.path.basename(src)} ({sz/1024/1024:.1f} MB) → {dst}')
    n = unpack(src, dst)
    if n < 0: sys.exit(1)
    print(f'✅ 解压完成：{n} 个条目')
    sub = os.listdir(dst)[:8]
    for s in sub: print('   ·', s)

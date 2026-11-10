#!/usr/bin/env python3
"""multi-dl.py v2 —— 多连接分段下载 + 断点续传（已完成的段直接跳过）"""
import os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

def head_size(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Length", 0))

def get_range(args):
    url, start, end, path = args
    need = end - start + 1
    if os.path.exists(path) and os.path.getsize(path) == need:
        return True   # 已有完整分段 → 跳过（断点续传）
    for _ in range(12):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=%d-%d" % (start, end)})
            with urllib.request.urlopen(req, timeout=180) as r:
                data = r.read()
            if len(data) == need:
                open(path, "wb").write(data)
                return True
        except Exception:
            pass
        time.sleep(2)
    return False

def main(url, out, parts=16):
    size = head_size(url)
    chunk = size // parts
    tasks = []
    for i in range(parts):
        s = i * chunk
        e = size - 1 if i == parts - 1 else s + chunk - 1
        tasks.append((url, s, e, "%s.part%d" % (out, i)))
    have = sum(1 for t in tasks if os.path.exists(t[3]) and os.path.getsize(t[3]) == (t[2] - t[1] + 1))
    print("大小 %.1f MB | %d 段 | 已有 %d 段" % (size / 1048576.0, parts, have))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=parts) as ex:
        ok = sum(1 for r in ex.map(get_range, tasks) if r)
    print("完成 %d/%d 段 | 本轮耗时 %.1fs" % (ok, parts, time.time() - t0))
    if ok != parts:
        return 1
    with open(out, "wb") as fo:
        for i in range(parts):
            p = "%s.part%d" % (out, i)
            fo.write(open(p, "rb").read())
            os.remove(p)
    print("拼接完成:", out, "%.1f MB" % (os.path.getsize(out) / 1048576.0))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 16))
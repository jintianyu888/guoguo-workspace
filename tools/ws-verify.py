#!/usr/bin/env python3
"""ws-verify.py SRC DST —— 逐目录比对文件数与总字节数，不一致则 rc=1"""
import os, sys
src, dst = sys.argv[1], sys.argv[2]
def stat(d):
    n = 0; b = 0
    for dp, dn, fn in os.walk(d):
        for f in fn:
            p = os.path.join(dp, f)
            try:
                if os.path.isfile(p) and not os.path.islink(p):
                    n += 1; b += os.path.getsize(p)
            except OSError:
                pass
    return n, b

def links(d):
    n = 0
    for dp, dn, fn in os.walk(d):
        for f in fn + dn:
            if os.path.islink(os.path.join(dp, f)):
                n += 1
    return n
bad = 0
for name in sorted(os.listdir(src)):
    s = os.path.join(src, name)
    if not os.path.isdir(s): continue
    t = os.path.join(dst, name)
    if not os.path.isdir(t):
        print("MISSING", name); bad += 1; continue
    a = stat(s); c = stat(t)
    la, lc = links(s), links(t)
    if la != lc: print("SYMLINK-DIFF", name, la, lc); bad += 1
    if a != c:
        print("MISMATCH", name, "files", a[0], c[0], "bytes", a[1], c[1]); bad += 1
print("BAD", bad)
sys.exit(1 if bad else 0)
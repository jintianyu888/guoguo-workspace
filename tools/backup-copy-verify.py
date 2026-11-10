#!/usr/bin/env python3
# backup-copy-verify.py —— 每日备份副本比对（2026-10-21 主公要求纳入日常）
# 比对 D/E/H 三处备份包：同名 + 同大小 + 头尾抽样 SHA256；缺份/不一致即告警
# 只读，不删任何文件；退出码恒为 0（告警走 notify.sh）
import hashlib, os, subprocess, sys, time

D = "/mnt/d/openclaw-backups"
E = "/mnt/e/openclaw-backups"
H = "/mnt/h/openclaw-backups"
OUT = "/home/j/.openclaw/workspace/state/backup-verify"
SAMPLE = 32 * 1024 * 1024

def sample_hash(p):
    h = hashlib.sha256(); sz = os.path.getsize(p)
    with open(p, "rb") as f: h.update(f.read(SAMPLE))
    if sz > SAMPLE * 2:
        with open(p, "rb") as f:
            f.seek(-SAMPLE, os.SEEK_END); h.update(f.read(SAMPLE))
    return h.hexdigest()

def index(root):
    idx = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if f.endswith(".tar.gz"):
                p = os.path.join(dp, f)
                try: idx.setdefault(f, []).append((p, os.path.getsize(p)))
                except OSError: pass
    return idx

def main():
    os.makedirs(OUT, exist_ok=True)
    day = time.strftime("%Y%m%d")
    lines, bad = [], []
    di, ei, hi = index(D), index(E), index(H)
    for name, cands in sorted(di.items()):
        p, sz = cands[0]
        dh = sample_hash(p)
        for other, idx in (("E", ei), ("H", hi)):
            m = [c for c in idx.get(name, []) if c[1] == sz]
            if not m:
                bad.append("%s 在 %s 缺失/大小不符" % (name, other))
                lines.append("✗ %s | %s 缺失或大小不符" % (name, other)); continue
            if any(sample_hash(c[0]) == dh for c in m):
                lines.append("✓ %s | %s 一致 (%.1fG)" % (name, other, sz/1024**3))
            else:
                bad.append("%s 在 %s 哈希不一致" % (name, other))
                lines.append("✗ %s | %s 哈希不一致" % (name, other))
    path = os.path.join(OUT, day + ".md")
    with open(path, "w") as f:
        f.write("# 备份副本比对 %s\n\n" % time.strftime("%F %T"))
        f.write("\n".join(lines) + "\n\n")
        f.write("结论：%s\n" % ("✅ 全部一致" if not bad else "⚠️ 问题 %d 项" % len(bad)))
    print("报告:", path)
    print("问题:", 0 if not bad else len(bad))
    if bad:
        msg = "备份副本比对异常 %d 项：%s" % (len(bad), "；".join(bad[:5]))
        subprocess.run(["bash", "/home/j/.openclaw/workspace/tools/notify.sh", msg], timeout=120)

main()

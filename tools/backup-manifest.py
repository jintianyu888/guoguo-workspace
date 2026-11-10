#!/usr/bin/env python3
"""备份清单：写时/入库后算 SHA-256，落 manifest.jsonl（名+大小+哈希+mtime）。
增量：已缓存的哈希直接复用；大小或 mtime 变化则重算；每算完一份立即落盘。"""
import os, sys, json, hashlib, time, argparse

CACHE_DIRS = ["/home/j/.openclaw/workspace/state/backups-hash"]

def sha256_dd(p):
    # 9p/drvfs 上大文件 open/read 会 ENOMEM（2026-11-10 实测 117G 归档），退回 dd 流式
    import subprocess
    try:
        p1 = subprocess.Popen(['dd', 'if=' + p, 'bs=16M'], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
        p2 = subprocess.Popen(['sha256sum'], stdin=p1.stdout, stdout=subprocess.PIPE)
        p1.stdout.close()
        out = p2.communicate()[0].decode().split()
        return out[0] if out and len(out[0]) == 64 else None
    except Exception:
        return None


def sha256(p, bs=4*1024*1024):
    try:
        return _sha256_file(p, bs)
    except (MemoryError, OSError) as e:
        if isinstance(e, OSError) and getattr(e, 'errno', None) != 12:
            raise
        v = sha256_dd(p)
        if v:
            return v
        raise


def _sha256_file(p, bs=4*1024*1024):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(bs)
            if not b: break
            h.update(b)
    return h.hexdigest()

def cached(name):
    for d in CACHE_DIRS:
        f = os.path.join(d, name + ".sha256")
        if os.path.isfile(f) and os.path.getsize(f) >= 64:
            try:
                v = open(f, encoding="utf-8", errors="ignore").read().split()[0]
                if len(v) == 64: return v
            except Exception: pass
    return None

def flush(out, rows):
    tmp = out + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, out)
    except Exception:
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pattern", default=".tar.gz")
    ap.add_argument("--max-minutes", type=int, default=90)
    a = ap.parse_args()
    root = a.root; t0 = time.time()
    out = os.path.join(root, "manifest.jsonl")
    files = sorted(f for f in os.listdir(root) if f.endswith(a.pattern))
    cache = {}
    if os.path.isfile(out):
        for line in open(out, encoding="utf-8", errors="ignore"):
            try:
                r = json.loads(line); cache[r["name"]] = r
            except Exception: pass
    rows, hashed, reused, skipped, failed = [], 0, 0, 0, 0
    for n in files:
        p = os.path.join(root, n)
        try: st = os.stat(p)
        except OSError: continue
        prev = cache.get(n)
        mt = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))
        if prev and prev.get("size") == st.st_size and prev.get("mtime") == mt and len(prev.get("sha256", "")) == 64:
            rows.append(prev); reused += 1; continue
        h = cached(n)
        if h:
            reused += 1
        else:
            if (time.time() - t0) / 60 > a.max_minutes:
                skipped += 1
                prev2 = prev if prev and len(prev.get("sha256", "")) == 64 else None
                if prev2: rows.append(prev2)
                continue
            try:
                h = sha256(p); hashed += 1
            except OSError as e:
                # 单文件读失败（网络盘 I/O 错误/临时消失）不应中断整盘清单
                failed += 1
                print(f"WARN 跳过不可读文件 {n}: {e}", flush=True)
                continue
        rows.append({"name": n, "size": st.st_size, "sha256": h, "mtime": mt})
        if hashed and hashed % 1 == 0:
            flush(out, rows)
    flush(out, rows)
    print(f"{root}: 共 {len(rows)} 条｜新算 {hashed}｜复用 {reused}｜超时跳过 {skipped}｜读失败 {failed}｜-> {out}")
    if failed:
        # 双审（kimi-k3.1-pro + MiniMax-M3.1）一致要求：清单不完整不得静默成功
        print(f"ERROR 清单不完整：读失败 {failed} 个文件", file=sys.stderr, flush=True)
        sys.exit(3)

if __name__ == "__main__":
    main()
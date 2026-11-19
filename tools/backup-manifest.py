#!/usr/bin/env python3
"""备份清单：写时/入库后算 SHA-256，落 manifest.jsonl（名+大小+哈希+mtime）。
增量：已缓存的哈希直接复用；大小或 mtime 变化则重算；每算完一份立即落盘。"""
import os, sys, json, hashlib, time, argparse

CACHE_DIRS = ["/home/j/.openclaw/workspace/state/backups-hash"]

# 2026-11-11（账本 #978）：/mnt/h 上 60-120G 归档在 9p/drvfs 上全量哈希需 2 小时+，
# 远超单盘 30 分钟上限，旧逻辑只能「超时跳过」→ 新归档永远进不了清单。
# 对策：超过阈值的文件只算「头+尾各 N MB + size」的分片指纹，记录标 partial=true，
# 校验语义明确区分（partial 不能当全量哈希用），秒级完成、清单不再缺失。
PARTIAL_MIN_BYTES = 15 * 1024**3        # 默认 15G 以上走分片指纹
PARTIAL_CHUNK = 64 * 1024 * 1024        # 头/尾各读 64MB


def sha256_span(p, off, n):
    """读 [off, off+n) 的 sha256；优先 dd 按字节精确跳读（9p 大文件 open/read 会 ENOMEM）。"""
    import subprocess
    try:
        p1 = subprocess.Popen(['dd', 'if=' + p, 'bs=1M', 'skip=%d' % off,
                               'count=%d' % n, 'iflag=skip_bytes,count_bytes'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out = p1.communicate()[0]
        if p1.returncode == 0 and out:
            return hashlib.sha256(out[:n]).hexdigest()
    except Exception:
        pass
    h = hashlib.sha256()
    with open(p, "rb") as f:
        f.seek(off)
        left = n
        while left > 0:
            b = f.read(min(4 * 1024 * 1024, left))
            if not b: break
            h.update(b); left -= len(b)
    return h.hexdigest()


PARTIAL_METHOD = "sampled-v2"   # 头/中/尾三段采样；方法或 chunk 变更即重算


def partial_fp(p, size, chunk=PARTIAL_CHUNK):
    """大文件分片指纹：size + 头/中/尾各 chunk（双审 2026-11-11 要求加中段采样）。"""
    n = min(chunk, size)
    spans = [(0, n), (max(0, size // 2 - n // 2), n), (max(0, size - chunk), n)]
    digests = [sha256_span(p, off, ln) for off, ln in spans]
    h = hashlib.sha256()
    h.update(("size=%d;chunk=%d;method=%s;" % (size, chunk, PARTIAL_METHOD)).encode())
    h.update("|".join(digests).encode())
    return h.hexdigest()

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
    ap.add_argument("--partial-over-gb", type=float, default=PARTIAL_MIN_BYTES / 1024**3,
                    help="超过该体积(GB)的文件只算头尾分片指纹，标 partial=true")
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
    rows, hashed, reused, skipped, failed, partial = [], 0, 0, 0, 0, 0
    for n in files:
        p = os.path.join(root, n)
        try: st = os.stat(p)
        except OSError: continue
        prev = cache.get(n)
        mt = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))
        prev_ok = bool(prev) and prev.get("size") == st.st_size and prev.get("mtime") == mt
        prev_full = prev_ok and len(prev.get("sha256") or "") == 64
        prev_partial = (prev_ok and bool(prev.get("partial"))
                        and len(prev.get("partial_sha256") or "") == 64
                        and prev.get("hash_method") == PARTIAL_METHOD
                        and prev.get("chunk_bytes") == PARTIAL_CHUNK)
        if prev_full or prev_partial:
            rows.append(prev); reused += 1; continue
        # 大文件（>= PARTIAL_MIN_BYTES）只做头尾分片指纹，避免全量哈希超过单盘时间上限
        if st.st_size >= a.partial_over_gb * 1024**3:
            try:
                fp = partial_fp(p, st.st_size)
                rows.append({"name": n, "size": st.st_size, "sha256": None,
                             "partial": True, "partial_sha256": fp,
                             "hash_method": PARTIAL_METHOD, "hash_scope": "head+mid+tail",
                             "chunk_bytes": PARTIAL_CHUNK, "mtime": mt})
                partial += 1
                flush(out, rows)
                continue
            except OSError as e:
                failed += 1
                print(f"WARN 分片指纹失败 {n}: {e}", flush=True)
                continue
        h = cached(n)
        if h:
            reused += 1
        else:
            if (time.time() - t0) / 60 > a.max_minutes:
                skipped += 1
                prev2 = prev if prev_full else None
                if prev2: rows.append(prev2)
                continue
            try:
                h = sha256(p); hashed += 1
            except OSError as e:
                # 单文件读失败（网络盘 I/O 错误/临时消失）不应中断整盘清单
                failed += 1
                print(f"WARN 跳过不可读文件 {n}: {e}", flush=True)
                continue
        rows.append({"name": n, "size": st.st_size, "sha256": h,
                     "hash_method": "full-sha256", "mtime": mt})
        if hashed and hashed % 1 == 0:
            flush(out, rows)
    flush(out, rows)
    if partial:
        print(f"{root}: 分片指纹(partial) {partial} 个（头/中/尾各 {PARTIAL_CHUNK // 1024**2}MB 采样，非全量哈希）", flush=True)
    print(f"{root}: 共 {len(rows)} 条｜新算 {hashed}｜复用 {reused}｜超时跳过 {skipped}｜读失败 {failed}｜-> {out}")
    if failed:
        # 双审（kimi-k3.1-pro + MiniMax-M3.1）一致要求：清单不完整不得静默成功
        print(f"ERROR 清单不完整：读失败 {failed} 个文件", file=sys.stderr, flush=True)
        sys.exit(3)
    if skipped:
        # 2026-11-11 双审补强：超时跳过同样是「清单缺项」，不得 rc=0 静默通过
        print(f"ERROR 清单不完整：超时跳过 {skipped} 个文件（可调 --max-minutes 或走 partial）",
              file=sys.stderr, flush=True)
        sys.exit(4)

if __name__ == "__main__":
    main()
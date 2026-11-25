#!/usr/bin/env python3
"""media-batch.py —— 一次发多张图时，把「多条消息」攒成「一次汇总回复」。

问题：飞书里连续发 N 张图 = N 条独立消息 = N 次模型调用，格格只能一句一句回。
做法：每收到一张就先登记 + 「等安静」（后续图片还在路上），只在确认没有更新的图之后，
      由最后一个回合把整批一次性读进来、一次回复。

子命令:
  add <文件路径>          登记一张来图，打印当前批次
  gate <文件路径>         等待「安静 quiet 秒」，判断本轮是否该回
                          exit 0 = 该回（我可一次性处理整批）；exit 10 = 后面还有更新的图，本轮闭嘴
  take                   取走整批（JSON）并清空
  status                 看当前批
  prune                  清掉超过 30 分钟的旧条目

参数: --quiet 秒（默认 7） --max 秒（最多等，默认 25）
状态: state/print/media-buffer.json
"""
import argparse, datetime, fcntl, hashlib, json, os, struct, sys, time

STATE_DIR = os.environ.get("PRINT_STATE_DIR", "/home/j/.openclaw/workspace/state/print")
BUF = os.path.join(STATE_DIR, "media-buffer.json")
WATCH_DIRS = [
    "/home/j/.openclaw/media/inbound",
    "/home/j/openclaw-workspaces/print/media/inbound",
]
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".pdf",
             ".heic", ".mp4", ".mov", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".docx", ".xlsx"}


LOCK = BUF + ".lock"


def load():
    try:
        with open(BUF, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return []


def save(items):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = BUF + ".tmp.%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    os.replace(tmp, BUF)


def newest_media(max_depth=2):
    """两个入站目录里最新的媒体文件 mtime。"""
    best = 0.0
    for d in WATCH_DIRS:
        if not os.path.isdir(d):
            continue
        try:
            for root, dirs, files in os.walk(d):
                depth = root[len(d):].count(os.sep)
                if depth >= max_depth:
                    dirs[:] = []
                for fn in files:
                    if os.path.splitext(fn)[1].lower() in MEDIA_EXT:
                        try:
                            best = max(best, os.path.getmtime(os.path.join(root, fn)))
                        except OSError:
                            pass
        except OSError:
            pass
    return best


def _sha256(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 16)
            if not b:
                break
            h.update(b)
            if limit and f.tell() > limit:
                break
    return h.hexdigest()


def _exif_orientation(path):
    """读 EXIF Orientation（手机照片常 6/8，需交换宽高）。失败返回 1。"""
    try:
        with open(path, "rb") as f:
            d = f.read(65536)
        if d[:2] != b"\xff\xd8":
            return 1
        i = 2
        while i < len(d) - 4:
            if d[i] != 0xFF:
                i += 1
                continue
            m = d[i + 1]
            if m == 0xE1:
                seg = d[i + 4:i + 2 + struct.unpack(">H", d[i + 2:i + 4])[0]]
                if seg[:6] == b"Exif\x00\x00":
                    t = seg[6:]
                    bo = ">" if t[:2] == b"MM" else "<"
                    off = struct.unpack(bo + "I", t[4:8])[0]
                    n = struct.unpack(bo + "H", t[off:off + 2])[0]
                    for k in range(n):
                        e = off + 2 + k * 12
                        tag, typ, cnt = struct.unpack(bo + "HHI", t[e:e + 8])
                        if tag == 0x0112:
                            return struct.unpack(bo + "H", t[e + 8:e + 10])[0] or 1
                return 1
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            i += 2 + struct.unpack(">H", d[i + 2:i + 4])[0]
    except Exception:  # noqa: BLE001
        pass
    return 1


def _jpeg_info(path):
    try:
        with open(path, "rb") as f:
            data = f.read(200000)
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h, data[i + 9] if len(data) > i + 9 else 3
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            ln = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + ln
    except Exception:  # noqa: BLE001
        pass
    return None, None, 0


def cmd_add(a):
    os.makedirs(STATE_DIR, exist_ok=True)
    lk = open(LOCK, "a+")
    fcntl.flock(lk, fcntl.LOCK_EX)
    try:
        return _add_locked(a)
    finally:
        fcntl.flock(lk, fcntl.LOCK_UN)
        lk.close()


def _add_locked(a):
    items = load()
    p = os.path.abspath(a.file)
    mt = os.path.getmtime(p) if os.path.exists(p) else time.time()
    if not any(x.get("path") == p for x in items):
        ent = {"path": p, "mtime": mt, "ts_epoch": time.time(),
               "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        try:
            ent["size"] = os.path.getsize(p)
            ent["sha256"] = _sha256(p, limit=8 << 20)[:16]
            w, h, _nc = _jpeg_info(p)
            if w and h:
                ent["w"], ent["h"] = w, h
        except Exception:  # noqa: BLE001
            pass
        items.append(ent)
        save(items)
    print(json.dumps({"count": len(items), "items": items}, ensure_ascii=False))


def _last_ts(items):
    return max([float(x.get("ts_epoch") or 0) for x in items] or [0.0])


def cmd_gate(a):
    p = os.path.abspath(a.file)
    quiet = a.quiet
    try:
        mine = [x for x in load() if x.get("path") == p]
        my_t = float(mine[-1].get("ts_epoch") or 0) if mine else 0
        others = [float(x.get("ts_epoch") or 0) for x in load()
                  if x.get("path") != p and 0 < my_t - float(x.get("ts_epoch") or 0) <= 90]
        if others:
            quiet = min(quiet, a.follow)   # 同一批的后续图：用更短窗口，加快收口
    except Exception:  # noqa: BLE001
        pass
    # 等「本批最后一次登记」安静 quiet 秒：只认自己的缓冲区，不看他人的入站目录
    start = time.time()
    while True:
        items = load()
        last = _last_ts(items)
        if time.time() - last >= quiet or time.time() - start >= a.max:
            break
        time.sleep(1)
    items = load()
    me = [x for x in items if x.get("path") == p]
    if not me:
        print(json.dumps({"count": len(items), "items": items}, ensure_ascii=False))
        return 0
    my_ts = float(me[-1].get("ts_epoch") or 0)
    if _last_ts(items) > my_ts + 0.2:
        if time.time() - my_ts > a.stale:
            print(json.dumps({"count": len(items), "items": items,
                              "stale_flush": True}, ensure_ascii=False))
            return 0
        print("later")          # 后面还有更新的图 → 本轮 MUST 闭嘴
        return 10
    print(json.dumps({"count": len(items), "items": items}, ensure_ascii=False))
    return 0


def cmd_take(a):
    items = load()
    seen, dup = set(), []
    for x in items:
        s = x.get("sha256")
        if s and s in seen:
            dup.append(x.get("path"))
        elif s:
            seen.add(s)
    print(json.dumps({"count": len(items), "items": items,
                      "duplicates": dup}, ensure_ascii=False))
    save([])
    return 0


def cmd_status(a):
    items = load()
    print(json.dumps({"count": len(items), "items": items}, ensure_ascii=False))
    return 0


def cmd_prune(a):
    cutoff = time.time() - 30 * 60
    items = [x for x in load() if float(x.get("ts_epoch") or x.get("mtime") or 0) >= cutoff]
    save(items)
    print(json.dumps({"count": len(items), "items": items}, ensure_ascii=False))
    return 0


def _iter_media(hours):
    cutoff = time.time() - hours * 3600
    out = []
    for d in WATCH_DIRS:
        if not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            if root[len(d):].count(os.sep) >= 2:
                dirs[:] = []
            for fn in files:
                if os.path.splitext(fn)[1].lower() in {".jpg", ".jpeg", ".png", ".pdf", ".heic"}:
                    fp = os.path.join(root, fn)
                    try:
                        mt = os.path.getmtime(fp)
                    except OSError:
                        continue
                    if mt >= cutoff:
                        out.append(mt)
    return sorted(out)


def cmd_analyze(a):
    ts = _iter_media(a.hours)
    if not ts:
        print("近 %g 小时没有媒体文件" % a.hours)
        return 0
    gaps, bursts, cur = [], [], [ts[0]]
    for prev, nxt in zip(ts, ts[1:]):
        g = nxt - prev
        gaps.append(g)
        if g <= a.gap:
            cur.append(nxt)
        else:
            bursts.append(cur); cur = [nxt]
    bursts.append(cur)
    multi = [b for b in bursts if len(b) >= 2]
    ingap = [g for g in gaps if g <= a.cluster]
    def pct(v, q):
        if not v: return 0
        v = sorted(v); k = min(len(v)-1, int(round(q*(len(v)-1))))
        return v[k]
    print("近 %g 小时媒体文件 %d 个，按 %gs 聚成 %d 批（其中多图批 %d）"
          % (a.hours, len(ts), a.cluster, len(bursts), len(multi)))
    if ingap:
        print("同批相邻间隔: 中位 %.1fs  P90 %.1fs  最大 %.1fs"
              % (pct(ingap,0.5), pct(ingap,0.9), max(ingap))) 
    if multi:
        print("多图批规模: 最大 %d 张, 平均 %.1f 张"
              % (max(len(b) for b in multi), sum(len(b) for b in multi)/len(multi)))
    print("建议静默窗: %.0fs（≥ P90 间隔）" % max(3, round(pct(ingap,0.9))))
    return 0


def _pdf_escape_name(b):
    return b


def _pdf_check_images(pdf_path, sources):
    """从 PDF 里抠出 DCTDecode 流，逐个和源 JPEG 比字节长度+尾部 EOI。"""
    try:
        with open(pdf_path, "rb") as f:
            data = f.read()
        streams, i = [], 0
        while True:
            i = data.find(b"/DCTDecode", i)
            if i < 0:
                break
            st = data.find(b"stream\n", i)
            en = data.find(b"\nendstream", st)
            if st < 0 or en < 0:
                return False, "图片流边界异常"
            st += len(b"stream\n")
            streams.append(data[st:en])
            i = en
        if len(streams) != len(sources):
            return False, "图片流数量 %d != 源 %d" % (len(streams), len(sources))
        notes = []
        for k, src in enumerate(sources):
            if not streams[k].startswith(b"\xff\xd8"):
                return False, "第 %d 页不是 JPEG 数据" % (k + 1)
            with open(src, "rb") as f:
                raw = f.read()
            if streams[k] != raw:
                return False, ("第 %d 页与源文件字节不一致（%d vs %d）"
                               % (k + 1, len(streams[k]), len(raw)))
            if b"\xff\xd9" not in raw[-65536:]:
                notes.append("第 %d 页原图 EOI 不在尾部（疑附加数据），字节一致，按可打处理" % (k + 1))
        return True, ("ok" if not notes else "; ".join(notes))
    except Exception as e:  # noqa: BLE001
        return False, "图片流校验异常 %s" % e


def _pdf_verify(path, nobj):
    """自检：startxref 指向 xref，每条 offset 必须正好落在 'N 0 obj' 上。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
        i = data.rfind(b"startxref")
        if i < 0:
            return False, "缺 startxref"
        off = int(data[i + 9:].split()[0])
        if not data[off:off + 4] == b"xref":
            return False, "startxref 未指向 xref"
        chunk = data[off:off + 400 * (nobj + 2)]
        lines = chunk.split(b"\n")
        bad = []
        for n in range(1, nobj + 1):
            try:
                line = lines[2 + n]
                o = int(line.split()[0])
            except Exception:  # noqa: BLE001
                bad.append(n)
                continue
            if data[o:o + len(b"%d 0 obj" % n)] != b"%d 0 obj" % n:
                bad.append(n)
        if bad:
            return False, "对象偏移不符: %s" % bad[:5]
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        return False, "自检异常 %s" % e


def cmd_merge(a):
    items = [x for x in load() if os.path.splitext(x.get("path", ""))[1].lower() in
             (".jpg", ".jpeg")]
    items.sort(key=lambda x: float(x.get("ts_epoch") or 0))
    if not items:
        print("批里没有 JPEG 图片，无需合并", file=sys.stderr)
        return 2
    pw, ph = (595.276, 841.89) if a.paper == "a4" else (841.89, 1190.55)
    objs = []          # 每个元素是 bytes（不含 obj 头）
    # 1 Catalog / 2 Pages 占位
    objs.append(None)  # 1
    objs.append(None)  # 2
    kids = []
    order = []
    for it in items:
        fp = it["path"]
        w, h, ncomp = _jpeg_info(fp)
        if not w or not h:
            continue
        with open(fp, "rb") as f:
            raw = f.read()
        cs = b"/DeviceGray" if ncomp == 1 else (b"/DeviceCMYK" if ncomp == 4 else b"/DeviceRGB")
        img_id = len(objs) + 1
        objs.append(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                    b"/ColorSpace %s /BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n"
                    % (w, h, cs, len(raw)) + raw + b"\nendstream")
        # 页面方向跟随图片
        rot = _exif_orientation(fp)
        eff_w, eff_h = (h, w) if rot in (5, 6, 7, 8) else (w, h)
        if eff_w > eff_h:
            P_W, P_H = ph, pw    # 横向
        else:
            P_W, P_H = pw, ph
        m = 0.0
        sc = min((P_W - 2 * m) / float(w), (P_H - 2 * m) / float(h))
        dw, dh = w * sc, h * sc
        x, y = (P_W - dw) / 2.0, (P_H - dh) / 2.0
        content = ("q %.2f 0 0 %.2f %.2f %.2f cm /Im0 Do Q" % (dw, dh, x, y)).encode()
        cont_id = len(objs) + 1
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        page_id = len(objs) + 1
        objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] "
                    b"/Resources << /XObject << /Im0 %d 0 R >> >> /Contents %d 0 R >>"
                    % (P_W, P_H, img_id, cont_id))
        kids.append(page_id)
        order.append(fp)

    if not kids:
        print("没有可用的 JPEG 页面", file=sys.stderr)
        return 2

    objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objs[1] = (b"<< /Type /Pages /Count %d /Kids [%s] >>"
               % (len(kids), b" ".join(b"%d 0 R" % k for k in kids)))

    out = []
    out.append(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    pos = len(out[0])
    for i, body in enumerate(objs, start=1):
        chunk = b"%d 0 obj\n" % i + (body or b"") + b"\nendobj\n"
        offsets.append(pos)
        out.append(chunk)
        pos += len(chunk)
    xref_pos = pos
    xref = [b"xref\n0 %d\n" % (len(objs) + 1), b"0000000000 65535 f \n"]
    for off in offsets[1:]:
        xref.append(b"%010d 00000 n \n" % off)
    tail = (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objs) + 1, xref_pos))
    data = b"".join(out) + b"".join(xref) + tail

    outp = a.out or os.path.join(STATE_DIR, "merged-%s.pdf" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    os.makedirs(os.path.dirname(outp) or ".", exist_ok=True)
    with open(outp, "wb") as f:
        f.write(data)
    verified, why = _pdf_verify(outp, len(objs))
    if verified:
        ok2, why2 = _pdf_check_images(outp, order)
        if not ok2:
            verified, why = False, why2
    if not a.keep:
        save([])
    print(json.dumps({"out": outp, "pages": len(kids), "bytes": len(data),
                      "verified": verified, "verify_note": why, "sources": order},
                     ensure_ascii=False))
    return 0


def cmd_selftest(a):
    """无人值守自证：拿真实 JPEG 模拟连发，验证 add/gate/take/merge 四条路径。"""
    import shutil
    try:
        _, vals, _ = (None, None, None)
    except Exception:  # noqa: BLE001
        pass
    srcs = [x for x in _iter_media(24 * 30)][:8]
    files = []
    for mt in srcs:
        for d in WATCH_DIRS:
            if not os.path.isdir(d):
                continue
            for root, _dirs, fs in os.walk(d):
                for fn in fs:
                    fp = os.path.join(root, fn)
                    try:
                        if abs(os.path.getmtime(fp) - mt) < 1e-6 and fn.lower().endswith((".jpg", ".jpeg")):
                            files.append(fp)
                    except OSError:
                        pass
            if len(files) >= a.n:
                break
        if len(files) >= a.n:
            break
    if len(files) < 2:
        print(json.dumps({"ok": False, "why": "找不到足够的 JPEG 样本"}, ensure_ascii=False))
        return 2

    tmpdir = os.path.join(STATE_DIR, "selftest")
    os.makedirs(tmpdir, exist_ok=True)
    cases = []
    for k, fp in enumerate(files):
        dst = os.path.join(tmpdir, "case-%d%s" % (k + 1, os.path.splitext(fp)[1]))
        shutil.copyfile(fp, dst)
        cases.append(dst)

    save([])
    t0 = time.time()
    import io as _io
    _buf = sys.stdout
    for dst in cases:
        sys.stdout = _io.StringIO()      # 吞掉 add 的回显
        try:
            cmd_add(argparse.Namespace(file=dst))
        finally:
            sys.stdout = _buf
        time.sleep(1.0)                  # 模拟连发间隔

    # 第一张：后面还有更新的 → 必须 10
    a_quiet, a_max = 3.0, 12.0
    a.quiet, a.max, a.file = a_quiet, a_max, cases[0]
    rc_first = cmd_gate(a)
    # 最后一张：已安静 → 必须 0
    a.file = cases[-1]
    rc_last = cmd_gate(a)
    took = time.time() - t0

    merge_out = os.path.join(tmpdir, "merged.pdf")
    ma = argparse.Namespace(out=merge_out, paper="a4", keep=True)
    buf = sys.stdout
    import io
    cap = io.StringIO()
    sys.stdout = cap
    rc_merge = None
    try:
        rc_merge = cmd_merge(ma)
    finally:
        sys.stdout = buf
    mres = {}
    try:
        mres = json.loads(cap.getvalue().strip() or "{}")
    except Exception:  # noqa: BLE001
        mres = {"raw": cap.getvalue()[:200]}

    # 取批 + 重复检测
    cap2 = io.StringIO()
    sys.stdout = cap2
    try:
        cmd_take(argparse.Namespace())
    finally:
        sys.stdout = buf
    tres = {}
    try:
        tres = json.loads(cap2.getvalue().strip() or "{}")
    except Exception:  # noqa: BLE001
        tres = {}

    ok = (rc_first == 10 and rc_last == 0 and rc_merge == 0
          and mres.get("verified") is True and mres.get("pages") == len(cases)
          and tres.get("count") == len(cases))
    print(json.dumps({"ok": ok, "n": len(cases), "gate_first_rc": rc_first,
                      "gate_last_rc": rc_last, "merge": mres, "take_count": tres.get("count"),
                      "duplicates": tres.get("duplicates"), "elapsed_s": round(took, 1),
                      "samples": cases}, ensure_ascii=False, indent=1))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", type=float, default=5)
    ap.add_argument("--follow", type=float, default=3)
    ap.add_argument("--max", type=float, default=20)
    ap.add_argument("--stale", type=float, default=180)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("add", "gate"):
        sp = sub.add_parser(name)
        sp.add_argument("file")
        sp.add_argument("--quiet", type=float, default=5)
        sp.add_argument("--follow", type=float, default=3)
        sp.add_argument("--max", type=float, default=20)
        sp.add_argument("--stale", type=float, default=180)
        sp.set_defaults(fn=cmd_add if name == "add" else cmd_gate)
    for name, fn in (("take", cmd_take), ("status", cmd_status), ("prune", cmd_prune)):
        sub.add_parser(name).set_defaults(fn=fn)
    sp = sub.add_parser("merge")
    sp.add_argument("--out")
    sp.add_argument("--paper", choices=["a4", "a3"], default="a4")
    sp.add_argument("--keep", action="store_true", help="合并后不清空缓冲")
    sp.set_defaults(fn=cmd_merge)
    sp = sub.add_parser("selftest")
    sp.add_argument("--n", type=int, default=3)
    sp.set_defaults(fn=cmd_selftest, fetch=False, keep=False, out=None)
    sp = sub.add_parser("analyze")
    sp.add_argument("--hours", type=float, default=72)
    sp.add_argument("--cluster", type=float, default=8)
    sp.add_argument("--gap", type=float, default=8)
    sp.set_defaults(fn=cmd_analyze)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

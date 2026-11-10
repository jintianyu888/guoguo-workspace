#!/usr/bin/env python3
"""print-ipp.py —— 走 IPP 631 直投原始 PDF/JPEG（设备自带引擎渲染）。

2026-10-01 定案：这台 TOSHIBA e-STUDIO 在 9100 裸推 PS 时能画文字/矢量，
但任何 `image`/`imagemask` 都不出图 ⇒ 乐谱永远白纸（已由老板实物确认）。
而 **IPP 631 直投 application/pdf 可正常出图**（老板 14:35 确认）。
所以：乐谱/图像类一律走这条，不再 print-prep 转 PS。

用法: print-ipp.py <文件.pdf|.jpg> [--host 192.168.1.80] [--port 631] [--path /ipp/print] [--dry]
"""
import argparse, os, socket, struct, sys, json, time, hashlib, datetime

def ipp_attr(tag, name, value):
    n = name.encode()
    v = value if isinstance(value, bytes) else value.encode()
    return struct.pack('>BH', tag, len(n)) + n + struct.pack('>H', len(v)) + v

def print_job(host, port, path, filename, mime, pages=None, media='iso_a4_210x297mm', sides=None, scaling='fit'):
    data = open(filename, 'rb').read()
    body = b''
    body += ipp_attr(0x47, 'attributes-charset', 'utf-8')
    body += ipp_attr(0x48, 'attributes-natural-language', 'en-us')
    body += ipp_attr(0x45, 'printer-uri', 'ipp://%s%s' % (host, path))
    body += ipp_attr(0x42, 'job-name', os.path.basename(filename))
    body += ipp_attr(0x49, 'document-format', mime)
    # 2026-10-03 修（乐谱被裁切）：显式 A4 + 缩放到可打印区，非 A4 原稿不再被 100% 裁边。
    body += ipp_attr(0x44, 'media', media)
    body += ipp_attr(0x44, 'print-scaling', scaling)
    if sides:
        body += ipp_attr(0x44, 'sides', sides)
    body += ipp_attr(0x23, 'print-quality', struct.pack('>i', 5))  # 5=high 质量
    if pages:
        # page-ranges (rangeOfInteger 0x33)：每段 8 字节（lower/upper 各 int32，1 基含端点）
        body += ipp_attr(0x33, 'page-ranges', b''.join(struct.pack('>ii', lo, hi) for lo, hi in pages))
    body += b'\x03'
    req = struct.pack('>BBHI', 2, 0, 0x0002, 1) + body + data
    _t0 = time.time()  # 2026-11-07 计时起点（速度记录用）
    s = socket.create_connection((host, port), timeout=60)
    s.sendall(('POST ' + path + ' HTTP/1.1\r\nHost: ' + host +
               '\r\nContent-Type: application/ipp\r\nContent-Length: ' + str(len(req)) +
               '\r\nConnection: close\r\n\r\n').encode() + req)
    resp = b''
    while True:
        c = s.recv(65536)
        if not c: break
        resp += c
    s.close()
    head = resp.split(b'\r\n\r\n', 1)[-1]
    i = head.find(b'\x02\x00')
    st = struct.unpack('>H', head[i+2:i+4])[0] if i >= 0 else -1
    return st, len(data)

def ledger(path, name, size, note):
    jobs = '/home/j/.openclaw/workspace-print/print/jobs.md'
    sent = '/home/j/.openclaw/workspace/state/print-sent.json'
    try:
        h = hashlib.sha256(open(path, 'rb').read()).hexdigest()[:16]
    except Exception:
        h = ''
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    try:
        import fcntl, re
        with open(jobs, 'a+', encoding='utf-8') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0); txt = f.read()
            ids = [int(x) for x in re.findall(r'\|\s*#(\d+)\s*\|', txt)]
            n = (max(ids) if ids else 0) + 1
            f.seek(0, 2)
            f.write('| #%d | %s（%d B） | A4×1 | 1 | 单面 | - | %s | 打印中 | %s；sha %s；等出纸确认 |\n' % (n, name, size, now, note, h))
            fcntl.flock(f, fcntl.LOCK_UN)
        old = {}
        try: old = json.load(open(sent))
        except Exception: pass
        old[h] = time.time()
        json.dump(old, open(sent, 'w'), ensure_ascii=False)
        return n
    except Exception as e:
        return 'ledger_err:%s' % e

def guess_mime(fn):
    l = fn.lower()
    if l.endswith('.pdf'): return 'application/pdf'
    if l.endswith(('.jpg', '.jpeg')): return 'image/jpeg'
    if l.endswith('.png'): return 'image/png'
    return 'application/octet-stream'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--host', default='192.168.1.80')
    ap.add_argument('--port', type=int, default=631)
    ap.add_argument('--path', default='/ipp/print')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--media', default='iso_a4_210x297mm')
    ap.add_argument('--sides', default=None)
    ap.add_argument('--scaling', default='fit')
    ap.add_argument('--pages', default=None, help='页范围，如 15-27 或 15-27,30-35（IPP page-ranges，文档页码 1 基含端点）')
    a = ap.parse_args()
    pgr = None
    if a.pages:
        pgr = []
        for part in a.pages.replace('，', ',').split(','):
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                lo, hi = part.split('-', 1)
            else:
                lo = hi = part
            pgr.append((int(lo), int(hi)))
    for f in a.files:
        if not os.path.isfile(f):
            print('跳过（不存在）：%s' % f, file=sys.stderr); continue
        mime = guess_mime(f)
        size = os.path.getsize(f)
        if a.dry:
            print('[dry] %s（%d B, %s）→ ipp://%s:%d%s' % (f, size, mime, a.host, a.port, a.path)); continue
        st, n = print_job(a.host, a.port, a.path, f, mime, pages=pgr, media=a.media, sides=a.sides, scaling=a.scaling)
        ok = (st == 0)
        msg = {0: 'successful-ok', 0x0401: 'bad-request', 0x0403: 'forbidden', 0x0405: 'not-found', 0x0406: 'not-allowed', 0x0505: 'format-not-supported'}.get(st, '0x%04x' % st)
        try:
            import subprocess as _sp, os as _os
            _pg = 1
            try:
                _o = _sp.run(['pdfinfo', f], capture_output=True, text=True, timeout=15).stdout
                for _l in _o.splitlines():
                    if _l.lower().startswith('pages:'):
                        _pg = int(_l.split(':')[1].strip()); break
            except Exception:
                _pg = 1
            _sp.run(['python3', _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'print-perf.py'), 'record',
                     '--file', f, '--pages', str(_pg), '--bytes', str(n), '--secs', str(round(time.time() - _t0, 1)),
                     '--method', 'ipp631', '--rc', '0' if ok else '1'], capture_output=True, timeout=30)
        except Exception as _e:
            print('  (绩效记录失败: %s)' % _e, file=sys.stderr)
        print('%s %s（%d B, %s）→ ipp://%s:%d  status=%s %s' % ('已发送' if ok else '失败', f, n, mime, a.host, a.port, msg, '' if ok else ''))
        if ok:
            num = ledger(f, os.path.basename(f), n, '管家直推 · IPP 631 直投 %s' % mime)
            if str(num).startswith('ledger_err'):
                print('  ⚠️ 台账未登记（%s）——出纸成功但无登记号，请手工补登 jobs.md' % num)
            else:
                print('  ✅ 已登记 #%s' % num)
        else:
            sys.exit(1)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""sms-inbox.py — 接收手机转发的短信（局域网 + token），落盘并列最近验证码。
用法:
  python3 tools/sms-inbox.py serve        启动 HTTP 接收（默认 0.0.0.0:18899）
  python3 tools/sms-inbox.py latest       打印最近一条可用验证码（JSON）
  python3 tools/sms-inbox.py list [n]     列最近 n 条（脱敏）
"""
import json, os, re, sys, time, hmac, hashlib, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WS = '/home/j/.openclaw/workspace'
CONF = '/home/j/.config/guoguo/sms.json'
INBOX = os.path.join(WS, 'state', 'sms', 'inbox')
INDEX = os.path.join(WS, 'state', 'sms', 'index.jsonl')
PORT = 18899

def conf():
    with open(CONF) as f:
        return json.load(f)

def ensure_dirs():
    os.makedirs(INBOX, exist_ok=True)
    os.makedirs(os.path.dirname(INDEX), exist_ok=True)
    os.chmod(os.path.dirname(INDEX), 0o700)

def save(rec):
    ensure_dirs()
    ts = datetime.datetime.now()
    key = hashlib.sha256((rec.get('from','')+rec.get('body','')+str(ts)).encode()).hexdigest()[:10]
    fn = os.path.join(INBOX, ts.strftime('%Y%m%d-%H%M%S') + '-' + key + '.json')
    with open(fn, 'w') as f:
        json.dump(rec, f, ensure_ascii=False)
    os.chmod(fn, 0o600)
    line = dict(rec); line['stored'] = ts.isoformat(timespec='seconds'); line['file'] = fn
    with open(INDEX, 'a') as f:
        f.write(json.dumps(line, ensure_ascii=False) + '\n')
    os.chmod(INDEX, 0o600)
    return fn

CODE_RE = re.compile(r'(?<!\d)(\d{4,8})(?!\d)')

def classify(body):
    site = None
    for name, pat in (
        ('拓竹/Bambu', r'拓竹|Bambu|bambulab|makerworld'),
        ('飞书/Feishu', r'飞书|Feishu|Lark'),
        ('银行', r'银行|储蓄|信用卡|借记卡'),
        ('政务', r'政务|社保|公积金|税务'),
    ):
        if re.search(pat, body, re.I):
            site = name; break
    m = CODE_RE.findall(body)
    return site, (m[-1] if m else None)

class H(BaseHTTPRequestHandler):
    server_version = 'sms-inbox/1.0'
    def _ok(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('content-type', 'application/json; charset=utf-8')
        self.send_header('content-length', str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def _auth(self):
        c = conf()
        tok = self.headers.get('x-sms-token') or ''
        if not tok and '?' in self.path:
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            tok = (q.get('token') or [''])[0]
        return hmac.compare_digest(tok, c['token'])
    def log_message(self, *a):
        pass
    def do_GET(self):
        if self.path.startswith('/health'):
            return self._ok({'ok': True, 'ts': datetime.datetime.now().isoformat(timespec='seconds')})
        self._ok({'error': 'not found'}, 404)
    def do_POST(self):
        if not self._auth():
            return self._ok({'ok': False, 'error': 'unauthorized'}, 401)
        n = int(self.headers.get('content-length') or 0)
        if n > 65536:
            return self._ok({'ok': False, 'error': 'too large'}, 413)
        raw = self.rfile.read(n).decode('utf-8', 'replace')
        try:
            data = json.loads(raw)
        except Exception:
            data = {'body': raw}
            try:
                from urllib.parse import parse_qs
                q = {k: v[0] for k, v in parse_qs(raw, keep_blank_values=True).items()}
                if q:
                    data = {'from': q.get('from') or q.get('sender') or q.get('phone') or '',
                            'body': q.get('body') or q.get('content') or q.get('msg') or q.get('text') or raw}
            except Exception:
                pass
        body = str(data.get('body') or data.get('text') or data.get('msg') or '')
        rec = {
            'from': str(data.get('from') or data.get('sender') or ''),
            'body': body,
            'ts': str(data.get('ts') or datetime.datetime.now().isoformat(timespec='seconds')),
            'ip': self.client_address[0],
        }
        site, code = classify(body)
        rec['site'] = site; rec['code'] = code
        fn = save(rec)
        print('[sms] %s from=%s site=%s code=%s' % (rec['ts'], rec['from'], site, bool(code)), flush=True)
        return self._ok({'ok': True, 'code': code, 'site': site, 'file': os.path.basename(fn)})

def latest(max_age=300):
    if not os.path.exists(INDEX):
        return {'ok': False, 'error': 'no-sms'}
    rows = [json.loads(l) for l in open(INDEX) if l.strip()]
    if not rows:
        return {'ok': False, 'error': 'no-sms'}
    for r in reversed(rows):
        try:
            t = datetime.datetime.fromisoformat(r['stored'])
        except Exception:
            continue
        age = (datetime.datetime.now() - t).total_seconds()
        if r.get('code') and age <= max_age:
            return {'ok': True, 'code': r['code'], 'site': r.get('site'), 'age_s': int(age), 'from': r.get('from')}
    return {'ok': False, 'error': 'no-recent-code', 'last': rows[-1].get('stored')}

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'serve'
    if cmd == 'serve':
        ensure_dirs()
        srv = ThreadingHTTPServer(('0.0.0.0', PORT), H)
        print('[sms] listening on 0.0.0.0:%d' % PORT, flush=True)
        srv.serve_forever()
    elif cmd == 'latest':
        print(json.dumps(latest(), ensure_ascii=False))
    elif cmd == 'list':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        rows = [json.loads(l) for l in open(INDEX)] if os.path.exists(INDEX) else []
        for r in rows[-n:]:
            print(r['stored'], r.get('site') or '-', 'code=' + ('***' if r.get('code') else '-'), (r.get('body') or '')[:40].replace('\n', ' '))
    else:
        print(__doc__)

if __name__ == '__main__':
    main()


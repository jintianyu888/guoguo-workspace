#!/usr/bin/env python3
"""print-send.py v2 - 分张送印 + 强去重（每张发完立刻落台账，中断也不丢记录）"""
import os, sys, time, json, socket, hashlib

LEDGER = os.path.expanduser('~/.openclaw/workspace/state/print-sent.json')
DEDUP_SEC = 1800

def sheets_from(data):
    i = data.find(b'@PJL ENTER LANGUAGE=POSTSCRIPT')
    head_end = data.find(b'\n', i) + 1
    hdr = data[:head_end]
    j = data.rfind(b'@PJL EOJ')
    body = data[head_end:j]
    lines = body.split(b'\n')
    while lines and not lines[0].strip(): lines.pop(0)
    pshdr = lines[0] + b'\n' + lines[1] + b'\n'
    rest = lines[2:]
    chunks, cur = [], []
    for ln in rest:
        cur.append(ln)
        if ln.strip() == b'showpage':
            chunks.append(cur); cur = []
    U = b'\x1b%-12345X'
    out = []
    for k in range(0, len(chunks), 2):
        part = chunks[k] + (chunks[k+1] if k+1 < len(chunks) else [])
        out.append(hdr + pshdr + b'\n'.join(part) + b'\n' + U + b'@PJL EOJ\r\n')
    return out

def load():
    if os.path.exists(LEDGER):
        try: return json.load(open(LEDGER))
        except Exception: return {}
    return {}

def save(led):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    json.dump({k: v for k, v in led.items() if time.time() - v < 86400}, open(LEDGER, 'w'))

def main():
    src = sys.argv[1]
    host = sys.argv[2] if len(sys.argv) > 2 else '192.168.1.80'
    data = open(src, 'rb').read()
    led = load()
    for idx, payload in enumerate(sheets_from(data), 1):
        h = hashlib.sha256(payload).hexdigest()[:16]
        age = time.time() - led.get(h, 0)
        if age < DEDUP_SEC:
            print('SKIP sheet %d (dedup, %ds ago)' % (idx, int(age))); sys.stdout.flush(); continue
        s = socket.socket(); s.settimeout(60)
        s.connect((host, 9100)); s.sendall(payload); s.close()
        led[h] = time.time()
        save(led)
        print('SENT sheet %d (%.0f KB)' % (idx, len(payload) / 1024)); sys.stdout.flush()
        time.sleep(8)
    print('DONE')

if __name__ == '__main__':
    main()
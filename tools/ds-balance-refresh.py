#!/usr/bin/env python3
# ds-balance-refresh.py v1.0 (2026-11-18) —— 把 DeepSeek 实时余额写回 quotas.json（供回复页脚显示新鲜值）
# 为什么：quota-scrape 两小时一轮且走浏览器，DeepSeek 余额常常是 1-2 小时前的；
#         ds-balance.sh 直查 API 很便宜，本脚本每 30 分钟跑一次并合并写回，不改其他字段。
# 用法: python3 tools/ds-balance-refresh.py [--dry-run]
import json, os, re, subprocess, sys, tempfile, datetime

WS = '/home/j/.openclaw/workspace'
QUO = WS + '/state/model-econ/quotas.json'
LOCK = WS + '/state/work/ds-balance-refresh.lock'


def main():
    dry = '--dry-run' in sys.argv
    r = subprocess.run(['bash', WS + '/tools/ds-balance.sh'], capture_output=True, text=True, timeout=60)
    out = (r.stdout or '').strip()
    m = re.search(r'([¥$])\s*([0-9.]+)\s*\(([A-Z]{3})\s*/\s*([0-9:\- ]+)\)', out)
    if not m:
        print('解析失败，原样输出:', out[:120] or r.stderr[:120])
        return 1
    cur, val, ccy, stamp = m.group(1), float(m.group(2)), m.group(3), m.group(4).strip()
    data = json.load(open(QUO))
    prov = data.setdefault('providers', {}).setdefault('deepseek', {})
    old = (prov.get('balance'), prov.get('captured_at'))
    prov['balance'] = val
    prov['currency'] = ccy
    prov['captured_at'] = stamp
    prov['source'] = 'ds-balance.sh 直查 API'
    prov['status'] = 'ok'
    if dry:
        print('dry-run:', old, '->', (val, stamp))
        return 0
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(QUO))
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, QUO)
    print('已写回 DeepSeek 余额 %s%s @ %s（旧: %s @ %s）' % (cur, val, stamp, old[0], old[1]))
    return 0


if __name__ == '__main__':
    sys.exit(main())

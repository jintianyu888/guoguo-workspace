#!/usr/bin/env python3
"""phone-kola-task.py — 每天只点「收淘金币」（Kola助手/小米游戏中心 一键执行任务）
用法: python3 tools/phone-kola-task.py [--dry]
"""
import os, re, subprocess, sys, time, json, datetime

ADB = '/home/j/.local/opt/platform-tools/adb.exe'
WS = '/home/j/.openclaw/workspace'
LOG = os.path.join(WS, 'state', 'phone', 'tasks.log')
PKG = 'com.xiaomi.gamecenter'

def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    line = '%s %s' % (datetime.datetime.now().isoformat(timespec='seconds'), msg)
    print(line, flush=True)
    with open(LOG, 'a') as f:
        f.write(line + '\n')

def adb(*args, timeout=60, retries=3):
    for i in range(retries):
        try:
            r = subprocess.run([ADB] + list(args), capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0 and 'no devices' not in (r.stdout + r.stderr):
                return r.stdout
        except Exception as e:
            pass
        subprocess.run([ADB, 'reconnect', 'offline'], capture_output=True, text=True, timeout=30)
        time.sleep(2)
    return ''

def device_ok():
    out = adb('devices')
    return re.search(r'^\S+\s+device$', out.replace('\r', ''), re.M) is not None

def dump_ui():
    adb('shell', 'uiautomator', 'dump', '/sdcard/wd.xml', timeout=60)
    adb('pull', '/sdcard/wd.xml', '/tmp/wd_phone.xml', timeout=60)
    try:
        return open('/tmp/wd_phone.xml', encoding='utf-8', errors='replace').read()
    except Exception:
        return ''

def nodes(xml):
    out = []
    for m in re.finditer(r'<node[^>]*>', xml):
        tag = m.group(0)
        def attr(k):
            mm = re.search(k + r'="([^"]*)"', tag)
            return mm.group(1) if mm else ''
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', tag)
        if not b:
            continue
        x1, y1, x2, y2 = map(int, b.groups())
        out.append({'text': attr('text'), 'desc': attr('content-desc'), 'checked': attr('checked') == 'true',
                    'clickable': attr('clickable') == 'true', 'bounds': (x1, y1, x2, y2)})
    return out

def center(n):
    x1, y1, x2, y2 = n['bounds']
    return ((x1 + x2) // 2, (y1 + y2) // 2)

def tap_node(n, label=''):
    x, y = center(n)
    adb('shell', 'input', 'tap', str(x), str(y))
    log('tap %s at %d,%d' % (label or n['text'], x, y))
    time.sleep(1.2)

def find(ns, text):
    for n in ns:
        if n['text'] == text:
            return n
    return None

def focus():
    out = adb('shell', 'dumpsys', 'window')
    m = re.search(r'mCurrentFocus=Window\{[^}]*?u0 ([\w\.]+)/', out.replace('\r', ''))
    return m.group(1) if m else ''

def main():
    dry = '--dry' in sys.argv
    if not device_ok():
        log('SKIP no device')
        return 0
    adb('shell', 'input', 'keyevent', 'KEYCODE_WAKEUP'); time.sleep(1)
    adb('shell', 'svc', 'power', 'stayon', 'true')
    adb('shell', 'settings', 'put', 'system', 'screen_off_timeout', '1200000')
    adb('shell', 'input', 'swipe', '540', '1900', '540', '700', '150'); time.sleep(1)
    adb('shell', 'monkey', '-p', PKG, '-c', 'android.intent.category.LAUNCHER', '1')
    time.sleep(6)
    f = focus()
    log('focus after open: %s' % f)
    if PKG not in f:
        log('ERROR app not foreground')
        return 2
    ns = nodes(dump_ui())
    btn = find(ns, '一键执行任务')
    if not btn:
        log('ERROR 一键执行任务 not found')
        return 3
    tap_node(btn, '一键执行任务')
    time.sleep(2.5)
    ns = nodes(dump_ui())
    # 只保留「淘金币」：取消其他所有已勾选项
    rows = [n for n in ns if n['text'] in ('芭芭农场', '淘金币', '淘宝签到', '淘特小鸡', '菜鸟', '饿了么')]
    checks = [n for n in ns if n['clickable'] and n['checked']]
    log('checked nodes: %d, rows: %s' % (len(checks), [r['text'] for r in rows]))
    for n in checks:
        # 找到与该勾选控件 y 最接近的行文本
        y = center(n)[1]
        near = min(rows, key=lambda r: abs(center(r)[1] - y)) if rows else None
        name = near['text'] if near else '?'
        if name != '淘金币' and abs(center(near)[1] - y) < 60 if near else False:
            tap_node(n, 'uncheck ' + name)
    if dry:
        log('DRY stop before start')
        return 0
    ns = nodes(dump_ui())
    start = find(ns, '开始执行')
    if not start:
        log('ERROR 开始执行 not found')
        return 4
    tap_node(start, '开始执行')
    time.sleep(0.7)
    tap_node(start, '开始执行(确认)')
    log('STARTED')
    # 等待执行结束（最长 20 分钟）
    for i in range(40):
        time.sleep(30)
        f = focus()
        if PKG in f:
            log('DONE after %ds' % ((i + 1) * 30))
            break
    else:
        log('TIMEOUT still running')
    adb('shell', 'input', 'keyevent', 'KEYCODE_BACK')
    adb('shell', 'input', 'keyevent', 'KEYCODE_HOME')
    adb('shell', 'svc', 'power', 'stayon', 'false')
    adb('shell', 'settings', 'put', 'system', 'screen_off_timeout', '30000')
    adb('shell', 'input', 'keyevent', 'KEYCODE_SLEEP')
    log('FINISHED')
    return 0

if __name__ == '__main__':
    sys.exit(main())

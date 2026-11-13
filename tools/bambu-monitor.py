#!/usr/bin/env python3
"""Bambu P2S 打印监控：取一次快照，与上次对比，异常/完成推飞书。零 token 脚本。
用法: python3 tools/bambu-monitor.py [--quiet]
状态: state/3dprint/state.json 事件: state/3dprint/events.jsonl"""
import json, os, ssl, subprocess, sys, time
from pathlib import Path
import paho.mqtt.client as mqtt

WS = Path(__file__).resolve().parent.parent
CRED = WS / 'state' / 'secrets' / 'bambu.json'
OUT = WS / 'state' / '3dprint'
STATE = OUT / 'state.json'
EVENTS = OUT / 'events.jsonl'

def load():
    d = json.loads(CRED.read_text())
    return d['ip'], d['serial'], d['code']

def snapshot(ip, serial, code, wait=15):
    got = {}
    def on_connect(c, u, f, rc, props=None):
        c.subscribe('device/%s/report' % serial, qos=0)
    def on_message(c, u, m):
        try:
            got.update(json.loads(m.payload.decode('utf-8', 'ignore')))
        except Exception:
            pass
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id='guoguo-mon-%d' % os.getpid())
    c.username_pw_set('bblp', code)
    c.tls_set_context(ctx)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(ip, 8883, 15)
    c.loop_start()
    time.sleep(1.5)
    c.publish('device/%s/request' % serial, json.dumps({'pushing': {'sequence_id': '1', 'command': 'pushall'}}))
    end = time.time() + wait
    while time.time() < end and not got:
        time.sleep(0.3)
    time.sleep(0.3)
    c.loop_stop(); c.disconnect()
    return got.get('print', {})

def notify(msg):
    try:
        subprocess.run(['bash', str(WS / 'tools' / 'notify.sh'), msg], timeout=120)
    except Exception as e:
        print('notify fail', e, file=sys.stderr)

def main():
    quiet = '--quiet' in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    ip, serial, code = load()
    try:
        p = snapshot(ip, serial, code)
    except Exception as e:
        print('连接失败:', e)
        prev = json.loads(STATE.read_text()) if STATE.exists() else {}
        miss = int(prev.get('_miss', 0)) + 1
        prev['_miss'] = miss
        STATE.write_text(json.dumps(prev, ensure_ascii=False))
        if miss == 3 and not quiet:
            notify('【3D 打印】打印机连续 3 次连不上（%s:8883），检查电源/网络/局域网模式' % ip)
        return 1

    ams = []
    a = p.get('ams') or {}
    for unit in a.get('ams', []) if isinstance(a, dict) else []:
        for t in unit.get('tray', []):
            if t.get('tray_type'):
                ams.append({'unit': unit.get('id'), 'slot': t.get('id'), 'type': t.get('tray_type'),
                            'color': t.get('tray_color'), 'remain': t.get('remain')})
    now = {'ts': int(time.time()), 'state': p.get('gcode_state'), 'percent': p.get('mc_percent'),
           'remain_min': p.get('mc_remaining_time'), 'file': p.get('subtask_name') or p.get('gcode_file'),
           'nozzle': p.get('nozzle_temper'), 'bed': p.get('bed_temper'), 'chamber': p.get('chamber_temper'),
           'firmware': p.get('ver'), 'wifi': p.get('wifi_signal'), 'error': p.get('print_error'),
           'hms': [h.get('code') if isinstance(h, dict) else h for h in (p.get('hms') or [])],
           'ams': ams, '_miss': 0}
    prev = json.loads(STATE.read_text()) if STATE.exists() else {}
    STATE.write_text(json.dumps(now, ensure_ascii=False, indent=1))

    ev = []
    ps, cs = prev.get('state'), now['state']
    name = now['file'] or '未命名'
    if cs == 'FAILED' and ps != 'FAILED':
        ev.append('【3D 打印失败】%s｜错误码 %s｜HMS %s' % (name, now['error'], now['hms'][:2]))
    elif cs == 'FINISH' and ps in ('RUNNING', 'PAUSE'):
        ev.append('【3D 打印完成】%s｜耗时约 %d 分钟' % (name, int((now['ts'] - prev.get('ts', now['ts'])) / 60)))
    if cs == 'RUNNING' and ps not in ('RUNNING', 'PAUSE'):
        ev.append('【3D 打印开始】%s' % name)
    # 耗材变化：新装料时提示
    prev_ams = prev.get('ams') or []
    if len(ams) > len(prev_ams):
        detail = '；'.join('AMS%s-%s %s %s 余%s%%' % (a['unit'], a['slot'], a['type'], a['color'], a['remain']) for a in ams)
        ev.append('【3D 打印·装料】检测到耗材：' + detail)
    new_hms = [h for h in now['hms'] if h not in (prev.get('hms') or [])]
    if new_hms and cs != 'FAILED':
        ev.append('【3D 打印告警】HMS %s（%s）' % (new_hms[:2], name))

    for line in ev:
        with EVENTS.open('a') as f:
            f.write(json.dumps({'ts': now['ts'], 'msg': line}, ensure_ascii=False) + '\n')
        if not quiet:
            notify(line)
    print('OK', cs, now['percent'], name)
    return 0

if __name__ == '__main__':
    sys.exit(main())

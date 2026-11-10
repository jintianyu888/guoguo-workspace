#!/usr/bin/env python3
"""备份前静默 v2（安全版）——2026-10-19 重写
与 v1 的区别（对应 10-18 事故复盘）：
1. 每禁用一个，立即逐条写 append-only 账本（JSONL + fsync），中断也能对账恢复
2. 显式绝不暂停：自身/守护/备份链任务（backup-quiet / backup-with-quiet / nas-push-archive）
3. 暂停数量上限 = 当前启用任务数的 70%（CAP_RATIO）
4. 恢复严格走账本：逐个恢复、逐个记账；恢复失败的任务保留在待恢复集，可重试
5. pause 前先查账本是否有未恢复的暂停（历史中断残留），有则拒绝并要求先 resume
用法: backup-quiet.py {pause|resume|status} [--dry-run] [--limit N] [--only id1,id2]
"""
import json, os, re, subprocess, sys, fcntl, datetime

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QDIR = os.path.join(WS, 'state', 'backup-quiet')
STATE = os.path.join(QDIR, 'state.json')
LEDGER = os.path.join(QDIR, 'ledger.jsonl')
LOCK = os.path.join(WS, 'state', 'work', 'backup-quiet.lock')
CAP_RATIO = 0.70
PROTECT = re.compile('备份|归档|镜像|恢复|演练|补推|告警|巡检|体检|监控|健康|磁盘|进程|IO|网络|余额|burn|watch|心跳|审计|自检|探测|错误分析|清理|静默|哨兵|backup|restore|drill|alert|health|monitor|sentinel|check|notify|watchdog|heartbeat')
SELF_ARGV = ('backup-quiet', 'backup-with-quiet', 'nas-push-archive', 'backup-mirror-verify',
              'backup-hash', 'backup-manage', 'backup-retain', 'verify-then-prune', 'restore-drill',
              'local-disk-copy', 'manifest-nightly', 'e-sync', 'h-sync', 'deh-sync', 'nas-push-queue',
              'backup-selfcheck', 'backup-fast', 'secure-cloud-backup', 'baidu-push', 'cloud-stage',
              'store-snapshot', 'eh-mirror', 'wsl-image-export', 'backup-audit-tonight',
              'backup-tier1-critical', 'backup-tier2-medium', 'backup-drill')
# 注：argv 不跑宽正则（会把 run-notify/notify 等大量任务误划入保护）；用上面备份/安全链脚本精准名单。
# run-notify 不列入：通用通知包装器，用它的任务太多，列入会大面积误保护；被暂停的任务本身不触发，无丢告警风险。


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


def ledger_append(rec):
    """账本只追加，逐条落盘（flush+fsync），这是安全版的核心。"""
    rec['ts'] = now()
    with open(LEDGER, 'a') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def cron_list():
    last = '未运行'
    for _ in range(2):  # 评审建议：失败/超时重试 1 次；timeout 90→120
        try:
            r = subprocess.run(['openclaw', 'cron', 'list', '--json'],
                               capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            last = '超时(120s)'
            continue
        if r.returncode == 0:
            d = json.loads(r.stdout)
            return d.get('jobs') if isinstance(d, dict) else d
        last = 'rc=%d: %s' % (r.returncode, r.stderr[:200])
    raise RuntimeError('cron list 失败(已重试): %s' % last)


def cron_set(action, jid):
    try:  # 评审必修2：超时不再裸抛（避免 pause/resume 循环中途崩溃），按失败记账
        r = subprocess.run(['openclaw', 'cron', action, jid],
                           capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False
    return r.returncode == 0


def is_protected(job):
    name = job.get('name') or ''
    argv = ' '.join(job.get('payload', {}).get('argv') or [])
    if PROTECT.search(name):
        return True
    return any(kw in argv for kw in SELF_ARGV)


def pending_from_ledger():
    """从账本推算仍处暂停态的任务（dict，按首次出现顺序）：有 intent 或 pause(ok)，
    且之后无 resume(ok)。两段式：disable 前先记 intent；被杀在窗口期时该任务按"可能已禁用"
    处理，resume 侧 enable 是幂等操作（对未禁用的任务 enable 无害），宁可多试不漏恢复。"""
    pending = {}
    if not os.path.exists(LEDGER):
        return pending
    for line in open(LEDGER):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue  # 坏行不致命：宁可不恢复也不误恢复
        jid = rec.get('id')
        if not jid:
            continue
        if rec.get('action') == 'pause':
            # intent(预备禁用) / done+ok(确认禁用) 都算入待恢复；done+ok=false 明确失败则不算
            if rec.get('phase') == 'intent' or (rec.get('phase') == 'done' and rec.get('ok')):
                if jid not in pending:
                    pending[jid] = rec.get('name', '')
            elif rec.get('phase') == 'done' and rec.get('ok') is False:
                pending.pop(jid, None)  # 禁用明确失败，非暂停态
        elif rec.get('action') == 'resume' and rec.get('ok'):
            pending.pop(jid, None)
    return pending


def save_state(count, capped, dropped=0):
    os.makedirs(QDIR, exist_ok=True)
    tmp = STATE + '.tmp'
    json.dump({'paused_at': now(), 'count': count, 'capped': capped,
               'dropped_by_cap': dropped}, open(tmp, 'w'), ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def do_pause(dry, limit, only_ids):
    if os.path.exists(STATE):
        print('已处于静默状态，先 resume'); return 4
    pending = pending_from_ledger()
    if pending:
        print('账本有 %d 个未恢复的历史暂停（可能上次中断），先执行 resume' % len(pending)); return 5
    jobs = cron_list()
    enabled = [j for j in jobs if j.get('enabled')]
    stop = [j for j in enabled if not is_protected(j)]
    keep = [j for j in enabled if is_protected(j)]
    if only_ids:
        only = [x.strip() for x in only_ids.split(',') if x.strip()]
        known = {j['id']: j for j in stop}
        bad = [i for i in only if i not in known]
        if bad:
            print('以下 id 不在可暂停名单（受保护或不存在），拒绝执行: %s' % bad); return 6
        stop = [known[i] for i in only]
    capped, dropped = False, 0
    cap = int(len(enabled) * CAP_RATIO)
    if len(stop) > cap:
        dropped = len(stop) - cap
        stop = stop[:cap]
        capped = True
    if limit is not None:
        stop = stop[:limit]
    print('[统计] 启用 %d / 保护 %d / 计划暂停 %d（上限 %d）%s'
          % (len(enabled), len(keep), len(stop), cap, '【触顶裁剪 %d 个】' % dropped if capped else ''))
    for i, n in [(j['id'], j.get('name') or '') for j in stop]:
        print('  暂停', n)
    if dry:
        print('== 试运行，未实际暂停 =='); return 0
    ok = 0
    for j in stop:
        jid, name = j['id'], j.get('name') or ''
        ledger_append({'action': 'pause', 'phase': 'intent', 'id': jid, 'name': name})  # 两段式：动作前先记 intent
        if cron_set('disable', jid):
            ok += 1
            ledger_append({'action': 'pause', 'phase': 'done', 'ok': True, 'id': jid, 'name': name})
        else:
            ledger_append({'action': 'pause', 'phase': 'done', 'ok': False, 'id': jid, 'name': name})
            print('  禁用失败(已记账):', name)
    save_state(ok, capped, dropped)
    print('已暂停并记账 %d/%d 个（逐条已落盘 %s）' % (ok, len(stop), LEDGER))
    return 0


def do_resume(dry):
    pending = pending_from_ledger()
    state_existed = os.path.exists(STATE)
    if not pending and not state_existed:
        print('无静默状态，无需恢复'); return 0
    if dry:
        print('将恢复 %d 个：' % len(pending))
        for jid, name in list(pending.items()):  # 同主循环：只遍历当前待恢复集
            print('  -', name)
        return 0
    ok = fail = 0
    for jid, name in list(pending.items()):  # 评审修正：只遍历当前待恢复集，历史已恢复的不再索引（KeyError 修复）
        if cron_set('enable', jid):
            ok += 1
            ledger_append({'action': 'resume', 'ok': True, 'id': jid, 'name': name})
        else:
            fail += 1
            ledger_append({'action': 'resume', 'ok': False, 'id': jid, 'name': name})
            print('  恢复失败(账本保留，可重试):', name)
    still = pending_from_ledger()
    if not still and state_existed:
        os.remove(STATE)
        print('全部恢复完成，状态已清除')
    print('RESUMED=%d FAIL=%d PENDING=%d' % (ok, fail, len(still)))
    return 0 if fail == 0 else 1


def do_status():
    state = None
    if os.path.exists(STATE):
        state = json.load(open(STATE))
        print('静默中，自 %s，账面 %d 个' % (state.get('paused_at'), state.get('count')))
    pending = pending_from_ledger()
    print('账本待恢复: %d 个' % len(pending))
    if state and len(pending) != state.get('count', -1):
        print('⚠️ 状态文件与账本不一致（可能中断），执行 resume 按账本为准')
    if not state and pending:
        print('⚠️ 无状态文件但账本有暂停（中断残留），执行 resume 可自愈')
    if not state and not pending:
        print('未静默')
    return 0


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'status'
    dry = '--dry-run' in sys.argv
    limit = None
    only_ids = ''
    for a in sys.argv[2:]:
        if a.startswith('--limit='):
            limit = int(a.split('=', 1)[1])
        elif a.startswith('--only='):
            only_ids = a.split('=', 1)[1]
        elif a == '--limit' and sys.argv.index(a) + 1 < len(sys.argv):
            limit = int(sys.argv[sys.argv.index(a) + 1])
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lf = open(LOCK, 'w')
    try:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('已有静默进程在跑'); return 3
    os.makedirs(QDIR, exist_ok=True)
    if action == 'status':
        return do_status()
    if action == 'pause':
        return do_pause(dry, limit, only_ids)
    if action == 'resume':
        return do_resume(dry)
    print('用法: backup-quiet.py {pause|resume|status} [--dry-run] [--limit N] [--only id1,id2]')
    return 2


if __name__ == '__main__':
    sys.exit(main())

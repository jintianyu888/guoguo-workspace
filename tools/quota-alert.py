#!/usr/bin/env python3
"""quota-alert.py —— 额度页告警队列（2026-10-31 主公令：额度告警交维护管家处理）
用法: quota-alert.py add "<msg>" | pending | ack <id> [<id>...] | prune
去重: 同一 msg 6 小时内未处理则不再重复入队；已处理的不再提醒。
"""
import sys, json, os, time, hashlib

Q = "/home/j/.openclaw/workspace/state/alert/quota-queue.jsonl"
DEDUPE_SECS = 6 * 3600
LOCK = Q + ".lock"

def load():
    if not os.path.exists(Q): return []
    out = []
    with open(Q, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: out.append(json.loads(line))
            except Exception: pass
    return out

def save(items):
    os.makedirs(os.path.dirname(Q), exist_ok=True)
    tmp = Q + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for it in items: f.write(json.dumps(it, ensure_ascii=False) + "\n")
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, Q)

def main():
    if len(sys.argv) < 2: print(__doc__); return 2
    cmd = sys.argv[1]
    items = load()
    now = int(time.time())
    if cmd == "add":
        msg = " ".join(sys.argv[2:]).strip()
        if not msg: return 2
        for it in items:
            if it.get("msg") == msg and not it.get("done") and now - it.get("ts", 0) < DEDUPE_SECS:
                print("duplicate-skip", it["id"]); return 0
        eid = hashlib.sha256((msg + str(now)).encode()).hexdigest()[:8]
        items.append({"id": eid, "ts": now, "msg": msg, "done": False, "acked_at": None})
        save(items); print("queued", eid); return 0
    if cmd == "pending":
        pend = [i for i in items if not i.get("done")]
        pend.sort(key=lambda x: x.get("ts", 0))
        if not pend: print("PENDING 0"); return 0
        print(f"PENDING {len(pend)}")
        for i in pend:
            print(f"- {i['id']} {time.strftime('%m-%d %H:%M', time.localtime(i['ts']))} {i['msg'][:160]}")
        return 0
    if cmd == "ack":
        ids = set(sys.argv[2:])
        n = 0
        for i in items:
            if i["id"] in ids and not i.get("done"):
                i["done"] = True; i["acked_at"] = now; n += 1
        save(items); print("acked", n); return 0
    if cmd == "prune":
        keep = [i for i in items if not (i.get("done") and now - (i.get("acked_at") or 0) > 30 * 86400)]
        save(keep); print("pruned", len(items) - len(keep)); return 0
    print("unknown cmd"); return 2

if __name__ == "__main__":
    sys.exit(main())

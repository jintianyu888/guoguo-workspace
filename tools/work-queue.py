#!/usr/bin/env python3
"""负载感知工作队列：重活排队，只在 CPU ≤ 目标时逐个取活干。
用法:
  work-queue.py add <type> <path> [说明...]   入队
  work-queue.py list                          看队列
  work-queue.py drain [--target 50]           取一件活（跑完出队）
类型: ocr（扫描件转文本） | whisper（音视频转写）
"""
import argparse, json, os, subprocess, sys, time

Q = os.path.expanduser("~/.openclaw/workspace/state/work-queue.json")
TOOLS = os.path.expanduser("~/.openclaw/workspace/tools")
GATE = os.path.join(TOOLS, "load-gate.py")

# 限核：只让重活跑在前一半核上（16 核 → 0-7 ≈ 50%），避免飙满
_HALF = max(1, (os.cpu_count() or 2) // 2)
AFF = ["taskset", "-c", f"0-{_HALF - 1}"] if os.path.exists("/usr/bin/taskset") or os.path.exists("/bin/taskset") else []

def load():
    if os.path.exists(Q):
        try: return json.load(open(Q))
        except Exception: return []
    return []

def save(q):
    os.makedirs(os.path.dirname(Q), exist_ok=True)
    json.dump(q, open(Q, "w"), ensure_ascii=False, indent=1)

def cpu_util(sample=0.5):
    def snap():
        with open('/proc/stat') as f: v=[int(x) for x in f.readline().split()[1:]]
        return v[3]+v[4], sum(v)
    i0,t0=snap(); time.sleep(sample); i1,t1=snap()
    return 100*(1-(i1-i0)/max(1,(t1-t0)))

p = argparse.ArgumentParser()
p.add_argument("action", choices=["add","list","drain","util"])
p.add_argument("rest", nargs="*")
p.add_argument("--target", type=float, default=50.0)
a = p.parse_args()

if a.action == "add":
    if len(a.rest) < 2:
        print("用法: work-queue.py add <type> <path> [说明]"); sys.exit(1)
    q = load()
    q.append({"type": a.rest[0], "path": a.rest[1],
              "note": " ".join(a.rest[2:]), "added": time.strftime("%Y-%m-%d %H:%M")})
    save(q); print(f"✅ 已入队（当前 {len(q)} 件）")

elif a.action == "list":
    q = load()
    if not q: print("（队列空）")
    for i, t in enumerate(q, 1):
        print(f"{i}. {t['type']} · {os.path.basename(t['path'])} · {t.get('note','')} · {t['added']}")

elif a.action == "util":
    print(f"{cpu_util():.1f}")

elif a.action == "drain":
    q = load()
    if not q:
        print("QUEUE_EMPTY"); sys.exit(0)
    u = cpu_util()
    if u > a.target:
        print(f"BUSY {u:.0f}%"); sys.exit(0)
    t = q[0]
    print(f"▶️ 开始：{t['type']} · {os.path.basename(t['path'])}")
    if t["type"] == "ocr":
        out = os.path.splitext(t["path"])[0] + ".txt"
        cmd = ["nice","-n","10"] + AFF + [sys.executable,GATE,"--target",str(a.target),"--",
               os.path.join(TOOLS,"ocr-file"), t["path"], "--out", out]
    elif t["type"] == "whisper":
        out = os.path.dirname(t["path"])
        cmd = ["nice","-n","10"] + AFF + [sys.executable,GATE,"--target",str(a.target),"--",
               sys.executable, os.path.join(TOOLS,"whisper-wrapper.py"), t["path"],
               "--output_format","txt","--output_dir",out,"--language","zh"]
    else:
        print(f"❓ 未知类型 {t['type']}，跳过"); q.pop(0); save(q); sys.exit(0)
    rc = subprocess.run(cmd).returncode
    if rc == 0:
        q.pop(0); save(q)
        print(f"✅ 完成并出队（剩 {len(q)} 件）")
    else:
        print(f"⚠️ 失败（退出码 {rc}），保留在队列待重试")

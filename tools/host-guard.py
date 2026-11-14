#!/usr/bin/env python3
"""host-guard.py — WSL 保命看门狗（零 token，2026-11-14 主公令）
目的：A/B 抢 GPU、网关内存上涨时，先自己降载，别让整台 WSL 卡死。

规则：
1. MemAvailable < 2500MB -> 降载：停 oc-face-guard（摄像头流最吃内存/设备），记状态
2. 降载后 MemAvailable > 4000MB 连续 3 次(>=6min) -> 自动恢复 oc-face-guard
3. 网关 RSS > 8.5GB 或 load1 > 24 -> 只告警（cóoldown 30min），不重启
4. 任何动作写 state/host-guard/guard.log；状态存 state/host-guard/state.json
"""
import json, os, subprocess, time

WS = "/home/j/.openclaw/workspace"
DIR = os.path.join(WS, "state/host-guard")
os.makedirs(DIR, exist_ok=True)
LOG = os.path.join(DIR, "guard.log")
STATE = os.path.join(DIR, "state.json")

MEM_LOW_KB = int(os.environ.get("HG_MEM_LOW_KB", 2500 * 1024))
MEM_OK_KB = int(os.environ.get("HG_MEM_OK_KB", 4000 * 1024))
RSS_LIMIT_KB = 8_500_000
LOAD_LIMIT = float(os.environ.get("HG_LOAD_LIMIT", "24.0"))
COOLDOWN = int(os.environ.get("HG_COOLDOWN", "1800"))


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    with open(LOG, "a") as f:
        f.write(line + "\n")
    print(line)


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"throttled": False, "ok_streak": 0, "last_alert": 0}


def save_state(s):
    json.dump(s, open(STATE, "w"))


def mem_available_kb():
    for ln in open("/proc/meminfo"):
        if ln.startswith("MemAvailable:"):
            return int(ln.split()[1])
    return 0


def rss_kb(pid):
    try:
        for ln in open("/proc/%d/status" % pid):
            if ln.startswith("VmRSS:"):
                return int(ln.split()[1])
    except Exception:
        pass
    return 0


def gateway_pid():
    try:
        out = subprocess.run(["systemctl", "--user", "show", "openclaw-gateway.service", "-p", "MainPID", "--value"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return int(out)
    except Exception:
        return 0


def notify(msg):
    if os.environ.get("HG_NO_NOTIFY"):
        return
    try:
        subprocess.run(["bash", os.path.join(WS, "tools/notify.sh"), "host-guard", msg],
                       capture_output=True, text=True, timeout=25)
    except Exception:
        pass


def unit_active(u):
    try:
        return subprocess.run(["systemctl", "--user", "is-active", u], capture_output=True, text=True,
                              timeout=10).stdout.strip() == "active"
    except Exception:
        return False


def ctl(action, unit):
    try:
        subprocess.run(["systemctl", "--user", action, unit], capture_output=True, text=True, timeout=45)
        return True
    except Exception:
        return False


def main():
    st = load_state()
    avail = mem_available_kb()
    pid = gateway_pid()
    rss = rss_kb(pid) if pid else 0
    load1 = os.getloadavg()[0]

    if not st["throttled"] and avail < MEM_LOW_KB:
        if unit_active("oc-face-guard.service") and ctl("stop", "oc-face-guard.service"):
            log("降载：MemAvailable=%dMB < %dMB，已停 oc-face-guard" % (avail // 1024, MEM_LOW_KB // 1024))
            notify("内存吃紧（可用 %d MB），已自动停掉摄像头守卫降载" % (avail // 1024))
        else:
            log("内存吃紧（可用 %dMB）但摄像头守卫未在跑，仅记录" % (avail // 1024))
        st["throttled"] = True
        st["ok_streak"] = 0
        save_state(st)
        return

    if st["throttled"]:
        if avail > MEM_OK_KB:
            st["ok_streak"] += 1
        else:
            st["ok_streak"] = 0
        if st["ok_streak"] >= 3:
            if ctl("start", "oc-face-guard.service"):
                log("恢复：MemAvailable=%dMB，重启 oc-face-guard" % (avail // 1024))
            st["throttled"] = False
            st["ok_streak"] = 0
        save_state(st)
        return

    now = time.time()
    if (rss > RSS_LIMIT_KB or load1 > LOAD_LIMIT) and now - st.get("last_alert", 0) > COOLDOWN:
        msg = "网关内存 %.1fGB / load1 %.1f，注意（不自动重启）" % (rss / 1048576.0, load1)
        log("告警：" + msg)
        notify(msg)
        st["last_alert"] = now
        save_state(st)


if __name__ == "__main__":
    main()

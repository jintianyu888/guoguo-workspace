#!/usr/bin/env python3
"""io-stuck-watch.py v2 (2026-10-17)
分类式 IO 体检：区分「9p/Windows 盘正常等待」与「真·卡死」，只在真异常时告警。
判据（v4-pro + glm-5.3 双评审后定稿）：
  A. wchan 命中 p9/v9fs/rpc 或命令涉及 /mnt/ → 9p 正常等待，只记录不告警
  B. 原生盘 D 态 → 观察 voluntary_ctxt_switches 是否增长；有增长=在推进，不告警
  C. 仅当 原生盘 + 无 9p 特征 + 上下文切换零增长 + 持续超过阈值 才告警
  不自动 kill（评审一致：误杀代价高于收益）
用法: io-stuck-watch.py [--alert-seconds N] [--print-ok] [--json]
退出码: 0
"""
import os, sys, json, datetime, argparse

W = "/home/j/.openclaw/workspace"
LOG = os.path.join(W, "state", "io-stuck.log")
STATE = os.path.join(W, "state", "io-stuck-state.json")
MOUNTS = ("/mnt/",)

def now_s(): return datetime.datetime.now().strftime("%F %T")
def now_ts(): return datetime.datetime.now().timestamp()

def load_state():
    try:
        with open(STATE, encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def save_state(s):
    tmp = STATE + ".t"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(s, f, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)

def read_file(p, limit=4096):
    try:
        with open(p, "rb") as f: return f.read(limit).decode("utf-8", "replace")
    except Exception: return ""

def d_pids():
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit(): continue
        try:
            with open("/proc/%s/stat" % d, encoding="utf-8", errors="replace") as f:
                st = f.read()
            rp = st.rfind(")")
            fields = st[rp+2:].split()
            if fields and fields[0] == "D": out.append(int(d))
        except Exception: continue
    return out

def proc_info(pid):
    info = {"pid": pid, "wchan": "", "cmd": "", "comm": "", "rr": 0, "wr": 0, "ctxt": 0, "elapsed": 0}
    info["comm"] = read_file("/proc/%d/comm" % pid, 64).strip()
    cmd = read_file("/proc/%d/cmdline" % pid, 2048).replace("\x00", " ").strip()
    info["cmd"] = cmd or info["comm"]
    info["wchan"] = read_file("/proc/%d/wchan" % pid, 128).strip()
    io = read_file("/proc/%d/io" % pid, 512)
    for line in io.splitlines():
        if line.startswith("read_bytes:"): info["rr"] = int(line.split()[1])
        elif line.startswith("write_bytes:"): info["wr"] = int(line.split()[1])
    stt = read_file("/proc/%d/status" % pid, 4096)
    for line in stt.splitlines():
        if line.startswith("voluntary_ctxt_switches:"):
            try: info["ctxt"] = int(line.split()[1])
            except Exception: pass
    try:
        with open("/proc/%d/stat" % pid, encoding="utf-8", errors="replace") as f: s = f.read()
        starttime = int(s[s.rfind(")")+2:].split()[19])
        with open("/proc/uptime") as f: up = float(f.read().split()[0])
        info["elapsed"] = int(up - starttime / os.sysconf("SC_CLK_TCK"))
    except Exception: pass
    return info

def classify(i):
    """返回 (类别, 是否告警)"""
    wc = (i["wchan"] or "").lower()
    cmd = i["cmd"]
    if any(k in wc for k in ("p9", "v9fs", "9p", "rpciod", "nfs")) or any(m in cmd for m in MOUNTS):
        return ("9p/Windows盘等待(正常)", False)
    return ("原生盘D态", True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert-seconds", type=int, default=900)
    ap.add_argument("--print-ok", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    st = load_state()
    pids = d_pids()
    now = now_ts()
    lines, alerts, seen = [], [], {}

    for pid in pids:
        i = proc_info(pid)
        kind, cand = classify(i)
        prev = st.get(str(pid), {})
        first = prev.get("first") or now
        dur = int(now - first)
        ctxt_prev = prev.get("ctxt")
        progressing = (ctxt_prev is None) or (i["ctxt"] != ctxt_prev) or (i["rr"] + i["wr"] != prev.get("bytes", -1))
        tag = "正常" if not cand else ("推进中" if progressing else "无进展")
        seen[str(pid)] = {"first": first, "ctxt": i["ctxt"], "bytes": i["rr"] + i["wr"], "cmd": i["cmd"][:200], "kind": kind, "tag": tag}

        changed = prev.get("tag") != tag
        hard_cap = cand and not progressing and dur >= max(a.alert_seconds, 4 * 3600)
        if changed or hard_cap:
            lines.append("%s D %s pid=%d dur=%ds wchan=%s %s [%s]" % (now_s(), i["comm"], pid, dur, i["wchan"] or "-", i["cmd"][:100], tag))

        if cand and not progressing and dur >= a.alert_seconds:
            alerts.append(i)

    for k in list(st.keys()):
        if k not in seen: del st[k]
    st.update(seen)
    save_state(st)

    with open(LOG, "a", encoding="utf-8") as f:
        for l in lines: f.write(l + "\n")

    if a.json:
        print(json.dumps({"d_state": len(pids), "alerts": [{"pid": x["pid"], "cmd": x["cmd"][:120], "elapsed": x["elapsed"], "wchan": x["wchan"]} for x in alerts]}, ensure_ascii=False))
        return 0

    if alerts:
        out = ["🧊 IO 哨兵：发现 %d 个真·卡死候选（非 9p 等待）" % len(alerts)]
        for i in alerts:
            out.append("· pid=%d %s｜已 D 态 %d 分钟｜wchan=%s｜命令 %s" % (
                i["pid"], i["comm"], max(1, i["elapsed"] // 60), i["wchan"] or "-", i["cmd"][:90]))
        out.append("—— 判定：原生盘且上下文切换零增长，属真卡死候选；我可按需清理，默认不动。")
        print("\n".join(out))
    elif a.print_ok:
        print("IO 体检正常：D 态 %d 个，均属 9p/Windows 盘等待或推进中" % len(pids))
    return 0

if __name__ == "__main__":
    sys.exit(main())

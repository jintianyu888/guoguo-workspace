#!/usr/bin/env python3
"""owner-todo-sync.py v0.1 — 把「必须主公本人操作」的自检发现自动写入待办台账
台账：state/tasks/tasks.json（items 列表，footer 唯一数据源）
去重：state/work/owner-todo.json 记录 key → task id；已完成且冷却期内不重复加
只读检查 + 只追加台账，不改任何系统配置。
"""
import json, os, re, subprocess, sys
from datetime import datetime, timedelta

WS = "/home/j/.openclaw/workspace"
LEDGER = WS + "/state/tasks/tasks.json"
REG = WS + "/state/work/owner-todo.json"
DOC = "docs/主公待办-20261020.md"

def sh(cmd, t=20):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t)
        return (p.stdout or "").strip()
    except Exception:
        return ""

def gateway_rss_mb():
    pid = sh("pgrep -f 'openclaw.*gateway' | head -1")
    if not pid.isdigit(): return None
    try:
        for ln in open("/proc/%s/status" % pid):
            if ln.startswith("VmRSS:"):
                return int(ln.split()[1]) // 1024
    except Exception:
        return None
    return None

def checks():
    out = []
    rss = gateway_rss_mb()
    soft = 8192
    raw = sh("systemctl --user show openclaw-gateway -p MemoryHigh 2>/dev/null")
    try:
        v = int(raw.split("=")[1].strip())
        if v > 0: soft = v // (1024 * 1024)
    except Exception:
        pass
    if rss and rss > soft * 0.85:
        out.append(("maint-gateway-memory", "P1", "🔧需主公：网关内存 %dMB 接近软限 %dMB，择机重启清理" % (rss, soft),
                    "步骤见 %s §1；重启会断 20-30 秒，需您点头" % DOC))
    if not sh("command -v clamscan"):
        out.append(("maint-clamav", "P1", "🔧需主公：ClamAV 未安装，杀毒扫描是假绿，需 sudo 密码安装",
                    "步骤见 %s §2（apt install clamav + freshclam）" % DOC))
    if not os.path.exists(os.path.expanduser("~/.config/hik-nvr.env")):
        out.append(("maint-nvr", "P2", "🔧需主公：NVR 密码缺失，人脸扫描连续失败，需加密窗口重发",
                    "步骤见 %s §3" % DOC))
    ver = sh("openclaw --version", 25)
    m = re.search(r"(\d{4}\.\d+\.\d+)", ver or "")
    if m and m.group(1) < "2026.10.5":
        out.append(("maint-update", "P2", "🔧需主公：可升级 v2026.10.5（含上次遗留迁移修复），需跑 修复系统.bat",
                    "步骤见 %s §4；跑前我会先备份" % DOC))
    rc = sh("timeout 8 ssh -o BatchMode=yes -o ConnectTimeout=5 nas 'echo ok' 2>/dev/null", 15)
    if "ok" not in rc:
        out.append(("maint-nas-ssh", "P2", "🔧需主公：群晖 SSH 不通，历史缺口归档补推不了",
                    "步骤见 %s §5" % DOC))
    out.append(("maint-secrets", "P2", "🔧需主公：7 个管家 Secret 待录入（有用/干活/信息板/项目/公司1-3）",
                "步骤见 %s §6；加密窗口一次一个" % DOC))
    out.append(("maint-ds-key", "P3", "🔧需主公：DeepSeek 密钥明文迁移 go/no-go（迁移后需轮换旧 key）",
                "步骤见 %s §7" % DOC))
    return out

def main():
    now = datetime.now()
    dry = "--dry-run" in sys.argv
    reg = {}
    try: reg = json.load(open(REG))
    except Exception: pass
    d = json.load(open(LEDGER))
    items = d.get("items") or []
    by_id = {it.get("id") or it.get("key"): it for it in items}
    maxno = max([it.get("no") or 0 for it in items] + [0])
    added = []
    for key, prio, title, note in checks():
        prev = reg.get(key)
        if prev:
            pid = prev.get("id")
            it = by_id.get(pid)
            if it and it.get("status") != "done":
                it["title"] = title  # 刷新数值（如内存大小）
                it["note"] = note
                continue
            if it and it.get("status") == "done":
                done_at = it.get("done_at") or it.get("updated") or ""
                try:
                    if datetime.fromisoformat(done_at) > now - timedelta(days=7):
                        continue
                except Exception:
                    pass
        maxno += 1
        tid = "T-%s-%04d" % (now.strftime("%Y%m%d"), maxno)
        items.append({"no": maxno, "id": tid, "title": title, "status": "pending",
                      "priority": prio, "owner": "主公", "created": now.strftime("%Y-%m-%d"),
                      "updated": now.strftime("%Y-%m-%d"), "note": note, "auto_key": key})
        reg[key] = {"id": tid, "added": now.strftime("%Y-%m-%d %H:%M")}
        added.append(title)
    d["items"] = items
    d["updated"] = now.isoformat(timespec="seconds")
    os.makedirs(os.path.dirname(REG), exist_ok=True)
    if dry:
        print("dry-run: 将新增 %d 条" % len(added)); [print(" -", a) for a in added]; return 0
    tmp = LEDGER + ".tmp"
    with open(tmp, "w") as f: json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LEDGER)
    json.dump(reg, open(REG, "w"), ensure_ascii=False, indent=1)
    print("新增 %d 条待办（主公操作）" % len(added))
    for a in added: print(" -", a)
    return 0

if __name__ == "__main__":
    sys.exit(main())

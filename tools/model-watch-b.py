#!/usr/bin/env python3
"""B 机新模型自动跟踪：发现→试装→实测→记账→通知（2026-10-30 主公令）

用法:
  python3 tools/model-watch-b.py --seed     # 首次：把现有库记录为已知（只记不测）
  python3 tools/model-watch-b.py            # 常态：发现新模型 → 限量试装 → 实测
  python3 tools/model-watch-b.py --dry      # 只看会做什么，不动手
限制: 单次最多试装 1 个；体积上限 22GB；B 机保留上限 4 个（超过只标记，删除需节点或人工）
"""
import json, os, re, subprocess, sys, time, urllib.request

WS = "/home/j/.openclaw/workspace"
STATE = os.path.join(WS, "state/model-econ/model-watch.json")
LEDGER = os.path.join(WS, "state/work/model-bench-b.md")
OLLAMA = "http://127.0.0.1:11434"
REG = "https://registry.ollama.ai/v2/library"
MAX_GB = 22.0
MAX_TRY_PER_RUN = 1
KEEP_MAX = 4


def http_get(url, timeout=40, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def library_names():
    html = http_get("https://ollama.com/library?sort=newest").decode("utf-8", "ignore")
    names = re.findall(r'href="/library/([a-zA-Z0-9._\-]+)"', html)
    out = []
    for n in names:
        if n not in out and n not in ("library", "tags"):
            out.append(n)
    return out


def manifest_size_gb(name, tag="latest"):
    try:
        raw = http_get(REG + "/" + name + "/manifests/" + tag, 25,
                       {"Accept": "application/vnd.docker.distribution.manifest.v2+json"})
        d = json.loads(raw)
        total = sum(l.get("size", 0) for l in d.get("layers", []))
        return round(total / 1e9, 1)
    except Exception:
        return None


def installed():
    try:
        d = json.loads(http_get(OLLAMA + "/api/tags", 20))
        return {m["name"]: round(m["size"] / 1e9, 1) for m in d.get("models", [])}
    except Exception:
        return {}


def pull(model, timeout=7200):
    body = json.dumps({"model": model, "stream": True}).encode()
    req = urllib.request.Request(OLLAMA + "/api/pull", data=body,
                                 headers={"Content-Type": "application/json"})
    last = None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for line in r:
            try:
                d = json.loads(line.decode())
            except Exception:
                continue
            if d.get("total"):
                last = (d.get("completed", 0), d["total"])
            if d.get("status") == "success":
                return True, "ok"
    return False, str(last)


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"known": [], "tested": {}, "updated": None}


def save_state(st):
    st["updated"] = time.strftime("%F %T")
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE)


def notify(msg):
    try:
        subprocess.run(["timeout", "60", "bash", os.path.join(WS, "tools/notify.sh"), msg],
                       cwd=WS, capture_output=True, timeout=90)
    except Exception:
        pass


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    seed = "--seed" in args
    st = load_state()
    names = library_names()
    if not names:
        print("库列表抓取失败")
        return 1
    known = set(st.get("known") or [])
    new = [n for n in names if n not in known]
    print("库内模型 %d 个，已知 %d 个，新增 %d 个" % (len(names), len(known), len(new)))
    if seed:
        st["known"] = sorted(set(names) | known)
        save_state(st)
        print("已记录为已知基线（不试装）")
        return 0
    tried = 0
    for n in new:
        if tried >= MAX_TRY_PER_RUN:
            print("本次已达试装上限 %d 个，其余留待下次" % MAX_TRY_PER_RUN)
            break
        size = manifest_size_gb(n)
        if size is None:
            print("- %s：拿不到体积，跳过" % n)
            known.add(n)
            continue
        if size > MAX_GB:
            print("- %s：%.1fG 超上限 %.0fG，跳过" % (n, size, MAX_GB))
            known.add(n)
            continue
        inst = installed()
        if any(k.split(":")[0] == n for k in inst):
            print("- %s：已装，记入已知" % n)
            known.add(n)
            continue
        print("- %s：%.1fG，符合条件 → 试装" % (n, size))
        if dry:
            continue
        ok, info = pull(n)
        if not ok:
            print("  下载失败：%s" % info)
            continue
        tried += 1
        known.add(n)
        subprocess.run(["timeout", "1800", "python3", os.path.join(WS, "tools/bench-suite-b.py"), n],
                       cwd=WS)
        st["tested"][n] = {"at": time.strftime("%F %T"), "size_gb": size}
        notify("B机新模型已试测：%s（%.1fG），结果见 model-bench-b.md" % (n, size))
    st["known"] = sorted(known)
    save_state(st)
    print("完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())

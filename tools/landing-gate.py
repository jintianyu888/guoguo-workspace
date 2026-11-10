#!/usr/bin/env python3
"""landing-gate.py —— 双审闸门（2026-10-29 主公令：规矩写死，不靠自觉）
subcommands:
  hash                    打印敏感文件清单及内容哈希
  record --task F --models A,B --verdicts GO,GO   写双审回执（绑定当前内容哈希）
  check                   校验当前敏感文件内容是否都有匹配回执；有缺口 exit 1
  scan                    巡检：发现无回执的敏感改动 -> 告警并记录（不自动回滚）
"""
import argparse, hashlib, json, os, subprocess, sys, time
W = "/home/j/.openclaw/workspace"
REV = os.path.join(W, "state/reviews")
SENSITIVE_DIRS = ["tools"]
SENSITIVE_FILES = ["USER.md", "MEMORY.md", "AGENTS.md", "SOUL.md", "BOOT.md"]
SENSITIVE_EXT = (".sh", ".py", ".service", ".timer")
SKIP_PREFIX = ("tools/_archive/", "tools/models/", "tools/asr-venv/", "tools/embed-venv/")

def sensitive_paths():
    out = []
    for d in SENSITIVE_DIRS:
        for root, dirs, files in os.walk(os.path.join(W, d)):
            rel = os.path.relpath(root, W) + "/"
            if any(rel.startswith(p) for p in SKIP_PREFIX):
                dirs[:] = []
                continue
            for f in files:
                if f.endswith(SENSITIVE_EXT):
                    out.append(os.path.join(root, f))
    for f in SENSITIVE_FILES:
        p = os.path.join(W, f)
        if os.path.exists(p):
            out.append(p)
    return sorted(out)

def h(p):
    try:
        with open(p, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return "ERR"

def manifest():
    return {os.path.relpath(p, W): h(p) for p in sensitive_paths()}

def load_receipts():
    os.makedirs(REV, exist_ok=True)
    rec = []
    for fn in sorted(os.listdir(REV)):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(REV, fn)) as fh:
                    rec.append(json.load(fh))
            except Exception:
                pass
    return rec

def cmd_hash(a):
    m = manifest()
    print(json.dumps(m, ensure_ascii=False, indent=0))

def cmd_record(a):
    models = [x.strip() for x in a.models.split(",") if x.strip()]
    verdicts = [x.strip().upper() for x in a.verdicts.split(",") if x.strip()]
    if len(models) < 2:
        sys.exit("需要 >=2 个不同厂商模型")
    if len(set(models)) != len(models):
        sys.exit("评审模型重复，需不同厂商")
    if len(verdicts) != len(models):
        sys.exit("verdicts 数量须与 models 一致")
    if any(v.startswith("VETO") or v.startswith("否决") for v in verdicts):
        sys.exit("存在否决，禁止落地")
    os.makedirs(REV, exist_ok=True)
    m = manifest()
    digest = hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()[:16]
    r = {"id": digest, "ts": time.strftime("%F %T"), "task": a.task,
         "models": models, "verdicts": verdicts, "files": m}
    p = os.path.join(REV, digest + ".json")
    with open(p, "w") as fh:
        json.dump(r, fh, ensure_ascii=False, indent=1)
    print("回执已写:", p)

def cmd_check(a):
    m = manifest()
    recs = load_receipts()
    matched = [r for r in recs if r.get("files") == m]
    if matched:
        print("OK 双审回执匹配:", matched[-1]["id"], matched[-1]["models"])
        return 0
    print("BLOCK 敏感文件当前内容没有匹配的双审回执", file=sys.stderr)
    print("  请先跑 tools/cross-review.sh 拿双 GO，再 landing-gate.py record", file=sys.stderr)
    return 1

def cmd_scan(a):
    m = manifest()
    state = os.path.join(W, "state/reviews/baseline.json")
    prev = {}
    if os.path.exists(state):
        try:
            prev = json.load(open(state)).get("files", {})
        except Exception:
            prev = {}
    changed = [f for f, v in m.items() if prev.get(f) and prev[f] != v]
    recs = load_receipts()
    ok_files = set()
    for r in recs:
        for f, v in (r.get("files") or {}).items():
            if m.get(f) == v:
                ok_files.add(f)
    bad = [f for f in changed if f not in ok_files]
    json.dump({"ts": time.strftime("%F %T"), "files": m}, open(state, "w"))
    if bad:
        print("违规改动（无回执）:", len(bad))
        for f in bad[:10]:
            print("  -", f)
        open(os.path.join(W, "state/reviews/violations.log"), "a").write(
            time.strftime("%F %T") + " " + " ".join(bad) + "\n")
        return 1
    print("巡检通过：无未审改动")
    return 0

p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="c", required=True)
sub.add_parser("hash").set_defaults(f=cmd_hash)
r = sub.add_parser("record"); r.add_argument("--task", default=""); r.add_argument("--models", required=True); r.add_argument("--verdicts", required=True); r.set_defaults(f=cmd_record)
sub.add_parser("check").set_defaults(f=cmd_check)
sub.add_parser("scan").set_defaults(f=cmd_scan)
a = p.parse_args()
sys.exit(a.f(a) or 0)

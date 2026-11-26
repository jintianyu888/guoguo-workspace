#!/usr/bin/env python3
"""upgrade-decide.py —— 08:00 窗口前的自动升级判定（2026-11-22 主公令，零 token）

新策略：出现新稳定版 + 当日 01:00 备份完整性通过 → 自动写判定件与批准件，
        由 restart-window.sh 走既有升级分支（含自检、体检、失败自动回滚）。
不再要求 7 天成熟度，不再需要人工批准件。

用法：python3 tools/upgrade-decide.py [--dry-run] [--json]
退出码：0 = 判定完成（无论升不升级）；1 = 判定失败（读不到版本等）
"""
import argparse, json, os, subprocess, sys, time

W = "/home/j/.openclaw/workspace"
ARM = os.path.join(W, "state/work/.upgrade-armed")
APPR = os.path.join(W, "state/work/.upgrade-approved")
LOG = os.path.join(W, "state/work/upgrade-decide.log")

def sh(cmd, timeout=90):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"

def installed():
    rc, out, _ = sh("openclaw --version", 40)
    if rc != 0 or not out:
        return ""
    for tok in out.replace("(", " ").split():
        t = tok.strip()
        if t[:4].isdigit() and t.count(".") >= 2:
            return t
    return ""

def latest_stable():
    rc, out, _ = sh("npm view openclaw dist-tags --json", 60)
    if rc != 0 or not out:
        return "", ""
    try:
        d = json.loads(out)
    except Exception:
        return "", ""
    return d.get("latest", ""), d.get("beta", "")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    cur = installed()
    latest, beta = latest_stable()
    result = {"installed": cur, "latest": latest, "action": "", "reason": ""}

    if not cur:
        result.update(action="error", reason="读不到当前安装版本")
        _emit(a, result)
        return 1
    if not latest:
        result.update(action="error", reason="读不到 npm latest（网络？）")
        _emit(a, result)
        return 1
    if "beta" in latest or "rc" in latest or "alpha" in latest:
        result.update(action="skip", reason="latest 是预发布版 " + latest)
        _emit(a, result)
        return 0
    if cur == latest:
        for f in (ARM, APPR):
            try: os.remove(f)
            except FileNotFoundError: pass
        result.update(action="uptodate", reason="已是最新 " + cur)
        _emit(a, result)
        return 0

    rc, out, err = sh("bash " + W + "/tools/backup-integrity.sh --quiet", 300)
    if rc != 0:
        result.update(action="blocked", reason="备份完整性未通过：" + (err or out)[:200])
        _emit(a, result)
        return 0

    # 2026-11-26 主公令：恢复"提案制"——判定结果只写提案，不自动批准
    # （11.10 事故期间 policy-auto 自动批准导致无人确认就上了坏版本）
    approved = None
    try:
        approved = json.load(open(APPR, encoding="utf-8")).get("target")
    except Exception:
        approved = None
    if approved == latest:
        result.update(action="arm", reason="新版本 " + latest + " + 备份完整 + 已有批准")
        if not a.dry_run:
            with open(ARM, "w") as f:
                f.write(latest + "\n")
    else:
        result.update(action="propose", reason="新版本 " + latest + "，待主公批准（回复 批准升级 " + latest + "）")
        if not a.dry_run:
            with open(os.path.join(W, "state/work/upgrade-proposal.json"), "w") as f:
                json.dump({"target": latest, "current": cur,
                           "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                           "how": "回复 批准升级 " + latest}, f, ensure_ascii=False)
    _emit(a, result)
    return 0

def _emit(a, result):
    line = time.strftime("%Y-%m-%dT%H:%M:%S") + " " + json.dumps(result, ensure_ascii=False)
    with open(LOG, "a") as f:
        f.write(line + "\n")
    if a.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print("升级判定：" + result["action"] + " —— " + result["reason"])

if __name__ == "__main__":
    sys.exit(main())

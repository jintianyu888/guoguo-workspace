#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cron-failure-alert.py — 定时任务「首败即告警」哨兵（2026-10-17 主公令）

背景：2026-10-17 三个备份任务因墙钟超时连续失败 4 天没人发现（T1 更是投递模式 none，
失败连告警都发不出去）。本哨兵补上「首败即报 + 超期未跑 + 关键任务被禁用」三件事。

规则：
 1) enabled 任务 consecutiveErrors>=1 或 lastRunStatus=error  -> 告警（首败即报）
 2) enabled 任务 nextRunAtMs 已过 15 分钟仍没跑              -> 告警（调度卡死）
 3) 关键任务（名字含 备份/归档/哈希）enabled=false            -> 告警（被误禁用）
 4) 同一批告警指纹相同且 6 小时内推过                          -> 抑制；指纹含错误次数与最后运行时间，情况变化会自动重报

用法：
  python3 tools/cron-failure-alert.py             # 巡检（有异常才推送飞书）
  python3 tools/cron-failure-alert.py --dry-run   # 只打印，不推送
  python3 tools/cron-failure-alert.py --json      # 输出明细 JSON
退出码恒为 0（告警任务自身不应被标记失败）；参数错误退 2。
"""
import hashlib
import json
import os
import subprocess
import sys
import time

W = os.path.expanduser("~/.openclaw/workspace")
STATE = os.path.join(W, "state/cron-alert-state.json")
LOG = os.path.join(W, "state/cron-alert.log")
NOTIFY = os.path.join(W, "tools/notify.sh")
COOLDOWN = int(os.environ.get("CFA_COOLDOWN", "21600"))      # 同批告警抑制窗口 6h
OVERDUE = int(os.environ.get("CFA_OVERDUE_SEC", "900"))      # 超期未跑阈值 15min
CRITICAL_KEYS = ("备份", "归档", "哈希", "backup")


def log(msg):
    """追加一行带时间戳的日志，写失败也不抛异常。"""
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        try:
            if os.path.getsize(LOG) > 512 * 1024:      # 日志轮转，防止无限增长
                os.replace(LOG, LOG + ".1")
        except Exception:
            pass
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def fetch_jobs():
    """取 cron 列表；失败返回 None（不抛异常，避免告警任务自己炸）。"""
    try:
        p = subprocess.run(["openclaw", "cron", "list", "--json"],
                           capture_output=True, text=True, timeout=90)
    except Exception as e:
        log("cron list 异常: %r" % (e,))
        return None
    if p.returncode != 0:
        log("cron list rc=%s err=%s" % (p.returncode, (p.stderr or "")[:200]))
        return None
    raw = p.stdout or ""
    d = None
    try:
        d = json.loads(raw)                     # 正常路径
    except Exception:
        i, j = raw.find("{"), raw.rfind("}")    # 退化路径：容忍 banner/尾部杂讯
        if i >= 0 and j > i:
            try:
                d = json.loads(raw[i:j + 1])
            except Exception as e:
                log("cron list JSON 解析失败: %r" % (e,))
        else:
            log("cron list 输出非 JSON")
    if d is None:
        return None
    jobs = d.get("jobs", d) if isinstance(d, dict) else d
    return jobs if isinstance(jobs, list) else None


def _as_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _as_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def fmt_err(s):
    return str(s or "").strip().replace("\n", " ")[:80]


def is_fresh_delivery_fail(st, now_ms):
    """2026-11-08 修：原来只要 lastDeliveryError 非空就报，历史残留会被每 6 小时翻出来一次。
    现在只报 48 小时内的失败；未知状态但带错误的，只算 6 小时内的新增。"""
    if not isinstance(st, dict):
        return False
    dstat = str(st.get("lastDeliveryStatus") or "")
    lrat = st.get("lastRunAtMs")
    age_h = (now_ms - lrat) / 3600000 if isinstance(lrat, (int, float)) and lrat else 999
    if age_h > 48:
        return False
    if dstat in ("failed", "error"):
        return True
    return bool(st.get("lastDeliveryError")) and dstat == "unknown" and age_h <= 6


def collect(jobs, now_ms):
    """返回 [(kind, id, name, detail, n)]，kind ∈ error/overdue/disabled。"""
    out = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        jid = str(j.get("id") or "")[:8]
        name = str(j.get("name") or jid)
        st = j.get("state") or {}
        if not isinstance(st, dict):
            st = {}
        enabled = j.get("enabled")
        n = _as_int(st.get("consecutiveErrors"))
        status = st.get("lastRunStatus")
        critical = any(k in name.lower() for k in CRITICAL_KEYS)

        if enabled is False:
            if critical:
                out.append(("disabled", jid, name, "关键备份类任务处于停用状态", 0))
            continue

        err_detail = fmt_err(st.get("lastDeliveryError")) or fmt_err(st.get("lastDiagnosticSummary"))
        # 2026-10-17：仅因网关重启被打断、且没有其它真实错误的，不算故障（等下次正常跑即清零）
        _errs = [e for e in (fmt_err(st.get("lastError")), err_detail) if e]
        _RS = ("interrupted by gateway restart", "Gateway stopping")
        _real = [e for e in _errs if not any(k in e for k in _RS)]
        # 2026-11-08：去掉 n<=1 的限制。只要所有错误文本都是「重启打断」，就不算任务故障，
        # 否则月任务/周任务被打断一次后，会连着几天被报警（自身状态要等下次跑才清零）。
        restart_only = bool(_errs) and not _real
        if restart_only:
            pass
        elif n >= 1 or status == "error":
            detail = err_detail or ("lastRunStatus=%s" % (status or "error"))
            out.append(("error", jid, name, "连续失败 %d 次｜%s" % (n, detail), n))
        elif is_fresh_delivery_fail(st, now_ms):
            out.append(("delivery", jid, name, "投递失败｜%s" % (err_detail or str(st.get("lastDeliveryStatus"))), 0))

        nxt = st.get("nextRunAtMs")
        if isinstance(nxt, (int, float)) and nxt > 0 and now_ms > nxt + OVERDUE * 1000:
            late = int((now_ms - nxt) / 60000)
            payload = j.get("payload") if isinstance(j.get("payload"), dict) else {}
            long_job = _as_int(payload.get("timeoutSeconds")) >= 1800 or _as_int(payload.get("noOutputTimeoutSeconds")) >= 1800
            threshold = max(OVERDUE, 3 * 3600) if long_job else OVERDUE
            if now_ms > nxt + threshold * 1000 and not backups_running():
                out.append(("overdue", jid, name, "计划时间已过 %d 分钟仍未运行" % late, n))
    return out


def fingerprint(items):
    # 只用「类型+任务ID+失败次数档位」，不掺动态文案（overdue 分钟数每轮都在变，掺进去 6h 抑制就永远不生效）
    out = []
    for it in items:
        k, i = str(it[0]), str(it[1])
        n = _as_int(it[4]) if len(it) >= 5 else 0
        out.append("%s|%s|%d" % (k, i, n if k == "error" else 0))
    return sorted(out)


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_state(d):
    try:
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        tmp = STATE + ".tmp.%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, STATE)
    except Exception as e:
        log("状态写入失败: %r" % (e,))


def backups_running():
    """备份在跑时不判超期；但跑超过 5 小时视为僵死，不再豁免（存活≠有进展）。"""
    try:
        p = subprocess.run(["pgrep", "-af", "backup-(tier1-critical|mirror-verify)|backup-archive|archive-verify|backup-retain"],
                           capture_output=True, text=True, timeout=10)
        pids = [ln.split()[0] for ln in p.stdout.splitlines() if ln.strip()]
        if not pids:
            return False
        ps = subprocess.run(["ps", "-o", "etimes=", "-p", ",".join(pids)], capture_output=True, text=True, timeout=10)
        secs = [int(x) for x in ps.stdout.split() if x.strip().isdigit()]
        if secs and max(secs) >= 5 * 3600:
            log("备份进程已跑 %d 分钟，疑似僵死，不再豁免超期判定" % (max(secs) // 60))
            return False
        return True
    except Exception:
        return False


NET_KEYS = ("connect failed", "断网", "network", "网络", "ws ", "[ws]", "feishu", "imap", "eai_again", "etimedout", "timeout", "unreachable", "no response from model")
QUIET_BUF = os.path.join(W, "state/quiet-buffer.jsonl")


def in_quiet_window():
    lt = time.localtime()
    return lt.tm_hour in (4, 5) or (lt.tm_hour == 6 and lt.tm_min < 5)


def notify(text):
    head = str(text).splitlines()[0][:80] if str(text).strip() else "(空)"
    if in_quiet_window():
        if any(k in str(text).lower() for k in NET_KEYS):
            try:
                with open(QUIET_BUF, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"ts": int(time.time()), "text": str(text)[:1500]}, ensure_ascii=False) + "\n")
            except Exception:
                pass
            log("静默窗(网络类)暂存：%s" % head)
            return True
        log("静默窗但属关键故障，照常推送：%s" % head)
    else:
        try:
            if os.path.exists(QUIET_BUF) and os.path.getsize(QUIET_BUF) > 0:
                n = sum(1 for _ in open(QUIET_BUF, encoding="utf-8"))
                open(QUIET_BUF, "w").close()
                subprocess.run(["bash", NOTIFY, "【静默窗补报】04:00–06:05 暂存 %d 条网络类告警（多已自愈，明细见 state/quiet-buffer.jsonl）" % n],
                               capture_output=True, text=True, timeout=90)
        except Exception as e:
            log("补报失败: %r" % (e,))
    try:
        p = subprocess.run(["bash", NOTIFY, "--alert", text], capture_output=True, text=True, timeout=90)
        return p.returncode == 0
    except Exception as e:
        log("notify 异常: %r" % (e,))
        return False


def main():
    argv = sys.argv[1:]
    dry = "--dry-run" in argv
    as_json = "--json" in argv
    unknown = [a for a in argv if a not in ("--dry-run", "--json")]
    if unknown:
        print("未知参数: %s" % " ".join(unknown))
        return 2

    now_ms = int(time.time() * 1000)
    jobs = fetch_jobs()
    if jobs is None or not jobs:
        if as_json:
            print(json.dumps({"status": "fetch_failed", "empty": jobs == []}, ensure_ascii=False))
        fp = "fetch_failed"
        st = load_state()
        same = st.get("fp") == fp and (time.time() - _as_float(st.get("at"))) < COOLDOWN
        if same:
            log("fetch_failed 告警抑制（6h 内已推）")
            return 0
        msg = ("【OpenClaw 哨兵自身异常｜%s】取不到 cron 任务列表（openclaw cron list 失败或返回空），"
               "本轮无法巡检备份任务，请检查网关。" % time.strftime("%m-%d %H:%M"))
        if dry:
            print(msg)
        elif notify(msg):
            save_state({"fp": fp, "at": time.time()})
            log("已推送 fetch_failed 告警")
        else:
            log("fetch_failed 告警推送失败，下轮重试")
        return 0

    try:
        issues = collect(jobs, now_ms)
    except Exception as e:
        log("collect 异常（已吞掉，退出码仍为 0）: %r" % (e,))
        issues = []
    if as_json:
        print(json.dumps({"checked": len(jobs), "issues": [
            {"kind": k, "id": i, "name": n, "detail": d, "errors": c} for k, i, n, d, c in issues
        ]}, ensure_ascii=False, indent=1))
        return 0

    if not issues:
        log("巡检正常：%d 个任务无异常" % len(jobs))
        return 0

    lines = ["⚠️ OpenClaw 定时任务异常（%s）" % time.strftime("%m-%d %H:%M")]
    icon = {"error": "🔴", "overdue": "🟠", "disabled": "🟡"}
    for k, i, n, d, c in sorted(issues, key=lambda x: (x[0] != "error", x[0] != "overdue")):
        lines.append("%s %s：%s" % (icon.get(k, "•"), n, d))
    lines.append("（同一批异常 6 小时内不重复推送；情况变化会立即重报）")
    text = "\n".join(lines)

    fp = "\n".join(fingerprint(issues))
    st = load_state()
    same = st.get("fp") == fp and (time.time() - _as_float(st.get("at"))) < COOLDOWN

    if dry:
        print(text)
        print("\n[dry-run] fingerprint=%s same=%s" % (hashlib.sha256(fp.encode("utf-8")).hexdigest()[:8], same))
        return 0

    if same:
        log("告警抑制（同批已推）: %d 项" % len(issues))
        return 0

    ok = notify(text)
    if ok:
        save_state({"fp": fp, "at": time.time()})
        log("已推送 %d 项异常" % len(issues))
    else:
        log("推送失败，下轮重试（%d 项异常）" % len(issues))
    return 0


if __name__ == "__main__":
    sys.exit(main())

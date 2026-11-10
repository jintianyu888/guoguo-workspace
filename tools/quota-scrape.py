#!/usr/bin/env python3
"""quota-scrape.py v0.1 — 拟人刷新各平台额度页（只读）
防封设计：
 - 只在 07:00-23:30 活动
 - 最小间隔随机 25-45 分钟（非死板周期）
 - 打开后随机停 4-9 秒、轻滚动、再停 2-5 秒才读
 - 单页串行、不并发、不连续 reload
 - 检测登录/验证/滑块 → 停止+6h 冷却+通知，绝不绕过
用法：
  python3 tools/quota-scrape.py --discover glm
  python3 tools/quota-scrape.py --run
  python3 tools/quota-scrape.py --show
"""
import json, os, random, re, subprocess, sys, time
from datetime import datetime

WS = "/home/j/.openclaw/workspace"
D = os.path.join(WS, "state/model-econ")
TARGETS = os.path.join(D, "quota-targets.json")
QUOTAS = os.path.join(D, "quotas.json")
LOCK = os.path.join(D, "quota-scrape.lock")
NOTIFY = os.path.join(WS, "tools/notify.sh")

def now(): return datetime.now()
def in_active_hours(t):
    return (7 <= t.hour < 23) or (t.hour == 23 and t.minute <= 30)

def load(p, d=None):
    try:
        with open(p) as f: return json.load(f)
    except Exception:
        return d

def save(p, obj):
    tmp = p + ".tmp"
    with open(tmp, "w") as f: json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)

def logline(msg):
    """只记日志、不推送（登录类噪音用）"""
    try:
        os.makedirs(os.path.join(WS, "state/work"), exist_ok=True)
        with open(os.path.join(WS, "state/work/quota-scrape.log"), "a") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass

def notify(msg):
    # 2026-10-31 主公令：额度页告警不再直发主公，改入队交维护管家处理
    # 先入队去重（同一文案 6 小时内只提醒一次），再直接投递到维护管家的飞书
    try:
        r = subprocess.run(["python3", os.path.join(WS, "tools/quota-alert.py"), "add", msg],
                           capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and (r.stdout or "").startswith("duplicate-skip"):
            return
    except Exception:
        pass
    # 2026-11-02 主公令：警报归「果果告警」（webhook 优先），维护管家只收报告
    try:
        r2 = subprocess.run(["bash", NOTIFY, "--alert", msg], capture_output=True, text=True, timeout=90)
        if r2.returncode == 0:
            return
    except Exception:
        pass
    try: subprocess.run(["bash", NOTIFY, msg], timeout=90)
    except Exception: pass

def _ensure_gw_token():
    """2026-10-31 修：扩展通道（--browser-profile chrome）需要网关凭证，
    之前用 --profile 且不带 token，导致每次都回落到未登录的托管浏览器。
    这里从 secret store 取 GATEWAY_AUTH_TOKEN，经环境变量注入（不进 argv，避免被 ps 看到）。"""
    if os.environ.get("OPENCLAW_GATEWAY_TOKEN"):
        return
    try:
        import sqlite3
        con = sqlite3.connect("/home/j/.openclaw/state/openclaw.sqlite")
        rows = dict(con.execute("select name,value from secret_store_entries"))
        con.close()
        t = rows.get("GATEWAY_AUTH_TOKEN")
        if t:
            os.environ["OPENCLAW_GATEWAY_TOKEN"] = t
    except Exception:
        pass

_ensure_gw_token()

def browser(args, timeout=90):
    # 2026-10-31 修：chrome 扩展掉线时自动回落到托管浏览器（openclaw profile）
    PROF = os.environ.get("QUOTA_BROWSER_PROFILE", "chrome")
    profs = [PROF]
    if PROF and os.environ.get("QUOTA_BROWSER_FALLBACK", "1") != "0":
        profs.append("")
    rc, out = 1, ""
    for prof in profs:
        cmd = ["timeout", str(timeout), "openclaw", "browser", args[0]]
        if prof:
            cmd += ["--browser-profile", prof]
        cmd += args[1:] + ["--json"]
        for attempt in range(3):
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
            rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
            if rc == 0:
                return rc, out
            # 2026-10-31 修：扩展连接偶发抖动，先重试再回落，避免退回未登录的托管浏览器
            if "extension is not connected" in out and attempt < 2:
                time.sleep(3)
                continue
            if "connectOverCDP" in out and attempt == 0:
                time.sleep(3)
                continue
            break
        if "extension is not connected" not in out:
            return rc, out
    return rc, out

def page_text(url):
    rc, out = browser(["open", url], timeout=35)
    if rc != 0: return None, f"open rc={rc}: {out[:200]}"
    if "/login" in (out or "") or "请登录" in (out or ""):
        return None, "login_required: 页面跳转到登录页"
    # 2026-10-24 修：evaluate 默认打在“当前活动页”，刚 open 的新页不一定是活动页
    # （实测：智谱 grab 到期页拿到的仍是用量页文本，MiniMax 恰好因为原页就是 /console/plan 才成功）
    _m = re.search(r'"targetId"\s*:\s*"([^"]+)"', out or "")
    _tid = _m.group(1) if _m else None
    _extra = ["--target-id", _tid] if _tid else []
    time.sleep(random.uniform(4, 9))
    # 2026-10-24 修：这一步原来没带 --browser-profile，会打到默认的本地 chromium（缺 libasound 起不来）白等超时
    browser(["evaluate", "--fn", "window.scrollBy(0, %d)" % random.randint(200, 500)] + _extra, timeout=45)
    time.sleep(random.uniform(2, 5))
    rc, out = browser(["evaluate", "--fn", "return document.body.innerText.slice(0,6000)"] + _extra, timeout=60)
    if rc != 0: return None, f"eval rc={rc}: {out[:200]}"
    # 2026-10-24 修：CLI 返回的 JSON 键是 result（不是 value）
    m = re.search(r'"(?:result|value)"\s*:\s*"((?:[^"\\]|\\.)*)"', out)
    if m:
        try: return json.loads('"' + m.group(1) + '"'), None
        except Exception: return m.group(1), None
    return out[:6000], None

def parse(text, patterns):
    vals = {}
    for key, pat in (patterns or {}).items():
        m = re.search(pat, text or "")
        if m: vals[key] = m.group(1) if m.groups() else m.group(0)
    return vals

def guard_page(text):
    bad = re.search(r"(请登录|扫码登录|验证码|人机验证|滑动验证|安全验证|登录已过期)", text or "")
    return bad.group(1) if bad else None

def sync_balances(q):
    """抓取成功后同步 balances.json（供监控面板每分钟读取）"""
    bp = os.path.join(D, "balances.json")
    try:
        b = json.load(open(bp))
    except Exception:
        b = {"providers": {}}
    prov = b.setdefault("providers", {})
    z = (q.get("providers") or {}).get("zai") or {}
    if z.get("status") == "ok":
        v = z.get("values") or {}
        try:
            used = int(str(v.get("weekly_credits_used", "0")).replace(",", "") or 0)
        except Exception:
            used = 0
        zz = prov.setdefault("zhipu", {})
        if used > 0:
            zz["weekly_limit"] = 10000
            zz["weekly_remaining"] = max(10000 - used, 0)
            zz["used_pct"] = v.get("weekly_pct")
        zz["reset_at"] = v.get("weekly_reset_at")
        zz["note"] = "抓页成功（实时）"
    k = (q.get("providers") or {}).get("kimi") or {}
    if k.get("status") == "ok":
        kk = prov.setdefault("kimi", {})
        kk["raw_values"] = k.get("values") or {}
        kk["note"] = "抓页成功（实时）"
    # 2026-10-24 补：DeepSeek 余额也要同步，否则面板一直显示旧值（实测面板 124.95 vs 抓页 117.76）
    ds = (q.get("providers") or {}).get("deepseek") or {}
    if ds.get("status") == "ok":
        dv = ds.get("values") or {}
        try:
            _bal = float(str(dv.get("balance", "")).replace(",", ""))
            dd = prov.setdefault("deepseek", {})
            dd["available"] = _bal
            dd["currency"] = dd.get("currency") or "CNY"
            if str(dv.get("total_spend", "")).strip():
                dd["total_spent"] = float(str(dv["total_spend"]).replace(",", ""))
            dd["source"] = "抓页实时（platform.deepseek.com/usage）"
            dd["note"] = "实时（页面标注 5 分钟延迟）"
        except Exception:
            pass
    # 2026-10-24 新增：把到期日同步到 balances.json（面板每行末尾显示）
    for _pk, _key in (("zai", "zhipu"), ("minimax", "minimax")):
        _st = (q.get("providers") or {}).get(_pk) or {}
        _exp = _st.get("plan_expire")
        if _exp:
            _pp = prov.setdefault(_key, {})
            _pp["plan_expire"] = _exp
            _pp["plan_expire_confident"] = bool(_st.get("plan_expire_confident", True))
    b["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    tmp = bp + ".tmp"
    open(tmp, "w").write(json.dumps(b, ensure_ascii=False, indent=1))
    os.replace(tmp, bp)

def run(only=None):
    t = now()
    if not only and not in_active_hours(t):
        print("inactive-hours skip"); return 0
    # 2026-10-31 修：先探测 chrome 扩展，掉线就整轮改用托管浏览器，避免每页都等两次超时
    if os.environ.get("QUOTA_PREFLIGHT", "1") != "0":
        _prof = os.environ.get("QUOTA_BROWSER_PROFILE", "chrome")
        if _prof:
            _p = subprocess.run(["timeout", "15", "openclaw", "browser", "open", "about:blank",
                                 "--browser-profile", _prof, "--json"],
                                capture_output=True, text=True)
            _o = (_p.stdout or "") + (_p.stderr or "")
            if _p.returncode != 0 and "extension is not connected" in _o:
                os.environ["QUOTA_BROWSER_PROFILE"] = ""
                print("preflight: chrome 扩展未连接，本轮改用托管浏览器")
    targets = load(TARGETS, {}) or {}
    q = load(QUOTAS, {"providers": {}, "updated": None})
    changed = False
    attempted = 0
    for name, cfg in targets.items():
        if only and name != only: continue
        if name.startswith("_") or not cfg.get("enabled"): continue
        st = q["providers"].get(name, {})
        last = st.get("last_run_ts", 0)
        if not only and last and (time.time() - last) < random.uniform(25, 45) * 60: continue
        if st.get("cooldown_until", 0) > time.time(): continue
        text, err = page_text(cfg["url"])
        st["last_run_ts"] = int(time.time())
        st["last_try_at"] = t.isoformat(timespec="seconds")
        attempted += 1
        if err:
            low = err.lower()
            if "login" in low or "登录" in err or "extension is not connected" in low or "cli_error" in low:
                st["status"] = "login_required"
            else:
                st["status"] = "error"
            st["error"] = err
        else:
            bad = guard_page(text)
            if bad:
                st["status"] = "auth_required"; st["note"] = bad
                st["cooldown_until"] = int(time.time() + 6*3600)
                # 2026-11-07 主公令：额度页登录类问题不再推飞书（无时效、纯噪音），只记日志，面板可查
                logline("QUOTA_AUTH %s: %s（已暂停6小时；仅记录，不推送）" % (name, bad))
            else:
                vals = parse(text, cfg.get("patterns"))
                st["values"] = vals
                st["sample"] = (text or "")[:400]
                # 2026-10-24 修：解析结果必须回写顶层字段并刷新 captured_at，否则面板永远读 10-20 的旧值（假绿）
                if vals:
                    for _k, _v in vals.items():
                        _s = str(_v).replace(",", "")
                        if re.fullmatch(r"-?\d+(\.\d+)?", _s):
                            _n = float(_s)
                            _v = int(_n) if _n == int(_n) else _n
                        st[_k] = _v
                    # 智谱 5h 窗口只给 "20:38" 这种当天时刻，补日期（2026-10-24）
                    _wr = str(st.get("window_reset_at") or "")
                    if re.fullmatch(r"\d{1,2}:\d{2}", _wr):
                        st["window_reset_at"] = t.strftime("%Y-%m-%d ") + _wr
                    st["status"] = "ok"
                    st["captured_at"] = t.strftime("%Y-%m-%d %H:%M")
                    st.pop("error", None)
                else:
                    st["status"] = "parse_fail"
                # 2026-10-24 新增：会员到期查询（主公令）—— 各家的「套餐/详情」页才有到期日
                purl = cfg.get("plan_url")
                if purl:
                    ptext, perr = page_text(purl)
                    if (perr or not ptext) or not parse(ptext, cfg.get("plan_patterns")).get("plan_expire"):
                        time.sleep(random.uniform(4, 7))
                        ptext2, perr2 = page_text(purl)
                        if not perr2 and ptext2:
                            ptext, perr = ptext2, None
                    if not perr and ptext:
                        pv = parse(ptext, cfg.get("plan_patterns"))
                        exp = str(pv.get("plan_expire") or "").strip()
                        mm = re.match(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", exp)
                        if mm:
                            _y, _mo, _d = mm.groups()
                            exp = "%s-%02d-%02d" % (_y, int(_mo), int(_d))
                        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", exp):
                            st["plan_expire"] = exp
                            st["plan_expire_confident"] = True
                        # 2026-10-28 新增：Kimi 月卡「用量进度」——面板要的是可用额度，不是钱包余额
                        if name == "kimi":
                            _mt = re.search(r"总使用量\s*([\d.]+)\s*%", ptext)
                            if _mt: st["month_pct"] = float(_mt.group(1))
                            _wt = re.search(r"5\s*小时用量[\s\S]{0,60}?(\d+(?:\.\d+)?)\s*%", ptext)
                            if _wt: st["window_pct"] = float(_wt.group(1))
                            _mr = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*后重置", ptext)
                            if _mr: st["month_reset_at"] = _mr.group(1)
                            _wseg = ptext.split("5 小时用量", 1)
                            _wr = re.search(r"(\d{2}-\d{2}\s+\d{2}:\d{2})\s*后重置", _wseg[1]) if len(_wseg) > 1 else None
                            if _wr: st["window_reset_at"] = _wr.group(1)
                            _pk = re.search(r"当前余额\s*[¥￥]\s*([\d.]+)", ptext)
                            if _pk: st["pack_balance"] = float(_pk.group(1))
                            _nm = re.search(r"\n([A-Za-z][^\n]{0,20})\n(?:重新订阅|升级订阅)", ptext)
                            if _nm: st["plan"] = _nm.group(1).strip()
                            if st.get("month_pct") is not None:
                                st["status"] = "ok"
                                st.pop("error", None)
        q["providers"][name] = st
        changed = True
    if changed:
        q["updated"] = t.isoformat(timespec="seconds")
        save(QUOTAS, q)
        print("updated:", ",".join(q["providers"].keys()))
    else:
        print("nothing due")
    try:
        subprocess.run(["python3", os.path.join(WS, "tools", "browser-tidy.py")],
                       capture_output=True, timeout=180)
    except Exception:
        pass
    ok_n = sum(1 for k, v in (q.get("providers") or {}).items() if v.get("status") == "ok")
    try:
        sync_balances(q)
    except Exception as e:
        print("balances sync warn:", e)
    if attempted == 0:
        return 0
    # 2026-10-31 修：失败不再以 exit 3 上报（会污染 cron 状态），改由告警通道提醒
    return 0

def discover(name):
    targets = load(TARGETS, {}) or {}
    url = (targets.get(name) or {}).get("url")
    if not url and len(sys.argv) > 2: url = sys.argv[2]
    text, err = page_text(url)
    if err: print("ERR", err); return 1
    fp = os.path.join(D, "scrape-%s.txt" % name)
    with open(fp, "w") as f: f.write(text or "")
    print("saved", fp, "chars:", len(text or ""))
    print((text or "")[:600])
    return 0

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return 2
    if a[0] == "--discover": return discover(a[1])
    if a[0] == "--show":
        print(json.dumps(load(QUOTAS, {}), ensure_ascii=False, indent=1)); return 0
    if a[0] == "--run":
        only = a[2] if len(a) >= 3 and a[1] == "--only" else None
        if os.path.exists(LOCK) and (time.time() - os.path.getmtime(LOCK)) < 600:
            # 2026-10-31 修：锁里的 PID 已死则视为僵尸锁，直接清掉
            try:
                _pid = int((open(LOCK).read() or "0").strip())
            except Exception:
                _pid = 0
            _alive = False
            if _pid > 0:
                try:
                    os.kill(_pid, 0); _alive = True
                except OSError:
                    _alive = False
            if _alive:
                print("locked skip"); return 0
            try: os.remove(LOCK)
            except OSError: pass
        open(LOCK, "w").write(str(os.getpid()))
        try: return run(only)
        finally:
            try: os.remove(LOCK)
            except OSError: pass
    print("unknown arg"); return 2

if __name__ == "__main__":
    sys.exit(main())

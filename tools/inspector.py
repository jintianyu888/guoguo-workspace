#!/usr/bin/env python3
# inspector.py —— 四查督察（哨兵之哨兵）v0.3  2026-10-20 [54]
# 双模评审共识修订：v4-pro + glm-5.3 均「修后挂」
# v0.2：exit合同0/flock/暂停窗口守卫/耗时历史连2次P0/超期门控/C去重
# v0.3（v4-pro 补充必修）：裸*→全量(修10任务漏查)/D查只比argv+跳空
#  （修真重复漏报）/假绿仅lastRunStatus==ok/快照复用窗2h→10min
#  /杀毒tol1.3/自检基线200/指纹\bok\b
import json, os, re, subprocess, sys, time, fcntl, hashlib
from datetime import datetime, timezone, timedelta

WS = "/home/j/.openclaw/workspace"
NOTIFY_STATE = f"{WS}/state/inspector/last-notify.json"


def _norm(line):
    """归一化：剥掉每次都会变的时长/日期/数字/summary 正文，只留'类型+任务'骨架"""
    s = (line or "").strip()
    s = re.sub(r"summary=「.*$", "summary=<...>", s)
    s = re.sub(r"\d+(?:\.\d+)?\s*s\b", "<dur>", s)
    s = re.sub(r"20\d\d-\d\d-\d\d(?:[T ]\d\d:\d\d(?::\d\d)?)?", "<date>", s)
    s = re.sub(r"\d+(?:\.\d+)?", "<n>", s)
    return re.sub(r"\s+", " ", s)


def _notify_fp(line):
    return hashlib.sha256(_norm(line).encode("utf-8")).hexdigest()[:16]


def _load_seen():
    try:
        with open(NOTIFY_STATE) as f:
            d = json.load(f)
        e = d.get("entries") if isinstance(d, dict) else None
        return e if isinstance(e, dict) else {}
    except Exception:
        return {}


def notify_filter(lines, window_h=6.0):
    """逐条去重：返回 (本次该推的行, 被抑制条数)。异常一律放行，绝不吞告警"""
    try:
        seen = _load_seen()
    except Exception:
        return list(lines), 0
    now = time.time()
    keep, suppressed = [], 0
    for ln in lines:
        ts = seen.get(_notify_fp(ln))
        try:
            fresh = ts is not None and (now - float(ts)) < float(window_h) * 3600
        except Exception:
            fresh = False
        if fresh:
            suppressed += 1
        else:
            keep.append(ln)
    return keep, suppressed


def notify_mark(lines):
    """推送成功后记账，24h 过期；写失败只告警（去重失效，绝不丢告警）"""
    try:
        seen = _load_seen()
        now = time.time()
        for ln in lines:
            seen[_notify_fp(ln)] = now
        seen = {k: v for k, v in seen.items() if isinstance(v, (int, float)) and now - v < 86400}
        os.makedirs(os.path.dirname(NOTIFY_STATE), exist_ok=True)
        tmp = NOTIFY_STATE + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"entries": seen}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, NOTIFY_STATE)
    except Exception as e:
        log(f"[告警] 去重状态写入失败（可能重复推送）：{e}")


CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
P0, P1, P2 = [], [], []
def log(msg): print(msg)

# ---------- flock：上轮没跑完就跳过 ----------
_lock = open(f"{WS}/state/work/inspector.lock", "w")
try:
    fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    print("skip: 上轮督察仍在运行"); sys.exit(0)

# ---------- 数据源：cron 注册表（快照<2h 复用；绝不中途改写；带拉取时间戳） ----------
# 2026-10-26 A6 修：/tmp 是内存盘，快照改落 state/tmp（磁盘），避免重启丢档
SNAP = f"{WS}/state/tmp/cron_list.json"
SNAP_TS = f"{WS}/state/tmp/cron_list.json.pulled_at"
PAUSE_WIN = (0, 55) <= (NOW.hour, NOW.minute) <= (1, 40)  # backup-quiet 暂停窗口

def load_jobs():
    pulled = 0
    if os.path.exists(SNAP_TS):
        try: pulled = int(open(SNAP_TS).read().strip())
        except ValueError: pulled = 0
    if not (pulled and time.time() - pulled < 600):
        r = subprocess.run(["timeout", "120", "openclaw", "cron", "list", "--all", "--json"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            open(SNAP, "w").write(r.stdout)
            open(SNAP_TS, "w").write(str(int(time.time())))
            pulled = int(time.time())
    if not os.path.exists(SNAP):
        return None, None
    try:
        d = json.load(open(SNAP))
    except json.JSONDecodeError:
        return None, None
    jobs = d.get("jobs", d) if isinstance(d, dict) else d
    snap_in_pause = bool(pulled and datetime.fromtimestamp(pulled, CST).strftime("%H%M") >= "0055"
                         and datetime.fromtimestamp(pulled, CST).strftime("%H%M") <= "0140")
    return jobs, pulled, (PAUSE_WIN or snap_in_pause)

# ---------- 耗时历史（近5次） ----------
HIST_P = f"{WS}/state/inspector/dur-history.json"
def load_hist():
    try: return json.load(open(HIST_P))
    except Exception: return {}
def save_hist(h):
    json.dump(h, open(HIST_P, "w"), ensure_ascii=False)

def probe_cmd_exists(c): return subprocess.run(["sh", "-c", f"command -v {c}"], capture_output=True).returncode == 0
def probe_file(p): return os.path.exists(os.path.expanduser(p))

MANIFEST = [
    # 2026-10-26 C1 修：周末全量/工作日下午全量已在 93→51 合并进「每日全量备份归档」0 1 * * *，
    #  清单改指真实现役任务，不再追已合并的名字
    {"name": "每日全量备份归档",  "cad": 26, "tol": 1.3, "base": 2000, "deps": [], "fp": r"\bok\b|完成|✅|heartbeat|退出码 0"},  # 2026-10-26：heartbeat-run 包装，摘要常被心跳占满，接受心跳行
    # 2026-10-27 夜间清零修：该任务已合并为「系统自检+稳定性(每日)」0 7 * * *（daily-health.sh 入口），
    #   原名在 cron 注册表不存在 → 每天误报 P0「清单任务缺失」。改名对齐 + 基线按时长合并。
    {"name": "系统自检+稳定性(每日)", "cad": 26, "tol": 1.6, "base": 900, "deps": [], "fp": r"."},
    {"name": "备份镜像+校验",     "cad": 26, "tol": 1.3, "base": 120, "deps": [], "fp": r"."},
    {"name": "归档哈希+保留",     "cad": 26, "tol": 1.3, "base": 1900, "deps": [], "fp": r"."},
    {"name": "备份哈希清单",      "cad": 26, "tol": 1.3, "base": 3000, "deps": [], "fp": r"."},
    {"name": "E-H互备",          "cad": 26, "tol": 1.3, "base": 140, "deps": [], "fp": r"."},
    {"name": "EH存储区快照",      "cad": 26, "tol": 1.3, "base": 120, "deps": [], "fp": r"."},
    {"name": "每周杀毒扫描",      "cad": 170, "tol": 1.3, "base": 240, "deps": ["cmd:clamscan"], "fp": r"Scanned files: [0-9]+|无感染|发现 [0-9]+ 个"},  # 2026-10-26 C2：实测 80-115s（已排除 venv/models 大目录），旧基线 1200s 造成假绿误报
    {"name": "NVR人脸扫描",       "cad": 26, "tol": 1.4, "base": 600, "detach": True, "deps": ["file:~/.config/hik-nvr.env"], "fp": r"已分离启动|\bok\b|完成|✅"},
    {"name": "体检采集",          "cad": 26, "tol": 1.3, "base": 15, "deps": [], "fp": r"."},
    {"name": "体检日报",          "cad": 26, "tol": 1.3, "base": 15, "deps": [], "fp": r"."},
    {"name": "T1重点备份",        "cad": 14, "tol": 1.5, "base": 60, "deps": [], "fp": r"."},
    {"name": "模型经济中枢",      "cad": 26, "tol": 1.3, "base": 400, "deps": [], "fp": r"."},
    # 2026-11-08 改：原清单项「工作区镜像到群晖」没有对应 cron（工作区已随每日全量归档整体推群晖），
    # 实际承担推送的是 cron「群晖补推(工作日下午)」，清单名对齐到它。
    {"name": "群晖补推",        "cad": 26, "tol": 1.5, "base": 0, "deps": [], "fp": r"."},
]

def check_A(jobs, in_pause):
    hist = load_hist()
    byname = {}
    for j in jobs: byname.setdefault(j.get("name", "?"), []).append(j)
    for m in MANIFEST:
        name = m["name"]
        cands = byname.get(name) or [j for n, lst in byname.items() if name in n for j in lst[:1]]
        if not cands:
            P0.append(f"[A-缺任务] 清单任务「{name}」在 cron 注册表中不存在（被删/改名/未建）")
            continue
        j = cands[0]
        if not j.get("enabled", True) and not in_pause:
            P0.append(f"[A-被禁用] 「{name}」enabled=false")
        st = j.get("state") or {}
        # 门控：已在连续失败/跳过的任务不判超期（已有其它告警路径）
        failing = (st.get("consecutiveErrors") or 0) > 0 or (st.get("consecutiveSkipped") or 0) > 0
        last_ms = st.get("lastRunAtMs")
        created_ms = j.get("createdAtMs")
        if not last_ms:
            age_h = (time.time() - (created_ms or 0) / 1000) / 3600
            if age_h > m["cad"] * m["tol"] + 24:
                P0.append(f"[A-从未跑] 「{name}」建立 {age_h:.0f}h 仍无一次运行记录")
            continue
        next_ms = st.get("nextRunAtMs")
        grace_ms = m["cad"] * m["tol"] * 3600 * 1000
        overdue_ref = (next_ms + 6 * 3600 * 1000) if next_ms else (last_ms + grace_ms)
        if not failing and time.time() * 1000 > overdue_ref:
            gap_h = (time.time() - last_ms / 1000) / 3600
            P0.append(f"[A-超期] 「{name}」距上次运行 {gap_h:.0f}h（预期≤{m['cad']}h）")
        status = st.get("lastRunStatus") or st.get("lastStatus")
        if status and status != "ok" and not failing:
            P1.append(f"[A-末次失败] 「{name}」lastRunStatus={status}")
        dur_s = (st.get("lastDurationMs") or 0) / 1000
        summ0 = st.get("lastDiagnosticSummary") or ""
        h = hist.setdefault(name, {"durs": [], "anom": 0})
        # 2026-10-26：detach=True 的任务（cron-detached.sh 分离启动）秒回是设计如此，不判耗时假绿
        # 2026-11-08 修：跑得快本身不算假绿——只要产出非空且与上次不同。只有「快 + 无产出/产出没变」才可疑。
        fast = bool(m["base"]) and dur_s and status == "ok" and not m.get("detach") and dur_s < m["base"] * 0.25
        fast_suspect = fast and (len(summ0.strip()) < 20 or summ0 == h.get("lastSumm"))
        if fast_suspect:
            if h.get("anom", 0) >= 1:
                P0.append(f"[A-疑似假绿] 「{name}」连续≥2次耗时异常（本次 {dur_s:.0f}s ≪ 基线 {m['base']}s 且无新产出）")
            else:
                P1.append(f"[A-疑似假绿·首现] 「{name}」耗时 {dur_s:.0f}s ≪ 基线 {m['base']}s 且无新产出，复看一次")
            h["anom"] = h.get("anom", 0) + 1
        else:
            h["anom"] = 0
        h["lastSumm"] = summ0
        if h["durs"] or dur_s:
            h["durs"] = ([dur_s] + h.get("durs", []))[:5] if dur_s else h["durs"]
        summ = st.get("lastDiagnosticSummary") or ""
        if m["fp"] != r"." and summ and not re.search(m["fp"], summ):
            P0.append(f"[A-产出指纹不符] 「{name}」summary=「{summ[:60]}」不含预期指纹")
        for dep in m["deps"]:
            kind, val = dep.split(":", 1)
            ok = probe_cmd_exists(val) if kind == "cmd" else probe_file(val)
            if not ok:
                P0.append(f"[A-依赖缺失] 「{name}」依赖 {dep} 不可用 → 即使跑也是假绿")
    save_hist(hist)

IO_KW = ("备份", "镜像", "互备", "归档", "哈希", "扫描", "杀毒", "导出", "快照", "真空", "push", "mirror", "hash", "scan", "archive", "image")
NET_KW = ("群晖", "百度", "网盘", "NAS", "推送", "补推", "云")
def parse_expr(expr):
    p = expr.split()
    if len(p) != 5: return None
    def rng(tok, cap=60):
        out = []
        for t in tok.split(","):
            step = 1
            if "/" in t:
                t, s = t.split("/", 1)
                step = int(s) if s.isdigit() and int(s) > 0 else 1
            if t == "*":
                lo, hi = 0, cap
            elif "-" in t:
                a, b = t.split("-", 1)
                lo = int(a) if a.lstrip("+").isdigit() else 0
                hi = int(b) if b.lstrip("+").isdigit() else cap
            elif t.isdigit():
                lo = hi = int(t)
            else:
                continue
            out.extend(range(lo, hi + 1, step))
        return out
    return rng(p[0]), rng(p[1], cap=23)

def check_BC(jobs):
    hist = load_hist()
    slots = []
    for j in jobs:
        if not j.get("enabled", True): continue
        sch = j.get("schedule") or {}
        if sch.get("kind") != "cron": continue
        pm = parse_expr(sch.get("expr") or "")
        if not pm: continue
        name = j.get("name", "?")
        dur = (j.get("state") or {}).get("lastDurationMs") or 0
        heavy = any(k in name for k in IO_KW); net = any(k in name for k in NET_KW)
        for h in pm[1]:
            for mi in pm[0]:
                slots.append((h, mi, name, dur / 60000, heavy, net))
    slots.sort()
    for i in range(len(slots) - 1):
        h1, m1, n1, d1, hv1, _ = slots[i]
        h2, m2, n2, d2, hv2, _ = slots[i + 1]
        gap = (h2 * 60 + m2) - (h1 * 60 + m1)
        if gap < 0: continue
        # 首跑无历史不判（v4-pro 建议）
        if not hist.get(n1, {}).get("durs") or not hist.get(n2, {}).get("durs"):
            continue
        if hv1 and hv2 and gap < 10 and gap - d1 < 5:
            P2.append(f"[B-缓冲薄] {h1:02d}:{m1:02d}「{n1}」({d1:.0f}分) → {gap}分后「{n2}」重载接力")
    seen_c = set()
    for h, mi, n, d, hv, net in slots:
        if 4 <= h < 6 and net and n not in seen_c:
            seen_c.add(n)
            P1.append(f"[C-断网窗口] {h:02d}:{mi:02d}「{n}」为网络任务却在 04-06 断网窗口")

def check_D(jobs):
    seen = set()
    items = []
    for j in jobs:
        argv = " ".join((j.get("payload") or {}).get("argv", []))
        if argv.strip():  # 跳空 argv（v4-pro：25个空 argv 任务否则互误报）
            items.append((j.get("name", "?"), argv))
    for i in range(len(items)):
        for k in range(i + 1, len(items)):
            a, b = items[i], items[k]
            if a[1] == b[1]:
                key = (a[1], b[1])
                if key in seen: continue
                seen.add(key)
                P1.append(f"[D-重复argv] 「{a[0]}」与「{b[0]}」argv 完全一致（{a[1][:60]}）")

def check_deep(jobs):
    # 深度版附加（周三，独立任务——主公 2026-10-20 19:41 采 GLM 方案）
    import difflib
    # ① every 型网络任务在 04-06 断网窗口必失败（补 C 查盲区）
    for j in jobs:
        sch = j.get("schedule") or {}
        if sch.get("kind") == "every" and j.get("enabled", True):
            name = j.get("name", "?")
            if any(k in name for k in NET_KW):
                mins = (sch.get("everyMs") or 0) // 60000
                P2.append(f"[C-断网窗口·every] 「{name}」全天每{mins}分钟跑且含网络依赖，04-06 断网窗口会失败（确认已加静默/容错）")
    # ② 名称相似重复候选（信息性，确认非同一功能重复挂载）
    names = [j.get("name", "?") for j in jobs if j.get("enabled", True)]
    reported = set()
    for i in range(len(names)):
        for k in range(i + 1, len(names)):
            r = difflib.SequenceMatcher(None, names[i], names[k]).ratio()
            if r > 0.66:
                pair = tuple(sorted([names[i], names[k]]))
                if pair not in reported:
                    reported.add(pair)
                    P2.append(f"[D-名称相似] 「{names[i]}」≈「{names[k]}」（{r:.2f}）——确认非同一功能重复挂载")

def check_model_econ(jobs):
    """模型经济链督察（2026-10-20 主公令：经济巡检纳入督察）。
    影子模式：查采集/规划/审查三件套是否真跑、输出是否新鲜非空、规则校验是否通过。"""
    import json as _j, os as _o
    d = f"{WS}/state/model-econ"
    # 2026-11-08 修：影子规划/审查三件套在 11-07 cron 清洗时按废弃删除（此前已停跑 10 天），
    # 有退役标记就只看「模型经济中枢」的 balances 新鲜度，不再追 plan/verdict 文件。
    if _o.path.exists(_o.path.join(d, "RETIRED-shadow-plan.md")):
        bp = _o.path.join(d, "balances.json")
        if not _o.path.exists(bp):
            P1.append("[E-模型链] balances.json 缺失（模型经济中枢未产出）")
        else:
            age = (NOW.timestamp() - _o.path.getmtime(bp)) / 3600.0
            if age > 26:
                P1.append(f"[E-模型链] balances.json 已 {age:.0f}h 未更新")
        return
    day = NOW.strftime("%Y%m%d")
    hm = (NOW.hour, NOW.minute)
    names = {j.get("name", "") for j in jobs}
    # 2026-10-26 C4 修：GLM配额守卫已合并进「额度守卫与调档(合并)」(*/30 7-23，argv 就是 quota-guard-all.sh)，
    #  按现役名核对，不再误报缺任务
    # 2026-10-29 修：load_jobs 改 --all 后可见已暂停任务，区分「被删」与「被暂停」，
    #  「模型经济巡检」已并入「模型经济中枢」(每日 22:10)。
    byname_all = {j.get("name", ""): j for j in jobs}
    for n in ("模型经济中枢", "模型规划(影子)", "模型规划审查(影子)", "额度守卫与调档"):
        hit = [x for x in names if n in x]
        if not hit:
            P0.append(f"[E-模型链] 任务「{n}」不在注册表（被删或未挂载）")
        elif all(not byname_all[x].get("enabled", True) for x in hit):
            P1.append(f"[E-模型链] 任务「{n}」已存在但被暂停（enabled=false）——确认是否该恢复")
    def _load(fn):
        fp = _o.path.join(d, fn)
        if not _o.path.exists(fp):
            return None, f"缺文件 {fn}"
        try:
            with open(fp) as f:
                return _j.load(f), None
        except Exception as e:
            return None, f"{fn} 解析失败: {str(e)[:60]}"
    # 2026-10-26 C5 修：采集器 22:30 才出当日 bundle，白天督察不该追当日文件（原逻辑 08:25 必报 P1）
    bundle_day = day if hm >= (22, 35) else time.strftime("%Y%m%d", time.localtime(NOW.timestamp() - 86400))
    b, err = _load(f"bundle-{bundle_day}.json")
    if err:
        P1.append(f"[E-模型链] 采集{err}")
    else:
        if not b.get("balance") or not b.get("cron_total"):
            P1.append("[E-模型链] 采集数据不全（余额或任务数为空）")
    plan_day = day if hm >= (22, 35) else time.strftime("%Y%m%d", time.localtime(NOW.timestamp() - 86400))
    grace = False
    for jj in jobs:  # 2026-10-26 C5 修：原用 _j 当循环变量，把 json 别名覆盖成 dict → _j.load() 报错
        if "模型规划(影子)" in (jj.get("name") or ""):
            created = (jj.get("createdAtMs") or 0) / 1000
            if created and (NOW.timestamp() - created) < 48 * 3600:
                grace = True
    if True:
        pl, err = _load(f"plan-{plan_day}.json")
        if err:
            if grace:
                P2.append(f"[E-模型链] 规划首跑宽限：{err}")
            else:
                P0.append(f"[E-模型链] 规划假跑：{err}")
        else:
            items = pl.get("items") or []
            # 2026-10-26 C5 修：plan-20261025 是"零改动"的真结论（notes 写了逐条依据），
            #  与"模型空转返回空"不同。带 notes 且明说零改动 → P2 信息；notes 也空才算假跑。
            _notes = (pl.get("notes") or "").strip()
            if not items:
                if _notes and ("零改动" in _notes or "无改动" in _notes):
                    P2.append(f"[E-模型链] 规划结论为零改动（notes {len(_notes)} 字，已人工可查）")
                else:
                    P0.append("[E-模型链] 规划输出为空 items=[] 且无 notes（空输出≠零改动）")
            else:
                r = subprocess.run(["python3", f"{WS}/tools/model-plan-check.py", "--validate", f"{d}/plan-{plan_day}.json"],
                                   capture_output=True, text=True, timeout=60)
                if r.returncode != 0:
                    P0.append(f"[E-模型链] 规划未过规则校验：{r.stdout.strip()[:120]}")
    if True:
        vd, err = _load(f"verdict-{plan_day}.json")
        if err:
            if grace:
                P2.append(f"[E-模型链] 审查首跑宽限：{err}")
            else:
                P0.append(f"[E-模型链] 审查假跑：{err}")
        elif vd.get("verdict") not in ("approve", "reject"):
            P0.append("[E-模型链] 审查结论非法（approve/reject 之外）")
    qq = _o.path.join(d, "quotas.json")
    qd = None
    if _o.path.exists(qq):
        try:
            with open(qq) as f: qd = _j.load(f)
        except Exception: qd = None
        age = (NOW.timestamp() - _o.path.getmtime(qq)) / 60
        if 8 <= NOW.hour <= 23 and age > 180:
            P2.append(f"[E-额度页] 额度总表 {int(age)} 分钟未刷新（抓取可能停摆）")
        for pname, pst in ((qd or {}).get("providers") or {}).items():
            if pst.get("status") == "auth_required":
                P1.append(f"[E-额度页] {pname} 需要重新登录，额度已停更（等主公重扫）")
    q = _o.path.join(d, "glm-quota-state.json")
    if not _o.path.exists(q):
        P2.append("[E-模型链] GLM 配额状态未生成（守卫未跑过）")
    else:
        age = (NOW.timestamp() - _o.path.getmtime(q)) / 60
        if age > 90:
            P2.append(f"[E-模型链] GLM 配额状态 {int(age)} 分钟未更新（守卫可能没跑）")

def check_maint():
    """F-系统维护：版本/升级遗留/插件迁移/systemd失败/网关内存/根盘（只读）"""
    try:
        pr = subprocess.run(["python3", f"{WS}/tools/system-maint-check.py"],
                            capture_output=True, text=True, timeout=240)
        for ln in (pr.stdout or "").splitlines():
            if ln.startswith("[p1]"):
                P1.append("[F-系统维护] " + ln[4:].strip())
            elif ln.startswith("[p2]"):
                P2.append("[F-系统维护] " + ln[4:].strip())
    except Exception as e:
        P2.append("[F-系统维护] 自检脚本异常：%s" % e)

def sync_owner_todo():
    """把需主公本人操作的自检发现同步进待办台账（去重）"""
    try:
        subprocess.run(["python3", f"{WS}/tools/owner-todo-sync.py"],
                       capture_output=True, text=True, timeout=180)
    except Exception as e:
        P2.append("[F-待办同步] 失败：%s" % e)

def main():
    loaded = load_jobs()
    if loaded[0] is None:
        print("督察自身失败：cron 注册表拉取失败")
        subprocess.run(["bash", f"{WS}/tools/notify.sh", "督察自身失败：cron 注册表拉取失败"], timeout=90)
        sys.exit(2)  # 仅自身失败非零（评审共识）
    jobs, pulled, in_pause = loaded
    log(f"督察输入：{len(jobs)} 个任务（快照 {datetime.fromtimestamp(pulled, CST).strftime('%H:%M') if pulled else '?'}；{'暂停窗口内：不判被禁用' if in_pause else '正常窗口'}）")
    check_A(jobs, in_pause); check_BC(jobs); check_D(jobs); check_model_econ(jobs); check_maint(); sync_owner_todo()
    deep = "--deep" in sys.argv
    if deep:
        check_deep(jobs)
        hist = load_hist()
        log("\n[深度] 基线校准表（实测p50 vs 当前base）：")
        for n, h in hist.items():
            if h.get("durs"):
                ds = sorted(h["durs"]); p50 = ds[len(ds)//2]
                base = next((m["base"] for m in MANIFEST if m["name"] == n), None)
                flag = "⚠️" if base and p50 < base * 0.3 else "  "
                log(f"{flag} {n}: p50={p50:.0f}s base={base}s")
    log(f"\nP0={len(P0)} P1={len(P1)} P2={len(P2)}")
    for x in P0: log("🔴 " + x)
    for x in P1: log("🟠 " + x)
    for x in P2: log("🟡 " + x)
    os.makedirs(f"{WS}/state/inspector", exist_ok=True)
    ts = NOW.strftime("%Y%m%d-%H%M")
    with open(f"{WS}/state/inspector/report-{ts}.md", "w") as f:
        f.write(f"# 督察报告 {NOW.isoformat()}\n\n输入: {len(jobs)} 任务\n\n")
        f.write(f"## P0 ({len(P0)})\n" + "\n".join("- " + x for x in P0) + "\n\n")
        f.write(f"## P1 ({len(P1)})\n" + "\n".join("- " + x for x in P1) + "\n\n")
        f.write(f"## P2 ({len(P2)}\n" + "\n".join("- " + x for x in P2) + "\n")
    log(f"\n报告: state/inspector/report-{ts}.md")
    if P0 and "--notify" in sys.argv:
        _lines, _sup = notify_filter(P0[:10])
        if _sup:
            log(f"[去重] {_sup} 条 P0 告警 6h 内已推送过，本次跳过")
        if _lines:
            _msg = "督察P0：\n" + "\n".join(_lines)
            _faillog = f"{WS}/state/notify-fail.log"
            try:
                _before = os.path.getsize(_faillog) if os.path.exists(_faillog) else 0
            except Exception:
                _before = 0
            try:
                _r = subprocess.run(["bash", f"{WS}/tools/notify.sh", _msg], timeout=90)
                try:
                    _after = os.path.getsize(_faillog) if os.path.exists(_faillog) else 0
                except Exception:
                    _after = _before
                if _r.returncode == 0 and _after <= _before:
                    notify_mark(_lines)
                elif _r.returncode == 0:
                    log(f"\u26a0 (rc=0) notify.sh \u53ef\u80fd\u5931\u8d25\uff08fail.log \u589e\u957f {_after-_before}B\uff09\uff0c\u4e0d\u8bb0\u8d26")
                else:
                    log(f"[告警] notify.sh 失败 rc={_r.returncode}，不记账，下次继续推")
            except Exception as _e:
                log(f"[告警] notify.sh 异常：{_e}，不记账，下次继续推")
    sys.exit(0)  # P0 不再非零退出（防双重轰炸，评审共识）

if __name__ == "__main__":
    main()

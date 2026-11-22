#!/usr/bin/env python3
"""advice-ask.py v1.1 (2026-11-22) —— 秘书（双顾问）直连入口，任何管家可用，零代理。
用法：
  python3 tools/advice-ask.py --plan <文件|-> [--advisor qwen|glm|both] [--goal 文本] [--level L1|L2|L3]
  python3 tools/advice-ask.py --adopt <ts> --note "采纳了什么"
顾问：qwen = 千问 qwen4-max（更优解/成本，max_tokens 6000）｜glm = 智谱 glm-5.3（风险/漏项，2000）
输出：state/advice/<ts>-<advisor>.md，并追加 state/advice/calls.jsonl（adopted=false）
预算：读 state/advice/budget.json（与 advice.sh 共用），qwen 20/日、glm 12/日
"""
import argparse, json, os, sqlite3, ssl, sys, time, urllib.request, urllib.error, datetime

WS = "/home/j/.openclaw/workspace"
D = os.path.join(WS, "state/advice")
DB = "/home/j/.openclaw/state/openclaw.sqlite"
os.makedirs(D, exist_ok=True)

PROFILES = {
    "qwen": {
        "label": "顾问·千问",
        "kind": "anthropic",
        "url": "https://token-plan.maas.qianwenaiapi.com/apps/anthropic/v1/messages",
        "model": "qwen4-max",
        "secret": "QIANWEN_PLAN_KEY",
        "max_tokens": 6000,
        "cap": 20,
        "focus": "更优解与替代路径：有没有更省、更快、更稳的做法？给出成本与风险差；指出过度设计或可砍掉的部分。",
    },
    "glm": {
        "label": "顾问·智谱",
        "kind": "openai",
        "url": "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions",
        "model": "glm-5.3",
        "secret": "ZHIPU_API_KEY",
        "max_tokens": 2000,
        "cap": 12,
        "focus": "风险与漏项：这个方案会怎么死？哪一步最可能翻车？漏了哪些边界、回滚、验证？",
    },
}


def _load_ext():
    """外部顾问配置：state/advice/advisors.json（2026-11-22 主公令：模型可灵活替换）。
    形如 {"advisors": {"kimi": {"label":..., "kind":"anthropic|openai", "url":..., "model":...,
                                "secret":"KIMI_API_KEY", "max_tokens":2000, "cap":10, "focus":"..."}}}
    同名覆盖内置，新名直接追加；密钥名只要在 secret_store 里能取到即可。"""
    import json as _j
    fp = os.path.join(D, "advisors.json")
    if not os.path.exists(fp):
        return
    try:
        ext = _j.load(open(fp, encoding="utf-8"))
    except Exception as e:
        print("advisors.json 解析失败，用内置配置：", e)
        return
    for k, v in (ext.get("advisors") or {}).items():
        if (v or {}).get("enabled") is False:
            PROFILES.pop(k, None)
            continue
        base = dict(PROFILES.get(k) or {})
        base.update(v or {})
        base.setdefault("label", "顾问·" + k)
        base.setdefault("kind", "openai")
        base.setdefault("max_tokens", 2000)
        base.setdefault("cap", 10)
        base.setdefault("secret", "")
        base.setdefault("focus", "指出风险、漏项与边界。")
        base.setdefault("url", "")
        base.setdefault("model", k)
        PROFILES[k] = base


_load_ext()

CONTRACT = """你是「秘书」，只做一件事：审方案、补漏、找更优解。不要执行方案，不要写代码。
输出必须五段，中文，总计不超过 600 字：
① 致命问题（≤3 条，每条带触发条件）
② 漏项（≤7 条，每条一句话补法）
③ 更优解（≤3 条，带成本/风险差）
④ 可验收标准（能机器判定的优先）
⑤ 一句话结论：可执行 / 需修改 / 否决
硬约束：不夸、不复述方案；不编造数据，取不到写「不确定」；引用文件须给路径。
"""


def secret(name):
    try:
        con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
        r = con.execute(
            "select value from secret_store_entries where name=? and deleted_at_ms is null order by updated_at_ms desc limit 1",
            (name,),
        ).fetchone()
        return r[0] if r else None
    except Exception:
        return None


def budget_path():
    return os.path.join(D, "budget.json")


def budget_load():
    p = budget_path()
    today = datetime.date.today().isoformat()
    d = {}
    if os.path.exists(p):
        try:
            d = json.load(open(p))
        except Exception:
            d = {}
    if d.get("date") != today:
        d = {"date": today}
        for _k, _v in PROFILES.items():
            d[_k] = {"cap": _v.get("cap", 10), "used": 0}
    return p, d


def budget_take(key):
    p, d = budget_load()
    cap = d.get(key, {}).get("cap", PROFILES[key]["cap"])
    used = d.get(key, {}).get("used", 0)
    if used >= cap:
        return None
    d.setdefault(key, {})
    d[key]["cap"] = cap
    d[key]["used"] = used + 1
    json.dump(d, open(p, "w"), ensure_ascii=False, indent=1)
    return "%d/%d" % (d[key]["used"], cap)


def call(prof, prompt):
    key = secret(prof["secret"])
    if not key:
        raise RuntimeError("缺少密钥 " + prof["secret"])
    ctx = ssl.create_default_context()
    if prof.get("kind") == "openai":
        body = {"model": prof["model"], "max_tokens": prof["max_tokens"], "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(prof["url"], data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180, context=ctx) as r:
            d = json.loads(r.read().decode())
        ch = d.get("choices") or []
        if not ch:
            raise RuntimeError("openai 格式无 choices：" + json.dumps(d)[:200])
        return (ch[0].get("message", {}).get("content") or "").strip()
    if prof["kind"] == "anthropic":
        body = {"model": prof["model"], "max_tokens": prof["max_tokens"],
                "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(prof["url"], data=json.dumps(body).encode(),
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                              "content-type": "application/json"}, method="POST")
    else:
        body = {"model": prof["model"], "max_tokens": prof["max_tokens"], "temperature": 0.2,
                "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(prof["url"], data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key,
                                              "content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180, context=ctx) as r:
        raw = r.read().decode("utf-8", "ignore")
    j = json.loads(raw)
    if prof["kind"] == "anthropic":
        parts = j.get("content") or []
        return "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
    return (j.get("choices", [{}])[0].get("message", {}) or {}).get("content", "").strip()


def do_adopt(ts, note):
    f = os.path.join(D, "calls.jsonl")
    if not os.path.exists(f):
        print("没有调用记录")
        return 1
    out, hit = [], 0
    for line in open(f, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            out.append(line + "\n")
            continue
        if r.get("ts") == ts:
            r["adopted"] = True
            r["note"] = note
            hit += 1
        out.append(json.dumps(r, ensure_ascii=False) + "\n")
    open(f, "w", encoding="utf-8").writelines(out)
    print("已标记采纳：%s（%d 条）%s" % (ts, hit, note))
    return 0


ap = argparse.ArgumentParser()
ap.add_argument("--plan", default="-")
ap.add_argument("--advisor", default="both")
ap.add_argument("--goal", default="")
ap.add_argument("--level", default="L2")
ap.add_argument("--max-chars", type=int, default=12000)
ap.add_argument("--adopt", default="")
ap.add_argument("--note", default="")
a = ap.parse_args()

if a.adopt:
    sys.exit(do_adopt(a.adopt, a.note))

plan = sys.stdin.read() if a.plan == "-" else open(a.plan, encoding="utf-8", errors="ignore").read()
if not plan.strip():
    print("方案为空：从 stdin 或 --plan 给正文")
    sys.exit(2)
plan = plan[: a.max_chars]
goal = a.goal or "(未给出，按方案正文推断)"
if a.advisor in ("both", "all", ""):
    targets = list(PROFILES)
else:
    targets = [x.strip() for x in a.advisor.split(",") if x.strip()]
for t in targets:
    if t not in PROFILES:
        print("未知顾问：%s（可选：%s）" % (t, ", ".join(PROFILES)))
        sys.exit(2)
ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
rows = []
for t in targets:
    prof = PROFILES[t]
    left = budget_take(t)
    if not left:
        print("· %s 今日预算已用完，跳过" % prof["label"])
        continue
    prompt = "%s\n\n【顾问分工】%s\n【任务目标】%s\n【级别】%s\n【待审方案】\n%s" % (
        CONTRACT, prof["focus"], goal, a.level, plan)
    t0 = time.time()
    try:
        out, err = call(prof, prompt), ""
    except urllib.error.HTTPError as e:
        out, err = "", "HTTP %s %s" % (e.code, e.read().decode("utf-8", "ignore")[:300])
    except Exception as e:
        out, err = "", str(e)[:300]
    dt = round(time.time() - t0, 1)
    path = os.path.join(D, "%s-%s.md" % (ts, t))
    with open(path, "w", encoding="utf-8") as f:
        f.write("# %s 评审（%s）\n\n目标：%s｜级别：%s｜耗时 %ss\n\n" % (prof["label"], ts, goal, a.level, dt))
        f.write(out or ("[失败] " + err))
        f.write("\n")
    rec = {"ts": ts, "advisor": t, "model": prof["model"], "goal": goal, "level": a.level,
           "seconds": dt, "ok": bool(out), "error": err, "path": path, "budget": left, "adopted": False}
    with open(os.path.join(D, "calls.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    rows.append(rec)
    print("== %s（%s，预算 %s，%ss）%s" % (prof["label"], prof["model"], left, dt, "" if out else " 失败：" + err))
    print(out or "(无正文)")
    print("→ 已存 %s" % path)
if rows:
    print("")
    print("采纳留痕：python3 tools/advice-ask.py --adopt %s --note \"采纳了什么\"" % ts)

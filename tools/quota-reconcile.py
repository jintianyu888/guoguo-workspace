#!/usr/bin/env python3
"""quota-reconcile.py —— 单一事实源归一器（v2）
规则：
 ①非空值优先：任一源有带来源的值，就不许写 null
 ②确实拿不到 → null + reason（必带原因）
 ③每家 captured_at 必填，并标注 fresh=本轮实抓 / snapshot=快照复用（附快照时间）
 ④reset/expire 一律绝对 ISO8601(+08:00)
 ⑤两源冲突进 conflicts 并给裁定规则
"""
import json, os, re, subprocess, sys, datetime

BASE = "/home/j/.openclaw/workspace/state/model-econ"
Q = os.path.join(BASE, "quotas.json")
B = os.path.join(BASE, "balances.json")
OUT = os.path.join(BASE, "provider-state.json")
TZ = datetime.timezone(datetime.timedelta(hours=8))
NOW = datetime.datetime.now(TZ)

def iso(dt): return dt.isoformat(timespec="seconds")

def parse_abs(s):
    if not s or not isinstance(s, str): return None
    s = s.strip()
    if s.startswith("约") or "后" in s: return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try: return iso(datetime.datetime.strptime(s, fmt).replace(tzinfo=TZ))
        except ValueError: pass
    try: return iso(datetime.datetime.fromisoformat(s))
    except Exception: return None

def metric(used, limit, unit, reset_at=None, src=None, reason=None):
    m = {"used": used, "limit": limit, "unit": unit,
         "remaining": (limit - used) if (used is not None and limit is not None) else None,
         "pct": round(used / limit * 100, 2) if (used is not None and limit) else None,
         "reset_at": reset_at, "source": src}
    if m["pct"] is None and reason: m["reason"] = reason
    return m

def num(v):
    if v is None: return None
    try:
        s = str(v).replace(",", "").replace("¥", "").replace("￥", "").strip()
        f = float(re.sub(r"[^0-9.\-]", "", s) or "nan")
        return int(f) if f == int(f) else f
    except Exception:
        return None

def captured(src_captured, note=None):
    """captured_at 必填：本轮实抓则 fresh，否则标 snapshot + 原始时间"""
    iso_t = parse_abs(src_captured)
    if not iso_t:
        return {"at": iso(NOW), "kind": "unavailable", "reason": "源未提供抓取时间"}
    fresh = iso_t >= iso(NOW - datetime.timedelta(minutes=40))
    d = {"at": iso_t, "kind": "fresh" if fresh else "snapshot"}
    if note: d["note"] = note
    return d

def load(p):
    try: return json.load(open(p))
    except Exception: return {}

def ds_balance():
    try:
        out = subprocess.run(["sh", "-c", "cd /home/j/.openclaw/workspace && sh tools/ds-balance.sh 2>/dev/null"],
                             capture_output=True, text=True, timeout=90).stdout
    except Exception:
        return None
    m = re.search(r"([¥￥$])\s*([0-9]+(?:\.[0-9]+)?)", out or "")
    if not m: return None
    return {"available": float(m.group(2)), "currency": "CNY" if m.group(1) in "¥￥" else "USD",
            "captured_at": iso(NOW), "source": "api.deepseek.com/user/balance"}

def main():
    q = (load(Q).get("providers") or {})
    braw = load(B); b = (braw.get("providers") or {})
    conflicts, provs = [], {}

    # ---------- 智谱 ----------
    qz, bz, bzp = q.get("zai", {}), b.get("zai", {}), b.get("zhipu", {})
    h5_used = num(bz.get("h5_used")); h5_used = h5_used if h5_used is not None else num(qz.get("window_credits_used"))
    h5_lim = num(bz.get("h5_limit")) or num(qz.get("window_credits_limit")) or 2000
    wk_used = num(qz.get("weekly_credits_used")); wk_used = wk_used if wk_used is not None else num(bz.get("week_used"))
    wk_lim = num(qz.get("weekly_credits_limit")) or num(bz.get("week_limit")) or 10000
    h5_reset = parse_abs(bz.get("h5_reset_at")) or parse_abs(qz.get("window_reset_at"))
    h5_m = metric(h5_used, h5_lim, "credits", h5_reset, qz.get("url"),
                  reason="页面未给出 5h 用量")
    if h5_reset and h5_reset < iso(NOW):
        h5_m.update({"used": None, "pct": None, "remaining": None,
                     "reason": "5h 窗口重置时间已过期(%s)，页面数值属旧窗口残留" % h5_reset})
        conflicts.append({"provider": "zai", "field": "h5.used",
                          "values": {"quotas.json": qz.get("window_credits_used"), "balances.json": bz.get("h5_used")},
                          "rule": "窗口已重置 → 旧 used 作废", "resolved": None})
    z_exp = parse_abs(bz.get("plan_expire")) or parse_abs(bzp.get("plan_expire"))
    provs["zai"] = {
        "label": qz.get("label") or "GLM Coding（季卡）", "unit": "credits",
        "h5": h5_m,
        "week": metric(wk_used, wk_lim, "credits", parse_abs(qz.get("weekly_reset_at")), qz.get("url"),
                       reason="页面未给出周用量"),
        "plan_expire": z_exp,
        "plan_expire_source": (bz.get("plan_expire_note") or bzp.get("plan_expire_note")
                               or ("页面实读" if z_exp else None)),
        "plan_expire_reason": None if z_exp else "页面未读到到期日（coding-plan 概览页 有效期至 字段）",
        "captured_at": captured(qz.get("captured_at"), "quotas 抓取时间"),
        "status": qz.get("status") or "unknown",
    }

    # ---------- DeepSeek ----------
    bd, off = b.get("deepseek", {}), ds_balance()
    page_val = num(bd.get("available"))
    auth = (off or {}).get("available")
    provs["deepseek"] = {
        "label": "DeepSeek 开放平台", "unit": "CNY",
        "available": auth if auth is not None else page_val,
        "available_source": "api.deepseek.com/user/balance" if auth is not None else "页面抓取",
        "page_available": page_val,
        "total_spent": num(bd.get("total_spent")),
        "page_unlimited": "pay-as-you-go 无到期",
        "captured_at": captured((off or {}).get("captured_at") or bd.get("captured_at"), "官方 API" if auth is not None else "页面"),
        "status": "ok" if auth is not None else "page_only",
    }
    if auth is not None and page_val is not None and abs(auth - page_val) > 0.5:
        conflicts.append({"provider": "deepseek", "field": "available",
                          "values": {"official_api": auth, "page": page_val},
                          "rule": "官方 API 为权威", "resolved": auth})

    # ---------- Kimi ----------
    bk = b.get("kimi", {}); raw = bk.get("raw_values") or {}
    wallet = num(raw.get("balance")); wallet = wallet if wallet is not None else num(bk.get("raw_balance"))
    if wallet is None:
        tb = num(bk.get("topup_balance"))
        wallet = tb if tb not in (None, 0, 0.0) else None
    month_pct = num(bk.get("month_used_pct"))
    month_spend = num(raw.get("month_spend")); month_spend = month_spend if month_spend is not None else num(bk.get("month_spend"))
    provs["kimi"] = {
        "label": bk.get("plan") or "Kimi Plus", "unit": "percent",
        "month": metric(month_pct, 100, "percent", None, "platform.kimi.com 控制台",
                        reason="页面未给出月度已用百分比"),
        "month_pct": month_pct,
        "month_reset": bk.get("month_reset"),
        "rate_limit_pct": num(bk.get("rate_limit_pct")),
        "wallet": {"available": wallet, "unit": "CNY",
                   "source": "raw_values.balance" if num(raw.get("balance")) is not None else ("raw_balance" if num(bk.get("raw_balance")) is not None else None),
                   "reason": None if wallet is not None else "页面未读到余额且 topup 为 0"},
        "month_spend": month_spend,
        "month_spend_source": "raw_values.month_spend" if num(raw.get("month_spend")) is not None else None,
        "cycle_spend_raw": bk.get("cycle_spend"),
        "cycle_spend_note": "页面 cycle_spend 显示 ¥0.00/无限制，与 month_spend 不一，按「禁用 0 兜底」不采用",
        "plan_expire": None,
        "plan_expire_reason": bk.get("plan_expire_note") or "Kimi 控制台无到期字段（4 个页面已核）",
        "captured_at": captured(bk.get("captured_at") or (bk.get("raw_captured_at")), "控制台页面"),
        "status": "ok" if (month_pct is not None or wallet is not None) else "degraded",
    }
    # 2026-10-28 主公令：Kimi 是月卡订阅，口径固定为订阅制，禁止折算金额
    _k = provs["kimi"]
    _k["label"] = "Kimi Plus 月卡（订阅制）"
    _k["plan_kind"] = "subscription"
    _k["unit"] = "percent"
    _k["month"]["unit"] = "percent"
    _k["month_note"] = "月卡按订阅周期计，不折算金额；只报本期用量百分比与重置时间"
    for _f in ("month_spend_cny", "month_money"):
        _k.pop(_f, None)

    # ---------- MiniMax ----------
    qm, bm = q.get("minimax", {}), b.get("minimax", {})
    plan = bm.get("plan")
    provs["minimax"] = {
        "label": plan or "MiniMax", "unit": "percent",
        "h5_pct": num(bm.get("window_pct")), "week_pct": num(bm.get("weekly_pct")),
        "h5_reset_at": parse_abs(qm.get("window_reset_at")), "week_reset_at": parse_abs(qm.get("weekly_reset_at")),
        "plan": plan, "plan_expire": parse_abs(bm.get("plan_expire")),
        "plan_expire_source": bm.get("plan_expire_note") or ("/console/plan 套餐详情页" if bm.get("plan_expire") else None),
        "auto_renew": bm.get("auto_renew"), "order_id": bm.get("order_id"),
        "wallet": {"available": num(bm.get("wallet_available")), "unit": "CNY"},
        "captured_at": captured(bm.get("captured_at") or qm.get("captured_at"), "usage/plan 页面"),
        "status": "ok" if plan else "degraded",
    }
    if "未购买" in json.dumps(qm, ensure_ascii=False) and plan:
        conflicts.append({"provider": "minimax", "field": "plan",
                          "values": {"quotas.json": "钱包为空/未购买套餐", "balances.json": plan},
                          "rule": "/console/plan 为准", "resolved": plan})

    state = {"schema": "provider-state/2", "updated_at": iso(NOW),
             "run": {"started_at": iso(NOW),
                     "status": "ok" if not [c for c in conflicts if c.get("resolved") is None] else "conflicts_open",
                     "conflict_count": len(conflicts),
                     "open_conflicts": len([c for c in conflicts if c.get("resolved") is None])},
             "providers": provs, "conflicts": conflicts}
    tmp = OUT + ".tmp"; json.dump(state, open(tmp, "w"), ensure_ascii=False, indent=2); os.replace(tmp, OUT)
    print(json.dumps({"ok": True, "conflicts": len(conflicts), "out": OUT}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())

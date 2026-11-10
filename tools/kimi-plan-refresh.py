#!/usr/bin/env python3
# 2026-10-28: Kimi 月卡「用量进度」专用抓取（console 钱包页不稳，改为只读订阅页）
import importlib.util, json, os, re, sys, time
WS = "/home/j/.openclaw/workspace"
Q = os.path.join(WS, "state/model-econ/quotas.json")
URL = "https://www.kimi.com/settings/subscription"

def load_qs():
    spec = importlib.util.spec_from_file_location("qs", os.path.join(WS, "tools/quota-scrape.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def main():
    qs = load_qs()
    text = None
    for i in range(3):
        t, err = qs.page_text(URL)
        if t and "总使用量" in t:
            text = t; break
        time.sleep(5)
    if not text:
        print("FAIL no text"); return 2
    st = {"label": "Kimi 开放平台", "enabled": True, "source": "订阅页用量进度",
          "url": URL, "status": "ok", "captured_at": time.strftime("%Y-%m-%d %H:%M")}
    m1 = re.search(r"总使用量\s*([\d.]+)\s*%", text)
    m2 = re.search(r"5\s*小时用量[\s\S]{0,60}?(\d+(?:\.\d+)?)\s*%", text)
    m3 = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*后重置", text)
    _wseg = text.split("5 小时用量", 1)
    m4 = re.search(r"(\d{2}-\d{2}\s+\d{2}:\d{2})\s*后重置", _wseg[1]) if len(_wseg) > 1 else None
    m5 = re.search(r"当前余额\s*[¥￥]\s*([\d.]+)", text)
    m6 = re.search(r"有效期至[：:]\s*(\d{4}-\d{2}-\d{2})", text)
    m7 = re.search(r"\n([A-Za-z][^\n]{0,20})\n(?:重新订阅|升级订阅)", text)
    if m1: st["month_pct"] = float(m1.group(1))
    if m2: st["window_pct"] = float(m2.group(1))
    if m3: st["month_reset_at"] = m3.group(1)
    if m4: st["window_reset_at"] = m4.group(1)
    if m5: st["pack_balance"] = float(m5.group(1))
    if m6: st["plan_expire"] = m6.group(1); st["plan_expire_confident"] = True
    if m7: st["plan"] = m7.group(1).strip()
    if "month_pct" not in st:
        print("FAIL parse", text[:200].replace("\n", " ")); return 3
    q = json.load(open(Q))
    prov = q.setdefault("providers", {})
    old = prov.get("kimi") or {}
    for k in ("plan_expire", "plan_expire_confident"):
        if k not in st and old.get(k) is not None: st[k] = old[k]
    prov["kimi"] = st
    q["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    tmp = Q + ".tmp"; json.dump(q, open(tmp, "w"), ensure_ascii=False, indent=2); os.replace(tmp, Q)
    print(json.dumps({k: st.get(k) for k in ("month_pct","window_pct","month_reset_at","window_reset_at","pack_balance","plan","plan_expire")}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())

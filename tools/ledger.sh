#!/usr/bin/env bash
# 记账工具 — 收支记录与统计（税务管家用）
# 用法: ledger.sh add|list|summary|report|tax|help
set -eo pipefail
LEDGER="/home/j/.openclaw/workspace/finance/ledger.jsonl"
if [ -n "$LEDGER_OVERRIDE" ]; then LEDGER="$LEDGER_OVERRIDE"; fi
mkdir -p "$(dirname "$LEDGER")"
python3 - "$LEDGER" "$@" <<'PY'
import sys, json, os
from datetime import datetime, date
from collections import defaultdict

ledger = sys.argv[1]
args = sys.argv[2:]
cmd = args[0] if args else "help"

def load():
    rows = []
    if os.path.exists(ledger):
        with open(ledger, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
    return rows

def money(x):
    return "{:,.2f}".format(x)

def parse_num(s):
    try:
        return float(str(s).replace(",", "").replace("¥", "").replace("￥", ""))
    except Exception:
        raise SystemExit("金额无法识别: " + str(s))

def cmd_add(a):
    if len(a) < 3:
        raise SystemExit("用法: ledger.sh add <收入|支出> <金额> <分类> [备注] [日期YYYY-MM-DD]")
    typ = a[0]
    if typ not in ("收入", "支出"):
        raise SystemExit("类型必须是 收入 或 支出")
    amt = parse_num(a[1])
    cat = a[2]
    note = a[3] if len(a) > 3 else ""
    d = a[4] if len(a) > 4 else date.today().isoformat()
    rec = {"date": d, "type": typ, "amount": amt, "category": cat,
           "note": note, "created": datetime.now().astimezone().isoformat(timespec="seconds")}
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    rows = load()
    bal = sum(r["amount"] if r["type"] == "收入" else -r["amount"] for r in rows)
    print("✅ 已记账：{} {} {}｜{}".format(d, typ, money(amt), cat) + ("｜" + note if note else ""))
    print("   累计结余：{}（共 {} 笔）".format(money(bal), len(rows)))

def cmd_list(a):
    n = int(a[0]) if a and a[0].isdigit() else 20
    rows = load()[-n:]
    if not rows:
        print("（暂无记账）"); return
    print("最近 {} 笔：".format(len(rows)))
    for r in rows:
        sign = "+" if r["type"] == "收入" else "-"
        tail = "  " + r.get("note", "") if r.get("note") else ""
        print("  {}  {}  {}{}  {}{}".format(r["date"], r["type"], sign, money(r["amount"]), r["category"], tail))

def month_rows(m):
    return [r for r in load() if r["date"][:7] == m]

def cmd_summary(a):
    rows = load()
    if not rows:
        print("（暂无记账）"); return
    m = a[0] if a else date.today().isoformat()[:7]
    sub = month_rows(m)
    inc = sum(r["amount"] for r in sub if r["type"] == "收入")
    exp = sum(r["amount"] for r in sub if r["type"] == "支出")
    print("📊 {} 收支小结（{} 笔）".format(m, len(sub)))
    print("  收入合计：{}".format(money(inc)))
    print("  支出合计：{}".format(money(exp)))
    print("  结余：{}".format(money(inc - exp)))
    if exp:
        cats = defaultdict(float)
        for r in sub:
            if r["type"] == "支出":
                cats[r["category"]] += r["amount"]
        print("  支出分类：")
        for c, v in sorted(cats.items(), key=lambda x: -x[1]):
            print("    {}: {}（{:.1f}%）".format(c, money(v), v / exp * 100))
    if inc:
        cats = defaultdict(float)
        for r in sub:
            if r["type"] == "收入":
                cats[r["category"]] += r["amount"]
        print("  收入分类：")
        for c, v in sorted(cats.items(), key=lambda x: -x[1]):
            print("    {}: {}".format(c, money(v)))

def cmd_tax(a):
    rows = load()
    if not rows:
        print("（暂无记账）"); return
    m = a[0] if a else date.today().isoformat()[:7]
    sub = month_rows(m)
    inc = sum(r["amount"] for r in sub if r["type"] == "收入")
    exp = sum(r["amount"] for r in sub if r["type"] == "支出")
    print("🧾 {} 税务口径小结".format(m))
    print("  收入合计：{}（销项/营业额参考）".format(money(inc)))
    print("  支出合计：{}".format(money(exp)))
    print("  结余：{}".format(money(inc - exp)))
    cats = defaultdict(float)
    for r in sub:
        if r["type"] == "支出":
            cats[r["category"]] += r["amount"]
    if cats:
        print("  支出分类（★=通常可作成本/进项凭证）：")
        for c, v in sorted(cats.items(), key=lambda x: -x[1]):
            star = "★" if any(w in c for w in ("发票", "进项", "成本", "办公", "差旅", "服务", "采购", "房租")) else " "
            print("   {} {}: {}".format(star, c, money(v)))
    print("  凭证要留好：发票 / 合同 / 付款记录。")

def cmd_report(a):
    rows = load()
    if not rows:
        print("（暂无记账）"); return
    bym = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        m = r["date"][:7]
        if r["type"] == "收入":
            bym[m][0] += r["amount"]
        else:
            bym[m][1] += r["amount"]
    print("📈 月度总览（收入 / 支出 / 结余）")
    ti = te = 0.0
    for m in sorted(bym):
        i, e = bym[m]; ti += i; te += e
        print("  {}: {} / {} / {}".format(m, money(i), money(e), money(i - e)))
    print("  合计: {} / {} / {}".format(money(ti), money(te), money(ti - te)))

def cmd_help(_=None):
    print("记账工具用法：")
    print("  ledger.sh add <收入|支出> <金额> <分类> [备注] [日期YYYY-MM-DD]")
    print("  ledger.sh list [N]            查看最近 N 笔（默认20）")
    print("  ledger.sh summary [YYYY-MM]   某月收支小结（默认本月）")
    print("  ledger.sh tax [YYYY-MM]       税务口径小结（进销项/可抵扣提示）")
    print("  ledger.sh report              逐月总览")
    print("数据文件：" + ledger + "（JSONL，只追加）")

{"add": cmd_add, "list": cmd_list, "summary": cmd_summary,
 "report": cmd_report, "tax": cmd_tax, "help": cmd_help}.get(cmd, cmd_help)(args[1:])
PY

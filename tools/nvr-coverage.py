#!/usr/bin/env python3
"""NVR 录像覆盖核对（只查询，不下载）—— 按小时统计各通道录像段数。
复用 tools/nvr-fetch-isapi.py 的已验证 search()（curl --digest，凭据只走临时文件）。
时区实测：接口时间戳带 Z，但末段时刻 == 本地当前时刻，即设备实际按本地时间记录。
用法: tools/nvr-coverage.py --date 2026-11-09 [--channels 101,301,701,1001,1301] [--out state/work/nvr-coverage.txt]
"""
import argparse, datetime, importlib.util, os, sys

WS = "/home/j/.openclaw/workspace"
TOOL = os.path.join(WS, "tools/nvr-fetch-isapi.py")


def load_nvr():
    spec = importlib.util.spec_from_file_location("nvr_fetch_isapi", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.creds()
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--channels", default="101,301,701,1001,1301")
    ap.add_argument("--out", default=os.path.join(WS, "state/work/nvr-coverage.txt"))
    a = ap.parse_args()
    m = load_nvr()
    day = datetime.datetime.strptime(a.date, "%Y-%m-%d")
    now = datetime.datetime.now()
    is_today = (day.date() == now.date())
    chans = [int(x) for x in a.channels.split(",") if x.strip()]
    lines = [
        "# NVR 录像覆盖核对（只查询不下载）",
        "# 生成: %s" % now.strftime("%Y-%m-%d %H:%M:%S"),
        "# 核查日: %s 00:00-24:00（设备时间戳=本地时间，实测末段==当前时刻）" % a.date,
        "# 工具: tools/nvr-coverage.py --date %s" % a.date,
        "",
    ]
    summary = []
    for ch in chans:
        segs = []
        errs = []
        # 全天一次查会漏段（实测 ch301 全天窗只返回 1 段），必须按 <=4 小时窗口分段查
        for i in range(6):
            wst = day + datetime.timedelta(hours=4 * i)
            try:
                segs.extend(m.search(ch, wst, wst + datetime.timedelta(hours=4)))
            except Exception as e:
                errs.append("win%d:%s" % (i, str(e)[:80]))
        if errs and not segs:
            lines.append("ch%-5d ERROR %s" % (ch, "; ".join(errs)))
            lines.append("")
            summary.append((ch, None))
            continue
        if errs:
            lines.append("ch%-5d 部分窗口失败: %s" % (ch, "; ".join(errs)))
        hours = {}
        for s in segs:
            try:
                dt = datetime.datetime.strptime(s["start"][:19], "%Y-%m-%dT%H:%M:%S")
            except Exception:
                continue
            if dt.date() != day.date():
                continue
            try:
                e = datetime.datetime.strptime(s["end"][:19], "%Y-%m-%dT%H:%M:%S")
            except Exception:
                e = dt
            last = min(e.hour, 23) if e.date() == dt.date() else 23
            for hh in range(dt.hour, last + 1):
                hours[hh] = hours.get(hh, 0) + 1
        lines.append("ch%-5d 段数=%d%s" % (ch, len(segs), "（达 100 上限，可能截断）" if len(segs) >= 100 else ""))
        lines.append("   有段小时: %s" % (",".join("%02d" % h for h in sorted(hours)) or "无"))
        if is_today:
            last_h = now.hour
            future = list(range(last_h + 1, 24))
        else:
            last_h = 23
            future = []
        tgt = list(range(11, last_h + 1))
        gaps = [h for h in tgt if not hours.get(h, 0)]
        lines.append("   11-23 已到时段 11-%02d：缺 %s" % (last_h, ",".join("%02d" % h for h in gaps) or "无"))
        if future:
            lines.append("   未到时段（不计缺）: %s" % ",".join("%02d" % h for h in future))
        lines.append("")
        summary.append((ch, len(gaps) if tgt else 0))
    ok = sum(1 for _, g in summary if g == 0)
    lines.append("汇总: %d/%d 通道在已到时段逐小时均有录像" % (ok, len(chans)))
    for ch, g in summary:
        lines.append("  ch%-5s %s" % (ch, "ERROR" if g is None else ("全覆盖" if g == 0 else "缺 %d 小时" % g)))
    out = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w").write(out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""print-run.py —— 统一送印闸门：自检 → 送印 → 出纸确认 → 记账。

铁律落地：只有「总印量计数器增加」才算真出纸，退出码 0 才是已完成。

用法:
  print-run.py -- <送印命令...>
  print-run.py --wait 240 -- <送印命令...>          # 最多等 240 秒
  print-run.py --allow-problem -- <命令...>          # 明知缺纸也要送（谨慎）
  print-run.py --dry -- <命令...>                    # 只自检不送印

退出码:
  0 出纸已确认（计数器增加）
  3 开印前自检不通过，未送印
  4 已送出但未确认出纸（超时/计数器没动）—— 需人工看纸
  5 送印命令本身失败
"""
import argparse, datetime, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(HERE, "printer-status.py")
STATE_DIR = os.environ.get("PRINT_STATE_DIR", "/home/j/.openclaw/workspace/state/print")
LOG = os.path.join(STATE_DIR, "print-run.log")


def call(args, timeout=120):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def status_json(paper=None):
    args = [sys.executable, STATUS, "--json"]
    if paper:
        args += ["--paper", paper]
    r = call(args, timeout=60)
    try:
        return json.loads(r.stdout)
    except Exception:  # noqa: BLE001
        return None, r


def counter_now():
    r = call([sys.executable, STATUS, "--usage", "--json"], timeout=40)
    try:
        return int(json.loads(r.stdout)["counter"])
    except Exception:  # noqa: BLE001
        return None


def log(line):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), line))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=240, help="等待出纸确认的最长秒数（默认 240）")
    ap.add_argument("--poll", type=int, default=5, help="轮询间隔秒（默认 5）")
    ap.add_argument("--allow-problem", action="store_true", help="自检异常也照样送印")
    ap.add_argument("--dry", action="store_true", help="只跑自检，不送印")
    ap.add_argument("--paper", choices=["a4", "a3"], help="本次纸型，只校验对应纸盒（A4=盒1，A3=盒2）")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = [c for c in a.cmd if c != "--"]
    if not cmd and not a.dry:
        print("用法: print-run.py [选项] -- <送印命令...>", file=sys.stderr)
        return 2

    # 1) 开印前自检
    st = status_json(a.paper)
    if not isinstance(st, dict):
        print("✗ 自检失败：查不到打印机状态，已停止送印（避免打废纸）", flush=True)
        log("BLOCKED 自检不可用 cmd=%s" % " ".join(cmd))
        return 3
    if st.get("verdict") == "problem" and not a.allow_problem:
        print("✗ 自检不通过，已停止送印：", flush=True)
        for p in st.get("problems") or []:
            print("   · %s" % p, flush=True)
        log("BLOCKED 自检异常 %s cmd=%s" % (";".join(st.get("problems") or []), " ".join(cmd)))
        return 3
    for n in st.get("notes") or []:
        print("· 提示：%s" % n)
    if a.dry:
        print("✓ 自检通过（dry-run，未送印）")
        return 0

    # 2) 记基线
    base = counter_now()
    if base is None:
        print("· 注意：取不到总计数器，出纸将无法机器确认（仍继续送印）")

    # 3) 送印
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=a.wait + 120)
    except subprocess.TimeoutExpired:
        print("✗ 送印命令超时未返回", flush=True)
        log("SENDFAIL timeout cmd=%s" % " ".join(cmd))
        return 5
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if out:
        print(out)
    if r.returncode != 0:
        print("✗ 送印命令失败（退出码 %d）" % r.returncode, flush=True)
        if err:
            print(err[-800:], flush=True)
        log("SENDFAIL rc=%d cmd=%s err=%s" % (r.returncode, " ".join(cmd), err[-200:]))
        return 5
    send_s = time.time() - t0
    print("· 已送出（%.1f 秒），开始核对出纸…" % send_s, flush=True)

    # 4) 出纸确认：看计数器有没有涨
    if base is not None:
        deadline = time.time() + a.wait
        last_queue = None
        while time.time() < deadline:
            time.sleep(a.poll)
            cur = counter_now()
            if cur is None:
                continue
            if cur > base:
                pages = cur - base
                print("✓ 出纸已确认：计数器 %d → %d，本单 %d 页（%.1f 秒）" % (base, cur, pages, time.time() - t0))
                call([sys.executable, STATUS, "--snapshot"], timeout=40)
                log("CONFIRMED pages=%d counter=%d->%d cmd=%s" % (pages, base, cur, " ".join(cmd)))
                return 0
            j = call([sys.executable, STATUS, "--jobs", "--json"], timeout=40)
            try:
                jd = json.loads(j.stdout)
                last_queue = len(jd.get("jobs") or []) if jd.get("ok") else last_queue
            except Exception:  # noqa: BLE001
                pass
        print("✗ 已送出但 %d 秒内计数器没有变化 —— 请到机器看是否有纸/是否卡在队列（队列状态: %s）"
              % (a.wait, "空" if last_queue == 0 else (("剩 %s 个任务" % last_queue) if last_queue is not None else "未知")),
              flush=True)
        call([sys.executable, STATUS, "--snapshot"], timeout=40)
        log("UNCONFIRMED counter=%d unchanged cmd=%s" % (base, " ".join(cmd)))
        return 4

    print("· 无计数器基线，无法机器确认出纸，请人工看一眼", flush=True)
    log("UNCONFIRMED no-baseline cmd=%s" % " ".join(cmd))
    return 4


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""网络打印机直推工具（9100 原始打印）。

用法：
  python3 print.py --discover                        # 扫描局域网找打印机（找 9100/631）
  python3 print.py --host 192.168.1.50 FILE [FILE..] # 把文件发到打印机
  python3 print.py --host 1.2.3.4 --port 9100 --test # 只探测端口通不通
  python3 print.py --host IP --duplex long --paper a3 FILE  # PJL：双面(长边)+A3纸

说明：
  - 9100 是「原始打印」端口：打印机必须自己能解释该格式（PDF / PostScript / PCL）。
  - 默认（不带 --duplex/--paper）走原来的裸文件直推，行为不变。
  - 带 --duplex/--paper 时用 PJL 包裹（@PJL JOB … ENTER LANGUAGE=PDF … EOJ）；
    纸盒不写死，由打印机按 PAPER=A3/A4 自选。若发现 PJL 被文档内 setpagedevice
    覆盖或出废纸，立即停手上报（2026-09-26 果果批准范围）。
"""
import argparse
import concurrent.futures
import ipaddress
import os
import socket
import sys

DEFAULT_PORTS = (9100, 631)
UEL = b"%-12345X\r\n"


def probe(host, port, timeout=0.6):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return host, port
    except Exception:
        return None


def discover(subnet, ports=DEFAULT_PORTS, workers=128):
    found = []
    hosts = [str(h) for h in ipaddress.ip_network(subnet, strict=False).hosts()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(probe, h, p) for h in hosts for p in ports]
        for f in concurrent.futures.as_completed(futs):
            r = f.result()
            if r:
                found.append(r)
    return sorted(set(found))


def pjl_prelude(duplex=None, paper=None, copies=1, lang="PDF"):
    lines = [UEL.decode(), "@PJL JOB\r\n", f"@PJL SET COPIES={copies}\r\n"]
    if paper:
        lines.append(f"@PJL SET PAPER={paper.upper()}\r\n")
    if duplex:
        lines.append("@PJL SET DUPLEX=ON\r\n")
        bind = "LONGEDGE" if duplex == "long" else "SHORTEDGE"
        lines.append(f"@PJL SET BINDING={bind}\r\n")
    lines.append(f"@PJL ENTER LANGUAGE={lang}\r\n")
    return "".join(lines).encode()


def send_raw(host, port, path, timeout=60, prelude=b"", epilog=b""):
    size = os.path.getsize(path)
    with socket.create_connection((host, port), timeout=timeout) as s:
        if prelude:
            s.sendall(prelude)
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                s.sendall(chunk)
        if epilog:
            s.sendall(epilog)
        try:
            s.shutdown(socket.SHUT_WR)
        except Exception:
            pass
    return size


def main():
    ap = argparse.ArgumentParser(description="网络打印机直推（9100）")
    ap.add_argument("files", nargs="*", help="要打印的文件")
    ap.add_argument("--host", help="打印机 IP")
    ap.add_argument("--port", type=int, default=9100, help="端口（默认 9100）")
    ap.add_argument("--discover", metavar="SUBNET", nargs="?", const="auto",
                    help="扫描局域网找打印机，例如 192.168.1.0/24（可省略=自动猜）")
    ap.add_argument("--test", action="store_true", help="只测试端口连通性")
    ap.add_argument("--duplex", choices=["long", "short"], default=None,
                    help="双面打印：long=长边翻页（乐谱用），short=短边；需 PJL")
    ap.add_argument("--paper", choices=["a3", "a4"], default=None,
                    help="PJL 指定纸型（默认不带；文件已是标准 A3/A4 页面时打印机可自选）")
    args = ap.parse_args()

    if args.discover:
        subnet = args.discover
        if subnet == "auto":
            subnet = "192.168.1.0/24"
            print(f"(未指定网段，先试 {subnet})", file=sys.stderr)
        print(f"扫描 {subnet} …（找打印机端口 {'/'.join(map(str, DEFAULT_PORTS))}）")
        found = discover(subnet)
        if not found:
            print("没找到。请确认打印机与这台机器在同一局域网，或直接告诉我它的 IP。")
        for h, p in found:
            tag = " ← 很可能是打印机" if p == 9100 else ""
            print(f"  {h}:{p}{tag}")
        return

    if not args.host:
        ap.error("需要 --host <打印机IP>（或用 --discover 扫描）")

    if args.test:
        r = probe(args.host, args.port, timeout=3)
        print(f"{args.host}:{args.port} → {'通 ✅' if r else '不通 ❌'}")
        return

    if not args.files:
        ap.error("请给要打印的文件")

    use_pjl = False  # 2026-10-01 铁证：这台 e-STUDIO 不吃 PJL 包裹（加了就把作业源码当文本打出）→ 一律裸发，靠 PS 自带 setpagedevice + 打印机自动识别
    epilog = (UEL.decode() + "@PJL EOJ\r\n" + UEL.decode()).encode() if use_pjl else b""

    for path in args.files:
        if not os.path.isfile(path):
            print(f"跳过（文件不存在）：{path}", file=sys.stderr)
            continue
        # 2026-10-01：语言按文件类型（必须在 path 定义之后）
        _lang = "POSTSCRIPT" if path.lower().endswith((".ps", ".eps")) else "PDF"
        prelude = pjl_prelude(args.duplex, args.paper, lang=_lang) if use_pjl else b""
        try:
            n = send_raw(args.host, args.port, path, prelude=prelude, epilog=epilog)
            # 2026-10-01 主公令：主会话直推也要登记进打印管家同一本台账
            try:
                import subprocess as _sp
                _r = _sp.run(["python3", "/home/j/.openclaw/workspace/tools/print-ledger-add.py", path, "果果直推（main agent）"],
                             capture_output=True, text=True, timeout=20)
                _msg = (_r.stdout or _r.stderr or "").strip()
                if _msg: print("  " + _msg)
            except Exception as _e:
                print(f"  ⚠️ 台账登记失败（不影响打印）: {_e}")
            flags = f" [PJL paper={args.paper or '-'} duplex={args.duplex or '-'}]" if use_pjl else ""
            print(f"已发送 {path}（{n} 字节）→ {args.host}:{args.port}{flags}")
        except Exception as e:
            print(f"发送失败 {path}: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

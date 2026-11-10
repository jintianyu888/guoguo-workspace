#!/usr/bin/env python3
"""booklet-ps.py —— 骑马钉 PS 生成 + 打印（东芝 PS3 专用，绕开 PDF 不兼容）

定版（2026-09-27 主公实测确认）：
  - 装订 BINDING=LONGEDGE（长边翻页）
  - 背面整页旋转 180°（关键！A3 横向 + 长边双面必须这样）
  - 纸型 PAPER=A3，双面 DUPLEX=ON
  - 语言 POSTSCRIPT（这台机器不吃 PDF）

用法:
  python3 booklet-ps.py --pages 8 --out /home/j/.openclaw/workspace/state/tmp/x.ps          # 只生成
  python3 booklet-ps.py --pages 8 --send 192.168.1.80      # 生成并送印（带去重）
"""
import argparse, hashlib, json, os, socket, sys, time

W, H = 1190.0, 842.0      # A3 横向 pt
AW, AH = 595.0, 842.0     # A4 半幅
LEDGER = os.path.expanduser("~/.openclaw/workspace/state/print-sent.json")
DEDUP_SEC = 300           # 5 分钟内同内容不重发

def make_ps(total, ver="OC", note="OpenClaw 骑马钉"):
    sides = []
    for k in range(1, total // 4 + 1):
        sides.append((total - 2*k + 2, 2*k - 1, "front"))
        sides.append((2*k, total - 2*k + 1, "back"))
    ps = ["%!PS-Adobe-3.0", "<< /PageSize [%.0f %.0f] >> setpagedevice" % (W, H)]
    for li, ri, side in sides:
        if side == "back":
            ps.append("[-1 0 0 -1 %.0f %.0f] concat" % (W, H))
        for p, x in ((li, 0.0), (ri, AW)):
            ps.append("newpath %.1f 18 moveto %.1f 18 lineto %.1f %.1f lineto %.1f %.1f lineto closepath 5 setlinewidth stroke"
                      % (x+18, x+AW-18, x+AW-18, AH-18, x+18, AH-18))
            ps.append("/Helvetica-Bold findfont 330 scalefont setfont")
            ps.append("%.1f %.1f moveto (P%d) show" % (x + AW*0.30, AH*0.44, p))
            ps.append("/Helvetica-Bold findfont 42 scalefont setfont")
            ps.append("%.1f %.1f moveto (%s %s) show" % (x + AW*0.16, AH*0.72, ver, side))
        ps.append("newpath %.1f 18 moveto %.1f %.1f lineto 3 setlinewidth 0.6 0.6 0.6 setrgbcolor stroke 0 setgray" % (AW, AW, H-18))
        ps.append("showpage")
    return ("\n".join(ps)).encode()

def wrap(body, name):
    uel = b"\x1b%-12345X"
    hdr  = uel + ("@PJL JOB NAME=\"%s\"\r\n" % name).encode()
    hdr += b"@PJL SET COPIES=1\r\n@PJL SET PAPER=A3\r\n@PJL SET DUPLEX=ON\r\n"
    hdr += b"@PJL SET BINDING=LONGEDGE\r\n@PJL ENTER LANGUAGE=POSTSCRIPT\r\n"
    return hdr + body + b"\n" + uel + b"@PJL EOJ\r\n"

def dedup_ok(payload):
    h = hashlib.sha256(payload).hexdigest()[:16]
    led = {}
    if os.path.exists(LEDGER):
        try: led = json.load(open(LEDGER))
        except Exception: led = {}
    last = led.get(h, 0)
    if time.time() - last < DEDUP_SEC:
        print("  ⏭  去重：相同内容 %ds 内已发过（%s），跳过" % (DEDUP_SEC, h))
        return False
    led[h] = time.time()
    led = {k: v for k, v in led.items() if time.time() - v < 86400}
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    json.dump(led, open(LEDGER, "w"))
    return True

def send(payload, host, port=9100):
    if not dedup_ok(payload):
        return False
    s = socket.socket(); s.settimeout(25)
    s.connect((host, port)); s.sendall(payload); s.close()
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=8)
    ap.add_argument("--out", default="/home/j/.openclaw/workspace/state/tmp/booklet.ps")
    ap.add_argument("--send", default=None, help="打印机 IP")
    ap.add_argument("--label", default="OC")
    a = ap.parse_args()
    body = make_ps(a.pages, a.label)
    payload = wrap(body, "booklet%s" % a.label)
    open(a.out, "wb").write(payload)
    print("  ✅ 生成 %s（%d 页 → %d 张 A3 双面，%d 字节）" % (a.out, a.pages, a.pages//4, len(payload)))
    if a.send:
        ok = send(payload, a.send)
        print("  %s 送印 %s" % ("✅" if ok else "⏭", a.send))

if __name__ == "__main__":
    main()
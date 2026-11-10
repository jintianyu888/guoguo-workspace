#!/usr/bin/env python3
"""海康 NVR 取帧（ISAPI 版）v1.1 —— curl --digest（已实测），分段下载 + ffmpeg 抽帧 + 立即删临时文件。
双审必改项：分段小窗、size 阈值跳空段、-an/-sn/-dn/-threads 2/-frames:v、下载前查磁盘、
孤儿清扫、RTSP 保底开关（--source rtsp 交给旧脚本）。

用法: tools/nvr-fetch-isapi.py --channel 101 --date 2026-10-24 --hours 13 --fps 0.2
"""
import argparse, datetime, glob, json, os, re, subprocess, sys, tempfile
from xml.etree import ElementTree as ET

WS = "/home/j/.openclaw/workspace"
ENVF = os.path.expanduser("~/.config/hik-nvr.env")
IP = "192.168.1.103"
PWD = ""

LOGF = os.path.join(WS, "state/work/nvr-isapi.log")

def log(m):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), m)
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOGF), exist_ok=True)
        with open(LOGF, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def creds():
    global IP, PWD
    d = {}
    for line in open(ENVF):
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            d[k.strip()] = v.strip()
    IP = d.get("HIK_NVR_IP", IP)
    PWD = d.get("HIK_NVR_PASS", "")

def curl(args, timeout=900):
    cmd = ["curl", "-sS", "--digest", "-u", "admin:%s" % PWD] + args
    p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return p.returncode, (p.stdout or b""), (p.stderr or b"").decode("utf-8", "ignore")

def post_xml(path, body, timeout=120):
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
        f.write(body)
        bf = f.name
    try:
        rc, out, err = curl(["-X", "POST", "-H", "Content-Type: application/xml",
                             "--data-binary", "@" + bf, "http://%s%s" % (IP, path)], timeout)
        return rc, out, err
    finally:
        os.unlink(bf)

def search(ch, start, end):
    sid = "8f2a1c11-1111-2222-3333-%012d" % int(start.timestamp())
    body = ("""<?xml version="1.0" encoding="utf-8"?><CMSearchDescription>"""
            """<searchID>%s</searchID><trackList><trackID>%d</trackID></trackList>"""
            """<timeSpanList><timeSpan><startTime>%s</startTime><endTime>%s</endTime></timeSpan></timeSpanList>"""
            """<maxResults>100</maxResults><searchResultPostion>0</searchResultPostion>"""
            """<metadataList><metadataDescriptor>//recordType.meta.std-cgi.com</metadataDescriptor></metadataList>"""
            """</CMSearchDescription>""") % (sid, ch,
                                            start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                            end.strftime("%Y-%m-%dT%H:%M:%SZ"))
    rc, out, err = post_xml("/ISAPI/ContentMgmt/search", body)
    if rc != 0 or not out:
        raise RuntimeError("search rc=%d %s" % (rc, err[:120]))
    root = ET.fromstring(out)
    segs = []
    for item in root.iter():
        if item.tag.endswith("searchMatchItem"):
            uri = st = et = None
            for c in item.iter():
                t = c.tag.split("}")[-1]
                if t == "playbackURI": uri = (c.text or "").strip()
                elif t == "startTime": st = c.text
                elif t == "endTime": et = c.text
            if uri:
                # size 只存在于 playbackURI 的 size= 参数里（实测：不是独立标签）
                m = re.search(r"size=(\d+)", uri)
                segs.append({"uri": uri, "size": int(m.group(1)) if m else 0,
                             "start": st, "end": et})
    return segs

def dl_segment(uri, dst):
    body = ('<downloadRequest version="1.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">'
            '<playbackURI>%s</playbackURI></downloadRequest>') % uri.replace("&", "&amp;")
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as f:
        f.write(body); bf = f.name
    try:
        rc, out, err = curl(["-X", "POST", "-H", "Content-Type: application/xml",
                             "--data-binary", "@" + bf, "-o", dst,
                             "http://%s/ISAPI/ContentMgmt/download" % IP], timeout=1800)
        return rc, os.path.getsize(dst) if os.path.exists(dst) else 0, err
    finally:
        os.unlink(bf)

def extract(seg, outdir, fps, max_frames, idx=1):
    pref = "s%02d_" % idx
    cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-an", "-sn", "-dn",
           "-threads", "2", "-i", seg, "-vf", "fps=%s" % fps,
           "-frames:v", str(max_frames), os.path.join(outdir, pref + "%05d.jpg")]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    n = len([x for x in os.listdir(outdir) if x.startswith(pref)])
    return p.returncode, n, (p.stderr or "").strip()[-200:]

def free_mb(p="/tmp"):
    st = os.statvfs(p)
    return st.f_bavail * st.f_frsize // 1048576

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="101")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--hours", default="13")
    ap.add_argument("--fps", type=float, default=0.2)
    ap.add_argument("--window", type=int, default=120)
    ap.add_argument("--min-mb", type=float, default=5.0)
    ap.add_argument("--max-frames", type=int, default=60)
    ap.add_argument("--max-segments", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(WS, "state/tmp/nvr_isapi"))
    ap.add_argument("--source", default="isapi", choices=["isapi", "rtsp"])
    a = ap.parse_args()

    if a.source == "rtsp":
        cmd = [sys.executable, os.path.join(WS, "tools/nvr-face-scan.py"), "--date", a.date,
               "--channels", a.channel, "--hours", a.hours, "--fps", str(a.fps)]
        log("回退 RTSP: " + " ".join(cmd))
        return subprocess.call(cmd)

    creds()
    if not PWD:
        log("缺 NVR 口令"); return 2
    tmp = os.path.join(a.out, "_seg"); os.makedirs(tmp, exist_ok=True)
    # 孤儿清扫：并发进程各自的 seg-*.ps 若因 kill 残留，超过 1 小时的删掉（双审必改项）
    _now = datetime.datetime.now().timestamp()
    for _f in glob.glob(os.path.join(tmp, "seg-*.ps")):
        try:
            if _now - os.path.getmtime(_f) > 3600:
                os.remove(_f); log("清扫孤儿临时段 %s" % _f)
        except OSError:
            pass
    # 注意：不再无条件清空 _seg —— 多个通道进程共用该目录，清空会打断别人的在途下载

    hours = []
    for part in a.hours.split(","):
        if "-" in part:
            s, e = part.split("-"); hours += list(range(int(s), int(e) + 1))
        else:
            hours.append(int(part))

    tot_seg = tot_frames = 0
    seen = set()   # 海康按整块返回，同一块会被多个检索窗口重复命中 → 去重
    for h in hours:
        local0 = datetime.datetime.strptime("%s %02d:00" % (a.date, h), "%Y-%m-%d %H:%M")
        cur = local0 - datetime.timedelta(hours=8)
        endh = cur + datetime.timedelta(hours=1)
        outdir = os.path.join(a.out, "ch%s_%s_%02d" % (a.channel, a.date, h))
        os.makedirs(outdir, exist_ok=True)
        while cur < endh:
            nxt = min(cur + datetime.timedelta(seconds=a.window), endh)
            try:
                segs = search(int(a.channel), cur, nxt)
            except Exception as e:
                log("检索失败 %s: %s" % (cur.strftime("%H:%M"), str(e)[:90])); cur = nxt; continue
            if not segs:
                log("%s-%s 无录像段" % (cur.strftime("%H:%M"), nxt.strftime("%H:%M")))
            for s in segs:
                # 海康返回的是整块录像段；把 URI 时间改写成我们要的小窗（实测设备支持任意子区间）
                try:
                    bs = datetime.datetime.strptime(s["start"], "%Y-%m-%dT%H:%M:%SZ")
                    be = datetime.datetime.strptime(s["end"], "%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    bs, be = cur, nxt
                w0 = max(cur, bs); w1 = min(nxt, be)
                if (w1 - w0).total_seconds() < 20:
                    continue
                bkey = (s["start"], s["end"])
                if bkey in seen:
                    continue
                seen.add(bkey)
                uri = re.sub(r"starttime=\d+T\d+Z", "starttime=" + w0.strftime("%Y%m%dT%H%M%SZ"), s["uri"])
                uri = re.sub(r"endtime=\d+T\d+Z", "endtime=" + w1.strftime("%Y%m%dT%H%M%SZ"), uri)
                mb = (s["size"] or 0) / 1048576.0 * ((w1 - w0).total_seconds() / max((be - bs).total_seconds(), 1))
                if mb < a.min_mb:
                    log("跳过短段 预计%.1fMB（窗口 %.0fs）" % (mb, (w1 - w0).total_seconds())); continue
                if free_mb() < 2000:
                    log("磁盘不足 2GB，停止"); return 3
                dst = os.path.join(tmp, "seg-%s-%d-%d.ps" % (a.channel, os.getpid(), tot_seg))
                t0 = datetime.datetime.now()
                rc, n, err = dl_segment(uri, dst)
                if rc != 0 or n == 0:
                    log("下载失败 rc=%d %s" % (rc, err[:90])); continue
                dt = max((datetime.datetime.now() - t0).total_seconds(), 1)
                frc, nf, ferr = extract(dst, outdir, a.fps, a.max_frames, tot_seg + 1)
                tot_seg += 1; tot_frames += nf
                log("段 %s %.0fMB %.0fs %.1fMB/s → 帧+%d rc=%d %s" % (
                    s["start"], n / 1048576.0, dt, n / 1048576.0 / dt, nf, frc, ferr[:70]))
                try:
                    os.remove(dst)
                except FileNotFoundError:
                    pass
                if a.max_segments and tot_seg >= a.max_segments:
                    log("达到 --max-segments，结束"); return 0
            cur = nxt
    log("完成：段 %d，帧 %d，输出 %s" % (tot_seg, tot_frames, a.out))
    return 0

if __name__ == "__main__":
    sys.exit(main())

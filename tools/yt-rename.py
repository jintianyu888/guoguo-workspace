#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""yt-rename.py —— 把 yt-dlp 下载的 <id>.mp4 改成可读名字。
用法: yt-rename.py <目录> [前缀]
规则: 名字=前缀 + 标题(清洗) + 时长；同目录 .wav 同步改名。
"""
import os, re, sys, subprocess, glob
PROXY="http://172.18.240.1:7891"
YTDLP="/home/j/.local/bin/yt-dlp"
ID_RE=re.compile(r'^-?[A-Za-z0-9_-]{11}$')
def dur(p):
    try:
        o=subprocess.run(["/home/j/.local/bin/ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p],capture_output=True,text=True,timeout=30).stdout.strip()
        return int(float(o))
    except Exception:
        return 0
def clean(s):
    s=re.sub(r'[\\/:*?"<>|]',' ',s)
    s=re.sub(r'\s+',' ',s).strip()
    return s[:80]
def title(i):
    env=dict(os.environ, HTTPS_PROXY=PROXY, HTTP_PROXY=PROXY)
    try:
        r=subprocess.run([YTDLP,"--no-warnings","--skip-download","--print","%(title)s",
                          f"https://www.youtube.com/watch?v={i}"],capture_output=True,text=True,timeout=90,env=env)
        return r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""
    except Exception:
        return ""
d=sys.argv[1] if len(sys.argv)>1 else "."
prefix=sys.argv[2] if len(sys.argv)>2 else ""
for f in sorted(glob.glob(os.path.join(d,"*.mp4"))):
    b=os.path.basename(f)[:-4]
    if not ID_RE.match(b): continue
    t=title(b.lstrip("-"))
    if not t: continue
    sec=dur(f); m=sec//60
    new=clean(f"{prefix}{t}-{m}分")
    os.rename(f, os.path.join(d,new+".mp4"))
    w=os.path.join(d,b+".wav")
    if os.path.exists(w): os.rename(w, os.path.join(d,new+".wav"))
    print(f"{b} -> {new}")

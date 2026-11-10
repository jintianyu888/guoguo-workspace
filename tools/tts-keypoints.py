#!/usr/bin/env python3
"""tts-keypoints.py v2 —— 挑重点 + 口语化规范化（数字/单位/英文缩写都转中文读法，便于听清）"""
import re, sys

D = "零一二三四五六七八九"

def num2cn(n):
    n = str(n)
    if "." in n:
        a, b = n.split(".", 1)
        return num2cn(a) + "点" + "".join(D[int(c)] if c.isdigit() else c for c in b)
    if not n.isdigit():
        return n
    n = n.lstrip("0") or "0"
    units = ["", "十", "百", "千"]
    if len(n) <= 4:
        out, L = "", len(n)
        for i, c in enumerate(n):
            d = int(c); p = L - i - 1
            if d: out += D[d] + units[p]
            elif out and not out.endswith("零"): out += "零"
        out = out.rstrip("零").replace("一十", "十")
        return out or "零"
    # 万/亿 分段
    res = ""
    for i, grp in enumerate(reversed([n[max(0, len(n)-4*(j+1)):len(n)-4*j] for j in range((len(n)+3)//4)])):
        v = num2cn(grp)
        if v != "零": res = v + ["", "万", "亿", "万亿"][i] + res
    return res or "零"

def norm(s):
    s = re.sub(r"(\d+(?:\.\d+)?)\s*(MB|Mb)", lambda m: num2cn(m.group(1)) + "兆", s)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*(GB|Gb|G)\b", lambda m: num2cn(m.group(1)) + "吉", s)
    s = re.sub(r"(\d+(?:\.\d+)?)\s*(KB|Kb|K)\b", lambda m: num2cn(m.group(1)) + "K", s)
    s = re.sub(r"(?<![A-Za-z])(\d+(?:\.\d+)?)%", lambda m: "百分之" + num2cn(m.group(1)), s)
    s = re.sub(r"(\d+(?:\.\d+)?)(?=[^0-9A-Za-z]|$)", lambda m: num2cn(m.group(1)), s)
    for a, b in [("token", "令牌"), ("Token", "令牌"), ("GPU", "显卡"), ("CPU", "处理器"),
                 ("ASR", "语音识别"), ("OCR", "图片识别"), ("TTS", "语音合成"), ("API", "接口"),
                 ("cuDNN", "库丹"), ("torch", "托奇"), ("URL", "链接"), ("OK", "好的")]:
        s = s.replace(a, b)
    return s

txt = open(sys.argv[1], encoding="utf-8", errors="ignore").read()
lines = []
for ln in txt.splitlines():
    l = ln.strip()
    if not l or l.startswith("```") or l.startswith("---"): continue
    keep = ("**" in l) or re.match(r"^[0-9]+[.、)]", l) or l.startswith("-") or l.startswith("·")
    if keep: lines.append(l)
if not lines: lines = [x.strip() for x in txt.splitlines() if x.strip()][:6]
out = []
for l in lines[:12]:
    l = re.sub(r"[*`#>\[\]]", "", l)
    l = re.sub(r"https?://\S+", "", l)
    l = re.sub(r"(MEDIA|reply_to_current|audio_as_voice)\S*", "", l)
    l = re.sub(r"^[0-9]+[.、)]\s*", "", l)
    l = re.sub(r"^-\s*", "", l)
    l = re.sub(r"\s+", " ", l).strip()
    l = norm(l)
    l = l.rstrip("。！？!?，,、；;：:")   # 2026-10-02 修：去行尾标点，避免拼出「。。」造成多余停顿
    if l: out.append(l)
s = "。".join(out)[:420]
print(s)
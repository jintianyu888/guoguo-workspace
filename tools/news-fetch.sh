#!/bin/sh
# news-fetch.sh v7.3 —— 天气 + 农历黄历 + 穿衣指南 + 今日必知 + 分类新闻（零 token）
WS=/home/j/.openclaw/workspace
CFG=$WS/state/news-config.json
ST=$WS/state

python3 - "$CFG" "$ST" <<"PY"
import json, sys, os, re, datetime, urllib.request

cfg = json.load(open(sys.argv[1]))
STATE = sys.argv[2]
city = cfg.get("city", "大连")
TZ8 = datetime.timezone(datetime.timedelta(hours=8))
today = datetime.datetime.now(TZ8).date()
WD = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"]

import subprocess
def fetch(url, timeout=20):
    try:
        r = subprocess.run(["curl", "-s", "--max-time", str(timeout), "-H",
                            "User-Agent: Mozilla/5.0 (news-fetch)", url], capture_output=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    except Exception:
        pass
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (news-fetch)"})
    return urllib.request.urlopen(req, timeout=timeout).read()

def conv24(s):
    s = (s or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})\s*(AM|PM)?$", s)
    if not m:
        return s
    h, mi, ap = int(m.group(1)), m.group(2), m.group(3)
    if ap == "PM" and h != 12: h += 12
    if ap == "AM" and h == 12: h = 0
    return "%02d:%s" % (h, mi)

# ---------------- 天气（j1 详细 → 失败则 format=3 兜底） ----------------
w = None
import time
for _ in range(3):
    try:
        w = json.loads(fetch("https://wttr.in/%s?format=j1" % city, 12).decode("utf-8", "replace"))
        break
    except Exception:
        w = None
        time.sleep(1)
desc = ""; tmin = tmax = None; wind = hum = uv = rain = None; sr = ""; ss = ""
if w:
    try:
        cur = w["current_condition"][0]; d0 = w["weather"][0]
        desc = cur["weatherDesc"][0]["value"].strip()
        tmin, tmax = int(d0["mintempC"]), int(d0["maxtempC"])
        wind = int(float(cur.get("windspeedKmph") or 0))
        hum = cur.get("humidity", "?")
        uv = cur.get("uvIndex", "0")
        ast = (d0.get("astronomy") or [{}])[0]
        sr = conv24(ast.get("sunrise", "")); ss = conv24(ast.get("sunset", ""))
        hs = d0.get("hourly") or []
        rain = max(int(h.get("chanceofrain") or 0) for h in hs) if hs else 0
    except Exception:
        pass
if w:
    print("⛅ 天气（%s）：%s，%s~%s℃" % (city, desc or "—", tmin, tmax))
    print("   湿度%s%% · 风%s km/h · 降雨概率%s%% · 紫外线%s · 日出%s 日落%s" % (hum, wind, rain, uv, sr, ss))
else:
    try:
        simple = fetch("https://wttr.in/%s?format=3&lang=zh" % city, 12).decode("utf-8", "replace").strip()
        print("⛅ 天气（%s）：%s" % (city, simple))
    except Exception:
        print("⛅ 天气（%s）：(天气源暂不可用，稍后重试)" % city)
# ---------------- 额外城市天气（按星期/日期生效，config: weather_extra） ----------------
try:
    for ec in (cfg.get("weather_extra") or []):
        ecity = str(ec.get("city") or "").strip()
        if not ecity:
            continue
        days = ec.get("days") or []
        if days and WD[today.weekday()] not in days:
            continue
        frm = str(ec.get("from") or "")
        to = str(ec.get("to") or "")
        if frm and today.isoformat() < frm:
            continue
        if to and today.isoformat() > to:
            continue
        ew = None
        for _ in range(2):
            try:
                ew = json.loads(fetch("https://wttr.in/%s?format=j1" % ecity, 12).decode("utf-8", "replace"))
                break
            except Exception:
                ew = None
                time.sleep(1)
        if ew:
            ecur = ew["current_condition"][0]; ed0 = ew["weather"][0]
            edesc = ecur["weatherDesc"][0]["value"].strip()
            etmin, etmax = int(ed0["mintempC"]), int(ed0["maxtempC"])
            ewind = int(float(ecur.get("windspeedKmph") or 0))
            ehum = ecur.get("humidity", "?")
            euv = ecur.get("uvIndex", "0")
            ehs = ed0.get("hourly") or []
            erain = max(int(h.get("chanceofrain") or 0) for h in ehs) if ehs else 0
            east = (ed0.get("astronomy") or [{}])[0]
            esr = conv24(east.get("sunrise", "")); ess = conv24(east.get("sunset", ""))
            etm = (etmin + etmax) / 2.0
            if etm >= 28: ebase = "短袖、透气薄装，注意防晒补水"
            elif etm >= 24: ebase = "短袖或薄衬衫，随身一件薄外套"
            elif etm >= 20: ebase = "长袖衬衫/薄卫衣，外搭薄外套"
            elif etm >= 16: ebase = "薄毛衣或卫衣 + 夹克/风衣"
            elif etm >= 12: ebase = "毛衣 + 风衣/厚夹克"
            elif etm >= 8: ebase = "厚外套或薄羽绒，内搭毛衣"
            else: ebase = "羽绒服/厚外套，注意头手保暖"
            etips = []
            if etmax - etmin >= 8: etips.append("昼夜温差%d℃，早晚加衣" % (etmax - etmin))
            if erain >= 40: etips.append("降雨概率%d%%，带伞" % erain)
            if ewind >= 30: etips.append("风力较大（%d km/h）" % ewind)
            print("⛅ 天气（%s）：%s，%s~%s℃" % (ecity, edesc or "—", etmin, etmax))
            print("   湿度%s%% · 风%s km/h · 降雨概率%s%% · 紫外线%s · 日出%s 日落%s" % (ehum, ewind, erain, euv, esr, ess))
            print("🧥 穿衣（%s）：%s%s" % (ecity, ebase, ("；" + "；".join(etips)) if etips else ""))
        else:
            print("⛅ 天气（%s）：(天气源暂不可用，稍后重试)" % ecity)
except Exception:
    pass
# ---------------- 仅天气地点（config: weather_only，只报天气） ----------------
try:
    for wp in (cfg.get("weather_only") or []):
        wname = wp.get("name") or wp.get("city") or ""
        wq = wp.get("query") or wname
        if not wname:
            continue
        ww = None
        for _ in range(2):
            try:
                ww = json.loads(fetch("https://wttr.in/%s?format=j1" % wq, 12).decode("utf-8", "replace"))
                break
            except Exception:
                ww = None
                time.sleep(1)
        if ww:
            wc = ww["current_condition"][0]; wd = ww["weather"][0]
            wdesc = wc["weatherDesc"][0]["value"].strip()
            wtmin, wtmax = int(wd["mintempC"]), int(wd["maxtempC"])
            whs = wd.get("hourly") or []
            wrain = max(int(h.get("chanceofrain") or 0) for h in whs) if whs else 0
            print("⛅ %s：%s，%s~%s℃，降雨概率%s%%" % (wname, wdesc or "—", wtmin, wtmax, wrain))
        else:
            print("⛅ %s：(天气源暂不可用)" % wname)
except Exception:
    pass

print()

# ---------------- 农历 / 黄历（香港天文台对照表，缓存 state/） ----------------
def hko_text(y):
    p = os.path.join(STATE, "hko-cal-%d.txt" % y)
    need = True
    if os.path.exists(p):
        age = (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(p))).days
        if age < 15:
            need = False
    if need:
        try:
            data = fetch("https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T%dc.txt" % y, 25)
            if data and (b"\xe6\x97\xa5\xe6\x9c\x9f" in data or "\u65e5\u671f" in data.decode("utf-8", "ignore")):
                open(p, "wb").write(data)
        except Exception:
            pass
    if os.path.exists(p):
        raw = open(p, "rb").read()
        for enc in ("utf-8-sig", "big5hkscs", "utf-8"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
    return None

ROWM = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\S+)\s+(星期[一二三四五六日])\s*(\S*)")
MONTHS = {"正月":1,"一月":1,"二月":2,"三月":3,"四月":4,"五月":5,"六月":6,"七月":7,"八月":8,
          "九月":9,"十月":10,"十一月":11,"冬月":11,"十二月":12,"臘月":12,"腊月":12}
T2S = {"驚蟄":"惊蛰","穀雨":"谷雨","小滿":"小满","芒種":"芒种","處暑":"处暑","閏":"闰","鬥":"斗"}
def cn(s):
    for a, b in T2S.items():
        s = s.replace(a, b)
    return s

def lunarday(n):
    if n == 10: return "初十"
    if n == 20: return "二十"
    if n == 30: return "三十"
    if n < 10: return "初" + "一二三四五六七八九"[n - 1]
    if n < 20: return "十" + "一二三四五六七八九"[n - 11]
    return "廿" + "一二三四五六七八九"[n - 21]

def parse(y):
    txt = hko_text(y); rows = {}
    if not txt: return rows, None
    head = None
    m = re.search(r"(\d{4})\((\S{2}) - 肖(\S)\)", txt)
    if m: head = (m.group(2), m.group(3))
    mon = None; leap = False
    for line in txt.splitlines():
        mm = ROWM.match(line.rstrip())
        if not mm: continue
        yy, mo, dd, lf, wd, term = int(mm.group(1)), int(mm.group(2)), int(mm.group(3)), cn(mm.group(4)), mm.group(5), cn(mm.group(6)).strip()
        if lf.startswith("闰"):
            leap = True; mon = MONTHS.get(lf[1:], mon); day = 1
        elif lf in MONTHS:
            leap = False; mon = MONTHS[lf]; day = 1
        else:
            day = None
            for i in range(1, 31):
                if lunarday(i) == lf: day = i; break
        rows[datetime.date(yy, mo, dd)] = {"m": mon, "d": day, "leap": leap, "wd": wd, "term": term}
    return rows, head

rows, head = parse(today.year)
if not rows or today not in rows:
    r2, h2 = parse(today.year - 1)
    if r2 and today in r2: rows, head = r2, h2
r = rows.get(today)

STEM = "甲乙丙丁戊己庚辛壬癸"; BR = "子丑寅卯辰巳午未申酉戌亥"; ZODIAC = "鼠牛虎兔龙蛇马羊猴鸡狗猪"
def jdn(y, m, d):
    a = (14 - m) // 12; yy = y + 4800 - a; mm = m + 12 * a - 3
    return d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045
GZ = (jdn(today.year, today.month, today.day) + 49) % 60
ds, db = GZ % 10, GZ % 12
MNAME = {1:"正月",2:"二月",3:"三月",4:"四月",5:"五月",6:"六月",7:"七月",8:"八月",9:"九月",10:"十月",11:"冬月",12:"腊月"}
na = None
print("📅 农历黄历 · %s %s" % (today.isoformat(), WD[today.weekday()]))
if r and r["m"]:
    chunjie = None
    for dt in sorted(rows):
        if rows[dt]["m"] == 1 and rows[dt]["d"] == 1 and not rows[dt]["leap"]:
            chunjie = dt; break
    ly = today.year if (chunjie is None or today >= chunjie) else today.year - 1
    yg = (ly - 4) % 60; ystem, ybr = yg % 10, yg % 12
    XIAMAP = {"立春":2,"惊蛰":3,"清明":4,"立夏":5,"芒种":6,"小暑":7,"立秋":8,"白露":9,"寒露":10,"立冬":11,"大雪":0,"小寒":1}
    mb = 2
    for dt in sorted(rows):
        t = rows[dt]["term"]
        if t in XIAMAP and dt <= today: mb = XIAMAP[t]
    ZHOUMAP = {0:2,5:2,1:4,6:4,2:6,7:6,3:8,8:8,4:0,9:0}
    mg = (ZHOUMAP[ystem] + ((mb - 2) % 12)) % 10
    print("农历：%s%s年（%s年）%s%s%s" % (STEM[ystem], BR[ybr], ZODIAC[ybr], "闰" if r["leap"] else "",
          MNAME.get(r["m"], ""), lunarday(r["d"])))
    print("干支：%s%s年 · %s%s月 · %s%s日" % (STEM[ystem], BR[ybr], STEM[mg], BR[mb], STEM[ds], BR[db]))
    JC = ["建","除","满","平","定","执","破","危","成","收","开","闭"]
    ji = (db - mb + 12) % 12
    sha = "南" if db in (8,0,4) else ("北" if db in (2,6,10) else ("西" if db in (11,3,7) else "东"))
    print("建除：%s日 ｜ 日冲%s 煞%s" % (JC[ji], ZODIAC[(db + 6) % 12], sha))
    YI = {"建":"祭祀 祈福 出行 赴任 上梁","除":"祭祀 祈福 出行 除服 疗病 扫舍","满":"祭祀 祈福 嫁娶 开市 交易",
          "平":"祭祀 嫁娶 修整 涂泥 修造","定":"祭祀 祈福 嫁娶 开市 交易 安床","执":"祭祀 祈福 嫁娶 修造 捕捉",
          "破":"破屋 求医 治病","危":"祭祀 祈福 安床 修造","成":"嫁娶 开市 交易 出行 入学 祈福",
          "收":"纳财 收账 嫁娶 祭祀 进人口","开":"祭祀 祈福 开市 交易 出行 入学 嫁娶","闭":"祭祀 筑堤 埋穴 收藏"}
    JI = {"建":"动土 开仓 安葬 伐木","除":"开市 交易 安葬 动土","满":"服药 栽种 安葬 赴任",
          "平":"开渠 栽种 动土","定":"诉讼 出行 移徙","执":"开市 交易 移徙 出财",
          "破":"嫁娶 开市 动土 安葬 出行","危":"出行 登高 行船 赴任 移徙","成":"诉讼 争执",
          "收":"开市 动土 安葬 出行","开":"安葬 动土 放水","闭":"开市 出行 求医 开渠"}
    print("宜：%s" % YI[JC[ji]]); print("忌：%s" % JI[JC[ji]])
    NAYIN = ["海中金","炉中火","大林木","路旁土","剑锋金","山头火","涧下水","城头土","白蜡金","杨柳木",
             "泉中水","屋上土","霹雳火","松柏木","长流水","沙中金","山下火","平地木","壁上土","金箔金",
             "覆灯火","天河水","大驿土","钗钏金","桑柘木","大溪水","沙中土","天上火","石榴木","大海水"]
    print("日五行：%s" % NAYIN[GZ // 2])
    nxt = None
    for dt in sorted(rows):
        if dt > today and rows[dt]["term"]:
            nxt = (dt, rows[dt]["term"]); break
    if nxt:
        print("节气：距「%s」（%d月%d日）还有 %d 天" % (nxt[1], nxt[0].month, nxt[0].day, (nxt[0] - today).days))
else:
    print("农历：数据源暂不可用（缓存恢复中）")

# ---------------- 穿衣指南 ----------------
if tmax is not None:
    tm = (tmin + tmax) / 2.0
    if tm >= 28: base = "短袖、透气薄装，注意防晒补水"
    elif tm >= 24: base = "短袖或薄衬衫，随身一件薄外套"
    elif tm >= 20: base = "长袖衬衫/薄卫衣，外搭薄外套"
    elif tm >= 16: base = "薄毛衣或卫衣 + 夹克/风衣"
    elif tm >= 12: base = "毛衣 + 风衣/厚夹克"
    elif tm >= 8: base = "厚外套或薄羽绒，内搭毛衣"
    else: base = "羽绒服/厚外套，注意头手保暖"
    tips = []
    if tmax - tmin >= 8: tips.append("昼夜温差%d℃，早晚加衣" % (tmax - tmin))
    if rain is not None and rain >= 40: tips.append("降雨概率%d%%，带伞" % rain)
    if wind is not None and wind >= 30: tips.append("风力较大（%d km/h），注意防风" % wind)
    if uv is not None and str(uv).isdigit() and int(uv) >= 6: tips.append("紫外线较强，注意防晒")
    print("🧥 穿衣指南：%d~%d℃ → %s%s" % (tmin, tmax, base, ("；" + "；".join(tips)) if tips else ""))

# ---------------- 今日必知 ----------------
KNOW = []
if tmax is not None:
    if rain is not None and rain >= 40: KNOW.append("今天降雨概率%d%%，出门带伞" % rain)
    if tmax - tmin >= 8: KNOW.append("昼夜温差%d℃，早晚明显偏凉" % (tmax - tmin))
    if wind is not None and wind >= 30: KNOW.append("有大风（%d km/h）" % wind)
    if sr and ss: KNOW.append("日出%s、日落%s" % (sr, ss))
if r and rows:
    FEST = {(1,1):"春节",(1,15):"元宵节",(2,2):"龙抬头",(5,5):"端午节",(7,7):"七夕节",(7,15):"中元节",
            (8,15):"中秋节",(9,9):"重阳节",(12,8):"腊八节",(12,23):"小年",(12,29):"除夕",(12,30):"除夕"}
    up = []
    for dt in sorted(rows):
        if today < dt <= today + datetime.timedelta(days=30):
            rr = rows[dt]
            if rr["m"] and (rr["m"], rr["d"]) in FEST and not rr["leap"]:
                up.append((dt, FEST[(rr["m"], rr["d"])]))
            if rr["term"]: up.append((dt, rr["term"]))
    seen = set()
    for dt, nm in up:
        if nm in seen: continue
        seen.add(nm)
        KNOW.append("%s（%d月%d日）还有%d天" % (nm, dt.month, dt.day, (dt - today).days))
        if len(seen) >= 4: break
if KNOW:
    print("🌟 今日必知：" + "；".join(KNOW))
print()
PY

python3 - "$CFG" <<"PY"
import json, sys, re, urllib.request
cfg = json.load(open(sys.argv[1]))
import os, datetime
HIST = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "sent-history.json")
def norm(s): return re.sub(r"\s+", "", s)
def load_seen(days=5):
    try:
        d = json.load(open(HIST))
        cut = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
        return {norm(x.get("t","")) for x in d.get("titles", []) if x.get("d","") >= cut}
    except Exception:
        return set()
SEEN = load_seen()
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
def grab_rss(url, n=8):
    try:
        d = get(url)
        out = []
        for it in re.findall(r"<item>(.*?)</item>", d, re.S)[:n]:
            t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
            if t: out.append(t.group(1).strip()[:90])
        return out
    except Exception: return []
def grab_hn(url, n=8):
    try:
        d = json.loads(get(url))
        return [h.get("title","")[:90] for h in d.get("hits", [])[:n] if h.get("title")]
    except Exception: return []
for cat, urls in cfg.get("sources", {}).items():
    lines = []
    for u in urls:
        if u.startswith("HN:"):
            lines += grab_hn(u[3:])
        else:
            lines += grab_rss(u)
    uniq, seen = [], set()
    for t in lines:
        k = re.sub(r"\s+", "", t)
        if not k or k in seen or k in SEEN: continue
        seen.add(k); uniq.append(t)
    if uniq:
        print(f"【{cat}】")
        for t in uniq[:8]: print("-", t)
        print()
PY
#!/usr/bin/env python3
"""小红书笔记采集 v4：复用同一标签页导航 + DOM 抽取标题/正文/标签/作者。
用法: tools/xhs-harvest.py --urls FILE --out FILE [--limit N] [--tab tNN] [--profile chrome]
输出 jsonl: {url,note_id,ok,title,desc,tags,author,error}
"""
import argparse, json, random, re, subprocess, time

PROFILE = "chrome"

JS_STATE = (
 'var q=function(s){var e=document.querySelector(s);return e?e.innerText:""};'
 'var d=q("#detail-desc")||q(".note-content")||q(".desc")||q(".note-scroller .desc");'
 'var t=q("#detail-title")||q(".note-content .title")||q(".title");'
 'if(!d&&!t){return JSON.stringify({ok:0});}'
 'return JSON.stringify({ok:1,title:t,desc:d.slice(0,3000),'
 'tags:Array.from(document.querySelectorAll(".tag")).map(function(x){return x.innerText}).slice(0,20),'
 'author:q(".author-wrapper .name")||q(".username")});'
)
JS_NAV = 'location.href=%s; return "nav"'

def cli(args, timeout=75):
    try:
        p = subprocess.run(["openclaw", "browser", "--browser-profile", PROFILE] + args,
                           capture_output=True, text=True, timeout=timeout)
        return (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return "__TIMEOUT__"

def jval(o):
    o = o.strip()
    try:
        if o.startswith('"'):
            o = json.loads(o)
        return json.loads(o)
    except Exception:
        return None

def main():
    global PROFILE
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--profile", default="chrome")
    ap.add_argument("--tab", default="")
    a = ap.parse_args()
    PROFILE = a.profile
    urls = [l.strip() for l in open(a.urls) if l.strip()][: a.limit]
    tab = a.tab
    if not tab:
        m = re.search(r"tab:\s*(t\d+)", cli(["open", "https://www.xiaohongshu.com/explore"]))
        tab = m.group(1) if m else ""
    if not tab:
        print("ERR no tab", flush=True)
        return
    print("tab", tab, "urls", len(urls), flush=True)
    ok = fail = 0
    t0 = time.time()
    with open(a.out, "w", encoding="utf-8") as fo:
        for i, u in enumerate(urls, 1):
            rec = {"url": u, "ok": False}
            m = re.search(r"/explore/([0-9a-f]+)", u)
            rec["note_id"] = m.group(1) if m else ""
            cli(["evaluate", "--target-id", tab, "--fn", JS_NAV % json.dumps(u)])
            d = None
            for _ in range(2):
                time.sleep(random.uniform(4, 6))
                d = jval(cli(["evaluate", "--target-id", tab, "--fn", JS_STATE]))
                if d and d.get("ok"):
                    break
            if d and d.get("ok"):
                rec.update(ok=True, title=d.get("title"), desc=d.get("desc"),
                           tags=d.get("tags"), author=d.get("author"))
                ok += 1
                print("[%d/%d] OK %s %ds" % (i, len(urls), str(d.get("title"))[:26], time.time() - t0), flush=True)
            else:
                rec["error"] = "blocked_or_empty"
                fail += 1
                print("[%d/%d] FAIL %s" % (i, len(urls), u[-32:]), flush=True)
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fo.flush()
            time.sleep(random.uniform(2, 4))
    print("DONE ok=%d fail=%d %ds" % (ok, fail, time.time() - t0), flush=True)

if __name__ == "__main__":
    main()

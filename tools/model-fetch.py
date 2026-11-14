#!/usr/bin/env python3
"""model-fetch.py — 用常驻登录态从 MakerWorld 取模型文件（零 token）
依赖: tools/models-console.sh start（CDP 9334，profile /home/j/.openclaw/browser-models）
用法:
  model-fetch.py <模型URL> [--out DIR] [--dry-run]
输出: 下载文件落到 DIR（默认 /home/j/openclaw-workspaces/maker/data/models/<模型ID>/）
注意: 只取免费/已授权模型；需登录的页面必须先由主公完成一次登录（会话长期有效）
"""
import os, sys, re, json, subprocess, argparse, datetime

CDP = "http://127.0.0.1:9334"
NODE = "/usr/bin/node"
PW = "/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core"
DEFAULT_OUT = "/home/j/openclaw-workspaces/maker/data/models"

JS = r'''
const {chromium}=require(process.argv[2]);
(async()=>{
  const url=process.argv[3], outDir=process.argv[4], dry=process.argv[5]==="1";
  const fs=require("fs"), path=require("path");
  const b=await chromium.connectOverCDP("http://127.0.0.1:9334");
  const ctx=b.contexts()[0];
  const p=await ctx.newPage();
  await p.goto(url,{waitUntil:"domcontentloaded",timeout:60000});
  await p.waitForTimeout(4000);
  const title=await p.title();
  // 收集页面里所有可能的模型文件链接
  const links=await p.evaluate(()=>{
    const out=new Set();
    document.querySelectorAll("a[href]").forEach(a=>{
      const h=a.getAttribute("href")||"";
      if(/.(3mf|stl|zip|7z|rar|obj)(\?|$)/i.test(h)) out.add(h);
    });
    return [...out];
  });
  const info={title, url:p.url(), links:links.slice(0,20)};
  if(!dry && links.length){
    const dir=outDir; fs.mkdirSync(dir,{recursive:true});
    for(const href of links){
      const abs=new URL(href, p.url()).href;
      const r=await ctx.request.get(abs);
      if(!r.ok()){ console.log("GET_FAIL",abs,r.status()); continue; }
      const cd=r.headers()["content-disposition"]||"";
      let name=(cd.match(/filename\*?=["']?([^"';]+)/)||[])[1]||path.basename(abs.split("?")[0])||("model_"+Date.now());
      name=decodeURIComponent(name.replace(/["']/g,""));
      const buf=await r.body();
      fs.writeFileSync(path.join(dir,name),buf);
      console.log("SAVED",path.join(dir,name),buf.length);
    }
  }
  console.log("INFO",JSON.stringify(info));
  await p.close(); await b.close();
})().catch(e=>{console.log("ERR",e.message);process.exit(1)});
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--out", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    mid = ""
    m = re.search(r"/models/(\d+)", a.url)
    if m:
        mid = m.group(1)
    out = a.out or (os.path.join(DEFAULT_OUT, mid) if mid else DEFAULT_OUT)
    js_path = "/tmp/model-fetch-%d.js" % os.getpid()
    with open(js_path, "w") as f:
        f.write(JS)
    cmd = [NODE, js_path, PW, a.url, out, "1" if a.dry_run else "0"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    print(r.stdout.strip()[-4000:])
    if r.returncode != 0:
        print("STDERR", r.stderr.strip()[-500:])
        return r.returncode
    if not a.dry_run:
        files = os.listdir(out) if os.path.isdir(out) else []
        print("[落盘] %s 共 %d 个文件: %s" % (out, len(files), ", ".join(files[:8])))
    return 0


if __name__ == "__main__":
    sys.exit(main())

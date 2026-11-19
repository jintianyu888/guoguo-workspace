#!/usr/bin/env python3
# 果果助手面板 v6 —— 本地 Web 面板（2026-10-29）
import json, os, subprocess, sys, threading, time, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WS = "/home/j/.openclaw/workspace"
CC = os.path.join(WS, "tools", "console-cmd.sh")
SAFE = {"status","selfcheck","fix","services","logs","diag","backups","quota","brief","clean-dry","cfgroll","oc-status","oc-health","oc-logs","oc-channels","oc-usage-table","oc-today"}
CONFIRM = {"restart","upgrade","backup-now","rescue"}
LOCK = threading.Lock()

PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>果果助手</title><style>
:root{--bg:#0d1117;--card:#161b22;--line:#21262d;--txt:#c9d1d9;--dim:#8b949e;--acc:#3fb950;--warn:#d29922;--bad:#f85149;--blue:#58a6ff}
*{box-sizing:border-box}body{margin:0;font:15px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--txt)}
header{padding:18px 24px;background:linear-gradient(120deg,#1f6feb22,#3fb95022);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:12px}
header h1{font-size:18px;margin:0;font-weight:600}header .dot{width:10px;height:10px;border-radius:50%;background:var(--acc);box-shadow:0 0 12px var(--acc)}
header .meta{margin-left:auto;font-size:13px;color:var(--dim)}
main{display:grid;grid-template-columns:180px 1fr;gap:18px;padding:18px 24px}
nav button{display:block;width:100%;margin-bottom:8px;padding:11px 14px;text-align:left;background:var(--card);color:var(--txt);border:1px solid var(--line);border-radius:10px;font:inherit;cursor:pointer;transition:.15s}
nav button:hover{border-color:var(--blue);transform:translateX(2px)}
nav button.danger{border-color:#f8514944;color:#ff9b95}
pre{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;min-height:60vh;overflow:auto;font:13px/1.55 "Cascadia Code",Consolas,monospace;white-space:pre-wrap;margin:0}
.spin{color:var(--dim);font-style:italic}
</style></head><body>
<header><span class="dot"></span><h1>果果助手</h1><span class="meta" id="meta">加载中…</span></header>
<main><nav id="nav"></nav><pre id="out">选择左侧功能</pre></main>
<script>
const BTNS=[["状态总览","status"],["一键自检","selfcheck"],["自动修复","fix"],["服务清单","services"],["备份状态","backups"],["额度与模型","quota"],["今日简报","brief"],["诊断包","diag"],["查看日志","logs"],["清理预演","clean-dry"],["OC·网关状态","oc-status"],["OC·健康","oc-health"],["OC·日志","oc-logs"],["OC·渠道","oc-channels"],["OC·会话用量","oc-usage-table"],["OC·今日token","oc-today"],["重启网关","restart",1],["立即备份","backup-now",1]];
const nav=document.getElementById('nav'),out=document.getElementById('out');
BTNS.forEach(([label,cmd,danger])=>{const b=document.createElement('button');b.textContent=label;if(danger)b.className='danger';b.onclick=()=>run(cmd,label,danger);nav.appendChild(b);});
async function run(cmd,label,danger){
  if(danger&&!confirm(label+'：确定执行？'))return;
  out.textContent='⟳ '+label+' 执行中…';out.className='spin';
  try{const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd})});
    const j=await r.json();out.className='';out.textContent=j.output||'(无输出)';out.scrollTop=0;}catch(e){out.className='';out.textContent='请求失败: '+e;}
}
async function meta(){try{const r=await fetch('/api/meta');const j=await r.json();
  document.getElementById('meta').textContent=j.host+' · '+j.time+(j.mem?' · 内存 '+j.mem:'');
}catch(e){}}
meta();setInterval(meta,30000);
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if self.path == "/api/meta":
            mem = ""
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal"):
                            mem = "%.0fG" % (int(line.split()[1]) / 1048576)
                            break
            except Exception:
                pass
            return self._send(200, json.dumps({"host": os.uname().nodename,
                "time": time.strftime("%F %H:%M"), "mem": mem}, ensure_ascii=False))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path != "/api/run":
            return self._send(404, json.dumps({"error": "not found"}))
        n = int(self.headers.get("Content-Length") or 0)
        try:
            cmd = json.loads(self.rfile.read(n) or b"{}").get("cmd", "")
        except Exception:
            return self._send(400, json.dumps({"error": "bad json"}))
        if cmd not in SAFE and cmd not in CONFIRM:
            return self._send(403, json.dumps({"output": "不允许的命令: %s" % cmd}, ensure_ascii=False))
        if not LOCK.acquire(timeout=180):
            return self._send(200, json.dumps({"output": "有任务在跑，稍后再试"}, ensure_ascii=False))
        try:
            p = subprocess.run(["bash", CC, cmd], capture_output=True, text=True, timeout=300, cwd=WS)
            body = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr.strip() else "")
            body += "\n[rc=%d]" % p.returncode
        except subprocess.TimeoutExpired:
            body = "超时（>300s），已中断"
        except Exception as e:
            body = "执行失败: %s" % e
        finally:
            LOCK.release()
        return self._send(200, json.dumps({"output": body}, ensure_ascii=False))

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18811
    host = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0"
    ThreadingHTTPServer((host, port), H).serve_forever()

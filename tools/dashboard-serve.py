#!/usr/bin/env python3
"""dashboard-serve.py — 极简看板服务：每次请求现场重生成 HTML（无需 cron）
监听 127.0.0.1:18810（仅本机；对外用 portal 或 Tailscale 暴露）
用法：python3 tools/dashboard-serve.py [port]
"""
import os,sys,subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

WS='/home/j/.openclaw/workspace'
GEN=os.path.join(WS,'tools/dashboard-gen.py')
HTML=os.path.join(WS,'state/portal/simple-dashboard.html')
PORT=int(sys.argv[1]) if len(sys.argv)>1 else 18810

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split('?')[0] not in ('/','/index.html'):
            self.send_response(404); self.end_headers(); return
        try:
            subprocess.run([sys.executable,GEN,'--quiet'],cwd=WS,timeout=20,check=False)
        except Exception:
            pass
        try:
            body=open(HTML,'rb').read()
        except Exception as ex:
            body=('<h1>看板暂不可用</h1><pre>%s</pre>'%ex).encode()
        self.send_response(200)
        self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self,*a):
        pass

if __name__=='__main__':
    srv=ThreadingHTTPServer(('127.0.0.1',PORT),H)
    print('dashboard on http://127.0.0.1:%d/'%PORT,flush=True)
    srv.serve_forever()

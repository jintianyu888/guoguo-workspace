#!/usr/bin/env python3
# fileshare.py — 带 token 的静态文件服务（支持断点续传/大文件，无 30M 限制）
import http.server,socketserver,os,sys,functools,urllib.parse,re
root=os.path.abspath(sys.argv[1]); port=int(sys.argv[2]); token=os.environ.get('FS_TOKEN','')
class H(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p=urllib.parse.urlparse(path).path
        if token:
            pre='/'+token
            if not p.startswith(pre): return os.path.join(root,'__denied__')
            p=p[len(pre):] or '/'
        return super().translate_path(p)
    def do_GET(self):
        rng=self.headers.get('Range')
        path=urllib.parse.urlparse(self.path).path
        if token and not path.startswith('/'+token):
            self.send_error(403); return
        if rng and token:
            name=path[len('/'+token):]
            fp=self._path_for(name.lstrip('/'))
            if os.path.isfile(fp):
                size=os.path.getsize(fp)
                m=re.match(r'bytes=(\d*)-(\d*)', rng) or None
                if m:
                    start=int(m.group(1) or 0); end=int(m.group(2) or size-1)
                    if end>=size: end=size-1
                    ln=max(0,end-start+1)
                    self.send_response(206)
                    ctype='video/mp4' if fp.endswith('.mp4') else ('audio/wav' if fp.endswith('.wav') else 'application/octet-stream')
                    self.send_header('Content-Type',ctype)
                    self.send_header('Accept-Ranges','bytes')
                    self.send_header('Content-Range','bytes %d-%d/%d'%(start,end,size))
                    self.send_header('Content-Length',str(ln))
                    self.end_headers()
                    with open(fp,'rb') as f:
                        f.seek(start); self.wfile.write(f.read(ln))
                    return
        return super().do_GET()
    def list_directory(self, path):
        try: items=sorted(os.listdir(path))
        except OSError: self.send_error(404); return None
        out=['<meta charset=utf-8><h3>files</h3><ul>']
        for n in items:
            fp=os.path.join(path,n); sz=os.path.getsize(fp) if os.path.isfile(fp) else 0
            out.append(f'<li><a href="{urllib.parse.quote(n)}">{n}</a> {sz/1048576:.1f} MB</li>')
        out.append('</ul><p>上传用 PUT：curl -T 文件 <本页地址>文件名</p>')
        data=''.join(out).encode()
        self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers()
        import io; return io.BytesIO(data)
    def _path_for(self, name):
        return os.path.join(root, os.path.basename(urllib.parse.unquote(name)))
    def do_PUT(self):
        p=urllib.parse.urlparse(self.path).path
        if token and not p.startswith('/'+token): self.send_error(403); return
        name=p[len('/'+token):] if token else p
        dst=self._path_for(name.lstrip('/'))
        n=int(self.headers.get('Content-Length','0'))
        got=0
        with open(dst,'wb') as o:
            while got<n:
                b=self.rfile.read(min(1048576, n-got))
                if not b: break
                o.write(b); got+=len(b)
        self.send_response(201); self.send_header('Content-Length','0'); self.end_headers()
        print('PUT', os.path.basename(dst), got, flush=True)
    def log_message(self,*a): pass
socketserver.TCPServer.allow_reuse_address=True
with socketserver.ThreadingTCPServer(('0.0.0.0',port),H) as s:
    print('serving',root,port,flush=True); s.serve_forever()
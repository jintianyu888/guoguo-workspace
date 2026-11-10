#!/usr/bin/env python3
"""ollama-proxy.py — 本机 127.0.0.1:11434 转发到 Windows 侧 ollama（方案C，2026-10-26）

为什么：Windows 的 IPv4 会变（DHCP），写死 192.168.1.x 后一旦换 IP，OpenClaw 的 ollama provider 全挂。
做法：代理自己发现上游——优先 ipconfig.exe 解析 192.168.*，探活 /api/tags；失败换下一个候选；
      运行中上游失败时自动重新发现一次再重试。纯标准库，无新依赖。

用法: python3 tools/ollama-proxy.py [--port 11434] [--upstream http://1.2.3.4:11434] [--once]
"""
import argparse, http.client, json, os, re, socket, socketserver, subprocess, sys, time
from http.server import BaseHTTPRequestHandler

UTC = "/mnt/c/Windows/System32/ipconfig.exe"
CAND_FILE = "/home/j/.openclaw/workspace/state/work/ollama-upstream.txt"
LOG = "/home/j/.openclaw/workspace/state/work/ollama-proxy.log"
UP_PORT = 11434
HOP_HEADERS = {"connection","keep-alive","proxy-authenticate","proxy-authorization",
               "te","trailers","transfer-encoding","upgrade","host","content-length"}
RESP_HOP = HOP_HEADERS - {"host", "content-length"}

def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass

def _save_cache(ip):
    """原子写上游缓存，避免并发读到半截内容"""
    try:
        tmp = CAND_FILE + ".tmp"
        with open(tmp, "w") as f:
            f.write(ip + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, CAND_FILE)
    except Exception:
        pass

def probe(host, timeout=2.0, need_model="", port=None):
    """GET /api/tags 200（且含我们的模型）才算真上游——防止误连别人家的 ollama"""
    try:
        c = http.client.HTTPConnection(host, port or UP_PORT, timeout=timeout)
        c.request("GET", "/api/tags")
        r = c.getresponse()
        body = r.read(200000) if r.status == 200 else b""
        c.close()
        if r.status != 200:
            return False
        if not need_model:
            return True
        try:
            tags = [m.get("name", "") for m in json.loads(body.decode("utf-8", "ignore")).get("models", [])]
        except Exception:
            return False
        return any(need_model in t for t in tags)
    except Exception:
        return False

def windows_ips():
    ips = []
    try:
        out = subprocess.run([UTC], capture_output=True, timeout=10).stdout.decode("gbk", "ignore")
    except Exception:
        out = ""
    for m in re.finditer(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", out):
        ip = m.group(1)
        if ip.startswith("192.168.") and ip not in ips:
            ips.append(ip)
    # 兜底：WSL 默认网关（Windows 侧 vEthernet）
    try:
        gw = subprocess.run(["ip","route","show","default"], capture_output=True, timeout=5).stdout.decode().split()[2]
        if gw not in ips:
            ips.append(gw)
    except Exception:
        pass
    return ips

def config_ips():
    """现役 openclaw.json 里 ollama.baseUrl 的 IP，作为稳定候选"""
    import re as _re
    out = []
    try:
        txt = open("/home/j/.openclaw/openclaw.json", encoding="utf-8").read()
        for m in _re.finditer(r'"baseUrl"\s*:\s*"http://(\d{1,3}(?:\.\d{1,3}){3}):11434"', txt):
            if m.group(1) not in out:
                out.append(m.group(1))
    except Exception:
        pass
    return out

def sweep(subnets=None, limit=254):
    """最后手段：/24 并发探活（只认带我们模型的 ollama；支持多网段）"""
    import concurrent.futures as _f
    if subnets is None:
        subnets = ["192.168.1"]
        try:
            sf = os.path.join(os.path.dirname(CAND_FILE), "ollama-subnets.txt")
            if os.path.exists(sf):
                subnets = [x.strip() for x in open(sf).read().split() if x.strip()] or subnets
        except Exception:
            pass
    ips = ["%s.%d" % (s, i) for s in subnets for i in range(1, limit + 1)]
    hits = []
    def one(ip):
        return ip if probe(ip, timeout=0.8, need_model="qwen3") else None
    try:
        with _f.ThreadPoolExecutor(max_workers=128) as ex:
            for r in ex.map(one, ips):
                if r:
                    hits.append(r)
    except Exception:
        pass
    return hits

def discover():
    cached = ""
    try:
        cached = open(CAND_FILE).read().strip()
    except Exception:
        pass
    cands = ([cached] if cached else []) + config_ips() + windows_ips()
    selfips = {"127.0.0.1", "localhost", "0.0.0.0"}
    try:
        selfips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except Exception:
        pass
    seen = set()
    for ip in cands:
        if ip in seen or ip in selfips or ip.startswith("127.") or ip in ("::1", "0.0.0.0"):
            continue
        seen.add(ip)
        if probe(ip, need_model="qwen3"):
            _save_cache(ip)
            log("upstream=%s OK" % ip)
            return ip
    # 候选都失败 → /24 兜底扫一遍
    hits = sweep()
    if hits:
        ip = hits[0]
        _save_cache(ip)
        log("upstream=%s OK (sweep, hits=%s)" % (ip, ",".join(hits)))
        return ip
    log("discover FAILED cands=%s" % ",".join(seen))
    # 2026-11-07（#174）：第二上游——B 机休眠/关机时退到 A 机本机 ollama(127.0.0.1:11435)
    try:
        if probe("127.0.0.1", timeout=2.0, port=LOCAL_PORT):
            log("upstream -> local fallback 127.0.0.1:%d" % LOCAL_PORT)
            return {"host": "127.0.0.1", "port": LOCAL_PORT, "local": True}
    except Exception:
        pass
    return None

LOCAL_PORT = int(os.environ.get("OLLAMA_LOCAL_PORT", "11435"))
UP = {"host": None}

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ollama-proxy/1"

    def log_message(self, fmt, *a):
        pass

    def _upstream(self, refresh=False):
        up = UP["host"]
        # 2026-11-07 21:20：一旦降级到本机 fallback 就再不回头（B 机恢复后仍打到本地，
        # 表现为 model not found）。降级状态下每 60s 重试一次远程发现。
        if (not refresh and up and isinstance(up, dict) and up.get("local")
                and time.time() - UP.get("ts", 0) > 60):
            refresh = True
        if refresh or not UP["host"]:
            UP["host"] = discover()
            UP["ts"] = time.time()
        return UP["host"]

    def _do(self, method):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_HEADERS}
        last = None
        for attempt in (0, 1):
            host = self._upstream(refresh=(attempt == 1))
            if not host:
                break
            try:
                _hp = host.get("port", UP_PORT) if isinstance(host, dict) else UP_PORT
                _hh = host.get("host") if isinstance(host, dict) else host
                conn = http.client.HTTPConnection(_hh, _hp, timeout=600)
                conn.request(method, self.path, body=body, headers=headers)
                r = conn.getresponse()
                _chunked = bool(r.getheader("Transfer-Encoding"))
                self.send_response(r.status, r.reason)
                for k, v in r.getheaders():
                    if k.lower() in RESP_HOP or k.lower() == "content-length":
                        continue
                    self.send_header(k, v)
                if _chunked:
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    while True:
                        chunk = r.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(("%X\r\n" % len(chunk)).encode() + chunk + b"\r\n")
                        self.wfile.flush()
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                else:
                    data = r.read()
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    if method != "HEAD" and data:
                        self.wfile.write(data)
                        self.wfile.flush()
                conn.close()
                return
            except Exception as e:
                last = e
                log("upstream %s %s failed: %s" % (host, self.path, e))
        self.send_response(502)
        self.send_header("Content-Type", "application/json")
        payload = json.dumps({"error": "ollama upstream unreachable", "detail": str(last)}).encode()
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path.rstrip("/") == "":
            pass
        self._do("GET")

    def do_POST(self):
        self._do("POST")

    def do_DELETE(self):
        self._do("DELETE")

    def do_HEAD(self):
        self._do("HEAD")

class S(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=11434)
    ap.add_argument("--upstream", default="")
    ap.add_argument("--once", action="store_true", help="只做一次发现并打印结果")
    a = ap.parse_args()
    if a.upstream:
        UP["host"] = a.upstream.split("//")[-1].split(":")[0]
    if a.once:
        h = UP["host"] or discover()
        print(h or "NONE")
        return 0 if h else 1
    srv = S(("127.0.0.1", a.port), H)
    log("listen 127.0.0.1:%d" % a.port)
    print("ollama-proxy listening on 127.0.0.1:%d (upstream auto)" % a.port)
    srv.serve_forever()

if __name__ == "__main__":
    sys.exit(main() or 0)

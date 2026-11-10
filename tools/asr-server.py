#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asr-server.py —— 常驻语音转写服务（2026-11-07，#206）

模型只加载一次，消除每次 3-5 秒冷启动。只监听 127.0.0.1（本机调用）。
POST /asr?path=/abs/file.ogg&lang=zh   → {"text": "...", "ms": 123}
POST /asr  (body=音频字节, 头 X-Lang: zh) → 同上
GET  /health → {"ok":true,"model":"small","loaded":true}
"""
import json, os, sys, time, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_NAME = os.environ.get('ASR_MODEL', 'small')
PORT = int(os.environ.get('ASR_PORT', '18940'))
_model = None
_lock = threading.Lock()


def model():
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel
            p = os.path.join(WS, 'tools', 'models', 'faster-whisper-' + MODEL_NAME)
            src = p if os.path.isdir(p) else MODEL_NAME
            if os.environ.get('ASR_FORCE_CPU', '0') == '1':
                _model = WhisperModel(src, device='cpu', compute_type='int8', cpu_threads=4)
            else:
                try:
                    _model = WhisperModel(src, device='cuda', compute_type='float16', cpu_threads=4)
                except Exception:
                    _model = WhisperModel(src, device='cpu', compute_type='int8', cpu_threads=4)
    return _model


def transcribe(path, lang='zh'):
    t0 = time.time()
    segs, info = model().transcribe(path, language=lang or None, vad_filter=True, beam_size=1)
    text = ''.join(s.text for s in segs).strip()
    return text, int((time.time() - t0) * 1000)


class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if urlparse(self.path).path == '/health':
            return self._json({'ok': True, 'model': MODEL_NAME, 'loaded': _model is not None})
        return self._json({'error': 'not found'}, 404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != '/asr':
            return self._json({'error': 'not found'}, 404)
        q = parse_qs(u.query)
        lang = (q.get('lang', [None])[0]) or self.headers.get('X-Lang') or 'zh'
        path = q.get('path', [None])[0]
        tmp = None
        try:
            if not path:
                n = int(self.headers.get('Content-Length') or 0)
                data = self.rfile.read(n) if n else b''
                if not data:
                    return self._json({'error': 'no audio'}, 400)
                fd, tmp = tempfile.mkstemp(suffix='.ogg', dir='/tmp')
                with os.fdopen(fd, 'wb') as f:
                    f.write(data)
                path = tmp
            if not os.path.exists(path):
                return self._json({'error': 'file not found', 'path': path}, 404)
            text, ms = transcribe(path, lang)
            return self._json({'text': text, 'ms': ms, 'model': MODEL_NAME})
        except Exception as e:
            return self._json({'error': str(e)[:300]}, 500)
        finally:
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass


if __name__ == '__main__':
    if '--preload' in sys.argv:
        model()
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    srv.serve_forever()

#!/usr/bin/env node
// tls-proxy.js — OpenClaw 网关的 TLS 终结代理（2026-11-12）
// 为什么需要：node host 走非回环地址连网关要求 secure 上下文；
// 网关本身不开 TLS（开了会打碎本机 HTTP 客户端、面板、cron CLI）。
// 所以在本机 9443 终结 TLS，明文转 127.0.0.1:18789。
// 安全：证书自签名 + 客户端固定指纹；网关自身的 token/配对鉴权仍在最外层之后。
const tls = require('node:tls');
const net = require('node:net');
const fs = require('node:fs');

const LISTEN_PORT = Number(process.env.OC_TLS_PORT || 9443);
const TARGET_PORT = Number(process.env.OC_TLS_TARGET || 18789);
const CRED_DIR = process.env.OC_TLS_DIR || '/home/j/.openclaw/tls';

const opts = {
  key: fs.readFileSync(CRED_DIR + '/gw.key'),
  cert: fs.readFileSync(CRED_DIR + '/gw.crt'),
  minVersion: 'TLSv1.2',
};

function log(msg) {
  console.log(new Date().toISOString() + ' ' + msg);
}

const server = tls.createServer(opts, (sock) => {
  const peer = sock.remoteAddress + ':' + sock.remotePort;
  log('tls in ' + peer);
  const upstream = net.connect(TARGET_PORT, '127.0.0.1');
  sock.on('error', (e) => { log('client err ' + e.message); });
  upstream.on('error', (e) => { log('upstream err ' + e.message); sock.destroy(); });
  sock.pipe(upstream);
  upstream.pipe(sock);
  sock.on('close', () => upstream.destroy());
  upstream.on('close', () => sock.destroy());
});

server.on('tlsClientError', (e) => log('handshake fail ' + e.message));
server.listen(LISTEN_PORT, '0.0.0.0', () => log('listening ' + LISTEN_PORT + ' -> 127.0.0.1:' + TARGET_PORT));

process.on('SIGTERM', () => { log('terminating'); server.close(() => process.exit(0)); });

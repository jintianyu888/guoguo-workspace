#!/usr/bin/env node
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const ERR_REPORT = require('./lib/error-report');
const { execFile, spawn } = require('child_process');

const OPS_JOBS = new Map();
const OPS_LIVE_HTML = String.raw`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>任务进度</title><style>
body{margin:0;background:#0b0f14;color:#d7e2ee;font:14px/1.55 Consolas,Menlo,monospace}
#h{padding:10px 14px;background:#111823;border-bottom:1px solid #1e2a38;position:sticky;top:0}
#t{font-size:15px;color:#8fd3ff}#s{color:#7c8b9c;font-size:12px;margin-top:3px}
#o{margin:0;padding:12px 14px;white-space:pre-wrap;word-break:break-all}
#f{padding:8px 14px;border-top:1px solid #1e2a38;color:#9fb3c8;font-size:12px}
.ok{color:#5ee38a}.bad{color:#ff7b7b}</style></head><body>
<div id="h"><div id="t">等待任务…</div><div id="s"></div></div>
<pre id="o"></pre><div id="f">实时输出（每 0.6 秒刷新）</div>
<script>
var job = new URLSearchParams(location.search).get("job") || "";
var off = 0, timer = null, el = document.getElementById("o");
function esc(s){return s;}
function tick(){
  fetch("/api/ops/log?job=" + encodeURIComponent(job) + "&off=" + off, {cache:"no-store"})
    .then(function(r){return r.json();})
    .then(function(j){
      if(!j || !j.ok){ document.getElementById("s").textContent = "任务不存在或已结束"; return; }
      document.getElementById("t").textContent = j.label + " · " + j.cmd;
      document.getElementById("s").textContent = "运行 " + j.elapsed + " 秒" + (j.done ? "" : " · 进行中…");
      if(j.chunk){ off = j.next; el.textContent += j.chunk; window.scrollTo(0, document.body.scrollHeight); }
      if(j.done){
        var f = document.getElementById("f");
        f.className = j.code === 0 ? "ok" : "bad";
        f.textContent = (j.code === 0 ? "✓ 完成" : "✗ 失败") + "（rc=" + j.code + "，耗时 " + j.elapsed + " 秒）— 本窗口可关闭";
        clearInterval(timer);
      }
    })
    .catch(function(){ document.getElementById("s").textContent = "连接中断，重试中…"; });
}
tick(); timer = setInterval(tick, 600);
</script></body></html>`;


const PORT = Number(process.env.INFOWIN_PORT || 8899);
const HOST = process.env.INFOWIN_HOST || '0.0.0.0';
const CLI = process.env.OPENCLAW_BIN || 'openclaw';
const PUBLIC = path.join(__dirname, 'public');
const BAL_SH = '/home/j/.openclaw/workspace/tools/ds-balance.sh';
const USAGE_DIR = '/home/j/.openclaw/workspace/state/usage-meter';
const PRICING_JSON = process.env.HOME + '/.openclaw/workspace/state/model-econ/pricing-windows.json';
const BAL_JSON = '/home/j/.openclaw/workspace/state/model-econ/balances.json';
const QH_JSON = '/home/j/.openclaw/workspace/state/model-econ/quota-history.jsonl';
const QUOTAS = '/home/j/.openclaw/workspace/state/model-econ/quotas.json';

const LOGS = [];
let LOG_TAIL_READY = false;
setTimeout(function(){ LOG_TAIL_READY = true; }, 8000);
let LOG_SEQ = 0, LOG_PROC = null, LOG_ALIVE = false, LOG_RESTARTS = 0;

function stripAnsi(x) { return x.replace(/\x1b\[[0-9;]*[A-Za-z]/g, ''); }

function startLogTail() {
  if (LOG_PROC) return;
  let p;
  try {
    p = spawn(CLI, ['logs', '--follow', '--limit', '60', '--interval', '1500'], { env: process.env });
  } catch (e) { ERR.logs = String(e.message || e); return; }
  LOG_PROC = p; LOG_ALIVE = true;
  let buf = '';
  const onData = (d) => {
    buf += d.toString('utf8');
    let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = stripAnsi(buf.slice(0, i)).replace(/\r$/, '');
      buf = buf.slice(i + 1);
      if (line.trim()) {
        LOGS.push({ n: ++LOG_SEQ, ts: Date.now(), s: line.slice(0, 700) });
        if (LOGS.length > 500) LOGS.shift();
      }
      if (line.trim() && LOG_TAIL_READY) ERR_REPORT.note(line);
    }
    if (buf.length > 20000) buf = buf.slice(-4000);
  };
  p.stdout.on('data', onData);
  p.stderr.on('data', onData);
  const done = () => { LOG_ALIVE = false; LOG_PROC = null; LOG_RESTARTS++; setTimeout(startLogTail, 3000); };
  p.on('close', done);
  p.on('error', (e) => { ERR.logs = String(e.message || e); done(); });
}

const CITIES = [
  { name: '大连', lat: 38.914, lon: 121.615 },
  { name: '肇东', lat: 46.069, lon: 125.992 },
  { name: '重庆', lat: 29.563, lon: 106.552 },
  { name: '南京', lat: 32.060, lon: 118.797 },
  { name: '比什凯克', lat: 42.875, lon: 74.570 }
];
const WMO = { 0:'晴',1:'晴间云',2:'多云',3:'阴',45:'雾',48:'雾凇',51:'毛毛雨',53:'毛毛雨',55:'毛毛雨',
  56:'冻雨',57:'冻雨',61:'小雨',63:'中雨',65:'大雨',66:'冻雨',67:'冻雨',71:'小雪',73:'中雪',75:'大雪',
  77:'米雪',80:'阵雨',81:'阵雨',82:'强阵雨',85:'阵雪',86:'阵雪',95:'雷阵雨',96:'雷雨冰雹',99:'雷雨冰雹' };
let WEATHER = null, WEATHER_AT = 0, WEATHER_ERR = null;
let DALIAN_DAILY = [];

const STOCK_CODES = [
  { code: 'sh000001', label: '上证' },
  { code: 'sz399001', label: '深成' },
  { code: 'sz399006', label: '创业板' },
  { code: 'sh000300', label: '沪深300' },
  { code: 'hkHSI', label: '恒生' },
  { code: 'usDJI', label: '道琼斯' },
  { code: 'usIXIC', label: '纳指' },
  { code: 'usINX', label: '标普500' }
];
let STOCKS = null, STOCKS_AT = 0, STOCKS_ERR = null;

let FX = null, FX_AT = 0, FX_ERR = null;

async function refreshFx(maxAgeMs = 60000) {
  if (Date.now() - FX_AT < maxAgeMs) return;
  if (inflight.fx) return inflight.fx;
  inflight.fx = (async () => {
    try {
      const res = await fetch('https://hq.sinajs.cn/list=fx_susdcny,fx_seurcny,fx_sjpycny,hf_XAU', {
        signal: AbortSignal.timeout(10000),
        headers: { referer: 'https://finance.sina.com.cn' }
      });
      const txt = new TextDecoder('gbk').decode(Buffer.from(await res.arrayBuffer()));
      const grab = (k) => { const m = txt.match(new RegExp('hq_str_' + k + '="([^"]*)"')); return m ? m[1].split(',') : null; };
      const out = [];
      const usd = grab('fx_susdcny'), eur = grab('fx_seurcny'), jpy = grab('fx_sjpycny'), xau = grab('hf_XAU');
      const push = (label, last, pct, chg, unit, dec) => {
        const v = Number(last);
        if (!isFinite(v) || v === 0) return;
        out.push({ label, value: v.toFixed(dec), pct: (pct == null || !isFinite(Number(pct))) ? null : Number(pct), chg: (chg == null || !isFinite(Number(chg))) ? null : Number(chg), unit });
      };
      if (usd) push('美元', usd[8], usd[10], usd[11], 'CNY', 4);
      if (eur) push('欧元', eur[8], eur[10], eur[11], 'CNY', 4);
      if (jpy) { const lj = Number(jpy[8]) * 100; push('日元100', lj, jpy[10], Number(jpy[11]) * 100, 'CNY', 4); }
      if (xau) { const cur = Number(xau[0]); const prev = Number(xau[7]) || Number(xau[1]); const p = prev ? (cur - prev) / prev * 100 : null; push('黄金', cur, p, prev ? cur - prev : null, 'USD/oz', 2); }
      if (!out.length) throw new Error('empty fx');
      FX = out; FX_AT = Date.now(); FX_ERR = null;
    } catch (e) {
      FX_ERR = String(e.message || e).slice(0, 100);
      FX_AT = Date.now() - maxAgeMs + 30000;
    }
    inflight.fx = null;
  })();
  return inflight.fx;
}

async function refreshStocks(maxAgeMs = 60000) {
  if (Date.now() - STOCKS_AT < maxAgeMs) return;
  if (inflight.stocks) return inflight.stocks;
  inflight.stocks = (async () => {
    try {
      const url = 'https://qt.gtimg.cn/q=' + STOCK_CODES.map(x => x.code).join(',');
      const res = await fetch(url, { signal: AbortSignal.timeout(10000), headers: { referer: 'https://finance.qq.com/' } });
      const txt = new TextDecoder('gbk').decode(Buffer.from(await res.arrayBuffer()));
      const out = [];
      for (const line of txt.split(';')) {
        const m = line.match(/v_([A-Za-z0-9_]+)="(.*)"/);
        if (!m) continue;
        const meta = STOCK_CODES.find(x => x.code === m[1]);
        if (!meta) continue;
        const f = m[2].split('~');
        out.push({
          code: m[1], label: meta.label, name: f[1] || meta.label,
          price: Number(f[3]) || null, chg: Number(f[31]) || 0, pct: Number(f[32]) || 0,
          time: f[30] || '', foreign: !/^(sh|sz)/.test(m[1])
        });
      }
      if (!out.length) throw new Error('empty response');
      STOCKS = out; STOCKS_AT = Date.now(); STOCKS_ERR = null;
    } catch (e) {
      STOCKS_ERR = String(e.message || e).slice(0, 100);
      STOCKS_AT = Date.now() - maxAgeMs + 30000;
    }
    inflight.stocks = null;
  })();
  return inflight.stocks;
}

async function refreshWeather(maxAgeMs = 600000) {
  if (Date.now() - WEATHER_AT < maxAgeMs) return;
  if (inflight.weather) return inflight.weather;
  inflight.weather = (async () => {
    try {
      const lats = CITIES.map(c => c.lat).join(',');
      const lons = CITIES.map(c => c.lon).join(',');
      const url = 'https://api.open-meteo.com/v1/forecast?latitude=' + lats + '&longitude=' + lons +
        '&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m,precipitation,cloud_cover,pressure_msl,wind_direction_10m,wind_gusts_10m,is_day' +
        '&hourly=visibility,dew_point_2m&forecast_hours=1' +
        '&daily=temperature_2m_max,temperature_2m_min,weather_code,sunrise,sunset,uv_index_max,precipitation_probability_max&timezone=Asia%2FShanghai&forecast_days=10';
      const r = await fetch(url);
      const data = await r.json();
      const arr = Array.isArray(data) ? data : [data];
      WEATHER = CITIES.map((c, idx) => {
        const d = arr[idx] || arr[0] || {};
        const cur = d.current || {};
        const dly = d.daily || {};
        return {
          name: c.name,
          temp: cur.temperature_2m != null ? Math.round(cur.temperature_2m) : null,
          apparent: cur.apparent_temperature != null ? Math.round(cur.apparent_temperature) : null,
          humidity: cur.relative_humidity_2m != null ? Math.round(cur.relative_humidity_2m) : null,
          wind: cur.wind_speed_10m != null ? Math.round(cur.wind_speed_10m) : null,
          code: cur.weather_code != null ? cur.weather_code : null,
          text: WMO[cur.weather_code] || '',
          max: dly.temperature_2m_max ? Math.round(dly.temperature_2m_max[0]) : null,
          min: dly.temperature_2m_min ? Math.round(dly.temperature_2m_min[0]) : null,
          precip: cur.precipitation != null ? cur.precipitation : null,
          cloud: cur.cloud_cover != null ? cur.cloud_cover : null,
          pressure: cur.pressure_msl != null ? Math.round(cur.pressure_msl) : null,
          windDir: cur.wind_direction_10m != null ? Math.round(cur.wind_direction_10m) : null,
          gust: cur.wind_gusts_10m != null ? Math.round(cur.wind_gusts_10m) : null,
          vis: (d.hourly && d.hourly.visibility && d.hourly.visibility[0] != null) ? Math.round(d.hourly.visibility[0]/1000) : null,
          dew: (d.hourly && d.hourly.dew_point_2m && d.hourly.dew_point_2m[0] != null) ? Math.round(d.hourly.dew_point_2m[0]) : null,
          uvMax: (dly.uv_index_max && dly.uv_index_max[0] != null) ? Math.round(dly.uv_index_max[0]) : null,
          precipProb: (dly.precipitation_probability_max && dly.precipitation_probability_max[0] != null) ? dly.precipitation_probability_max[0] : null,
          sunrise: dly.sunrise ? String(dly.sunrise[0]).slice(11,16) : null,
          sunset: dly.sunset ? String(dly.sunset[0]).slice(11,16) : null,
          isDay: cur.is_day != null ? cur.is_day : null,
        };
      });
      const d0 = arr[0] || {};
      const dly = d0.daily || {};
      DALIAN_DAILY = (dly.time || []).map((t, i) => ({
        date: t,
        max: dly.temperature_2m_max ? Math.round(dly.temperature_2m_max[i]) : null,
        min: dly.temperature_2m_min ? Math.round(dly.temperature_2m_min[i]) : null,
        code: dly.weather_code ? dly.weather_code[i] : null,
        text: WMO[dly.weather_code ? dly.weather_code[i] : -1] || ''
      }));
      WEATHER_AT = Date.now(); WEATHER_ERR = null;
    } catch (e) {
      WEATHER_ERR = String(e.message || e).slice(0, 120);
      WEATHER_AT = Date.now() - maxAgeMs + 60000;
    }
    inflight.weather = null;
  })();
  return inflight.weather;
}

const CACHE = { status: null, statusAt: 0, cron: null, cronAt: 0, sess: null, sessAt: 0, host: null, hostAt: 0 };
const PS = process.env.INFOWIN_PS || '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe';
const PS1 = process.env.INFOWIN_PS1 || '\\\\wsl.localhost\\Ubuntu\\home\\j\\openclaw-workspaces\\work\\果果助手\\host-metrics.ps1';
const ERR = {};
let inflight = {};

function runCli(args, timeoutMs) {
  return new Promise((resolve) => {
    execFile(CLI, args, { timeout: timeoutMs || 90000, maxBuffer: 64 * 1024 * 1024, env: process.env }, (err, stdout, stderr) => {
      if (err && !stdout) return resolve({ ok: false, error: (stderr || err.message || '').slice(0, 300) });
      const txt = String(stdout || '').trim();
      const starts = [txt.indexOf('{'), txt.indexOf('[')].filter(i => i >= 0);
      const start = starts.length ? Math.min.apply(null, starts) : -1;
      try { resolve({ ok: true, data: JSON.parse(start >= 0 ? txt.slice(start) : txt) }); }
      catch (e) { resolve({ ok: false, error: 'JSON parse failed: ' + e.message }); }
    });
  });
}

function runHost() {
  return new Promise((resolve) => {
    execFile(PS, ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', PS1],
      { timeout: 45000, maxBuffer: 4 * 1024 * 1024, windowsHide: true }, (err, stdout) => {
        if (err && !stdout) return resolve({ ok: false, error: String(err.message || '').slice(0, 200) });
        const txt = String(stdout || '');
        const i = txt.indexOf('{');
        try { resolve({ ok: true, data: JSON.parse(txt.slice(i, txt.lastIndexOf('}') + 1)) }); }
        catch (e) { resolve({ ok: false, error: 'host json parse: ' + e.message }); }
      });
  });
}

const HM_FAST = '/mnt/c/Users/J/AppData/Local/Temp/hm-fast.json';
const FAST_PS = process.env.INFOWIN_PS1_FAST || '\\\\wsl.localhost\\Ubuntu\\home\\j\\openclaw-workspaces\\work\\果果助手\\host-metrics-loop.ps1';
let fastProc = null;
function startFastSampler() {
  try { const st = fs.statSync(HM_FAST); if (Date.now() - st.mtimeMs < 5000) return; } catch (e) {}
  if (fastProc) return;
  try {
    let ffd = 'ignore';
    try { ffd = fs.openSync('/tmp/host-fast-sampler.log', 'a'); } catch (e) {}
    fastProc = spawn(PS, ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', FAST_PS], { detached: true, stdio: ['ignore', ffd, ffd], windowsHide: true });
    fastProc.on('exit', () => { fastProc = null; });
    fastProc.on('error', () => { fastProc = null; });
    fastProc.unref();
  } catch (e) { fastProc = null; }
}
function readFast() {
  try { return JSON.parse(fs.readFileSync(HM_FAST, 'utf8')); } catch (e) { return null; }
}
let FAST = null;
function applyFast(d) {
  const hh = CACHE.host;
  if (!hh || !d) return;
  if (d.lhm) hh.lhm = d.lhm;   /* CPU 温度 / 风扇（LHM） */
  if (typeof d.cpu === 'number') hh.cpu = d.cpu;
  if (d.memUsedGB) { hh.memUsedGB = d.memUsedGB; hh.memTotalGB = d.memTotalGB || hh.memTotalGB; }
  if (d.commitUsedGB) { hh.commitUsedGB = d.commitUsedGB; hh.commitLimitGB = d.commitLimitGB || hh.commitLimitGB; }
  if (d.readMBs != null) hh.diskIO = { readMBs: d.readMBs, writeMBs: d.writeMBs, busyPct: d.busyPct };
  if (d.rxMBs != null) hh.netIO = { rxMBs: d.rxMBs, txMBs: d.txMBs };
  if (d.procCount) hh.procCount = d.procCount;
  if (d.uptimeSec) hh.uptimeSec = d.uptimeSec;
  if (d.wslMemMB != null) { hh.wslMemMB = d.wslMemMB; hh.wslCpu = d.wslCpu || 0; }
  if (d.gpu) hh.gpu = Object.assign({}, hh.gpu || {}, d.gpu);
  hh.fastAt = d.t;
}
function mergeFast() {
  const d = readFast();
  if (!d || !d.t || Date.now() - d.t > 6000) return false;
  if (!CACHE.host) return false;
  FAST = d;
  applyFast(d);
  CACHE.hostAt = Date.now();
  return true;
}

/* ---- gateway (OpenClaw) live sample from /proc ---- */
let GW_PID = 0, GW_CHECKED = 0, ocPrev = null;
function findGatewayPid() {
  if (GW_PID && Date.now() - GW_CHECKED < 60000) return GW_PID;
  GW_CHECKED = Date.now();
  try {
    for (const p of fs.readdirSync('/proc')) {
      if (!/^\d+$/.test(p)) continue;
      try {
        const cl = fs.readFileSync('/proc/' + p + '/cmdline', 'utf8');
        if (cl.indexOf('openclaw') >= 0 && cl.indexOf('gateway') >= 0) { GW_PID = Number(p); return GW_PID; }
      } catch (e) {}
    }
  } catch (e) {}
  return GW_PID;
}
function sampleOc() {
  if (!CACHE.host) return;
  const pid = findGatewayPid();
  if (!pid) return;
  try {
    const st = fs.readFileSync('/proc/' + pid + '/stat', 'utf8');
    const rest = st.slice(st.lastIndexOf(')') + 2).split(' ');
    const ticks = Number(rest[11]) + Number(rest[12]);
    const now = Date.now();
    let rssMB = null;
    try {
      const status = fs.readFileSync('/proc/' + pid + '/status', 'utf8');
      const m = /VmRSS:\s+(\d+) kB/.exec(status);
      if (m) rssMB = Math.round(Number(m[1]) / 1024);
    } catch (e) {}
    if (ocPrev) {
      const dt = (now - ocPrev.t) / 1000;
      const dc = (ticks - ocPrev.ticks) / 100 / dt;
      const cores = require('os').cpus().length || 1;
      CACHE.host.ocCpu = Math.max(0, Math.min(100, Math.round(dc * 100 / cores)));
    }
    ocPrev = { t: now, ticks };
    if (rssMB != null) CACHE.host.ocMemMB = rssMB;
    CACHE.host.ocPid = pid;
  } catch (e) {}
}

async function refreshHost(maxAgeMs) {
  if (Date.now() - CACHE.hostAt < maxAgeMs) return;
  if (inflight.host) return inflight.host;
  inflight.host = (async () => {
    const r = await runHost();
    CACHE.hostAt = Date.now();
    if (r.ok) { CACHE.host = r.data; if (FAST) applyFast(FAST); delete ERR.host; } else { ERR.host = r.error; }
    inflight.host = null;
  })();
  return inflight.host;
}

async function refresh(key, args, maxAgeMs) {
  const now = Date.now();
  const at = key + 'At';
  if (now - CACHE[at] < maxAgeMs) return;
  if (inflight[key]) return inflight[key];
  inflight[key] = (async () => {
  const r = await runCli(args, 10000);
  inflight[key] = null;
  CACHE[at] = Date.now();
  if (r.ok) { CACHE[key] = r.data; delete ERR[key]; }
  else { ERR[key] = r.error; }
  })();
  return inflight[key];
}

function procUptime(pid) {
  try {
    const st = fs.readFileSync('/proc/' + pid + '/stat', 'utf8');
    const rest = st.slice(st.lastIndexOf(')') + 2).split(' ');
    const startTicks = Number(rest[19]);
    const uptime = Number(fs.readFileSync('/proc/uptime', 'utf8').split(' ')[0]);
    const hz = 100;
    return Math.max(0, Math.round(uptime - startTicks / hz));
  } catch { return null; }
}

function pad(n) { return String(n).padStart(2, '0'); }

function humanSchedule(s) {
  if (!s) return '—';
  if (s.kind === 'cron') {
    const e = String(s.expr || '').trim();
    const p = e.split(/\s+/);
    if (p.length === 5) {
      const [mi, ho, dom, mon, dow] = p;
      if (mi === '*' && ho === '*' && dom === '*' && mon === '*' && dow === '*') return '每分钟';
      let m = mi.match(/^\*\/(\d+)$/);
      if (m && ho === '*') return '每 ' + m[1] + ' 分钟';
      m = ho.match(/^\*\/(\d+)$/);
      if (/^\d+$/.test(mi) && m && dom === '*') return '每 ' + m[1] + ' 小时 (第 ' + mi + ' 分)';
      if (/^\d+$/.test(mi) && /^\d+$/.test(ho) && dom === '*' && mon === '*' && dow === '*')
        return '每天 ' + pad(ho) + ':' + pad(mi);
      if (/^\d+$/.test(mi) && /^\d+$/.test(ho) && /^\d+$/.test(dom)) return '每月 ' + dom + '日 ' + pad(ho) + ':' + pad(mi);
      // minute/hour lists: detect constant step
      const list = (x) => x.split(',').map(Number).filter(n => !isNaN(n));
      const step = (a) => {
        if (a.length < 2) return null;
        const d = a[1] - a[0];
        for (let i = 2; i < a.length; i++) if (a[i] - a[i - 1] !== d) return null;
        return d;
      };
      if (ho === '*' && /^[\d,]+$/.test(mi)) {
        const a = list(mi), d = step(a);
        if (d && a.length >= 3) return '每 ' + d + ' 分钟';
      }
      if (/^\d+$/.test(mi) && /^[\d,]+$/.test(ho)) {
        const a = list(ho), d = step(a);
        if (d && a.length >= 2) return '每 ' + d + ' 小时 (第 ' + mi + ' 分)';
      }
      return 'cron ' + (e.length > 22 ? e.slice(0, 22) + '…' : e);
    }
    return 'cron ' + (e.length > 22 ? e.slice(0, 22) + '…' : e);
  }
  if (s.kind === 'every') {
    let ms = s.everyMs || s.ms;
    if (!ms && s.expr) { const mm = String(s.expr).match(/(\d+)\s*(m|s|h|d)/i); if (mm) { const n = Number(mm[1]); const u = mm[2].toLowerCase(); ms = n * ({ s: 1000, m: 60000, h: 3600000, d: 86400000 }[u] || 60000); } }
    if (ms) { if (ms < 60000) return '每 ' + Math.round(ms / 1000) + ' 秒'; if (ms < 3600000) return '每 ' + Math.round(ms / 60000) + ' 分钟'; return '每 ' + (ms / 3600000).toFixed(1).replace(/\.0$/, '') + ' 小时'; }
    return 'every ' + (s.expr || '') ;
  }
  if (s.kind === 'at') return s.atMs ? new Date(s.atMs).toLocaleString('zh-CN', { hour12: false }) : '一次性';
  return s.kind || '—';
}

function humanSession(key) {
  const p = String(key || '').split(':');
  if (p[0] === 'agent') {
    const agent = p[1] || '?';
    const chan = p[2] || '';
    const kind = p[3] || '';
    const peer = p[4] || '';
    const label = [agent, chan, kind].filter(Boolean).join(' · ');
    return peer ? label + ' · ' + (peer.length > 12 ? peer.slice(0, 8) + '…' : peer) : label;
  }
  return key || '';
}

let LUNAR = null;
try { LUNAR = require('lunar-javascript'); } catch (e) { LUNAR = null; }

function almanac() {
  if (!LUNAR) return null;
  const nowCN = new Date(Date.now() + 8 * 3600 * 1000);
  const y = nowCN.getUTCFullYear(), m = nowCN.getUTCMonth() + 1, d = nowCN.getUTCDate();
  try {
    const solar = LUNAR.Solar.fromYmd(y, m, d);
    const l = solar.getLunar();
    const wk = ['日', '一', '二', '三', '四', '五', '六'][new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
    return {
      date: y + '-' + String(m).padStart(2, '0') + '-' + String(d).padStart(2, '0'),
      weekday: '星期' + wk,
      lunar: l.getMonthInChinese() + '月' + l.getDayInChinese(),
      ganzhi: l.getYearInGanZhi() + '年 ' + l.getMonthInGanZhi() + '月 ' + l.getDayInGanZhi() + '日',
      shengxiao: l.getYearShengXiao(),
      jieqi: l.getJieQi() || '',
      yi: (l.getDayYi() || []).slice(0, 7),
      ji: (l.getDayJi() || []).slice(0, 7),
      chong: l.getDayChongDesc ? l.getDayChongDesc() : '',
      sha: l.getDaySha ? l.getDaySha() : ''
    };
  } catch (e) { return null; }
}

function readPricing(){
  try { return JSON.parse(require('fs').readFileSync(PRICING_JSON,'utf8')); } catch(e){ return null; }
}

function build() {
  const now = Date.now();
  const modelStats = readModelStats();
  const status = CACHE.status || {};
  const pid = status.pid || status.gateway?.pid || null;
  const gw = status.gateway || {};
  const gatewayOk = gw.reachable !== false && (gw.status ? gw.status === 'ok' : !!pid);
  const jobs = (CACHE.cron && CACHE.cron.jobs) ? CACHE.cron.jobs : [];
  const sessions = (CACHE.sess && CACHE.sess.sessions) ? CACHE.sess.sessions : [];
  const SESSION_TOK = {};
  for (const se of sessions) {
    const k = se.key || se.sessionKey || '';
    const mm = /cron:([0-9a-f-]{8,})/.exec(k);
    if (mm) SESSION_TOK[mm[1]] = Math.round((se.inputTokens || 0) + (se.outputTokens || 0));
  }

  const mapped = jobs.map(j => ({
    id: j.id,
    name: j.name || '(未命名)',
    enabled: j.enabled !== false,
    scheduleText: humanSchedule(j.schedule),
    scheduleRaw: j.schedule,
    nextAt: j.nextRunAtMs || j.state?.nextRunAtMs || null,
    lastAt: j.lastRunAtMs || j.state?.lastRunAtMs || null,
    lastStatus: j.lastRunStatus || j.state?.lastRunStatus || null,
    lastError: j.state?.lastError || j.lastError || '',
    status: j.status || j.state?.status || 'unknown',
    agent: j.effectiveAgentId || j.agentId || 'main',
    kind: (j.payload && j.payload.kind) || null,
    tok: SESSION_TOK[j.id] || null,
    target: j.sessionTarget || ''
  })).sort((a, b) => (a.nextAt || Infinity) - (b.nextAt || Infinity));

  const running = mapped.filter(j => j.status === 'running');
  const recentDone = mapped.filter(j => j.lastAt && now - j.lastAt < 30 * 60000)
    .sort((a, b) => b.lastAt - a.lastAt);
  const upcoming = mapped.filter(j => j.enabled && j.nextAt && j.nextAt > now && j.nextAt - now < 24 * 3600000);

  const humanSet = new Set(), channelSet = new Set();
  for (const se of sessions) {
    const a = se.createdActor || {}; if (a.type === 'human' && a.id) humanSet.add(a.id);
    (se.participants || []).forEach(function(pt){ const idn = pt && pt.identity; if (idn && idn.senderKind === 'human' && idn.id) humanSet.add(idn.id); });
    const kp = String(se.key || '').split(':'); if (kp[2]) channelSet.add(kp[2]);
  }
  const humanCount = humanSet.size, channelCount = channelSet.size;

  const activeSessions = sessions
    .filter(s => s.updatedAt && now - s.updatedAt < 5 * 60000)
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, 12)
    .map(s => ({
      key: s.key, label: humanSession(s.key), agent: s.agentId, model: s.model,
      kind: s.kind, updatedAt: s.updatedAt, ageMs: s.ageMs, totalTokens: s.totalTokens,
      aborted: !!s.abortedLastRun
    }));

  const activeSubagents = sessions
    .filter(s => (s.kind === 'spawn-child' || /:subagent:/.test(String(s.key||''))) && s.updatedAt && now - s.updatedAt < 15*60000)
    .sort((a,b) => b.updatedAt - a.updatedAt)
    .slice(0, 8)
    .map(s => ({ key: s.key, label: s.label || String(s.key||'').split(':').pop().slice(0,8), agent: s.agentId || '(root)' , model: s.model || null, updatedAt: s.updatedAt, ageMs: now - s.updatedAt }));

  const subagents = sessions
    .filter(s => s.kind === 'spawn-child' && s.updatedAt && now - s.updatedAt < 12*3600000)
    .sort((a,b) => b.updatedAt - a.updatedAt)
    .slice(0, 20)
    .map(s => ({
      key: s.key,
      label: s.label || String(s.key||'').split(':').pop().slice(0,10),
      role: s.subagentRole || '',
      model: s.model || null,
      agent: s.agentId || '(root)',
      parent: s.parentSessionKey || '',
      updatedAt: s.updatedAt,
      totalTokens: s.totalTokens || 0,
      aborted: !!s.abortedLastRun
    }));

  return {
    pricing: readPricing(),
    usageToday: readUsageToday(),
    almanac: almanac(),
    dalianDaily: DALIAN_DAILY,   serverTime: now,
    gateway: {
      ok: gatewayOk, pid, uptimeSec: pid ? procUptime(pid) : null,
      version: status.runtimeVersion || gw.self?.version || null,
      latest: LATEST_V.version, latestErr: LATEST_V.err, latestAt: LATEST_V.at,
      memoryMB: status.processMemory ? Math.round((status.processMemory.rssBytes || status.processMemory.rss || 0) / 1048576) : null,
      eventLoop: status.eventLoop ? Math.round((status.eventLoop.p99Ms || status.eventLoop.meanMs || 0)) : null,
      users: humanCount, channels: channelCount,
      sessions: Array.isArray(status.sessions) ? status.sessions.length : (status.sessions?.count ?? status.sessions?.total ?? null),
      agents: Array.isArray(status.agents) ? status.agents.length : (status.agents?.count ?? null),
      host: status.os?.hostname || null,
      url: gw.url || null,
      lanIp: (() => { try { const n = require('os').networkInterfaces(); for (const k of Object.keys(n)) for (const a of (n[k]||[])) if (a.family === 'IPv4' && !a.internal) return a.address; } catch(e){} return null; })(),
      service: status.gatewayService?.state || null,
      latencyMs: gw.connectLatencyMs ?? null
    },
    stats: (() => {
      const enabled = mapped.filter(j => j.enabled);
      const dayAgo = now - 86400000;
      const ran24h = mapped.filter(j => j.lastAt && j.lastAt > dayAgo).length;
      const okLast = mapped.filter(j => /ok|success|done/i.test(String(j.lastStatus || ''))).length;
      const bad = mapped.filter(j => /error|fail/i.test(String(j.lastStatus || '')));
      const hours = new Array(12).fill(0);
      for (const j of mapped) {
        if (!j.lastAt) continue;
        const idx = Math.floor((now - j.lastAt) / 3600000);
        if (idx >= 0 && idx < 12) hours[11 - idx]++;
      }
      return {
        total: mapped.length, enabled: enabled.length, running: running.length,
        errors: bad.length, ran24h, okLast,
        successPct: mapped.length ? Math.round(okLast / mapped.length * 100) : 0,
        coveragePct: enabled.length ? Math.round(Math.min(1, ran24h / enabled.length) * 100) : 0,
        hours,
        tokenSum: sessions.reduce((a, x) => a + (x.totalTokens || 0), 0),
        active24h: sessions.filter(x => x.updatedAt && now - x.updatedAt < 86400000).length
      };
    })(),
    failing: mapped.filter(j => j.enabled !== false && !/disabled by operator/i.test(String(j.lastError || '')) && /error|fail/i.test(String(j.lastStatus || '')) && !/interrupted by gateway restart|gateway stopping|isolated agent setup timed out|not completed startup inspection/i.test(String(j.lastError || ''))).slice(0, 5).map(j => {      try { const m = JSON.parse(require('node:fs').readFileSync('/home/j/.openclaw/workspace/state/work/job-fix-eta.json', 'utf8')); const e = m[j.name] || {}; return Object.assign({}, j, { eta: e.eta || '', etaWhy: e.why || '' }); } catch (e) { return j; }    }),
    running,
    recentDone: recentDone.slice(0, 10),
    upcoming: upcoming.slice(0, 40),
    jobs: mapped,
    activeSessions,
    activeSubagents,
    subagents,
    buildId: buildId(),
    version: readVersion(),
    ledger: (loadLedger(), LEDGER),
    agentReply: (CACHE.agentReply || []).slice(0, 64),
    toolActivity: TOOLS.val || [],
    agentNames: (Array.isArray(CACHE.agents) ? CACHE.agents : []).reduce((m, a) => { if (a && a.id) m[a.id] = { name: a.identityName || a.name || a.id, emoji: a.identityEmoji || '' }; return m; }, {}),
    agentModels: (Array.isArray(CACHE.agents) ? CACHE.agents : []).reduce((m, a) => { if (a && a.id) m[a.id] = a.model || ''; return m; }, {}),
    activeModels: (() => {
      const am = (Array.isArray(CACHE.agents) ? CACHE.agents : []).reduce((m, a) => { if (a && a.id) m[a.id] = a.model || ''; return m; }, {});
      const counts = {};
      for (const x of activeSessions) {
        const mdl = String(x.model || am[x.agent] || '').split('/').pop();
        if (!mdl) continue;
        counts[mdl] = (counts[mdl] || 0) + 1;
      }
      return Object.keys(counts).map(k => ({ model: k, count: counts[k] })).sort((a, b) => b.count - a.count);
    })(),
    todos: TODOS,
    stocks: STOCKS,
    fx: FX,
    fxAt: FX_AT,
    fxError: FX_ERR,
    stocksAt: STOCKS_AT,
    stocksError: STOCKS_ERR,
    weather: WEATHER,
    weatherAt: WEATHER_AT,
    weatherError: WEATHER_ERR,
    balances: BAL,
    quotaDelta: readQuotaDelta(),
    usageRate: readUsageRate(),
    modelRegistry: readModelRegistry(),
    backup: readBackup(),
    modelStats: modelStats,
    agentTokens: modelStats.agents || {},
    ollamaEndpoints: OLLAMA_EPS,
    lastUsed: readLastUsed(),
    ollama: OLLAMA.val,
    ollamaLatest: OL_LATEST.tag,
    bhost: BHOST.val,
    ollamaUpdate: OL_UPDATE,
    balRefresh: BAL_REFRESH,
    taskRefresh: TASK_REFRESH,
    balancesAt: BAL_AT,
    balancesError: BAL_ERR,
    logs: LOGS.slice(-40),
    logSeq: LOG_SEQ,
    logAlive: LOG_ALIVE,
    logRestarts: LOG_RESTARTS,
    host: CACHE.host ? Object.assign({}, CACHE.host, { ageMs: now - CACHE.hostAt }) : null,
    hostError: ERR.host || null,
    errors: Object.keys(ERR).length ? ERR : null,
    degraded: !CACHE.cron || !CACHE.sess
  };
}

const OR_CRED = '/home/j/openclaw-workspaces/work/state/openrouter-credits.json';
const OR_SH = __dirname + '/tools/openrouter-credits.sh';
let OR_BUSY = false, OR_LAST_TRY = 0;
function refreshOpenRouterCredits() {
  const now = Date.now();
  if (OR_BUSY || now - OR_LAST_TRY < 10 * 60e3) return;
  OR_BUSY = true; OR_LAST_TRY = now;
  execFile('bash', [OR_SH], { timeout: 40000 }, () => { OR_BUSY = false; });
}
function addOpenRouter(out) {
  try {
    if (!out || out.some(function (x) { return x && x.provider === 'OpenRouter'; })) return out;
    let j = null;
    try { j = JSON.parse(fs.readFileSync(OR_CRED, 'utf8')); } catch (e) {}
    const avail = (j && typeof j.available === 'number') ? j.available : null;
    const tot = (j && typeof j.total_credits === 'number') ? j.total_credits : null;
    const used = (j && typeof j.total_usage === 'number') ? j.total_usage : null;
    const capMs = (j && j.captured_at) ? Date.parse(j.captured_at) : NaN;
    const ageH = isFinite(capMs) ? (Date.now() - capMs) / 3600e3 : null;
    let status = 'na';
    if (avail != null) status = (avail <= 0.05) ? 'over' : ((ageH == null || ageH > 24) ? 'stale' : 'ok');
    if (avail == null || ageH == null || ageH > 0.5) refreshOpenRouterCredits();
    const detail = (tot != null)
      ? ('充值 $' + tot.toFixed(2) + (used != null ? (' · 已用 $' + used.toFixed(4)) : '') + ' · openrouter.ai/api/v1/credits')
      : '尚未采集（充值后点 ⟳）';
    out.push({
      provider: 'OpenRouter',
      model: 'deepseek / qwen / glm / kimi / minimax / gpt-oss',
      currency: 'USD', unit: '',
      balance: avail, spent: used,
      status: status, detail: detail,
      capturedAt: (j && j.captured_at) || null,
      updatedAt: Date.now()
    });
  } catch (e) {}
  return out;
}
function addExtras(out) { return addOpenRouter(addQianwen(out)); }

function addQianwen(out) {
  try {
    if (out && !out.some(function (x) { return x && x.provider === '千问'; })) {
      let qk = null;
      try { qk = (JSON.parse(fs.readFileSync(QUOTAS, 'utf8')).providers || {}).qianwen || null; } catch (e) {}
      let pct = null, usedPct = null;
      if (qk) {
        const rawRem = (typeof qk.month_remaining_pct === 'number') ? qk.month_remaining_pct
          : ((typeof qk.month_pct === 'number') ? qk.month_pct
          : ((qk.values && qk.values.month_pct != null && isFinite(Number(qk.values.month_pct))) ? Number(qk.values.month_pct) : null));
        if (rawRem != null) { pct = Math.round(rawRem * 10) / 10; usedPct = Math.round((100 - rawRem) * 10) / 10; }
      }
      const parts = [];
      if (qk && (qk.plan_name || qk.plan)) parts.push((qk.plan_name || qk.plan) + ' 套餐');
      if (usedPct != null) parts.push('本期已用 ' + usedPct + '%');
      if (qk && qk.plan_status) parts.push(qk.plan_status);
      if (qk && qk.month_reset_at) parts.push('月重置 ' + String(qk.month_reset_at).slice(5, 10).replace('-', '/'));
      out.push({
        provider: '千问', model: 'qwen3.8-max / qwen3.8-flash',
        currency: 'CNY', unit: pct != null ? '%可用' : '',
        balance: pct,
        status: pct == null ? 'na' : (pct <= 0 ? 'over' : 'ok'),
        detail: parts.length ? parts.join(' · ') : '套餐通道 · 5 个模型 · 余量待登录后可查',
        expires: (qk && qk.plan_expire) || null,
        capturedAt: (qk && qk.captured_at) || null,
        updatedAt: Date.now()
      });
    }
  } catch (e) {}
  return out;
}
let BAL = [], BAL_AT = 0, BAL_ERR = null, DS_LIVE = null;
let TOOLS = { at: 0, val: [] };
function refreshTools(){
  try {
    execFile('python3', [__dirname + '/tools/tool-activity.py'], { timeout: 20000, maxBuffer: 2e6 }, (err, stdout) => {
      if (err) return;
      try { TOOLS.val = JSON.parse(String(stdout || '[]')); TOOLS.at = Date.now(); } catch (e) {}
    });
  } catch (e) {}
}
setInterval(refreshTools, 10000); refreshTools();
let BAL_REFRESH = { running: false, startedAt: 0, finishedAt: 0, code: null, error: null, p: {} };
let TASK_REFRESH = { running: false, startedAt: 0, finishedAt: 0, error: null };
function startBalanceRefresh() {
  if (BAL_REFRESH.running) return BAL_REFRESH;
  BAL_REFRESH = { running: true, startedAt: Date.now(), finishedAt: 0, code: null, error: null, p: BAL_REFRESH.p || {} };
  const cmd = 'bash ' + BAL_SH + ' >/tmp/ocw-bal.log 2>&1; python3 /home/j/.openclaw/workspace/tools/quota-scrape.py --run >>/tmp/ocw-bal.log 2>&1';
  try {
    const p = spawn('sh', ['-lc', cmd], { detached: true, stdio: 'ignore', env: process.env });
    p.on('exit', (code) => {
      BAL_REFRESH.running = false;
      BAL_REFRESH.finishedAt = Date.now();
      BAL_REFRESH.code = code;
      BAL_REFRESH.error = code === 0 ? null : ('exit ' + code);
      BAL_AT = 0;
    });
    p.unref();
  } catch (e) {
    BAL_REFRESH.running = false; BAL_REFRESH.finishedAt = Date.now(); BAL_REFRESH.error = String(e.message || e);
  }
  return BAL_REFRESH;
}
function startBalanceRefreshOne(key) {
  const KNOWN = { deepseek: 1, zai: 1, kimi: 1, minimax: 1 };
  if (!KNOWN[key]) return { running: false, error: 'unknown provider: ' + key };
  BAL_REFRESH.p = BAL_REFRESH.p || {};
  const st = BAL_REFRESH.p[key] || (BAL_REFRESH.p[key] = { running: false, startedAt: 0, finishedAt: 0, code: null, error: null });
  if (st.running) return st;
  st.running = true; st.startedAt = Date.now(); st.finishedAt = 0; st.code = null; st.error = null;
  let cmd, log;
  if (key === 'deepseek') { cmd = 'bash ' + BAL_SH; log = '/tmp/ocw-bal-deepseek.log'; }
  else if (key === 'kimi') { cmd = 'python3 /home/j/.openclaw/workspace/tools/kimi-plan-refresh.py'; log = '/tmp/ocw-bal-kimi.log'; }
  else { cmd = 'python3 /home/j/.openclaw/workspace/tools/quota-scrape.py --run --only ' + key; log = '/tmp/ocw-bal-' + key + '.log'; }
  try {
    const p = spawn('sh', ['-lc', cmd + ' >>' + log + ' 2>&1'], { detached: true, stdio: 'ignore', env: process.env });
    p.on('exit', (code) => {
      st.running = false; st.finishedAt = Date.now(); st.code = code;
      st.error = code === 0 ? null : ('exit ' + code);
      if (key === 'deepseek' && code === 0) {
        try {
          const txt = fs.readFileSync(log, 'utf8');
          const m = txt.match(/¥\s*([0-9]+(?:\.[0-9]+)?)/g) || [];
          if (m.length) {
            const v = Number(m[m.length - 1].replace(/[^0-9.]/g, ''));
            if (isFinite(v)) DS_LIVE = { bal: v, at: Date.now() };
          }
        } catch (e) {}
      }
      BAL_AT = 0;
    });
    p.unref();
  } catch (e) {
    st.running = false; st.finishedAt = Date.now(); st.error = String(e.message || e);
  }
  return st;
}
const OLLAMA_CANDIDATES = [process.env.OLLAMA_URL, 'http://127.0.0.1:11434', 'http://192.168.1.106:11434', 'http://192.168.1.109:11434'].filter(Boolean);
let OLLAMA_URL = OLLAMA_CANDIDATES[0];
let OLLAMA = { at: 0, val: { up: null, baseUrl: OLLAMA_URL } };
async function pollOllama() {
  const t0 = Date.now();
  const list = [OLLAMA_URL].concat(OLLAMA_CANDIDATES.filter(u => u !== OLLAMA_URL));
  let lastErr = null;
  for (const base of list) {
    try {
      const v = await fetch(base + '/api/version', { signal: AbortSignal.timeout(2500) }).then(r => r.json());
      const ps = await fetch(base + '/api/ps', { signal: AbortSignal.timeout(2500) }).then(r => r.json());
      const models = (ps.models || []).map(m => ({
        name: m.name,
        sizeGB: Math.round((m.size || 0) / 1e9 * 10) / 10,
        vramGB: Math.round((m.size_vram || 0) / 1e9 * 10) / 10,
        expiresAt: m.expires_at || null
      }));
      if (base !== OLLAMA_URL) {
        OLLAMA_URL = base;
        console.log('[guoguo] ollama endpoint -> ' + base);
      }
      OLLAMA = { at: Date.now(), val: { up: true, version: v.version || null, latencyMs: Date.now() - t0, models: models, baseUrl: base, at: Date.now() } };
      return;
    } catch (e) {
      lastErr = e;
    }
  }
  OLLAMA = { at: Date.now(), val: { up: false, error: String((lastErr && lastErr.message) || lastErr || 'unreachable').slice(0, 60), baseUrl: OLLAMA_URL, at: Date.now() } };
}
pollOllama();
setInterval(pollOllama, 10000);
// --- B 机（192.168.1.107）指标：需 B 机运行 bmeter.ps1 提供 /metrics ---
const BHOST_URL = 'http://192.168.1.107:18080/metrics';
let BHOST = { at: 0, val: { ok: false, reason: 'B 机未运行采集器', url: BHOST_URL } };
async function pollBHost() {
  try {
    const ctl = new AbortController();
    const to = setTimeout(() => ctl.abort(), 12000);
    const r = await fetch(BHOST_URL, { signal: ctl.signal, cache: 'no-store' });
    clearTimeout(to);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    BHOST = { at: Date.now(), val: Object.assign({ ok: true, url: BHOST_URL }, d) };
  } catch (e) {
    const msg = (e && e.name === 'AbortError') ? '超时不可达' : String((e && e.message) || e).slice(0, 48);
    BHOST = { at: Date.now(), val: { ok: false, reason: 'B 机未运行采集器', detail: msg, url: BHOST_URL } };
  }
}
pollBHost();
setInterval(pollBHost, 20000);

let OLLAMA_EPS = [];
async function pollOllamaAll() {
  // 只有一台真实 Ollama：192.168.1.107。本机 127.0.0.1:11434 是 WSL 内的 ollama-proxy.py 转发，不是独立实例，不再重复列出。
  const eps = [
    { name: '本机 A机', baseUrl: 'http://127.0.0.1:11435', known: [] },
    { name: 'B机 192.168.1.107', baseUrl: 'http://192.168.1.107:11434', known: [] }
  ];
  const out = [];
  for (const ep of eps) {
    const t0 = Date.now();
    try {
      const ctl = new AbortController();
      const to = setTimeout(() => ctl.abort(), 3000);
      const r1 = await fetch(ep.baseUrl + '/api/version', { signal: ctl.signal });
      clearTimeout(to);
      const v = await r1.json().catch(() => ({}));
      let models = [];
      try {
        const c2 = new AbortController();
        const to2 = setTimeout(() => c2.abort(), 3000);
        const r2 = await fetch(ep.baseUrl + '/api/ps', { signal: c2.signal });
        clearTimeout(to2);
        const ps = await r2.json().catch(() => ({}));
        models = (ps && ps.models) || [];
        models.forEach(function(mm){ mm.loaded = true; });
      } catch (e) {}
      try {
        // 合并已安装但未加载的模型（/api/tags），保证新装模型也能显示
        const c3 = new AbortController();
        const to3 = setTimeout(() => c3.abort(), 3000);
        const r3 = await fetch(ep.baseUrl + '/api/tags', { signal: c3.signal });
        clearTimeout(to3);
        const tags = await r3.json().catch(() => ({}));
        const seen = {};
        models.forEach(function(mm){ const n = mm.name || mm.model; if (n) seen[n] = true; });
        (tags.models || []).forEach(function(t){
          const n = t.name || t.model;
          if (n && !seen[n]) { seen[n] = true; models.push({ name: n, size: t.size, loaded: false }); }
        });
      } catch (e) {}
      out.push({ name: ep.name, baseUrl: ep.baseUrl, up: true, version: v.version || '', latencyMs: Date.now() - t0, models: models, known: ep.known });
    } catch (e) {
      out.push({ name: ep.name, baseUrl: ep.baseUrl, up: false, error: String((e && e.message) || e).slice(0, 60), models: [], known: ep.known });
    }
  }
  OLLAMA_EPS = out;
}
pollOllamaAll();
setInterval(pollOllamaAll, 10000);

// --- agent 回复状态：只读扫描各 agent 的 sqlite（5s 一次）---
CACHE.agentReply = CACHE.agentReply || [];
function pollAgentReply() {
  execFile('python3', [__dirname + '/tools/agent-reply.py'], { timeout: 15000, maxBuffer: 4e6 }, (err, stdout) => {
    if (err) return;
    try {
      const arr = JSON.parse(stdout);
      if (Array.isArray(arr)) CACHE.agentReply = arr;
    } catch (e) {}
  });
}
pollAgentReply();
setInterval(pollAgentReply, 5000);


let UR_CACHE = null, UR_AT = 0;
let LU_CACHE = null, LU_KEY = '';
function readLastUsed() {
  try {
    const fp = '/home/j/.openclaw/workspace/state/usage-meter/ledger.jsonl';
    const st = fs.statSync(fp);
    const key = st.size + ':' + Math.floor(st.mtimeMs);
    if (LU_CACHE && LU_KEY === key) return LU_CACHE;
    const lines = fs.readFileSync(fp, 'utf8').split(String.fromCharCode(10));
    const TS = /"ts"\s*:\s*"([^"]+)"/, MD = /"model"\s*:\s*"([^"]+)"/;
    const byProvider = {}, byModel = {};
    const prov = (m) => m.indexOf('deepseek') >= 0 ? 'deepseek'
      : (m.indexOf('glm') === 0 ? 'zhipu'
      : (m.indexOf('kimi') >= 0 || m.indexOf('k3') === 0 ? 'kimi'
      : (m.indexOf('minimax') >= 0 ? 'minimax' : (m.indexOf('qwen') === 0 ? 'ollama' : 'other'))));
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i]; if (l.length < 20) continue;
      const mt = TS.exec(l), mm = MD.exec(l);
      if (!mt || !mm) continue;
      const t = Date.parse(mt[1].replace(' ', 'T') + '+08:00');
      if (!isFinite(t)) continue;
      const model = mm[1], pv = prov(model.toLowerCase());
      if (pv !== 'other') {
        let cur = byProvider[pv];
        if (!cur) { cur = byProvider[pv] = { t: 0, model: '', calls: 0 }; }
        cur.calls = (cur.calls || 0) + 1;
        if (t > cur.t) { cur.t = t; cur.model = model; }
      }
      if (!byModel[model] || t > byModel[model].t) byModel[model] = { t: t, provider: pv };
    }
    LU_CACHE = { byProvider: byProvider, byModel: byModel, at: Date.now() };
    LU_KEY = key;
    return LU_CACHE;
  } catch (e) { return { byProvider: {}, byModel: {}, error: String((e && e.message) || e).slice(0, 60) }; }
}

const MS_PATH = '/home/j/.openclaw/workspace/state/usage-meter/ledger.jsonl';
let MS_CACHE = null, MS_MT = 0, MS_AT = 0;
function readModelStats() {
  try {
    const now = Date.now();
    let _st = null; try { _st = fs.statSync(MS_PATH); } catch (e) {}
    if (MS_CACHE && _st && _st.mtimeMs === MS_MT && now - MS_AT < 20000) return MS_CACHE;
    const txt = fs.readFileSync(MS_PATH, 'utf8');
    const lines = txt.split(String.fromCharCode(10));
    const t10 = now - 10 * 60e3, t60 = now - 60 * 60e3, t7d = now - 7 * 86400e3;
    const d = new Date(now + 8 * 3600e3);
    const tDay = Date.parse(d.toISOString().slice(0, 10) + 'T00:00:00+08:00');
    const by = {};
    const ag = {};
    const wins = [['h1', 3600e3], ['h6', 6 * 3600e3], ['h12', 12 * 3600e3], ['h24', 24 * 3600e3]];
    function bumpAg(agent, t, tin, tout) {
      const key = String(agent || '');
      if (!key) return;
      if (!ag[key]) ag[key] = { h1: [0, 0], h6: [0, 0], h12: [0, 0], h24: [0, 0] };
      for (let wi = 0; wi < wins.length; wi++) {
        if (t >= now - wins[wi][1]) {
          const w = wins[wi][0];
          ag[key][w][0] += tin;
          ag[key][w][1] += tout;
        }
      }
    }
    function bump(model, k, v) {
      const key = String(model || '');
      if (!key) return;
      if (!by[key]) by[key] = { today: 0, c10: 0, c60: 0, out10: 0, d7: 0 };
      by[key][k] += v;
    }
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      if (!l) continue;
      let o; try { o = JSON.parse(l); } catch (e) { continue; }
      const t = Date.parse(String(o.ts).replace(' ', 'T') + '+08:00');
      if (!isFinite(t)) continue;
      const _agent = o.agent || o.agentId || '';
      if (_agent) {
        const _tin = Number(o.input || o.inputTokens || o.prompt_tokens || 0);
        const _tout = Number(o.output || o.out || o.outputTokens || o.completion_tokens || 0);
        bumpAg(_agent, t, _tin, _tout);
      }
      const model = o.model || '';
      if (!model) continue;
      if (!by[model]) by[model] = { today: 0, c10: 0, c60: 0, out10: 0, d7: 0, last: 0 };
      if (t > by[model].last) by[model].last = t;
      if (t >= tDay) bump(model, 'today', 1);
      if (t >= t7d) bump(model, 'd7', 1);
      if (t >= t60) {
        bump(model, 'c60', 1);
        const out = Number(o.output || o.out || o.outputTokens || o.completion_tokens || o.output_tokens || 0);
        if (t >= t10) { bump(model, 'c10', 1); bump(model, 'out10', out); }
      }
    }
    const _res = { by: by, agents: ag, at: now };
    MS_CACHE = _res; MS_MT = _st ? _st.mtimeMs : 0; MS_AT = now;
    return _res;
  } catch (e) { return { by: {}, at: Date.now() }; }
}


let OL_LATEST = { at: 0, tag: '' };
let OL_UPDATE = { running: false, startedAt: 0, msg: '' };
async function pollOllamaLatest() {
  try {
    const r = await fetch('https://api.github.com/repos/ollama/ollama/releases/latest', { headers: { 'user-agent': 'info-window', accept: 'application/vnd.github+json' }, signal: AbortSignal.timeout(8000) });
    const j = await r.json().catch(function(){ return {}; });
    if (j && j.tag_name) OL_LATEST = { at: Date.now(), tag: String(j.tag_name).replace(/^v/, '') };
  } catch (e) {}
}
pollOllamaLatest();
setInterval(pollOllamaLatest, 6 * 3600 * 1000);
let BK_CACHE = null, BK_KEY = '';
function readBackup(){
  try {
    const fp = '/home/j/.openclaw/workspace/state/work/bk-run.log';
    const st = fs.statSync(fp);
    const key = st.size + ':' + Math.floor(st.mtimeMs);
    if (BK_CACHE && BK_KEY === key) return BK_CACHE;
    const lines = fs.readFileSync(fp, 'utf8').split(String.fromCharCode(10));
    let at = null, name = '', bytes = 0;
    for (let i = lines.length - 1; i >= 0; i--) {
      const L = lines[i];
      const m = L.match(/✅ 归档已推送到群晖: (\S+) \((\d+) 字节\)/);
      if (m) { name = m[1]; bytes = Number(m[2]) || 0; break; }
      const m2 = L.match(/✅ 已落 D 盘: (\S+) \((\d+) 字节\)/);
      if (m2 && !name) { name = m2[1]; bytes = Number(m2[2]) || 0; }
    }
    const nm = name.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2})-(\d{2})-(\d{2})/);
    if (nm) at = new Date(+nm[1], +nm[2]-1, +nm[3], +nm[4], +nm[5], +nm[6]).getTime();
    BK_CACHE = { ok: !!name, at: at, name: name, gb: bytes ? Math.round(bytes/1073741824*10)/10 : null };
    BK_KEY = key;
    return BK_CACHE;
  } catch (e) { return { ok: false, at: null, name: '', gb: null, error: String(e && e.message || e).slice(0,60) }; }
}

const REG_PATH = '/home/j/.openclaw/workspace-model/state/model-warden/registry.json';
let REG_CACHE = null, REG_MT = 0;
function readModelRegistry() {
  try {
    const st = fs.statSync(REG_PATH);
    if (REG_CACHE && st.mtimeMs === REG_MT) return REG_CACHE;
    const d = JSON.parse(fs.readFileSync(REG_PATH, 'utf8'));
    const out = { updated: d.updated || null, summary: d.summary || null, providers: {}, at: st.mtimeMs };
    Object.keys(d.providers || {}).forEach(function(pk){
      const pv = d.providers[pk] || {};
      const ms = pv.models || {};
      out.providers[pk] = Object.keys(ms).map(function(mn){
        const m = ms[mn] || {};
        return { name: mn, tier: m.tier || '', ctx: m.ctx || '', in: (m.in == null ? null : m.in), out: (m.out == null ? null : m.out), use: m.use || '', status: m.status || '', note: m.note || '', speed: m.speed || '', size: m.size || '' };
      }).filter(function(m){
        return !/^(removed|retired|missing|deleted|gone)/i.test(String(m.status || '').trim());
      });
    });
    if (out.providers.zai && out.providers.zhipu) {
      const seen = {};
      out.providers.zai.forEach(function(m){ seen[m.name] = 1; });
      out.providers.zhipu.forEach(function(m){ if (!seen[m.name]) out.providers.zai.push(m); });
      delete out.providers.zhipu;
    }
    REG_CACHE = out; REG_MT = st.mtimeMs;
    return out;
  } catch (e) {
    return { error: String((e && e.message) || e).slice(0, 60), providers: {} };
  }
}
function readUsageRate() {
  const now = Date.now();
  if (UR_CACHE && (now - UR_AT) < 30000) return UR_CACHE;
  try {
    const txt = fs.readFileSync('/home/j/.openclaw/workspace/state/usage-meter/ledger.jsonl', 'utf8');
    const lines = txt.split(String.fromCharCode(10));
    const t5 = now - 5 * 60e3, t10 = now - 10 * 60e3, t60 = now - 60 * 60e3;
    let c5 = 0, c10 = 0, c60 = 0;
    const bm = {};
    const bp = { deepseek: { c10: 0, c60: 0, out10: 0 }, zhipu: { c10: 0, c60: 0, out10: 0 }, kimi: { c10: 0, c60: 0, out10: 0 }, minimax: { c10: 0, c60: 0, out10: 0 }, ollama: { c10: 0, c60: 0, out10: 0 } };
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i];
      if (!l) continue;
      let o; try { o = JSON.parse(l); } catch (e) { continue; }
      const t = Date.parse(String(o.ts).replace(' ', 'T') + '+08:00');
      if (!isFinite(t)) continue;
      if (t >= t60) {
        c60++;
        const m = String(o.model || '').toLowerCase();
        const prov = m.indexOf('deepseek') >= 0 ? 'deepseek'
          : (m.indexOf('glm') === 0 ? 'zhipu'
          : (m.indexOf('kimi') >= 0 || m.indexOf('k3') === 0 ? 'kimi'
          : (m.indexOf('minimax') >= 0 ? 'minimax' : (m.indexOf('qwen') === 0 ? 'ollama' : 'other'))));
        if (!(prov in bp)) bp[prov] = { c10: 0, c60: 0, out10: 0 };
        bp[prov].c60++;
        if (t >= t10) { c10++; bp[prov].c10++; bp[prov].out10 += Number(o.output || 0); }
        {
          const mn = String(o.model || '');
          if (mn) {
            if (!(mn in bm)) bm[mn] = { c10: 0, c60: 0, out10: 0, out60: 0 };
            bm[mn].c60++; bm[mn].out60 += Number(o.output || 0);
            if (t >= t10) { bm[mn].c10++; bm[mn].out10 += Number(o.output || 0); }
          }
        }
        if (t >= t5) c5++;
      }
    }
    const byProvider = {};
    Object.keys(bp).forEach(function(k){
      byProvider[k] = { c10: bp[k].c10, c60: bp[k].c60, pm10: Math.round(bp[k].c10 / 10 * 10) / 10, out10: bp[k].out10, tps: Math.round(bp[k].out10 / 600 * 10) / 10 };
    });
    const byModel = {};
    Object.keys(bm).forEach(function(k){ byModel[k] = { c10: bm[k].c10, c60: bm[k].c60, pm10: Math.round(bm[k].c10 / 10 * 10) / 10, out10: bm[k].out10, out60: bm[k].out60 || 0, tps: Math.round(bm[k].out10 / 600 * 10) / 10 }; });
    UR_CACHE = { c5: c5, byModel: byModel, c10: c10, c60: c60, pm10: Math.round(c10 / 10 * 10) / 10, pm60: Math.round(c60 / 60 * 10) / 10, byProvider: byProvider, at: now };
    UR_AT = now;
    return UR_CACHE;
  } catch (e) { return UR_CACHE || {}; }
}

function readUsageToday() {
  try {
    const csv = fs.readFileSync(path.join(USAGE_DIR, 'daily.csv'), 'utf8').trim().split('\n');
    const today = new Date(Date.now() + 8 * 3600 * 1000).toISOString().slice(0, 10);
    let userMsgs = 0;
    try { const ut = JSON.parse(fs.readFileSync(path.join(USAGE_DIR, 'user-turns.json'), 'utf8')); userMsgs = ut[today] || 0; } catch {}
    let calls = 0, inp = 0, out = 0, cache = 0, cost = 0, rows = 0;
    const byProvider = {};
    const provOf = (m) => {
      const s0 = String(m || '');
      if (s0.indexOf(':') > 0) return null;                 // 本地 Ollama（形如 qwen3:14b）不计入云端厂商
      if (/^deepseek/i.test(s0)) return 'deepseek';
      if (/^glm/i.test(s0) || /^zai\//i.test(s0)) return 'zhipu';
      if (/^kimi/i.test(s0) || /^k3/i.test(s0)) return 'kimi';
      if (/^minimax/i.test(s0)) return 'minimax';
      if (/^qwen3\.[78]-/i.test(s0)) return 'qianwen';
      return null;
    };
    for (let i = 1; i < csv.length; i++) {
      const c = csv[i].split(',');
      if (c[0] !== today) continue;
      if (c[1] === 'delivery-mirror') continue;
      calls += Number(c[9] || 0); inp += Number(c[2] || 0); out += Number(c[3] || 0);
      cache += Number(c[4] || 0); cost += Number(c[8] != null ? c[8] : c[7] || 0); rows++;
      const pv = provOf(String(c[1] || ''));
      if (pv) {
        const b = byProvider[pv] || (byProvider[pv] = { calls: 0, input: 0, output: 0, cacheRead: 0, cost: 0 });
        b.calls += Number(c[9] || 0); b.input += Number(c[2] || 0); b.output += Number(c[3] || 0);
        b.cacheRead += Number(c[4] || 0); b.cost += Number(c[8] != null ? c[8] : c[7] || 0);
      }
    }
    const st = fs.statSync(path.join(USAGE_DIR, 'daily.csv'));
    Object.keys(byProvider).forEach(k => { byProvider[k].cost = Math.round(byProvider[k].cost * 10000) / 10000; });
    return { date: today, calls, userMsgs, input: inp, output: out, cacheRead: cache, cost: Math.round(cost * 10000) / 10000, models: rows, byProvider, mtime: st.mtimeMs };
  } catch (e) { return null; }
}

function parseRelDate(str){
  if (!str) return null;
  var m = /(\d+)\s*d/i.exec(str); var dd = m ? +m[1] : 0;
  m = /(\d+)\s*h/i.exec(str); var hh = m ? +m[1] : 0;
  m = /(\d+)\s*m/i.exec(str); var mm = m ? +m[1] : 0;
  if (!dd && !hh && !mm) return null;
  var t = new Date(Date.now() + (dd*86400 + hh*3600 + mm*60) * 1000);
  var p = function(n){ return String(n).padStart(2, '0'); };
  return t.getFullYear() + '-' + p(t.getMonth() + 1) + '-' + p(t.getDate());
}

function recordQuotaSnap(p) {
  const NL = String.fromCharCode(10);
  const vals = {
    kimi: (p.kimi && typeof p.kimi.month_used_pct === 'number') ? p.kimi.month_used_pct : null,
    minimax: (p.minimax && typeof p.minimax.weekly_pct === 'number') ? p.minimax.weekly_pct : null,
    zai: (p.zhipu && typeof p.zhipu.week_pct === 'number') ? p.zhipu.week_pct : null
  };
  if (vals.kimi == null && vals.minimax == null) return;
  const now = Date.now();
  const today = new Date(now + 8 * 3600 * 1000).toISOString().slice(0, 10);
  let last = null;
  try {
    const txt = fs.readFileSync(QH_JSON, 'utf8').trim().split(NL).filter(Boolean);
    if (txt.length) last = JSON.parse(txt[txt.length - 1]);
  } catch (e) {}
  if (last && (now - (last.ts || 0)) < 10 * 60 * 1000 && last.kimi === vals.kimi && last.minimax === vals.minimax) return;
  try { fs.appendFileSync(QH_JSON, JSON.stringify(Object.assign({ ts: now, date: today }, vals)) + NL); } catch (e) {}
}

function readQuotaDelta() {
  const NL = String.fromCharCode(10);
  const out = {};
  try {
    const now = Date.now();
    const today = new Date(now + 8 * 3600 * 1000).toISOString().slice(0, 10);
    const rows = fs.readFileSync(QH_JSON, 'utf8').trim().split(NL).filter(Boolean)
      .map(l => { try { return JSON.parse(l); } catch (e) { return null; } }).filter(Boolean);
    if (!rows.length) return out;
    const last = rows[rows.length - 1];
    ['kimi', 'minimax'].forEach(k => {
      if (typeof last[k] !== 'number') return;
      let base = null, baseAt = null;
      for (const r of rows) { if (r.date === today && typeof r[k] === 'number') { base = r[k]; baseAt = r.ts; break; } }
      if (base == null) { for (const r of rows) { if (r.date < today && typeof r[k] === 'number') { base = r[k]; baseAt = r.ts; } } }
      if (base == null) return;
      out[k] = { d: Math.round((last[k] - base) * 100) / 100, base: base, now: last[k], since: baseAt ? new Date(baseAt).toISOString() : null };
    });
  } catch (e) {}
  return out;
}

// v3.9.1 DeepSeek 余额实时取数：直接跑 ds-balance.sh（官方 API），5 分钟缓存
let DS_LIVE_BUSY = false;
async function refreshDeepSeekLive(maxAgeMs = 300000) {
  if (DS_LIVE && Date.now() - DS_LIVE.at < maxAgeMs) return;
  if (DS_LIVE_BUSY) return;
  DS_LIVE_BUSY = true;
  try {
    const out = await new Promise((res, rej) => {
      execFile('sh', [BAL_SH], { timeout: 20000 }, (e, so) => (e ? rej(e) : res(String(so || ''))));
    });
    const m = out.match(/([0-9]+(?:\.[0-9]+)?)/);
    if (m && isFinite(Number(m[1]))) DS_LIVE = { bal: Number(m[1]), at: Date.now() };
  } catch (e) {
    BAL_ERR = 'deepseek live: ' + String(e.message || e).slice(0, 80);
  } finally {
    DS_LIVE_BUSY = false;
  }
}

async function fetchBalances() {
  const now = Date.now();
  if (now - BAL_AT < 60 * 1000) return;

  // v3.9.1 DeepSeek 每次刷新走实时脚本，避免读取过期快照
  try { await refreshDeepSeekLive(5 * 60 * 1000); } catch (e) {}

  // 优先：果果维护的 balances.json（真实口径，含各家积分）
  try {
    const raw = fs.readFileSync(BAL_JSON, 'utf8');
    if (raw && raw.trim()) {
      const j = JSON.parse(raw);
      const p = (j && j.providers) || {};
      let qp = {};
      try { qp = (JSON.parse(fs.readFileSync(QUOTAS, 'utf8')).providers) || {}; } catch (e) {}
      try { recordQuotaSnap(p); } catch (e) {}
      const at = j.updated_at || null;
      const out = [];
      const num = (v) => (typeof v === 'number' && isFinite(v) ? v : null);
      // 谁新用谁：quotas.json 的抓取结果若比 balances.json 更新，就覆盖展示口径
      const qms = (v) => { if (!v) return 0; const t = Date.parse(String(v).replace(' ', 'T') + (String(v).trim().length <= 16 ? ':00+08:00' : '')); return isFinite(t) ? t : 0; };
      const bms = (raw, norm) => {
        const c = norm && norm.captured_at;
        // kind=unavailable 表示那只是「文件生成时间」，不是抓取时间，不能拿来比新旧
        if (c && c.kind === 'unavailable') return 0;
        const a = (c && c.at) || (raw && raw.captured_at) || null;
        return a ? (Date.parse(a) || 0) : 0;
      };
      if (qp.zai && qp.zai.status === 'ok' && qms(qp.zai.captured_at) > bms(p.zhipu, p.zhipu && p.zhipu.norm)) {
        const z = p.zhipu = p.zhipu || {};
        if (qp.zai.weekly_credits_used != null) z.weekly_used = qp.zai.weekly_credits_used;
        if (qp.zai.weekly_credits_limit != null) z.weekly_limit = qp.zai.weekly_credits_limit;
        if (qp.zai.weekly_pct != null) z.weekly_pct = qp.zai.weekly_pct;
        if (qp.zai.window_credits_used != null) z.window_used = qp.zai.window_credits_used;
        if (qp.zai.window_credits_limit != null) z.window_limit = qp.zai.window_credits_limit;
        if (qp.zai.window_pct != null) z.window_pct = qp.zai.window_pct;
        if (qp.zai.weekly_reset_at) z.weekly_reset = qp.zai.weekly_reset_at;
        if (qp.zai.window_reset_at) z.window_reset = qp.zai.window_reset_at;
      }
      if (qp.kimi && qp.kimi.month_pct != null && qms(qp.kimi.captured_at) > bms(p.kimi, p.kimi && p.kimi.norm)) {
        const k = p.kimi = p.kimi || {};
        if (qp.kimi.month_pct != null) k.month_used_pct = qp.kimi.month_pct;
        if (qp.kimi.window_pct != null) k.rate_limit_pct = qp.kimi.window_pct;
        if (qp.kimi.month_reset_at) k.month_reset = qp.kimi.month_reset_at;
        if (qp.kimi.window_reset_at) k.rate_reset = qp.kimi.window_reset_at;
        if (qp.kimi.pack_balance != null) { k.raw_values = k.raw_values || {}; k.raw_values.pack_balance = qp.kimi.pack_balance; }
        if (qp.kimi.plan) k.plan = qp.kimi.plan;
        if (qp.kimi.plan_expire) k.plan_expire = qp.kimi.plan_expire;
      }
      if (qp.minimax && qp.minimax.status === 'ok' && qms(qp.minimax.captured_at) > bms(p.minimax, p.minimax && p.minimax.norm)) {
        const m2 = p.minimax = p.minimax || {};
        if (qp.minimax.window_pct != null) m2.h5_pct = qp.minimax.window_pct;
        if (qp.minimax.weekly_pct != null) m2.week_pct = qp.minimax.weekly_pct;
        if (qp.minimax.plan_expire) m2.plan_expire = qp.minimax.plan_expire;
      }
      if (p.deepseek) {
        const d = p.deepseek;
        const dn = d.norm || {};
        const dsAt = dn.captured_at && dn.captured_at.at ? (Date.parse(dn.captured_at.at) || 0) : 0;
        const liveOk = DS_LIVE && DS_LIVE.at > dsAt;
        const bal = liveOk ? DS_LIVE.bal : num(dn.available != null ? dn.available : (d.available != null ? d.available : d.balance));
        out.push({
          provider: 'DeepSeek', model: 'v4-pro / flash',
          currency: d.currency || 'CNY', unit: '',
          balance: bal,
          spent: num(d.total_spent),
          status: bal == null ? 'na' : (bal <= 0 ? 'over' : 'ok'),
          detail: '',
          capturedAt: liveOk ? new Date(DS_LIVE.at).toISOString() : ((dn.captured_at && dn.captured_at.at) || null),
          title: d.note || '', updatedAt: at
        });
      }
      if (p.zhipu) {
        const z = p.zhipu;
        const wUsed = num(z.weekly_used), wLim = num(z.weekly_limit);
        const wPct = num(z.weekly_pct) != null ? num(z.weekly_pct) : (wUsed != null && wLim ? Math.round(wUsed / wLim * 100) : null);
        const wLeft = (wUsed != null && wLim != null) ? (wLim - wUsed) : null;
        const parts = [];
        if (num(z.window_used) != null && num(z.window_limit)) parts.push('5h ' + z.window_used + '/' + z.window_limit + (num(z.window_pct) != null ? '（' + z.window_pct + '%）' : ''));
        if (wUsed != null && wLim) parts.push('周 ' + wUsed + '/' + wLim + (wPct != null ? '（' + wPct + '%）' : ''));
        if (z.weekly_reset) parts.push('周重置 ' + String(z.weekly_reset).slice(5));
        out.push({
          capturedAt: (qp.zai && qp.zai.captured_at) || z.captured_at || null,
          provider: '智谱 GLM', model: 'Coding Lite 季卡',
          unit: '%可用',
          balance: wPct != null ? Math.max(0, 100 - wPct) : (wLeft != null && wLim ? Math.round(wLeft / wLim * 1000) / 10 : null),
          status: 'ok',
          detail: parts.join(' · '),
          expires: (z.plan_expire || (function(){ var mm = /有效期至\s*([0-9]{4}-[0-9]{2}-[0-9]{2})/.exec(z.plan || ''); return mm ? mm[1] : null; })()), expiresConfident: (z.plan_expire_confident !== false),
          title: (z.plan ? z.plan + '｜' : '') + (z.note || ''), updatedAt: at
        });
      }
      if (p.kimi) {
        const k = p.kimi;
        const mp = num(k.month_used_pct), rp = num(k.rate_limit_pct);
        const parts = [];
        if (rp != null) parts.push('频限 ' + rp + '%');
        const fmtRst = (v) => { const t = String(v).replace(/^约\s*/, ''); return /^\d{4}-/.test(t) ? t.slice(0, 10) : t.slice(0, 11); };
        if (k.rate_reset) parts.push('5h重置 ' + fmtRst(k.rate_reset));
        if (k.month_reset) parts.push('月重置 ' + fmtRst(k.month_reset));
        // 2026-10-28：月卡口径 —— 面板显示「可用额度」，加油包只作附注（钱包已停 key，不参与主值）
        var packBal = (k.raw_values && k.raw_values.pack_balance != null) ? Number(k.raw_values.pack_balance) : null;
        var wallet = (packBal != null) ? packBal : num(k.topup_balance);
        if (wallet != null) parts.push('加油包 ¥' + wallet.toFixed(2));
        const availPct = (mp != null) ? Math.max(0, 100 - mp) : null;
        out.push({
          capturedAt: (qp.kimi && qp.kimi.captured_at) || at,
          provider: 'Kimi', model: k.plan || 'Kimi Plus',
          unit: '%可用',
          balance: availPct,
          status: availPct != null ? 'ok' : 'na',
          detail: parts.join(' · '),
          expires: (k.plan_expire || null), expiresConfident: (k.plan_expire_confident === true),
          title: k.note || '', updatedAt: at
        });
      }
      if (p.minimax) {
        const m = p.minimax;
        const wallet = num(m.available != null ? m.available : m.wallet_available);
        const wPct = num(m.window_pct), dPct = num(m.weekly_pct);
        const planMode = (wPct != null || dPct != null);
        const parts = [];
        if (wPct != null) parts.push('5h ' + wPct + '%');
        if (dPct != null) parts.push('周 ' + dPct + '%');
        if (wallet != null) parts.push('钱包 ¥' + Number(wallet).toFixed(2));
        if (m.topup_credits) parts.push(m.topup_credits);

        out.push({
          capturedAt: (qp.minimax && qp.minimax.captured_at) || at,
          provider: 'MiniMax', model: m.plan || '钱包',
          currency: m.currency || 'CNY',
          unit: planMode ? '%可用' : '',
          balance: planMode ? (dPct != null ? Math.max(0, 100 - dPct) : (wPct != null ? Math.max(0, 100 - wPct) : null)) : wallet,
          status: planMode ? 'ok' : (wallet == null ? 'na' : (wallet <= 0 ? 'empty' : 'ok')),
          detail: parts.join(' · ') + (m.auto_renew === false ? ' · 自动续费已关闭' : ''),
          expires: m.plan_expire || null, expiresConfident: (m.plan_expire_confident !== false),
          autoRenew: (m.auto_renew === false ? false : null),
          title: m.note || '', updatedAt: at
        });
      }
      if (out.length >= 1) { BAL = addExtras(out); BAL_ERR = null; BAL_AT = Date.now(); return; }
    }
  } catch (e) { /* file absent: fall through */ }


  const out = [];

  // 1) DeepSeek — 用果果提供的 ds-balance.sh（自动解析网关现役 key）
  try {
    const txt = await new Promise((res, rej) => {
      execFile('sh', [BAL_SH], { timeout: 25000 }, (e, so) => (e ? rej(e) : res(String(so || ''))));
    });
    const line = (txt.trim().split('\n').pop() || '').trim();
    const m = line.match(/([\u00a5$])\s?(-?[\d.]+)/);
    const sym = m ? m[1] : '\u00a5';
    const usable = /可用/.test(line) && !/不可用|欠费/.test(line);
    out.push({
      provider: 'DeepSeek', model: 'v4-pro / flash',
      currency: sym === '\u00a5' ? 'CNY' : 'USD',
      balance: m ? Number(m[2]) : null,
      status: usable ? 'ok' : 'over',
      detail: line.slice(0, 40), source: 'ds-balance.sh'
    });
  } catch (e) {
    out.push({ provider: 'DeepSeek', model: 'v4-pro / flash', status: 'error', detail: String(e.message || e).slice(0, 40) });
  }

  // 2) 智谱 GLM — 仅本地页面快照（可能过期）
  try {
    const q = JSON.parse(fs.readFileSync(QUOTAS, 'utf8'));
    const z = (q.providers && q.providers.zai) || null;
    if (z) {
      out.push({
        provider: '智谱 GLM', model: (z.label || 'Coding 季卡'),
        currency: '', balance: (z.weekly_pct != null ? z.weekly_pct : null), status: 'snapshot',
        detail: '周额度 · 窗口 ' + (z.window_pct != null ? z.window_pct + '%' : '—') +
                ' · 快照 ' + (z.captured_at || '—'),
        capturedAt: z.captured_at || null, source: z.url || 'page'
      });
    }
  } catch (e) {}

  // 3) 订阅制 / 无公开接口
  out.push({ provider: 'Kimi', model: 'coding 月卡', status: 'na', detail: '订阅制 · 无余额接口' });
  out.push({ provider: 'MiniMax', model: '', status: 'na', detail: '无公开余额接口' });

  BAL = addExtras(out); BAL_AT = now; BAL_ERR = null;
}

async function refreshAll() {
  fetchBalances().catch(() => {});
  Promise.resolve(refreshHost(25000)).catch(function(){});
  Promise.resolve(refreshWeather(600000)).catch(function(){});
  Promise.resolve(refreshStocks(60000)).catch(function(){});
  Promise.resolve(refreshFx(60000)).catch(function(){});
  await Promise.all([
    refresh('cron', ['cron', 'list', '--json'], 12000),
    refresh('sess', ['sessions', '--json', '--all-agents', '--limit', '300'], 20000),
    refresh('status', ['status', '--json'], 20000),
    refresh('agents', ['agents', 'list', '--json'], 300000)
  ]);
}

const LEDGER_FILE = '/home/j/.openclaw/workspace/state/tasks/tasks.json';
const LEDGER_DB = '/home/j/.openclaw/workspace/state/tasks/tasks.db';
let LEDGER = null, LEDGER_MT = 0;
function loadLedger() {
  try {
    if (fs.existsSync(LEDGER_DB)) {
      const dst = fs.statSync(LEDGER_DB);
      let jst = null;
      try { jst = fs.statSync(LEDGER_FILE); } catch (e) {}
      if (!jst || dst.mtimeMs >= jst.mtimeMs) {
      if (LEDGER && LEDGER.src === 'db' && dst.mtimeMs === LEDGER_MT) return;
      try {
        const { DatabaseSync } = require('node:sqlite');
        const db = new DatabaseSync(LEDGER_DB, { readOnly: true });
        const rows = db.prepare('SELECT no,title,status,prio,grp,kind,notes,updated,wait_user,due_plan,eta_min,slip_reason FROM tasks').all();
        db.close();
        const items = rows.map(x => ({
          no: x.no, id: x.no, title: x.title, status: x.status, kind: x.kind || '', notes: x.notes || '', wait_user: x.wait_user ? 1 : 0, due_plan: x.due_plan || '', eta_min: x.eta_min || 0, slip_reason: x.slip_reason || '',
          priority: x.prio || '', source: x.grp || x.kind || '', notes: x.notes || '', due: '', updated: x.updated || ''
        }));
        const counts = items.reduce((m, x) => { m[x.status] = (m[x.status] || 0) + 1; return m; }, {});
        const latest = items.reduce((a, x) => (x.updated && x.updated > a ? x.updated : a), '');
        LEDGER = { updated: latest, items, counts, total: items.length, src: 'db' };
        LEDGER_MT = dst.mtimeMs;
        return;
      } catch (e) {}
      }
    }
    const st = fs.statSync(LEDGER_FILE);
    if (LEDGER && st.mtimeMs === LEDGER_MT) return;
    const j = JSON.parse(fs.readFileSync(LEDGER_FILE, 'utf8'));
    const items = (j.items || []).map(x => ({
      no: x.no, id: x.id, title: x.title, status: x.status, kind: x.kind || '', notes: x.notes || '', wait_user: x.wait_user ? 1 : 0, due_plan: x.due_plan || '', eta_min: x.eta_min || 0, slip_reason: x.slip_reason || '',
      priority: x.priority || '', source: x.source || '', due: x.due || '', due_plan: x.due_plan || '', eta_min: x.eta_min || 0, slip_reason: x.slip_reason || '', wait_user: x.wait_user || 0, updated: x.updated || ''
    }));
    const counts = items.reduce((m, x) => { m[x.status] = (m[x.status] || 0) + 1; return m; }, {});
    LEDGER = { updated: j.updated || '', items, counts, total: items.length };
    LEDGER_MT = st.mtimeMs;
  } catch (e) { /* keep previous */ }
}

function refreshLedgerNow() {
  LEDGER = null; LEDGER_MT = 0;
  loadLedger();
  return LEDGER
    ? { ok: true, total: LEDGER.total, updated: LEDGER.updated, at: Date.now() }
    : { ok: false, at: Date.now() };
}

const DATA_DIR = path.join(__dirname, 'data');
const TODO_FILE = path.join(DATA_DIR, 'todos.json');
function loadTodos() {
  try { return JSON.parse(fs.readFileSync(TODO_FILE, 'utf8')); } catch { return []; }
}
function saveTodos(list) {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    const tmp = TODO_FILE + '.tmp';
    fs.writeFileSync(tmp, JSON.stringify(list, null, 1));
    fs.renameSync(tmp, TODO_FILE);
    return true;
  } catch { return false; }
}
let TODOS = loadTodos();

function handleTodo(body, res) {
  const act = body && body.action;
  let changed = false;
  if (act === 'add') {
    const text = String(body.text || '').trim().slice(0, 200);
    if (text) {
      TODOS.unshift({ id: 't' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), text, done: false, createdAt: Date.now(), dueAt: body.dueAt || null, source: 'local' });
      changed = true;
    }
  } else if (act === 'toggle') {
    const it = TODOS.find(x => x.id === body.id);
    if (it) { it.done = !it.done; it.doneAt = it.done ? Date.now() : null; changed = true; }
  } else if (act === 'del') {
    const n = TODOS.length; TODOS = TODOS.filter(x => x.id !== body.id); changed = TODOS.length !== n;
  } else if (act === 'clearDone') {
    const n = TODOS.length; TODOS = TODOS.filter(x => !x.done); changed = TODOS.length !== n;
  } else if (act === 'import') {
    const arr = Array.isArray(body.items) ? body.items : [];
    for (const t of arr) {
      const text = String(t.text || '').trim();
      if (!text) continue;
      if (TODOS.some(x => x.source === (t.source || 'wecom') && x.extId === t.extId)) continue;
      TODOS.push({ id: 't' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6), text, done: !!t.done, createdAt: t.createdAt || Date.now(), dueAt: t.dueAt || null, source: t.source || 'wecom', extId: t.extId || null });
      changed = true;
    }
  }
  if (changed) saveTodos(TODOS);
  res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify({ ok: changed, todos: TODOS }));
}

function readVersion() {
  try { return fs.readFileSync(path.join(__dirname, 'VERSION'), 'utf8').trim() || '?'; } catch { return '?'; }
}

function buildId() {
  try {
    const st = fs.statSync(path.join(__dirname, 'public', 'index.html'));
    return String(Math.round(st.mtimeMs)) + '-' + st.size;
  } catch { return '0'; }
}

const MIME = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml' };

// ---- 最新可升级版本（npm registry，6h 一次）----
const LATEST_V = { version: null, at: null, err: null };
async function pollLatestVer() {
  try {
    const urls = ['https://registry.npmmirror.com/openclaw/latest', 'https://registry.npmjs.org/openclaw/latest'];
    let j = null, lastErr = '';
    for (const u of urls) {
      try {
        const r = await fetch(u, { signal: AbortSignal.timeout(8000), headers: { 'accept': 'application/json' } });
        const t = await r.json();
        if (t && t.version) { j = t; break; }
        lastErr = u + ' no version';
      } catch (e) { lastErr = u + ' ' + String((e && e.message) || e).slice(0, 80); }
    }
    if (j) { LATEST_V.version = String(j.version); LATEST_V.at = Date.now(); LATEST_V.err = null; }
    else LATEST_V.err = lastErr || 'unknown';
  } catch (e) { LATEST_V.err = String((e && e.message) || e).slice(0, 120); }
}
pollLatestVer();
setInterval(pollLatestVer, 6 * 3600 * 1000);


// ===== 运维（原「果果助手」功能并入信息窗）=====
const CONSOLE_SH = '/home/j/openclaw-workspaces/work/果果助手/tools/console-cmd.sh';

// v3.9.4 PowerShell / CMD 面板改为一次性执行（tmux + powershell.exe 在 WSL PTY 下无法正常渲染，
// 表现为卡在 >> 续行、屏幕空白）。输出按会话缓存，out 直接回放文本。
const TERM_HIST = { '1': [], '3': [] };
const TERM_DECODE = (buf) => {
  if (!buf || !buf.length) return '';
  const b = Buffer.isBuffer(buf) ? buf : Buffer.from(String(buf));
  let nul = 0;
  const lim = Math.min(b.length, 4000);
  for (let i = 0; i < lim; i++) if (b[i] === 0) nul++;
  if (nul > lim / 8) return b.toString('utf16le').replace(/\uFEFF/g, '');
  return b.toString('utf8');
};
const TERM_ONESHOT = (idx, cmd, cb) => {
  const exe = idx === '1'
    ? '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    : '/mnt/c/Windows/System32/cmd.exe';
  const args = idx === '1'
    ? ['-NoLogo', '-NoProfile', '-NonInteractive', '-Command', '[Console]::OutputEncoding=[Text.Encoding]::UTF8; ' + cmd]
    : ['/d', '/s', '/c', 'chcp 65001>nul & ' + cmd];
  const t0 = Date.now();
  execFile(exe, args, { timeout: 25000, maxBuffer: 4e6, encoding: 'buffer', windowsHide: true }, (err, so, se) => {
    const out = TERM_DECODE(so);
    const errTxt = TERM_DECODE(se);
    let body = out;
    if (errTxt && errTxt.trim()) body += (body ? String.fromCharCode(10) : '') + errTxt;
    if (err && err.killed) body += String.fromCharCode(10) + '[超时/被终止]';
    if (!body.trim() && err) body = '[错误] ' + (err.message || '');
    if (!body.trim()) body = '[无输出]';
    cb({ body: body.replace(/[ \t]+$/gm, ''), ms: Date.now() - t0 });
  });
};
let NODES_CACHE = null; // 双机状态缓存
let GW_VER_CACHE = ''; // 网关版本缓存
const OPENCLAW_BIN = '/home/j/.npm-global/bin/openclaw';
let HEALTH_HIST = [];      // [{t, a:{memPct,swapPct,load,diskPct}, b:{on,seen}, ok}]
let HEALTH_LAST_OC = null; // 最近一次 openclaw health --json
const HEALTH_FILE = path.join(__dirname, 'data', 'health-history.json');
try { HEALTH_HIST = (JSON.parse(fs.readFileSync(HEALTH_FILE, 'utf8')) || {}).hist || []; } catch (e) { HEALTH_HIST = []; }
function healthSample(){
  const t = Date.now();
  const a = {};
  try { const mi = fs.readFileSync('/proc/meminfo', 'utf8'); const g = (n) => { const m = new RegExp(n + ':\\s+(\\d+) kB').exec(mi); return m ? Number(m[1]) * 1024 : 0; }; const mt = g('MemTotal'), ma = g('MemAvailable'), st = g('SwapTotal'), sf = g('SwapFree'); a.memPct = mt ? Math.round(100 * (1 - ma / mt)) : 0; a.swapPct = st ? Math.round(100 * (1 - sf / st)) : 0; } catch (e) {}
  try { a.load = Number(fs.readFileSync('/proc/loadavg', 'utf8').split(' ')[0]) || 0; } catch (e) {}
  try { const st = fs.statfsSync('/'); const tot = st.blocks * st.bsize, av = st.bavail * st.bsize; a.diskPct = tot ? Math.round(100 * (1 - av / tot)) : 0; } catch (e) {}
  execFile(OPENCLAW_BIN, ['health', '--json', '--timeout', '8000'], { timeout: 12000 }, (e2, so2) => {
    let ok = false;
    try { HEALTH_LAST_OC = JSON.parse(so2); ok = !!(HEALTH_LAST_OC && HEALTH_LAST_OC.ok); } catch (err) { HEALTH_LAST_OC = null; }
    execFile(OPENCLAW_BIN, ['nodes', 'status', '--json', '--timeout', '8000'], { timeout: 12000 }, (e, so) => {
      const b = { on: false, seen: 0 };
      try {
        const ns = (JSON.parse(so) || {}).nodes || [];
        if (ns[0]) { b.on = !!ns[0].connected; b.seen = ns[0].connected ? t : (ns[0].lastSeenAtMs || ns[0].lastConnectedAtMs || 0);
          const prevSelf = (NODES_CACHE && NODES_CACHE.data && NODES_CACHE.data.self) || {};
          NODES_CACHE = { t: Date.now(), data: { ok: !e, ts: Date.now(), nodes: ns, self: prevSelf } };
        }
      } catch (err) {}
      HEALTH_HIST.push({ t, a, b, ok });
      const cut = Date.now() - 24 * 3600 * 1000;
      HEALTH_HIST = HEALTH_HIST.filter(x => x.t >= cut).slice(-1440);
      try { fs.writeFile(HEALTH_FILE + '.tmp', JSON.stringify({ hist: HEALTH_HIST }), () => { try { fs.renameSync(HEALTH_FILE + '.tmp', HEALTH_FILE); } catch (er) {} }); } catch (er) {}
    });
  });
}
healthSample();
setInterval(healthSample, 60000);
const OPS_SPEC = {
  'oc-status':      { label: 'OC总览',    arg: 'oc-status',      ms: 60000  },
  'oc-health':      { label: 'OC健康',    arg: 'oc-health',      ms: 30000  },
  'oc-channels':    { label: 'OC渠道',    arg: 'oc-channels',    ms: 30000  },
  'oc-usage-table': { label: '会话用量',  arg: 'oc-usage-table', ms: 120000 },
  'oc-today':       { label: '今日token', arg: 'oc-today',       ms: 150000 },
  'oc-doctor':      { label: 'OC体检',    arg: 'oc-doctor',      ms: 240000 },
  'oc-doctor-fix':  { label: 'OC体检修复', arg: 'oc-doctor-fix',  ms: 240000 , confirm: true},
  selfcheck: { label: '一键自检',  arg: 'selfcheck',  ms: 90000  },
  status:    { label: '网关状态',  arg: 'status',     ms: 30000  },
  services:  { label: '服务状态',  arg: 'services',   ms: 30000  },
  diag:      { label: '深度诊断',  arg: 'diag',       ms: 180000 },
  backups:   { label: '备份清单',  arg: 'backups',    ms: 90000  },
  logs:      { label: '最近日志',  arg: 'logs',       ms: 60000  },
  quota:     { label: '额度余额',  arg: 'quota',      ms: 90000  },
  brief:     { label: '今日简报',  arg: 'brief',      ms: 180000 },
  restart:   { label: '重启网关',  arg: 'restart',    ms: 150000, confirm: true },
  stop:      { label: '维护停机(网关+看门狗)', arg: 'stop', ms: 120000, confirm: true },
  'start-gw': { label: '启动网关', arg: 'start-gw', ms: 150000 },
  overview:  { label: '状态总览',  arg: 'overview',   ms: 150000 },
  checkup:   { label: '体检',      arg: 'checkup',    ms: 300000 },
  repair:    { label: '修复',      arg: 'repair',     ms: 300000, confirm: true },
  usage:     { label: '用量',      arg: 'usage',      ms: 180000 },
  fix:       { label: '修复系统',  arg: 'fix',        ms: 420000, confirm: true },
  backup:    { label: '本地备份',  arg: 'backup-now', ms: 5400000, confirm: true },
  'push-backup': { label: '推送备份', arg: 'push-backup', ms: 3600000, confirm: true },
  rescue:    { label: '一键自救',  script: '/home/j/openclaw-workspaces/work/果果助手/tools/rescue-v2.sh', ms: 180000, confirm: true },
  upgrade:   { label: '一键升级',  arg: 'upgrade',    ms: 1800000, confirm: true },
  cfgroll:   { label: '配置回滚点', arg: 'cfgroll',   ms: 60000  },
  clean:     { label: '清理预演',  arg: 'clean-dry',  ms: 180000 },
  digest:    { label: '崩溃摘要',  script: '/home/j/openclaw-workspaces/work/果果助手/tools/crash-digest.sh', ms: 90000 },
  vhdx:           { label: 'X盘占用',   script: '/home/j/.openclaw/workspace/tools/vhdx-status.sh', ms: 60000 },
  "vhdx-compact": { label: '压缩镜像',  script: '/home/j/.openclaw/workspace/tools/win-launch.sh', args: ['compact'], ms: 20000, confirm: true },
  "vhdx-sparse":  { label: '开启稀疏',  script: '/home/j/.openclaw/workspace/tools/win-launch.sh', args: ['sparse'], ms: 20000 },
  "vhdx-fstrim":  { label: 'fstrim释放',script: '/home/j/.openclaw/workspace/tools/win-launch.sh', args: ['fstrim'], ms: 20000 },
  "vhdx-cfg":     { label: 'WSL配置检查',script: '/home/j/.openclaw/workspace/tools/win-launch.sh', args: ['cfgcheck'], ms: 20000 }
};
let OPS_BUSY = null;
let OPS_LAST = null;

// v3.9.3 运维台局域网登录地址：读取 Windows 宿主 LAN IPv4（缓存 10 分钟）
let LAN_CACHE = { at: 0, ip: '' };
function detectLanIp() {
  const now = Date.now();
  if (now - LAN_CACHE.at < 60000) return LAN_CACHE.ip;
  let ip = '';
  try {
    const pwsh = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe';
    const cmd = "[Console]::Out.Write((Get-NetIPAddress -AddressFamily IPv4 | Select-Object -ExpandProperty IPAddress) -join ',')";
    const raw = require('child_process').execFileSync(pwsh, ['-NoProfile','-NonInteractive','-Command', cmd], { timeout: 9000, encoding: 'buffer' });
    const txt = Buffer.from(raw).toString('latin1').replace(/\0/g, '');
    const cands = (txt.match(/(?:\d{1,3}\.){3}\d{1,3}/g) || []);
    for (const c of cands) {
      if (c.startsWith('169.254.') || c.startsWith('127.') || c.startsWith('172.18.') || c.startsWith('172.17.')) continue;
      if (/^192\.168\./.test(c) || /^10\./.test(c) || /^172\.(1[6-9]|2[0-9]|3[01])\./.test(c)) { ip = c; break; }
    }
  } catch (e) {}
  if (!ip) {
    try {
      const n = require('os').networkInterfaces();
      for (const k of Object.keys(n)) for (const a of (n[k]||[])) {
        if (a.family === 'IPv4' && !a.internal && !a.address.startsWith('172.18.') && !a.address.startsWith('172.17.')) { ip = a.address; break; }
      }
    } catch (e) {}
  }
  LAN_CACHE = { at: now, ip };
  return ip;
}

function ipAllowed(raw) {
  let ip = String(raw || '').replace(/^::ffff:/, '');
  if (!ip) return false;
  if (ip === '::1' || ip === '127.0.0.1') return true;
  if (ip.startsWith('127.')) return true;
  const m = ip.match(/^(\d+)\.(\d+)\./);
  if (m) { const a = +m[1], b = +m[2]; if (a === 172 && b >= 16 && b <= 31) return true; }
  const extra = String(process.env.INFOWIN_ALLOW_IPS || '').split(',').map(x => x.trim()).filter(Boolean);
  return extra.includes(ip);
}

const HERMES = require('./lib/hermes')(runCli);

function renderGv() {
  var WORD = { ok: '正常', warn: '需注意', bad: '异常', unknown: '未采集' };
  var COLOR = { ok: '#35c97a', warn: '#f2b73d', bad: '#f2545b', unknown: '#7a8494' };
  var ORDER = ['服务', '任务', '资金', '存储', '安防', '模型'];
  var d = null;
  try { d = JSON.parse(fs.readFileSync('/home/j/.openclaw/workspace/state/overview/health.json', 'utf8')); } catch (e) { d = null; }
  if (!d) return '<span class="gvt-ts">上帝视角：未采集</span>';
  var s = d.summary || {};
  var vc = COLOR[s.verdict] || COLOR.unknown;
  var vw = s.verdict === 'ok' ? '全部正常' : (s.verdict === 'warn' ? '需注意' : '异常');
  var h = '';
  for (var i = 0; i < ORDER.length; i++) {
    var n = ORDER[i], x = (d.domains || {})[n];
    if (!x) continue;
    var lv = x.level || 'unknown';
    h += '<i title="' + String(x.source || '').replace(/"/g, '&quot;') + '"><span class="dt" style="background:' +
      (COLOR[lv] || COLOR.unknown) + '"></span>' + n + ' ' + String(x.headline || WORD[lv] || '') + '</i>';
  }
  return '<a class="gvt" href="/overview.html" target="_blank" title="打开上帝视角全屏页">上帝视角 <span class="gvv" style="color:' +
    vc + '">' + vw + '</span> ↗</a><div class="gvd">' + h + '</div><span class="gvt-ts">采集 ' +
    String(d.generated_at || '-') + '</span>';
}

const server = http.createServer(async (req, res) => {
  if (!ipAllowed(req.socket && req.socket.remoteAddress)) {
    const who = (req.socket && req.socket.remoteAddress) || '?';
    try { fs.appendFileSync('/home/j/.openclaw/workspace/state/desktop-console/panel-deny.log', new Date().toISOString() + ' deny ' + who + ' ' + req.url + '\n'); } catch (e) {}
    res.writeHead(403, { 'content-type': 'text/plain; charset=utf-8' }); res.end('403 仅限本机/WSL 内部访问\n'); return;
  }
  const url = new URL(req.url, 'http://x');
  if (url.pathname === '/api/lanip') {
    const ip = detectLanIp();
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    res.end(JSON.stringify({ ip: ip || '', port: PORT, url: ip ? ('http://' + ip + ':' + PORT + '/') : '' }));
    return;
  }
  if (url.pathname === '/api/oc-detect') {
    const hdr = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' };
    const cfgPath = process.env.OPENCLAW_CONFIG_PATH || path.join(process.env.HOME || '', '.openclaw', 'openclaw.json');
    let cfg = {}, cfgErr = null;
    try { cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8')); } catch (e) { cfgErr = String(e.message || e).slice(0, 160); }
    const gw = cfg.gateway || {};
    const port = Number(process.env.OPENCLAW_GATEWAY_PORT || gw.port || 18789);
    const mode = gw.mode || (fs.existsSync(cfgPath) ? 'unknown' : 'remote?');
    const bind = gw.bind || '—';
    const authMode = (gw.auth && gw.auth.mode) || 'none';
    const tokenRef = gw.auth && gw.auth.token ? (gw.auth.token.id || gw.auth.token.source || '') : '';
    let version = '';
    try { version = String(require('child_process').execFileSync(CLI, ['--version'], { timeout: 8000, encoding: 'utf8' })).trim().split(String.fromCharCode(10))[0].slice(0, 60); } catch (e) {}
    const health = await new Promise((resolve) => {
      const t0 = Date.now();
      const rq = http.get({ host: '127.0.0.1', port, path: '/health', timeout: 2500 }, (rs) => {
        rs.resume();
        rs.on('end', () => resolve({ s: rs.statusCode === 200 ? 'ok' : ('http ' + rs.statusCode), ms: Date.now() - t0 }));
      });
      rq.on('error', () => resolve({ s: 'down', ms: Date.now() - t0 }));
      rq.on('timeout', () => { try { rq.destroy(); } catch (e) {} resolve({ s: 'timeout', ms: Date.now() - t0 }); });
    });
    res.writeHead(200, hdr);
    res.end(JSON.stringify({ ok: !cfgErr, configPath: cfgPath, configError: cfgErr, mode, port, bind, authMode, tokenRef, cli: CLI, version, health: health.s, healthMs: health.ms, hostHome: process.env.HOME || '' }));
    return;
  }
  if (url.pathname === '/api/hermes') {
    const force = url.searchParams.get('refresh') === '1';
    const data = await HERMES.get(force);
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    res.end(JSON.stringify(data));
    return;
  }
  if (url.pathname === '/api/errors') {
    try {
      const snap = ERR_REPORT.snapshot();
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
      res.end(JSON.stringify(snap));
    } catch (e) {
      console.error('[errors] snapshot failed', e && e.stack || e);
      res.writeHead(500, { 'content-type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify({ ok: false, error: String(e && e.message || e) }));
    }
    return;
  }
  if (url.pathname === '/api/errors/report') {
    const er = await ERR_REPORT.report(true);
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    res.end(JSON.stringify(er));
    return;
  }
  if (url.pathname === '/api/open') {
    const target = String(url.searchParams.get('u') || '');
    const allow = /^https?:\/\/(127\.0\.0\.1|localhost|(?:\d{1,3}\.){3}\d{1,3})(:\d+)?(\/|$)/.test(target);
    const hdr = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' };
    if (!allow) { res.writeHead(400, hdr); res.end(JSON.stringify({ ok: false, error: 'url not allowed' })); return; }
    const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
    try {
      execFile(PS, ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
        "Start-Process -FilePath '" + CHROME + "' -ArgumentList '" + target.replace(/'/g, '') + "'"]);
    } catch (e) {}
    res.writeHead(200, hdr); res.end(JSON.stringify({ ok: true, url: target }));
    return;
  }
  // ===== 面板内置终端：tmux 会话 ocpanel =====
  if (url.pathname.indexOf('/api/term/') === 0) {
    const hdr = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' };
    const act = url.pathname.slice('/api/term/'.length);
    const sn = String(url.searchParams.get('s') || '1');
    const SESS = 'ocpanel' + (['1', '2', '3'].indexOf(sn) >= 0 ? sn : '1');
    const sh = (c, cb) => execFile('bash', ['-lc', c], { timeout: 8000, maxBuffer: 2e6 }, cb);
    const WCMD = { '1': '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoLogo -NoProfile', '2': 'bash -l', '3': '/mnt/c/Windows/System32/cmd.exe' };
    const sessIdx = SESS.slice(-1);
    if (sessIdx === '1' || sessIdx === '3') {
      const hdr2 = hdr;
      if (act === 'out') {
        const t = (TERM_HIST[sessIdx] || []).join(String.fromCharCode(10));
        res.writeHead(200, hdr2); res.end(JSON.stringify({ ok: true, text: t.slice(-12000) })); return;
      }
      if (act === 'run') {
        const cmd = String(url.searchParams.get('c') || '');
        if (!cmd.trim() || cmd.length > 1200 || /\n/.test(cmd)) {
          res.writeHead(400, hdr2); res.end(JSON.stringify({ ok: false, error: 'bad cmd' })); return;
        }
        try { fs.appendFileSync('/home/j/.openclaw/workspace/state/work/term-cmd.log', new Date().toISOString() + ' [' + sessIdx + '] ' + cmd + String.fromCharCode(10)); } catch (e) {}
        const hist = TERM_HIST[sessIdx] || (TERM_HIST[sessIdx] = []);
        hist.push('>>> ' + cmd);
        TERM_ONESHOT(sessIdx, cmd, (r) => {
          hist.push(r.body);
          hist.push('[耗时 ' + r.ms + ' ms]');
          while (hist.length > 400) hist.shift();
          res.writeHead(200, hdr2); res.end(JSON.stringify({ ok: true, ms: r.ms }));
        });
        return;
      }
      if (act === 'reset') {
        TERM_HIST[sessIdx] = [];
        res.writeHead(200, hdr2); res.end(JSON.stringify({ ok: true })); return;
      }
      if (act === 'key') { res.writeHead(200, hdr2); res.end(JSON.stringify({ ok: true })); return; }
      res.writeHead(200, hdr2); res.end(JSON.stringify({ ok: true })); return;
    }
    const ensure = (cb) => sh('tmux has-session -t ' + SESS + ' 2>/dev/null || tmux new-session -d -s ' + SESS + ' -x 200 -y 45 ' + (WCMD[sessIdx] || 'bash -l'), () => cb());
    if (act === 'out') {
      sh('tmux capture-pane -pt ' + SESS + ' -S -200 2>/dev/null', (e, out) => {
        const txt = String(out || '').replace(/[ \t]+$/gm, '').replace(/\n{3,}/g, '\n\n');
        res.writeHead(200, hdr); res.end(JSON.stringify({ ok: true, text: txt.slice(-8000) }));
      });
      return;
    }
    if (act === 'run') {
      const cmd = String(url.searchParams.get('c') || '');
      if (!cmd.trim() || cmd.length > 1200 || /\n/.test(cmd)) { res.writeHead(400, hdr); res.end(JSON.stringify({ ok: false, error: 'bad cmd' })); return; }
      try { fs.appendFileSync('/home/j/.openclaw/workspace/state/work/term-cmd.log', new Date().toISOString() + ' ' + cmd + String.fromCharCode(10)); } catch (e) {}
      const doSend = (recovered) => {
        execFile('tmux', ['send-keys', '-t', SESS, '-l', '--', cmd], { timeout: 5000 }, () => {
          execFile('tmux', ['send-keys', '-t', SESS, 'Enter'], { timeout: 5000 }, () => {
            res.writeHead(200, hdr); res.end(JSON.stringify({ ok: true, recovered: !!recovered }));
          });
        });
      };
      ensure(() => {
        sh('tmux capture-pane -pt ' + SESS + ' -S -15 2>/dev/null', (e, prev) => {
          const tail = String(prev || '').split(String.fromCharCode(10)).filter((x) => x.trim()).slice(-1)[0] || '';
          const t2 = tail.trim();
          const stuck = t2.indexOf('>>') === 0 || t2 === '>' || t2 === '...' || /[|\\]$/.test(t2);
          if (stuck) {
            execFile('tmux', ['send-keys', '-t', SESS, 'C-c'], { timeout: 4000 }, () => {
              setTimeout(() => doSend(true), 180);
            });
          } else { doSend(false); }
        });
      });
      return;
    }
    if (act === 'secret') {
      const v = String(url.searchParams.get('c') || '');
      if (!v || v.length > 400 || /\n/.test(v)) { res.writeHead(400, hdr); res.end(JSON.stringify({ ok: false })); return; }
      try { fs.appendFileSync('/home/j/.openclaw/workspace/state/work/term-cmd.log', new Date().toISOString() + ' <secret input hidden>' + String.fromCharCode(10)); } catch (e) {}
      ensure(() => {
        execFile('tmux', ['send-keys', '-t', SESS, '-l', '--', v], { timeout: 5000 }, () => {
          execFile('tmux', ['send-keys', '-t', SESS, 'Enter'], { timeout: 5000 }, () => {
            res.writeHead(200, hdr); res.end(JSON.stringify({ ok: true }));
          });
        });
      });
      return;
    }
    if (act === 'key') {
      const k = String(url.searchParams.get('k') || '');
      const allow = { 'C-c': 'C-c', 'C-d': 'C-d', 'Enter': 'Enter', 'Tab': 'Tab', 'Up': 'Up', 'Down': 'Down', 'BSpace': 'BSpace' };
      if (!allow[k]) { res.writeHead(400, hdr); res.end(JSON.stringify({ ok: false })); return; }
      ensure(() => {
        execFile('tmux', ['send-keys', '-t', SESS, allow[k]], { timeout: 5000 }, () => {
          res.writeHead(200, hdr); res.end(JSON.stringify({ ok: true }));
        });
      });
      return;
    }
    if (act === 'reset') {
      sh('tmux kill-session -t ' + SESS + ' 2>/dev/null; sleep 0.3', () => ensure(() => {
        res.writeHead(200, hdr); res.end(JSON.stringify({ ok: true }));
      }));
      return;
    }
    res.writeHead(404, hdr); res.end(JSON.stringify({ ok: false }));
    return;
  }

  // ===== 双机状态：B机 nodes status --json + A机本机指标（缓存60s） =====
  if (url.pathname === '/api/nodes') {
    const nhdr = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' };
    if (NODES_CACHE && NODES_CACHE.data && Date.now() - NODES_CACHE.t < 60000) {
      res.writeHead(200, nhdr); res.end(JSON.stringify(NODES_CACHE.data)); return;
    }
    const osMod = require('os');
    const self = { hostname: osMod.hostname(), platform: 'linux(WSL2)', version: GW_VER_CACHE || '', ip: null,
      memTotalBytes: 0, memFreeBytes: 0, diskTotalBytes: 0, diskAvailableBytes: 0, uptimeS: Math.floor(osMod.uptime()) };
    try { const ni = osMod.networkInterfaces(); outer: for (const k of Object.keys(ni)) for (const a of ni[k] || []) { if (a.family === 'IPv4' && !a.internal) { self.ip = a.address; break outer; } } } catch (e) {}
    try { const mi = fs.readFileSync('/proc/meminfo', 'utf8'); const g = (n) => { const m = new RegExp(n + ':\\s+(\\d+) kB').exec(mi); return m ? Number(m[1]) * 1024 : 0; }; self.memTotalBytes = g('MemTotal'); self.memFreeBytes = g('MemAvailable'); } catch (e) {}
    try { const st = fs.statfsSync('/'); self.diskTotalBytes = st.blocks * st.bsize; self.diskAvailableBytes = st.bavail * st.bsize; } catch (e) {}
    if (!GW_VER_CACHE) execFile('/home/j/.npm-global/bin/openclaw', ['--version'], { timeout: 8000 }, (ve, vo) => { if (!ve && vo) GW_VER_CACHE = String(vo).trim().split('\n')[0].slice(0, 40); });
    execFile('/home/j/.npm-global/bin/openclaw', ['nodes', 'status', '--json', '--timeout', '8000'], { timeout: 12000, cwd: '/home/j' }, (nerr, stdout) => {
      const nd = { ok: !nerr, ts: Date.now(), nodes: [], self };
      try { const nj = JSON.parse(stdout); nd.nodes = (nj && nj.nodes) || []; } catch (e) { nd.ok = false; }
      NODES_CACHE = { t: Date.now(), data: nd };
      res.writeHead(200, nhdr); res.end(JSON.stringify(nd));
    });
    return;
  }

  // ===== 健康总览：A机/OC/B机 + 24h 稳定性 =====
  if (url.pathname === '/api/health-summary') {
    const hh = HEALTH_HIST || [], now = Date.now();
    const day = hh.filter(x => now - x.t <= 24 * 3600 * 1000);
    const last = hh.length ? hh[hh.length - 1] : null;
    const oc = HEALTH_LAST_OC || {};
    const el = oc.eventLoop || {};
    const dq0 = (oc.deliveryQueues && oc.deliveryQueues.failed);
    let dq = 0; if (typeof dq0 === 'number') dq = dq0; else if (dq0 && typeof dq0 === 'object') dq = dq0.count || dq0.total || Object.keys(dq0).length;
    let drops = 0; for (let i = 1; i < day.length; i++) { if (day[i].b && !day[i].b.on && day[i - 1].b && day[i - 1].b.on) drops++; }
    const bOn = day.filter(x => x.b && x.b.on).length;
    const okC = day.filter(x => x.ok).length;
    const out = { ts: now, samples: day.length,
      a: last && last.a ? last.a : {}, aMemPeak: day.reduce((m, x) => Math.max(m, (x.a && x.a.memPct) || 0), 0),
      oc: { ok: !!oc.ok, degraded: !!el.degraded, delayMaxMs: el.delayMaxMs || 0, delayP99Ms: el.delayP99Ms || 0, util: el.utilization || 0, dq, channels: Object.keys(oc.channels || {}).length, sessions: (oc.sessions && oc.sessions.count) || 0, agents: Array.isArray(oc.agents) ? oc.agents.length : 0, okPct: day.length ? Math.round(100 * okC / day.length) : 100 },
      b: { on: !!(last && last.b && last.b.on), seen: (last && last.b && last.b.seen) || 0, onlinePct: day.length ? Math.round(100 * bOn / day.length) : null, drops } };
    const osM = require('os');
    const nc = (NODES_CACHE && NODES_CACHE.data) || {};
    const node0 = (nc.nodes || [])[0] || {};
    const hst = node0.hostStats || {};
    let sip = null;
    try { const ni = osM.networkInterfaces(); for (const k of Object.keys(ni)) { if (sip) break; for (const a of ni[k] || []) { if (a.family === 'IPv4' && !a.internal) { sip = a.address; break; } } } } catch (e) {}
    let memT = 0, memA = 0;
    try { const mi = fs.readFileSync('/proc/meminfo', 'utf8'); const gg = (n) => { const m = new RegExp(n + ':\\s+(\\d+) kB').exec(mi); return m ? Number(m[1]) * 1024 : 0; }; memT = gg('MemTotal'); memA = gg('MemAvailable'); } catch (e) {}
    out.machines = { a: { name: osM.hostname(), ip: sip, memT, memA },
      b: { name: node0.displayName || '', ip: node0.remoteIp || '', plat: node0.platform || '', ver: node0.version || '',
        memT: hst.memoryTotalBytes || 0, memA: hst.memoryFreeBytes || 0, diskA: hst.diskAvailableBytes || 0 } };
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    res.end(JSON.stringify(out)); return;
  }



function upgradeBlockers(){
  const fs = require("fs"), cp = require("child_process");
  const W = "/home/j/.openclaw/workspace/state/work";
  const out = [];
  const exists = p => { try { return fs.existsSync(p); } catch { return false; } };
  const unitActive = u => { try { return cp.execSync("systemctl --user is-active " + u, {encoding:"utf8", stdio:["ignore","pipe","ignore"]}).trim() === "active"; } catch { return false; } };
  if (exists(W + "/.upgrade-running")) out.push("已有升级在进行（.upgrade-running）");
  if (exists(W + "/.safe-restart-running")) out.push("有安全重启在进行（.safe-restart-running）");
  if (exists(W + "/.watchdog-pause")) out.push("看门狗处于暂停状态（.watchdog-pause 残留）");
  if (unitActive("openclaw-gateway.service")) { /* 正常 */ } else out.push("网关未运行");
  try {
    const r = cp.execSync("bash -c 'ls /home/j/.openclaw/workspace/state/work/pending-backup-push /home/j/.openclaw/workspace/state/work/pending-x /home/j/.openclaw/workspace/state/work/pending-mirror 2>/dev/null | wc -l'", {encoding:"utf8"}).trim();
  } catch {}
  try {
    const busy = (() => { try { return cp.execFileSync("pgrep", ["-f", "openclaw backup create|nas-push-archive|backup-mirror-verify"], {encoding:"utf8"}).trim().split(String.fromCharCode(10)).filter(Boolean).length; } catch { return 0; } })();
    if (Number(busy) > 0) out.push("备份链路正在运行（" + busy + " 个进程）");
  } catch {}
  return out;
}

  // ===== 实时进度窗口：/api/ops/start → 后台跑并把输出写日志；/ops-live 页面轮询 =====

  if (url.pathname === "/api/upgrade/state") {
    const hdr4 = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
    const cp = require("child_process");
    let ver = "";
    try { ver = cp.execSync("openclaw --version 2>/dev/null | tail -1", {encoding:"utf8", timeout:4000}).trim(); } catch {}
    let tgt = "";
    try { const st = JSON.parse(cp.execFileSync("openclaw", ["update","status","--json"], {encoding:"utf8", timeout:8000})); tgt = (st.availability && st.availability.latestVersion) || ""; } catch {}
    const blk = upgradeBlockers();
    const running = OPS_BUSY === "upgrade";
    res.writeHead(200, hdr4);
    res.end(JSON.stringify({ ok:true, running, blockers: blk, version: ver, target: tgt, canStart: !running && blk.length === 0 }));
    return;
  }
  if (url.pathname === '/api/ops/start') {
    const hdr2 = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' };
    const key = String(url.searchParams.get('cmd') || '');
    const spec = OPS_SPEC[key];
    if (!spec) { res.writeHead(400, hdr2); res.end(JSON.stringify({ ok: false, error: 'unknown cmd' })); return; }
  if (key === "upgrade") {
    const hdr3 = { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" };
    if (OPS_BUSY === "upgrade") { res.writeHead(409, hdr3); res.end(JSON.stringify({ ok:false, error:"升级已在进行中，等它跑完再点" })); return; }
    const blk = upgradeBlockers();
    if (blk.length) { res.writeHead(409, hdr3); res.end(JSON.stringify({ ok:false, blocked:true, blockers:blk, error:"现在不能升级：" + blk.join("；") })); return; }
  }
    if (spec.confirm && url.searchParams.get('confirm') !== '1') {
      res.writeHead(400, hdr2); res.end(JSON.stringify({ ok: false, needConfirm: true, label: spec.label })); return;
    }
    if (OPS_BUSY) { res.writeHead(409, hdr2); res.end(JSON.stringify({ ok: false, error: '已有任务在跑：' + OPS_BUSY })); return; }
    const jobId = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 6);
    const jdir = path.join(__dirname, 'data', 'ops-jobs');
    try { fs.mkdirSync(jdir, { recursive: true }); } catch (e) {}
    const logPath = path.join(jdir, jobId + '.log');
    const startedAt = Date.now();
    const fd = fs.openSync(logPath, 'a');
    let child;
    OPS_BUSY = key;
    try {
      child = spawn('bash', (spec.script ? [spec.script].concat(spec.args || []) : [CONSOLE_SH, spec.arg]), {
        cwd: '/home/j/.openclaw/workspace',
        env: Object.assign({}, process.env, { PATH: '/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin' }),
        stdio: ['ignore', fd, fd],
        timeout: spec.ms
      });
    } catch (e) {
      try { fs.closeSync(fd); } catch (e2) {}
      OPS_BUSY = null;
      res.writeHead(500, hdr2); res.end(JSON.stringify({ ok: false, error: String(e && e.message || e) })); return;
    }
    fs.writeSync(fd, '=== ' + new Date().toLocaleString('zh-CN') + ' 启动 ' + (spec.label || key) + ' ===\n');
    const job = { id: jobId, cmd: key, label: spec.label || key, logPath, startedAt, code: null, done: false };
    OPS_JOBS.set(jobId, job);
    child.on('exit', function (code, sig) {
      job.code = typeof code === 'number' ? code : -1;
      job.done = true;
      job.endedAt = Date.now();
      try { fs.appendFileSync(logPath, '\n=== 结束 rc=' + job.code + (sig ? ' sig=' + sig : '') + '，耗时 ' + Math.round((job.endedAt - job.startedAt) / 1000) + ' 秒 ===\n'); } catch (e) {}
      if (OPS_BUSY === key) OPS_BUSY = null;
      try { if (job.fd) fs.closeSync(job.fd); } catch (e) {}
    });
    job.fd = fd;
    res.writeHead(200, hdr2);
    res.end(JSON.stringify({ ok: true, jobId: jobId, label: job.label }));
    return;
  }

  if (url.pathname === '/api/ops/log') {
    const hdr3 = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' };
    const job = OPS_JOBS.get(String(url.searchParams.get('job') || ''));
    if (!job) { res.writeHead(404, hdr3); res.end(JSON.stringify({ ok: false, error: 'no such job' })); return; }
    const off = Math.max(0, Number(url.searchParams.get('off') || 0) || 0);
    let chunk = '';
    let size = 0;
    try {
      const st = fs.statSync(job.logPath);
      size = st.size;
      if (size > off) {
        const len = Math.min(size - off, 262144);
        const buf = Buffer.alloc(len);
        const fd2 = fs.openSync(job.logPath, 'r');
        fs.readSync(fd2, buf, 0, len, off);
        fs.closeSync(fd2);
        chunk = buf.toString('utf8');
      }
    } catch (e) {}
    res.writeHead(200, hdr3);
    res.end(JSON.stringify({ ok: true, done: job.done, code: job.code, label: job.label, cmd: job.cmd,
      startedAt: job.startedAt, elapsed: Math.round(((job.endedAt || Date.now()) - job.startedAt) / 1000),
      chunk: chunk, next: size }));
    return;
  }

  if (url.pathname === '/ops-live') {
    const hdr4 = { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' };
    res.writeHead(200, hdr4);
    res.end(OPS_LIVE_HTML);
    return;
  }

  // ===== 运维动作（果果助手并入）：执行 console-cmd.sh 白名单命令 =====
  if (url.pathname === '/api/ops') {
    const hdr = { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' };
    const key = String(url.searchParams.get('cmd') || '');
    const spec = OPS_SPEC[key];
    if (!spec) { res.writeHead(400, hdr); res.end(JSON.stringify({ ok: false, error: '未知操作' })); return; }
    if (OPS_BUSY) {
      res.writeHead(409, hdr);
      res.end(JSON.stringify({ ok: false, error: '已有运维动作在执行：' + ((OPS_SPEC[OPS_BUSY] || {}).label || OPS_BUSY), busy: OPS_BUSY }));
      return;
    }
    OPS_BUSY = key;
    const t0 = Date.now();
    const r0 = await new Promise((resolve) => {
      let buf = '', done = false;
      let cp;
      try {
        cp = spawn('bash', (spec.script ? [spec.script].concat(spec.args || []) : [CONSOLE_SH, spec.arg]), {
          cwd: '/home/j/.openclaw/workspace',
          env: Object.assign({}, process.env, { PATH: '/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin' }),
          timeout: spec.ms
        });
      } catch (e) { resolve({ code: -1, out: e.message }); return; }
      const push = (d) => { if (Buffer.byteLength(buf) < 300000) buf += d.toString(); };
      cp.stdout.on('data', push);
      cp.stderr.on('data', push);
      cp.on('error', (e) => { if (!done) { done = true; resolve({ code: -1, out: buf + String.fromCharCode(10) + e.message }); } });
      cp.on('close', (code, sig) => { if (!done) { done = true; resolve({ code: code == null ? -1 : code, sig: sig || '', out: buf }); } });
    });
    OPS_BUSY = null;
    const ms = Date.now() - t0;
    OPS_LAST = { cmd: key, label: spec.label, code: r0.code, ms, at: new Date().toISOString(), ok: r0.code === 0 };
    res.writeHead(200, hdr);
    res.end(JSON.stringify({ ok: r0.code === 0, cmd: key, label: spec.label, code: r0.code, sig: r0.sig || '', ms, out: (r0.out || '').trim() }));
    return;
  }

  if (url.pathname === '/api/ollama/refresh') {
    await pollOllama();
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    res.end(JSON.stringify({ ok: true, ollama: OLLAMA.val }));
    return;
  }
  if (url.pathname === '/api/ollama/update') {
    const cur = String((OLLAMA.val && OLLAMA.val.version) || '');
    const lt = String(OL_LATEST.tag || '');
    const send = function(code, obj){ res.writeHead(code, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' }); res.end(JSON.stringify(obj)); };
    if (OL_UPDATE.running) return send(200, { ok: true, running: true, msg: '更新已在进行中', target: OL_UPDATE.msg });
    if (cur && lt && lt === cur) return send(200, { ok: true, upToDate: true, msg: '已是最新版本 v' + cur });
    if (!lt) return send(200, { ok: false, msg: '取不到 Ollama 最新版本，请稍后再试' });
    OL_UPDATE = { running: true, startedAt: Date.now(), msg: '安装 v' + lt };
    const ps = "$ErrorActionPreference='Stop'; $u='https://ollama.com/download/OllamaSetup.exe'; $o=Join-Path $env:TEMP 'OllamaSetup.exe'; Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $o; Start-Process -FilePath $o -ArgumentList '/SILENT' -Wait; Remove-Item $o -Force -ErrorAction SilentlyContinue; 'DONE'";
    execFile(process.env.INFOWIN_PS || 'powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps], { timeout: 900000, maxBuffer: 1e6 }, function(err, stdout, stderr) {
      const good = !err && String(stdout || '').indexOf('DONE') >= 0;
      OL_UPDATE = { running: false, startedAt: 0, msg: good ? ('已安装 v' + lt + '，正在重测') : ('更新失败：' + String((stderr || (err && err.message) || '')).slice(0, 160)) };
      setTimeout(function(){ try { pollOllama(); pollOllamaAll(); } catch (e) {} }, 4000);
    });
    return send(202, { ok: true, started: true, target: lt, msg: '已开始下载并安装 v' + lt + '（约 1-3 分钟）' });
  }
  if (url.pathname === '/api/balances/refresh') {
    const pv = url.searchParams.get('p');
    const st = pv ? startBalanceRefreshOne(pv) : startBalanceRefresh();
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    res.end(JSON.stringify({ ok: true, provider: pv || null, running: st.running, startedAt: st.startedAt, finishedAt: st.finishedAt, error: st.error || null }));
    return;
  }
  if (url.pathname === '/api/ledger/refresh') {
    const out = refreshLedgerNow();
    res.writeHead(out.ok ? 200 : 500, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    res.end(JSON.stringify(out));
    return;
  }
  if (url.pathname === '/api/tasks/refresh') {
    if (TASK_REFRESH.running) {
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
      return res.end(JSON.stringify({ ok: true, running: true, startedAt: TASK_REFRESH.startedAt }));
    }
    TASK_REFRESH = { running: true, startedAt: Date.now(), finishedAt: 0, error: null };
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    res.end(JSON.stringify({ ok: true, running: true, startedAt: TASK_REFRESH.startedAt }));
    (async () => {
      try {
        CACHE.cronAt = 0; CACHE.sessAt = 0; CACHE.statusAt = 0;
        await Promise.all([
          refresh('cron', ['cron', 'list', '--json'], 0),
          refresh('sess', ['sessions', '--json', '--all-agents', '--limit', '300'], 0),
          refresh('status', ['status', '--json'], 0)
        ]);
        refreshLedgerNow();
        TASK_REFRESH.running = false; TASK_REFRESH.finishedAt = Date.now();
      } catch (e) {
        TASK_REFRESH.running = false; TASK_REFRESH.finishedAt = Date.now(); TASK_REFRESH.error = String(e.message || e);
      }
    })();
    return;
  }
  if (url.pathname === '/api/refresh') {
    const started = Date.now();
    try {
      CACHE.statusAt = 0; CACHE.cronAt = 0; CACHE.sessAt = 0; CACHE.hostAt = 0; CACHE.agentsAt = 0;
      STOCKS_AT = 0; STOCKS_ERR = null; WEATHER_AT = 0; WEATHER_ERR = null; BAL_AT = 0;
      inflight.stocks = null; inflight.weather = null;
      await refreshAll();
      fetchBalances().catch(() => {});
      const body = JSON.stringify({ ok: true, ms: Date.now() - started, at: Date.now() });
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
      return res.end(body);
    } catch (e) {
      res.writeHead(500, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
      return res.end(JSON.stringify({ ok: false, error: String(e.message || e) }));
    }
  }
  if (url.pathname === '/api/host') {
    const hh = CACHE.host ? Object.assign({}, CACHE.host, { ageMs: Date.now() - CACHE.hostAt }) : null;
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    return res.end(JSON.stringify(hh));
  }
  if (url.pathname === '/api/state') {
    try { await refreshAll(); } catch (e) { ERR.refresh = e.message; }
    const body = JSON.stringify(build());
    res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    return res.end(body);
  }
  if (url.pathname === '/api/todo' && req.method === 'POST') {
    let raw = '';
    req.on('data', c => { raw += c; if (raw.length > 100000) req.destroy(); });
    req.on('end', () => {
      let body = {};
      try { body = JSON.parse(raw || '{}'); } catch {}
      handleTodo(body, res);
    });
    return;
  }
  if (url.pathname === '/health') { res.writeHead(200); return res.end('ok'); }
  let p = url.pathname === '/' ? '/index.html' : url.pathname;
  p = path.join(PUBLIC, path.normalize(p).replace(/^([.][.][/\\])+/, ''));
  fs.readFile(p, (e, buf) => {
    if (e) { res.writeHead(404); return res.end('not found'); }
    // 2026-11-09 上帝视角：首页由服务端注入六域状态条，避免依赖 fetch/子资源（面板内子请求曾挂起）
    if (p.endsWith('/index.html')) {
      try { buf = Buffer.from(String(buf).replace('<!--GV-->', renderGv()), 'utf8'); } catch (err) {}
    }
    res.writeHead(200, { 'content-type': MIME[path.extname(p)] || 'application/octet-stream', 'cache-control': 'no-store' });
    res.end(buf);
  });
});

setInterval(function(){ ERR_REPORT.report(false).catch(function(){}); }, 5 * 60 * 1000);
server.listen(PORT, HOST, () => {
  console.log('[guoguo] listening on http://' + HOST + ':' + PORT);
  startLogTail();
  refreshAll();
});

setInterval(() => { refreshAll().catch(() => {}); }, 15000);
// 2026-10-28：PC 指标单独加速（不改其他 15s 轮询）
setInterval(() => { refreshHost(6000).catch(() => {}); }, 8000);
let loopPrev = Date.now();
setInterval(() => {
  startFastSampler(); mergeFast(); sampleOc();
  const now = Date.now();
  const lag = Math.max(0, now - loopPrev - 1000);
  loopPrev = now;
  if (CACHE.host) {
    CACHE.host.eventLoopMs = Math.round(lag * 10) / 10;
    CACHE.host.rssMB = Math.round(process.memoryUsage().rss / 1048576);
  }
}, 1000);
startFastSampler();

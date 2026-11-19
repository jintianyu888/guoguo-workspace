#!/usr/bin/env python3
"""保安管家 — 常驻多路监控：进出追踪 + 房间停留 + 实时飞书通知
零 token：所有人脸识别本地 InsightFace + 3070 GPU。
飞书只发纯文字通知。

用法:
  python security-patrol.py                    # 全部 9 路常驻
  python security-patrol.py --channels 101,701  # 只看门口
  python security-patrol.py --test-notify     # 测试飞书通知
  python security-patrol.py --report          # 生成今日动向报表

依赖：
  - face-recognize.py 的 db.npz 人脸库（先跑 nvr-scan + face-collect cluster + register 建库）
  - ~/.config/hik-nvr.env（NVR 凭据）
  - ffmpeg + cv2 + insightface + numpy

数据:
  state/events.db          — SQLite 事件日志
  state/snapshots/         — 抓拍快照
  state/reports/           — 每日报表
"""
import os as _os, site as _site, glob as _glob, ctypes as _ct
_libs = _glob.glob(_os.path.join(_site.getsitepackages()[0], "nvidia", "*", "lib"))
_os.environ["LD_LIBRARY_PATH"] = ":".join(_libs + ["/usr/lib/wsl/lib"]) + ":" + _os.environ.get("LD_LIBRARY_PATH", "")
for _d in _libs:
    for _f in sorted(_glob.glob(_os.path.join(_d, "lib*.so*"))):  # 2026-10-26 C6 修：此处 os 尚未 import，误用 os.path 导致 NameError（每 10 分钟失败）
        try: _ct.CDLL(_f)
        except Exception: pass

import argparse, glob, hashlib, json, os, subprocess, sys, time, sqlite3, threading, datetime
import numpy as np, cv2

BASE = "/home/j/.openclaw/workspace"
FD = os.path.join(BASE, "state", "faces")
DBP = os.path.join(FD, "db.npz")           # 识别库（face-recognize.py 的）
COLL_NPZ = os.path.join(FD, "collected.npz")  # 收集库
HITS = os.path.join(FD, "hits"); os.makedirs(HITS, exist_ok=True)
DB_PATH = os.path.join(BASE, "state", "events.db")
SNAP_DIR = os.path.join(BASE, "state", "snapshots")
RPT_DIR = os.path.join(BASE, "state", "reports")
WORK_DIR = os.path.join(BASE, "state", "work")
LOG = os.path.join(WORK_DIR, "security-patrol.log")
for d in (HITS, SNAP_DIR, RPT_DIR, WORK_DIR, os.path.dirname(DB_PATH)):
    os.makedirs(d, exist_ok=True)

# ── NVR 配置 ──
ENV = {}
env_path = os.path.expanduser("~/.config/hik-nvr.env")
if os.path.exists(env_path):
    for ln in open(env_path):
        if "=" in ln:
            k, v = ln.strip().split("=", 1)
            ENV[k] = v
NVR_IP = ENV.get("HIK_NVR_IP", "192.168.1.103")
NVR_PASS = ENV.get("HIK_NVR_PASS", "")

# ── 通道映射（从 nvr-scan-daily.sh 推断 + AGENTS.md 房间名）──
# NVR 通道号 → 房间名 + 类型
CHANNELS = {
    "101":  {"name": "门口左",   "type": "door"},
    "701":  {"name": "门口右",   "type": "door"},
    "301":  {"name": "后门左",   "type": "door"},
    "1601": {"name": "后门右",   "type": "door"},
    "1001": {"name": "大厅",     "type": "room"},
    "1201": {"name": "乐理",     "type": "room"},
    "1301": {"name": "小琴",     "type": "room"},
    "1401": {"name": "主琴",     "type": "room"},
    "1501": {"name": "卫生间厅",  "type": "room"},
}

# 拓扑：人从 X 进 → 下一步应该出现在 Y
TOPOLOGY = {
    "门口左":   ["大厅"],
    "门口右":   ["大厅"],
    "大厅":     ["乐理", "小琴", "主琴", "卫生间厅"],
    "后门左":   ["卫生间厅", "大厅"],
    "后门右":   ["卫生间厅", "大厅"],
    "乐理":     ["大厅"],
    "小琴":     ["大厅"],
    "主琴":     ["大厅"],
    "卫生间厅": ["大厅", "后门左", "后门右"],
}

# ── 日志 ──
def log(msg):
    line = "[%s] %s" % (time.strftime("%F %T"), msg)
    print(line, flush=True)
    open(LOG, "a").write(line + "\n")

# ── SQLite ──
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY,
        timestamp TEXT NOT NULL,
        person TEXT,
        action TEXT,
        channel TEXT,
        confidence REAL,
        snapshot_path TEXT,
        note TEXT
    )""")
    for idx in ("idx_ts", "idx_person", "idx_action"):
        col = idx.split("_")[1]
        try: conn.execute("CREATE INDEX %s ON events(%s)" % (idx, col))
        except Exception: pass
    conn.commit()
    return conn

def log_event(conn, person, action, channel, confidence=0.0, snapshot="", note=""):
    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute("INSERT INTO events(timestamp,person,action,channel,confidence,snapshot_path,note) VALUES(?,?,?,?,?,?,?)",
                 (ts, person, action, channel, confidence, snapshot, note))
    conn.commit()
    return ts

# ── 人脸识别库 ──
_app = None
def app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis
        _app = FaceAnalysis(name="antelopev2", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        _app.prepare(ctx_id=0, det_size=(1024, 1024))
    return _app

def load_db():
    if os.path.exists(DBP):
        d = np.load(DBP, allow_pickle=True)
        return list(d["labels"]), d["samples"]
    return [], np.zeros((0, 512), dtype=np.float32)

def norm(v):
    return v / (np.linalg.norm(v) + 1e-8)

def identify(v, labels, samples, threshold=0.38):
    """返回 (name, confidence) 或 (None, max_sim)"""
    if not len(labels):
        return None, 0.0
    sims = samples @ v
    i = int(np.argmax(sims))
    s = float(sims[i])
    return (labels[i], s) if s >= threshold else (None, s)

# ── 飞书通知（纯文字，通过 openclaw message 工具或直接 curl）──
# 注意：这个函数设计为通过 openclaw 的 message 工具发送。
# 在独立运行模式下，它写入一个通知队列文件，由 openclaw 的 automation 读取并发送。
NOTIFY_QUEUE = os.path.join(WORK_DIR, "notify-queue.jsonl")

NOTIFY_STATE = os.path.join(WORK_DIR, ".patrol-notify-state.json")
NOTIFY_COOLDOWN_SEC = int(os.environ.get("PATROL_NOTIFY_COOLDOWN", "21600"))  # 6h
_notify_lock = threading.Lock()

def _notify_state_load():
    try:
        with open(NOTIFY_STATE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def _notify_state_save(state):
    """原子写；按冷却期清理过期项，防无限增长。"""
    now = time.time()
    pruned = {k: v for k, v in state.items() if now - v < NOTIFY_COOLDOWN_SEC}
    tmp = NOTIFY_STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pruned, f)
    os.replace(tmp, NOTIFY_STATE)

def notify(text):
    """安保告警：文本哈希冷却去重 → 优先真实投递 notify.sh → 失败回落写队列。
    2026-11-02 双审（kimi-k3.1-pro + qwen3.8-max）后落地：
    原实现只写 state/work/notify-queue.jsonl，而该文件无任何消费方，告警等于静默丢弃。
    冷却时间戳只在投递或回落**成功**后记录，避免通道故障时把告警一并压掉。"""
    try:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
    except Exception:
        key = str(len(text))
    with _notify_lock:
        state = _notify_state_load()
        ts = state.get(key)
        if ts and (time.time() - float(ts)) < NOTIFY_COOLDOWN_SEC:
            log("通知冷却跳过: %s" % text[:60])
            return
        ok = False
        try:
            # 2026-11-02 双审(qwen3.8-max+glm-5.3)后修：脚本在 BASE/tools 下，原用 WORK_DIR(state/work) 拼出不存在路径 → rc=127 每轮必失败入死信
            r = subprocess.run(["bash", os.path.join(BASE, "tools", "notify.sh"), "安保告警", text],
                               cwd=WORK_DIR, timeout=120, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            ok = (r.returncode == 0)
        except Exception as e:
            log("通知投递异常(%s): %s" % (type(e).__name__, str(e)[:100]))
        if ok:
            log("通知已投递: %s" % text[:80])
        else:
            try:
                entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "text": text}
                with open(NOTIFY_QUEUE, "a") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                log("通知投递失败，已落本地队列(无消费方，仅供排查): %s" % text[:80])
            except Exception as e:
                log("通知落盘也失败(%s): %s" % (type(e).__name__, str(e)[:100]))
                return
        # 只在真实投递成功后记冷却：通道故障期间不压制，网关恢复后下个 10 分钟窗自动补发
        if ok:
            state[key] = time.time()
            try:
                _notify_state_save(state)
            except Exception as e:
                log("通知冷却状态写入失败(不阻断): %s" % type(e).__name__)

# ── 当前在场状态 ──
# person -> {room, since_ts, last_seen_ts}
presence = {}
# person -> last_event_ts（用于冷却）
cooldowns = {}
COOLDOWN = 60  # 同人同通道 60 秒内不重复告警

def _jpeg_size(data):
    """从 JPEG 头解析 (宽, 高)，失败返回 (0, 0)。不依赖解码库。"""
    try:
        i = 2
        n = len(data)
        while i < n - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h = (data[i + 5] << 8) | data[i + 6]
                w = (data[i + 7] << 8) | data[i + 8]
                return (w, h)
            if m in (0xD8, 0xD9) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            seg = (data[i + 2] << 8) | data[i + 3]
            i += 2 + seg
    except IndexError:
        pass
    return (0, 0)


def _flog(path, line):
    """抓帧明细日志：5MB 轮转，避免长跑撑爆磁盘。"""
    try:
        if os.path.exists(path) and os.path.getsize(path) > 5 * 1024 * 1024:
            try: os.replace(path, path + ".1")
            except OSError: pass
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), line))
    except OSError:
        pass


# ── ISAPI 快照抓帧器（替代 RTSP，接口模仿 Popen.poll）──
class _IsapiPoller(threading.Thread):
    """用 NVR 的 ISAPI picture 接口按间隔取 JPEG。

    背景：2026-11-05 实测所有房间主/子码流均为 HEVC，本地 ffmpeg 拉流报
    "PPS id out of range"、20 秒拿不到一帧；同通道 ISAPI 快照 9 路并发
    全部 HTTP 200、总耗时约 1.5 秒。故抓帧层改走 HTTP 快照。
    """

    def __init__(self, ip, pwd, ch_id, tmp, interval, res=None):
        super().__init__(daemon=True)
        self.ip, self.pwd, self.ch_id, self.tmp = ip, pwd, ch_id, tmp
        self.interval = max(1.0, float(interval))
        self.returncode = None
        self._stop = False
        self.seq = 0
        self._last_md5 = None
        self.dup = 0
        self.res = res
        self._last_change = time.time()
        self._stall_warned = False
        self.vlog = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "state", "work", "security-patrol-fetch.log")
        self.vlog = os.path.abspath(self.vlog)

    def run(self):
        fail = 0
        while not self._stop:
            self.seq += 1
            dst = os.path.join(self.tmp, "f_%06d.jpg" % self.seq)
            url = "http://%s/ISAPI/Streaming/channels/%s/picture" % (self.ip, self.ch_id)
            if self.res:
                url += "?videoResolutionWidth=%d&videoResolutionHeight=%d" % self.res
            http = 0
            _cfg = 'user = "admin:%s"\n' % str(self.pwd).replace("\\", "\\\\").replace('"', '\\"')
            try:
                _r = subprocess.run(
                    ["curl", "-s", "-o", dst, "-w", "%{http_code}", "--max-time", "8",
                     "--digest", "-K", "-", url],
                    input=_cfg.encode("utf-8"),
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    timeout=12)
                try:
                    http = int((_r.stdout or b"").decode("ascii", "ignore").strip() or 0)
                except ValueError:
                    http = 0
                rc = _r.returncode
            except Exception:
                rc = 1
                http = 0
            ok = False
            if rc == 0 and http == 200:
                try:
                    ok = os.path.getsize(dst) > 1500
                except OSError:
                    ok = False
            if ok:
                fail = 0
                try:
                    with open(dst, "rb") as fh:
                        data = fh.read()
                except OSError:
                    data = b""
                dims = _jpeg_size(data)
                # NVR 快照是周期刷新的，同一画面会重复返回；重复帧不落盘、不重复识别
                h = hashlib.md5(data).hexdigest() if data else None
                dup = False
                if h is not None and h == self._last_md5:
                    try: os.remove(dst)
                    except OSError: pass
                    self.dup += 1
                    dup = True
                    if not self._stall_warned and time.time() - self._last_change > 30:
                        self._stall_warned = True
                        log("ch%s 快照连续 %.0f 秒无变化（可能卡在缓存帧或画面已停），md5=%s"
                            % (self.ch_id, time.time() - self._last_change, h[:8]))
                else:
                    self._last_md5 = h
                    self._last_change = time.time()
                    self._stall_warned = False
                _flog(self.vlog, "ch%s http=%s %dB %sx%s%s"
                      % (self.ch_id, http, len(data), dims[0], dims[1],
                         " DUP" if dup else ""))
            else:
                fail += 1
                _flog(self.vlog, "ch%s http=%s 失败 rc=%s fails=%d"
                      % (self.ch_id, http, rc, fail))
                try: os.remove(dst)
                except OSError: pass
                if fail >= 3:
                    self.returncode = 1
                    return
            time.sleep(self.interval)

    def stop(self):
        self._stop = True

    def poll(self):
        return self.returncode


BACKOFF = (5, 10, 15, 20)  # 抓帧失败重试退避（秒）

# ── 单路监控线程 ──
def watch_channel(ch_id, interval, conn, labels, samples):
    """常驻抓帧 + 人脸识别 + 事件记录"""
    info = CHANNELS.get(ch_id, {"name": ch_id, "type": "unknown"})
    ch_name = info["name"]
    ch_type = info["type"]
    tmp = "/tmp/patrol-%s" % ch_id
    os.makedirs(tmp, exist_ok=True)

    def spawn_ffmpeg():
        for f in glob.glob(tmp + "/*.jpg"):
            try: os.remove(f)
            except Exception: pass
        _res = (1920, 1080) if ch_type == "door" else None
        _p = _IsapiPoller(NVR_IP, NVR_PASS, ch_id, tmp, interval, _res)
        _p.start()
        return _p

    log("ch%s(%s) 启动 快照模式（ISAPI）每%.0f秒" % (ch_id, ch_name, interval))
    _bi = 0
    proc = spawn_ffmpeg()
    seen_files = set()
    frame_count = 0

    while True:
        if proc.poll() is not None:
            _wait = BACKOFF[min(_bi, len(BACKOFF) - 1)]
            _bi += 1
            log("ch%s 快照抓帧器退出(%s)，%s秒后重启" % (ch_id, proc.returncode, _wait))
            time.sleep(_wait)
            proc = spawn_ffmpeg()
            seen_files = set()
            continue

        for p in sorted(glob.glob(tmp + "/*.jpg")):
            if p in seen_files:
                continue
            seen_files.add(p)
            frame_count += 1
            _bi = 0
            if len(seen_files) > 200:
                seen_files = set(sorted(seen_files)[-50:])

            img = cv2.imread(p)
            if img is None:
                continue

            faces = app().get(img)
            now = time.time()

            if not faces:
                # 没人 — 检查是否需要记录"离开"
                if ch_type == "room":
                    for person in list(presence.keys()):
                        st = presence[person]
                        if st["room"] == ch_name and now - st["last_seen_ts"] > 30:
                            # 超过 30 秒没看到 → 记录离开
                            duration = int(now - st["since_ts"])
                            ts = log_event(conn, person, "leave", ch_name, 0.0, note="停留%ds" % duration)
                            notify("📤 %s 离开 %s（停留 %s）" % (person, ch_name, fmt_duration(duration)))
                            del presence[person]
                continue

            for f in faces:
                v = norm(f.embedding)
                name, conf = identify(v, labels, samples)
                person = name or "unknown_%03d" % (hash(f.embedding.tobytes()) % 1000)
                key = "%s_%s" % (person, ch_id)

                # 冷却
                if now - cooldowns.get(key, 0) < COOLDOWN:
                    continue
                cooldowns[key] = now

                # 抓拍存档
                b = f.bbox.astype(int)
                x1, y1, x2, y2 = b
                pad = int(0.25 * max(x2 - x1, y2 - y1))
                y1c = max(0, y1 - pad); y2c = min(img.shape[0], y2 + pad)
                x1c = max(0, x1 - pad); x2c = min(img.shape[1], x2 + pad)
                snap_path = os.path.join(SNAP_DIR, time.strftime("%Y%m%d"), "%s_%s_%s.jpg" % (ch_name, person, time.strftime("%H%M%S")))
                os.makedirs(os.path.dirname(snap_path), exist_ok=True)
                cv2.imwrite(snap_path, img[y1c:y2c, x1c:x2c])

                if name is None:
                    # 陌生人
                    ts = log_event(conn, person, "stranger", ch_name, conf, snap_path)
                    notify("🔴 陌生人出现在 %s（%.2f）抓拍已存档" % (ch_name, conf))
                else:
                    # 已知人物
                    if ch_type == "door":
                        # 门口 → 判断进/出
                        ts = log_event(conn, person, "enter", ch_name, conf, snap_path)
                        notify("🚪 %s 从 %s 进入（%.2f）" % (person, ch_name, conf))
                        presence[person] = {"room": "（刚进门）", "since_ts": now, "last_seen_ts": now, "channel": ch_name}
                    else:
                        # 房间 → 更新停留
                        if person not in presence or presence[person]["room"] != ch_name:
                            # 新进入此房间
                            ts = log_event(conn, person, "present", ch_name, conf, snap_path)
                            notify("📍 %s 在 %s（%.2f）" % (person, ch_name, conf))
                            presence[person] = {"room": ch_name, "since_ts": now, "last_seen_ts": now, "channel": ch_name}
                        else:
                            # 同房间续留，更新 last_seen
                            presence[person]["last_seen_ts"] = now

            # 清理临时帧
            try: os.remove(p)
            except Exception: pass

        time.sleep(0.5)

def fmt_duration(secs):
    m, s = divmod(int(secs), 60)
    h, m = divmod(m, 60)
    if h: return "%dh%dm" % (h, m)
    if m: return "%dm%ds" % (m, s)
    return "%ds" % s

# ── 当前面板 ──
def print_presence():
    """打印当前人员分布"""
    now = time.time()
    lines = ["📍 当前人员分布 (%s)" % time.strftime("%H:%M")]
    if not presence:
        lines.append("  （无人）")
    for person, st in presence.items():
        dur = fmt_duration(now - st["since_ts"])
        lines.append("  %s: %s（停留 %s）" % (person, st["room"], dur))
    return "\n".join(lines)

# ── 每日报表 ──
def generate_report(conn):
    """生成今日动向报表"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT person, action, channel, timestamp, confidence FROM events "
        "WHERE timestamp LIKE ? ORDER BY timestamp", (today + "%",)
    ).fetchall()

    lines = ["📊 %s 人员动向" % today, "━" * 30]
    if not rows:
        lines.append("（无事件）")
    else:
        by_person = {}
        for r in rows:
            by_person.setdefault(r[0], []).append(r)
        strangers = 0
        for person, events in sorted(by_person.items()):
            lines.append("%s:" % person)
            for _, action, ch, ts, conf in events:
                t = ts.split("T")[1] if "T" in ts else ts
                if action == "stranger": strangers += 1
                lines.append("  %s %s %s (%.2f)" % (t, action, ch, conf))
            lines.append("")
        lines.append("━" * 30)
        lines.append("总计: %d 人，%d 次陌生人事件" % (len(by_person), strangers))

    report = "\n".join(lines)
    rpt_path = os.path.join(RPT_DIR, "%s.txt" % today)
    with open(rpt_path, "w") as f:
        f.write(report)
    log("报表已生成: %s" % rpt_path)
    return report

# ── 测试通知 ──
def test_notify():
    notify("✅ 安保监控通知测试 — 如果你看到这条消息，说明通知通道通了。")
    log("测试通知已入队")

# ── 主入口 ──
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channels", default="101,701,301,1601,1001,1201,1301,1401,1501",
                    help="逗号分隔的通道号")
    ap.add_argument("--interval-door", type=float, default=2.0, help="门禁抓帧间隔(秒)")
    ap.add_argument("--interval-room", type=float, default=5.0, help="房间抓帧间隔(秒)")
    ap.add_argument("--test-notify", action="store_true", help="测试飞书通知")
    ap.add_argument("--report", action="store_true", help="生成今日报表")
    ap.add_argument("--presence", action="store_true", help="打印当前人员分布")
    ap.add_argument("--once", action="store_true", help="跑一轮抓帧后退出（供 systemd timer 用）")
    ap.add_argument("--once-seconds", type=float, default=60, help="--once 模式抓帧时长(秒)")
    args = ap.parse_args()

    if args.test_notify:
        test_notify()
        return
    if args.report:
        conn = init_db()
        report = generate_report(conn)
        print(report)
        conn.close()
        return
    if args.presence:
        print(print_presence())
        return

    # 正常多路监控模式
    conn = init_db()
    labels, samples = load_db()
    log("=== 保安管家巡逻启动 ===")
    log("人脸库: %d 人 %d 样本" % (len(set(labels)), len(labels)))
    if not labels:
        log("⚠️ 人脸库为空！请先跑 nvr-face-scan.py + face-collect.py cluster + face-recognize.py register 建库")
        log("⚠️ 现在只能检测陌生人，无法识别已知人物")
        notify("⚠️ 安保监控启动但人脸库为空，当前只能检测陌生人。需要先跑 NVR 录像扫描建库。")

    ch_list = [c.strip() for c in args.channels.split(",")]
    threads = []
    for ch in ch_list:
        info = CHANNELS.get(ch, {"type": "unknown"})
        interval = args.interval_door if info["type"] == "door" else args.interval_room
        t = threading.Thread(target=watch_channel, args=(ch, interval, conn, labels, samples), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(2)  # 错开启动

    log("全部 %d 路已启动" % len(ch_list))
    if args.once:
        time.sleep(args.once_seconds)
        log("once 结束，人员分布: %s" % print_presence().replace("\n", " | "))
        return
    notify("🛡️ 安保监控已启动：%d 路摄像头" % len(ch_list))

    # 主循环：每小时写一次状态日志
    try:
        while True:
            time.sleep(3600)
            log("状态: %s" % print_presence().replace("\n", " | "))
    except KeyboardInterrupt:
        log("收到退出信号，停止监控")
        report = generate_report(conn)
        notify("🛡️ 安保监控已停止\n" + report)

if __name__ == "__main__":
    main()

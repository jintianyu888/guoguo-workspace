#!/usr/bin/env python3
"""printer-status.py —— 查东芝 e-STUDIO 的实时状态：缺纸/卡纸/纸盒余量/粉量。

两条通道（都用标准库，无第三方依赖）：
  1) IPP 631  Get-Printer-Attributes  → printer-state-reasons 里有 media-empty / media-needed / jam
  2) SNMP 161 v1 GET                  → 每个纸盒 prtInputStatus / prtInputCurrentLevel（%）

用法:
  printer-status.py                 # 两条都查，人读
  printer-status.py --json          # 机器读（供打印前自检脚本用）
  printer-status.py --ipp / --snmp  # 只查一条
  printer-status.py --host 192.168.1.80 --timeout 4

退出码: 0=正常可打  1=有异常(缺纸/卡纸/离线)  2=两条通道都查不到(状态未知)
"""
import argparse, datetime, json, os, socket, struct, sys

DEFAULT_HOST = "192.168.1.80"
PAPER_TRAY = {"a4": "1", "a3": "2"}   # 主公 2026-11-24 确认：纸盒1=A4，纸盒2=A3
COUNTER_OID = "1.3.6.1.2.1.43.10.2.1.4.1.1"   # prtMarkerLifeCount 总印量
STATE_DIR = os.environ.get("PRINT_STATE_DIR", "/home/j/.openclaw/workspace/state/print")
HISTORY = os.path.join(STATE_DIR, "counter-history.json")
IPP_PATH = "/ipp/print"

STATE = {3: "idle", 4: "processing", 5: "stopped"}
INPUT_STATUS = {
    1: "other", 2: "unknown", 3: "idle", 4: "running", 5: "warning",
    6: "shutdown", 7: "jam", 8: "door-open", 9: "empty", 10: "full",
    11: "input-overflow", 12: "output-overflow", 13: "paper-problem",
    14: "power-off", 15: "offline",
}


def ipp_status(host, port=631, path=IPP_PATH, timeout=4):
    """IPP Get-Printer-Attributes；返回 (ok, attrs, err)。"""
    def attr(tag, name, value):
        n = name.encode()
        if isinstance(value, str):
            v = value.encode()
        else:
            v = bytes(value)
        return bytes([tag]) + struct.pack(">H", len(n)) + n + struct.pack(">H", len(v)) + v

    body = b"\x01\x01" + struct.pack(">H", 0x000B) + struct.pack(">I", 1)  # ver 1.1, Get-Printer-Attributes
    body += b"\x01"  # operation-attributes-tag
    body += attr(0x47, "attributes-charset", "utf-8")        # charset
    body += attr(0x48, "attributes-natural-language", "en")  # natural-language
    body += attr(0x45, "printer-uri", "ipp://%s:%d%s" % (host, port, path))  # uri
    for a in ("printer-state", "printer-state-reasons", "printer-is-accepting-jobs",
              "printer-state-message", "queued-job-count", "marker-levels", "marker-names"):
        body += attr(0x44, "requested-attributes", a)  # keyword
    body += b"\x03"  # end-of-attributes-tag

    req = ("POST %s HTTP/1.1\r\nHost: %s:%d\r\nContent-Type: application/ipp\r\n"
           "Content-Length: %d\r\nConnection: close\r\n\r\n" % (path, host, port, len(body))).encode() + body
    try:
        s = socket.create_connection((host, port), timeout)
    except OSError as e:
        return False, {}, "IPP 连不上 %s:%d (%s)" % (host, port, e)
    try:
        s.sendall(req)
        chunks = []
        while True:
            b = s.recv(65536)
            if not b:
                break
            chunks.append(b)
    finally:
        s.close()
    raw = b"".join(chunks)
    if b"\r\n\r\n" not in raw:
        return False, {}, "IPP 响应不完整 (%d B)" % len(raw)
    payload = raw.split(b"\r\n\r\n", 1)[1]
    if len(payload) < 8:
        return False, {}, "IPP 响应体为空"
    if payload[2:4] != b"\x00\x00":
        return False, {}, "IPP 返回错误码 0x%s" % payload[2:4].hex()

    attrs, i, n = {}, 8, len(payload)
    while i < n:
        tag = payload[i]
        if tag in (0x03,):
            break
        if tag < 0x10:            # delimiter tag
            i += 1
            continue
        if i + 3 > n:
            break
        nlen = struct.unpack(">H", payload[i + 1:i + 3])[0]
        name = payload[i + 3:i + 3 + nlen].decode("utf-8", "replace")
        i += 3 + nlen
        if i + 2 > n:
            break
        vlen = struct.unpack(">H", payload[i:i + 2])[0]
        val = payload[i + 2:i + 2 + vlen]
        i += 2 + vlen
        if tag in (0x21, 0x23):   # integer / enum
            v = struct.unpack(">i", val)[0] if len(val) == 4 else int.from_bytes(val or b"\0", "big")
        elif tag == 0x41:         # textWithoutLanguage
            v = val.decode("utf-8", "replace")
        elif tag == 0x42:         # nameWithoutLanguage
            v = val.decode("utf-8", "replace")
        elif tag == 0x44:         # keyword
            v = val.decode("utf-8", "replace")
        elif tag == 0x22:         # boolean
            v = bool(val and val[0])
        else:
            v = val
        attrs.setdefault(name, []).append(v)
    return True, attrs, None


_LAST_STATUS = {"code": 0}


def _ipp_http(host, port, path, body, timeout):
    req = ("POST %s HTTP/1.1\r\nHost: %s:%d\r\nContent-Type: application/ipp\r\n"
           "Content-Length: %d\r\nConnection: close\r\n\r\n" % (path, host, port, len(body))).encode() + body
    s = socket.create_connection((host, port), timeout)
    try:
        s.sendall(req)
        chunks = []
        while True:
            b = s.recv(65536)
            if not b:
                break
            chunks.append(b)
    finally:
        s.close()
    raw = b"".join(chunks)
    if b"\r\n\r\n" not in raw:
        raise ValueError("IPP 响应不完整 (%d B)" % len(raw))
    payload = raw.split(b"\r\n\r\n", 1)[1]
    if len(payload) < 8:
        raise ValueError("IPP 响应体为空")
    return payload


def _ipp_parse(payload):
    code = struct.unpack(">H", payload[2:4])[0]
    _LAST_STATUS["code"] = code
    attrs, i, n = {}, 8, len(payload)
    while i < n:
        tag = payload[i]
        if tag == 0x03:
            break
        if tag < 0x10:
            i += 1
            continue
        if i + 3 > n:
            break
        nlen = struct.unpack(">H", payload[i + 1:i + 3])[0]
        name = payload[i + 3:i + 3 + nlen].decode("utf-8", "replace")
        i += 3 + nlen
        if i + 2 > n:
            break
        vlen = struct.unpack(">H", payload[i:i + 2])[0]
        val = payload[i + 2:i + 2 + vlen]
        i += 2 + vlen
        if tag in (0x21, 0x23):
            v = struct.unpack(">i", val)[0] if len(val) == 4 else int.from_bytes(val or b"\0", "big")
        elif tag in (0x41, 0x42, 0x44):
            v = val.decode("utf-8", "replace")
        elif tag == 0x22:
            v = bool(val and val[0])
        else:
            v = val
        attrs.setdefault(name, []).append(v)
    return attrs, code


def _ipp_attr(tag, name, value):
    n = name.encode()
    v = value.encode() if isinstance(value, str) else bytes(value)
    return bytes([tag]) + struct.pack(">H", len(n)) + n + struct.pack(">H", len(v)) + v


def ipp_jobs(host, port=631, path=IPP_PATH, timeout=6, which="not-completed"):
    """IPP Get-Jobs：列出队列任务。返回 (ok, jobs, err)。"""
    body = b"\x01\x01" + struct.pack(">H", 0x000A) + struct.pack(">I", 1) + b"\x01"
    body += _ipp_attr(0x47, "attributes-charset", "utf-8")
    body += _ipp_attr(0x48, "attributes-natural-language", "en")
    body += _ipp_attr(0x45, "printer-uri", "ipp://%s:%d%s" % (host, port, path))
    body += _ipp_attr(0x44, "which-jobs", which)
    for a in ("job-id", "job-name", "job-state", "job-state-reasons", "job-impressions-completed"):
        body += _ipp_attr(0x44, "requested-attributes", a)
    body += b"\x03"
    try:
        attrs, code = _ipp_parse(_ipp_http(host, port, path, body, timeout))
    except OSError as e:
        return False, [], "IPP 连不上 %s:%d (%s)" % (host, port, e)
    except Exception as e:  # noqa: BLE001
        return False, [], "IPP 查询失败 (%s)" % e
    if code >= 0x0400:
        return False, [], "IPP 返回错误码 0x%04x" % code
    ids = attrs.get("job-id") or []
    names = attrs.get("job-name") or []
    states = attrs.get("job-state") or []
    reasons = attrs.get("job-state-reasons") or []
    compl = attrs.get("job-impressions-completed") or []
    JOB_STATE = {3: "pending", 4: "pending-held", 5: "processing", 6: "processing-stopped",
                 7: "canceled", 8: "aborted", 9: "completed"}
    jobs = []
    for k, jid in enumerate(ids):
        jobs.append({
            "job-id": jid,
            "job-name": names[k] if k < len(names) else "",
            "state": JOB_STATE.get(states[k] if k < len(states) else None,
                                   states[k] if k < len(states) else None),
            "reasons": [reasons[0]] if reasons and len(ids) == 1 else [],
            "impressions": compl[k] if k < len(compl) else None,
        })
    return True, jobs, None


def ipp_cancel(host, job_id, port=631, path=IPP_PATH, timeout=6, user="print-agent"):
    """IPP Cancel-Job：撤掉队列里的任务。返回 (ok, msg)。"""
    body = b"\x01\x01" + struct.pack(">H", 0x0008) + struct.pack(">I", 1) + b"\x01"
    body += _ipp_attr(0x47, "attributes-charset", "utf-8")
    body += _ipp_attr(0x48, "attributes-natural-language", "en")
    body += _ipp_attr(0x45, "printer-uri", "ipp://%s:%d%s" % (host, port, path))
    body += _ipp_attr(0x21, "job-id", struct.pack(">i", int(job_id)))
    body += _ipp_attr(0x42, "requesting-user-name", user)
    body += b"\x03"
    try:
        _attrs, code = _ipp_parse(_ipp_http(host, port, path, body, timeout))
    except Exception as e:  # noqa: BLE001
        return False, "撤单失败 (%s)" % e
    if code in (0x0000, 0x0001):
        return True, "已撤单 job #%s" % job_id
    return False, "撤单被拒，IPP 状态码 0x%04x（任务可能已开始打印或已结束）" % code


def _ber_len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _ber_tlv(tag, value):
    return bytes([tag]) + _ber_len(len(value)) + value


def _ber_int(v):
    if v == 0:
        return _ber_tlv(0x02, b"\x00")
    # minimal two's complement
    length = 1
    while True:
        try:
            b = v.to_bytes(length, "big", signed=True)
            if not (len(b) > 1 and ((b[0] == 0x00 and b[1] < 0x80) or (b[0] == 0xFF and b[1] >= 0x80))):
                return _ber_tlv(0x02, b)
        except OverflowError:
            pass
        length += 1


def _ber_oid(oid):
    parts = [int(x) for x in oid.split(".")]
    out = bytearray([40 * parts[0] + parts[1]])
    for p in parts[2:]:
        if p < 0x80:
            out.append(p)
        else:
            stack = [p & 0x7F]
            p >>= 7
            while p:
                stack.append(0x80 | (p & 0x7F))
                p >>= 7
            out.extend(reversed(stack))
    return _ber_tlv(0x06, bytes(out))


def _ber_read(buf, i):
    tag = buf[i]; i += 1
    l = buf[i]; i += 1
    if l & 0x80:
        k = l & 0x7F
        l = int.from_bytes(buf[i:i + k], "big"); i += k
    return tag, buf[i:i + l], i + l


def snmp_get(host, oids, community="public", port=161, timeout=4):
    """SNMPv1 GET 多个 OID；返回 (ok, {oid: value}, err)。"""
    varbinds = b"".join(_ber_tlv(0x30, _ber_oid(o) + _ber_tlv(0x05, b"")) for o in oids)
    pdu = _ber_tlv(0xA0, _ber_int(1) + _ber_int(0) + _ber_int(0) + _ber_tlv(0x30, varbinds))
    msg = _ber_tlv(0x30, _ber_int(0) + _ber_tlv(0x04, community.encode()) + pdu)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(timeout)
        s.sendto(msg, (host, port))
        data, _ = s.recvfrom(65535)
    except OSError as e:
        return False, {}, "SNMP 无响应 %s:161 (%s)" % (host, e)
    finally:
        try:
            s.close()
        except Exception:
            pass
    try:
        tag, val, _ = _ber_read(data, 0)
        _, _, rest = _ber_read(data, 0)
        # 依次跳过 version/community，进入 PDU
        i = 0
        _, _, i = _ber_read(data, i)                       # outer SEQUENCE (indices 0..2)
        body_start = 0
        # 重新手工遍历
        _, outer, after = _ber_read(data, 0)
        j = 0
        _, _ver, j = _ber_read(outer, j)
        _, _comm, j = _ber_read(outer, j)
        t, pdu_body, _ = _ber_read(outer, j)
        if t != 0xA2:
            return False, {}, "SNMP 返回错误 PDU 0x%02x" % t
        k = 0
        _, _rid, k = _ber_read(pdu_body, k)
        _, _es, k = _ber_read(pdu_body, k)
        _, _ei, k = _ber_read(pdu_body, k)
        _, vb_list, _ = _ber_read(pdu_body, k)
        out, m = {}, 0
        while m < len(vb_list):
            _, vb, m = _ber_read(vb_list, m)
            _, oid_b, p = _ber_read(vb, 0)
            vtag, vval, _ = _ber_read(vb, p)
            # decode oid
            first = oid_b[0]
            nums = [first // 40, first % 40]
            acc = 0
            for byte in oid_b[1:]:
                acc = (acc << 7) | (byte & 0x7F)
                if not byte & 0x80:
                    nums.append(acc); acc = 0
            oid = ".".join(str(x) for x in nums)
            if vtag == 0x02:
                out[oid] = int.from_bytes(vval, "big", signed=True)
            elif vtag in (0x41, 0x42, 0x43, 0x46):   # Counter32 / Gauge32 / TimeTicks / Counter64
                out[oid] = int.from_bytes(vval, "big")
            elif vtag == 0x04:
                out[oid] = vval.decode("utf-8", "replace")
            else:
                out[oid] = vval.hex()
        return True, out, None
    except Exception as e:  # noqa: BLE001
        return False, {}, "SNMP 解析失败 (%s)" % e


SNMP_OIDS = {
    "1.3.6.1.2.1.43.8.2.1.6.1.1": "tray1_name",     # prtInputName
    "1.3.6.1.2.1.43.8.2.1.9.1.1": "tray1_status",   # prtInputStatus
    "1.3.6.1.2.1.43.8.2.1.10.1.1": "tray1_level",   # prtInputCurrentLevel
    "1.3.6.1.2.1.43.8.2.1.9.1.2": "tray2_status",
    "1.3.6.1.2.1.43.8.2.1.10.1.2": "tray2_level",
    "1.3.6.1.2.1.43.8.2.1.9.1.3": "tray3_status",
    "1.3.6.1.2.1.43.8.2.1.10.1.3": "tray3_level",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--timeout", type=float, default=4)
    ap.add_argument("--community", default="public")
    ap.add_argument("--paper", choices=["a4", "a3"], help="按本次要打的纸型只校验对应纸盒（A4=纸盒1，A3=纸盒2）")
    ap.add_argument("--trays", default="1,2",
                    help="真正在用纸的纸盒（逗号分隔，默认 1,2；其余纸盒余量清零只当提示，不算故障）")
    ap.add_argument("--min-level", type=int, default=10, help="余量低于该百分比视为即将缺纸（默认 10）")
    ap.add_argument("--ipp", action="store_true")
    ap.add_argument("--snmp", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--oid", action="append", default=[], help="任意 SNMP OID，可重复；只查这些 OID 并打印")
    ap.add_argument("--jobs", action="store_true", help="列出队列里未完成的任务")
    ap.add_argument("--cancel", type=int, metavar="JOBID", help="撤掉指定队列任务")
    ap.add_argument("--usage", action="store_true", help="用计数器历史算本月印量")
    ap.add_argument("--snapshot", action="store_true", help="把当前总计数器写进历史（print-run 自动调用）")
    a = ap.parse_args()
    if a.jobs:
        ok, jobs, err = ipp_jobs(a.host, timeout=max(a.timeout, 6))
        if a.json:
            print(json.dumps({"ok": ok, "jobs": jobs, "error": err}, ensure_ascii=False, indent=2))
        elif not ok:
            print("查队列失败: %s" % err)
        elif not jobs:
            print("队列空闲：没有未完成的任务")
        else:
            print("队列 %d 个任务：" % len(jobs))
            for j in jobs:
                print("  #%s  %s  状态=%s  已印=%s" % (j["job-id"], j["job-name"] or "(无名称)",
                                                     j["state"], j["impressions"]))
        return 0 if ok else 2

    if a.cancel is not None:
        ok, msg = ipp_cancel(a.host, a.cancel, timeout=max(a.timeout, 6))
        print(msg)
        return 0 if ok else 1

    if a.usage or a.snapshot:
        ok, vals, err = snmp_get(a.host, [COUNTER_OID], community=a.community, timeout=a.timeout)
        if not ok or COUNTER_OID not in vals:
            print("取总计数器失败: %s" % (err or "无返回"), file=sys.stderr)
            return 2
        cur = int(vals[COUNTER_OID])
        hist = []
        try:
            with open(HISTORY, "r", encoding="utf-8") as f:
                hist = json.load(f)
        except Exception:  # noqa: BLE001
            hist = []
        if a.snapshot:
            hist.append({"ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "counter": cur})
            hist = hist[-2000:]
            os.makedirs(STATE_DIR, exist_ok=True)
            tmp = HISTORY + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(hist, f, ensure_ascii=False, indent=1)
            os.replace(tmp, HISTORY)
        month = datetime.datetime.now().strftime("%Y-%m")
        mh = [h for h in hist if str(h.get("ts", "")).startswith(month)]
        if a.json:
            print(json.dumps({"counter": cur, "month": month,
                              "month_start": mh[0]["counter"] if mh else None,
                              "month_pages": (cur - mh[0]["counter"]) if mh else None}, ensure_ascii=False))
        else:
            print("总印量（累计）: %d 页" % cur)
            if mh:
                print("本月(%s) 首次快照 %s = %d 页；本月已印 %d 页" % (month, mh[0]["ts"], mh[0]["counter"], cur - mh[0]["counter"]))
            else:
                print("本月暂无历史快照，已记录当前值作为起点")
        return 0

    if a.oid:
        ok, vals, err = snmp_get(a.host, a.oid, community=a.community, timeout=a.timeout)
        if not ok:
            print("SNMP 失败: %s" % err, file=sys.stderr)
            return 2
        for o in a.oid:
            print("%s = %s" % (o, vals.get(o, "(无此 OID)")))
        return 0

    watch = [x.strip() for x in str(a.trays).split(",") if x.strip()]
    if a.paper:
        watch = [PAPER_TRAY[a.paper]]
    do_ipp = a.ipp or not (a.ipp or a.snmp)
    do_snmp = a.snmp or not (a.ipp or a.snmp)

    report = {"host": a.host, "ipp": None, "snmp": None, "watch_trays": watch,
              "problems": [], "notes": [], "verdict": "unknown"}
    blocking, notes = [], []
    ipp_state = None

    if do_ipp:
        ok, attrs, err = ipp_status(a.host, timeout=a.timeout)
        if ok:
            state = (attrs.get("printer-state") or [None])[0]
            ipp_state = STATE.get(state, state)
            reasons = attrs.get("printer-state-reasons") or []
            report["ipp"] = {
                "state": ipp_state,
                "reasons": reasons,
                "accepting": (attrs.get("printer-is-accepting-jobs") or [None])[0],
                "queued": (attrs.get("queued-job-count") or [None])[0],
                "marker_levels": attrs.get("marker-levels") or [],
            }
            if ipp_state == "stopped":
                blocking.append("IPP:打印机已停机(stopped)")
            for r in reasons:
                if not isinstance(r, str) or r == "none":
                    continue
                if "media-empty" in r or "media-needed" in r:
                    notes.append("IPP:" + r + "(待与纸盒余量交叉核对)")
                else:
                    blocking.append("IPP:" + r)
        else:
            report["ipp"] = {"error": err}
            blocking.append(err)

    snmp_ok = False
    if do_snmp:
        ok, vals, err = snmp_get(a.host, list(SNMP_OIDS), community=a.community, timeout=a.timeout)
        if ok:
            snmp_ok = True
            trays = {}
            for oid, key in SNMP_OIDS.items():
                if oid in vals:
                    trays[key] = vals[oid]
            report["snmp"] = trays
            for i in (1, 2, 3, 4, 5):
                st = trays.get("tray%d_status" % i)
                lv = trays.get("tray%d_level" % i)
                name = trays.get("tray%d_name" % i)
                name = ("纸盒%d" % i) if not isinstance(name, str) else name
                if st is None and lv is None:
                    continue
                label = INPUT_STATUS.get(st, st)
                watched = str(i) in watch
                if label in ("jam", "offline", "paper-problem", "door-open"):
                    blocking.append("SNMP:%s 状态=%s" % (name, label))
                elif label == "empty" or (isinstance(lv, int) and lv == 0):
                    (blocking if watched else notes).append(
                        "SNMP:%s 纸量 0%%" % name)
                elif isinstance(lv, int) and lv < a.min_level:
                    (blocking if watched else notes).append(
                        "SNMP:%s 纸量仅 %d%%" % (name, lv))
        else:
            report["snmp"] = {"error": err}
            if not (report["ipp"] and "error" not in report["ipp"]):
                blocking.append(err)

    # media-empty 只有在「受监视纸盒都没纸」或「打印机停机」时才算故障
    watch_levels = []
    if report["snmp"] and "error" not in report["snmp"]:
        for i in watch:
            lv = report["snmp"].get("tray%s_level" % i)
            if isinstance(lv, int):
                watch_levels.append(lv)
    media_notes = [x for x in notes if x.startswith("IPP:media-empty") or x.startswith("IPP:media-needed")]
    if media_notes and (ipp_state == "stopped" or (watch_levels and max(watch_levels) <= 0)):
        blocking.extend(media_notes)
        notes = [x for x in notes if x not in media_notes]

    report["problems"] = blocking
    report["notes"] = notes
    if blocking:
        report["verdict"] = "problem"
    elif report["ipp"] and "error" not in report["ipp"]:
        report["verdict"] = "ok"
    elif snmp_ok:
        report["verdict"] = "ok"
    else:
        report["verdict"] = "unknown"

    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        ipp = report["ipp"] or {}
        print("打印机 %s" % a.host)
        if "error" in ipp:
            print("  IPP : %s" % ipp["error"])
        else:
            print("  IPP : 状态=%s 可接收任务=%s 队列=%s" % (ipp.get("state"), ipp.get("accepting"), ipp.get("queued")))
            print("        原因=%s" % (", ".join(ipp.get("reasons") or ["none"])))
        sn = report["snmp"] or {}
        if "error" in sn:
            print("  SNMP: %s" % sn["error"])
        elif sn:
            for i in ("1", "2", "3", "4", "5"):
                if "tray%s_status" % i in sn or "tray%s_level" % i in sn:
                    st = sn.get("tray%s_status" % i)
                    lv = sn.get("tray%s_level" % i)
                    print("        纸盒%s: %s 余量=%s%s" % (i, INPUT_STATUS.get(st, st), lv,
                          "" if i in watch else "（不在用纸纸盒，仅提示）"))
        print("  结论: %s" % report["verdict"])
        for x in report["problems"]:
            print("        故障: %s" % x)
        for x in report["notes"]:
            print("        提示: %s" % x)

    return 0 if report["verdict"] == "ok" else (1 if report["verdict"] == "problem" else 2)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收集每周模型任务的最近一次产出（只读 lcm.db），写入 state/weekly-reports/。"""
import argparse, datetime as dt, os, sqlite3, sys

DB = "/home/j/.openclaw/lcm.db"
W = "/home/j/.openclaw/workspace"
OUT = os.path.join(W, "state", "weekly-reports")

# 任务自己落盘的权威产物：当最终回复过短（如 NO_REPLY 静默）时优先读这里
ARTIFACTS = {
    "selfcheck": os.path.join(W, "state", "selfcheck-weekly.md"),
    "pkg-review": os.path.join(W, "state", "pkg-upgrade-report.md"),
}

JOBS = [
    ("5bcf0636-af4a-4346-9e51-ba21c5664038", "zhoujie", "周结"),
    ("2fd10b3c-1882-4789-8ec1-3f1f7d41bba4", "selfcheck", "selfcheck-weekly"),
    ("da85600a-1a4d-42cd-a7ac-a3b64714ad9d", "guanjia-shencha", "管家定期审查"),
    ("58570794-a1b5-436a-9017-09f7731d557d", "paiqi-tijian", "定时任务排期体检"),
    ("330261ca-5dcf-42fc-b2a1-c625a5cf4f69", "pkg-review", "pkg-upgrade-review"),
    ("6ec8ec62-442a-4372-a146-05300d0da962", "recovery-doc", "recovery-doc-review"),
]

def fmt_ts(v):
    if isinstance(v, (int, float)):
        return dt.datetime.fromtimestamp(v/1000).strftime("%Y-%m-%d %H:%M")
    s = str(v)
    if s.isdigit():
        return dt.datetime.fromtimestamp(int(s)/1000).strftime("%Y-%m-%d %H:%M")
    return s[:16].replace("T", " ")

def latest_assistant_text(con, cid):
    return con.execute(
        """
        SELECT p.text_content, m.created_at
        FROM messages m JOIN message_parts p ON p.message_id = m.message_id
        WHERE m.conversation_id = ? AND m.role = 'assistant'
          AND p.part_type = 'text' AND p.text_content IS NOT NULL
          AND length(trim(p.text_content)) > 0
        ORDER BY m.seq DESC, p.ordinal DESC LIMIT 1
        """, (cid,)).fetchone()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--outdir", default=OUT)
    a = ap.parse_args()
    cutoff = int((dt.datetime.now().timestamp() - a.days*86400)*1000)
    os.makedirs(a.outdir, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d")
    if not os.path.exists(DB):
        print("ERROR: db missing", file=sys.stderr); return 2
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = []
    for job_id, slug, name in JOBS:
        r = con.execute(
            "SELECT conversation_id, updated_at FROM conversations "
            "WHERE session_key LIKE ? AND updated_at >= ? ORDER BY updated_at DESC LIMIT 1",
            (f"agent:main:cron:{job_id}:%", cutoff)).fetchone()
        path = os.path.join(a.outdir, f"{stamp}-{slug}.md")
        if not r:
            art0 = ARTIFACTS.get(slug)
            if art0 and os.path.exists(art0):
                t0 = open(art0, encoding="utf-8", errors="replace").read()
                am0 = dt.datetime.fromtimestamp(os.path.getmtime(art0)).strftime("%Y-%m-%d %H:%M")
                body = (f"# {name}\n\n- 状态：近 {a.days} 天内无运行记录，改用任务产物文件\n"
                        f"- 文件：{art0}（{am0} 更新）\n- job: {job_id}\n- 字数：{len(t0)}\n\n---\n\n{t0}\n")
                note, chars = "NO_RUN_FILE", len(t0)
            else:
                body, note, chars = f"# {name}\n\n- 状态：近 {a.days} 天内无运行记录\n- job: {job_id}\n", "NO_RECORD", 0
        else:
            cid, _ = r
            got = latest_assistant_text(con, cid)
            art = ARTIFACTS.get(slug)
            art_text = None
            if art and os.path.exists(art):
                try:
                    art_text = open(art, encoding="utf-8", errors="replace").read()
                except Exception:
                    art_text = None
            if (not got or not got[0] or len((got[0] or "").strip()) < 200) and art_text and len(art_text.strip()) >= 200:
                am = dt.datetime.fromtimestamp(os.path.getmtime(art)).strftime("%Y-%m-%d %H:%M")
                body = (f"# {name}\n\n- 来源：任务产物文件 {art}（{am} 更新）\n"
                        f"- job: {job_id}\n- 字数：{len(art_text)}\n\n---\n\n{art_text}\n")
                chars = len(art_text)
                note = "OK_FILE" if not got or not got[0] else "FILE_OVER_TEXT"
            elif not got or not got[0]:
                body, note, chars = (f"# {name}\n\n- 状态：有运行但无 assistant 文本（疑似空跑）\n"
                                     f"- job: {job_id}\n- conversation: {cid}\n"), "EMPTY_OUTPUT", 0
            else:
                text, created = got
                chars = len(text)
                ts = fmt_ts(created)
                body = f"# {name}\n\n- 运行时间：{ts}\n- job: {job_id}\n- 字数：{chars}\n\n---\n\n{text}\n"
                note = "OK" if chars >= 200 else "SHORT"
        open(path, "w", encoding="utf-8").write(body)
        rows.append((name, note, chars, path))
    con.close()
    print(f"收集完成：{a.outdir}")
    for name, note, chars, path in rows:
        print(f"  {note:<12} {name:<20} {chars:>6} 字  {os.path.basename(path)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

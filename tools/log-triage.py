#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""log-triage.py —— 日志四类归类（磁盘 / 权限 / 超时 / 网络）+ 环境附注，零 token、只读

用法:
  tools/log-triage.py --out state/work/20261107-report.md LOG [LOG...]
  tools/log-triage.py LOG                 # 只打印摘要

归类优先级: 磁盘 > 权限 > 环境 > 超时 > 网络 > 其它
每条非空行只进一类，不重复计数；代表行截断 200 字。
"""
import argparse
import os
import re
import sys
import time

CATS = [
    ("磁盘", re.compile(
        r"No space|ENOSPC|磁盘|空间不足|quota|read-only file system|只读文件系统|"
        r"disk full|inode", re.I)),
    ("权限", re.compile(
        r"权限|permission denied|EACCES|EPERM|Access denied|not permitted|"
        r"Operation not permitted|chmod|不是所有者|Authentication failed", re.I)),
    ("环境", re.compile(
        r"failed to execute process|command not found|No such file or directory", re.I)),
    ("超时", re.compile(
        r"超时|timed out|deadline exceeded|ETIMEDOUT|took too long|(?<![a-z])timeout(?![a-z:])", re.I)),
    ("网络", re.compile(
        r"网络|network|ECONNREFUSED|ECONNRESET|EAI_AGAIN|getaddrinfo|connection reset|"
        r"connection refused|HTTP 50[234]|http=50[234]|unreachable", re.I)),
]
MAX_LINE = 200


def classify(line):
    for name, rx in CATS:
        if rx.search(line):
            return name
    return "其它"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--out", default="")
    ap.add_argument("--max-sample", type=int, default=3)
    a = ap.parse_args()

    report = []
    total = 0
    for path in a.logs:
        if not os.path.isfile(path):
            report.append("- `%s`：**文件不存在**（未采集，不猜）" % path)
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = [ln.rstrip("\n") for ln in f]
        stat = os.stat(path)
        buckets = {name: [] for name, _ in CATS}
        buckets["其它"] = 0
        for ln in lines:
            if not ln.strip():
                continue
            total += 1
            c = classify(ln)
            if c == "其它":
                buckets["其它"] += 1
            else:
                buckets[c].append(ln[:MAX_LINE])
        report.append("### `%s`" % path)
        report.append("")
        report.append("- 行数 %d（非空 %d）／大小 %d B／mtime %s"
                      % (len(lines), sum(1 for x in lines if x.strip()),
                         stat.st_size,
                         time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))))
        for name, _ in CATS:
            hits = buckets[name]
            report.append("- **%s**：%d 条" % (name, len(hits)))
            for h in hits[:a.max_sample]:
                report.append("    - `%s`" % h.replace("`", "'"))
            if len(hits) > a.max_sample:
                report.append("    - ……另 %d 条同类" % (len(hits) - a.max_sample))
        report.append("- 其它（正常/信息）：%d 条" % buckets["其它"])
        report.append("")

    header = ["# 日志四类归类报告（磁盘/权限/超时/网络）＋环境附注", "",
              "> 生成 %s；只读扫描，未改动任何被扫文件；非空行合计 %d"
              % (time.strftime("%Y-%m-%d %H:%M"), total),
              "> 归类优先级：磁盘 > 权限 > 环境 > 超时 > 网络 > 其它；每行只计一次", ""]
    out = "\n".join(header + report) + "\n"

    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(out)
        print("written: %s (%d B)" % (a.out, len(out.encode())))
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()

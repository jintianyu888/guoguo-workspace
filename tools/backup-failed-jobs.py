#!/usr/bin/env python3
"""列出「备份相关」且 lastRunStatus 为 error/failed 的自动化任务。
2026-10-24 新建：health-alert.sh 原来用 grep+awk 解析人读表格，
把「备份管家闹钟」行的第 4 列（cron）当成任务名，误报「备份任务失败：cron」。
现在改用 --json 结构化解析，只认真实失败状态。
输出：空格分隔的 name(status)；无失败则输出空。
"""
import json
import subprocess
import sys

KEYS = ("backup", "备份")
BAD = ("error", "failed", "failure", "crash")


def main() -> int:
    try:
        raw = subprocess.run(
            ["openclaw", "automations", "list", "--all", "--json"],
            capture_output=True, text=True, timeout=90,
        ).stdout
        data = json.loads(raw)
    except Exception as exc:  # 解析不了就当没失败，绝不误报
        print("", end="")
        sys.stderr.write("backup-failed-jobs: %s\n" % exc)
        return 0
    out = []
    for job in data.get("jobs", []):
        name = job.get("name") or ""
        if not any(k in name.lower() for k in KEYS):
            continue
        # 只报启用中的任务：停用的一次性/历史任务错误不是当前故障
        if not job.get("enabled"):
            continue
        state = job.get("state") or {}
        status = str(state.get("lastRunStatus") or state.get("lastStatus") or "")
        if status.lower() in BAD:
            out.append("%s(%s)" % (name, status))
    print(" ".join(out[:5]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

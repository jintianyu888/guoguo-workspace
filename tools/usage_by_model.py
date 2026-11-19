#!/usr/bin/env python3
"""Per-model LLM usage report for OpenClaw.

Answers: "which LLM was actually used, and how much (tokens + cost)?" for a lookback window.

Source of truth: `trajectory_runtime_events` rows of type `model.completed` in every
agent DB under ~/.openclaw/agents/<agentId>/agent/openclaw-agent.sqlite.
Each such row is one agent run and carries provider / modelId and
data.usage {input, output, cacheRead, cacheWrite, total, cost.total}.

These numbers were verified to match `openclaw gateway usage-cost` exactly for a
closed day (same tokens, same cost), so this script is a per-model breakdown of
the same data.

Limitations:
  * READ-ONLY. Every DB is opened with mode=ro via a file: URI. Nothing is written.
  * Day buckets are UTC calendar days, matching `openclaw gateway usage-cost`
    (NOT local Asia/Shanghai days). `--days 1` == today's UTC bucket so far.
  * Attribution is per run: if a run switched models mid-flight, the whole run's
    tokens are credited to the final modelId.
  * Cost comes from the runtime's own pricing; models with no price entry
    contribute 0 cost and are counted in `missingCostEntries`.
  * Events are gone if a session transcript was archived/rewritten before the scan.

Usage:
  python3 usage_by_model.py [--days N] [--json]
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sqlite3
import sys
from collections import defaultdict

AGENTS_DIR = os.path.expanduser("~/.openclaw/agents")
UTC = dt.timezone.utc
TOKEN_FIELDS = ("input", "output", "cacheRead", "cacheWrite")


def discover_targets():
    """Return ([(db_path, agent_id), ...], [agent_id without a DB, ...]).

    Agent IDs come from the directory layout ~/.openclaw/agents/<agentId>/agent/,
    so a configured agent with no DB yet is still reported.
    """
    targets, missing = [], []
    for agent_dir in sorted(glob.glob(os.path.join(AGENTS_DIR, "*"))):
        if not os.path.isdir(agent_dir):
            continue
        agent = os.path.basename(agent_dir)
        db_path = os.path.join(agent_dir, "agent", "openclaw-agent.sqlite")
        if os.path.exists(db_path):
            targets.append((db_path, agent))
        else:
            missing.append(agent)
    return targets, missing


def window_start_ms(days: int) -> int:
    """First instant of the oldest UTC calendar day in the window.

    Mirrors `usage-cost --days N`: N UTC dates ending with today.
    """
    today = dt.datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((today - dt.timedelta(days=max(days, 1) - 1)).timestamp() * 1000)


def day_of(ts_iso, fallback_ms: int) -> str:
    try:
        stamp = dt.datetime.fromisoformat(str(ts_iso).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        stamp = dt.datetime.fromtimestamp(fallback_ms / 1000, UTC)
    return stamp.astimezone(UTC).strftime("%Y-%m-%d")


def collect(db_path: str, agent: str, start_ms: int, end_ms: int, start_date: str,
            rows_out: list, warnings: list):
    """Append per-(date, agent, model) aggregates for in-window model.completed events."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        try:
            cursor = con.execute(
                "SELECT event_json, created_at FROM trajectory_runtime_events "
                "WHERE created_at >= ? AND created_at < ?",
                (start_ms, end_ms),
            )
        except sqlite3.Error as exc:  # table absent in a fresh agent DB
            warnings.append(f"{agent}: skipped ({exc})")
            return
        agg = defaultdict(lambda: {"calls": 0, "cost": 0.0, "total": 0, "missingCost": 0,
                                   **{f: 0 for f in TOKEN_FIELDS}})
        for event_json, created_at in cursor:
            try:
                event = json.loads(event_json)
            except json.JSONDecodeError:
                warnings.append(f"{agent}: unparseable event, skipped")
                continue
            if event.get("type") != "model.completed":
                continue
            usage = (event.get("data") or {}).get("usage") or {}
            if not usage:
                continue
            day = day_of(event.get("ts"), created_at)
            if day < start_date:  # belt-and-braces: never report outside the window
                continue
            model = (event.get("provider") or "unknown", event.get("modelId") or "unknown")
            bucket = agg[(day, model)]
            bucket["calls"] += 1
            for field in TOKEN_FIELDS:
                bucket[field] += int(usage.get(field) or 0)
            total = usage.get("total")
            bucket["total"] += int(total) if total else sum(int(usage.get(f) or 0) for f in TOKEN_FIELDS)
            cost = (usage.get("cost") or {}).get("total")
            if cost is None:
                bucket["missingCost"] += 1
            else:
                bucket["cost"] += float(cost)
    finally:
        con.close()

    for (date, model), bucket in agg.items():
        rows_out.append({"date": date, "agent": agent, "provider": model[0], "model": model[1], **bucket})


def human(n: int) -> str:
    for limit, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(n) >= limit:
            return f"{n / limit:.2f}{suffix}"
    return str(n)


def summarize(rows: list) -> dict:
    keys = TOKEN_FIELDS + ("total", "cost", "calls", "missingCost")
    return {k: sum(r[k] for r in rows) for k in keys}


def render_text(rows: list, days: int) -> str:
    ordered = sorted(rows, key=lambda r: -r["total"])
    label = lambda r: f"{r['provider']}/{r['model']}"  # noqa: E731
    width = max([len(label(r)) for r in ordered] + [5])
    multi_day = len({r["date"] for r in ordered}) > 1
    date_prefix = f"{'DATE':<10}  " if multi_day else ""

    def line(name, r, prefix=""):
        return (f"{prefix}{name:<{width}}  {r['calls']:>6}  {human(r['input']):>9}  "
                f"{human(r['output']):>9}  {human(r['cacheRead']):>9}  {human(r['total']):>9}  "
                f"{r['cost']:>10.4f}")

    out = [f"{date_prefix}{'MODEL':<{width}}  {'CALLS':>6}  {'INPUT':>9}  {'OUTPUT':>9}  "
           f"{'CACHE_RD':>9}  {'TOTAL':>9}  {'COST($)':>10}"]
    out.append("-" * len(out[0]))
    for r in ordered:
        out.append(line(label(r), r, f"{r['date']:<10}  " if multi_day else ""))
    t = summarize(ordered)
    out.append("-" * len(out[0]))
    out.append(line("TOTAL", t))
    out.append("")
    out.append(f"window: last {days} UTC day(s)   "
               f"models: {len({label(r) for r in ordered})}   "
               f"agents: {len({r['agent'] for r in ordered})}   "
               f"missing-cost entries: {t['missingCost']}")
    return "\n".join(out)


def render_json(rows: list, days: int) -> str:
    per_model = {}
    for r in rows:
        key = f"{r['provider']}/{r['model']}"
        entry = per_model.setdefault(key, {
            "provider": r["provider"], "model": r["model"], "calls": 0,
            "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0,
            "totalTokens": 0, "totalCost": 0.0, "missingCostEntries": 0, "dailyTokens": {},
        })
        entry["calls"] += r["calls"]
        entry["totalTokens"] += r["total"]
        entry["totalCost"] += r["cost"]
        entry["missingCostEntries"] += r["missingCost"]
        for f in TOKEN_FIELDS:
            entry[f] += r[f]
        entry["dailyTokens"][r["date"]] = entry["dailyTokens"].get(r["date"], 0) + r["total"]
    daily = {}
    for r in rows:
        d = daily.setdefault(r["date"], {f: 0 for f in TOKEN_FIELDS} |
                             {"totalTokens": 0, "totalCost": 0.0, "calls": 0,
                              "missingCostEntries": 0, "models": {}})
        d["calls"] += r["calls"]
        d["totalTokens"] += r["total"]
        d["totalCost"] += r["cost"]
        d["missingCostEntries"] += r["missingCost"]
        for f in TOKEN_FIELDS:
            d[f] += r[f]
        d["models"][f"{r['provider']}/{r['model']}"] = {
            "calls": r["calls"], **{f: r[f] for f in TOKEN_FIELDS},
            "totalTokens": r["total"], "totalCost": r["cost"],
        }
    t = summarize(rows)
    return json.dumps({
        "days": days,
        "timezone": "UTC",
        "generatedAt": dt.datetime.now(UTC).isoformat(),
        "agentsScanned": sorted({r["agent"] for r in rows}),
        "models": per_model,
        "daily": [{"date": d, **daily[d]} for d in sorted(daily)],
        "totals": {
            "calls": t["calls"], "input": t["input"], "output": t["output"],
            "cacheRead": t["cacheRead"], "cacheWrite": t["cacheWrite"],
            "totalTokens": t["total"], "totalCost": t["cost"],
            "missingCostEntries": t["missingCost"],
        },
    }, indent=2)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Per-model LLM usage/cost report from OpenClaw agent DBs.")
    parser.add_argument("--days", type=int, default=1, help="lookback window in UTC calendar days (default 1)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error("--days must be >= 1")

    start_ms = window_start_ms(args.days)
    end_ms = int(dt.datetime.now(UTC).timestamp() * 1000) + 1
    start_date = dt.datetime.fromtimestamp(start_ms / 1000, UTC).strftime("%Y-%m-%d")
    rows: list = []
    warnings: list = []
    targets, missing = discover_targets()
    for agent in missing:
        warnings.append(f"{agent}: no agent DB yet, skipped")
    for db_path, agent in targets:
        try:
            with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True):
                pass
        except sqlite3.Error as exc:
            warnings.append(f"{agent}: cannot open ({exc})")
            continue
        collect(db_path, agent, start_ms, end_ms, start_date, rows, warnings)

    if args.json:
        print(render_json(rows, args.days))
    elif not rows:
        print(f"No model.completed events in the last {args.days} UTC day(s).")
    else:
        print(render_text(rows, args.days))
    if warnings and not args.json:
        print("\nwarnings:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

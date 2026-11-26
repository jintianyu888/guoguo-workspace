
#!/usr/bin/env python3
"""backup-policy.py — 全盘备份保留/删除/补齐的唯一决策引擎 (2026-11-26)

规则（单一真源）:
  1) 每份归档必须在 >=2 块不同物理盘上，且其中至少一份在冷档 (h / nas)。不满足 = 受保护，任何盘上都不许删。
  2) 分层槽位 (按归档日期从新到旧取):
       H   : 日5 周4 月3   (冷档主历史)
       NAS : 日3 周2 月1   (冷档镜像)
       E   : 最新3          (温档)
       X   : 最新2          (热档)
       D   : 最新1          (热档)
  3) 超出槽位的副本 -> 先进 _quarantine/日期/，24 小时后仍有 >=2 份才物理删。
  4) 水位: 任一分区 >=88% 追加 EXTEND (由旧到新删超槽副本直到 85%)；>=92% 报 P0。
  5) 只删副本，不删对象；最后一两份永远不动。
用法:
  backup-policy.py                 # dry-run，打印计划
  backup-policy.py --apply         # 执行(隔离/清理/补齐)
  backup-policy.py --apply --repair  # 额外补齐缺失副本
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timedelta
from pathlib import Path

W = Path("/home/j/.openclaw/workspace")
STATE = W / "state/backup"
LOG = W / "state/work/backup-policy.log"
QHOURS = 24

LOCS = [
    ("x",   "/mnt/x/openclaw-backups",                            "hot",  {"daily": 2}),
    ("d",   "/mnt/d/openclaw-backups",                            "hot",  {"daily": 1}),
    ("e",   "/mnt/e/openclaw-backups",                            "warm", {"daily": 3}),
    ("h",   "/mnt/h/openclaw-backups",                            "cold", {"daily": 5, "weekly": 4, "monthly": 3}),
    ("nas", "/mnt/nas/archive/jinyu/openclaw-archives",           "cold", {"daily": 3, "weekly": 2, "monthly": 1}),
]
COLD = {"h", "nas"}
PAT = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})")
NAME = re.compile(r"^(\d{4}-\d{2}-\d{2}T[0-9-]+\.\d+\+\d{2}-\d{2}-openclaw-backup\.tar\.gz)$")


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now():%F %T} {msg}"
    with LOG.open("a") as f:
        f.write(line + "\n")
    print(line)


def scan():
    """name -> {'size':int,'locs':{loc:path}}"""
    inv = {}
    for loc, path, tier, slots in LOCS:
        p = Path(path)
        if not p.is_dir():
            log(f"WARN 不可访问 {loc}:{path}")
            continue
        cand = []
        for f in p.iterdir():
            if f.is_file() and f.name.endswith(".tar.gz"):
                cand.append((f, loc))
            elif f.is_dir() and f.name.startswith("_"):
                for g in f.rglob("*.tar.gz"):
                    cand.append((g, loc + "q"))
        for f, l in cand:
            if not NAME.match(f.name):
                continue
            try:
                sz = f.stat().st_size
            except OSError:
                continue
            e = inv.setdefault(f.name, {"size": sz, "locs": {}})
            e["locs"][l] = str(f)
    return inv


def adm(ts):
    return datetime.now().astimezone() - ts


def dkey(name):
    m = PAT.search(name)
    if not m:
        return None
    return datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}", "%Y-%m-%d %H:%M:%S").astimezone()


def gfs(names):
    """返回各层的 keep 集合"""
    ordered = sorted([n for n in names if dkey(n)], key=dkey, reverse=True)
    daily, weekly, monthly = [], [], []
    seen_d, seen_w, seen_m = set(), set(), set()
    for n in ordered:
        d = dkey(n)
        if d.date() not in seen_d:
            seen_d.add(d.date()); daily.append(n)
        if d.isocalendar()[:2] not in seen_w:
            seen_w.add(d.isocalendar()[:2]); weekly.append(n)
        if (d.year, d.month) not in seen_m:
            seen_m.add((d.year, d.month)); monthly.append(n)
    return {"daily": daily, "weekly": weekly, "monthly": monthly}


def keep_for(loc, slots, g):
    keep = set(g["daily"][: slots.get("daily", 0)])
    keep |= set(g["weekly"][: slots.get("weekly", 0)])
    keep |= set(g["monthly"][: slots.get("monthly", 0)])
    return keep


def du(p):
    try:
        return shutil.disk_usage(p)
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--repair", action="store_true")
    a = ap.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    inv = scan()
    names = [n for n in inv if dkey(n)]
    if not names:
        print("NO_ARCHIVES"); return 1
    g = gfs(names)
    newest = sorted(names, key=dkey, reverse=True)[0]
    plan = {"ts": datetime.now().isoformat(timespec="seconds"), "newest": newest,
            "objects": len(names), "deletes": [], "copies": [], "watermark": [], "protected": []}

    # 每个对象的副本数与冷档覆盖
    for n, e in inv.items():
        e["copies"] = len(e["locs"])
        e["cold"] = bool(set(e["locs"]) & COLD)

    # 槽位删除
    for loc, path, tier, slots in LOCS:
        keep = keep_for(loc, slots, g)
        for n in sorted([x for x in inv if loc in inv[x]["locs"]], key=dkey):
            if n in keep or loc.endswith("q"):
                continue
            e = inv[n]
            rest = set(e["locs"]) - {loc}
            if n == newest:
                plan["protected"].append(f"{loc}:{n} 最新档不删"); continue
            if len(rest) < 2 or not (rest & COLD):
                plan["protected"].append(f"{loc}:{n} 删除后仅{len(rest)}份/冷档{bool(rest & COLD)}，受保护")
                continue
            plan["deletes"].append({"loc": loc, "name": n, "size": e["size"],
                                    "why": f"超{slots}槽位", "rest": len(rest)})

    # 水位延伸
    for loc, path, tier, slots in LOCS:
        u = du(path)
        if not u:
            continue
        pct = u.used / u.total * 100
        plan["watermark"].append({"loc": loc, "pct": round(pct, 1), "free_g": round(u.free / 1e9)})
        if pct >= 88:
            extra = 0
            for n in sorted([x for x in inv if loc in inv[x]["locs"]
                             and not any(d["loc"] == loc and d["name"] == n for d in plan["deletes"])], key=dkey):
                if pct - extra * 100 * inv[n]["size"] / u.total < 85:
                    break
                rest = set(inv[n]["locs"]) - {loc}
                if n == newest or len(rest) < 2 or not (rest & COLD):
                    continue
                plan["deletes"].append({"loc": loc, "name": n, "size": inv[n]["size"],
                                        "why": f"水位{pct:.0f}%延伸", "rest": len(rest)})
                extra += 1

    # 下沉：单副本对象先复制到另一块冷/温盘，之后才允许删原副本
    for n, e in inv.items():
        if e["copies"] > 1:
            continue
        only = next(iter(e["locs"]))
        for tgt in ("h", "e"):
            if tgt == only:
                continue
            u = du(dict((l[0], l[1]) for l in LOCS)[tgt])
            if u and u.free > e["size"] * 1.3:
                plan["copies"].append({"from": e["locs"][only], "to": str(Path(dict((l[0], l[1]) for l in LOCS)[tgt]) / n),
                                       "loc": tgt, "name": n, "why": "SINK 单副本下沉"})
                break

    # 补齐：keep 集合在冷档缺副本
    if a.repair:
        for n in sorted(g["daily"][:5] + g["weekly"][:4], key=dkey, reverse=True):
            e = inv[n]
            src = e["locs"].get("x") or e["locs"].get("e") or e["locs"].get("d") or next(iter(e["locs"].values()))
            for loc, path, tier, slots in LOCS:
                need = loc in ("h", "nas")
                if not need or loc in e["locs"]:
                    continue
                plan["copies"].append({"from": src, "to": str(Path(path) / n), "loc": loc, "name": n})

    # 输出
    rec = sum(d["size"] for d in plan["deletes"])
    print(f"== 对象 {len(names)}  最新 {newest}")
    for w in plan["watermark"]:
        flag = "🔴" if w["pct"] >= 92 else ("🟠" if w["pct"] >= 88 else "🟢")
        print(f"  {flag} {w['loc']}: {w['pct']}% 可用{w['free_g']}G")
    print(f"== 删除 {len(plan['deletes'])} 份  可回收 {rec/1e9:.1f}G  受保护 {len(plan['protected'])}")
    for d in plan["deletes"]:
        print(f"  DEL {d['loc']}: {d['name'][:20]} {d['size']/1e9:.0f}G ({d['why']}, 剩{d['rest']}份)")
    for c in plan["copies"]:
        why = c.get("why", "补齐冷档")
        print(f"  COPY -> {c['loc']}: {c['name'][:20]} ({why})")
    (STATE / f"plan-{datetime.now():%Y%m%d-%H%M}.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    log(f"PLAN objects={len(names)} del={len(plan['deletes'])} reclaim={rec/1e9:.1f}G apply={a.apply}")

    if not a.apply and not a.repair:
        return 0

    # 执行删除：隔离 -> 24h 后物理删（必须 --apply）
    qday = datetime.now().strftime("%Y%m%d")
    done = 0
    if not a.apply:
        plan["deletes"] = []
    for d in plan["deletes"]:
        src = Path(inv[d["name"]]["locs"][d["loc"]])
        base_loc = d["loc"].rstrip("q")
        qdir = Path(dict((l[0], l[1]) for l in LOCS)[base_loc]) / "_quarantine" / qday
        try:
            qdir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(qdir / src.name)); done += 1
            log(f"QUAR {d['loc']}:{src.name} ({d['why']})")
        except Exception as ex:
            log(f"ERR quar {src}: {ex}")

    # 清理超 24h 且别处仍有 >=2 份的隔离件（必须 --apply）
    for loc, path, tier, slots in (LOCS if a.apply else []):
        qroot = Path(path) / "_quarantine"
        if not qroot.is_dir():
            continue
        for sub in qroot.iterdir():
            if not sub.is_dir():
                continue
            for f in sub.glob("*.tar.gz"):
                age_h = (time.time() - f.stat().st_mtime) / 3600
                if age_h < QHOURS:
                    continue
                others = [Path(pp) / f.name for ll, pp, _, _ in LOCS if ll != loc and (Path(pp) / f.name).is_file()]
                cold_ok = any(ll in COLD and (Path(pp) / f.name).is_file() for ll, pp, _, _ in LOCS if ll != loc)
                if len(others) >= 2 and cold_ok:
                    f.unlink(); log(f"PURGE {loc}:{f.name} (剩{len(others)}份)")
                else:
                    log(f"PROTECT {loc}:{f.name} (剩{len(others)}份/冷档{cold_ok})")

    # 补齐
    for c in plan["copies"]:
        dst = Path(c["to"] + ".part")
        try:
            subprocess.run(["rsync", "-a", "--partial", "--append-verify", "--inplace", c["from"], str(dst)],
                           check=True, timeout=7200)
            if dst.stat().st_size == Path(c["from"]).stat().st_size:
                dst.replace(c["to"]); log(f"REPAIR ok {c['loc']}:{Path(c['to']).name}")
            else:
                log(f"REPAIR size-mismatch {c['to']}")
        except Exception as ex:
            log(f"REPAIR fail {c['loc']}: {ex}")
    log(f"APPLY done quarantined={done}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

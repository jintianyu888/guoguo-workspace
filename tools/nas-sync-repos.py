#!/usr/bin/env python3
"""把各管家工作区镜像到群晖分类仓库 + 生成索引 + 输出占用/增减报表。
用法: python3 nas-sync-repos.py [--only <agent>] [--index-only]
策略: rsync -a **不加 --delete**（只增不删，双保险）；
      每仓生成 索引.md（文件清单+大小+日期）。
"""
import argparse, json, os, subprocess, time

NAS = "nas"
BASE = os.path.expanduser("~/.openclaw")
REPO = "archive/jinyu/migrated-20261102/openclaw-repos"
STATE = os.path.join(BASE, "workspace/state/nas-repo-state.json")
SSH = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "StrictHostKeyChecking=accept-new"]
EXC = [".git/", "node_modules/", "__pycache__/", ".venv/", ".DS_Store", "*.tmp"]
LABEL = {"main":"🎙️麦克","mom-health":"🩺妈妈健康","tax":"🧾税务","fitness":"🏃运动","wealth":"💰理财",
 "piano-app":"🎹钢琴APP","health-wang":"🩺王爸爸","health-jin":"🩺靳爸爸","health-wife":"🩺媳妇",
 "health-self":"🩺本人","calendar":"📅日程","doll-brand":"🧸玩偶品牌","piano-room":"🎹琴房","cooking":"🍳做饭",
 "sheet-music":"🎼乐谱","print":"🖨️打印","class-schedule":"🗓️排课","script-mystery":"🎭剧本杀",
 "health-doudou":"🩺豆豆健康","schedule-doudou":"📅豆豆日程","doudou-apply":"🎓豆豆申请"}

def sh(a, t=600):
    return subprocess.run(a, capture_output=True, text=True, timeout=t)

def agents():
    out = []
    for d in sorted(os.listdir(BASE)):
        p = os.path.join(BASE, d)
        if not os.path.isdir(p) or not d.startswith("workspace"): continue
        aid = "main" if d == "workspace" else d[len("workspace-"):]
        out.append((aid, p))
    return out

def make_index(aid, path):
    lines = [f"# {LABEL.get(aid, aid)} 仓库索引", "",
             f"> 自动生成：{time.strftime('%Y-%m-%d %H:%M')} · 源：`{path}`", "",
             "> 本仓库由该管家分管；只增不删，便于直接查找。", ""]
    total_files = total_size = 0
    groups = {}
    for r, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
        for f in files:
            fp = os.path.join(r, f)
            try: sz = os.path.getsize(fp)
            except OSError: continue
            rel = os.path.relpath(fp, path)
            top = rel.split(os.sep)[0] if os.sep in rel else "（根目录）"
            groups.setdefault(top, []).append((rel, sz))
            total_files += 1; total_size += sz
    lines += [f"**文件数**：{total_files} · **总大小**：{total_size/1048576:.1f} MB", ""]
    for top in sorted(groups):
        items = sorted(groups[top], key=lambda x: -x[1])
        lines.append(f"## {top}（{len(items)} 个）")
        for rel, sz in items[:200]:
            lines.append(f"- `{rel}` — {sz/1024:.0f} KB")
        if len(items) > 200: lines.append(f"- …另有 {len(items)-200} 个")
        lines.append("")
    return "\n".join(lines), total_files, total_size

p = argparse.ArgumentParser(); p.add_argument("--only"); p.add_argument("--index-only", action="store_true")
a = p.parse_args()

prev = {}
if os.path.exists(STATE):
    try: prev = json.load(open(STATE))
    except Exception: prev = {}

rows, new_state = [], dict(prev)
for aid, path in agents():
    if a.only and aid != a.only: continue
    rp = f"{REPO}/{aid}"
    sh(["ssh", *SSH, NAS, f"mkdir -p ~/'{rp}'"])
    if not a.index_only:
        ex = [f"--exclude={e}" for e in EXC]
        t1 = subprocess.Popen(["tar", "--warning=no-file-changed", "czf", "-", "-C", path] + ex + ["."], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        rc = f"mkdir -p ~/{rp} && tar xzf - -C ~/{rp}"
        t2 = subprocess.Popen(["ssh", *SSH, NAS, rc], stdin=t1.stdout,
                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        t1.stdout.close()
        _, err = t2.communicate(timeout=900)
        t1.wait()
        ok = (t2.returncode == 0)
        if not ok:
            print("   ⚠️", (err or b"").decode()[:120])
    else:
        ok = True
    idx, nf, ts = make_index(aid, path)
    tmp = f"/home/j/.openclaw/workspace/state/tmp/idx-{aid}.md"
    open(tmp, "w").write(idx)
    try:
        subprocess.run(["ssh", *SSH, NAS, f"cat > ~/{rp}/索引.md"], stdin=open(tmp),
                       capture_output=True, timeout=120)
    except Exception: pass
    rows.append((aid, nf, ts, ok))

# NAS 实际占用（KB）
out = sh(["ssh", *SSH, NAS, f"du -sk ~/{REPO}/* 2>/dev/null"], 300).stdout
sizes = {}
for line in out.splitlines():
    pr = line.split("\t")
    if len(pr) == 2: sizes[os.path.basename(pr[1].strip())] = int(pr[0])

rows.sort(key=lambda r: -r[2])
print("【群晖分类仓库 · 同步结果】")
print(f"仓库根：~/archive/jinyu/migrated-20261102/openclaw-repos/（{'只增不删' if not a.index_only else '仅重建索引'}）")
for aid, nf, ts, ok in rows:
    cur = sizes.get(aid, 0) / 1024
    old = prev.get(aid)
    delta = "" if old is None else (f"（{'+' if cur-old>=0 else ''}{cur-old:.1f} MB）" if abs(cur-old) >= 0.1 else "（持平）")
    print(f"{LABEL.get(aid,aid)} ({aid}) · {nf} 文件 · {cur:.1f} MB {delta}{'' if ok else ' ⚠️同步有错'}")
    new_state[aid] = round(cur, 1)
tot = sum(sizes.get(a, 0) for a, _, _, _ in rows) / 1024
print(f"合计：{tot:.0f} MB")
try:
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(new_state, open(STATE, "w"), ensure_ascii=False, indent=1)
except Exception: pass

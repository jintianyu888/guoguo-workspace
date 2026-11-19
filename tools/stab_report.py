import sys,os,json,datetime
tsv,outd,deep=sys.argv[1],sys.argv[2],sys.argv[3]
rows=[]
for line in open(tsv,encoding="utf-8"):
    line=line.rstrip("\n")
    if not line.strip(): continue
    p=line.split("\t")
    if len(p)<5: continue
    rows.append({"ring":p[0],"id":p[1],"status":p[2],"value":p[3],"threshold":p[4],"source":p[5] if len(p)>5 else ""})
def cnt(s): return sum(1 for r in rows if r["status"]==s)
P,W,F,S=cnt("PASS"),cnt("WARN"),cnt("FAIL"),cnt("SKIP")
rc=2 if F>0 else (1 if W>0 else 0)
verdict={0:"PASS",1:"WARN",2:"FAIL"}[rc]
ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
json.dump({"ts":ts,"deep":deep=="1","rc":rc,"verdict":verdict,"counts":{"pass":P,"warn":W,"fail":F,"skip":S},"items":rows},
          open(os.path.join(outd,"latest.json"),"w",encoding="utf-8"),ensure_ascii=False,indent=1)
names={"A":"硬件","B":"系统(WSL+Win)","C":"OpenClaw"}
lines=["# 系统稳定性审查 %s（%s）" % (ts, "深度" if deep=="1" else "常规"),
       "结论：%s · PASS %d / WARN %d / FAIL %d / SKIP %d" % (verdict,P,W,F,S),""]
for ring in ("A","B","C"):
    sub=[r for r in rows if r["ring"]==ring]
    if not sub: continue
    lines.append("## %s · %s" % (ring,names.get(ring,ring)))
    for r in sub:
        mark={"PASS":"✅","WARN":"⚠️","FAIL":"❌","SKIP":"⏭️"}.get(r["status"],"?")
        lines.append("- %s %s：%s%s" % (mark, r["id"], r["value"], ("（阈值 "+r["threshold"]+"）") if r["threshold"] else ""))
    lines.append("")
def _atomic(path, data):
    tmp = path + ".tmp.%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

_atomic(os.path.join(outd,"latest.md"), "\n".join(lines) + "\n")
# 历史留档：同日覆盖，仅保留最近 14 天
try:
    import datetime, glob
    day = datetime.date.today().isoformat()
    _atomic(os.path.join(outd, "%s.json" % day), json.dumps(
        {"ts":ts,"deep":deep=="1","rc":rc,"verdict":verdict,
         "counts":{"pass":P,"warn":W,"fail":F,"skip":S},"items":rows}, ensure_ascii=False, indent=1))
    hist = sorted(glob.glob(os.path.join(outd, "20*.json")))
    for old in hist[:-14]:
        os.remove(old)
except Exception:
    pass
print(rc)
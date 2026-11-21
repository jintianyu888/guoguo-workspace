#!/usr/bin/env bash
# advice.sh v1.0 (2026-11-21 主公令) —— 双顾问"秘书"统一入口
# 作用：任何管家要提升方案质量，都从这里发起；统一模板、统一预算、统一留痕。
# 顾问：qwen（千问，找更优解/替代路径，便宜）｜glm（智谱，找风险/错误/漏项）
# 用法：
#   bash tools/advice.sh <方案文件|-> [--advisor qwen|glm|both] [--goal 文本] [--level L1|L2|L3]
#   bash tools/advice.sh --stats
set -o pipefail
WS=/home/j/.openclaw/workspace
D=$WS/state/advice
mkdir -p "$D"
BUD="$D/budget.json"
CALLS="$D/calls.jsonl"
[ -f "$BUD" ] || echo '{"date":"","qwen":{"cap":20,"used":0},"glm":{"cap":12,"used":0}}' > "$BUD"
if [ "$1" = "--adopt" ]; then
  ID="$2"; NOTE="$3"
  python3 - "$D" "$ID" "$NOTE" <<'PY'
import json,sys,os
d,ts,note=sys.argv[1],sys.argv[2],sys.argv[3]
f=os.path.join(d,"calls.jsonl")
out=[]; hit=0
if os.path.exists(f):
    for line in open(f):
        try: r=json.loads(line)
        except Exception: out.append(line); continue
        if r.get("ts")==ts: r["adopted"]=True; r["note"]=note; hit+=1
        out.append(json.dumps(r,ensure_ascii=False)+"\n")
open(f,"w").writelines(out)
print("已标记采纳：%s（%d 条）%s" % (ts, hit, ("｜"+note) if note else ""))
PY
  exit 0
fi
if [ "$1" = "--stats" ]; then
  python3 - "$BUD" "$CALLS" <<'PY'
import json,sys,os,collections
bud=json.load(open(sys.argv[1])); calls=sys.argv[2]
n=0; adv=collections.Counter(); adopts=0
if os.path.exists(calls):
    for line in open(calls):
        try: r=json.loads(line)
        except Exception: continue
        n+=1; adv[r.get("advisor")]+=1
        if r.get("adopted"): adopts+=1
print("顾问调用：共 %d 次 %s｜采纳 %d 次（采纳率 %s%%）" % (n, dict(adv), adopts, round(adopts*100.0/n,1) if n else 0))
print("今日预算：", json.dumps(bud, ensure_ascii=False))
PY
  exit 0
fi
SRC="$1"; shift 2>/dev/null || true
ADV="both"; GOAL=""; LEVEL="L2"
while [ $# -gt 0 ]; do case "$1" in --advisor) ADV="$2"; shift; shift;; --goal) GOAL="$2"; shift; shift;; --level) LEVEL="$2"; shift; shift;; *) shift;; esac; done
[ -z "$SRC" ] && { echo "usage: bash tools/advice.sh <方案文件|-> [--advisor qwen|glm|both] [--goal 文本] [--level L1|L2|L3]"; exit 2; }
if [ "$SRC" = "-" ]; then PLAN="$(cat)"; else [ -f "$SRC" ] || { echo "FAIL 找不到方案文件 $SRC"; exit 1; }; PLAN="$(cat "$SRC")"; fi
python3 - "$BUD" "$ADV" <<'PY'
import json,sys,datetime
p,adv=sys.argv[1],sys.argv[2]
d=json.load(open(p)); today=datetime.date.today().isoformat()
if d.get("date")!=today:
    d={"date":today,"qwen":{"cap":d.get("qwen",{}).get("cap",20),"used":0},"glm":{"cap":d.get("glm",{}).get("cap",12),"used":0}}
need=["qwen","glm"] if adv=="both" else [adv]
for k in need:
    b=d.get(k,{"cap":20,"used":0})
    if b["used"]>=b["cap"]:
        print("BUDGET_EXCEEDED %s %d/%d" % (k,b["used"],b["cap"])); sys.exit(3)
for k in need: d[k]["used"]=d[k].get("used",0)+1
json.dump(d,open(p,"w"),ensure_ascii=False,indent=1)
print("BUDGET_OK " + " ".join("%s %d/%d" % (k,d[k]["used"],d[k]["cap"]) for k in need))
PY
RC=$?
[ "$RC" -ne 0 ] && { echo "顾问当日预算已用完，改用 deepseek 自审或排队到明天"; exit 3; }
TS=$(date +%Y%m%d-%H%M%S)
LEVEL="$LEVEL" GOAL="$GOAL" python3 - "$D" "$TS" "$ADV" "$SRC" "$PLAN" <<'PY'
import json,os,sys,datetime
D,ts,adv,src,plan=sys.argv[1:6]
goal=os.environ.get("GOAL") or "(未给出，按方案正文推断)"
level=os.environ.get("LEVEL","L2")
profiles={
 "qwen":{"name":"顾问·千问","model":"qianwen-token-plan/qwen4-max",
         "focus":"更优解与替代路径：有没有更省/更快/更稳的干法；有没有被忽略的现成能力；成本与收益差"},
 "glm":{"name":"顾问·智谱","model":"zai/glm-5.3",
        "focus":"风险与漏项：会怎么失败、边界条件、合规与权限、验收标准缺失、回滚缺口"},
}
made=[]
for k in (["qwen","glm"] if adv=="both" else [adv]):
    pr=profiles[k]
    body="""你在扮演【%s】，只做一件事：把下面这份方案改得更好。你不执行、不写文件、不发外部消息。

目标：%s
风险级别：%s

你的专责角度：%s

硬性要求：
1) 不夸、不复述方案，直接给问题与改进；
2) 不许编造数据或来源；引用我们自己的东西必须给文件路径，取不到就写"不确定"；
3) 每条改进都要能落地，带"怎么改"和"怎么验"；
4) 全文不超过 600 字。

输出固定五段：
① 致命问题（≤3 条，写清触发条件）
② 漏项（≤7 条，每条一句补法）
③ 更优解（≤3 条，写清成本/风险差）
④ 可验收标准（能机器判定的优先）
⑤ 一句话结论：可执行 / 需修改后执行 / 建议否决（附最关键的 1 条理由）

=== 方案正文 ===
%s""" % (pr["name"], goal, level, pr["focus"], plan)
    fp=os.path.join(D, "%s-%s.md" % (ts,k))
    open(fp,"w").write(body)
    made.append((k,pr["name"],pr["model"],fp))
    with open(os.path.join(D,"calls.jsonl"),"a") as f:
        f.write(json.dumps({"ts":ts,"advisor":k,"model":pr["model"],"goal":goal,"level":level,"src":src,"prompt_file":fp,"adopted":False}, ensure_ascii=False)+"\n")
for k,name,model,fp in made:
    print("【%s】model=%s" % (name, model))
    print("  prompt=%s" % fp)
print("max_tokens 建议：千问 6000（它会先用思考额度，给小了只回空正文）；智谱 2000")
print("调用方式（任一管家）：用 sessions_spawn 起子会话，model=%s，message=上面 prompt 文件内容；拿到结论后回填：bash tools/advice.sh --adopt %s [--note 采纳了什么]" % (made[0][2] if len(made)==1 else "qianwen-token-plan/qwen4-max / zai/glm-5.3", ts))
PY

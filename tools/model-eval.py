#!/usr/bin/env python3
"""model-eval.py — 统一模型评测：quick(2题) / full(题库全量)，结果留档并追加台账。
用法: python3 tools/model-eval.py <provider/model> [quick|full] [备注]
台账: docs/模型评测台账.md  历史: state/eval/history/"""
import subprocess, time, json, re, sys, os, datetime
WS="/home/j/.openclaw/workspace"
HIS=os.path.join(WS,"state/eval/history")
LEDGER=os.path.join(WS,"docs/模型评测台账.md")
PRICE={"deepseek/deepseek-flash":(1,0.2,2),"deepseek/deepseek-v4-pro":(0.25,0.05,1),
 "zai/glm-5.3":(8,2,28),"zai/glm-5.3-flash":(0.8,0,2.8),"moonshot/kimi-k2.6":(6.8,1.1,28.6),
 "ollama/qwen3:30b-a3b-instruct-2507-q4_K_M":(0,0,0),"ollama/qwen3:14b":(0,0,0)}
P1="用一句话回答：9.11 和 9.9 哪个大？只输出答案，不要解释。"
P2="写一个 Python 函数 longest_unique(s) 返回最长不含重复字符子串的长度。只输出代码，不要解释。"
TESTS=[("abcabcbb",3),("bbbbb",1),("pwwkew",3),("",0)]
def call(m,p,to=240):
    t=time.time()
    try:
        extra=["--thinking","on"] if m.startswith("kimi-coding/kimi-k3.1") else []
        r=subprocess.run(["openclaw","infer","model","run","--agent","main","--gateway","--model",m]+extra+["--prompt",p],capture_output=True,text=True,timeout=to)
        out=r.stdout
    except subprocess.TimeoutExpired:
        return None,"TIMEOUT"
    return round(time.time()-t,1), out.split("outputs: 1",1)[-1].strip()
def check_code(code):
    code=re.sub(r"^```[a-z]*$|^```$","",code,flags=re.M).strip()
    ns={}
    try:
        exec(code,ns); f=ns.get("longest_unique")
        if not f: return "NO_FUNC"
        bad=[s for s,e in TESTS if f(s)!=e]
        return "PASS" if not bad else "WRONG"
    except Exception as ex: return "ERR:"+type(ex).__name__
def main():
    if len(sys.argv)<2: print(__doc__); return 2
    m=sys.argv[1]; mode=sys.argv[2] if len(sys.argv)>2 else "quick"
    note=sys.argv[3] if len(sys.argv)>3 else ""
    os.makedirs(HIS,exist_ok=True)
    ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    s1,o1=call(m,P1)
    q1="PASS" if s1 is not None and re.search(r"9\.9",o1) else "FAIL"
    s2,o2=call(m,P2)
    q2=check_code(o2) if s2 is not None else "TIMEOUT"
    rec={"model":m,"mode":mode,"ts":ts,"t1_s":s1,"t1":q1,"t2_s":s2,"t2":q2,"note":note}
    fn=os.path.join(HIS,"%s-%s.json"%(datetime.datetime.now().strftime("%Y%m%d-%H%M"),m.replace("/","_")))
    json.dump(rec,open(fn,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
    avg=None
    if s1 and s2: avg=round((s1+s2)/2,1)
    row="| %s | %s | %s | %s | %s | %s |"%(ts,m,q1,("%ss"%s1 if s1 else "-"),q2,("%ss"%avg if avg else "-"))
    if not os.path.exists(LEDGER):
        open(LEDGER,"w",encoding="utf-8").write("# 模型评测台账\n\n| 时间 | 模型 | T1 精确 | T1 延迟 | T2 代码 | 平均延迟 |\n|---|---|---|---|---|---|\n")
    open(LEDGER,"a",encoding="utf-8").write(row+"\n")
    print(row)
    print("saved:",fn)
    try:
        import importlib.util as _iu
        _sp=_iu.spec_from_file_location("eval_ledger",os.path.join(WS,"tools/eval-ledger.py"))
        _m=_iu.module_from_spec(_sp); _sp.loader.exec_module(_m)
        _c=_m.conn(); _m.import_json(_c,fn); _c.commit(); _c.close()
        print("ledger: state/eval/eval.db 已同步")
    except Exception as e:
        print("ledger append failed:",e)
    return 0 if q1=="PASS" and q2=="PASS" else 1
if __name__=="__main__": sys.exit(main())
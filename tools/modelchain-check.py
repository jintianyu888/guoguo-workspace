
import json,urllib.request,sys,re
CFG="/home/j/.openclaw/openclaw.json"
d=json.load(open(CFG))
provs=d.get("models",{}).get("providers",{})
known={}
for pname,p in provs.items():
    for m in (p.get("models") or []):
        mid=m.get("id")
        if mid: known[pname+"/"+mid]=True
# 1) collect all model refs
refs=set()
def walk(o):
    if isinstance(o,dict):
        # tools/media 里 model 与 provider 分开写（{provider:"deepseek",model:"deepseek-flash"}），
        # 这种不是 "provider/model" 全名，需要拼起来判断，否则会误报 DANGLING。
        pv=o.get("provider")
        if isinstance(pv,str) and isinstance(o.get("model"),str) and "/" not in o["model"]:
            refs.add(pv+"/"+o["model"])
            for k,v in o.items():
                if k!="model": walk(v)
            return
        for k,v in o.items():
            if k in ("primary","model") and isinstance(v,str): refs.add(v)
            elif k=="fallbacks" and isinstance(v,list):
                for x in v:
                    if isinstance(x,str): refs.add(x)
            walk(v)
    elif isinstance(o,list):
        for v in o: walk(v)
walk(d)
dangling=[r for r in sorted(refs) if r not in known]
# 1b) embedding 模型（如 nomic-embed-text）不是聊天模型，按各自 provider 的 baseUrl 实探 /api/tags 校验
_embed_live={}
for _r in list(dangling):
    _pn,_,_mid = _r.partition("/")
    if "embed" not in _mid: continue
    _bu = (provs.get(_pn) or {}).get("baseUrl") or ""
    if not _bu: continue
    if _bu not in _embed_live:
        try:
            _t=json.load(urllib.request.urlopen(_bu.rstrip("/")+"/api/tags",timeout=8))
            _embed_live[_bu]={m.get("name") for m in _t.get("models",[])}
        except Exception:
            _embed_live[_bu]=None
    _names=_embed_live[_bu]
    if _names and (_mid in _names or _mid+":latest" in _names):
        known[_r]=True
dangling=[r for r in sorted(refs) if r not in known]

# 2) ollama live tags
ollama_refs=[r for r in refs if r.startswith("ollama/")]
live=None; err=None
try:
    tags=json.load(urllib.request.urlopen("http://127.0.0.1:11434/api/tags",timeout=15))
    live={m["name"] for m in tags.get("models",[])}
except Exception as e:
    err=str(e)[:120]
missing_local=[r for r in ollama_refs if live is not None and r.split("/",1)[1] not in live]
print("REFS",len(refs),"| DANGLING",len(dangling),"| OLLAMA",len(ollama_refs))
for r in dangling: print("  FAIL 配置引用不存在:",r)
if err:
    print("  ALARM 本地模型不可查（B机/代理不可达）:",err,"→ 该项判为 UNKNOWN，不放行沉默")
elif missing_local:
    for r in missing_local: print("  FAIL 本地模型未安装:",r)
else:
    print("  PASS 本地模型引用全部在 B 机 tags 中")
if dangling or missing_local: sys.exit(1)
if err: sys.exit(2)
# 停用模型校验（2026-11-01 立）
import os as _os
_mp = "/home/j/.openclaw/workspace/state/model-policy"
_bad = []
if _os.path.isdir(_mp):
    for _fn in _os.listdir(_mp):
        if not _fn.endswith(".json"):
            continue
        try:
            _d = json.load(open(_os.path.join(_mp, _fn), encoding="utf-8"))
        except Exception:
            continue
        if _d.get("status") != "suspended":
            continue
        _m = _d.get("model", "")
        _k = _m.split("/")[-1]
        _hit = [r for r in refs if _k and _k in str(r)]
        if _hit:
            _bad.append((_m, len(_hit)))
if _bad:
    for _m, _n in _bad:
        print("SUSPENDED_VIOLATION " + _m + " 出现 " + str(_n) + " 次（该模型已停用）")
    print("MODELCHAIN_FAIL 停用模型仍被引用")
    sys.exit(1)
print("MODELCHAIN_OK")
sys.exit(0)

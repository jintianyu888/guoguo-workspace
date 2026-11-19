import json,os,sys
p=os.path.expanduser("~/.openclaw/openclaw.json")
raw=open(p,encoding="utf-8").read()
try: d=json.loads(raw)
except Exception: print(0); raise SystemExit
KEYS=("apikey","api_key","token","secret","password")
n=0
def walk(o):
    global n
    if isinstance(o,dict):
        for k,v in o.items():
            if isinstance(v,str) and k.lower() in KEYS and len(v)>=12 and not v.startswith(("store:","secret:","env:")):
                n+=1
            else: walk(v)
    elif isinstance(o,list):
        for i in o: walk(i)
walk(d); print(n)
#!/usr/bin/env python3
import os, sys
roots=[r"/home/j/openclaw-workspaces/sheet-music"]
kw=[s.lower() for s in ("haydn","海顿")]
hits=[]
for root in roots:
    for dp,dn,fn in os.walk(root):
        for f in fn:
            fl=f.lower()
            if any(k in fl for k in kw):
                p=os.path.join(dp,f)
                try: sz=os.path.getsize(p)
                except OSError: sz=-1
                hits.append((p,sz))
for p,s in hits[:80]:
    print(s, p)
print("total", len(hits))

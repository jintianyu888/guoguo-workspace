import json,sys
d=json.load(sys.stdin)
if isinstance(d,list):
    print(len(d))
else:
    for k in ("agents","jobs","sessions"):
        if k in d:
            print(len(d[k])); break

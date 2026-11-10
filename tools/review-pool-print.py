#!/usr/bin/env python3
# 输出评审池：vendor|model|think 每行一条，供 cross-review.sh 读取
import json,sys
p=sys.argv[1]
d=json.load(open(p,encoding='utf-8'))
for v in d['vendors']:
    print(v['vendor']+'|'+v['model']+'|'+v.get('think',''))

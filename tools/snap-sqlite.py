import sqlite3, os, time
pairs=[('/home/j/.openclaw/lcm.db','/home/j/fast-snap/lcm.db'),('/home/j/.openclaw/agents/main/agent/openclaw-agent.sqlite','/home/j/fast-snap/openclaw-agent.sqlite')]
os.makedirs('/home/j/fast-snap',exist_ok=True)
t=time.time()
for src,dst in pairs:
    s=sqlite3.connect('file:'+src+'?mode=ro',uri=True); d=sqlite3.connect(dst); s.backup(d); d.close(); s.close(); print('ok',dst,os.path.getsize(dst))
print('elapsed %.1fs'%(time.time()-t))
for dst in ['/home/j/fast-snap/lcm.db','/home/j/fast-snap/openclaw-agent.sqlite']:
    c=sqlite3.connect(dst); print('integrity',dst,c.execute('pragma integrity_check').fetchone()[0]); c.close()

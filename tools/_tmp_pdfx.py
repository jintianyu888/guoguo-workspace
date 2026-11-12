import socket,time
def probe(port):
    s=socket.socket(); s.settimeout(5)
    try:
        s.connect(("192.168.1.80",port)); return True
    except Exception as e:
        return False
    finally: s.close()
ok=False
for i in range(4):
    if probe(631): ok=True; print("631 OK at try",i+1); break
    print("try",i+1,"fail"); time.sleep(5)
print("REACHABLE",ok)

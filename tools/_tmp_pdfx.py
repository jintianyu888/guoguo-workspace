import socket,struct
def attr(tag,name,val):
    b=bytes([tag])+struct.pack(">H",len(name))+name.encode()
    if isinstance(val,str): b+=struct.pack(">H",len(val))+val.encode()
    else: b+=struct.pack(">H",4)+struct.pack(">i",val)
    return b
body=b"\x01\x01"+struct.pack(">H",0x000A)+struct.pack(">I",1)
body+=b"\x01"
body+=attr(0x47,"attributes-charset","utf-8")
body+=attr(0x48,"attributes-natural-language","en")
body+=attr(0x45,"printer-uri","ipp://192.168.1.80:631/ipp/print")
body+=attr(0x44,"requested-attributes","job-id")
body+=attr(0x44,"requested-attributes","job-state")
body+=attr(0x44,"requested-attributes","job-state-message")
body+=b"\x03"
s=socket.socket(); s.settimeout(8); s.connect(("192.168.1.80",631))
s.sendall(b"POST /ipp/print HTTP/1.1\r\nHost: 192.168.1.80:631\r\nContent-Type: application/ipp\r\nContent-Length: "+str(len(body)).encode()+b"\r\nConnection: close\r\n\r\n")
s.sendall(body)
data=b""
while True:
    c=s.recv(65536)
    if not c: break
    data+=c
s.close()
hdr,_,res=data.partition(b"\r\n\r\n")
print("status-code",struct.unpack(">H",res[2:4])[0],"len",len(res))
# 解析属性
p=8
cur=None; jobs=[]
while p<len(res):
    tag=res[p]; p+=1
    if tag==0x03: break
    if tag<0x10:
        if tag==0x02:
            cur={}; jobs.append(cur)
        continue
    n=struct.unpack(">H",res[p:p+2])[0]; p+=2
    name=res[p:p+n].decode("utf-8","replace"); p+=n
    v=struct.unpack(">H",res[p:p+2])[0]; p+=2
    val=res[p:p+v]; p+=v
    if tag in (0x21,0x23): val=struct.unpack(">i",val)[0]
    elif tag==0x22: val=struct.unpack(">b",val)[0]
    else: val=val.decode("utf-8","replace")
    if cur is not None and name: cur[name]=val
for j in jobs: print(j)
print("jobs",len(jobs))

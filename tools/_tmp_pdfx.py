import zipfile,os,zlib,re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
import pikepdf
from pikepdf import Name, Dictionary
SRC="/home/j/openclaw-workspaces/print/media/inbound/openclaw-staged-8a8fb08a-cecb-4042-bcd5-12a3a664989b/input-20_Nov_单词填空---ce22f3c7-b127-4339-8d62-8eb40a41d60f.docx"
OUT="/home/j/openclaw-workspaces/print/out/20_Nov_单词填空_打印版.pdf"
TITLE="20 Nov 单词填空"
LAT="/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"; LATB="/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"; CJK="/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
root=ET.fromstring(zipfile.ZipFile(SRC).read("word/document.xml"))
paras=["".join(t.text or "" for t in p.iter(W+"t")).strip() for p in root.iter(W+"p")]
paras=[p for p in paras if p]
pairs=[(paras[i],paras[i+1]) for i in range(0,len(paras)-1,2)]
print("pairs",len(pairs))
Wp,Hp=2481,3507; M=170; TW=Wp-2*M
def F(p,s): return ImageFont.truetype(p,s)
is_cjk=lambda ch: bool(re.match(r"[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]", ch))
def toks(s):
    o=[];i=0
    while i<len(s):
        ch=s[i]
        if ch==" ":o.append(" ");i+=1;continue
        if is_cjk(ch):o.append(ch);i+=1;continue
        j=i
        while j<len(s) and not is_cjk(s[j]) and s[j]!=" ":j+=1
        o.append(s[i:j]);i=j
    return o
def mk(FS):
    B=F(LAT,FS); C=F(CJK,FS); LH=int(FS*1.30); PAD=14
    cw=[int(TW*0.46), TW-int(TW*0.46)]
    def wrap(s,mw):
        lines=[];cur="";w=0
        for tk in toks(s):
            a=C.getlength(tk) if any(is_cjk(c) for c in tk) else B.getlength(tk)
            if w+a>mw and cur.strip():
                lines.append(cur.rstrip());cur="" if tk==" " else tk;w=0 if tk==" " else a
            else: cur+=tk;w+=a
        if cur.strip():lines.append(cur.rstrip())
        return lines or [""]
    hdr_h=LH+2*PAD
    rows=[[wrap(a,cw[0]-30),wrap(b,cw[1]-30)] for a,b in pairs]
    hs=[max(len(r[0]),len(r[1]))*LH+2*PAD for r in rows]
    return B,C,LH,PAD,cw,rows,hs,hdr_h,M+120+hdr_h+sum(hs)+M
for FS in range(92,24,-2):
    B,C,LH,PAD,cw,rows,hs,hdr_h,total=mk(FS)
    if total<=Hp: break
print("FS",FS,"total",total)
img=Image.new("RGB",(Wp,Hp),(255,255,255)); d=ImageDraw.Draw(img)
HB=F(LATB,FS); HC=F(CJK,FS); TF=F(LATB,54); TC=F(CJK,54)
def draw(x,y,s,font,cjf):
    for ch in s:
        f=cjf if is_cjk(ch) else font
        d.text((x,y),ch,font=f,fill=(0,0,0));x+=f.getlength(ch)
draw(M,M,TITLE+"（%d 词）"%len(pairs),TF,TC)
y=M+120
d.rectangle([M,y,M+TW,y+hdr_h],fill=(238,238,238))
draw(M+14,y+PAD,"单词（原词 + 释义）",HB,HC)
draw(M+cw[0]+14,y+PAD,"默写（挖空 + 释义）",HB,HC)
d.line([(M,y),(M+TW,y)],fill=(110,110,110),width=2); y+=hdr_h
top=y
for r in range(len(rows)):
    h=hs[r]
    for k,ln in enumerate(rows[r][0]): draw(M+14,y+PAD+k*LH,ln,B,C)
    for k,ln in enumerate(rows[r][1]): draw(M+cw[0]+14,y+PAD+k*LH,ln,B,C)
    d.line([(M,y),(M+TW,y)],fill=(110,110,110),width=2); y+=h
d.line([(M,y),(M+TW,y)],fill=(110,110,110),width=2)
for x in (M,M+cw[0],M+TW): d.line([(x,top),(x,y)],fill=(110,110,110),width=2)
raw=zlib.compress(img.tobytes(),6)
pdf=pikepdf.new(); p=pdf.add_blank_page(page_size=(595.28,841.89))
st=pdf.make_stream(raw); st.Type=Name.XObject; st.Subtype=Name.Image
st.Width=Wp; st.Height=Hp; st.BitsPerComponent=8; st.ColorSpace=Name.DeviceRGB; st.Filter=Name.FlateDecode
p.Resources=Dictionary(XObject=Dictionary(Im0=st))
p.Contents=pdf.make_stream(("q 595.28 0 0 841.89 0 0 cm /Im0 Do Q").encode())
pdf.save(OUT); print("saved",os.path.getsize(OUT))
img.resize((715,1011),Image.LANCZOS).save("/home/j/openclaw-workspaces/print/docx_preview.png"); print("ok")

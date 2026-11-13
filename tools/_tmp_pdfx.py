import zipfile,os,zlib,re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
import pikepdf
from pikepdf import Name, Dictionary
SRC="/home/j/openclaw-workspaces/print/media/inbound/openclaw-staged-13d1bfe4-0495-4009-804c-dead71bf41dd/input-13_Nov_单词填空---10233a99-080b-4147-b639-a0e1531eddba.docx"
OUT="/mnt/e/openclaw-workspaces/print/out/13_Nov_单词填空_打印版.pdf"
TITLE="13 Nov 单词填空"
LAT="/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"; LATB="/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"; CJK="/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
root=ET.fromstring(zipfile.ZipFile(SRC).read("word/document.xml"))
paras=["".join(t.text or "" for t in p.iter(W+"t")).strip() for p in root.iter(W+"p")]
paras=[p for p in paras if p]
half=len(paras)//2; full=paras[:half]; blanks=paras[half:]
print("paras",len(paras),"full",len(full),"blanks",len(blanks))
W_,H_=2481,3507; M=190; acc=W_-2*M
img=Image.new("RGB",(W_,H_),(255,255,255)); d=ImageDraw.Draw(img)
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
def tw(t,font,cjf): return d.textlength(t,font=(cjf if any(is_cjk(c) for c in t) else font))
def wrap(s,font,cjf,mw):
    lines=[];cur="";w=0
    for tk in toks(s):
        a=tw(tk,font,cjf)
        if w+a>mw and cur.strip():
            lines.append(cur.rstrip());cur="" if tk==" " else tk;w=0 if tk==" " else a
        else: cur+=tk;w+=a
    if cur.strip():lines.append(cur.rstrip())
    return lines or [""]
def draw(x,y,s,font,cjf):
    for ch in s:
        f=cjf if is_cjk(ch) else font
        d.text((x,y),ch,font=f,fill=(0,0,0));x+=d.textlength(ch,font=f)
H1=F(LATB,54); CJKH=F(CJK,54); LH1=110; SH=95; SGAP=55; LGAP=10
chosen=None
for FS in (46,44,42,40,38,36,34,32):
    body=F(LAT,FS); cjf=F(CJK,FS); LH=int(FS*1.30); y=240+LH1; total=y
    for items in (full,blanks):
        total+=SH
        for it in items: total+=len(wrap(it,body,cjf,acc-120))*LH+LGAP
        total+=SGAP
    if total<=H_-M: chosen=(FS,body,cjf,LH); break
FS,body,cjf,LH=chosen; print("FS",FS)
y=240
draw(M,y,TITLE+"（%d 词）"%len(full),H1,CJKH); y+=LH1
for title,items in (("一、单词表（原词 + 释义）",full),("二、默写（挖空）",blanks)):
    draw(M,y,title,H1,CJKH); y+=SH
    for i,it in enumerate(items,1):
        draw(M,y,"%2d."%i,body,cjf)
        lines=wrap(it,body,cjf,acc-120)
        for k,ln in enumerate(lines): draw(M+110,y+k*LH,ln,body,cjf)
        y+=len(lines)*LH+LGAP
    y+=SGAP
print("bottom",y,"limit",H_-M)
raw=zlib.compress(img.tobytes(),6)
pdf=pikepdf.new(); p=pdf.add_blank_page(page_size=(595.28,841.89))
st=pdf.make_stream(raw); st.Type=Name.XObject; st.Subtype=Name.Image
st.Width=W_; st.Height=H_; st.BitsPerComponent=8; st.ColorSpace=Name.DeviceRGB; st.Filter=Name.FlateDecode
p.Resources=Dictionary(XObject=Dictionary(Im0=st))
p.Contents=pdf.make_stream(("q 595.28 0 0 841.89 0 0 cm /Im0 Do Q").encode())
pdf.save(OUT); print("saved",os.path.getsize(OUT))
img.resize((715,1011),Image.LANCZOS).save("/home/j/openclaw-workspaces/print/docx_preview.png"); print("ok")

import zipfile,re,os,zlib
from PIL import Image, ImageDraw, ImageFont
import pikepdf
from pikepdf import Name, Dictionary
SRC="/home/j/openclaw-workspaces/print/media/inbound/openclaw-staged-d00c1d7a-f74b-4623-aedc-a62352db9f8d/input-11_Nov_单词填空_1---7ef8c005-12c4-40e0-bf70-bb5eae38cc43.docx"
OUT="/mnt/e/openclaw-workspaces/print/out/11_Nov_单词填空_1_打印版.pdf"
LAT="/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"; LATB="/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"; CJK="/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
xml=zipfile.ZipFile(SRC).read("word/document.xml").decode("utf-8","replace")
tbl=re.search(r"<w:tbl>.*?</w:tbl>", xml, re.S).group(0)
data=[]
for r in re.findall(r"<w:tr[ >].*?</w:tr>", tbl, re.S):
    t=[]
    for c in re.findall(r"<w:tc>.*?</w:tc>", r, re.S):
        s=re.sub(r"<[^>]+>","","".join(re.split(r"</w:p>", c))).replace("\u00a0"," ")
        t.append(re.sub(r"\s+"," ",s).strip())
    while len(t)<2: t.append("")
    data.append(t[:2])
W,H=2481,3507; FS=46
img=Image.new("RGB",(W,H),(255,255,255)); d=ImageDraw.Draw(img)
def F(p,s): return ImageFont.truetype(p,s)
BODY=F(LAT,FS); CJKF=F(CJK,FS); HEAD=F(LATB,56); CJKH=F(CJK,56)
is_cjk=lambda ch: bool(re.match(r"[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]", ch))
def tokens(s):
    out=[];i=0
    while i<len(s):
        ch=s[i]
        if ch==" ": out.append(" "); i+=1; continue
        if is_cjk(ch): out.append(ch); i+=1; continue
        j=i
        while j<len(s) and not is_cjk(s[j]) and s[j]!=" ": j+=1
        out.append(s[i:j]); i=j
    return out
def tl(tok,font,cjf): return d.textlength(tok,font=(cjf if any(is_cjk(c) for c in tok) else font))
def wrap(text,font,cjf,maxw):
    lines=[];cur="";w=0
    for tk in tokens(text):
        a=tl(tk,font,cjf)
        if w+a>maxw and cur.strip():
            lines.append(cur.rstrip()); cur="" if tk==" " else tk; w=0 if tk==" " else a
        else:
            cur+=tk; w+=a
    if cur.strip(): lines.append(cur.rstrip())
    return lines or [""]
def draw(x,y,s,font,cjf):
    for ch in s:
        f=cjf if is_cjk(ch) else font
        d.text((x,y),ch,font=f,fill=(0,0,0));x+=d.textlength(ch,font=f)
M=180;GAP=50
lw=int((W-2*M-GAP)*0.60); rw=(W-2*M-GAP)-lw
x1=M; x2=M+lw+GAP; y=230
draw(x1,y,"11 Nov 单词填空（1–20）",HEAD,CJKH); y+=120
LH=int(FS*1.32); PAD=15
rows=[]
for left,right in data:
    l1=wrap(left,BODY,CJKF,lw-36); r1=wrap(right,BODY,CJKF,rw-36)
    rows.append((l1,r1,max(len(l1),len(r1))*LH+2*PAD))
total=sum(r[2] for r in rows); avail=H-M-y
sc=min(1.0,avail/total); print("scale",round(sc,3))
yy=y
for l1,r1,h in rows:
    d.line([(x1,yy),(x2+rw,yy)],fill=(140,140,140),width=3)
    for i,s in enumerate(l1): draw(x1+16,yy+PAD+i*LH*sc,s,BODY,CJKF)
    for i,s in enumerate(r1): draw(x2+16,yy+PAD+i*LH*sc,s,BODY,CJKF)
    yy+=h*sc
d.line([(x1,yy),(x2+rw,yy)],fill=(140,140,140),width=3)
for x in (x1,x2,x2+rw): d.line([(x,y),(x,yy)],fill=(140,140,140),width=3)
raw=zlib.compress(img.tobytes(),6)
pdf=pikepdf.new(); p=pdf.add_blank_page(page_size=(595.28,841.89))
st=pdf.make_stream(raw); st.Type=Name.XObject; st.Subtype=Name.Image
st.Width=W; st.Height=H; st.BitsPerComponent=8; st.ColorSpace=Name.DeviceRGB; st.Filter=Name.FlateDecode
p.Resources=Dictionary(XObject=Dictionary(Im0=st))
p.Contents=pdf.make_stream(("q 595.28 0 0 841.89 0 0 cm /Im0 Do Q").encode())
pdf.save(OUT); print("saved",os.path.getsize(OUT))
img.resize((715,1011),Image.LANCZOS).save("/home/j/openclaw-workspaces/print/docx_preview.png"); print("ok")

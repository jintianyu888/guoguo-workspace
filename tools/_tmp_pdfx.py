import zipfile,os,zlib,re
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
import pikepdf
from pikepdf import Name, Dictionary
SRC="/home/j/openclaw-workspaces/print/unzip-1114/小黑龙20261114托福听力笔记整理.docx"
OUT="/mnt/e/openclaw-workspaces/print/out/20261114_托福听力笔记_打印版.pdf"
LAT="/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"; LATB="/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"; CJK="/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
W="{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
root=ET.fromstring(zipfile.ZipFile(SRC).read("word/document.xml"))
tbl=next(root.iter(W+"tbl")); rows=[]
for tr in tbl.findall(W+"tr"):
    cells=[]
    for tc in tr.findall(W+"tc"):
        txt=" ".join("".join(t.text or "" for t in p.iter(W+"t")).strip() for p in tc.iter(W+"p")).strip()
        cells.append(txt)
    rows.append(cells+[""]*(3-len(cells)))
header=rows[0]; body=rows[1:]
Wp,Hp=2481,3507; M=170; FS=40
def F(p,s): return ImageFont.truetype(p,s)
BODY=F(LAT,FS); CJKF=F(CJK,FS); HB=F(LATB,FS); HCJ=F(CJK,FS); TF=F(LATB,52); TCJ=F(CJK,52)
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
def wrap(s,font,cjf,mw):
    lines=[];cur="";w=0
    for tk in toks(s):
        a=cjf.getlength(tk) if any(is_cjk(c) for c in tk) else font.getlength(tk)
        if w+a>mw and cur.strip():
            lines.append(cur.rstrip());cur="" if tk==" " else tk;w=0 if tk==" " else a
        else: cur+=tk;w+=a
    if cur.strip():lines.append(cur.rstrip())
    return lines or [""]
def draw_mixed(d,x,y,s,font,cjf):
    for ch in s:
        f=cjf if is_cjk(ch) else font
        d.text((x,y),ch,font=f,fill=(0,0,0));x+=f.getlength(ch)
total_w=Wp-2*M
c1=int(total_w*0.40); c2=int(total_w*0.36); c3=total_w-c1-c2
colw=[c1,c2,c3]
LH=int(FS*1.32); PAD=12
def row_h(cells,font,cjf):
    n=1
    for i,c in enumerate(cells): n=max(n,len(wrap(c,font,cjf,colw[i]-26)))
    return n*LH+2*PAD
hdr_h=row_h(header,HB,HCJ)
pages=[]
def new_page(title=None):
    img=Image.new("RGB",(Wp,Hp),(255,255,255)); d=ImageDraw.Draw(img)
    if title:
        draw_mixed(d,M,M,title,TF,TCJ); top=M+150
    else:
        top=M
    return img,d,top
def close(img,d,top,bot):
    x=M
    for i in range(4):
        d.line([(x,top),(x,bot)],fill=(120,120,120),width=2)
        if i<3: x+=colw[i]
def draw_row(d,cells,font,cjf,hh,yy,shade=False):
    if shade: d.rectangle([M,yy,M+total_w,yy+hh],fill=(238,238,238))
    x=M
    for i,c in enumerate(cells):
        for k,ln in enumerate(wrap(c,font,cjf,colw[i]-26)): draw_mixed(d,x+13,yy+PAD+k*LH,ln,font,cjf)
        x+=colw[i]
    d.line([(M,yy),(M+total_w,yy)],fill=(120,120,120),width=2)

img,d,top=new_page("20261114 托福听力笔记（词汇+短语+原句）")
y=top
draw_row(d,header,HB,HCJ,hdr_h,y,shade=True); y+=hdr_h
for r in body:
    hh=row_h(r,BODY,CJKF)
    if y+hh>Hp-M:
        d.line([(M,y),(M+total_w,y)],fill=(120,120,120),width=2)
        close(img,d,top,y); pages.append(img)
        img,d,top=new_page(); y=top
        draw_row(d,header,HB,HCJ,hdr_h,y,shade=True); y+=hdr_h
    draw_row(d,r,BODY,CJKF,hh,y); y+=hh
d.line([(M,y),(M+total_w,y)],fill=(120,120,120),width=2)
close(img,d,top,y); pages.append(img)
for i,pg in enumerate(pages,1):
    ImageDraw.Draw(pg).text((Wp-M-130,Hp-M+40),"Page %d of %d"%(i,len(pages)),font=F(LAT,34),fill=(120,120,120))
print("pages",len(pages),"rows",len(body))
pdf=pikepdf.new()
for pg in pages:
    raw=zlib.compress(pg.tobytes(),6)
    p=pdf.add_blank_page(page_size=(595.28,841.89))
    st=pdf.make_stream(raw); st.Type=Name.XObject; st.Subtype=Name.Image
    st.Width=Wp; st.Height=Hp; st.BitsPerComponent=8; st.ColorSpace=Name.DeviceRGB; st.Filter=Name.FlateDecode
    p.Resources=Dictionary(XObject=Dictionary(Im0=st))
    p.Contents=pdf.make_stream(("q 595.28 0 0 841.89 0 0 cm /Im0 Do Q").encode())
pdf.save(OUT); print("saved",os.path.getsize(OUT))
pages[0].resize((715,1011),Image.LANCZOS).save("/home/j/openclaw-workspaces/print/docx_preview.png")
pages[-1].resize((715,1011),Image.LANCZOS).save("/home/j/openclaw-workspaces/print/docx_preview_last.png")
print("ok")

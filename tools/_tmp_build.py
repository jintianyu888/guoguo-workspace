#!/usr/bin/env python3
import os, pypdfium2 as pdfium
from PIL import Image
root="/home/j/openclaw-workspaces/sheet-music/scores/files/海顿 钢琴谱全集/奏鸣曲"
src=os.path.join(root,"Piano Sonata No 49 in Eb_NoRestriction.pdf")
outdir="/home/j/openclaw-workspaces/print/out"
os.makedirs(outdir, exist_ok=True)
out=os.path.join(outdir,"haydn-eb-sonata-XVI49-mov2-Adagio-cantabile.pdf")
d=pdfium.PdfDocument(src)
AW,AH=2481,3507
pages=[]
for i in (7,8,9,10):
    im=d[i].render(scale=300/72).to_pil().convert("RGB")
    w=int(im.width*AH/im.height); sc=min(AW/im.width, AH/im.height)
    im2=im.resize((int(im.width*sc),int(im.height*sc)), Image.LANCZOS)
    pg=Image.new("RGB",(AW,AH),(255,255,255)); pg.paste(im2,((AW-im2.width)//2,(AH-im2.height)//2))
    pages.append(pg); print("page",i+1,im.size,"->",im2.size)
im=d[11].render(scale=300/72).to_pil().convert("RGB")
cut=int(im.height*0.52)
top=im.crop((0,0,im.width,cut))
sc=min(AW/top.width, AH/top.height)
top2=top.resize((int(top.width*sc),int(top.height*sc)), Image.LANCZOS)
pg=Image.new("RGB",(AW,AH),(255,255,255)); pg.paste(top2,((AW-top2.width)//2,0))
pages.append(pg); print("crop p12",im.size,"->",top2.size)
pages[0].save(out,save_all=True,append_images=pages[1:],resolution=300.0)
print("saved",out,os.path.getsize(out),"pages",len(pages))

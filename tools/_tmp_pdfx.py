import pypdfium2 as pdfium
from PIL import Image
p="/mnt/e/openclaw-workspaces/print/out/李斯特-叹息-UnSospiro-9p.pdf"
d=pdfium.PdfDocument(p); print("pages",len(d))
ims=[d[0].render(scale=1.6).to_pil().convert("RGB"), d[8].render(scale=1.6).to_pil().convert("RGB")]
w=max(i.width for i in ims); h=max(i.height for i in ims)
s=Image.new("RGB",(w*2+20,h),(255,255,255))
s.paste(ims[0],(0,0)); s.paste(ims[1],(w+20,0))
s.save("/home/j/openclaw-workspaces/print/liszt_slice.png"); print(s.size)

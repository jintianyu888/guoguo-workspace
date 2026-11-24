import pikepdf, os
from pikepdf import Name, Dictionary
A4W,A4H=595.28,841.89
LM,RM=56.7,56.7          # 20mm 左右
TOP,BOT=56.7,56.7
left,right=LM,A4W-RM
width=right-left
systems=9
gap=8.0                   # 线间距 8pt（约 2.8mm）
staff_h=gap*4             # 五线四条间隔
usable=A4H-TOP-BOT
block=usable/systems      # 每个系统占高
pdf=pikepdf.new()
page=pdf.add_blank_page(page_size=(A4W,A4H))
ops=[]
for i in range(systems):
    top=A4H-TOP-i*block-(block-staff_h)/2
    for k in range(5):
        y=top-k*gap
        ops.append("0.6 w %.2f %.2f m %.2f %.2f l S"%(left,y,right,y))
page.Contents=pdf.make_stream(("\n".join(ops)).encode())
page.Resources=Dictionary()
out="/home/j/openclaw-workspaces/print/out/20261124_空白五线谱_A4_9行.pdf"
pdf.docinfo["/Title"]="空白五线谱 A4 9行"
pdf.save(out); print("saved",os.path.getsize(out))
import pypdfium2 as pdfium
d=pdfium.PdfDocument(out); print("pages",len(d))
d[0].render(scale=1.4).to_pil().convert("RGB").resize((680,962)).save("/home/j/openclaw-workspaces/print/staff_a4.png")
print("ok")

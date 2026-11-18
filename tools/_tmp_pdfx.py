import pikepdf, os, pypdfium2 as pdfium
src="/home/j/openclaw-workspaces/print/scores/files/肖邦 钢琴谱全集/ETUDES/OP10_4.PDF"
out="/home/j/openclaw-workspaces/print/out/Chopin-Etude-Op10-No4-Csharp-minor-A4.pdf"
with pikepdf.open(src) as pdf:
    for page in pdf.pages:
        mb=[float(x) for x in page.MediaBox]
        w,h=mb[2]-mb[0], mb[3]-mb[1]
        s=min(595.28/w, 841.89/h)
        tx=(595.28-s*w)/2; ty=(841.89-s*h)/2
        raw=page.Contents.read_bytes()
        page.Contents=pdf.make_stream(("q %.6f 0 0 %.6f %.4f %.4f cm\n"%(s,s,tx,ty)).encode()+raw+b"\nQ")
        page.MediaBox=pikepdf.Array([0,0,595.28,841.89]); page.CropBox=pikepdf.Array([0,0,595.28,841.89])
    pdf.save(out)
print("saved",os.path.getsize(out))
d=pdfium.PdfDocument(out); print("pages",len(d),d[0].get_size())
d[0].render(scale=1.6).to_pil().convert("RGB").resize((760,1075)).save("/home/j/openclaw-workspaces/print/op10_4_final.png")

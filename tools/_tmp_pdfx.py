import io,os,pikepdf,shutil
from PIL import Image
from pikepdf import Name, Dictionary
P=["/home/j/openclaw-workspaces/print/media/inbound/openclaw-staged-6714ccca-fd77-4645-b5d2-70b1f641e86a/input-5902436d-9895-49c8-a749-84d292c8f96a.jpg",
   "/home/j/openclaw-workspaces/print/media/inbound/openclaw-staged-fbb17033-112a-40a1-9545-660ded920bc5/input-59bc733c-16f5-4517-b2d4-dbd2a16e7fa0.jpg",
   "/home/j/openclaw-workspaces/print/media/inbound/openclaw-staged-14d4db03-0f23-4422-a666-341a7f411b0e/input-4b93a585-32da-45be-afb8-07571c9ec2a7.jpg",
   "/home/j/openclaw-workspaces/print/media/inbound/openclaw-staged-91574ed4-0d64-473e-b5e2-e11f011c55c8/input-53dff274-c859-4c7f-8471-1342cde45e26.jpg",
   "/home/j/openclaw-workspaces/print/media/inbound/openclaw-staged-40c65ecd-749e-47a3-bae7-f8fbbb2076b7/input-0fd52146-e6ea-436a-8d87-93c6bdfc1383.jpg"]
out="/home/j/openclaw-workspaces/print/out/20261121_喜欢你_5页版_A4.pdf"
A4W,A4H=595.28,841.89; M=12
pdf=pikepdf.new()
for src in P:
    im=Image.open(src).convert("L"); w,h=im.size
    s=min((A4W-2*M)/w,(A4H-2*M)/h); pw,ph=w*s,h*s
    buf=io.BytesIO(); im.save(buf,"JPEG",quality=93,optimize=True)
    page=pdf.add_blank_page(page_size=(A4W,A4H))
    st=pdf.make_stream(buf.getvalue()); st.Type=Name.XObject; st.Subtype=Name.Image
    st.Width=w; st.Height=h; st.BitsPerComponent=8; st.ColorSpace=Name.DeviceGray; st.Filter=Name.DCTDecode
    page.Resources=Dictionary(XObject=Dictionary(Im0=st))
    page.Contents=pdf.make_stream(("q %.4f 0 0 %.4f %.4f %.4f cm /Im0 Do Q"%(pw,ph,(A4W-pw)/2,(A4H-ph)/2)).encode())
    print(w,h,round(s,3))
pdf.docinfo["/Title"]="喜欢你 5页版"
pdf.save(out); print("saved",os.path.getsize(out))
import pypdfium2 as pdfium
d=pdfium.PdfDocument(out); print("pages",len(d))
d[0].render(scale=1.0).to_pil().convert("RGB").resize((660,933)).save("/home/j/openclaw-workspaces/print/xhn5_p1.png")
shutil.copy2(P[0],"/home/j/openclaw-workspaces/print/scores/files/20261121_喜欢你_5页版_第1页.jpg")
print("ok")

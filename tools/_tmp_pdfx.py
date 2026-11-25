from PIL import Image, ImageChops
import shutil
new="/home/j/openclaw-workspaces/print/media/inbound/openclaw-staged-34c1101e-223f-4c8f-9683-7993359f7763/input-d3669ebe-0902-4efd-8bbb-4b269287593e.jpg"
old="/home/j/openclaw-workspaces/print/scores/files/20261120_慌啥子嘛_第1页_虫虫音乐.jpg"
a=Image.open(new).convert("L"); b=Image.open(old).convert("L")
print("new",a.size,"old",b.size)
a2=a.resize((600,int(600*a.height/a.width))); b2=b.resize((600,int(600*b.height/b.width)))
if a2.size!=b2.size: b2=b2.resize(a2.size)
h=ImageChops.difference(a2,b2).histogram(); tot=sum(h); big=sum(h[40:])
print("diff>40 %:", round(100*big/tot,2))
shutil.copy2(new,"/home/j/openclaw-workspaces/print/scores/files/20261125_慌啥子嘛_第1页_再收.jpg")

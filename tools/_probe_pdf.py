import sys
mods=[]
for m in ('fitz','pypdf','PyPDF2','pikepdf','reportlab','PIL'):
    try:
        __import__(m); mods.append(m+':OK')
    except Exception as e:
        mods.append(m+':NO')
print(' | '.join(mods))

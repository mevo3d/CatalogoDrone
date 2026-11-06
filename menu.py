import os,json
base='/volume5/DRONE/_CATALOGO'
TITLES={'ARCHIVO_COMPLETO':'★ Archivo COMPLETO (todas las regiones)','FUERA_DE_DRONE':'📦 Material de dron FUERA de la carpeta DRONE','PILOTO_CENTRO':'Cuautla — Colonia Centro (Zócalo + Alameda)','PILOTO_CDMX':'CDMX'}
cats=[]
for d in sorted(os.listdir(base)):
    idx=os.path.join(base,d,'index.html')
    if not os.path.isfile(idx) or d in('assets',) or d.startswith('PRUEBA'): continue
    nv=nf=0
    try:
        data=json.load(open(os.path.join(base,d,'catalog.json'),encoding='utf-8'))
        nv=sum(1 for r in data if r.get('type')=='video'); nf=len(data)-nv
    except Exception: pass
    cats.append((d,TITLES.get(d,d),nv,nf))
rows=''.join(f'<a class=cat href="{d}/index.html"><div class=t>{t}</div><div class=c>▶ {nv} videos · 📷 {nf} fotos</div></a>' for d,t,nv,nf in cats)
html=f'<!doctype html><html lang=es><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Catálogo DRONE — Menú</title><style>body{{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#0f0f10;color:#eee}}header{{padding:22px 20px;border-bottom:1px solid #333;background:#1b1b1d}}h1{{margin:0;font-size:20px}}.wrap{{padding:20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}a.cat{{display:block;text-decoration:none;background:#1c1c1e;border:1px solid #2c2c30;border-radius:12px;padding:18px;color:#eee}}a.cat:hover{{border-color:#3a6;background:#20241f}}.t{{font-weight:600;font-size:16px}}.c{{color:#9bd;font-size:13px;margin-top:6px}}</style></head><body><header><h1>🛸 Catálogo DRONE</h1></header><div class=wrap>{rows}</div></body></html>'
open(os.path.join(base,'index.html'),'w',encoding='utf-8').write(html)
print('menu:',[c[0] for c in cats])

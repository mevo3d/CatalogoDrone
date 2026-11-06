#!/bin/sh
# Actualizador del catalogo DRONE. Ejecutar cuando agregues material nuevo.
# - Re-escanea las carpetas configuradas (solo procesa archivos NUEVOS; los previews ya hechos se reutilizan).
# - Reconstruye el menu maestro (auto-detecta todos los catalogos).
# - Asegura que el servidor web este corriendo.
cd /volume5/DRONE/_CATALOGO || exit 1
FF=./bin/ffmpeg; FP=./bin/ffprobe; MR=/volume5/DRONE/MEDIA

gen(){ OUT="$1"; shift; echo ">> $OUT"; python3 build_catalog.py --out "$OUT" --media-root "$MR" --ffmpeg "$FF" --ffprobe "$FP" --geocode --only-drone "$@" 2>&1 | tail -2; }

# ===== CATALOGOS (agrega una linea gen ... por cada catalogo nuevo) =====
gen ARCHIVO_COMPLETO --src "$MR"
# Material de dron FUERA de la carpeta DRONE (no se mueve, solo se cataloga con su ubicacion real)
[ -f ./lista_externos.txt ] && gen FUERA_DE_DRONE --filelist ./lista_externos.txt
# (los pilotos quedan como subconjuntos; puedes borrarlos si ya no los usas)
gen PILOTO_CENTRO --src "$MR/MORELOS/CUAUTLA/ZOCALO" --src "$MR/MORELOS/CUAUTLA/ALAMEDA" --src "$MR/MORELOS/CUAUTLA/COLONIAS/CENTRO"
gen PILOTO_CDMX   --src "$MR/CDMX"
# =======================================================================

echo ">> Construyendo menu maestro (index.html)"
python3 - <<'PY'
import os,json
base='/volume5/DRONE/_CATALOGO'
TITLES={'ARCHIVO_COMPLETO':'★ Archivo COMPLETO (todas las regiones)','FUERA_DE_DRONE':'📦 Material de dron FUERA de la carpeta DRONE','PILOTO_CENTRO':'Cuautla — Colonia Centro (Zócalo + Alameda)','PILOTO_CDMX':'CDMX'}
cats=[]
for d in sorted(os.listdir(base)):
    idx=os.path.join(base,d,'index.html')
    if not os.path.isfile(idx) or d=='assets': continue
    nv=nf=0
    try:
        data=json.load(open(os.path.join(base,d,'catalog.json'),encoding='utf-8'))
        nv=sum(1 for r in data if r.get('type')=='video'); nf=len(data)-nv
    except Exception: pass
    cats.append((d,TITLES.get(d,d),nv,nf))
rows=''.join(f'''<a class=cat href="{d}/index.html">
  <div class=t>{t}</div>
  <div class=c>▶ {nv} videos &nbsp;·&nbsp; 📷 {nf} fotos</div></a>''' for d,t,nv,nf in cats)
html=f'''<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Catálogo DRONE — Menú</title>
<style>body{{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#0f0f10;color:#eee}}
header{{padding:22px 20px;border-bottom:1px solid #333;background:#1b1b1d}}h1{{margin:0;font-size:20px}}
p.s{{color:#999;margin:6px 0 0}}.wrap{{padding:20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
a.cat{{display:block;text-decoration:none;background:#1c1c1e;border:1px solid #2c2c30;border-radius:12px;padding:18px;color:#eee;transition:.15s}}
a.cat:hover{{border-color:#3a6;background:#20241f}}.t{{font-weight:600;font-size:16px}}.c{{color:#9bd;font-size:13px;margin-top:6px}}</style></head>
<body><header><h1>🛸 Catálogo DRONE</h1><p class=s>{len(cats)} catálogo(s). Haz clic para entrar y buscar.</p></header>
<div class=wrap>{rows}</div></body></html>'''
open(os.path.join(base,'index.html'),'w',encoding='utf-8').write(html)
print(f'   menu con {len(cats)} catalogos')
PY

# ===== Servidor web (lo levanta si no esta corriendo) =====
if ! curl -s -o /dev/null --max-time 3 http://127.0.0.1:8088/ 2>/dev/null; then
  cd /volume5/DRONE && setsid nohup python3 -m http.server 8088 --bind 0.0.0.0 </dev/null >/volume5/DRONE/_CATALOGO/web.log 2>&1 &
  echo ">> servidor web levantado en 8088"
else
  echo ">> servidor web ya estaba corriendo"
fi
echo "LISTO. Menu: http://100.85.255.86:8088/_CATALOGO/index.html"

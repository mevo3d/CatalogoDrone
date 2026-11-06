#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de catalogo de DRONE (no destructivo).
- VIDEO: poster (1 frame) + sprite 4x4 (scrub) + metadatos (duracion, tamaño, resolucion, GPS, hora).
- FOTO jpg/png: preview jpg.  DNG/raw: preview via 'dcraw -e' (JPEG embebido).  Conserva originales.
- Lee el .SRT hermano para fecha/hora/GPS del video.
- Deriva tags de la ruta (region/municipio/colonia/lugar/tema) + fecha/hora.
- HTML autocontenido: buscador en vivo + resultados AGRUPADOS POR CARPETA con liga a la carpeta local.

Uso:
  python3 build_catalog.py --out OUT --media-root /volume5/DRONE/MEDIA \
     --ffmpeg ./bin/ffmpeg --ffprobe ./bin/ffprobe \
     --src "ruta1" --src "ruta2" [--limit N]
"""
import os, sys, re, json, hashlib, subprocess, argparse, time, urllib.request

VIDEO_EXT = {'.mov', '.mp4'}
PHOTO_EXT = {'.jpg', '.jpeg', '.png', '.dng', '.tif', '.tiff', '.nef', '.psd', '.webp', '.heic'}
RAW_EXT   = {'.dng', '.nef', '.arw', '.cr2'}
DRONE_PREFIX_RE = re.compile(r'^(DJI|HYPERLAPSE|PANO)', re.I)  # DJI/Osmo dron; excluye DSC_(Nikon), SCREENSHOT_, etc.
EDIT_FOLDERS = {'FINAL','FINALES','EDITADAS','EDITADA','PROCESADAS','SELECCION','SELECCIONADAS','ENTREGA','EXPORTADOS','EXPORT','RETOQUE'}
EDIT_RE = re.compile(r'MEJORAD|EDIT|RETOQUE|SELECC|-NR|FINAL|COLOR GRAD', re.I)
def is_edited(fn, root, ext):
    if ext in ('.psd','.tif','.tiff'): return True
    if os.path.basename(root).upper() in EDIT_FOLDERS: return True
    return bool(EDIT_RE.search(fn))
SKIP_DIRS = {'@eaDir', '#recycle', 'proxies'}
MES_NOMBRE = {1:'enero',2:'febrero',3:'marzo',4:'abril',5:'mayo',6:'junio',7:'julio',
              8:'agosto',9:'septiembre',10:'octubre',11:'noviembre',12:'diciembre'}
NOISE_SEG = {'FOTO','VIDEO','MEDIA','MAÑANA','MANANA','TARDE','NOCHE','DIA','AMANECER',
             'ATARDECER','COLONIAS','PANORAMA','HYPERLAPSE','FINAL','FINALES',
             'NUEVA CARPETA','100MEDIA'}
FFMPEG='ffmpeg'; FFPROBE='ffprobe'

def run(cmd, timeout=180):
    try:
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=timeout).stdout
    except Exception as e:
        return b'ERR:'+str(e).encode()

def probe(path):
    out = run([FFPROBE,'-v','error','-select_streams','v:0',
               '-show_entries','format=duration:stream=width,height',
               '-of','default=noprint_wrappers=1:nokey=1', path]).decode('utf-8','replace')
    w=h=None; dur=0.0
    nums=[x for x in out.split() if x.strip()]
    vals=[]
    for x in nums:
        try: vals.append(float(x))
        except: pass
    # stream w,h primero, luego duration (orden de -show_entries puede variar); tomamos heuristica
    ints=[int(v) for v in vals if v==int(v) and v>1]
    flts=[v for v in vals if v!=int(v) or v<=1]
    if len(ints)>=2: w,h=ints[0],ints[1]
    if flts: dur=max(flts)
    elif vals: dur=vals[-1]
    return dur,w,h

def make_poster(src,dst,dur):
    ss = max(0.0, min(dur*0.10,3.0)) if dur else 0.5
    run([FFMPEG,'-y','-ss',f'{ss:.2f}','-i',src,'-frames:v','1','-vf','scale=480:-2',dst])
    return os.path.exists(dst) and os.path.getsize(dst)>0

def make_sprite(src,dst,dur):
    # 16 saltos rapidos (1 frame c/u, memoria minima) + montage 4x4.
    # Evita decodificar el video completo (que en 4K HEVC revienta la RAM del NAS).
    import tempfile
    if not dur or dur<=0.5: dur=16.0
    tmpd=tempfile.mkdtemp(prefix='spr_')
    got=[]
    try:
        for i in range(16):
            t=dur*(i+0.5)/16.0
            fp=os.path.join(tmpd,f'fr_{i:02d}.jpg')
            run([FFMPEG,'-y','-ss',f'{t:.2f}','-i',src,'-frames:v','1','-threads','1',
                 '-vf','scale=160:90:force_original_aspect_ratio=increase,crop=160:90',fp],timeout=60)
            got.append(fp if os.path.exists(fp) and os.path.getsize(fp)>0 else None)
        # rellena huecos con el ultimo frame bueno para mantener 16 celdas
        last=next((g for g in got if g),None)
        if not last: return False
        ordered=[]
        for g in got:
            if g: last=g
            ordered.append(last)
        subprocess.run(['montage']+CLIM+ordered+['-tile','4x4','-geometry','160x90+0+0',
                        '-background','#000000',dst],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120)
    finally:
        for f in got:
            if f:
                try: os.remove(f)
                except: pass
        try: os.rmdir(tmpd)
        except: pass
    return os.path.exists(dst) and os.path.getsize(dst)>0

CLIM=['-limit','memory','256MB','-limit','map','512MB','-limit','disk','2GB']
def make_photo(src,dst,is_raw):
    if is_raw:
        try:
            p=subprocess.run(['dcraw','-c','-e',src],stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL,timeout=120)
            if p.stdout:
                subprocess.run(['convert']+CLIM+['-','-auto-orient','-resize','480x480>','-quality','80',dst],
                               input=p.stdout,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120)
        except Exception: pass
    else:
        e=os.path.splitext(src)[1].lower()
        srcarg=src+'[0]' if e in ('.psd','.tif','.tiff','.gif') else src
        flat=['-flatten'] if e=='.psd' else []
        run(['convert']+CLIM+[srcarg]+flat+['-auto-orient','-resize','480x480>','-quality','80',dst])
    return os.path.exists(dst) and os.path.getsize(dst)>0

SRT_DT=re.compile(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})')
SRT_LAT=re.compile(r'latitude\s*:\s*([-\d.]+)')
SRT_LON=re.compile(r'long?titude\s*:\s*([-\d.]+)')
SRT_ALT=re.compile(r'altitude\s*:?\s*([-\d.]+)')
def parse_srt(path):
    d={'date':None,'time':None,'lat':None,'lon':None,'alt':None}
    try:
        with open(path,'r',encoding='utf-8',errors='replace') as f: txt=f.read(8000)
    except Exception: return d
    m=SRT_DT.search(txt)
    if m:
        y,mo,da,h,mi,s=m.groups(); d['date']=f'{y}-{mo}-{da}'; d['time']=f'{h}:{mi}:{s}'
    ml=SRT_LAT.search(txt); mn=SRT_LON.search(txt); ma=SRT_ALT.search(txt)
    if ml:
        try: d['lat']=round(float(ml.group(1)),6)
        except: pass
    if mn:
        try: d['lon']=round(float(mn.group(1)),6)
        except: pass
    if ma:
        try: d['alt']=round(float(ma.group(1)),1)
        except: pass
    return d

DRONE_MODELS={'L1D-20c':'DJI Mavic 2 Pro','FC3411':'DJI Air 2','FC3582':'DJI Mini 3 Pro',
    'FC7303':'DJI Mini 2','FC3170':'DJI Mavic Air 2','FC2103':'DJI Mavic Air','FC220':'DJI Mavic Pro',
    'FC6310':'DJI Phantom 4 Pro','FC8482':'DJI Mini SE','FC3681':'DJI Mini 4 Pro'}
def friendly_model(m):
    if not m: return None
    m=m.strip().strip('"')
    return DRONE_MODELS.get(m,m) if m else None
def _out(cmd):
    try: return subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=40).stdout.decode('utf-8','replace')
    except Exception: return ''
def camera_model(full,is_video,is_raw,ext):
    try:
        if is_raw:
            mm=re.search(r'Camera model:\s*(.+)',_out(['dcraw','-i','-v',full])); return friendly_model(mm.group(1)) if mm else None
        if is_video:
            o=_out([FFPROBE,'-v','error','-show_entries','format_tags=encoder','-of','default=nk=1:nw=1',full]).strip()
            return friendly_model(o.splitlines()[0]) if o else None
        o=_out(['identify','-format','%[EXIF:Model]',full]).strip()
        if not o or ':' in o or 'nknown' in o: return None
        return friendly_model(o)
    except Exception: return None
OSMO_RE=re.compile(r'osmo|pocket|action',re.I)
AERIAL_RE=re.compile(r'AERE|DRON|PANO|HYPERLAPSE',re.I)
DRONE_NAME_RE=re.compile(r'mavic|air|mini|phantom|inspire|avata|l1d|^fc\d',re.I)
def classify_aerial(full,srt,model):
    if model and OSMO_RE.search(model): return False
    if srt and srt.get('alt') is not None: return True
    if model and DRONE_NAME_RE.search(model): return True
    if AERIAL_RE.search(full): return True
    return False

def geocode_lookup(lat,lon):
    # reverse-geocode con OpenStreetMap Nominatim (gratis). Devuelve colonia/municipio/estado/calle.
    try:
        url=f'https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}&zoom=16&addressdetails=1'
        req=urllib.request.Request(url,headers={'User-Agent':'MegaDroneCatalog/1.0 (mevo@mevo.com.mx)'})
        with urllib.request.urlopen(req,timeout=20) as r:
            a=json.load(r).get('address',{})
        return {'colonia':a.get('neighbourhood') or a.get('suburb') or a.get('quarter') or a.get('city_district'),
                'municipio':a.get('city') or a.get('town') or a.get('municipality') or a.get('village'),
                'estado':a.get('state'),'road':a.get('road')}
    except Exception:
        return {}

def tod_from_time(t):
    if not t: return None
    h=int(t.split(':')[0])
    if 5<=h<12: return 'MAÑANA'
    if 12<=h<19: return 'TARDE'
    return 'NOCHE'

MES_SET={v.upper() for v in MES_NOMBRE.values()}  # ENERO..DICIEMBRE
def derive_tags(full,media_root):
    rel=os.path.relpath(full,media_root); parts=rel.split(os.sep)
    region=parts[0] if parts else ''; municipio=parts[1] if len(parts)>1 else ''
    rest=parts[2:-1]; year=month=day=tod=None; places=[]
    for seg in rest:
        su=seg.upper()
        if re.fullmatch(r'(19|20)\d{2}',seg): year=seg; continue
        m=re.match(r'(\d{1,2})[_\s]*(.*)$',seg)
        if m:
            num=int(m.group(1)); restp=m.group(2).strip(); restU=restp.upper()
            # mes: "04_ABRIL" (numero 1-12 + nombre de mes)
            if 1<=num<=12 and (restU in MES_SET or any(restU.startswith(x[:3]) for x in MES_SET)):
                month=f'{num:02d}'; continue
            # dia: "17_METROHM" -> day=17, descripcion -> tag/lugar
            if year and 1<=num<=31:
                day=f'{num:02d}'
                if restp and restU not in NOISE_SEG: places.append(restp)
                continue
        if su in ('MAÑANA','MANANA','TARDE','NOCHE','DIA','AMANECER','ATARDECER'):
            tod=su.replace('MANANA','MAÑANA'); continue
        if su in NOISE_SEG: continue
        places.append(seg)
    return region,municipio,year,month,day,tod,places

# Ubicaciones manuales (material sin GPS cuyo lugar conocemos)
LOC_OVERRIDES=[
    ('STUDIO/GRUINDAG', {'estado':'Morelos','municipio':'Ayala','colonia':'Parque Industrial','lugar':'Gruindag'}),
    ('STUDIO/40_OQUETZA', {'estado':'Morelos','municipio':'Cuautla','colonia':'Gabriel Tepepa','lugar':'Colegio Oquetza'}),
]
def build_external_item(full,assets,label):
    ext=os.path.splitext(full)[1].lower()
    is_video=ext in VIDEO_EXT; is_raw=ext in RAW_EXT; fn=os.path.basename(full)
    h=hashlib.md5(full.encode()).hexdigest()[:16]
    srt={'date':None,'time':None,'lat':None,'lon':None,'alt':None}
    base=os.path.splitext(full)[0]
    for c in (base+'.SRT',base+'.srt'):
        if os.path.exists(c): srt=parse_srt(c); break
    try: size=os.path.getsize(full)
    except: size=0
    parts=full.split('/'); share=parts[2] if len(parts)>2 else ''; proj=parts[3] if len(parts)>3 else ''
    model=camera_model(full,is_video,is_raw,ext); aerial=classify_aerial(full,srt,model)
    edited=is_edited(fn,os.path.dirname(full),ext)
    rec={'id':h,'name':fn,'type':'video' if is_video else 'photo','raw':is_raw,'edited':edited,
         'external':True,'realpath':full,'origin':proj or share,'model':model,'aerial':aerial,
         'src':full,'folder':proj or share,'folderlink':full,
         'lat':srt['lat'],'lon':srt['lon'],'time':srt['time'],'tod':tod_from_time(srt['time']),
         'size':size,'sizetxt':human_size(size)}
    if srt['date']:
        rec['date']=srt['date'];rec['year']=srt['date'][:4];rec['month']=srt['date'][5:7];rec['day']=srt['date'][8:10]
    else:
        try:
            import datetime; mt=datetime.datetime.fromtimestamp(os.path.getmtime(full))
            rec['date']=mt.strftime('%Y-%m-%d');rec['year']=mt.strftime('%Y');rec['month']=mt.strftime('%m');rec['day']=mt.strftime('%d')
        except: rec['date']=None;rec['year']=rec['month']=rec['day']=None
    try:
        if is_video:
            po=os.path.join(assets,h+'_p.jpg');sp=os.path.join(assets,h+'_s.jpg')
            dur,w,ht=probe(full);rec['dur']=dur;rec['durtxt']=human_dur(dur);rec['res']=f'{w}x{ht}' if w and ht else ''
            if not os.path.exists(po) or os.path.getsize(po)==0: make_poster(full,po,dur)
            if not os.path.exists(sp) or os.path.getsize(sp)==0: make_sprite(full,sp,dur)
            rec['poster']='assets/'+h+'_p.jpg' if os.path.exists(po) and os.path.getsize(po)>0 else None
            rec['sprite']='assets/'+h+'_s.jpg' if os.path.exists(sp) and os.path.getsize(sp)>0 else None
        else:
            pv=os.path.join(assets,h+'_t.jpg')
            if not os.path.exists(pv) or os.path.getsize(pv)==0: make_photo(full,pv,is_raw)
            rec['poster']='assets/'+h+'_t.jpg' if os.path.exists(pv) and os.path.getsize(pv)>0 else None
    except Exception as e: rec['err']=str(e)
    loc_tags=[]
    for key,loc in LOC_OVERRIDES:
        if key in full:
            rec['geo']={'colonia':loc.get('colonia'),'municipio':loc.get('municipio'),'road':loc.get('lugar')}
            loc_tags=[v for v in (loc.get('estado'),loc.get('municipio'),loc.get('colonia'),loc.get('lugar')) if v]
            break
    tags=[label, proj or share, share, 'VIDEO' if is_video else 'FOTO']+loc_tags
    if is_raw: tags.append('RAW')
    tags.append('EDITADA' if edited else 'ORIGINAL')
    tags.append('AEREO' if aerial else 'NO AEREO')
    if model: tags.append(model)
    tags.append(ext.lstrip('.').upper())
    if rec['tod']: tags.append(rec['tod'])
    if rec.get('year'): tags.append(rec['year'])
    if rec.get('month'):
        try: tags.append(MES_NOMBRE[int(rec['month'])])
        except: pass
    rec['tags']=[x for x in tags if x]
    return rec

def editor_html():
    p=os.path.join(os.path.dirname(os.path.abspath(__file__)),'editor_snippet.html')
    try: return open(p,encoding='utf-8').read()
    except Exception: return ''

def write_index(out,items):
    html=HTML_TPL.replace('<!--__EDITOR__-->',editor_html()).replace('/*__DATA__*/',json.dumps(items,ensure_ascii=False))
    with open(os.path.join(out,'index.html'),'w',encoding='utf-8') as f: f.write(html)

def flush(out,items):
    with open(os.path.join(out,'catalog.json'),'w',encoding='utf-8') as f:
        json.dump(items,f,ensure_ascii=False)
    write_index(out,items)

def human_size(n):
    for u in ('B','KB','MB','GB'):
        if n<1024: return f'{n:.0f} {u}' if u in ('B','KB') else f'{n:.1f} {u}'
        n/=1024
    return f'{n:.1f} TB'
def human_dur(s):
    if not s: return ''
    s=int(s); h=s//3600; m=(s%3600)//60; sec=s%60
    return f'{h}:{m:02d}:{sec:02d}' if h else f'{m}:{sec:02d}'

def main():
    global FFMPEG,FFPROBE
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",required=True); ap.add_argument("--media-root",default="")
    ap.add_argument('--src',action='append',default=[])
    ap.add_argument('--filelist',default=None,help='archivo con lista de rutas (modo externo)')
    ap.add_argument('--external',default='FUERA DE DRONE',help='etiqueta para items en modo filelist')
    ap.add_argument('--ffmpeg',default='ffmpeg'); ap.add_argument('--ffprobe',default='ffprobe')
    ap.add_argument('--limit',type=int,default=0)
    ap.add_argument('--geocode',action='store_true',help='reverse-geocode GPS a colonia/municipio (Nominatim)')
    ap.add_argument('--only-drone',dest='only_drone',action='store_true',help='solo archivos de dron (DJI/HYPERLAPSE/PANO); excluye DSC_ Nikon etc.')
    ap.add_argument('--render-only',dest='render_only',action='store_true',help='solo regenera index.html desde catalog.json existente (no escanea)')
    a=ap.parse_args(); FFMPEG=a.ffmpeg; FFPROBE=a.ffprobe
    if a.render_only:
        items=json.load(open(os.path.join(a.out,'catalog.json'),encoding='utf-8')); write_index(a.out,items)
        print(f'render-only: {len(items)} items -> {a.out}/index.html'); return
    assets=os.path.join(a.out,'assets'); os.makedirs(assets,exist_ok=True)
    items=[]; nseen=0
    if a.filelist:
        flist=[l.strip() for l in open(a.filelist,encoding='utf-8',errors='replace') if l.strip()]
        seen=0
        for full in flist:
            if os.path.splitext(full)[1].lower() not in (VIDEO_EXT|PHOTO_EXT): continue
            if a.only_drone and not DRONE_PREFIX_RE.match(os.path.basename(full)): continue
            if not os.path.exists(full): continue
            seen+=1
            if a.limit and seen>a.limit: break
            try: items.append(build_external_item(full,assets,a.external))
            except Exception as e: print('  err',os.path.basename(full),e)
            if seen%20==0: print(f'  ...{seen} externos',flush=True)
            if seen%100==0:
                try: flush(a.out,items)
                except Exception: pass
    for src in a.src:
        for root,dirs,files in os.walk(src):
            dirs[:]=[d for d in dirs if d not in SKIP_DIRS and not d.startswith('@')]
            for fn in sorted(files):
                ext=os.path.splitext(fn)[1].lower()
                if (ext not in VIDEO_EXT and ext not in PHOTO_EXT) or fn.startswith('.'): continue
                if a.only_drone and not DRONE_PREFIX_RE.match(fn): continue
                full=os.path.join(root,fn); nseen+=1
                if a.limit and nseen>a.limit: break
                h=hashlib.md5(full.encode()).hexdigest()[:16]
                region,municipio,pyear,pmonth,pday,ptod,places=derive_tags(full,a.media_root)
                is_video=ext in VIDEO_EXT; is_raw=ext in RAW_EXT; edited=is_edited(fn,root,ext)
                srt={'date':None,'time':None,'lat':None,'lon':None}
                base=os.path.splitext(full)[0]
                for c in (base+'.SRT',base+'.srt'):
                    if os.path.exists(c): srt=parse_srt(c); break
                try: size=os.path.getsize(full)
                except: size=0
                rec={'id':h,'name':fn,'type':'video' if is_video else 'photo','raw':is_raw,'edited':edited,
                     'src':os.path.relpath(full,a.out),
                     'folder':os.path.relpath(root,a.media_root),
                     'folderlink':os.path.relpath(root,a.out),
                     'region':region,'municipio':municipio,'places':places,
                     'tod':tod_from_time(srt['time']) or ptod,
                     'lat':srt['lat'],'lon':srt['lon'],'time':srt['time'],
                     'size':size,'sizetxt':human_size(size)}
                if srt['date']:
                    rec['date']=srt['date']; rec['year']=srt['date'][:4]; rec['month']=srt['date'][5:7]; rec['day']=srt['date'][8:10]
                else:
                    rec['year']=pyear; rec['month']=pmonth or None; rec['day']=pday or None
                    rec['date']=f'{pyear}-{pmonth}-{pday}' if (pyear and pmonth and pday) else None
                try:
                    if is_video:
                        po=os.path.join(assets,h+'_p.jpg'); sp=os.path.join(assets,h+'_s.jpg')
                        dur,w,ht=probe(full); rec['dur']=dur; rec['durtxt']=human_dur(dur)
                        rec['res']=f'{w}x{ht}' if w and ht else ''
                        if not os.path.exists(po) or os.path.getsize(po)==0: make_poster(full,po,dur)
                        if not os.path.exists(sp) or os.path.getsize(sp)==0: make_sprite(full,sp,dur)
                        rec['poster']='assets/'+h+'_p.jpg' if os.path.exists(po) and os.path.getsize(po)>0 else None
                        rec['sprite']='assets/'+h+'_s.jpg' if os.path.exists(sp) and os.path.getsize(sp)>0 else None
                    else:
                        pv=os.path.join(assets,h+'_t.jpg')
                        if not os.path.exists(pv) or os.path.getsize(pv)==0: make_photo(full,pv,is_raw)
                        rec['poster']='assets/'+h+'_t.jpg' if os.path.exists(pv) and os.path.getsize(pv)>0 else None
                except Exception as e: rec['err']=str(e)
                tags=[region,municipio]+places
                tags.append('VIDEO' if is_video else 'FOTO')
                if is_raw: tags.append('RAW')
                tags.append('EDITADA' if edited else 'ORIGINAL')
                tags.append(ext.lstrip('.').upper())  # MOV, MP4, DNG, JPG, PNG, PSD
                if rec['tod']: tags.append(rec['tod'])
                if rec['year']: tags.append(rec['year'])
                if rec['month']:
                    try: tags.append(MES_NOMBRE[int(rec['month'])])
                    except: pass
                rec['tags']=[x for x in tags if x]
                items.append(rec)
                if nseen%20==0: print(f'  ...{nseen} ({rec["name"]})',flush=True)
                if nseen%200==0:
                    try: flush(a.out,items)
                    except Exception: pass
        if a.limit and nseen>a.limit: break
    if a.geocode:
        gcpath=os.path.join(os.path.dirname(os.path.abspath(a.out)),'geocache.json')
        try: cache=json.load(open(gcpath,encoding='utf-8'))
        except Exception: cache={}
        keys={}
        for r in items:
            if r.get('lat') is not None and r.get('lon') is not None:
                keys.setdefault(f"{round(r['lat'],4)},{round(r['lon'],4)}",(r['lat'],r['lon']))
        nuevos=[k for k in keys if k not in cache]
        print(f'  geocode: {len(keys)} ubicaciones unicas, {len(nuevos)} nuevas por consultar')
        for i,k in enumerate(nuevos,1):
            la,lo=keys[k]; cache[k]=geocode_lookup(la,lo); time.sleep(1.1)
            if i%10==0: print(f'    ...{i}/{len(nuevos)} geocodificadas',flush=True)
        try: json.dump(cache,open(gcpath,'w',encoding='utf-8'),ensure_ascii=False)
        except Exception: pass
        for r in items:
            if r.get('lat') is None: continue
            g=cache.get(f"{round(r['lat'],4)},{round(r['lon'],4)}") or {}
            r['geo']=g
            for fld in ('colonia','municipio','estado','road'):
                val=g.get(fld)
                if val and val not in r['tags']: r['tags'].append(val)
    flush(a.out,items)
    nv=sum(1 for x in items if x['type']=='video'); nf=len(items)-nv
    print(f'LISTO: {len(items)} items ({nv} video, {nf} foto) -> {a.out}/index.html')

HTML_TPL = r"""<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Catalogo DRONE</title>
<style>
*{box-sizing:border-box}body{margin:0;font:14px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;background:#0f0f10;color:#eee}
header{position:sticky;top:0;background:#1b1b1d;padding:12px 16px;border-bottom:1px solid #333;z-index:20}
h1{margin:0 0 8px;font-size:17px}#q{width:100%;padding:10px 12px;font-size:15px;border-radius:8px;border:1px solid #444;background:#222;color:#fff}
#chips{margin-top:8px;display:flex;flex-wrap:wrap;gap:6px}.chip{padding:3px 10px;border-radius:14px;background:#2a2a2a;border:1px solid #444;cursor:pointer;font-size:12px}
.chip.on{background:#3a6;border-color:#3a6;color:#000;font-weight:600}#stat{color:#999;font-size:12px;margin-left:8px}
#sort{background:#222;color:#ddd;border:1px solid #444;border-radius:6px;padding:4px 6px;font-size:12px;margin-top:8px}
.grp{margin:18px 16px 0}.ghead{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 10px;background:#1c1c20;border:1px solid #2c2c30;border-radius:8px;position:sticky;top:118px;z-index:10}
.ghead .gt{font-weight:600}.ghead .gd{color:#9bd;font-size:12px}.ghead .gc{color:#888;font-size:12px}
.ghead a{color:#7cf;text-decoration:none;font-size:12px;margin-left:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;padding:10px 0}
.card{background:#1c1c1e;border:1px solid #2c2c2e;border-radius:10px;overflow:hidden}
.thumb{position:relative;width:100%;aspect-ratio:16/9;background:#000 center/cover no-repeat;cursor:pointer}
.badge{position:absolute;top:6px;left:6px;background:rgba(0,0,0,.72);padding:1px 7px;border-radius:10px;font-size:11px}
.raw{position:absolute;top:6px;right:6px;background:#c83;padding:1px 7px;border-radius:10px;font-size:11px}
.dur{position:absolute;bottom:6px;right:6px;background:rgba(0,0,0,.78);padding:1px 7px;border-radius:6px;font-size:11px}
.meta{padding:8px 10px}.nm{font-weight:600;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row{color:#aaa;font-size:11px;margin-top:3px;display:flex;gap:8px;flex-wrap:wrap}.row b{color:#cde;font-weight:600}
.links{margin-top:5px;font-size:11px;display:flex;gap:10px}.links a{color:#7cf;text-decoration:none}
</style></head><body>
<header><h1>📁 Catalogo DRONE<span id=stat></span></h1>
<input id=q placeholder='Buscar: ej. "zocalo", "alameda 2023", "cuautla noche" ...'>
<div><select id=sort><option value=date>Ordenar grupos: fecha (reciente)</option><option value=datea>fecha (antigua)</option><option value=name>nombre carpeta</option><option value=count>cantidad</option></select>
<span id=chips></span></div></header>
<div id=out></div>
<script>
const DATA=/*__DATA__*/;
const out=document.getElementById('out'),q=document.getElementById('q'),stat=document.getElementById('stat'),chips=document.getElementById('chips'),sortSel=document.getElementById('sort');
DATA.forEach(d=>d._s=(d.tags.join(' ')+' '+d.folder+' '+d.name).toLowerCase());
let active=new Set();
function mkchip(label,val){const c=document.createElement('span');c.className='chip';c.textContent=label;c.onclick=()=>{c.classList.toggle('on');active.has(val)?active.delete(val):active.add(val);render()};chips.appendChild(c)}
const nVid=DATA.filter(d=>d.type==='video').length,nFot=DATA.filter(d=>d.type==='photo').length,nRaw=DATA.filter(d=>d.raw).length;
const nEd=DATA.filter(d=>d.edited).length,nOr=DATA.length-nEd;
const nExt=DATA.filter(d=>d.external).length,nAer=DATA.filter(d=>d.aerial).length;
mkchip('▶ VIDEO ('+nVid+')','VIDEO');mkchip('📷 FOTO ('+nFot+')','FOTO');if(nRaw)mkchip('RAW ('+nRaw+')','RAW');if(nEd)mkchip('✏️ EDITADA ('+nEd+')','EDITADA');if(nOr)mkchip('ORIGINAL ('+nOr+')','ORIGINAL');if(nExt)mkchip('📦 FUERA DE DRONE ('+nExt+')','FUERA DE DRONE');if(nAer)mkchip('🛸 AÉREO ('+nAer+')','AEREO');
const freq={};DATA.forEach(d=>d.places.forEach(p=>freq[p]=(freq[p]||0)+1));
Object.entries(freq).sort((a,b)=>b[1]-a[1]).slice(0,12).forEach(([p,n])=>mkchip(p+' ('+n+')',p));
function scrub(el,d){if(!d.sprite)return;const N=16,C=4;
 el.onmousemove=e=>{const r=el.getBoundingClientRect();let i=Math.max(0,Math.min(N-1,Math.floor((e.clientX-r.left)/r.width*N)));const col=i%C,row=(i/C)|0;el.style.backgroundImage=`url('${d.sprite}')`;el.style.backgroundSize=`${C*100}% ${C*100}%`;el.style.backgroundPosition=`${col/(C-1)*100}% ${row/(C-1)*100}%`};
 el.onmouseleave=()=>{el.style.backgroundImage=`url('${d.poster}')`;el.style.backgroundSize='cover';el.style.backgroundPosition='center'}}
function card(d){const c=document.createElement('div');c.className='card';
 const t=document.createElement('div');t.className='thumb';if(d.poster)t.style.backgroundImage=`url('${d.poster}')`;
 t.innerHTML=`<span class=badge>${d.type==='video'?'▶ video':(d.raw?'📷 RAW':'📷 foto')}</span>`+(d.raw?'<span class=raw>+DNG</span>':'')+(d.durtxt?`<span class=dur>${d.durtxt}</span>`:'');
 if(d.type==='video')scrub(t,d);t.onclick=()=>d.type==='photo'&&window.openPhoto?window.openPhoto(d):window.open(encodeURI(d.src),'_blank');
 const m=document.createElement('div');m.className='meta';
 const gps=(d.lat!=null&&d.lon!=null)?`<a href="https://maps.google.com/?q=${d.lat},${d.lon}" target=_blank>📍 ${d.lat},${d.lon}</a>`:'';
 const geo=(d.geo&&(d.geo.colonia||d.geo.municipio||d.geo.road))?`<div class=row style="color:#9c9">🗺 ${[d.geo.road,d.geo.colonia,d.geo.municipio].filter(Boolean).join(', ')}</div>`:'';
 const fh=`📅 ${d.date||'(sin fecha)'}${d.time?' · 🕐 '+d.time.slice(0,5):''}${d.tod?' · '+d.tod:''}`;
 const modelo=d.model?`<span>🛸 <b>${d.model}</b></span>`:'';
 const externo=d.external?`<div class=row style="color:#e8a55a">📦 FUERA DE DRONE${d.origin?' · '+d.origin:''}${d.aerial?' · AÉREO':''}</div><div class=row style="color:#888;font-size:10px;word-break:break-all">📁 ${d.realpath||''}</div>`:'';
 m.innerHTML=`<div class=nm title="${d.name}">${d.edited?'✏️ ':''}${d.name}</div>`+
  `<div class=row style="color:#9bd">${fh}</div>`+
  `<div class=row>${d.durtxt?`<span>⏱ <b>${d.durtxt}</b></span>`:''}<span>💾 <b>${d.sizetxt}</b></span>${d.res?`<span>🖥 ${d.res}</span>`:''}${modelo}</div>`+
  externo+geo+`<div class=row>${gps}</div>`+
  `<div class=links>${d.type==='photo'?`<a href="#" onclick="openPhoto(DATA.find(x=>x.id==='${d.id}'));return false">⬇ JPG / editar</a>`:''}<a href="${encodeURI(d.src)}" target=_blank>abrir archivo ↗</a><a href="${encodeURI(d.folderlink)}" target=_blank>📂 abrir carpeta</a></div>`;
 c.appendChild(t);c.appendChild(m);return c}
function render(){const terms=q.value.toLowerCase().split(/\s+/).filter(Boolean);
 const res=DATA.filter(d=>{for(const t of terms)if(!d._s.includes(t))return false;for(const p of active)if(!d.tags.includes(p))return false;return true});
 window.__res=res;const nv=res.filter(d=>d.type==='video').length;stat.textContent=`— ${res.length} resultados (${nv} video, ${res.length-nv} foto)`;
 const groups={};res.forEach(d=>{(groups[d.folder]=groups[d.folder]||[]).push(d)});
 let keys=Object.keys(groups);const s=sortSel.value;
 const gdate=k=>{const a=groups[k];for(const d of a)if(d.date)return d.date;return (a[0].year||'')+(a[0].month||'')+(a[0].day||'')};
 if(s==='date')keys.sort((a,b)=>gdate(b).localeCompare(gdate(a)));
 else if(s==='datea')keys.sort((a,b)=>gdate(a).localeCompare(gdate(b)));
 else if(s==='count')keys.sort((a,b)=>groups[b].length-groups[a].length);
 else keys.sort();
 out.innerHTML='';const frag=document.createDocumentFragment();let shown=0;
 for(const k of keys){if(shown>1200){const w=document.createElement('div');w.style.cssText='padding:16px;color:#999';w.textContent='… afina la búsqueda para ver más.';frag.appendChild(w);break}
  const a=groups[k];const g=document.createElement('div');g.className='grp';
  const date=gdate(k);const dd=a.find(d=>d.date);
  const head=document.createElement('div');head.className='ghead';
  head.innerHTML=`<span class=gt>📂 ${k.replace(/</g,'')}</span>`+(dd&&dd.date?`<span class=gd>${dd.date}${dd.tod?' · '+dd.tod:''}</span>`:'')+`<span class=gc>${a.length} archivo(s)</span>`+`<a href="${encodeURI(a[0].folderlink)}" target=_blank>📂 abrir esta carpeta ↗</a>`;
  const grid=document.createElement('div');grid.className='grid';
  a.forEach(d=>{grid.appendChild(card(d));shown++});
  g.appendChild(head);g.appendChild(grid);frag.appendChild(g)}
 out.appendChild(frag)}
q.addEventListener('input',render);sortSel.addEventListener('change',render);render();
</script>
<!--__EDITOR__-->
</body></html>"""

if __name__=='__main__': main()

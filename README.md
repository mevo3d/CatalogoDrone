# Catálogo DRONE

Generador de catálogos web navegables para el material de dron (videos y fotos DJI/Osmo) almacenado en un NAS. Es no destructivo: nunca mueve ni modifica los originales, solo genera previews, metadatos y páginas HTML.

## Qué hace

- **Videos**: póster (1 frame), sprite 4x4 para scrub, y metadatos (duración, tamaño, resolución, GPS, fecha/hora).
- **Fotos**: preview JPG; para RAW (DNG/NEF/ARW/CR2) extrae el JPEG embebido con `dcraw -e`.
- Lee el `.SRT` hermano de cada video para obtener fecha, hora y GPS.
- Deriva etiquetas de la ruta (región, municipio, colonia, lugar, tema) y geocodifica (`geocache.json`).
- Detecta material editado (carpetas FINAL, EDITADAS, nombres con MEJORADO, etc.).
- Cada catálogo es un HTML autocontenido con buscador en vivo y resultados agrupados por carpeta.
- Un menú maestro (`index.html`) lista todos los catálogos con su conteo de videos y fotos.

## Estructura

| Archivo / carpeta | Descripción |
|---|---|
| `build_catalog.py` | Generador de un catálogo (`catalog.json` + `index.html`). |
| `actualizar.sh` | Re-escanea las fuentes (solo procesa archivos nuevos), reconstruye el menú y levanta el servidor web (puerto 8088). |
| `menu.py` | Reconstruye el menú maestro auto-detectando los catálogos. |
| `index.html` | Menú maestro. |
| `ARCHIVO_COMPLETO/` | Catálogo de todas las regiones. |
| `FUERA_DE_DRONE/` | Material de dron ubicado fuera de la carpeta DRONE (se cataloga sin moverlo; lista en `lista_externos.txt`). |
| `PILOTO_CENTRO/`, `PILOTO_CDMX/` | Catálogos piloto (Cuautla Centro, CDMX), subconjuntos del completo. |
| `geocache.json` | Caché de geocodificación. |

## Uso

```sh
python3 build_catalog.py --out OUT --media-root /volume5/DRONE/MEDIA \
   --ffmpeg ./bin/ffmpeg --ffprobe ./bin/ffprobe \
   --src "ruta1" --src "ruta2" [--limit N] [--geocode] [--only-drone]

./actualizar.sh   # en el NAS, cuando haya material nuevo
```

### Enlace con el servidor

El repo vive en el Mac; el NAS (`imevoserver`, usuario `mevo`, llave `~/.ssh/id_ed25519`) solo recibe archivos.

```sh
./deploy.sh --dry   # ver qué se enviaría
./deploy.sh         # enviar código a /volume5/DRONE/_CATALOGO
ssh imevoserver 'cd /volume5/DRONE/_CATALOGO && ./actualizar.sh'   # regenerar catálogos
./pull.sh           # traer catálogos regenerados para versionarlos
```

Requiere Python 3, ffmpeg/ffprobe y dcraw (para RAW). Las rutas del NAS (`/volume5/DRONE/...`) están fijas en los scripts.

## Versiones

El número de versión actual está en `VERSION`. El historial está en [CHANGELOG.md](CHANGELOG.md). Seguimos versionado `MAYOR.MENOR.PARCHE`, empezando en `0.0.0`.

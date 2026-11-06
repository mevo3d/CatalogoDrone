# Changelog

Formato `MAYOR.MENOR.PARCHE`. Cada versión se marca con un tag de git (`v0.0.0`, ...).

## [0.2.0] - 2026-11-06
Descarga en JPG y edición rápida de fotos desde el catálogo.
- Al abrir una foto (clic en la miniatura o "⬇ JPG / editar") pregunta: descargar original (JPG) o edición rápida.
- Elección de resolución: original, 4K, 2560, Full HD, 1280, 800 px.
- Funciona con JPG, PNG y también DNG: el RAW se revela en el navegador a resolución completa (LibRaw-WASM en `vendor/libraw/`, sin internet).
- Edición rápida: luz, contraste, temperatura, tono (hue), saturación y vibración, con vista previa en vivo y "mantén pulsado para ver original".
- Estilos guardados (por navegador), "último usado" y "estilo del día" que se recuerda al descargar.
- Aplicar un estilo a varias fotos (carpeta, mismo día o resultados filtrados) y bajarlas en un ZIP; opción de omitir el DNG si hay JPG con el mismo nombre.
- `editor_snippet.html` contiene el editor; `build_catalog.py` lo inyecta y suma `--render-only` para regenerar los `index.html` sin reescanear.
- `deploy.sh` ahora también envía `editor_snippet.html`, `vendor/` y los `index.html` de los catálogos.
- Limitación: fotos de `FUERA_DE_DRONE` (rutas fuera de la web) usan solo la miniatura de 480 px.

## [0.1.0] - 2026-11-06
Enlace con el servidor (imevoserver).
- `deploy.sh`: envía el código al NAS por tar sobre SSH (`--dry` para simular). No borra nada en el servidor.
- `pull.sh`: trae los catálogos regenerados (`catalog.json`, `index.html`, `geocache.json`) para versionarlos.
- Flujo: se trabaja y versiona en el Mac; el servidor solo recibe archivos (sin git ahí).

## [0.0.0] - 2026-11-05
Primer push: estado inicial del proyecto.
- Generador de catálogo (`build_catalog.py`) con posters, sprites, previews y metadatos.
- Script de actualización (`actualizar.sh`) y menú maestro (`menu.py`, `index.html`).
- Catálogos generados: ARCHIVO_COMPLETO, FUERA_DE_DRONE, PILOTO_CENTRO, PILOTO_CDMX.
- Caché de geocodificación.

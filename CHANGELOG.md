# Changelog

Formato `MAYOR.MENOR.PARCHE`. Cada versión se marca con un tag de git (`v0.0.0`, ...).

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

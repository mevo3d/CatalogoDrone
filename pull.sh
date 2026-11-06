#!/bin/sh
# Trae del servidor los catalogos generados (catalog.json + index.html de cada uno,
# menu maestro y geocache) para versionarlos aqui. No trae assets ni videos.
# Uso: ./pull.sh
HOST=imevoserver
SRC=/volume5/DRONE/_CATALOGO
cd "$(dirname "$0")" || exit 1
ssh "$HOST" "cd $SRC && find . -maxdepth 2 \( -name catalog.json -o -name index.html \) -not -path './assets/*' -not -path './bin/*' -not -path './PRUEBA*' -print; echo ./geocache.json" \
  | sed 's|^\./||' > /tmp/catdrone_pull.list
ssh "$HOST" "cd $SRC && tar cf - -T -" < /tmp/catdrone_pull.list | tar xf - && echo "OK: traidos $(wc -l < /tmp/catdrone_pull.list) archivos"
rm -f /tmp/catdrone_pull.list

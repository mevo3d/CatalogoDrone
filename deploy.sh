#!/bin/sh
# Envia el codigo de este Mac al servidor (tar por SSH). No borra nada en el servidor.
# Uso: ./deploy.sh [--dry]   (--dry solo lista lo que enviaria)
HOST=imevoserver
DEST=/volume5/DRONE/_CATALOGO
cd "$(dirname "$0")" || exit 1
FILES="build_catalog.py editor_snippet.html actualizar.sh menu.py lista_externos.txt vendor ARCHIVO_COMPLETO/index.html FUERA_DE_DRONE/index.html PILOTO_CENTRO/index.html PILOTO_CDMX/index.html"
if [ "$1" = "--dry" ]; then
  echo "Se enviaria a $HOST:$DEST ->"; ls -ld $FILES; exit 0
fi
COPYFILE_DISABLE=1 tar cf - $FILES | ssh "$HOST" "cd $DEST && tar xf - && chmod +x actualizar.sh build_catalog.py menu.py" \
  && echo "OK: codigo enviado a $HOST:$DEST (ejecuta ./actualizar.sh en el servidor para regenerar)"

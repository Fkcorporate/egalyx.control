#!/usr/bin/env bash
# Egalyx — restauration d'une sauvegarde (REMPLACE les données actuelles).
# Usage, depuis la racine du projet :
#   ./deploiement/on-premise/scripts/restaurer.sh sauvegardes/egalyx_20261125_013000_base.dump [sauvegardes/egalyx_20261125_013000_fichiers.tar.gz]
set -euo pipefail
cd "$(dirname "$0")/../../.."
BASE="${1:?Indiquez le fichier .dump de la base}"
FICHIERS="${2:-}"
[ -f "$BASE" ] || { echo "Fichier introuvable : $BASE"; exit 1; }
set -a; . ./.env; set +a
read -r -p "Les données actuelles vont être REMPLACÉES par $BASE. Taper OUI pour continuer : " r
[ "$r" = "OUI" ] || { echo "Abandon."; exit 1; }
echo "→ Sauvegarde de sécurité de l'état actuel…"
./deploiement/on-premise/scripts/sauvegarder.sh
docker compose stop web
echo "→ Restauration de la base…"
docker compose exec -T db pg_restore -U "${POSTGRES_USER:-egalyx}" -d "${POSTGRES_DB:-egalyx}" --clean --if-exists --no-owner < "$BASE"
if [ -n "$FICHIERS" ]; then
  echo "→ Restauration des fichiers…"
  docker compose run --rm -T --no-deps --entrypoint sh web -c 'rm -rf /donnees/* && tar xzf - -C /donnees' < "$FICHIERS"
fi
docker compose start web
echo "✅ Restauration terminée."

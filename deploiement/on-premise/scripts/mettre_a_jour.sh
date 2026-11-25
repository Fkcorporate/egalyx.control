#!/usr/bin/env bash
# Egalyx — installer une mise à jour livrée par Egalyx.
# Usage, depuis la racine du projet :
#   ./deploiement/on-premise/scripts/mettre_a_jour.sh /chemin/vers/paquet_de_mise_a_jour     (dossier décompressé)
#   ./deploiement/on-premise/scripts/mettre_a_jour.sh                                        (code déjà mis à jour, ex. git pull)
set -euo pipefail
cd "$(dirname "$0")/../../.."
echo "→ Sauvegarde avant mise à jour…"
./deploiement/on-premise/scripts/sauvegarder.sh
if [ -n "${1:-}" ]; then
  echo "→ Copie des fichiers de la mise à jour…"
  python3 "$1/installer_mise_a_jour.py" "$(pwd)"
fi
echo "→ Reconstruction et redémarrage…"
docker compose build web
docker compose up -d
echo "→ Mise à jour du schéma de la base…"
sleep 10
docker compose exec -T web flask mettre-a-jour-base
docker compose exec -T web flask verifier-installation || true
echo "✅ Mise à jour installée."

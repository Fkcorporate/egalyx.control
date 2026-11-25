#!/usr/bin/env bash
# Egalyx — sauvegarde complète : base de données + fichiers déposés (logos, preuves, pièces jointes…).
# À lancer depuis la racine du projet :   ./deploiement/on-premise/scripts/sauvegarder.sh
# Résultat : sauvegardes/egalyx_<date>_base.dump et egalyx_<date>_fichiers.tar.gz (gardés 30 jours).
# Copiez ensuite le dossier sauvegardes/ hors du serveur (NAS, autre site) : une sauvegarde sur le même disque
# ne protège pas d'une panne du serveur.
# Tâche planifiée conseillée (crontab -e) :  30 1 * * *  cd /opt/egalyx && ./deploiement/on-premise/scripts/sauvegarder.sh
set -euo pipefail
cd "$(dirname "$0")/../../.."
set -a; . ./.env; set +a
mkdir -p sauvegardes
DATE=$(date +%Y%m%d_%H%M%S)
echo "→ Base de données…"
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-egalyx}" -d "${POSTGRES_DB:-egalyx}" -Fc > "sauvegardes/egalyx_${DATE}_base.dump"
echo "→ Fichiers déposés…"
docker compose exec -T web tar czf - -C /donnees . > "sauvegardes/egalyx_${DATE}_fichiers.tar.gz"
find sauvegardes -name 'egalyx_*' -mtime +30 -delete
echo "✅ Sauvegarde terminée :"
ls -lh "sauvegardes/egalyx_${DATE}_"*

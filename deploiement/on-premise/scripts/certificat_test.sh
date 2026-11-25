#!/usr/bin/env bash
# Egalyx — certificat HTTPS auto-signé, POUR UN ESSAI SEULEMENT (le navigateur affichera un avertissement).
# En production, utilisez le certificat fourni par le client : egalyx.crt et egalyx.key dans
# deploiement/on-premise/certificats/
set -euo pipefail
cd "$(dirname "$0")/.."
DOMAINE="${1:-egalyx.client.local}"
mkdir -p certificats
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout certificats/egalyx.key -out certificats/egalyx.crt \
  -subj "/CN=${DOMAINE}" -addext "subjectAltName=DNS:${DOMAINE}"
chmod 600 certificats/egalyx.key
echo "✅ Certificat d'essai créé pour ${DOMAINE} (valable 1 an)."

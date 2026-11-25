# Egalyx Control — installation chez un client (on-premise)

Ce guide s'adresse à la personne qui installe Egalyx sur le serveur du client (Egalyx ou l'informaticien du client).
Durée : environ 1 heure, si les prérequis (fichier `PREREQUIS_CLIENT.md`) sont réunis.

L'installation comprend trois éléments, tous sur le serveur du client :

| Élément | Rôle |
|---|---|
| **web** | l'application Egalyx Control |
| **db** | la base de données PostgreSQL 15 (jamais accessible hors du serveur) |
| **nginx** | la porte d'entrée HTTPS (ports 80 et 443) |

Les données restent sur le serveur du client. Rien n'est envoyé à Egalyx, sauf si le client renseigne une clé
d'intelligence artificielle (facultative).

---

## 1. Préparer le serveur

Sur un serveur Ubuntu 22.04 ou 24.04 (ou Debian 12), connecté en administrateur :

```bash
# Docker et son module compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER      # puis se déconnecter / reconnecter
docker compose version             # doit afficher « Docker Compose version v2… »
```

Pare-feu : ouvrir **443** (et 80, qui redirige vers 443) depuis le réseau des utilisateurs. Rien d'autre.

## 2. Copier l'application

```bash
sudo mkdir -p /opt/egalyx && sudo chown $USER /opt/egalyx
# copier ici le code fourni par Egalyx (archive .zip décompressée, ou git clone)
cd /opt/egalyx
```

## 3. Remplir les réglages

```bash
cp deploiement/on-premise/env.exemple .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # → SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(30))"   # → POSTGRES_PASSWORD
nano .env
chmod 600 .env
```

À remplir au minimum : `SECRET_KEY`, `POSTGRES_PASSWORD`, `EGALYX_DOMAINE`, `EGALYX_LICENCE` (clé fournie par Egalyx, une ligne `EGX1-…`) et les réglages `MAIL_…` du client.

Sans clé de licence, l'outil affiche « en pause » ; le super administrateur peut aussi coller la clé plus tard sur la page `https://<adresse>/licence`.

## 4. Installer le certificat HTTPS

Le client fournit un certificat pour son adresse (ex. `egalyx.sodemi.ci`) :

```bash
mkdir -p deploiement/on-premise/certificats
cp certificat_client.crt deploiement/on-premise/certificats/egalyx.crt   # certificat + chaîne intermédiaire
cp cle_client.key        deploiement/on-premise/certificats/egalyx.key
chmod 600 deploiement/on-premise/certificats/egalyx.key
```

Pour un **essai** seulement (le navigateur affichera un avertissement) :
`./deploiement/on-premise/scripts/certificat_test.sh egalyx.client.local`

## 5. Démarrer

```bash
docker compose up -d --build        # 5 à 10 minutes la première fois
docker compose ps                   # les 3 éléments doivent être « running » / « healthy »
docker compose logs -f web          # suivre le démarrage (Ctrl+C pour quitter)
```

## 6. Créer le premier compte et vérifier

```bash
docker compose exec web flask creer-super-admin
docker compose exec web flask verifier-installation
```

`verifier-installation` doit finir par **« Installation prête. »**. Sinon, il indique quoi corriger.

Ouvrez ensuite `https://<adresse du client>` :

1. connectez-vous avec le super administrateur et **activez la double authentification** ;
2. créez l'organisation du client (Super admin → Gestion clients), sa formule et son administrateur ;
3. réglages de l'organisation : heure, devise, papiers à en-tête, modèles de lettre de mission.

## 7. Sauvegardes (indispensable)

- **Automatique** : la base est sauvegardée chaque nuit à 2 h dans `/opt/egalyx/sauvegardes`.
- **Complète** (base + fichiers déposés), à planifier chaque nuit :

```bash
crontab -e
30 1 * * *  cd /opt/egalyx && ./deploiement/on-premise/scripts/sauvegarder.sh >> sauvegardes/journal.txt 2>&1
```

- **Copier `sauvegardes/` hors du serveur** (NAS, second site) : c'est la responsabilité du client.
- **Tester une restauration** une fois par an :
  `./deploiement/on-premise/scripts/restaurer.sh sauvegardes/egalyx_<date>_base.dump sauvegardes/egalyx_<date>_fichiers.tar.gz`

## 8. Mises à jour livrées par Egalyx

```bash
cd /opt/egalyx
./deploiement/on-premise/scripts/mettre_a_jour.sh /chemin/vers/le_paquet_decompresse
```

Le script : sauvegarde → copie des fichiers (anciens fichiers gardés dans `sauvegarde_maj_<date>/`) → reconstruction →
redémarrage → mise à jour de la base → vérification. Interruption de service : 1 à 3 minutes.

Mettre aussi à jour le système et Docker chaque mois : `sudo apt update && sudo apt upgrade`.

## 9. Commandes utiles

| Besoin | Commande |
|---|---|
| État des services | `docker compose ps` |
| Journaux de l'application | `docker compose logs --tail 200 web` |
| Redémarrer | `docker compose restart web` |
| Arrêter / relancer tout | `docker compose down` / `docker compose up -d` |
| Mot de passe oublié (super admin) | `docker compose exec web python3 reinitialiser_mot_de_passe.py <identifiant>` |
| … et téléphone perdu (2FA) | ajouter `--sans-2fa` |
| Contrôle de l'installation | `docker compose exec web flask verifier-installation` |
| État de la licence | `docker compose exec web flask licence` |
| Renouveler la licence | page `/licence` (super admin), ou nouvelle valeur `EGALYX_LICENCE` dans `.env` puis `docker compose up -d` |

⚠️ `docker compose down -v` **efface la base de données**. Ne jamais utiliser `-v` sans sauvegarde.

## 10. En cas de problème

| Symptôme | Cause probable | Que faire |
|---|---|---|
| Page « 502 Bad Gateway » | l'application démarre encore ou a planté | attendre 1 min ; `docker compose logs --tail 100 web` |
| `POSTGRES_PASSWORD manquant` | `.env` absent ou incomplet | étape 3 |
| Nginx redémarre en boucle | certificat absent | étape 4 (`egalyx.crt` et `egalyx.key`) |
| Connexion impossible, page qui se recharge | site ouvert en `http://` | utiliser `https://`, ou `EGALYX_HTTPS=0` pour un essai |
| Pas d'e-mails | réglages `MAIL_…` | vérifier avec l'informaticien (port 587, compte d'envoi autorisé) |

Support Egalyx : contact@egalyx.com — joindre la sortie de `flask verifier-installation` et les 200 dernières lignes du journal.

---

### Installation sans Docker (si le client l'impose)

Ubuntu, Python 3.11 à 3.13, PostgreSQL 15+, Nginx :

```bash
sudo apt install python3-venv postgresql nginx libpango-1.0-0 libpangoft2-1.0-0
python3 -m venv /opt/egalyx/venv && /opt/egalyx/venv/bin/pip install -r requirements.txt weasyprint
# variables : les mêmes que .env, plus EGALYX_PRODUCTION=1, EGALYX_LICENCE_REQUISE=1, EGALYX_DONNEES=/var/lib/egalyx,
#             EGALYX_DOSSIER_SAUVEGARDES=/var/backups/egalyx, DATABASE_URL=postgresql://…
# service : gunicorn app:app --bind 127.0.0.1:8000 --workers=1 --threads=8 --worker-class=gthread --timeout=120
#           (un seul processus : sinon les e-mails planifiés partent en double)
# Nginx : reprendre deploiement/on-premise/nginx/egalyx.conf en remplaçant « web:8000 » par « 127.0.0.1:8000 »
```

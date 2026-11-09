# Egalyx Control — v4 : modules ajoutés

## Installation (remplace la v3)
1. Remplacez `app.py`, `models.py` et `cotation.py`, et ajoutez le dossier `egalyx/`.
2. **Fusionnez** le dossier `templates/` avec le vôtre (ne le remplacez pas) : il contient `templates/egalyx/` et les pages modifiées.
3. Aucune nouvelle dépendance Python n'est nécessaire.
4. Au démarrage, les nouvelles tables et colonnes sont créées automatiquement. Les colonnes manquantes sont seulement ajoutées : rien n'est supprimé.
   - Pour vérifier avant d'appliquer : `flask mettre-a-jour-base --simulation`
   - Pour appliquer : `flask mettre-a-jour-base`
5. Faites une sauvegarde avant la mise à jour : `flask sauvegarder`.

## Ce qui a été ajouté

| Module | Adresse | Pour qui |
|---|---|---|
| Double authentification (code TOTP + 8 codes de secours) | Menu utilisateur > Sécurité du compte | Tous les utilisateurs. **Obligatoire pour les administrateurs.** |
| Connexion unique Microsoft / Google | Boutons sur la page de connexion | Uniquement quand les variables `SSO_*` sont définies |
| Dispositif d'alerte interne (Sapin II) | Lien public `/alerte/<référence client>`, back-office dans Conformité > Alertes internes | Lanceurs d'alerte (anonymes possibles) ; référents (rôle conformité ou admin client) |
| Tiers & LCB-FT | Conformité > Tiers & LCB-FT | Tous |
| Tiers & LCB-FT : listes de sanctions (import CSV) | Conformité > Listes de sanctions | Super admin |
| Signature interne | Bandeau « Signer » sur la fiche audit et la fiche plan d'action | Tous |
| Paramètres des risques | Administration > Paramètres des risques | Admin client |
| Abonnement et paiement en ligne (CinetPay + Stripe) | Administration > Abonnement | Admin client |
| Export complet des données (ZIP JSON + CSV) | Administration > Export des données | Admin client |
| Documentation de l'API | `/api/documentation` et `/api/v1/openapi.json` | Tous |
| Éditeur d'organigramme | Bouton « Modifier l'organigramme » sur un processus | Tous |
| Contrôles d'un processus | Carte sur la fiche processus | Tous |
| Sauvegardes | Administration > Sauvegardes | Super admin |

Détail de quelques modules :
- **Paramètres des risques** : seuils de cotation, taux de maîtrise, appétence au risque et listes GAFI/LCB-FT.
- **Appétence au risque** : les risques au-delà de l'appétence sont signalés sur le tableau de bord stratégique et sur la fiche risque.
- **Signature interne** : la signature se confirme par un code reçu par e-mail. Le document est horodaté et son empreinte SHA-256 est enregistrée, ce qui permet de détecter une modification faite après la signature.

## Corrections incluses
- **E-mail** : les paramètres SMTP se règlent dans les variables d'environnement et le certificat du serveur est désormais vérifié. Avant, la vérification était désactivée.
- **Diagnostic SMTP** : `/check-credentials` affichait la fin du mot de passe. Il est maintenant réservé au super admin et n'affiche plus aucun secret.
- **API `/api/v1`** :
  - Elle renvoyait des listes vides depuis la v3. Elle est corrigée et limitée à l'organisation de la clé.
  - `POST /api/v1/audits` n'était plus bloqué par la protection CSRF.
- **Cotation** : le recalcul utilise les paramètres de l'organisation de chaque risque. Avant, il recalculait toutes les organisations.
- **Ajout d'un contrôle sur un processus** :
  - Le risque couvert est maintenant demandé.
  - Une référence est générée.
  - L'accès à l'organisation est vérifié, ainsi que pour l'ajout d'une étape.
- **Provisionnement « serveur dédié »** : il n'invente plus d'adresse IP. Il enregistre une demande, à compléter avec les vraies informations du serveur.
- **Page sécurité** :
  - Retiré de la page sécurité : ISO 27001, SOC 2, HDS, AES-256, bug bounty, tests d'intrusion et 99,9 %.
  - Retirées aussi des badges de connexion, de l'accueil, de la landing, de « À propos », des tarifs, de la documentation, de la politique de confidentialité et de la pro forma.
  - Elles sont remplacées par des mesures qui existent réellement dans l'application.

## Variables d'environnement

```bash
# Obligatoire en production
EGALYX_CLE_CHIFFREMENT=...        # clé Fernet. À générer avec :
                                  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
EGALYX_URL_PUBLIQUE=https://app.egalyx.com

# E-mail (sans mot de passe : simulation, rien n'est envoyé)
SMTP_HOTE=smtp.hostinger.com
SMTP_PORT=465
SMTP_SECURITE=ssl                 # ssl | starttls | aucune
SMTP_EXPEDITEUR=contact@egalyx.com
SMTP_MOT_DE_PASSE=...             # l'ancien HOSTINGER_EMAIL_PASSWORD est encore accepté

# Double authentification
EGALYX_2FA_OBLIGATOIRE_ADMINS=1   # 0 pour ne plus l'exiger des administrateurs

# SSO (facultatif)
SSO_MICROSOFT_CLIENT_ID=...
SSO_MICROSOFT_CLIENT_SECRET=...
SSO_MICROSOFT_TENANTS=<id d'annuaire>   # obligatoire pour activer Microsoft
SSO_GOOGLE_CLIENT_ID=...
SSO_GOOGLE_CLIENT_SECRET=...
SSO_GOOGLE_DOMAINES=acme.ci             # recommandé
# URL de retour à déclarer chez Microsoft / Google :
#   <EGALYX_URL_PUBLIQUE>/sso/microsoft/retour
#   <EGALYX_URL_PUBLIQUE>/sso/google/retour

# Paiement (chaque prestataire s'active quand ses clés sont présentes)
CINETPAY_APIKEY=...
CINETPAY_SITE_ID=...
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...         # webhook : <URL>/paiement/stripe/webhook
                                  # événements : checkout.session.completed et checkout.session.expired

# Sauvegardes
EGALYX_SAUVEGARDE_AUTO=1
EGALYX_SAUVEGARDE_HEURE=2
EGALYX_SAUVEGARDE_RETENTION_JOURS=30
EGALYX_DOSSIER_SAUVEGARDES=/srv/egalyx/sauvegardes
EGALYX_MAJ_SCHEMA_AUTO=1
```

## Points d'attention
- **2FA des administrateurs** : à la première connexion après la mise à jour, chaque administrateur doit activer la 2FA. Un administrateur peut réinitialiser la 2FA d'un utilisateur depuis la liste des utilisateurs (icône téléphone).
- **Listes de sanctions** : le criblage ne contrôle rien tant qu'aucune liste n'est importée. Importez les listes ONU, UE, OFAC et les listes nationales en CSV, avec les colonnes `nom;alias;pays;programme;type`.
- **Listes du GAFI** : celles fournies datent de juin 2026. Vérifiez-les après chaque plénière, puis mettez-les à jour dans Paramètres des risques.
- **Sauvegardes** : copiez le dossier de sauvegardes hors du serveur. PostgreSQL nécessite `pg_dump` et MySQL nécessite `mysqldump`.
- **Fichiers obsolètes** : supprimez les copies (`home copie*.html`, `*.backup`, `app_avant.py`, `models_avant.py`). Elles contiennent encore les anciennes mentions.

## Tests

```bash
python3 -m pytest -q tests/
```

La suite compte 37 tests :
- fonctions de calcul ;
- parcours 2FA, alerte et paiement ;
- rendu des gabarits.

Ces tests utilisent des doubles de SQLAlchemy et de Flask-Login. Un essai sur votre base réelle reste nécessaire, de préférence sur une copie.

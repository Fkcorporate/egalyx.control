# Egalyx Control — ce que nous demandons à votre équipe informatique

Pour installer Egalyx Control dans vos locaux (« on-premise »), merci de préparer les éléments ci-dessous.
Vos données resteront sur votre serveur.

## 1. Un serveur

| | Minimum | Conseillé (plus de 50 utilisateurs) |
|---|---|---|
| Système | Ubuntu 22.04 ou 24.04 LTS (ou Debian 12), 64 bits | idem |
| Processeur | 2 cœurs | 4 cœurs |
| Mémoire | 4 Go | 8 Go |
| Disque | 50 Go SSD | 100 Go SSD |
| Logiciels | Docker et Docker Compose v2 (nous pouvons les installer) | idem |

Machine virtuelle acceptée (VMware, Hyper-V, Proxmox…). Le serveur doit pouvoir télécharger des paquets
sur Internet pendant l'installation et les mises à jour.

## 2. Une adresse et un certificat

- Une adresse interne pour le site, par exemple **egalyx.votre-entreprise.ci**, pointant vers le serveur (DNS).
- Un **certificat HTTPS** pour cette adresse : fichier du certificat (avec la chaîne intermédiaire) et clé privée.
- Pare-feu : port **443** ouvert depuis le réseau des utilisateurs (et 80, qui redirige vers 443).

## 3. L'envoi des e-mails

Un compte d'envoi pour les notifications (alertes, relances, lettres de mission) :
serveur SMTP, port (587 en général), identifiant, mot de passe, et adresse d'expéditeur
(ex. audit@votre-entreprise.ci).

## 4. Un accès pour Egalyx

Un accès à distance au serveur (VPN ou équivalent, compte administrateur) pendant l'installation,
puis pour les mises à jour et le support, selon les modalités de votre politique de sécurité.

## 5. Ce qui reste sous votre responsabilité

- **Sauvegardes** : copier chaque nuit le dossier des sauvegardes produit par Egalyx vers un autre support
  (NAS, second site), et tester une restauration une fois par an.
- **Sécurité du serveur** : mises à jour du système, antivirus et supervision selon vos règles.
- **Comptes utilisateurs** : création par votre administrateur Egalyx.

## Calendrier type

| Étape | Durée |
|---|---|
| Préparation du serveur, de l'adresse et du certificat (votre équipe) | quelques jours |
| Installation et vérification (Egalyx) | ½ journée |
| Paramétrage de votre organisation et formation | selon le contrat |

Contact : contact@egalyx.com

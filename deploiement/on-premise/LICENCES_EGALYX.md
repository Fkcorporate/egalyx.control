# Licences on-premise — mode d'emploi pour Egalyx (document interne, ne pas remettre au client)

La licence ne concerne **que** les installations chez un client (Docker du kit on-premise, qui pose
`EGALYX_LICENCE_REQUISE=1`). Sur Render, rien ne change : la licence n'y est jamais demandée.

## Une seule fois : créer votre clé Egalyx

Sur **votre** ordinateur, dans le dossier du projet :

```bash
pip install cryptography          # si besoin
python3 outils/licence_egalyx.py initialiser
```

- Votre **clé privée** est créée dans `~/.egalyx_licence/cle_privee.txt` (Windows : `C:\Users\<vous>\.egalyx_licence\`).
  Elle sert à fabriquer les licences. **Ne la mettez jamais dans git, ni sur Render, ni chez un client.**
  Sauvegardez-la (clé USB, coffre de mots de passe) : si vous la perdez, il faudra relancer `initialiser --forcer`
  et redonner une nouvelle clé de licence à tous les clients.
- La **clé publique** est écrite dans `egalyx/licence_cle.py`. Elle sert seulement à vérifier :
  committez-la et poussez (`git add egalyx/licence_cle.py && git commit -m "Clé publique licences" && git push`).

Tant que `initialiser` n'a pas été lancé, `egalyx/licence_cle.py` est vide et la licence n'est pas contrôlée.

## Pour chaque client : émettre une licence

```bash
python3 outils/licence_egalyx.py emettre --client "SODEMI" --fin 2027-12-31 --utilisateurs 25
```

La commande affiche une clé sur une ligne (`EGX1-…`). Transmettez-la au client (ou à l'installateur) :
- soit dans `.env` : `EGALYX_LICENCE=EGX1-…` puis `docker compose up -d` ;
- soit, plus simple, le super administrateur la colle sur la page `https://<adresse>/licence`.

`--utilisateurs` est indicatif : il s'affiche sur la page `/licence` à côté du nombre de comptes actifs, sans bloquer.

Vérifier une clé : `python3 outils/licence_egalyx.py lire EGX1-…`

## Ce que voit le client

| Moment | Effet |
|---|---|
| Plus de 30 jours avant la fin | rien |
| 30 derniers jours | bandeau orange en bas de page, pour les administrateurs |
| 1 à 15 jours après la fin (grâce) | bandeau rouge « l'outil se mettra en pause dans N jours » |
| Plus de 15 jours après la fin | page « Egalyx Control est en pause » ; le super admin peut se connecter et coller une nouvelle clé |

Les données ne sont **jamais** effacées. Renouveler = émettre une nouvelle clé avec une nouvelle date de fin.

## Limite à connaître

Chez le client, le code est sur son serveur : un informaticien déterminé pourrait retirer le contrôle.
La licence évite l'usage « par oubli » au-delà du contrat et rappelle les échéances ; la vraie protection reste
le contrat (durée, droit d'usage, interdiction de modifier ou copier le logiciel).

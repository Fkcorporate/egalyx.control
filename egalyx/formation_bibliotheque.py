"""
egalyx/formation_bibliotheque.py — contenu initial de la bibliothèque Egalyx de formation (e-learning).

Ces modules sont copiés UNE FOIS dans la table formation_bibliotheque au démarrage (par code, s'ils n'y sont pas).
Ensuite, c'est le super admin qui les modifie et les publie depuis « Super admin > Bibliothèque de formation » :
ce fichier n'écrase jamais une modification faite à l'écran.

profil : 'tous', 'uemoa' (Côte d'Ivoire / UEMOA) ou 'france' — sert à proposer en premier la bonne version au client.
Mise en forme du contenu : « ## » intertitre, « - » liste, « 1. » liste numérotée, **gras**.
"""

PARCOURS = {
    'controle_interne': ('Parcours contrôle interne', 'Des bases du contrôle interne aux plans d’action, avec la mise en pratique dans Egalyx'),
    'conformite': ('Parcours conformité', 'Les formations réglementaires et de sensibilisation à suivre par le personnel'),
}


def _q(texte, choix, bonnes, explication=''):
    return {'texte': texte, 'choix': choix, 'bonnes': bonnes, 'explication': explication}


MODULES = [
    # ======================================================================================== parcours contrôle interne
    dict(code='ci_bases', parcours='controle_interne', ordre=1, profil='tous', categorie='controle_interne', duree_minutes=12,
         titre='Les bases du contrôle interne',
         resume='À quoi sert le contrôle interne, comment il s’organise et quel est votre rôle.',
         contenu="""## À quoi sert le contrôle interne ?
Le contrôle interne est l’ensemble des dispositifs qui donnent à la direction une **assurance raisonnable** que l’organisation atteint ses objectifs : des opérations efficaces, une information financière fiable, le respect des lois et la protection du patrimoine.

Il ne s’agit pas d’un service ni d’un contrôle de plus : ce sont les règles, les vérifications et les comportements intégrés au travail de chacun. Une double signature sur un paiement, un rapprochement bancaire mensuel, la séparation entre la personne qui commande et celle qui paie : c’est du contrôle interne.

## Le référentiel COSO
Le référentiel le plus utilisé est le COSO (version 2013). Il décrit cinq composantes qui doivent fonctionner ensemble :
1. **L’environnement de contrôle** : l’éthique, l’exemple donné par la direction, l’organisation des responsabilités.
2. **L’évaluation des risques** : identifier ce qui peut empêcher d’atteindre les objectifs.
3. **Les activités de contrôle** : les vérifications qui réduisent ces risques.
4. **L’information et la communication** : chacun sait ce qu’il doit faire et peut remonter un problème.
5. **Le pilotage** : on vérifie régulièrement que le dispositif fonctionne et on le corrige.

## Les trois lignes de maîtrise
- **Première ligne** : les opérationnels. Ils possèdent les risques de leur activité et réalisent les contrôles du quotidien (contrôles de premier niveau).
- **Deuxième ligne** : le contrôle interne, la gestion des risques, la conformité. Ils définissent la méthode, accompagnent et vérifient (contrôles de deuxième niveau).
- **Troisième ligne** : l’audit interne. Il évalue de façon indépendante si l’ensemble fonctionne.

## Votre rôle
Quelle que soit votre fonction, vous contribuez : en appliquant les procédures, en réalisant les contrôles qui vous sont confiés, en conservant les preuves et en signalant une anomalie ou un risque nouveau.

## Dans Egalyx
- **Contrôle Interne > Cartographie risques** : les risques de l’organisation.
- **Logigrammes** et **Cartographie des processus** : comment l’organisation fonctionne.
- **Campagnes de contrôle** et **Contrôle Interne N2** : les contrôles de premier et de deuxième niveau.
- **Plans d’action** : les corrections décidées.""",
         questions=[
             _q('Le contrôle interne apporte à la direction…', ['Une garantie absolue qu’aucune erreur ne se produira', 'Une assurance raisonnable d’atteindre ses objectifs', 'Un contrôle réalisé une fois par an par un auditeur'], [1],
                'Aucun dispositif ne supprime tout risque : on parle d’assurance raisonnable.'),
             _q('Quelles composantes font partie du COSO ?', ['L’environnement de contrôle', 'L’évaluation des risques', 'Le budget marketing', 'Le pilotage'], [0, 1, 3]),
             _q('Qui réalise les contrôles de premier niveau ?', ['Les opérationnels, dans leur travail quotidien', 'L’audit interne', 'Le commissaire aux comptes'], [0]),
             _q('L’audit interne fait partie de…', ['La première ligne', 'La deuxième ligne', 'La troisième ligne'], [2],
                'L’audit interne apporte une assurance indépendante : c’est la troisième ligne.'),
             _q('Vous constatez qu’une procédure n’est plus adaptée. Que faites-vous ?', ['Je l’ignore et je fais à ma façon', 'Je le signale à mon responsable ou au contrôle interne', 'J’attends le prochain audit'], [1]),
         ]),

    dict(code='ci_cartographie_risques', parcours='controle_interne', ordre=2, profil='tous', categorie='controle_interne', duree_minutes=15,
         titre='La cartographie des risques',
         resume='Identifier un risque, le coter avant et après les contrôles, et décider du traitement.',
         contenu="""## Pourquoi une cartographie des risques ?
La cartographie recense les événements qui pourraient empêcher l’organisation d’atteindre ses objectifs et les classe par importance. Elle sert à décider où placer les contrôles, où envoyer l’audit et quels risques présenter à la direction.

## Bien formuler un risque
Un risque bien écrit permet d’agir. Il précise :
- **la cause** : ce qui peut le provoquer (absence de double validation, personnel non formé…) ;
- **l’événement** : ce qui peut arriver (paiement d’une facture fictive) ;
- **la conséquence** : l’impact (perte financière, sanction, atteinte à l’image).

« Risque de fraude » est trop vague. « Paiement d’une facture fictive faute de vérification du bon de commande, entraînant une perte financière » est exploitable.

## Coter le risque
Chaque risque est évalué selon deux axes : **la probabilité** qu’il survienne et **l’impact** s’il survient. Le score combine les deux (par exemple probabilité × impact) et place le risque dans la matrice.

On cote d’abord le **risque brut**, sans tenir compte des contrôles. On rattache ensuite les contrôles existants et on cote le **risque résiduel** (ou net), c’est-à-dire ce qui reste une fois les contrôles pris en compte. L’écart entre les deux montre l’efficacité du dispositif.

## Décider du traitement
Pour chaque risque résiduel trop élevé, on choisit :
- **réduire** : ajouter ou renforcer un contrôle, avec un plan d’action ;
- **transférer** : assurance, sous-traitance encadrée ;
- **éviter** : arrêter l’activité concernée ;
- **accepter** : décision formelle de la direction, dans la limite de l’appétence au risque.

## Faire vivre la cartographie
Une cartographie se revoit au moins une fois par an, et dès qu’un incident, un nouveau projet ou une nouvelle réglementation le justifie. Un risque coté « faible » mais touché par plusieurs incidents doit être réévalué.

## Dans Egalyx
- **Contrôle Interne > Cartographie risques** : créer la cartographie, ajouter les risques, coter brut et net.
- **Bibliothèque de risques** : partir de risques types par secteur.
- **Importer une cartographie** : reprendre un fichier Excel existant.
- **Comparaison des matrices** : voir l’effet des contrôles entre brut et net.""",
         questions=[
             _q('Quelle formulation de risque est la plus exploitable ?', ['Risque de fraude', 'Paiement d’une facture fictive faute de vérification du bon de commande, entraînant une perte', 'Problème dans les achats'], [1]),
             _q('Le risque brut est évalué…', ['Avant de tenir compte des contrôles', 'Après la prise en compte des contrôles', 'Uniquement par l’audit interne'], [0]),
             _q('Sur quels axes cote-t-on un risque ?', ['La probabilité', 'L’impact', 'Le nombre de personnes dans le service'], [0, 1]),
             _q('Souscrire une assurance contre un risque, c’est…', ['Le réduire', 'Le transférer', 'L’éviter'], [1]),
             _q('Un risque coté faible subit trois incidents en un trimestre. Que faire ?', ['Rien, la cotation est faite pour l’année', 'Le réévaluer', 'Le supprimer de la cartographie'], [1]),
         ]),

    dict(code='ci_processus', parcours='controle_interne', ordre=3, profil='tous', categorie='controle_interne', duree_minutes=12,
         titre='Décrire un processus et placer les contrôles',
         resume='Décrire un processus étape par étape et repérer où placer les points de contrôle.',
         contenu="""## Qu’est-ce qu’un processus ?
Un processus est une suite d’activités qui transforme une demande en résultat : du besoin d’achat au paiement du fournisseur, de la commande client à l’encaissement. Le décrire permet de voir **qui fait quoi, dans quel ordre, avec quels documents**.

## Décrire un processus
1. Fixez le **début** et la **fin** (par exemple : de l’expression du besoin au paiement).
2. Listez les **étapes** dans l’ordre, avec pour chacune l’acteur responsable.
3. Indiquez les **documents** et les **outils** utilisés (bon de commande, logiciel comptable).
4. Repérez les **décisions** (validation, refus) et ce qui se passe dans chaque cas.

Un logigramme (schéma du processus) rend tout cela lisible en un coup d’œil.

## Repérer les étapes à risque
Pour chaque étape, demandez-vous ce qui pourrait mal tourner : une erreur de saisie, une validation contournée, une même personne qui commande et réceptionne, un délai non tenu.

## Placer les points de contrôle
Un bon point de contrôle est placé **au plus près du risque** et laisse une **preuve**. Exemples :
- **séparation des tâches** : celui qui commande ne valide pas le paiement ;
- **validation** selon une délégation de pouvoirs écrite ;
- **rapprochement** : commande, réception et facture doivent concorder ;
- **contrôle automatique** : le logiciel bloque une facture sans commande.

On distingue les contrôles **préventifs** (ils empêchent l’erreur) et **détectifs** (ils la repèrent après coup). Les deux sont utiles.

## Dans Egalyx
- **Contrôle Interne > Logigrammes** : dessiner le processus, ses étapes et ses acteurs.
- Rattachez à chaque étape les **risques** de la cartographie et les **contrôles** qui les couvrent : les étapes sans contrôle apparaissent.""",
         questions=[
             _q('Décrire un processus permet surtout de voir…', ['Qui fait quoi, dans quel ordre, avec quels documents', 'Le chiffre d’affaires du service', 'La liste du personnel'], [0]),
             _q('Lesquels sont de bons points de contrôle ?', ['Séparer la personne qui commande de celle qui paie', 'Rapprocher commande, réception et facture', 'Faire confiance sans vérifier'], [0, 1]),
             _q('Un contrôle qui empêche l’erreur de se produire est…', ['Détectif', 'Préventif', 'Correctif'], [1]),
             _q('Où placer un point de contrôle ?', ['Au plus près du risque, avec une preuve', 'Toujours à la fin du processus', 'Là où il gêne le moins'], [0]),
             _q('Une même personne commande, réceptionne et paie. C’est…', ['Une bonne pratique d’efficacité', 'Un défaut de séparation des tâches', 'Sans importance'], [1]),
         ]),

    dict(code='ci_carto_processus', parcours='controle_interne', ordre=4, profil='tous', categorie='controle_interne', duree_minutes=10,
         titre='La cartographie des processus',
         resume='Avoir une vue d’ensemble de l’organisation : pilotage, réalisation et support.',
         contenu="""## La vue d’ensemble
Avant de décrire chaque processus en détail, il faut une **carte d’ensemble** : quels sont les grands processus de l’organisation et comment s’enchaînent-ils ? Cette carte tient souvent sur une page.

## Trois familles de processus
- **Les processus de pilotage** (ou de management) : ils fixent la direction et contrôlent sa mise en œuvre. Exemples : stratégie, budget, gestion des risques, audit.
- **Les processus de réalisation** (ou opérationnels, ou métier) : ils produisent ce que l’organisation apporte à ses clients. Exemples : vente, production, octroi de crédit, prestation de service.
- **Les processus de support** : ils fournissent les moyens. Exemples : achats, ressources humaines, informatique, comptabilité, trésorerie.

## Les interactions
Un processus en alimente un autre : les achats approvisionnent la production, la paie dépend des ressources humaines, la comptabilité reçoit les factures des achats et des ventes. Représenter ces liens montre les **points de passage** où une erreur se transmet d’un service à l’autre.

## À quoi sert la cartographie des processus ?
- donner une **structure commune** pour ranger les risques, les contrôles et les audits ;
- vérifier qu’**aucun processus important n’est oublié** dans la cartographie des risques ;
- choisir les processus à auditer en priorité ;
- désigner un **propriétaire** pour chaque processus.

## Dans Egalyx
- **Contrôle Interne > Cartographie des processus** : la carte pilotage, réalisation, support et les liens entre processus.
- Les vues « risques » et « audit » montrent, pour chaque processus, ses risques et les audits réalisés.
- Chaque processus s’ouvre sur ses **logigrammes** détaillés.""",
         questions=[
             _q('Les achats, les ressources humaines et l’informatique sont des processus…', ['De pilotage', 'De réalisation', 'De support'], [2]),
             _q('L’octroi de crédit dans une banque est un processus…', ['De réalisation', 'De support', 'De pilotage'], [0]),
             _q('À quoi sert la cartographie des processus ?', ['Vérifier qu’aucun processus important n’est oublié', 'Désigner un propriétaire par processus', 'Remplacer la cartographie des risques'], [0, 1],
                'Elle structure la cartographie des risques, elle ne la remplace pas.'),
             _q('Représenter les liens entre processus permet de…', ['Voir où une erreur passe d’un service à l’autre', 'Réduire le nombre d’employés', 'Supprimer les contrôles'], [0]),
         ]),

    dict(code='ci_campagnes_n1', parcours='controle_interne', ordre=5, profil='tous', categorie='controle_interne', duree_minutes=12,
         titre='Réaliser un contrôle de premier niveau',
         resume='Réaliser les contrôles qui vous sont confiés, conserver la preuve et signaler une anomalie.',
         contenu="""## Le contrôle de premier niveau
Le contrôle de premier niveau est réalisé **par les équipes opérationnelles**, dans leur travail : le comptable qui rapproche le relevé bancaire, l’acheteur qui vérifie les trois devis, le responsable d’agence qui contrôle la caisse en fin de journée.

C’est la base du dispositif : la deuxième ligne et l’audit vérifient ensuite que ces contrôles sont faits et bien faits.

## Bien réaliser un contrôle
1. **Lisez la fiche de contrôle** : objectif, périmètre, fréquence, ce qu’il faut vérifier.
2. **Réalisez le contrôle** sur la période ou l’échantillon demandé.
3. **Conservez la preuve** : document signé, capture d’écran, état de rapprochement, liste des éléments vérifiés. Un contrôle sans preuve est considéré comme non réalisé.
4. **Concluez** : conforme, ou non conforme avec une description précise de l’écart.
5. **Respectez l’échéance** de la campagne.

## Que faire en cas d’anomalie ?
Une anomalie n’est pas une faute de celui qui la trouve : c’est le contrôle qui fonctionne. Décrivez-la de façon factuelle (quoi, combien, quand), corrigez ce qui peut l’être immédiatement et signalez-la à votre responsable. Si elle révèle un risque nouveau ou un incident, déclarez-le.

## Les erreurs à éviter
- cocher « conforme » sans avoir vérifié ;
- oublier de joindre la preuve ;
- corriger une anomalie sans la signaler, ce qui empêche d’en traiter la cause.

## Dans Egalyx
- **Contrôle Interne > Campagnes de contrôle** : les contrôles qui vous sont confiés, avec leur échéance.
- Pour chaque contrôle : saisissez le résultat, joignez la preuve, décrivez l’anomalie éventuelle.
- **Signaler un incident** (menu du haut) si l’anomalie révèle un incident.""",
         questions=[
             _q('Qui réalise les contrôles de premier niveau ?', ['Les équipes opérationnelles', 'L’audit interne', 'Le conseil d’administration'], [0]),
             _q('Un contrôle réalisé sans preuve conservée est considéré comme…', ['Réalisé', 'Non réalisé', 'Facultatif'], [1]),
             _q('Vous trouvez une anomalie. Que faites-vous ?', ['Je la décris de façon factuelle', 'Je la signale à mon responsable', 'Je la corrige discrètement sans rien dire'], [0, 1],
                'Corriger sans signaler empêche d’en traiter la cause.'),
             _q('Trouver une anomalie lors d’un contrôle signifie…', ['Que le contrôle fonctionne', 'Que vous avez mal travaillé', 'Qu’il faut supprimer le contrôle'], [0]),
             _q('Quelle est la première étape d’un contrôle ?', ['Cocher conforme', 'Lire la fiche de contrôle', 'Archiver la campagne'], [1]),
         ]),

    dict(code='ci_controle_n2', parcours='controle_interne', ordre=6, profil='tous', categorie='controle_interne', duree_minutes=15,
         titre='Le contrôle de deuxième niveau',
         resume='Vérifier par échantillon que les contrôles sont faits et efficaces, et conclure.',
         contenu="""## Le rôle du deuxième niveau
Le contrôle de deuxième niveau est réalisé par une fonction **indépendante des opérations** : contrôle interne, contrôle permanent, conformité, gestion des risques. Il vérifie que les contrôles de premier niveau sont réalisés et qu’ils sont efficaces, et que les opérations respectent les règles.

## Préparer le contrôle
- **L’objectif** : que veut-on vérifier ? (par exemple : chaque crédit est approuvé dans la limite de la délégation)
- **La population** : l’ensemble des opérations concernées sur la période (tous les crédits du trimestre).
- **Les critères** : la règle de référence (procédure, délégation de pouvoirs, réglementation).

## Tirer un échantillon
On teste rarement toute la population. L’échantillon doit être :
- **représentatif** : tiré au hasard, ou de façon systématique (un élément sur dix) ;
- **ciblé** si besoin : les montants les plus élevés, les opérations inhabituelles ;
- **documenté** : comment il a été tiré, pour que le contrôle puisse être refait.

Quand les données sont disponibles, l’analyse de données permet de tester 100 % de la population et de cibler l’échantillon sur les exceptions.

## Tester et conclure
Pour chaque élément, comparez à la règle et notez le résultat avec la preuve. Le **taux de conformité** (éléments conformes ÷ éléments testés) donne la conclusion. Chaque anomalie est analysée : erreur isolée ou défaillance du dispositif ? Les défaillances donnent lieu à un **plan d’action**.

## Communiquer
Le résultat est partagé avec le responsable opérationnel : constats, taux, anomalies, actions attendues. Un bon rapport de contrôle est factuel, court et propose des actions mesurables.

## Dans Egalyx
- **Contrôle Interne N2** : programmes de contrôle, missions, échantillons, résultat élément par élément, taux de conformité.
- Les anomalies ouvrent un **plan d’action** avec un responsable et une échéance.
- L’**analyse de données** (si elle est activée) peut alimenter directement le contrôle de deuxième niveau.""",
         questions=[
             _q('Le contrôle de deuxième niveau est réalisé par…', ['Une fonction indépendante des opérations', 'La personne qui a réalisé l’opération', 'Le client'], [0]),
             _q('Un bon échantillon est…', ['Représentatif ou ciblé selon l’objectif', 'Documenté pour pouvoir refaire le contrôle', 'Choisi parmi les dossiers les plus simples'], [0, 1]),
             _q('Sur 40 éléments testés, 36 sont conformes. Le taux de conformité est de…', ['36 %', '90 %', '4 %'], [1]),
             _q('Une anomalie révèle une défaillance du dispositif. Il faut…', ['Ouvrir un plan d’action', 'Retirer l’élément de l’échantillon', 'Attendre le prochain contrôle'], [0]),
             _q('Pourquoi documenter la façon dont l’échantillon a été tiré ?', ['Pour que le contrôle puisse être refait et vérifié', 'Ce n’est pas utile', 'Pour allonger le rapport'], [0]),
         ]),

    dict(code='ci_plans_action', parcours='controle_interne', ordre=7, profil='tous', categorie='controle_interne', duree_minutes=10,
         titre='Les plans d’action',
         resume='Rédiger une action utile, la suivre et prouver qu’elle a été mise en œuvre.',
         contenu="""## Pourquoi les plans d’action comptent
Un contrôle, un audit ou un incident n’a de valeur que si les défaillances constatées sont **corrigées**. Le plan d’action transforme un constat en amélioration réelle.

## Rédiger une bonne action
Une bonne action est :
- **précise et mesurable** : « mettre en place une double validation des changements de RIB fournisseurs » plutôt que « renforcer les contrôles » ;
- **confiée à une personne nommée**, pas à un service ;
- **datée** : une échéance réaliste ;
- **assortie d’une preuve attendue**, définie dès le départ : procédure signée, capture du paramétrage, échantillon testé.

## Suivre l’avancement
Mettez à jour l’avancement régulièrement et ajoutez vos commentaires. Si l’échéance ne peut pas être tenue, demandez un **report justifié** avant qu’elle ne soit dépassée ; un report n’est jamais automatique.

## Clôturer avec la preuve
Une action n’est close que lorsque la preuve est déposée et **vérifiée** par celui qui l’a demandée (contrôle interne, audit). Pour les actions importantes, on vérifie quelques mois plus tard que la correction est **efficace dans la durée**.

## Les erreurs fréquentes
- des actions vagues impossibles à vérifier ;
- un statut « en cours » qui ne bouge pas pendant des mois ;
- une clôture sans preuve.

## Dans Egalyx
- **Plans d’action** : vos actions, leur échéance, leur avancement.
- Déposez la **preuve** sur l’action ; l’émetteur la vérifie et clôt.
- Les relances arrivent automatiquement avant l’échéance et en cas de retard.""",
         questions=[
             _q('Quelle action est la mieux rédigée ?', ['Renforcer les contrôles', 'Mettre en place une double validation des changements de RIB fournisseurs', 'Améliorer la situation'], [1]),
             _q('Une action doit être confiée à…', ['Un service', 'Une personne nommée', 'Personne en particulier'], [1]),
             _q('Quand une action est-elle close ?', ['Quand le responsable dit l’avoir faite', 'Quand la preuve est déposée et vérifiée', 'Quand l’échéance est passée'], [1]),
             _q('Vous ne pourrez pas tenir l’échéance. Que faites-vous ?', ['Je demande un report justifié avant l’échéance', 'J’attends qu’on me relance', 'Je clôture l’action'], [0]),
         ]),

    # ======================================================================================== parcours conformité
    dict(code='lcbft_uemoa', parcours='conformite', ordre=1, profil='uemoa', categorie='lcb_ft', duree_minutes=20,
         titre='Lutte contre le blanchiment et le financement du terrorisme (UEMOA)',
         resume='Reconnaître une opération suspecte, connaître ses obligations et savoir à qui la signaler, dans l’espace UEMOA.',
         contenu="""## De quoi parle-t-on ?
Le **blanchiment de capitaux** consiste à donner une apparence légale à de l’argent issu d’une activité criminelle (corruption, trafic, fraude, détournement). Le **financement du terrorisme** consiste à fournir des fonds, même d’origine légale, à des personnes ou groupes terroristes. Le financement de la prolifération des armes de destruction massive est également visé.

## Le cadre dans l’UEMOA
Dans les huit pays de l’UEMOA, la lutte repose sur une **loi uniforme** relative à la lutte contre le blanchiment de capitaux, le financement du terrorisme et de la prolifération, transposée dans chaque État. Les établissements de crédit, les systèmes financiers décentralisés, les assurances, mais aussi d’autres professions (notaires, agents immobiliers, commerçants de biens de valeur…) sont assujettis.

Chaque pays dispose d’une **CENTIF** (Cellule nationale de traitement des informations financières), qui reçoit les déclarations de soupçon.

## Vos obligations
- **Connaître le client** : vérifier son identité, celle du bénéficiaire effectif, l’objet de la relation et l’origine des fonds ; mettre à jour le dossier.
- **Vigilance renforcée** pour les situations à risque : personnes politiquement exposées, pays à haut risque, opérations complexes ou inhabituelles.
- **Surveiller les opérations** et repérer celles qui n’ont pas de logique économique.
- **Déclarer** : tout soupçon est transmis au responsable conformité, qui décide de la déclaration à la CENTIF.
- **Conserver** les documents pendant la durée fixée par la réglementation.

## Les signaux d’alerte
- dépôts en espèces fractionnés pour rester sous un seuil de déclaration ;
- client qui refuse ou évite de justifier l’origine des fonds ;
- opérations sans rapport avec l’activité connue du client ;
- transferts répétés vers ou depuis des pays à haut risque ;
- recours inhabituel à des intermédiaires ou à des comptes de tiers.

## Ne jamais avertir le client
Il est interdit d’informer le client, ou un tiers, qu’une déclaration de soupçon a été faite ou envisagée. Restez professionnel et transmettez l’information en interne.

## Dans Egalyx
- **Conformité > Tiers et LCB-FT** : fiches clients et fournisseurs, vigilance, criblage des listes de sanctions.
- Remontez tout soupçon à votre responsable conformité selon la procédure interne.""",
         questions=[
             _q('À qui une déclaration de soupçon est-elle transmise dans un pays de l’UEMOA ?', ['À la CENTIF', 'Au client', 'À la presse'], [0],
                'La CENTIF est la cellule de renseignement financier de chaque pays de l’UEMOA.'),
             _q('Un client dépose des espèces trois jours de suite, chaque fois juste sous le seuil de déclaration. C’est…', ['Normal', 'Un signal d’alerte de fractionnement', 'Une bonne gestion de trésorerie'], [1]),
             _q('Que comprend la connaissance du client ?', ['Son identité', 'Le bénéficiaire effectif', 'L’origine des fonds', 'Son équipe de football préférée'], [0, 1, 2]),
             _q('Pouvez-vous dire au client qu’un signalement a été fait le concernant ?', ['Oui, par transparence', 'Non, c’est interdit'], [1]),
             _q('Le financement du terrorisme peut-il porter sur des fonds d’origine légale ?', ['Oui', 'Non'], [0]),
             _q('Vous avez un doute sur une opération. Que faites-vous ?', ['Je transmets l’information au responsable conformité', 'Je refuse l’opération et j’explique pourquoi au client', 'Je ne fais rien sans certitude'], [0]),
         ]),

    dict(code='lcbft_france', parcours='conformite', ordre=1, profil='france', categorie='lcb_ft', duree_minutes=20,
         titre='Lutte contre le blanchiment et le financement du terrorisme (France)',
         resume='Reconnaître une opération suspecte, connaître ses obligations et savoir à qui la signaler, en France.',
         contenu="""## De quoi parle-t-on ?
Le **blanchiment de capitaux** consiste à donner une apparence légale à de l’argent issu d’un crime ou d’un délit (fraude fiscale, corruption, trafic, escroquerie). Le **financement du terrorisme** consiste à fournir des fonds, même d’origine légale, à des personnes ou groupes terroristes.

## Le cadre en France
Les obligations figurent principalement dans le **Code monétaire et financier**, qui transpose les directives européennes. Elles s’appliquent aux banques, assurances, établissements de paiement, mais aussi à d’autres professions : experts-comptables, commissaires aux comptes, notaires, agents immobiliers, marchands de biens de valeur…

Les déclarations de soupçon sont adressées à **Tracfin**, le service de renseignement financier rattaché aux ministères économiques et financiers.

## Vos obligations
- **Identifier et vérifier** le client et le bénéficiaire effectif, comprendre l’objet de la relation d’affaires.
- **Évaluer le risque** et adapter la vigilance : vigilance renforcée pour les personnes politiquement exposées, les pays à haut risque, les opérations complexes ou inhabituelles.
- **Surveiller** les opérations tout au long de la relation.
- **Déclarer** : tout soupçon est transmis au responsable LCB-FT, qui décide de la déclaration à Tracfin.
- **Geler** les avoirs des personnes visées par les mesures de gel nationales et européennes.
- **Conserver** les documents pendant cinq ans.

## Les signaux d’alerte
- opérations fractionnées pour rester sous un seuil ;
- client qui refuse de justifier l’origine des fonds ;
- montages complexes sans justification économique ;
- flux avec des pays à haut risque ou des centres offshore ;
- changement brutal du fonctionnement d’un compte.

## Ne jamais avertir le client
La loi interdit de porter à la connaissance du client, ou d’un tiers, l’existence d’une déclaration de soupçon. Restez professionnel et transmettez l’information en interne.

## Dans Egalyx
- **Conformité > Tiers et LCB-FT** : fiches clients et fournisseurs, vigilance, criblage des listes de sanctions.
- Remontez tout soupçon à votre responsable LCB-FT selon la procédure interne.""",
         questions=[
             _q('En France, à qui la déclaration de soupçon est-elle adressée ?', ['À Tracfin', 'Au client', 'À la police municipale'], [0]),
             _q('Quels clients appellent une vigilance renforcée ?', ['Les personnes politiquement exposées', 'Les clients liés à des pays à haut risque', 'Tous les clients qui paient par carte'], [0, 1]),
             _q('Pendant combien de temps conserver les documents ?', ['Six mois', 'Cinq ans', 'Inutile de les conserver'], [1]),
             _q('Pouvez-vous informer le client qu’une déclaration le concerne ?', ['Oui', 'Non, c’est interdit'], [1]),
             _q('Un client fractionne ses versements pour rester sous un seuil. C’est…', ['Un signal d’alerte', 'Sans importance'], [0]),
             _q('Vous avez un doute sur une opération. Que faites-vous ?', ['Je transmets l’information au responsable LCB-FT', 'Je déclare moi-même directement sur internet sans en parler', 'Je ne fais rien'], [0]),
         ]),

    dict(code='anticorruption', parcours='conformite', ordre=2, profil='tous', categorie='anticorruption', duree_minutes=15,
         titre='Prévenir la corruption et le trafic d’influence',
         resume='Reconnaître une situation à risque (cadeaux, paiements de facilitation, conflits d’intérêts) et savoir réagir.',
         contenu="""## Qu’est-ce que la corruption ?
La corruption consiste à **offrir, promettre, solliciter ou accepter** un avantage indu (argent, cadeau, invitation, emploi, faveur) pour qu’une personne agisse ou s’abstienne d’agir dans le cadre de ses fonctions. Elle est punie que l’avantage soit donné ou reçu, directement ou par un intermédiaire, et qu’il concerne un agent public ou une personne du secteur privé.

Le **trafic d’influence** consiste à monnayer une influence, réelle ou supposée, pour obtenir une décision favorable.

## Le cadre
- **En France**, la loi Sapin II impose aux grandes entreprises un dispositif anticorruption : code de conduite, cartographie des risques de corruption, évaluation des tiers, contrôles comptables, **formation des personnels les plus exposés**, dispositif d’alerte et régime disciplinaire. L’Agence française anticorruption (AFA) contrôle ces dispositifs.
- **Dans l’espace UEMOA**, les États ont adopté des lois de lutte contre la corruption et créé des autorités dédiées (en Côte d’Ivoire, la Haute Autorité pour la Bonne Gouvernance). La corruption d’agents publics, nationaux ou étrangers, est pénalement sanctionnée.

## Les situations à risque
- **Cadeaux et invitations** : acceptables s’ils sont modestes, occasionnels, transparents et sans lien avec une décision en cours ; à déclarer selon la politique interne.
- **Paiements de facilitation** : petites sommes versées pour accélérer une formalité. Ils sont interdits.
- **Intermédiaires** : un agent ou consultant rémunéré sans prestation réelle peut servir à verser un pot-de-vin.
- **Conflits d’intérêts** : un lien personnel avec un fournisseur, un client ou un candidat doit être déclaré.
- **Dons, mécénat, sponsoring** : ils ne doivent jamais servir de contrepartie.

## Comment réagir ?
1. Refusez tout avantage indu, poliment et clairement.
2. En cas de doute, demandez avant d’accepter : à votre responsable ou au référent conformité.
3. Déclarez les cadeaux et conflits d’intérêts selon la procédure.
4. Si vous êtes témoin d’un fait, utilisez le dispositif d’alerte : vous êtes protégé.

## Dans Egalyx
- **Conformité > Tiers et LCB-FT** : l’évaluation des fournisseurs et intermédiaires.
- **Signalements** : le dispositif d’alerte, y compris par le lien public.""",
         questions=[
             _q('Un fournisseur vous offre un week-end tous frais payés pendant un appel d’offres. Vous…', ['Acceptez, c’est un geste commercial', 'Refusez et le signalez selon la procédure', 'Acceptez sans le dire'], [1]),
             _q('Les paiements de facilitation (petites sommes pour accélérer une formalité) sont…', ['Autorisés s’ils sont faibles', 'Interdits'], [1]),
             _q('Quelles situations sont à risque ?', ['Un intermédiaire payé sans prestation réelle', 'Un lien familial non déclaré avec un fournisseur', 'Un stylo publicitaire offert à un salon'], [0, 1],
                'Un objet publicitaire de faible valeur, offert sans contrepartie, n’est généralement pas problématique.'),
             _q('La corruption est punie…', ['Seulement si elle concerne un agent public', 'Que l’avantage soit donné ou reçu, dans le public comme dans le privé'], [1]),
             _q('Vous êtes témoin d’un fait de corruption. Que faites-vous ?', ['J’utilise le dispositif d’alerte', 'Je garde le silence', 'J’en parle sur les réseaux sociaux'], [0]),
         ]),

    dict(code='donnees_personnelles', parcours='conformite', ordre=3, profil='tous', categorie='donnees', duree_minutes=15,
         titre='Protéger les données personnelles',
         resume='Les bons réflexes pour collecter, utiliser, partager et conserver des données personnelles.',
         contenu="""## Qu’est-ce qu’une donnée personnelle ?
Toute information qui permet d’identifier une personne, directement ou indirectement : nom, numéro de téléphone, adresse électronique, numéro de compte, photo, adresse IP, matricule… Certaines données sont **sensibles** (santé, opinions, origine, données biométriques) et demandent une protection renforcée.

## Le cadre
- **Dans l’Union européenne**, le RGPD s’applique depuis le 25 mai 2018 ; en France, la **CNIL** en contrôle le respect. Les sanctions peuvent atteindre 20 millions d’euros ou 4 % du chiffre d’affaires mondial.
- **En Côte d’Ivoire**, la loi n° 2013-450 du 19 juin 2013 encadre la protection des données personnelles ; l’**ARTCI** en est l’autorité de contrôle.

## Les principes à respecter
- **Finalité** : on ne collecte des données que pour un objectif précis et légitime.
- **Minimisation** : seulement les données nécessaires.
- **Exactitude** : des données à jour.
- **Durée limitée** : on ne garde pas les données plus longtemps que nécessaire.
- **Sécurité et confidentialité** : seules les personnes habilitées y accèdent.
- **Droits des personnes** : accès, rectification, effacement, opposition… Toute demande est transmise sans délai au délégué à la protection des données ou au référent.

## Les bons réflexes au quotidien
- ne pas envoyer de fichiers de clients ou de salariés vers une messagerie personnelle ;
- vérifier le destinataire avant d’envoyer un courriel contenant des données ;
- ne pas laisser de documents sur l’imprimante ou sur le bureau ;
- verrouiller sa session en quittant son poste ;
- utiliser les outils et espaces de stockage fournis par l’organisation.

## En cas de fuite de données
Une perte de clé USB, un courriel envoyé au mauvais destinataire ou un piratage est une **violation de données**. Signalez-la **immédiatement** : dans l’Union européenne, l’autorité doit être notifiée dans les 72 heures lorsque la violation présente un risque pour les personnes.

## Dans Egalyx
- **Signaler un incident** (menu du haut) : pour déclarer immédiatement une fuite ou une perte de données.""",
         questions=[
             _q('Lesquelles sont des données personnelles ?', ['Un numéro de téléphone', 'Une adresse électronique nominative', 'Le chiffre d’affaires de l’entreprise'], [0, 1]),
             _q('Le principe de minimisation signifie…', ['Collecter seulement les données nécessaires', 'Réduire la taille des fichiers', 'Effacer toutes les données chaque mois'], [0]),
             _q('Vous envoyez par erreur un fichier de clients à un mauvais destinataire. Vous…', ['Le signalez immédiatement', 'Attendez de voir si quelqu’un se plaint', 'Supprimez le courriel envoyé et n’en parlez pas'], [0]),
             _q('Dans l’Union européenne, en combien de temps l’autorité doit-elle être notifiée d’une violation à risque ?', ['72 heures', '30 jours', '1 an'], [0]),
             _q('En Côte d’Ivoire, quelle autorité contrôle la protection des données personnelles ?', ['L’ARTCI', 'La CNIL', 'La BCEAO'], [0]),
         ]),

    dict(code='cybersecurite', parcours='conformite', ordre=4, profil='tous', categorie='cyber', duree_minutes=12,
         titre='Cybersécurité : repérer l’hameçonnage et protéger ses accès',
         resume='Reconnaître un message piégé, protéger ses mots de passe et réagir vite en cas de doute.',
         contenu="""## La menace la plus courante : l’hameçonnage
L’hameçonnage (phishing) est un message frauduleux (courriel, SMS, appel, message sur une messagerie) qui se fait passer pour une source de confiance afin de vous faire **cliquer sur un lien, ouvrir une pièce jointe, donner vos identifiants ou faire un virement**.

## Les signaux d’alerte
- un ton **urgent** ou menaçant : « votre compte sera bloqué dans 24 heures » ;
- une adresse d’expéditeur qui ressemble, sans être identique, à une adresse connue ;
- une demande inhabituelle : changer un RIB, payer une facture urgente, acheter des cartes cadeaux ;
- un lien dont l’adresse réelle (visible en survolant) ne correspond pas au site attendu ;
- une pièce jointe inattendue, surtout une archive ou un document qui demande d’activer des macros.

## La fraude au président et au changement de RIB
Un fraudeur se fait passer pour un dirigeant ou un fournisseur et demande un virement urgent et confidentiel, ou annonce un nouveau RIB. **Vérifiez toujours par un autre canal**, avec un numéro de téléphone que vous connaissez déjà, jamais celui indiqué dans le message.

## Protéger ses accès
- un mot de passe **long et unique** pour chaque service (une phrase de passe est plus facile à retenir) ;
- la **double authentification** activée partout où c’est possible ;
- ne jamais communiquer son mot de passe, même au service informatique ;
- verrouiller sa session en quittant son poste ;
- installer les mises à jour proposées.

## Réagir vite
Vous avez cliqué ou donné un mot de passe ? Ce n’est pas grave si vous réagissez **immédiatement** : prévenez le service informatique et changez votre mot de passe. Le temps perdu par peur d’être blâmé profite à l’attaquant.

## Dans Egalyx
- Activez la **double authentification** dans votre profil.
- **Signaler un incident** (menu du haut) pour déclarer un message suspect ou un clic malheureux.""",
         questions=[
             _q('Lesquels sont des signaux d’hameçonnage ?', ['Un ton urgent et menaçant', 'Une adresse d’expéditeur légèrement différente', 'Un courriel d’un collègue sur un projet en cours, sans demande inhabituelle'], [0, 1]),
             _q('Un fournisseur annonce par courriel un nouveau RIB. Vous…', ['Mettez à jour le RIB immédiatement', 'Vérifiez par téléphone avec un numéro déjà connu', 'Répondez au courriel pour confirmer'], [1]),
             _q('Le service informatique vous demande votre mot de passe par courriel. Vous…', ['Le donnez', 'Ne le donnez jamais et signalez le message'], [1]),
             _q('Vous avez cliqué sur un lien suspect. Que faites-vous ?', ['Je préviens immédiatement le service informatique', 'J’attends de voir', 'J’éteins mon ordinateur et n’en parle à personne'], [0]),
             _q('Qu’est-ce qui renforce le plus la protection d’un compte ?', ['La double authentification', 'Un mot de passe court et facile', 'Le même mot de passe partout'], [0]),
         ]),

    dict(code='ethique_alerte', parcours='conformite', ordre=5, profil='tous', categorie='ethique', duree_minutes=10,
         titre='Éthique et dispositif d’alerte',
         resume='Les comportements attendus et comment signaler un manquement en toute sécurité.',
         contenu="""## Pourquoi un code de conduite ?
Le code de conduite (ou charte éthique) décrit les comportements attendus de chacun : honnêteté, respect des personnes, loyauté envers l’organisation, respect des lois. Il aide à décider dans les situations délicates, quand la procédure ne dit pas tout.

## Quelques questions pour décider
Face à une situation inhabituelle, posez-vous ces questions :
- Est-ce légal et conforme aux règles internes ?
- Serais-je à l’aise si cette décision était connue de mes collègues, de ma famille ou publiée dans la presse ?
- Est-ce que j’agis dans l’intérêt de l’organisation, ou dans mon intérêt personnel ?

Si la réponse vous met mal à l’aise, demandez conseil avant d’agir.

## Le dispositif d’alerte
Le dispositif d’alerte permet de signaler un manquement grave : fraude, corruption, harcèlement, discrimination, atteinte à la sécurité ou à l’environnement, violation de la loi.
- Le signalement peut être fait par le canal interne prévu, et selon les cas de façon **confidentielle**.
- L’identité de la personne qui signale et les faits sont **protégés** ; seules les personnes chargées du traitement y ont accès.
- **Aucune sanction ni représaille** ne peut viser une personne qui signale de bonne foi.
- En France, la loi encadre la protection des lanceurs d’alerte, avec des délais pour accuser réception et informer de la suite donnée.

## Bien signaler
Décrivez des **faits précis** (quoi, quand, où, qui), joignez les éléments dont vous disposez et évitez les jugements. Un signalement de bonne foi qui se révèle infondé n’expose à aucune sanction ; un signalement fait de mauvaise foi, si.

## Dans Egalyx
- **Signalements** : déposer un signalement et suivre sa prise en charge ; un **lien public** permet aussi de signaler sans compte, si votre organisation l’a ouvert.""",
         questions=[
             _q('Qu’est-ce qui peut être signalé par le dispositif d’alerte ?', ['Une fraude', 'Un harcèlement', 'Une violation de la loi', 'Un désaccord sur la couleur des bureaux'], [0, 1, 2]),
             _q('Une personne qui signale de bonne foi peut-elle être sanctionnée ?', ['Oui', 'Non'], [1]),
             _q('Un bon signalement contient…', ['Des faits précis et datés', 'Des rumeurs', 'Des jugements sur les personnes'], [0]),
             _q('Une situation vous met mal à l’aise et la procédure ne dit rien. Que faites-vous ?', ['Je demande conseil avant d’agir', 'J’agis comme bon me semble', 'Je laisse faire'], [0]),
         ]),
]

CODES = {m['code'] for m in MODULES}
assert len(CODES) == len(MODULES)
for _m in MODULES:
    assert _m['parcours'] in PARCOURS and _m['profil'] in ('tous', 'uemoa', 'france'), _m['code']
    for _x in _m['questions']:
        assert _x['bonnes'] and all(0 <= b < len(_x['choix']) for b in _x['bonnes']), (_m['code'], _x['texte'])

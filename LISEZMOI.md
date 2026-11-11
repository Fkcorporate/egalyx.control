# Egalyx Control — v5

## Nouveautés v5 (aucune nouvelle table, aucune nouvelle dépendance)
| Fonction | Où | Pour qui |
|---|---|---|
| **Organisation de démonstration** « Sahel Finance » (fictive, complète, 6 mois d'historique) | Administration > Démonstration, ou `flask creer-demo` | Super admin |
| **Rapport au comité d'audit** en un clic : synthèse rédigée, décisions attendues, matrice, évolution 12 mois, appétence, plans en retard, audits, conformité — impression / PDF | Menu Contrôle interne, et bouton sur le tableau de bord stratégique | Tous |
| **Bibliothèque de 84 risques types** (8 secteurs : transverse, banque, microfinance, assurance CIMA, mines et énergie, télécoms, secteur public, industrie) avec causes, conséquences et référentiels BCEAO / COBAC / CIMA / OHADA | Contrôle interne > Bibliothèque de risques | Tous |
| **Recherche globale** : risques, audits, plans, incidents, tiers, processus, KRI, cartographies | Ctrl+K (⌘K sur Mac) ou « Rechercher » dans le menu | Tous |
| **Ma semaine** : actions, recommandations, évaluations, mesures de KRI, revues de tiers, alertes — par urgence | En tête du menu | Tous |
| **Mise en route** : 10 étapes qui se cochent seules (organisation, équipe, 2FA, cartographie, risques, évaluation, appétence, processus, tiers, audit) | En tête du menu | Admin client |
| **Liens automatiques entre modules** | Notifications | Admins et responsables concernés |
| **Relances par e-mail** | Automatique ; `flask envoyer-relances` pour un envoi immédiat | Utilisateurs concernés et référents |

Détail des liens automatiques :
- Un incident grave rattaché à un risque déclenche une notification « réévaluer le risque ».
- Une mesure de KRI au-delà du seuil d'alerte déclenche une notification.

Détail des relances par e-mail :
- Chaque lundi, un récapitulatif « Ma semaine » est envoyé à chaque utilisateur qui a des retards.
- Chaque jour, un rappel est envoyé aux référents dont les accusés de réception d'alerte arrivent à échéance.
- Les relances exigent que le SMTP soit configuré. Pour les couper : `EGALYX_RELANCES_AUTO=0`.

Démonstration : notez les mots de passe affichés à la création, ils ne sont plus visibles ensuite. Désactivez l'organisation de démonstration après usage (Gestion Clients).

## Cloisonnement et droits d'écriture (toutes les routes)
L'analyse des modules Processus/logigrammes, Campagnes et Audit a révélé **69 routes** où un utilisateur d'une organisation pouvait lire ou modifier les données d'une autre en changeant un numéro dans l'adresse. Exemples :
- ajouter une constatation à l'audit d'un autre client ;
- supprimer l'étape d'un autre processus ;
- exporter le rapport d'audit d'un autre client (la vérification se limitait au rôle « admin », de n'importe quel client).

**Correction structurelle (`egalyx/cloisonnement.py`)** : avant chaque requête, chaque identifiant présent dans l'adresse est relié à l'objet que la route va charger. La correspondance a été extraite automatiquement du code de 781 routes. Si l'objet appartient à une autre organisation, la réponse est « introuvable » (404). L'organisation d'un objet sans `client_id` est retrouvée par son parent : constatation → audit, étape → processus, etc.

**Droits d'écriture** : 232 routes qui modifient des données ne vérifiaient aucune permission. Désormais, pour modifier des données d'un module, il faut l'une des permissions de ce module, **ou** être en charge de l'élément visé :
- responsable, créateur ou évaluateur désigné ;
- membre de l'équipe de l'audit concerné ;
- référent de l'évaluation du risque concerné.

Les opérateurs gardent leurs propres permissions. La lecture n'est pas changée.

Chaque refus est inscrit dans le journal de l'application. Coupure d'urgence : `EGALYX_CLOISONNEMENT=0` ou `EGALYX_DROITS_ECRITURE=0`. **Testez vos parcours habituels** (auditeur, audité, responsable d'action, évaluateur de risque) : si un refus vous paraît injustifié, le journal indique la route et le module.

Un **module désactivé** pour un client est maintenant bloqué aussi par son adresse, pas seulement masqué dans le menu.

Autres corrections :
- Export HTML et JSON d'un logigramme : ces exports ne fonctionnaient jamais (modèles inexistants, opérateur `@` collé à un `return`). Ils étaient en plus accessibles sans connexion. Ils sont réécrits sur les vrais modèles.
- `/audit/ajouter` : sans connexion, cette adresse créait un audit fictif « REF001 » rattaché à aucune organisation. Elle renvoie maintenant vers la vraie création.
- Clôturer ou changer une campagne d'évaluation : ces actions se déclenchaient par un simple lien, donc depuis n'importe quelle page piégée. Elles exigent maintenant un jeton de sécurité.

## Intelligence artificielle : un seul interrupteur
**Où :** Super admin > **Intelligence artificielle**. Vous pouvez aussi forcer la coupure avec la variable `EGALYX_IA=0`.

**Quand l'IA est utilisable :** il faut à la fois que la plateforme l'active, que le module « Analyse IA » soit coché pour le client (page Modules), et que l'utilisateur ait la permission « Utiliser l'analyse IA ». Avant, **aucune** des 52 adresses IA ne vérifiait cette permission.

**Quand une condition manque :**
- les 46 pages et fonctions IA dédiées sont bloquées ;
- les analyses automatiques (création et résolution d'incident, synchronisation de la veille, assistant) ne sont plus appelées, et l'action continue sans IA ;
- les boutons IA disparaissent des pages ; l'assistant reste, mais répond sans IA (centre d'aide + données), voir plus bas.

**Réglage immédiat :** il est enregistré dans `instance/egalyx_reglages.json` et s'applique tout de suite, sans redémarrage.

**Analyse IA Ultra de la cartographie :**
- elle respecte maintenant la permission IA ;
- le « % de risques évalués » compte les risques et non les évaluations : il dépassait 100 % dès la 2e campagne ;
- un message clair s'affiche si le service `services/analyse_hybride.py` est absent.

**Évaluation triphasée** (et écran d'évaluation de l'opérateur) : les couleurs de la maîtrise étaient inversées (« Insuffisant » en vert). Elles vont maintenant du rouge (1 Insuffisant) au vert (5 Excellent), y compris dans les listes de choix des phases de validation et de confirmation.

## PCA, qualité, gestion des clients, historique des recommandations (v6.4)

**Mise à jour** : sauvegarder la base (`flask sauvegarder`), remplacer les fichiers livrés, redémarrer. Les nouvelles
colonnes du PCA et de la qualité et la table `activations_pca` sont ajoutées automatiquement au démarrage
(`flask mettre-a-jour-base --simulation` pour voir avant).

**PCA** (`egalyx/pca.py`, pages `/pca` et `/pca-suivi`)
- Droits identiques partout : voir = « Voir », « Tester » ou « Gérer les PCA » ; exercices et résultats = « Tester » ou
  « Gérer » ; plans, actions, documents, liens = « Gérer les PCA ». Le responsable d'une action peut la mettre à jour.
  Avant : la plupart des pages demandaient « Gérer les audits », le tableau de bord et le stress test étaient ouverts à
  tous, et la personne nommée valideur pouvait modifier tout le plan.
- Circuit : en rédaction → en relecture (soumis) → validé par le valideur désigné (sans valideur : un gestionnaire des
  PCA). « Validé » ne se choisit plus dans le formulaire ; modifier un plan validé le repasse en rédaction ; à la
  validation : version +0.1 et fin de validité à un an si vide. `EGALYX_PCA_DOUBLE_REGARD=1` : on ne valide pas ce qu'on
  a soumis.
- Exercices : résultat saisi (réalisé / reporté / annulé, durée réelle de reprise comparée au RTO, note, points forts,
  axes d'amélioration) ; dates du dernier et du prochain test mises à jour ; un axe peut devenir une action.
- RTO / RPO convertis en heures (« 4 h », « 2 jours », « 30 min »). Activations réelles du PCA (incident majeur) avec
  durée constatée. Liens vers les risques de la cartographie et les processus métier. Documents joints.
- « Ma semaine » : plan à valider, plan expiré ou bientôt expiré, test en retard, actions confiées.
- La référence saisie est conservée si elle est libre ; sinon numérotation PCA-AAAA-NNN propre à chaque organisation.
- Les analyses d'un plan inexistant répondent « introuvable » au lieu d'une erreur serveur.

**Qualité** (`egalyx/qualite.py`, pages `/qualite` et `/qualite-suivi`)
- Nouvelle permission « Voir la qualité ». Plans, non-conformités, actions, formations, réunions = « Gérer la qualité »
  ou « Gérer les plans qualité » ; audits qualité = « Gérer la qualité » ou « Gérer les audits qualité ». Avant : la
  plupart des pages acceptaient « Gérer les audits » et 12 pages s'ouvraient sans aucun droit qualité.
  Les droits existants sont repris automatiquement au premier démarrage.
- Plan qualité : brouillon → soumis → validé (valideur désigné ou gestionnaire qualité) ; actif seulement une fois
  validé ; modifier un plan validé retire la validation. `EGALYX_QUALITE_DOUBLE_REGARD=1` disponible.
- Non-conformités : clôture seulement après vérification d'efficacité « efficace » (vérificateur tracé) ; « Créer une
  action » la transforme en action d'amélioration suivie.
- Revue de direction tenue : date de dernière revue mise à jour, prochaine calculée selon la périodicité.

**Gestion des clients (super admin)** (`egalyx/gestion_clients.py`)
- Les boutons « Résilier », « Réinitialiser les données », « Exporter les données », « Synchroniser les permissions »
  et « Voir les permissions » de la fiche client appelaient des adresses inexistantes : rien ne se passait.
- **Supprimer définitivement** (liste des clients et fiche client) : aperçu de ce qui sera supprimé, puis le nom du
  client à retaper. Tout ce qui appartient au client est supprimé, y compris les éléments qui en dépendent sans porter
  de client_id ; les liens depuis d'autres données sont vidés. La structure (liens, colonnes obligatoires) est lue dans
  la base elle-même. Une seule transaction : en cas d'erreur, rien n'est supprimé et la cause est affichée. La
  suppression est tracée au journal de la plateforme (SystemLog). Les fichiers déjà déposés sur le disque restent.
- **Réinitialiser les données** : efface risques, audits, contrôles, plans… ; garde le client, ses utilisateurs, son
  organigramme et ses réglages. Même confirmation par le nom.
- **Exporter** : un zip, une table par fichier JSON, sans mots de passe ni secrets 2FA. À faire avant une suppression.
- Un super admin ne peut pas supprimer l'organisation de son propre compte.

**Registre des recommandations** : sur la fiche, le gestionnaire des recommandations (de l'origine concernée) peut
supprimer une ligne d'historique (et sa preuve jointe) ou vider tout l'historique. L'avancement et le statut ne changent
pas ; la suppression reste inscrite au journal d'activité.

## Ce qui n'est pas disponible n'apparaît nulle part · permissions · cartographie (v6.1)
- **Masquage partout** (`egalyx/masquage.py`) : sur chaque page, les liens, boutons, formulaires et lignes cliquables vers un module
  non souscrit, une fonction sans permission (listes, créations) ou l'IA désactivée sont retirés avant l'envoi ; les blocs dont le
  titre désigne un module indisponible (« KRI », « Incidents », « Plans d'action »…) sont masqués. Les liens vers UN élément précis
  confié à la personne restent (la page vérifie les droits). Coupure d'urgence : `EGALYX_MASQUAGE=0`.
  Masquage de l'IA ajouté aussi à l'espace opérateur.
- **Registre des recommandations = module à part** (catalogue des modules, activable par client) avec deux permissions :
  « voir le registre » et « gérer les recommandations ». Les gestionnaires d'audit / du N2 existants les reçoivent une fois
  automatiquement. Clôture : gestionnaire de l'origine (audit, N2) ou « gérer les recommandations ».
- **Page des permissions** générée depuis le catalogue (plus de permission oubliée : voir / réaliser les campagnes, PCA,
  incidents, veille, logigrammes, registre…). Module non souscrit = section grisée, cases non cochables. À l'enregistrement,
  quel que soit l'écran, les permissions d'un module non souscrit sont remises à « non » ; « gérer » entraîne « voir ».
  ⚠ Quand vous activez un module pour un client, ses utilisateurs doivent ensuite recevoir les permissions de ce module.
- **Évaluation des risques en 3 phases** : cadres = fonctionnement d'origine (aucun contrôle ajouté sur les phases 2 et 3).
  Opérateurs = fonctionnement d'origine, avec un réglage facultatif : « Valideur des évaluations des opérateurs ».
  Où le régler : page admin des opérateurs, tableau de bord de l'admin client, menu « Valideur des opérateurs »
  (admin, super admin, ou gestionnaire ayant paramètres / validation / confirmation des risques), et Paramètres > Risques.
  **Un valideur par cartographie** : chaque cartographie peut avoir son valideur (page de la cartographie ou page
  « Valideur des opérateurs ») ; le valideur de l'organisation s'applique aux cartographies qui n'en ont pas.
  Nouvelle colonne cartographie.valideur_operateurs_id (ajoutée automatiquement au démarrage).
  Le valideur peut être un opérateur (il valide depuis l'espace opérationnel, page « Évaluations à valider ») ou un cadre
  (il valide depuis la page d'évaluation). L'opérateur ne fait alors que la pré-évaluation ; le valideur valide ou renvoie
  à revoir (commentaire obligatoire, opérateur prévenu) ; l'administrateur confirme comme avant. Sans valideur : inchangé.
  Ouvrir la page d'évaluation ne crée plus de campagne en douce (invitation à ouvrir une campagne).
- **Corrigé : page KRI bloquée par « Seuils incohérents ».** Le contrôle des seuils s'appliquait à chaque
  enregistrement d'un indicateur (la page KRI enregistre état et tendance) : un seul KRI ancien incohérent bloquait tout.
  Il ne s'applique plus qu'à la création et à la modification des seuils ou du sens. Les KRI incohérents existants
  portent un badge « Seuils à corriger » et une explication sur leur fiche.
- **Corrigé : modules réactivés absents du menu.** Les droits des modules désactivés étaient effacés ; à la
  réactivation, le menu restait vide (KRI, incidents, logigrammes, PCA, campagnes…). Désormais : les droits d'un module
  désactivé sont conservés mais sans effet, et ne peuvent pas être modifiés tant qu'il est désactivé. Quand le super
  admin active des modules, les administrateurs de l'organisation reçoivent leurs droits. Au premier démarrage,
  les administrateurs de chaque organisation reçoivent les droits de tous ses modules actifs.
  « Valideurs des opérateurs » est désormais dans les cartographies (bouton de la liste et page de chaque cartographie),
  plus dans le menu.
- **Corrigé (KRI et autres modules)** : un module activé par le super admin pour un client mais absent de sa formule
  s'affichait dans le menu puis renvoyait « Accès non autorisé au module liste_kri » : la correction automatique des
  permissions (toutes les 5 minutes) ne lisait que la formule et retirait la permission. Toutes les vérifications
  « formule » suivent maintenant la même règle que le menu (choix du super admin, sinon formule). Au premier démarrage,
  les administrateurs touchés retrouvent les permissions des modules actifs.
- **Corrigé** : sur certaines pages (tableau de bord des audits), du code JavaScript s'affichait en bas de page : le
  script de traduction/masquage était inséré dans une chaîne JavaScript au lieu de la fin réelle de la page.
- **Corrigé** : page des permissions entièrement blanche quand un module n'était pas souscrit (le masquage des blocs prenait
  les titres de la grille pour des blocs à cacher) ; masquage désormais exclu des pages d'administration et limité aux vrais
  blocs ; boutons de raccourci de la page des permissions rebranchés sur la nouvelle grille.
- Recette : `recette/masquage_permissions.py` (18) et `recette/cartographie_campagne.py` (14).

## Logigrammes : versions, couloirs, vérification, conversion (v6.0)
`egalyx/logigrammes.py` (bouton « Versions, validation, couloirs » au-dessus de l'éditeur, badges dans la liste).
- **Versions et validation** : brouillon → en validation → validé (vN figée, consultable et imprimable) ; rejet motivé ;
  toute modification repasse en brouillon, la version validée reste en vigueur ; revue annuelle (date = validation + 1 an,
  « confirmer la revue » tracé) ; propriétaire de procédure ; tâches dans « Ma semaine ». Validation par l'auteur possible
  et tracée (`EGALYX_LOGIGRAMME_DOUBLE_REGARD=1` impose un second gestionnaire).
- **Couloirs d'acteurs** : bandes dans l'éditeur et dans les exports ; l'acteur de chaque étape figure dans la version figée.
- **Vérification du dessin** (bouton « Vérifier le dessin ») : erreurs bloquantes (pas de début / fin, étape isolée, décision à une
  sortie) et avertissements (sorties non libellées, inaccessibles, impasses, contrôle non rattaché au référentiel, hors couloir).
- **Conversion** d'un ancien « Processus » (étapes, liens, responsables => couloirs) en logigramme, une seule fois.
- **Corrigé** : « Oui / Non » des sorties de décision perdus au rechargement de l'éditeur ; filtres Jinja `min` / `max`
  redéfinis par app.py qui cassaient « [a, b]|min » (barres d'avancement vides, organigramme, rapport au comité) ;
  organigramme des anciens processus (filtre `truncate`).
- Base : table `versions_logigramme` + colonnes ajoutées automatiquement. Recette : `recette/logigramme_gouvernance.py` (32 vérifications).

## Processus et logigrammes (v5.9)
- **Droits** : les appels de l'éditeur (`/api/logigramme`, `/api/element`, `/api/lien`) n'étaient rattachés à aucun module :
  un simple lecteur pouvait ajouter ou supprimer des éléments. Ils exigent désormais « gérer les logigrammes ».
- **Liens** : un lien pouvait viser un élément inexistant ou un élément d'un AUTRE logigramme ; refusé désormais (et la boucle sur soi-même).
- **Rattachements** : on pouvait rattacher à une étape le risque ou le contrôle d'une autre organisation ; refusé désormais.
- **Nouvelle forme « Décision »** (losange) dans l'éditeur, avec des sorties libellées (Oui / Non…) ; rendue aussi dans les exports.
- Recette : `recette/logigramme.py` (27 vérifications).

## Plans d'action et recommandations : modules et permissions (v5.8)
- **Contrôle interne N2** : 34 pages exigeaient « gérer les audits » au lieu des droits du N2 (un responsable N2 sans droit d'audit
  ne pouvait ni voir les recommandations ni les plans d'action du N2). Désormais : consultation = voir OU gérer le N2 ;
  modifications = gérer le N2. ⚠ Un auditeur qui n'a que « gérer les audits » n'entre plus dans le N2 : donnez-lui les droits N2 si besoin.
- **Registre des recommandations** : chaque origine suit son module (Audit interne, Contrôle interne N2) et ses droits ;
  un gestionnaire N2 ne voit ni ne clôture les recommandations d'audit, et inversement ; module désactivé = recommandations masquées
  partout (registre, « Mes recommandations », « Ma semaine », fiches, preuves). Entrée aussi dans le menu du N2.
- **Audit** : rapport, réponses, temps et indépendance inaccessibles si le module Audit interne n'est pas souscrit.
- Recette : `recette/coherence_modules.py` (20 vérifications).

## Recommandations, KRI et audit (v5.7)
**Registre unique des recommandations** (`egalyx/recommandations.py`, menu Audit interne) : audit interne, contrôle N2 et
recommandations externes (commissaire aux comptes, régulateur, inspection, auditeur externe — nouvelle table).
Indicateurs de comité (taux de mise en œuvre, échues, ancienneté, > 6 mois, par origine). « Mes recommandations »
(aussi dans l'espace opérateur et « Ma semaine ») : avancement commenté, preuve jointe, demande de clôture (preuve exigée),
clôture validée ou refusée (motif) par un gestionnaire qui n'est ni le responsable ni le demandeur. Tout est tracé.

**KRI** (`egalyx/kri_suivi.py`) : « mesure en retard » / « jamais mesuré » selon la fréquence ; seuils incohérents refusés
à l'enregistrement ; historique des seuils (une mesure passée est jugée avec les seuils de son époque) ; mesure critique =>
notification aux gestionnaires des risques, et « risque à réévaluer » au tableau stratégique si le risque est coté Faible/Moyen.
Correction : « Ma semaine » utilisait des fréquences au féminin qui ne correspondaient pas au formulaire.

**Audit** (`egalyx/audit_plus.py`, encadré « Rapport et équipe » sur la fiche d'audit) : rapport provisoire puis définitif ;
réponse de l'audité par constat (position, plan, date d'engagement) ; constats en 5C (critère, conséquence) ; déclarations
d'indépendance obligatoires avant le rapport provisoire ; temps passé par auditeur et activité. Programme d'audit : approbation
depuis « en élaboration » seulement ; l'auteur peut l'approuver lui-même (tracé « auto-approbation » au journal du programme ;
`EGALYX_PROGRAMME_DOUBLE_REGARD=1` impose un second gestionnaire) ; désapprobation motivée et journalisée.
Lien plan d'action ↔ audits désormais enregistré (table `plans_action_audits`).

**Base :** 6 tables créées au démarrage, colonnes ajoutées automatiquement. Recette : `recette/ameliorations.py` (53 vérifications).

## Tableau de bord stratégique : signaux de vigilance (v5.6)
- « KRI en alerte » affiche « Aucun KRI suivi dans ce périmètre » (en orange) au lieu de « 0 » quand aucun indicateur n'est suivi.
- « Incidents » signale « Aucun incident déclaré depuis 12 mois » : zéro incident peut vouloir dire que rien ne remonte.
- Plans d'action sans responsable : badge « Sans responsable » et compteur sur la carte « Plans en retard ».
  Les plans créés automatiquement après une réévaluation reçoivent désormais un responsable (à défaut, le valideur).
- Sous la matrice nette : explication des scores décimaux (net = impact × probabilité réduite selon la maîtrise).
- Recette : `recette/strategique.py` (7 vérifications).

## Tableau de bord : modules du client et permissions (v5.5)
- **Formule d'abonnement prise en compte** : un client sans module dans sa formule ne le voit plus, ni dans le tableau de bord
  ni ailleurs (avant, la formule était ignorée tant que le super admin n'avait pas coché les modules du client à la main).
  Ordre : choix explicite du super admin (page « Modules » du client) > modules de la formule > aucune restriction.
  Retour à l'ancien comportement : `EGALYX_MODULES_PAR_FORMULE=0`.
- **Admin client** : il voyait toutes les cartes, même des modules que son organisation n'a pas ; il ne voit plus que les modules actifs.
- **Permissions de consultation** prises en compte (voir les campagnes, les plans d'action, le contrôle N2, les incidents, les tickets).
- **Nouvelles cartes** : plans d'action (ouverts / en retard), contrôles N2 (à valider), plans de continuité.
- Recette : `recette/tableau_de_bord.py` (11 vérifications), inclus dans `recette/tout_lancer.py`.

## Recette de bout en bout sur une vraie base (v5.4)
L'application complète a été démarrée sur une base SQLite vide, avec deux organisations et un utilisateur par rôle
(super admin, admin client, gestionnaire, validateur, opérateur, lecteur, admin d'une autre organisation).

**Relancer la recette** (depuis la racine du projet, dépendances installées) : `python recette/tout_lancer.py`.
Elle n'utilise jamais votre vraie base ni le fichier `.env` (base de test `recette/recette.db`, 2FA désactivée pour le test seulement).
Elle couvre : le circuit campagne ↔ N2 (22 vérifications), 15 décisions × 6 rôles en forgeant les requêtes,
680 pages × 5 à 6 rôles (erreurs serveur), l'étanchéité entre organisations, et les colonnes « fantômes ».

**Corrigé suite à la recette :**
- anomalies saisies par l'opérateur jamais créées (la liste était comparée à elle-même) → aucune non-conformité à la validation ;
- au démarrage, deux blocs d'import échouaient en entier : les formulaires (un modèle importé par erreur) et les fonctions de `utils.py`
  (6 noms absents) — 45 fonctions étaient remplacées en silence par des versions vides (tendance KRI, synchronisation des matrices…) ;
- opérateurs : le contrôle d'écriture les laissait tout faire (désapprouver/archiver un programme d'audit, accepter/rejeter une
  recommandation N2, terminer un plan d'action) ; désormais seulement par leurs pages ou sur ce dont ils ont la charge ;
- une permission de consultation (« voir les rapports », activée par défaut) suffisait pour écrire : un simple lecteur pouvait supprimer
  une mission d'audit ; il faut désormais une permission de gestion du module ;
- les actions par lien (clôturer/changer une campagne d'évaluation, convertir une mission) contournaient le contrôle d'écriture ;
- validation des risques proposés et des demandes de réévaluation : rôles figés → permission « valider les risques », jamais sa propre proposition ;
- 33 valeurs écrites dans des colonnes inexistantes (dernier score/niveau du risque, tendance KRI, responsable/durée/entrées/sorties
  des sous-étapes, objectifs des programmes de contrôle, date d'escalade d'incident…) → colonnes ajoutées (ajout automatique au démarrage) ;
- pages en erreur : liste des risques vide, création d'utilisateur par l'admin client, usage de l'abonnement sans formule,
  nouvelle campagne d'évaluation, export de matrice, vérification des incohérences, Gantt, chronogramme, préférences de notification,
  sessions utilisateurs, exports veille Excel/PDF, page « organisation introuvable », directions/pôles par pays.

**Reste à traiter :** voir le rapport de recette (page /ci : contenu fictif ; benchmark des dispositifs non implémenté ;
liaison plan d'action ↔ audits non enregistrée ; fichier `requirements.txt` incomplet → `requirements_complet.txt`).

## Campagnes de contrôle ↔ contrôle interne N2 : un seul circuit (v5.3)
`egalyx/circuit_controle.py` porte toutes les règles ; les écrans campagne (opérateur et administration), « À valider » du N2 et les anciennes routes de synchronisation passent tous par lui.

**Problèmes corrigés :**
- aucune page ne permettait de valider ou rejeter une campagne (routes sans bouton) : elles restaient « en attente de validation » ;
- les colonnes de suivi (soumission, validation, rejet, réouverture, historique) n'existaient pas en base : rien n'était enregistré ;
- deux validations indépendantes : la décision prise dans le N2 n'atteignait pas la campagne, et l'inverse contournait les règles du N2 ;
- non-conformités créées dès la soumission (et laissées ouvertes en cas de rejet) ; quatre autres chemins en créaient aussi, à partir de textes libres (doublons) ;
- exécution N2 jamais mise à jour après correction (taux de conformité faux) ; réouvertures non comptées ;
- droits fondés sur « gérer les audits » ; pas d'interdiction de valider sa propre campagne ;
- page de détail d'une campagne sans contrôle d'accès ; tableau de bord opérateur vide quand aucune direction n'était attribuée (alors que la règle est « toutes ») ;
- compteurs de « À valider » du N2 calculés sur tous les clients.

**Règles :** soumission → exécution N2 à jour + planification soumise + validateur notifié ; une seule décision (validateur désigné, à défaut celui de la planification, à défaut les gestionnaires ; jamais l'auteur ni le contrôleur), prise d'un côté ou de l'autre et appliquée aux deux ; non-conformités créées à la validation, une par anomalie retenue ; rejet sans non-conformité ; réouverture après validation réservée aux gestionnaires, 3 au maximum. Droits : « gérer les campagnes » / « gérer le contrôle interne N2 » / administrateur.
**Base :** 12 colonnes ajoutées à `campagnes_controle` (ajout automatique au démarrage ; `python reparer_base.py` pour SQLite).

## Bascule français / anglais (v5.2)
**Avant :** 5 « context processors » et 4 systèmes de traduction concurrents ; une traduction par morceaux qui mélangeait les langues (« Risks critiques ») ; la langue dans l'adresse (`?lang=en`) ; ~60 gabarits sur 400 traduits ; et un ancien script avait remplacé en dur des textes français par de l'anglais dans 158 gabarits (de l'anglais apparaissait en mode français).

**Maintenant (`egalyx/langue.py`) :**
- bouton FRANÇAIS / ENGLISH → `/langue/fr|en` : enregistre la langue (session + cookie 1 an) et revient sur la même page, sans paramètre dans l'adresse ; à défaut, langue de l'organisation (`Client.langue`), sinon français ;
- dictionnaire unique `egalyx/traductions/` : **9 400 textes d'interface** traduits (menus, titres, boutons, colonnes, statuts, messages flash, messages d'erreur, confirmations JavaScript), 500 modèles pour les messages variables (« Campagne "X" archivée avec succès »), et **528 restes d'anglais remis en français** en mode français ;
- toute page HTML est traduite à la sortie, gabarits non modifiés : textes, `placeholder`, `title`, `aria-label`, boutons, `<html lang>` ; jamais de remplacement partiel (un texte inconnu reste tel quel) ; `<script>`, `<textarea>`, `<pre>` et tout élément `translate="no"` sont ignorés ;
- le texte ajouté par JavaScript (tableaux chargés en AJAX, fenêtres, `alert` / `confirm`) est traduit dans le navigateur avec le même dictionnaire (fichier mis en cache) ;
- les réponses JSON `message` / `error` sont traduites ;
- `t()`, `_()` et l'ancien `translation_system.translate` utilisent tous le même moteur.

**Ce qui reste en français en mode anglais :** les données saisies par les utilisateurs, le centre d'aide et les réponses de l'assistant, et les modèles de contrats (générateur de conventions).
**Ajouter / corriger une traduction :** une ligne `texte français<TAB>traduction` dans `egalyx/traductions/fr_en_complements.tsv` (`{}` = partie variable), puis redémarrer.
Mesure sur 237 gabarits rendus en anglais : 25 920 lignes de texte, 35 restes français distincts (textes composés avec des variables).

## Centre d'aide et assistant autonome (v5.1)
**Centre d'aide** — `/aide`, lien « Centre d'aide » dans le menu de gauche et sur la page de connexion :
- 90 fiches en 15 rubriques (premiers pas, compte et 2FA, administration, risques, maîtrise / KRI / incidents, processus / campagnes / C2N, audit, plans d'action, conformité, PCA et qualité, pilotage, IA, abonnement et API, dépannage, super admin) et un glossaire de 28 termes ;
- recherche tolérante aux fautes et aux formulations (« mdp oublié », « la personne ne voit rien », « payer par Orange Money ») ;
- **guide complet imprimable** (`/aide/guide-complet`, Ctrl P → PDF, environ 25 pages) ;
- droits respectés : un visiteur non connecté ne voit que les fiches de connexion, 2FA et alerte ; les fiches super admin ne sont visibles que de lui ; si une personne n'a pas accès à la fonction, la fiche le dit (🔒) et n'affiche pas de bouton vers la page.
- Pour ajouter ou corriger une fiche : `egalyx/aide_contenu.py` (un bloc `A(...)` par fiche). Les tests vérifient les identifiants, les catégories et que chaque lien vise une route existante.

**Assistant** :
- répond désormais aux questions « comment faire », « pourquoi », « je n'arrive pas à… », « je ne vois pas… » avec la fiche du centre d'aide (étapes, conseils, boutons vers les pages) ;
- **toujours disponible, même IA désactivée** (il ne passe plus par l'interrupteur IA ; seule sa partie ChatGPT facultative, `ASSISTANT_IA_EXTERNE=1`, suit l'interrupteur) ;
- s'il n'est pas sûr, il ne devine pas : il propose les fiches proches et un bouton **« Oui, envoyer ma question au support »** qui crée le ticket (avec la question, l'utilisateur et la page) ; on peut aussi écrire « crée un ticket : … » ou « je veux parler à un conseiller » ;
- les questions non comprises restent consultables dans la page existante des questions non comprises : c'est la liste des fiches à ajouter.

## Modules opérationnels (incidents, KRI, PCA, qualité, veille, questionnaires, plans d'action, contrôle de 2e niveau)
- Le cloisonnement et les droits d'écriture ci-dessus s'appliquent aussi à ces modules. Les routes de ces modules qui n'étaient pas reconnues ont été ajoutées.
- **Questionnaires** : les adresses d'envoi de réponses, accessibles sans connexion, acceptaient n'importe quel numéro de questionnaire. On pouvait donc injecter des réponses dans les questionnaires internes de n'importe quel client. Désormais, le questionnaire doit être actif, dans sa période d'ouverture, et public, ou bien l'utilisateur connecté doit appartenir à son organisation (`egalyx/questionnaires_publics.py`).
- **Tickets de support** : la page de confirmation, sans connexion et avec des références séquentielles, affichait l'e-mail et le sujet de n'importe quel ticket. Elle n'est plus visible que par la session qui a créé le ticket, ou par l'organisation concernée. La liste des tickets exige maintenant la permission « tickets » (elle exigeait « gérer les audits »).
- **Veille** : activer ou désactiver une veille et archiver une action se déclenchaient par un simple lien. Ces actions exigent maintenant un jeton de sécurité.

## Modules par client (super admin)
Fiche client > **Modules**, ou l'icône pièce de puzzle dans la liste des clients. Après la création d'un client, l'application ouvre directement cette page.

**Comment s'en servir :**
1. Choisissez un profil : « Cabinet d'audit », « Gestion des risques », « Contrôle interne », « Conformité et LCB-FT » ou « Suite complète ».
2. Ajustez les 19 modules, puis appliquez.

**Comment fonctionnent les accès :** un utilisateur peut utiliser une fonction si le module est activé pour son organisation **et** s'il a la permission correspondante. Un module désactivé disparaît des menus et devient inaccessible pour tous les utilisateurs du client, administrateur compris. Les recherches et les tâches de « Ma semaine » ne le montrent plus non plus. L'effet est immédiat, sans reconnexion.

**Clients existants :** tant que vous n'avez rien choisi pour un client, rien ne change pour lui. La page vous propose un choix de départ tiré de sa formule.

Nouvelle colonne `clients.modules_actifs` : elle est ajoutée par `python3 reparer_base.py` ou automatiquement au démarrage.

## Permissions des nouveaux modules
Les nouveaux modules utilisent le système de permissions existant (`User.has_permission`). Les liens du menu n'apparaissent qu'aux personnes autorisées, et chaque page est aussi protégée côté serveur.

Cinq permissions sont ajoutées. Elles apparaissent dans la section « Conformité et reporting » de la page des permissions d'un utilisateur.

| Permission | Donne accès à | Accordée par défaut à |
|---|---|---|
| `can_view_tiers` | Tiers & LCB-FT en lecture | admin, manager, auditeur, compliance |
| `can_manage_tiers` | création et modification des tiers, criblage, décisions | admin, compliance |
| `can_manage_alertes` | référent du dispositif d'alerte (signalements confidentiels) | admin, compliance — **jamais le super admin** |
| `can_view_rapport_comite` | rapport au comité d'audit | admin |
| `can_sign_documents` | signature interne | admin, manager, auditeur, compliance |

Permissions existantes réutilisées :

| Module | Permission |
|---|---|
| Bibliothèque de risques | `can_manage_risks` |
| Paramètres des risques | `can_manage_settings` |
| Éditeur d'organigramme | `can_manage_logigram` |
| Documentation de l'API | `can_manage_api` |
| Export complet | admin client + `can_export_data` |
| Signature d'un audit | consulter l'audit (`can_manage_audit` ou `can_view_reports`) |
| Signature d'un plan d'action | consulter le plan (`can_manage_action_plans` ou `can_view_action_plans`) |

La recherche globale ne cherche que dans les modules que l'utilisateur a le droit de voir.

**Correction de la page des permissions :** elle affiche maintenant les droits *réels* de l'utilisateur, y compris ceux hérités de son rôle. Avant, tout apparaissait décoché pour un administrateur : enregistrer la page lui retirait silencieusement tous ses droits.

## Module Pôles et filiales : corrections
- Rattacher ou dissocier un pôle d'un pays via l'API exige maintenant la permission `can_manage_departments`. Avant, n'importe quel utilisateur connecté pouvait le faire.
- Les boutons de gestion (créer, modifier, rattacher, supprimer, ajouter une direction ou un service) sont masqués pour qui ne peut que consulter.
- Les noms avec apostrophe (« Pôle d'Abidjan », « Côte d'Ivoire ») ne cassent plus les boutons.
- « Nouveau pôle » depuis un pays présélectionne ce pays.
- Le super admin travaille sur l'organisation qu'il consulte. Avant, les pôles qu'il créait n'étaient rattachés à aucune organisation, et la liste des responsables mélangeait tous les clients.
- La suppression d'un pôle ou d'un pays devient un **archivage**. Elle est refusée s'il reste des cartographies actives rattachées. Avant, la suppression était définitive et risquait de casser l'historique.

---

# v4 : modules ajoutés

## Installation (remplace la v3)
1. Remplacez `app.py`, `models.py` et `cotation.py`, et ajoutez le dossier `egalyx/`.
2. **Fusionnez** le dossier `templates/` avec le vôtre (ne le remplacez pas) : il contient `templates/egalyx/` et les pages modifiées.
3. Aucune nouvelle dépendance Python n'est nécessaire.
4. **Base SQLite existante : lancez d'abord `python3 reparer_base.py`** (ajoute les colonnes 2FA, avec copie de sécurité).
5. Au démarrage, les nouvelles tables et colonnes sont créées automatiquement. Les colonnes manquantes sont seulement ajoutées : rien n'est supprimé.
   - Pour vérifier avant d'appliquer : `flask mettre-a-jour-base --simulation`
   - Pour appliquer : `flask mettre-a-jour-base`
6. Faites une sauvegarde avant la mise à jour : `flask sauvegarder`.

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

La suite compte 65 tests :
- fonctions de calcul ;
- parcours 2FA, alerte et paiement ;
- rendu des gabarits ;
- synthèse du rapport, bibliothèque, démonstration, recherche (v5).

Ces tests utilisent des doubles de SQLAlchemy et de Flask-Login. Un essai sur votre base réelle reste nécessaire, de préférence sur une copie.

"""
egalyx/aide_contenu.py — base de connaissances d'Egalyx Control.

Une seule source pour :
  - le centre d'aide (/aide), consultable, cherchable et imprimable ;
  - l'assistant (chatbot), qui y cherche la réponse avant de proposer un ticket.

Chaque article :
  id        identifiant stable (sert d'adresse : /aide/<id>)
  cat       code de catégorie (voir CATEGORIES)
  titre     question ou tâche telle qu'un utilisateur la formule
  resume    réponse courte en une ou deux phrases
  etapes    étapes numérotées (facultatif)
  notes     points d'attention, astuces, erreurs fréquentes (facultatif)
  mots      mots-clés et synonymes (sans accents, en minuscules), y compris fautes courantes
  liens     [(libellé, endpoint Flask)] — affichés seulement si la page existe et est accessible
  perms     permissions dont l'une suffit pour utiliser la fonction (None = tout le monde)
  pour      'tous' | 'admin' (administrateur de l'organisation) | 'super_admin' | 'public' (sans compte)

Mise en forme autorisée dans les textes : **gras** uniquement.
Pour ajouter un article : copier un bloc A(...) et l'adapter ; les tests vérifient que
les identifiants sont uniques et que chaque catégorie existe.
"""

CATEGORIES = [
    ('demarrer', 'Premiers pas', 'fa-rocket'),
    ('compte', 'Compte, connexion et sécurité', 'fa-user-shield'),
    ('admin', 'Administration de l’organisation', 'fa-users-cog'),
    ('risques', 'Cartographie et évaluation des risques', 'fa-map'),
    ('maitrise', 'Dispositifs de maîtrise, KRI et incidents', 'fa-shield-alt'),
    ('controle', 'Processus, campagnes et contrôle N2', 'fa-clipboard-check'),
    ('audit', 'Audit interne', 'fa-search'),
    ('plans', 'Plans d’action', 'fa-tasks'),
    ('conformite', 'Conformité : veille, tiers LCB-FT, alerte', 'fa-balance-scale'),
    ('continuite', 'Continuité d’activité et qualité', 'fa-life-ring'),
    ('pilotage', 'Pilotage, rapports et exports', 'fa-chart-pie'),
    ('ia', 'Intelligence artificielle', 'fa-robot'),
    ('abonnement', 'Abonnement, paiement et API', 'fa-credit-card'),
    ('depannage', 'Dépannage', 'fa-wrench'),
    ('superadmin', 'Super administrateur', 'fa-crown'),
]


def A(id, cat, titre, resume, etapes=(), notes=(), mots=(), liens=(), perms=None, pour='tous', questions=()):
    return {'id': id, 'cat': cat, 'titre': titre, 'resume': resume, 'etapes': list(etapes),
            'notes': list(notes), 'mots': list(mots), 'liens': list(liens),
            'perms': tuple(perms) if perms else None, 'pour': pour, 'questions': list(questions)}


ARTICLES = [
    # ==================================================================
    # PREMIERS PAS
    # ==================================================================
    A('presentation', 'demarrer', 'Qu’est-ce qu’Egalyx Control ?',
      'Egalyx Control est une plateforme de gouvernance, gestion des risques et conformité (GRC) : '
      'cartographie des risques, dispositifs de maîtrise, KRI, incidents, contrôle interne, audit, '
      'plans d’action, conformité (veille, LCB-FT, alerte), continuité d’activité et pilotage.',
      notes=['Chaque organisation cliente ne voit que ses propres données.',
             'Les modules visibles dépendent de votre abonnement, des modules activés pour votre organisation '
             'et de vos permissions personnelles.'],
      mots=['egalyx', 'presentation', 'outil', 'logiciel', 'plateforme', 'grc', 'sert', 'fonctionnalites', 'modules'],
      liens=[('Tableau de bord', 'dashboard')],
      questions=['a quoi sert egalyx', 'que fait l outil', 'quels sont les modules']),

    A('premiere_connexion', 'demarrer', 'Je me connecte pour la première fois : que faire ?',
      'Connectez-vous avec l’identifiant et le mot de passe reçus, changez votre mot de passe, '
      'puis ouvrez « Ma semaine » pour voir ce qui vous attend.',
      etapes=['Ouvrez la page de connexion et saisissez votre identifiant (ou e-mail) et le mot de passe provisoire.',
              'Si l’application vous le demande, choisissez un nouveau mot de passe (12 caractères minimum).',
              'Si vous êtes administrateur, activez la double authentification (elle est obligatoire pour les administrateurs).',
              'Ouvrez **Ma semaine** dans le menu de gauche : vos tâches, échéances et validations y sont regroupées.',
              'Cliquez sur le bouton rond de l’assistant (en bas à droite) pour poser une question à tout moment.'],
      mots=['premiere', 'premier', 'fois', 'debut', 'commencer', 'debuter', 'demarrer', 'bienvenue', 'prise', 'main', 'debutant'],
      liens=[('Ma semaine', 'ma_semaine.page'), ('Mon profil', 'profil_utilisateur')],
      questions=['par ou commencer', 'je suis nouveau', 'comment debuter']),

    A('mise_en_route', 'demarrer', 'Mettre en route Egalyx pour mon organisation (administrateur)',
      'La page « Mise en route » liste les étapes de paramétrage dans l’ordre et coche celles qui sont faites.',
      etapes=['Menu de gauche → **Mise en route**.',
              'Créez l’organisation : pays, pôles, directions, services.',
              'Ajustez les paramètres de cotation (seuils, appétence) dans **Paramètres → Risques**.',
              'Créez les utilisateurs et attribuez rôles et permissions.',
              'Importez votre cartographie Excel telle quelle (**Importer une cartographie**), ou partez de la **Bibliothèque de risques** de votre secteur (risques et contrôles types).',
              'Ajoutez les dispositifs de maîtrise, puis évaluez les risques.',
              'Créez les KRI et les plans d’action prioritaires.'],
      mots=['mise', 'route', 'parametrage', 'installation', 'configurer', 'initialiser', 'onboarding', 'demarrage', 'lancer'],
      liens=[('Mise en route', 'ma_semaine.demarrage'), ('Importer une cartographie', 'import_carto.page'),
             ('Bibliothèque de risques', 'bibliotheque.page')],
      pour='admin',
      questions=['comment configurer l outil', 'comment parametrer egalyx', 'premiers parametrages']),

    A('navigation', 'demarrer', 'Se repérer dans l’interface',
      'Le menu de gauche regroupe les modules par famille ; la barre du haut donne accès aux notifications, '
      'au thème, au profil et à la déconnexion.',
      etapes=['**Pilotage personnel** : Rechercher (Ctrl K), Ma semaine, Mise en route (administrateurs).',
              '**Contrôle interne** : tableau de bord, bibliothèque, cartographie, KRI, veille, logigrammes, qualité, campagnes, PCA, incidents, tableau de bord stratégique, rapport au comité, contrôle N2, support.',
              '**Audit** : tableau de bord global, programme d’audit, missions, rapports, plans d’action.',
              '**Conformité** : tiers et LCB-FT, dispositif d’alerte.',
              '**Administration** : utilisateurs, organisation, paramètres, intégrations, abonnement.',
              'Le bouton en haut à gauche replie le menu ; sur téléphone, le menu s’ouvre avec l’icône ☰.'],
      notes=['Un module absent du menu n’est pas activé pour vous : voir « Je ne vois pas un module ».'],
      mots=['menu', 'interface', 'navigation', 'naviguer', 'repere', 'trouver', 'barre', 'gauche', 'ou'],
      questions=['ou se trouve le menu', 'comment naviguer']),

    A('ma_semaine', 'demarrer', 'Ma semaine : mes tâches et échéances',
      '« Ma semaine » rassemble ce qui vous concerne : actions en retard, échéances des 7 prochains jours, '
      'validations à faire, mesures de KRI à saisir, incidents à traiter.',
      etapes=['Menu de gauche → **Ma semaine**.',
              'Les éléments sont classés par urgence (en retard, cette semaine, à venir).',
              'Cliquez sur un élément pour ouvrir directement la fiche concernée.'],
      notes=['Vous ne voyez que les éléments des modules auxquels vous avez accès.',
             'Un récapitulatif hebdomadaire peut aussi être envoyé par e-mail si l’envoi d’e-mails est configuré.',
             'Dans l’assistant, demandez « Qu’est-ce qui m’attend ? ».'],
      mots=['semaine', 'taches', 'tache', 'echeance', 'echeances', 'agenda', 'todo', 'retard', 'faire', 'attend'],
      liens=[('Ma semaine', 'ma_semaine.page')],
      questions=['qu est ce que je dois faire', 'mes taches de la semaine']),

    A('recherche', 'demarrer', 'Rechercher n’importe quoi (Ctrl K)',
      'La recherche globale trouve risques, audits, constatations, plans d’action, incidents, KRI, tiers, '
      'veilles… par mot ou par référence.',
      etapes=['Appuyez sur **Ctrl K** (ou Cmd K sur Mac), ou cliquez sur **Rechercher** dans le menu.',
              'Tapez au moins 2 caractères : un mot, un nom, une référence (ex. RSQ-2026-0012).',
              'Naviguez avec les flèches et validez avec Entrée.'],
      notes=['Les résultats respectent vos permissions : vous ne trouvez que ce que vous pouvez ouvrir.'],
      mots=['recherche', 'rechercher', 'chercher', 'trouver', 'ctrl', 'raccourci', 'reference', 'retrouver'],
      questions=['comment retrouver un risque', 'je cherche un dossier']),

    A('assistant', 'demarrer', 'Utiliser l’assistant',
      'L’assistant répond aux questions sur l’outil et sur vos données : « quels plans sont en retard ? », '
      '« comment déclarer un incident ? », « c’est quoi un KRI ? », ou une référence comme RSQ-2026-0012.',
      notes=['Il fonctionne même quand l’intelligence artificielle est désactivée : ses réponses viennent de ce guide et de vos données.',
             'Il ne montre que ce que vos permissions autorisent.',
             'S’il ne sait pas répondre, il vous propose d’envoyer la question aux gestionnaires de votre organisation (réponse dans « Mes signalements »).',
             'Le bouton ↻ en haut de la fenêtre efface la conversation.'],
      mots=['assistant', 'chatbot', 'chat', 'bot', 'robot', 'discuter', 'question'],
      questions=['comment marche l assistant', 'que peux tu faire']),

    A('langue_theme', 'demarrer', 'Changer la langue ou le thème (clair / sombre)',
      'Langue : bouton rond en bas à droite, puis FRANÇAIS ou ENGLISH ; la page se recharge dans la langue choisie, '
      'qui est mémorisée sur ce navigateur. Thème : icône lune / soleil dans la barre du haut.',
      notes=['Toute l\u2019interface passe en anglais : menus, pages, boutons, messages, fenêtres de confirmation. '
             'Les données saisies par votre organisation (intitulés de risques, commentaires…) restent telles qu\u2019elles ont été écrites.',
             'Le centre d\u2019aide et les réponses de l\u2019assistant sont rédigés en français.'],
      mots=['langue', 'anglais', 'english', 'francais', 'traduction', 'theme', 'sombre', 'nuit', 'clair', 'dark', 'couleur'],
      questions=['mettre en anglais', 'mode sombre']),

    A('notifications', 'demarrer', 'Notifications : où les voir et comment elles marchent',
      'La cloche en haut de l’écran affiche vos notifications (incident déclaré, KRI en alerte, validation '
      'demandée, échéance proche…). La page Notifications les liste toutes.',
      notes=['Les incidents graves et les KRI critiques créent automatiquement une notification « urgent ».',
             'Les e-mails ne partent que si votre organisation a configuré l’envoi d’e-mails.'],
      mots=['notification', 'notifications', 'cloche', 'alerte', 'alertes', 'message', 'messages', 'email', 'mail', 'courriel', 'rappel', 'relance'],
      liens=[('Mes notifications', 'notifications.liste_notifications')],
      questions=['je ne recois pas les mails', 'ou voir mes alertes']),

    # ==================================================================
    # COMPTE, CONNEXION, SÉCURITÉ
    # ==================================================================
    A('mot_de_passe_changer', 'compte', 'Changer mon mot de passe',
      'Depuis « Mon profil » (menu en haut à droite).',
      etapes=['Cliquez sur votre nom en haut à droite → **Mon profil**.',
              'Saisissez l’ancien mot de passe puis le nouveau deux fois.',
              'Règles : au moins 12 caractères, une majuscule, une minuscule, un chiffre et un caractère spécial, sans espace.'],
      notes=['Les 5 derniers mots de passe ne peuvent pas être réutilisés.',
             'Le mot de passe expire au bout de 90 jours : l’application vous demande alors d’en choisir un nouveau.'],
      mots=['mot', 'passe', 'motdepasse', 'password', 'mdp', 'changer', 'modifier', 'nouveau', 'expire', 'expiration'],
      liens=[('Mon profil', 'profil_utilisateur')],
      questions=['changer mon mot de passe', 'modifier mdp']),

    A('mot_de_passe_oublie', 'compte', 'J’ai oublié mon mot de passe',
      'Utilisez « Mot de passe oublié » sur la page de connexion ; un lien de réinitialisation vous est envoyé par e-mail.',
      etapes=['Page de connexion → **Mot de passe oublié ?**',
              'Saisissez l’adresse e-mail de votre compte.',
              'Ouvrez le lien reçu (valable pour une durée limitée) et choisissez un nouveau mot de passe.',
              'Pas d’e-mail après quelques minutes ? Vérifiez les indésirables, puis demandez à votre administrateur de réinitialiser votre mot de passe.'],
      mots=['oublie', 'oubli', 'perdu', 'mot', 'passe', 'motdepasse', 'password', 'mdp', 'reinitialiser', 'reinitialisation', 'reset', 'recuperer'],
      liens=[('Mot de passe oublié', 'forgot_password')],
      pour='public',
      questions=['j ai oublie mon mot de passe', 'je ne me souviens plus du mot de passe']),

    A('compte_bloque', 'compte', 'Mon compte est bloqué',
      'Après 5 échecs de connexion le compte est bloqué 30 minutes ; après 10 échecs, seul un administrateur peut le débloquer.',
      etapes=['Attendez 30 minutes et réessayez en vérifiant majuscules et clavier (AZERTY / QWERTY).',
              'Si le message persiste, utilisez « Mot de passe oublié ».',
              'Toujours bloqué : contactez l’administrateur de votre organisation, qui peut réactiver le compte et réinitialiser le mot de passe.'],
      notes=['Un compte désactivé (départ, mutation) ne peut être réactivé que par un administrateur.'],
      mots=['bloque', 'bloquer', 'verrouille', 'verrouillage', 'desactive', 'connecter', 'connexion', 'impossible', 'acces', 'refuse', 'echec', 'tentatives'],
      pour='public',
      questions=['je n arrive pas a me connecter', 'compte verrouille', 'impossible de me connecter']),

    A('double_auth_activer', 'compte', 'Activer la double authentification (2FA)',
      'La double authentification ajoute un code à 6 chiffres, généré par une application sur votre téléphone, après le mot de passe.',
      etapes=['Installez une application d’authentification : Google Authenticator, Microsoft Authenticator, FreeOTP…',
              'Menu profil → **Sécurité du compte** → **Activer la double authentification**.',
              'Scannez le QR code avec l’application (ou saisissez la clé affichée).',
              'Saisissez le code à 6 chiffres affiché par l’application pour confirmer.',
              'Notez ou imprimez les **8 codes de secours** : ils ne sont affichés qu’une seule fois.'],
      notes=['Obligatoire pour les administrateurs : tant qu’elle n’est pas activée, l’application vous redirige vers cette page.',
             'Le code change toutes les 30 secondes ; l’heure du téléphone doit être automatique.',
             'Une connexion par Microsoft ou Google (SSO) n’exige pas ce code : votre fournisseur gère déjà la sécurité.'],
      mots=['double', 'authentification', '2fa', 'mfa', 'totp', 'otp', 'code', 'authenticator', 'google', 'microsoft', 'qr', 'securite', 'activer', 'deux', 'facteurs'],
      liens=[('Sécurité du compte', 'securite_compte.index')],
      questions=['comment activer la 2fa', 'double authentification']),

    A('double_auth_perdu', 'compte', 'J’ai perdu mon téléphone / je n’ai plus mes codes 2FA',
      'Utilisez un de vos codes de secours à la place du code à 6 chiffres. Sans code de secours, '
      'demandez à votre administrateur de réinitialiser votre double authentification.',
      etapes=['Sur l’écran du code, saisissez un **code de secours** (chacun ne sert qu’une fois).',
              'Une fois connecté : **Sécurité du compte** → désactivez puis réactivez la 2FA avec le nouveau téléphone.',
              'Générez de nouveaux codes de secours.',
              'Plus aucun code de secours ? L’administrateur de votre organisation (ou le super administrateur pour un administrateur) peut réinitialiser votre 2FA ; vous la réactiverez à la connexion suivante.'],
      notes=['Le code est refusé alors que l’application l’affiche ? Réglez l’heure du téléphone en automatique.'],
      mots=['perdu', 'perte', 'telephone', 'portable', 'mobile', 'change', 'changement', 'secours', 'code', 'codes', '2fa', 'authentificateur', 'refuse', 'invalide', 'double'],
      liens=[('Sécurité du compte', 'securite_compte.index')],
      pour='public',
      questions=['j ai change de telephone', 'code 2fa invalide', 'je n ai plus acces a mon authenticator']),

    A('double_auth_reinit_admin', 'compte', 'Réinitialiser la 2FA d’un utilisateur (administrateur)',
      'Dans la gestion des utilisateurs, ouvrez le compte et utilisez « Réinitialiser la double authentification ».',
      etapes=['Administration → **Utilisateurs**.',
              'Sur la ligne de la personne, cliquez sur l’icône **Réinitialiser la double authentification** et confirmez.',
              'Prévenez l’utilisateur : à sa prochaine connexion il réactivera la 2FA avec son nouveau téléphone.'],
      notes=['Vérifiez l’identité de la personne (appel, présence) avant de réinitialiser : c’est une opération sensible, elle est journalisée.'],
      mots=['reinitialiser', 'reset', '2fa', 'double', 'authentification', 'utilisateur', 'debloquer', 'administrateur'],
      liens=[('Utilisateurs', 'client_admin_utilisateurs')],
      pour='admin'),

    A('sso', 'compte', 'Se connecter avec Microsoft ou Google (SSO)',
      'Si votre organisation l’a activé, des boutons « Se connecter avec Microsoft / Google » apparaissent sur la page de connexion.',
      etapes=['Cliquez sur le bouton de votre fournisseur sur la page de connexion.',
              'Connectez-vous avec votre compte professionnel.',
              'Votre adresse e-mail doit correspondre à un compte Egalyx existant : le SSO ne crée pas de compte.'],
      notes=['Les boutons n’apparaissent pas ? Le SSO n’est pas activé sur la plateforme : il est désactivé par défaut et se configure côté serveur (variables SSO_*).',
             'Message « aucun compte » : demandez à votre administrateur de créer votre compte avec la même adresse e-mail.'],
      mots=['sso', 'microsoft', 'google', 'office', '365', 'azure', 'entra', 'gmail', 'workspace', 'connexion', 'unique', 'oidc'],
      pour='public',
      questions=['se connecter avec microsoft', 'connexion google']),

    A('profil', 'compte', 'Modifier mon profil (nom, e-mail, téléphone)',
      'Menu en haut à droite → Mon profil.',
      notes=['Certains champs (rôle, organisation, rattachement) ne sont modifiables que par un administrateur.'],
      mots=['profil', 'nom', 'email', 'adresse', 'telephone', 'photo', 'informations', 'personnelles', 'modifier'],
      liens=[('Mon profil', 'profil_utilisateur')]),

    A('deconnexion', 'compte', 'Déconnexion automatique et session expirée',
      'Par sécurité, la session se ferme après une période d’inactivité. Reconnectez-vous ; les données enregistrées ne sont pas perdues.',
      notes=['Un formulaire resté ouvert longtemps peut afficher « jeton CSRF expiré » à l’envoi : rechargez la page et recommencez.'],
      mots=['deconnecte', 'deconnexion', 'session', 'expire', 'expiree', 'inactivite', 'csrf', 'jeton', 'token', 'deconnecter']),

    # ==================================================================
    # ADMINISTRATION DE L'ORGANISATION
    # ==================================================================
    A('roles', 'admin', 'Rôles et permissions : comment ça marche ?',
      'Ce qu’une personne voit dépend de trois couches : les **modules activés** pour l’organisation, '
      'son **rôle** (permissions par défaut) et ses **permissions personnelles** (ajoutées ou retirées par l’administrateur).',
      etapes=['**Modules de l’organisation** : fixés par le super administrateur (selon l’abonnement). Un module désactivé disparaît pour tout le monde, administrateur compris.',
              '**Rôle** : administrateur, manager, auditeur, conformité, utilisateur… chaque rôle donne un jeu de permissions par défaut.',
              '**Permissions personnelles** : l’administrateur coche ou décoche des permissions précises (voir, gérer, valider…).',
              'Dans chaque module, une personne peut en plus agir sur un élément dont elle est responsable (responsable d’action, évaluateur, membre de l’équipe d’audit…).'],
      notes=['Voir ≠ gérer : « voir » permet de consulter, « gérer » permet de créer, modifier, archiver.',
             'L’administrateur de l’organisation a toutes les permissions des modules actifs.'],
      mots=['role', 'roles', 'permission', 'permissions', 'droit', 'droits', 'acces', 'profil', 'habilitation', 'habilitations', 'visibilite', 'voir'],
      liens=[('Utilisateurs', 'client_admin_utilisateurs')],
      questions=['comment fonctionnent les permissions', 'qui voit quoi']),

    A('utilisateur_creer', 'admin', 'Créer un utilisateur',
      'Administration → Utilisateurs → Créer un utilisateur ; choisissez le rôle puis ajustez les permissions.',
      etapes=['Administration → **Utilisateurs** → **Créer un utilisateur**.',
              'Renseignez l’identifiant et l’e-mail professionnel, puis **prénom, nom et fonction** : c’est ce qui s’affiche dans les listes et l’organigramme.',
              'Choisissez sa **direction** et, si besoin, son **service**, puis **ce qu’elle peut voir** : toute l’organisation, son pôle, sa direction ou son service.',
              'Choisissez le **rôle** : il applique les permissions par défaut.',
              'Enregistrez, puis ouvrez **Permissions** pour cocher ou décocher des droits précis si besoin.',
              'Transmettez l’identifiant et le mot de passe provisoire par un canal sûr ; la personne le changera à la première connexion.'],
      notes=['Astuce : depuis la page **Structure de l’organisation**, l’icône « créer un collaborateur » d’une direction ou d’un service ouvre ce formulaire avec le rattachement déjà choisi.',
             'Le nombre d’utilisateurs peut être limité par votre abonnement.',
             'Les managers ayant la permission « gérer les utilisateurs » peuvent aussi créer des comptes, dans la limite de leurs propres droits.'],
      mots=['utilisateur', 'utilisateurs', 'compte', 'comptes', 'collaborateur', 'collaborateurs', 'collegue', 'collegues', 'creer', 'ajouter', 'inviter', 'nouveau', 'membre', 'personne', 'equipe', 'integrer'],
      liens=[('Utilisateurs', 'client_admin_utilisateurs')],
      perms=['can_manage_users'], pour='admin',
      questions=['ajouter un collaborateur', 'creer un compte', 'mettre un collegue dans l outil', 'inviter mon equipe']),

    A('permissions_modifier', 'admin', 'Donner ou retirer un accès à un utilisateur',
      'Administration → Utilisateurs → Permissions de la personne : cochez les droits voulus, par module.',
      etapes=['Administration → **Utilisateurs** → bouton **Permissions** sur la ligne de la personne.',
              'Les cases reflètent les droits effectifs actuels (rôle + ajouts + modules actifs).',
              'Cochez / décochez puis **Enregistrer**. La personne voit le changement à sa prochaine page.'],
      notes=['Une permission d’un module non activé pour l’organisation reste sans effet : demandez l’activation du module au super administrateur.',
             'Pour un accès en lecture seule, cochez seulement les permissions « voir ».'],
      mots=['permission', 'permissions', 'droit', 'droits', 'acces', 'donner', 'retirer', 'enlever', 'autoriser', 'interdire', 'lecture', 'seule', 'cocher'],
      liens=[('Utilisateurs', 'client_admin_utilisateurs')],
      perms=['can_manage_users'], pour='admin',
      questions=['donner acces a un module', 'retirer un droit', 'lecture seule', 'donner les droits sur un module a un collegue', 'mon collegue doit pouvoir modifier']),

    A('utilisateur_desactiver', 'admin', 'Désactiver un utilisateur qui part',
      'Désactivez le compte plutôt que de le supprimer : l’historique (évaluations, validations, signatures) reste attribué.',
      etapes=['Administration → **Utilisateurs** → ouvrez la personne → **Désactiver le compte** (ou l’icône de la ligne).',
              'La personne ne peut plus se connecter ; ses sessions ouvertes sont fermées. Rien n’est effacé.',
              'Egalyx ouvre ensuite la liste de ses **responsabilités en cours** (risques, plans d’action, KRI, incidents, directions dirigées…) : '
              'choisissez à qui les **transférer** (toutes, ou seulement certaines catégories).'],
      notes=['Le compte peut être réactivé à tout moment.'],
      mots=['desactiver', 'supprimer', 'depart', 'quitte', 'partir', 'retirer', 'utilisateur', 'compte', 'reattribuer'],
      liens=[('Utilisateurs', 'client_admin_utilisateurs')],
      perms=['can_manage_users'], pour='admin'),

    A('organisation', 'admin', 'Organisation : pays, pôles, filiales, directions, services',
      'La structure suit la hiérarchie pays → pôle (ou filiale) → direction → service. Elle sert au rattachement '
      'des utilisateurs, des cartographies, des incidents et aux filtres des tableaux de bord.',
      etapes=['Paramétrage → **Directions** : la page **Structure de l’organisation** montre tout, en arborescence.',
              'Bouton **Ajouter** : créez les **pays**, puis les **pôles / filiales** (rattachés à un pays), puis les **directions**.',
              'Sur la ligne d’une direction, **+** ajoute un **service** ; sur un pays, un pôle ; sur un pôle, une direction (le parent est déjà choisi).',
              'Désignez un **responsable** à chaque niveau (« À pourvoir » signale ceux qui manquent) et rattachez les collaborateurs.',
              'Bouton **Organigramme** : la même structure, dessinée, imprimable en A3.'],
      notes=['Une entité encore utilisée (cartographies, collaborateurs, sous-entités…) ne peut pas être archivée : Egalyx dit exactement ce qui la retient.',
             'Une direction peut être rattachée directement à l’organisation (direction générale) : elle s’affiche en tête.',
             'L’organigramme visuel d’un processus se modifie depuis la fiche du processus.'],
      mots=['organisation', 'organigramme', 'pole', 'poles', 'filiale', 'filiales', 'direction', 'directions', 'service', 'services', 'pays', 'structure', 'entite', 'entites', 'departement'],
      liens=[('Structure de l’organisation', 'admin_directions'), ('Organigramme', 'admin_organigramme')],
      perms=['can_view_departments', 'can_manage_departments'], pour='admin',
      questions=['creer une filiale', 'ajouter une direction', 'gestion des poles']),

    A('parametres_risque', 'admin', 'Paramétrer la cotation : seuils, taux de maîtrise, appétence',
      'Paramètres → Risques permet d’adapter à votre organisation les seuils de niveaux, la réduction apportée '
      'par chaque niveau de maîtrise, l’appétence au risque et les paramètres LCB-FT.',
      etapes=['Menu Administration → **Paramètres des risques**.',
              '**Seuils** : bornes des niveaux Faible / Moyen / Élevé (le reste est Critique). Par défaut : 4, 10, 16 sur 25.',
              '**Taux de maîtrise** : réduction de la probabilité pour les niveaux 1 à 5. Par défaut 0 %, 10 %, 25 %, 40 %, 60 %.',
              '**Appétence** : score net au-delà duquel un risque est « hors appétence » (global ou par catégorie).',
              'Enregistrez : toutes les cotations sont recalculées.'],
      notes=['Changer les seuils modifie les couleurs et les compteurs de tous les risques : faites-le valider par votre comité.',
             'Chaque changement est journalisé (ancienne et nouvelle valeur).'],
      mots=['parametre', 'parametres', 'parametrer', 'seuil', 'seuils', 'cotation', 'bareme', 'echelle', 'taux', 'appetence', 'tolerance', 'configurer', 'reglage', 'reglages', 'matrice'],
      liens=[('Paramètres des risques', 'parametres_risque.page')],
      perms=['can_manage_settings'], pour='admin',
      questions=['changer les seuils de criticite', 'definir l appetence au risque']),

    A('identite_organisation', 'admin', 'Afficher le nom et le logo de mon organisation',
      'Le nom affiché et le logo apparaissent en haut de l’outil, dans l’objet des e-mails d’alerte et sur le '
      'rapport au comité d’audit.',
      etapes=['Menu du compte → **Identité de l’organisation**.',
              'Saisissez un nom court (sigle, 30 caractères) et, si vous le souhaitez, déposez votre logo.',
              'Enregistrez : l’en-tête change immédiatement pour tous les utilisateurs de l’organisation.'],
      notes=['Logo : PNG, JPEG ou WebP, 1 Mo au maximum, de préférence horizontal sur fond transparent.'],
      mots=['logo', 'nom', 'identite', 'marque', 'personnaliser', 'entete', 'sigle'],
      liens=[('Identité de l’organisation', 'identite.page')], pour='admin',
      questions=['mettre mon logo', 'changer le nom affiche', 'personnaliser l outil']),

    A('presentation_rapports', 'admin', 'Mettre les rapports aux couleurs de mon organisation',
      'Les rapports PDF, imprimables et Word reprennent votre logo, votre couleur, votre mention de confidentialité et votre '
      'pied de page : rapport d’audit (PDF, complet et Word), rapport au comité d’audit, cartographie des risques, KRI, '
      'incidents, plans d’action N2, logigrammes, dispositifs de contrôle, organigramme, feuilles de travail et audits qualité.',
      etapes=['Menu du compte → **Identité de l’organisation**, section **Présentation des rapports**.',
              'Cochez la case de la couleur et choisissez une teinte assez foncée (les couleurs trop claires sont refusées).',
              'Choisissez une mention de confidentialité (« Confidentiel — usage interne », « Diffusion restreinte »…) '
              'et, si vous le souhaitez, un pied de page (raison sociale, direction, adresse).',
              'Gardez ou décochez « Afficher le logo sur les rapports », puis **Enregistrer** : l’aperçu montre le résultat, '
              'et tous les rapports suivants l’appliquent.'],
      notes=['Sans réglage, les rapports gardent leur présentation habituelle.',
             'Les réglages ne concernent que votre organisation ; ils sont journalisés.',
             'La lettre de mission garde ses propres en-têtes (réglés par le super-administrateur).'],
      mots=['rapport', 'rapports', 'couleur', 'logo', 'confidentiel', 'confidentialite', 'mention', 'pied', 'page',
            'charte', 'presentation', 'personnaliser', 'pdf', 'entete'],
      liens=[('Identité de l’organisation', 'identite.page')], pour='admin',
      questions=['mettre mon logo sur les rapports', 'changer la couleur des rapports', 'ajouter confidentiel sur les rapports',
                 'personnaliser le pied de page des rapports', 'rapport aux couleurs de la banque']),

    A('contenu_rapports', 'admin', 'Choisir le contenu du rapport d’audit et du rapport au comité',
      'Pour le rapport d’audit (PDF et Word) et le rapport au comité d’audit, votre organisation choisit le titre, les sections '
      'affichées, un texte d’introduction et de conclusion types, et les signataires.',
      etapes=['Menu du compte → **Identité de l’organisation** → lien « Choisir aussi le contenu » '
              '(ou directement **Contenu des rapports**), puis l’onglet du rapport.',
              'Saisissez un titre (vide : titre habituel) et décochez les sections à ne pas afficher ; '
              'la numérotation et le sommaire suivent.',
              'Rédigez l’introduction et la conclusion types. Les champs {organisation}, {date}, et pour l’audit '
              '{reference} et {mission}, sont remplis automatiquement à chaque rapport.',
              'Cochez « Choisir les signataires » et indiquez jusqu’à 4 fonctions (le nom est facultatif : sans nom, '
              'une ligne reste pour signer à la main), puis **Enregistrer**.'],
      notes=['« Rétablir le contenu d’origine » annule tous ces choix pour le rapport affiché.',
             'La synthèse du rapport au comité et le résumé exécutif du rapport d’audit sont toujours affichés.',
             'Chaque changement est journalisé et ne concerne que votre organisation.'],
      mots=['contenu', 'section', 'sections', 'masquer', 'signataire', 'signataires', 'signature', 'introduction',
            'conclusion', 'titre', 'sommaire', 'rapport', 'comite', 'modele', 'texte'],
      liens=[('Contenu des rapports', 'rapport_contenu.page')], pour='admin',
      questions=['changer les signataires du rapport d audit', 'masquer une section du rapport au comite',
                 'ajouter une introduction au rapport', 'changer le titre du rapport d audit',
                 'personnaliser le contenu des rapports']),

    A('dossier_fige', 'audit', 'Dossier de mission figé après le rapport définitif',
      'Dès que le rapport définitif est émis, le dossier de mission ne se modifie plus : feuilles de travail, tests, '
      'erreurs, preuves, constats, équipe et fiche de l’audit. C’est la règle des normes d’audit interne : le dossier '
      'doit refléter exactement ce qui a fondé le rapport.',
      etapes=['Le suivi continue normalement : recommandations, plans d’action, temps passé, dépôt du rapport signé, '
              'clôture ou archivage de l’audit.',
              'Pour une correction, un gestionnaire de l’audit ouvre la fiche de l’audit → **Constats et réponses** → '
              '« Rouvrir le dossier pour une correction » et indique le motif (15 caractères au moins).',
              'L’équipe est prévenue, la réouverture est journalisée avec son motif.',
              'Une fois la correction faite : **Figer de nouveau le dossier**.'],
      notes=['Une modification refusée affiche « le dossier de mission est figé ».',
             'La fiche de l’audit indique « Dossier figé » ou « Dossier rouvert pour correction ».'],
      mots=['fige', 'figer', 'verrouille', 'verrouiller', 'bloque', 'rouvrir', 'reouvrir', 'dossier', 'definitif',
            'modifier', 'feuille', 'constat', 'correction'],
      liens=[('Missions d’audit', 'liste_audits')],
      questions=['je ne peux plus modifier ma feuille de travail', 'rouvrir un audit apres le rapport definitif',
                 'le dossier de mission est fige', 'corriger un constat apres le rapport definitif']),

    A('satisfaction_audites', 'audit', 'Questionnaire de satisfaction des audités',
      'À l’émission du rapport définitif, les audités (participants et responsables des recommandations) reçoivent '
      'une notification pour donner leur avis sur la mission : 6 affirmations notées de 1 à 5 et un commentaire.',
      etapes=['L’audité clique sur la notification, ou sur **Donner mon avis** depuis la fiche de l’audit.',
              'Il répond aux questions qu’il souhaite (« sans avis » possible) ; il peut modifier sa réponse pendant 30 jours.',
              'Le gestionnaire voit les résultats de la mission dans **Constats et réponses**, et la synthèse de l’année '
              'dans le menu Audit interne → **Satisfaction des audités**.'],
      notes=['Les résultats sont présentés sans nom, et seulement à partir de 2 réponses.',
             'L’équipe d’audit n’est pas invitée : elle ne s’évalue pas elle-même.'],
      mots=['satisfaction', 'avis', 'questionnaire', 'audites', 'audite', 'enquete', 'evaluation', 'retour', 'mission',
            'qualite', 'note'],
      liens=[('Satisfaction des audités', 'satisfaction_audit.synthese')],
      questions=['questionnaire de satisfaction apres un audit', 'avis des audites sur la mission',
                 'mesurer la satisfaction des audites', 'donner mon avis sur un audit']),

    A('univers_audit', 'audit', 'Univers d’audit : ce qui doit être audité, et quand',
      'L’univers d’audit liste ce que l’audit interne peut auditer (processus, directions, filiales, systèmes, projets), '
      'avec un niveau de risque, un cycle d’audit, la date du dernier audit et l’échéance du prochain.',
      etapes=['Menu Audit interne → **Univers d’audit**.',
              '« Ajouter ceux qui manquent » crée une entité par processus (logigramme) et, si coché, par direction ; '
              'ou ajoutez une entité à la main (filiale, système…).',
              'Réglez le risque de chaque entité : le cycle suit (élevé 1 an, moyen 2 ans, faible 3 ans), ou fixez-le vous-même.',
              'Pour un audit fait avant l’outil, saisissez la date du dernier audit. Les audits de l’outil comptent '
              'automatiquement s’ils portent sur le processus de l’entité, ou s’ils lui sont rattachés (« Modifier » → Rattacher).',
              'Les entités « Jamais audité » ou « À auditer » remontent en tête : c’est la base du programme d’audit.'],
      notes=['Un audit compte à la date de son rapport définitif.', 'Une entité retirée reste consultable et peut être remise.'],
      mots=['univers', 'entite', 'entites', 'auditable', 'auditables', 'cycle', 'couverture', 'dernier', 'audite',
            'programme', 'planifier', 'prochain', 'risque'],
      liens=[('Univers d’audit', 'fonction_audit.page_univers')],
      questions=['univers d audit', 'quand auditer ce processus', 'liste des entites auditables',
                 'qu est ce qui n a pas ete audite depuis longtemps', 'couverture du plan d audit']),

    A('qualite_fonction_audit', 'audit', 'Qualité de la fonction d’audit (Normes IIA 2024)',
      'Évaluez la conformité de votre fonction d’audit interne aux 15 principes des Normes internationales d’audit interne : '
      'évaluation interne périodique (au moins une fois par an) et évaluation externe au moins tous les 5 ans.',
      etapes=['Menu Audit interne → **Qualité de la fonction** : alertes, indicateurs de l’année et observations par principe.',
              '**Évaluation interne** : pour chaque principe, Conforme / Partiellement / Non conforme / Sans objet, '
              'un constat et, si besoin, une action d’amélioration.',
              'Indiquez la date, la conclusion générale et la synthèse pour le Conseil, puis **Valider** '
              '(une évaluation validée ne se modifie plus).',
              '**Saisir une évaluation externe** : même grille, avec le cabinet ou la personne qui l’a conduite.'],
      notes=['Indicateurs calculés par l’outil : programme réalisé, délai du rapport définitif, recommandations mises en œuvre, '
             'satisfaction des audités, indépendance documentée, couverture de l’univers, charte.',
             'Les observations aident l’évaluation ; elles ne remplacent pas le jugement de l’évaluateur.'],
      mots=['qualite', 'qaip', 'normes', 'iia', 'principes', 'evaluation', 'externe', 'interne', 'conformite',
            'auto', 'autoevaluation', 'fonction', 'indicateurs', 'kpi'],
      liens=[('Qualité de la fonction', 'fonction_audit.page_qualite')],
      questions=['evaluation externe de l audit interne', 'auto evaluation de la fonction audit', 'conformite aux normes iia',
                 'programme d assurance et d amelioration qualite', 'indicateurs de la fonction audit']),

    A('charte_audit', 'audit', 'Charte d’audit interne',
      'La charte fixe la mission, le positionnement, les droits d’accès et les responsabilités de l’audit interne. '
      'Elle est approuvée par le Conseil et revue au moins une fois par an.',
      etapes=['Menu Audit interne → **Charte d’audit** → « Rédiger la charte à partir du modèle » '
              '(le modèle reprend les points attendus par les Normes ; adaptez-le).',
              'Enregistrez le brouillon autant de fois que nécessaire.',
              'Après approbation, indiquez la date et l’instance (Conseil d’administration, comité d’audit…) puis '
              '**Mettre en vigueur**. La revue suivante est prévue un an après.',
              'Pour la modifier : « Préparer une nouvelle version » ; l’ancienne est conservée dans l’historique.'],
      mots=['charte', 'mandat', 'mission', 'audit', 'interne', 'conseil', 'approbation', 'revue', 'version'],
      liens=[('Charte d’audit', 'fonction_audit.page_charte')],
      questions=['charte d audit interne', 'rediger la charte d audit', 'mettre a jour la charte d audit',
                 'faire approuver la charte par le conseil']),

    A('application_telephone', 'admin', 'Installer Egalyx sur mon téléphone',
      'Egalyx s’installe comme une application, sans passer par un magasin : icône sur l’écran d’accueil, plein écran, '
      'ouverture sur « Ma semaine », raccourci « Signaler un incident ».',
      etapes=['Ouvrez Egalyx à son adresse en ligne (https://…egalyx.com), pas sur 127.0.0.1 depuis un téléphone.',
              'Android (Chrome) : menu du compte (en haut à droite) → **Installer l’application**, ou menu ⋮ → **Installer l’application**.',
              'iPhone / iPad (Safari) : bouton **Partager** (carré avec une flèche) → **Sur l’écran d’accueil** → **Ajouter**.',
              'Ordinateur Chrome ou Edge : menu du compte → **Installer l’application**, ou l’icône d’installation à droite de la barre d’adresse.',
              'Mac avec Safari : menu **Fichier → Ajouter au Dock**.'],
      notes=['Si « Installer l’application » vous amène sur cette page, c’est que votre navigateur ne propose pas l’installation directe : suivez l’étape de votre appareil ci-dessus.',
             'Firefox sur ordinateur ne permet pas d’installer d’application : utilisez Chrome, Edge ou Safari.',
             'Aucune donnée n’est conservée sur le téléphone : sans réseau, une page « hors ligne » s’affiche.',
             'Les notifications par e-mail et le résumé quotidien se règlent dans « Mes notifications ».'],
      mots=['application', 'mobile', 'telephone', 'android', 'iphone', 'installer', 'ecran', 'accueil', 'pwa'],
      liens=[('Mes notifications', 'preferences_notifications')], pour='tous',
      questions=['installer egalyx sur mon telephone', 'application mobile', 'egalyx sur iphone']),

    A('alertes_incidents', 'maitrise', 'Régler les e-mails d’alerte des incidents',
      'Les alertes (délai dépassé, escalade) s’affichent toujours dans l’application ; leur copie par e-mail se règle '
      'par organisation et est désactivée tant qu’elle n’a pas été activée.',
      etapes=['Incidents → bouton **Alertes e-mail**.',
              'Activez l’envoi, choisissez les événements et les destinataires (responsable, superviseur, gestionnaires).',
              'Ajoutez si besoin des adresses supplémentaires (boîte du risk manager, astreinte).'],
      notes=['Chacun peut arrêter ces e-mails pour lui-même avec le lien en bas de chaque alerte.',
             'Plusieurs délais dépassés en même temps donnent un seul e-mail récapitulatif.'],
      mots=['alerte', 'email', 'e-mail', 'mail', 'notification', 'delai', 'depasse', 'sla', 'escalade', 'desabonner'],
      liens=[('Alertes e-mail des incidents', 'alertes_incidents.page')],
      perms=['can_manage_incidents'], pour='tous',
      questions=['je recois des mails d alerte incident', 'arreter les emails de delai depasse', 'configurer les alertes incidents']),

    A('import_cartographie', 'risques', 'Importer ma cartographie Excel existante',
      'Déposez le fichier tel que vous l’utilisez : Egalyx trouve le tableau, reconnaît les colonnes par leur titre et '
      'vous montre ce qui sera créé avant tout enregistrement.',
      etapes=['Menu **Importer une cartographie** : déposez le fichier .xlsx ou .csv.',
              'Vérifiez l’aperçu : colonnes reconnues, cotations converties sur 1 à 5, anomalies et doublons signalés.',
              'Corrigez une colonne mal reconnue si besoin, puis « Actualiser l’aperçu ».',
              'Choisissez la cartographie (existante ou nouvelle) et cliquez sur **Importer**.',
              'Complétez les dispositifs créés (type, fréquence, responsable) et lancez l’évaluation.'],
      notes=['Échelles acceptées : 1 à 5, 1 à 10 (ramenée sur 5), ou en mots (faible, moyen, élevé…). Pour une échelle '
             'sur 3 ou 4, indiquez-la dans le titre de colonne : « Impact (1-4) ».',
             'Plusieurs contrôles dans une cellule : séparez-les par « ; » ou un retour à la ligne ; chacun devient un '
             'dispositif de maîtrise non évalué.',
             'Une cotation absente ou illisible donne une valeur provisoire 3 × 3, signalée sur le risque.',
             'Votre référence de risque est conservée si elle est libre ; le responsable est rattaché s’il correspond à un '
             'utilisateur (identifiant, e-mail ou nom).'],
      mots=['import', 'importer', 'excel', 'xlsx', 'csv', 'cartographie', 'reprise', 'migration', 'fichier', 'existant'],
      liens=[('Importer une cartographie', 'import_carto.page'), ('Bibliothèque de risques', 'bibliotheque.page')],
      perms=['can_manage_risks'], pour='admin',
      questions=['importer ma cartographie excel', 'reprendre mon fichier de risques', 'comment importer mes risques']),

    A('import_export_admin', 'admin', 'Importer des données en masse',
      'Les risques d’un secteur s’importent depuis la Bibliothèque de risques ; les autres données depuis '
      'Intégrations → Import / export (modèles de fichiers fournis).',
      mots=['import', 'importer', 'importation', 'excel', 'csv', 'fichier', 'masse', 'charger', 'reprise', 'migration'],
      liens=[('Bibliothèque de risques', 'bibliotheque.page'), ('Import / export', 'admin_import_export')],
      perms=['can_manage_import_export', 'can_manage_risks'], pour='admin'),

    A('journal', 'admin', 'Qui a fait quoi ? (journal d’activité)',
      'Les actions sensibles (connexion, changement de permissions, validation, signature, paramètres, export) sont '
      'journalisées avec l’auteur, la date et l’adresse IP. L’administrateur les consulte depuis l’administration.',
      mots=['journal', 'historique', 'trace', 'tracabilite', 'logs', 'modifie', 'modification', 'modifications', 'piste', 'auteur'],
      questions=['qui a modifie ce risque', 'qui a fait cette modification'],
      pour='admin'),

    # ==================================================================
    # RISQUES
    # ==================================================================
    A('cartographie_creer', 'risques', 'Créer une cartographie des risques',
      'Cartographie risques → Nouvelle cartographie : nommez-la et rattachez-la à un périmètre.',
      etapes=['Menu **Cartographie risques** → **Nouvelle cartographie**.',
              'Donnez un nom (ex. « Cartographie 2026 – Direction financière ») et choisissez le périmètre : pôle, direction ou service.',
              'Ajoutez les risques un par un, ou importez-les depuis la **Bibliothèque de risques**.',
              'Évaluez chaque risque (évaluation triphasée).'],
      mots=['cartographie', 'cartographies', 'carto', 'creer', 'nouvelle', 'ajouter', 'risques', 'perimetre'],
      liens=[('Nouvelle cartographie', 'nouvelle_cartographie'), ('Cartographies', 'liste_cartographies')],
      perms=['can_manage_risks'],
      questions=['faire une cartographie', 'creer une carto']),

    A('risque_ajouter', 'risques', 'Ajouter un risque',
      'Ouvrez la cartographie puis « Ajouter un risque » : intitulé, description, catégorie, causes, conséquences, propriétaire.',
      etapes=['Ouvrez la cartographie concernée → **Ajouter un risque**.',
              'Intitulé court et explicite (« Fraude au virement fournisseur » plutôt que « Fraude »).',
              'Catégorie (opérationnel, financier, conformité, stratégique…), causes et conséquences.',
              'Propriétaire du risque et processus concerné.',
              'Enregistrez puis lancez l’évaluation.'],
      notes=['Une référence unique (RSQ-AAAA-NNNN) est attribuée automatiquement.',
             'Pour aller vite, importez des risques types depuis la Bibliothèque de risques puis adaptez-les.'],
      mots=['risque', 'risques', 'ajouter', 'creer', 'nouveau', 'saisir', 'identifier', 'identification'],
      liens=[('Cartographies', 'liste_cartographies')],
      perms=['can_manage_risks']),

    A('bibliotheque', 'risques', 'Bibliothèque de risques par secteur',
      'Une bibliothèque de 84 risques types répartis en 8 secteurs (banque, microfinance, assurance, industrie, '
      'services, secteur public, télécoms, santé…) que vous importez dans une cartographie en quelques clics.',
      etapes=['Menu **Bibliothèque de risques**.',
              'Choisissez le secteur, cochez les risques utiles.',
              'Choisissez la cartographie de destination puis **Importer**.',
              'Adaptez ensuite l’intitulé et la description à votre contexte, puis évaluez.'],
      mots=['bibliotheque', 'referentiel', 'secteur', 'modele', 'modeles', 'types', 'catalogue', 'liste', 'risques', 'importer', 'banque', 'microfinance', 'assurance'],
      liens=[('Bibliothèque de risques', 'bibliotheque.page')],
      perms=['can_manage_risks'],
      questions=['liste de risques types', 'importer des risques']),

    A('evaluation_triphasee', 'risques', 'Évaluation triphasée d’un risque',
      'Chaque risque est évalué en trois phases : pré-évaluation, validation, confirmation. Le niveau n’est '
      'retenu qu’après la confirmation.',
      etapes=['**Phase 1 – Pré-évaluation** (évaluateur ou référent) : impact (1-5), probabilité (1-5) et niveau de maîtrise (1-5), avec commentaire.',
              '**Phase 2 – Validation** (validateur) : il accepte ou corrige les cotations.',
              '**Phase 3 – Confirmation** : la cotation devient la cotation officielle du risque.',
              'Le score brut, le score net et le niveau sont calculés automatiquement à chaque phase.'],
      notes=['Les niveaux de maîtrise s’affichent en couleur : 1 Insuffisant (rouge), 2 Partiel (orange), 3 Adéquat (jaune), 4 Bon (vert clair), 5 Excellent (vert).',
             'Un risque évalué par un opérationnel peut être attribué via un lien d’évaluation ; la personne ne voit que ce risque.'],
      mots=['evaluation', 'evaluer', 'triphasee', 'triphase', 'phase', 'phases', 'pre', 'validation', 'confirmation', 'cote', 'coter', 'cotation', 'noter', 'notation', 'impact', 'probabilite', 'maitrise', 'reevaluer'],
      liens=[('Cartographies', 'liste_cartographies')],
      perms=['can_manage_risks', 'can_confirm_evaluations'],
      questions=['comment evaluer un risque', 'les trois phases']),

    A('cotation', 'risques', 'Comment le score brut et le score net sont-ils calculés ?',
      '**Brut = impact × probabilité** (1 à 25). **Net = impact × probabilité ajustée**, la probabilité étant réduite '
      'selon le niveau de maîtrise (par défaut 0 %, 10 %, 25 %, 40 %, 60 % pour les niveaux 1 à 5).',
      etapes=['Exemple : impact 4, probabilité 5 → brut 20 (Critique).',
              'Maîtrise 4 (Bon) → réduction 40 % → probabilité ajustée 3 → net 12 (Élevé).',
              'Niveaux par défaut : jusqu’à 4 Faible · jusqu’à 10 Moyen · jusqu’à 16 Élevé · au-delà Critique.'],
      notes=['C’est le score **net** qui sert au tri, aux couleurs et au décompte des risques critiques.',
             'Les seuils et taux peuvent être adaptés par votre organisation (Paramètres → Risques).',
             'L’impact n’est pas réduit par les contrôles : un bon dispositif réduit la probabilité que le risque survienne.'],
      mots=['brut', 'net', 'residuel', 'inherent', 'score', 'calcul', 'calcule', 'formule', 'cotation', 'criticite', 'niveau', 'pourquoi', 'difference', 'multiplication', 'matrice'],
      liens=[('Cartographies', 'liste_cartographies')],
      questions=['pourquoi mon risque est critique', 'difference entre brut et net', 'comment est calcule le score']),

    A('appetence', 'risques', 'Appétence au risque et risques « hors appétence »',
      'L’appétence est le niveau de risque net que la direction accepte. Un risque dont le score net dépasse ce '
      'seuil est signalé « hors appétence » sur le tableau de bord stratégique et dans le rapport au comité.',
      etapes=['L’administrateur définit le seuil global ou par catégorie dans **Paramètres → Risques**.',
              'Les risques au-dessus du seuil apparaissent dans un bandeau du tableau de bord stratégique.',
              'Pour chacun : renforcer les dispositifs de maîtrise ou lancer un plan d’action, ou accepter formellement le risque.'],
      mots=['appetence', 'tolerance', 'acceptable', 'seuil', 'hors', 'depasse', 'depassement', 'limite'],
      liens=[('Paramètres des risques', 'parametres_risque.page'), ('Tableau de bord stratégique', 'tableau_de_bord_strategique')]),

    A('matrice', 'risques', 'Lire la matrice et les couleurs des risques',
      'La matrice 5 × 5 place chaque risque selon son impact (vertical) et sa probabilité (horizontal). '
      'Couleurs : vert Faible, jaune Moyen, orange Élevé, rouge Critique.',
      notes=['Un risque peut apparaître deux fois si vous affichez brut et net : la flèche montre l’effet des contrôles.'],
      mots=['matrice', 'heatmap', 'couleur', 'couleurs', 'rouge', 'orange', 'vert', 'jaune', 'carte', 'chaleur', 'graphique', 'position'],
      liens=[('Cartographies', 'liste_cartographies')]),

    A('risque_archiver', 'risques', 'Supprimer ou archiver un risque',
      'Un risque se clôt ou s’archive plutôt que de se supprimer, pour garder l’historique de ses évaluations, incidents et contrôles.',
      mots=['supprimer', 'archiver', 'effacer', 'retirer', 'cloturer', 'risque', 'doublon'],
      perms=['can_manage_risks']),

    A('analyse_carto', 'risques', 'Analyser une cartographie (statistiques, IA ultra)',
      'Chaque cartographie a un tableau d’analyse : répartition par niveau, catégorie et périmètre, évolution, top risques. '
      'L’« analyse IA ultra » ajoute une lecture rédigée, seulement si l’IA est active pour vous.',
      notes=['Les chiffres (nombre de risques distincts, niveaux) sont calculés sans IA et restent disponibles même IA désactivée.'],
      mots=['analyse', 'analyser', 'statistiques', 'stats', 'ultra', 'synthese', 'repartition', 'cartographie'],
      liens=[('Cartographies', 'liste_cartographies')],
      perms=['can_manage_risks']),

    # ==================================================================
    # MAÎTRISE, KRI, INCIDENTS
    # ==================================================================
    A('dispositif_creer', 'maitrise', 'Créer un dispositif de maîtrise (DMR) et le lier à un risque',
      'Depuis la fiche du risque : « Ajouter un dispositif » ; décrivez le contrôle, son type, sa fréquence, son '
      'responsable, son efficacité et sa couverture.',
      etapes=['Ouvrez le risque → onglet **Dispositifs de maîtrise** → **Ajouter**.',
              'Type : préventif, détectif, correctif ou de pilotage ; manuel ou automatique.',
              'Fréquence (quotidien, mensuel…), responsable, preuve attendue.',
              'Efficacité (1 à 5) et couverture : elles déterminent le niveau de maîtrise et donc le score net.'],
      notes=['Un incident rattaché au dispositif fait automatiquement baisser son efficacité selon sa gravité.',
             'Une vérification « Non conforme » retire 2 points d’efficacité, « À corriger » ou « À améliorer » 1 point ; '
             'le niveau de maîtrise suggéré des évaluations en cours est recalculé et l’écart avec la maîtrise saisie est signalé.',
             'Prochaine vérification : 3 mois (contrôles permanents à mensuels), 6 mois (trimestriels), 1 an (semestriels, '
             'annuels) ; 30 jours après une vérification défavorable. Elle apparaît dans « Ma semaine » du responsable.',
             'Le responsable désigné du dispositif peut le consulter et enregistrer ses vérifications et documents ; '
             'créer, modifier, évaluer ou archiver demande « Gérer les risques ».',
             'Les dispositifs testés en campagne de contrôle ou en contrôle N2 voient leur efficacité confirmée ou revue.'],
      mots=['dispositif', 'dispositifs', 'dmr', 'maitrise', 'controle', 'controles', 'mesure', 'barriere', 'ajouter', 'creer', 'lier', 'efficacite', 'couverture'],
      liens=[('Cartographies', 'liste_cartographies')],
      perms=['can_manage_risks'],
      questions=['ajouter un controle a un risque', 'dispositif de maitrise']),

    A('kri_creer', 'maitrise', 'Créer un indicateur KRI ou KPI',
      'Nouveau KRI : type (KRI ou KPI), risque associé, unité, seuil d’alerte, seuil critique, sens, fréquence et responsable.',
      etapes=['Menu **Indicateurs KRI** → **Nouveau KRI**.',
              'Choisissez **KRI** (exposition à un risque) ou **KPI** (performance, avec cible).',
              'Associez-le à un risque si possible : ses alertes remontent alors sur le risque.',
              'Fixez le **seuil d’alerte**, le **seuil critique** et le **sens** (alerte quand la valeur monte, ou quand elle baisse).',
              'Fréquence de mesure (mensuelle, trimestrielle…) et responsable de la saisie.'],
      mots=['kri', 'kpi', 'indicateur', 'indicateurs', 'creer', 'nouveau', 'ajouter', 'seuil', 'seuils', 'alerte', 'critique'],
      liens=[('Nouveau KRI', 'nouveau_kri_sans_risque'), ('Indicateurs', 'liste_kri')],
      perms=['can_manage_kri']),

    A('kri_mesure', 'maitrise', 'Saisir une mesure de KRI',
      'Ouvrez l’indicateur → Ajouter une mesure (date, valeur, commentaire). L’état normal / alerte / critique est recalculé.',
      notes=['Une mesure critique crée une notification urgente pour le responsable et les gestionnaires.',
             'Les mesures à saisir apparaissent dans « Ma semaine ».'],
      mots=['mesure', 'mesures', 'saisir', 'valeur', 'valeurs', 'kri', 'kpi', 'indicateur', 'renseigner', 'mettre', 'jour'],
      liens=[('Indicateurs', 'liste_kri')],
      perms=['can_manage_kri']),

    A('kri_alerte', 'maitrise', 'Mon KRI est en alerte : que faire ?',
      'Analysez la cause, commentez la mesure, puis si besoin créez un plan d’action ou déclarez un incident.',
      etapes=['Ouvrez l’indicateur et regardez la tendance des dernières mesures.',
              'Ajoutez un commentaire d’analyse sur la mesure.',
              'Si la cause est un dysfonctionnement : déclarez un **incident** ; si un contrôle manque : créez un **plan d’action**.',
              'Ajustez les seuils seulement s’ils étaient mal calibrés (et documentez pourquoi).'],
      mots=['alerte', 'critique', 'depasse', 'depassement', 'rouge', 'kri', 'indicateur', 'seuil'],
      liens=[('Indicateurs', 'liste_kri')]),

    A('incident_declarer', 'maitrise', 'Déclarer un incident',
      'Gestion des incidents → Nouvel incident : description, date, gravité, impact, risque et dispositif concernés.',
      etapes=['Menu **Gestion des incidents** → **Nouvel incident**.',
              'Décrivez les faits (quoi, quand, où, qui a constaté), sans jugement sur les personnes.',
              'Rattachez le **risque** et le **dispositif de maîtrise** concernés, si vous les connaissez déjà ; sinon l’incident reste « à qualifier » (le risque sera exigé avant la résolution).',
              'Choisissez la **gravité** et estimez l’impact (financier, client, réglementaire, image).',
              'Enregistrez : le responsable est notifié, l’incident est suivi jusqu’à sa clôture.'],
      notes=['La gravité réduit automatiquement l’efficacité du dispositif concerné.',
             'Un incident grave crée une notification urgente.',
             'Fraude, corruption ou harcèlement signalés de façon confidentielle : utilisez plutôt le **dispositif d’alerte**.'],
      mots=['incident', 'incidents', 'declarer', 'signaler', 'nouveau', 'creer', 'perte', 'sinistre', 'panne', 'dysfonctionnement', 'evenement'],
      liens=[('Incidents', 'liste_incidents')],
      perms=['can_manage_incidents', 'can_view_incidents'],
      questions=['signaler un incident', 'j ai une perte a declarer']),

    A('incident_suivi', 'maitrise', 'Suivre et clôturer un incident (statuts, délais, escalade)',
      'Statuts : ouvert → en cours → (en attente d’approbation) → résolu → fermé. Chaque incident a un délai ; '
      'sans avancement il est escaladé sur 3 niveaux.',
      etapes=['Le responsable passe l’incident **en cours** et documente l’analyse des causes.',
              'Il propose la résolution ; si une approbation est requise, l’incident passe **en attente d’approbation**.',
              'Après approbation : **résolu**, puis **fermé** une fois les actions correctives terminées.',
              'Délai dépassé : l’incident est marqué et le responsable, le superviseur et les gestionnaires sont prévenus ; escalade automatique au niveau 2 (superviseur) puis 3 (direction) selon les délais de l’incident.',
              'L’approbation de la résolution revient au superviseur, au directeur ou à un gestionnaire, jamais au responsable qui a résolu.'],
      notes=['Créez un plan d’action depuis l’incident pour éviter qu’il se reproduise.'],
      mots=['incident', 'incidents', 'statut', 'suivi', 'suivre', 'cloturer', 'fermer', 'resoudre', 'resolu', 'escalade', 'delai', 'sla', 'approbation', 'approuver', 'traite', 'longtemps', 'attente', 'relance'],
      liens=[('Incidents', 'liste_incidents')],
      perms=['can_manage_incidents']),

    # ==================================================================
    # PROCESSUS, CAMPAGNES, C2N
    # ==================================================================
    A('logigramme', 'controle', 'Dessiner un processus (logigramme)',
      'Logigrammes → Nouveau logigramme : ajoutez étapes, décisions, acteurs, risques et contrôles, reliés par des flèches.',
      etapes=['Menu **Logigrammes** → **Nouveau logigramme**.',
              'Glissez les formes : début / fin, étape, décision, document, contrôle.',
              'Reliez-les par des flèches ; indiquez l’acteur de chaque étape.',
              'Rattachez les **risques** et **contrôles** aux étapes concernées.',
              'Enregistrez ; exportez en image / HTML pour vos procédures.'],
      mots=['logigramme', 'logigrammes', 'processus', 'procedure', 'schema', 'flux', 'diagramme', 'dessiner', 'workflow', 'bpmn', 'etape', 'etapes'],
      liens=[('Logigrammes', 'liste_logigrammes'), ('Nouveau logigramme', 'nouveau_logigramme')],
      perms=['can_manage_logigram']),

    A('processus_controles', 'controle', 'Rattacher des contrôles à un processus et à ses étapes',
      'Depuis la fiche du processus, ajoutez les contrôles clés en précisant l’étape concernée ; ils apparaissent '
      'sur l’organigramme du processus et peuvent être testés en campagne.',
      mots=['processus', 'controle', 'controles', 'etape', 'rattacher', 'lier', 'organigramme', 'acteurs'],
      liens=[('Processus métier', 'liste_processus_metier')],
      perms=['can_manage_logigram']),

    A('campagne', 'controle', 'Mener une campagne de contrôle (et la faire valider)',
      'Une campagne teste un contrôle sur un échantillon de dossiers. Elle suit le même circuit que le contrôle '
      'interne N2 : saisie → soumission → une seule décision du validateur → non-conformités créées à la validation.',
      etapes=['Menu **Campagnes de contrôle** → **Nouvelle campagne** (ou depuis une planification N2 : la campagne en reprend le contrôleur et le validateur).',
              'L\u2019opérateur démarre la campagne et saisit les volumes : dossiers contrôlés, conformes, anomalies (un motif et une criticité par anomalie).',
              '**Soumettre** : l\u2019exécution N2 reçoit les chiffres à jour, la planification passe « soumise », le validateur est prévenu.',
              'Le validateur décide **une seule fois**, depuis la page de la campagne (encadré « Validation ») ou depuis **À valider** du N2 : la décision vaut pour les deux.',
              '**Validée** : chaque anomalie retenue devient une non-conformité N2. **Rejetée** : aucune non-conformité ; l\u2019opérateur corrige puis resoumet.'],
      notes=['Validateur : celui de la campagne, à défaut celui de la planification N2, à défaut les gestionnaires des campagnes.',
             'Personne ne valide une campagne qu\u2019il a réalisée ou soumise, ni le contrôleur de la planification.',
             'Réouverture après validation : gestionnaires seulement ; 3 réouvertures au maximum, comptées avec la planification N2. Retirer une soumission n\u2019en est pas une.',
             'Les campagnes à valider apparaissent dans « Ma semaine » et en tête de « À valider » du N2.'],
      mots=['campagne', 'campagnes', 'controle', 'test', 'tests', 'echantillon', 'dossiers', 'conformite', 'taux', 'anomalie', 'anomalies', 'terrain', 'valider', 'validation', 'soumettre', 'rejeter', 'operateur', 'valideur'],
      liens=[('Campagnes de contrôle', 'liste_campagnes_controle'), ('À valider', 'c2n_a_valider')],
      perms=['can_manage_campaigns', 'can_view_campaigns'],
      questions=['comment valider une campagne', 'qui valide la campagne', 'ma campagne est bloquee en attente de validation']),

    A('registre_recommandations', 'audit', 'Suivre toutes les recommandations (audit, N2, commissaire aux comptes, régulateur)',
      'Le registre rassemble en un seul tableau les recommandations d\u2019audit interne, du contrôle interne N2 et celles venues '
      'de l\u2019extérieur (commissaire aux comptes, régulateur, inspection, auditeur externe), avec les chiffres attendus par le comité d\u2019audit.',
      etapes=['Menu **Audit interne → Registre des recommandations**.',
              'Pour une recommandation externe : **Recommandation externe**, choisissez l\u2019origine, l\u2019échéance et le responsable.',
              'Le responsable la retrouve dans **Mes recommandations** (et dans « Ma semaine ») : il déclare l\u2019avancement avec un commentaire et une preuve.',
              'À 100 %, il **demande la clôture** (une preuve est exigée).',
              'Un gestionnaire, qui n\u2019est ni le responsable ni l\u2019auteur de la demande, **valide** ou **refuse en expliquant pourquoi**.'],
      notes=['Indicateurs : taux de mise en œuvre, recommandations échues, ancienneté moyenne, ouvertes depuis plus de 6 mois, répartition par origine.',
             'Les opérateurs ont aussi « Mes recommandations » dans leur espace.',
             'Preuves acceptées : PDF, images, Office, texte, ZIP (15 Mo au maximum).'],
      mots=['recommandation', 'recommandations', 'registre', 'suivi', 'cac', 'commissaire', 'regulateur', 'inspection', 'cloture', 'preuve', 'taux', 'mise', 'oeuvre'],
      liens=[('Registre des recommandations', 'recommandations.registre'), ('Mes recommandations', 'recommandations.miennes')],
      questions=['comment suivre les recommandations du commissaire aux comptes', 'comment cloturer une recommandation',
                 'qui valide la cloture d une recommandation']),

    A('rapport_provisoire', 'audit', 'Rapport provisoire, réponses de l\u2019audité et rapport définitif',
      'Depuis la fiche d\u2019un audit (encadré « Rapport et équipe »), le rapport passe de provisoire à définitif ; entre les deux, '
      'l\u2019audité répond à chaque constat.',
      etapes=['Chaque membre de l\u2019équipe signe sa **déclaration d\u2019indépendance** (obligatoire avant le rapport provisoire).',
              'Complétez les constats en **5C** : constat, critère, cause, conséquence (la recommandation est liée au constat).',
              '**Émettre le rapport provisoire** : les audités (participants et responsables des recommandations) sont prévenus, avec une date limite (15 jours par défaut).',
              'L\u2019audité répond : d\u2019accord, accord partiel ou désaccord ; en cas d\u2019accord, il décrit son plan et sa date d\u2019engagement.',
              '**Émettre le rapport définitif** quand tout le monde a répondu ou après la date limite. Tout est alors figé.'],
      notes=['Le temps passé se saisit par auditeur et par activité (bouton « Temps ») et se compare au budget de la mission.',
             'Programme d\u2019audit : seul un programme en élaboration s\u2019approuve ; si son auteur l\u2019approuve lui-même, c\u2019est noté « auto-approbation » dans le journal du programme ; la désapprobation exige un motif.'],
      mots=['rapport', 'provisoire', 'definitif', 'reponse', 'audite', 'constat', 'critere', 'consequence', 'independance', 'conflit', 'temps', 'heures'],
      perms=['can_manage_audit'],
      questions=['comment emettre le rapport provisoire', 'comment l audite repond', 'declaration d independance']),

    A('kri_fiabilite', 'risques', 'KRI : mesures en retard, seuils et alertes',
      'Un KRI n\u2019est utile que s\u2019il est mesuré à temps et si ses seuils sont cohérents.',
      etapes=['La fréquence du KRI fixe la date de la prochaine mesure : au-delà (avec une marge), le KRI est « mesure en retard » (liste des KRI, Ma semaine, tableau de bord stratégique).',
              'Seuils : si le risque monte avec la valeur, le seuil d\u2019alerte doit être sous le seuil critique (l\u2019inverse sinon) ; une incohérence est refusée.',
              'Changer un seuil ne réécrit pas le passé : chaque ancienne mesure garde la couleur des seuils de son époque.',
              'Une mesure au seuil critique prévient les gestionnaires des risques ; le tableau stratégique signale « risque à réévaluer » si le risque lié est coté Faible ou Moyen.'],
      mots=['kri', 'indicateur', 'seuil', 'seuils', 'retard', 'mesure', 'frequence', 'alerte', 'critique'],
      perms=['can_manage_kri'],
      questions=['pourquoi mon kri est en retard', 'seuils incoherents kri', 'mon kri est critique que faire']),

    A('logigramme_validation', 'controle', 'Logigrammes : couloirs, vérification, validation et versions',
      'Un logigramme décrit une procédure. Il se dessine dans l\u2019éditeur, se vérifie, se fait valider, puis se revoit chaque année.',
      etapes=['Dans **Versions, validation, couloirs** (bouton au-dessus de l\u2019éditeur), saisissez les **acteurs** (un par ligne) : '
              'des couloirs apparaissent ; placez chaque étape dans le couloir de celui qui la réalise.',
              'Utilisez **Décision** (losange) pour une question ; reliez ses sorties et nommez-les (Oui / Non).',
              'Cliquez **Vérifier le dessin** : début et fin présents, aucune étape isolée, décision à deux sorties au moins… '
              'Les étapes en cause sont entourées.',
              '**Soumettre à validation**, puis un gestionnaire des logigrammes **valide** (version n, copie figée) ou **renvoie en brouillon** avec un motif.',
              'Chaque année, le propriétaire **confirme la revue** si rien n\u2019a changé ; sinon il modifie et refait valider.'],
      notes=['Modifier un logigramme validé le repasse en brouillon : la version validée reste la version en vigueur jusqu\u2019à la suivante.',
             'Chaque version validée se consulte et s\u2019imprime (dessin, acteurs, risques et contrôles par étape).',
             'Un ancien « Processus » (étapes) se convertit en logigramme depuis sa fiche, une seule fois.'],
      mots=['logigramme', 'procedure', 'processus', 'couloir', 'acteur', 'decision', 'losange', 'version', 'validation', 'revue', 'verifier'],
      liens=[('Logigrammes', 'liste_logigrammes')], perms=['can_manage_logigram'],
      questions=['comment valider un logigramme', 'comment ajouter des couloirs', 'comment verifier mon logigramme']),

    A('permissions_modules', 'admin', 'Permissions des utilisateurs et modules de l\u2019organisation',
      'Ce que voit un utilisateur dépend de deux choses : les modules souscrits par l\u2019organisation et ses permissions.',
      etapes=['Administration → Utilisateurs → **Permissions** d\u2019un utilisateur : une section par module.',
              'Un module **non souscrit** apparaît grisé avec « Module non souscrit » : ses permissions ne peuvent pas être données.',
              'Cocher « gérer » donne aussi « voir » (campagnes, N2, incidents, PCA, registre des recommandations…).',
              'Ce qui n\u2019est pas disponible disparaît partout : menus, boutons, liens et blocs des pages, y compris l\u2019IA quand elle est coupée.'],
      notes=['Quand votre fournisseur active un nouveau module, donnez ensuite ses permissions aux utilisateurs concernés.',
             'Une personne à qui l\u2019on confie un élément précis (un plan d\u2019action, une recommandation) y accède même sans la permission du module.'],
      mots=['permission', 'permissions', 'module', 'modules', 'grise', 'souscrit', 'abonnement', 'voir', 'masque', 'invisible', 'ia'],
      liens=[('Utilisateurs', 'client_admin_utilisateurs')],
      questions=['pourquoi une permission est grisee', 'pourquoi je ne vois pas un module', 'comment donner une permission']),

    A('valideur_operateurs', 'risques', 'Faire valider les évaluations des opérateurs par une personne désignée',
      'Par défaut, un opérateur pré-évalue puis valide lui-même son évaluation, et l\u2019administrateur la confirme. '
      'Vous pouvez désigner un valideur.',
      etapes=['**Cartographies → Valideurs des opérateurs**, ou la page d\u2019une cartographie (aussi : page admin des opérateurs, Paramètres → Risques) : choisissez le valideur, enregistrez. '
              'Admin, super admin et gestionnaires des risques peuvent le faire.',
              'Le valideur peut être un opérateur (il valide depuis son espace opérationnel, « Évaluations à valider ») ou un cadre.',
              'Vous pouvez choisir un valideur par cartographie (aussi depuis la page de la cartographie) ; le valideur de l\u2019organisation sert pour les cartographies qui n\u2019en ont pas.',
              'L\u2019opérateur fait la pré-évaluation : le valideur reçoit une notification.',
              'Le valideur ouvre l\u2019évaluation et fait la phase 2 : valider, ou renvoyer à revoir avec un commentaire (l\u2019opérateur est prévenu).',
              'L\u2019administrateur confirme comme d\u2019habitude.'],
      notes=['Laisser le champ vide rétablit le fonctionnement habituel.'],
      mots=['valideur', 'operateur', 'evaluation', 'valider', 'phase', 'pre-evaluation', 'parametres'],
      liens=[('Valideur des opérateurs', 'parametres_risque.valideur_page')], perms=[],
      questions=['qui valide les evaluations des operateurs', 'designer un valideur']),

    A('c2n_principe', 'controle', 'Contrôle interne de niveau 2 (C2N) : le principe',
      'Le C2N organise les contrôles faits par une fonction indépendante : référentiel des contrôles → planification → '
      'exécution → validation → non-conformités → recommandations et plans d’action.',
      etapes=['**Référentiel** : liste des points de contrôle (objectif, méthode, fréquence).',
              '**Planification** : qui contrôle quoi, quand.',
              '**Exécution** : volume contrôlé, conformes, anomalies, preuves.',
              '**Validation** par un validateur (jamais par le contrôleur lui-même).',
              '**Non-conformités** et **plans d’action** jusqu’à correction.'],
      mots=['c2n', 'n2', 'niveau', 'second', 'deuxieme', 'controle', 'interne', 'permanent', 'referentiel'],
      liens=[('Tableau de bord C2N', 'c2n_dashboard'), ('Référentiel', 'c2n_liste_referentiel')],
      perms=['can_view_controle_interne_n2', 'can_manage_controle_interne_n2']),

    A('c2n_planification', 'controle', 'C2N : exécuter, soumettre et valider une planification',
      'À faire → en cours → soumis → validé ou rejeté. Une planification validée ou rejetée peut être rouverte 3 fois au maximum.',
      etapes=['Le contrôleur assigné **démarre** la planification (à faire → en cours).',
              'Il saisit l’exécution : volume contrôlé, conformes, anomalies, commentaires, pièces.',
              'Il **soumet** ; la planification apparaît dans **À valider** pour les validateurs.',
              'Le validateur **valide** ou **rejette** avec un motif.',
              'Les anomalies deviennent des **non-conformités** à traiter.'],
      mots=['planification', 'planifications', 'executer', 'execution', 'soumettre', 'valider', 'rejeter', 'rouvrir', 'c2n', 'n2', 'valider'],
      liens=[('Planifications', 'c2n_liste_planifications'), ('À valider', 'c2n_a_valider')],
      perms=['can_view_controle_interne_n2', 'can_manage_controle_interne_n2']),

    A('c2n_nc', 'controle', 'Traiter une non-conformité',
      'Ouvrez la non-conformité, analysez la cause, rattachez une recommandation et un plan d’action, puis clôturez une fois corrigée.',
      mots=['non', 'conformite', 'conformites', 'nc', 'ecart', 'traiter', 'corriger', 'cloturer'],
      liens=[('Non-conformités', 'c2n_liste_non_conformites'), ('Recommandations', 'c2n_recommandations_central')],
      perms=['can_view_controle_interne_n2', 'can_manage_controle_interne_n2']),

    A('questionnaires', 'controle', 'Questionnaires d’autoévaluation',
      'Créez un questionnaire (catégories et questions), partagez-le, puis suivez et analysez les réponses.',
      etapes=['Menu **Questionnaires** → **Nouveau questionnaire** (ou **Importer**).',
              'Créez des catégories, puis des questions : texte, choix unique / multiple, échelle, oui / non…',
              'Fixez les dates d’ouverture et de fermeture, et la visibilité (public ou réservé à l’organisation).',
              'Partagez le lien ; suivez le taux de réponse et exportez les résultats.'],
      notes=['Un questionnaire fermé, hors dates ou désactivé n’accepte plus de réponses.'],
      mots=['questionnaire', 'questionnaires', 'enquete', 'sondage', 'autoevaluation', 'auto', 'evaluation', 'formulaire', 'questions', 'reponses', 'csa'],
      liens=[('Questionnaires', 'liste_questionnaires'), ('Nouveau questionnaire', 'nouveau_questionnaire')],
      perms=['can_manage_questionnaires', 'can_create_questionnaires']),

    # ==================================================================
    # AUDIT
    # ==================================================================
    A('programme_audit', 'audit', 'Construire le programme d’audit',
      'Programme d’audit → Créer un programme : période (annuelle ou pluriannuelle), missions prévues, priorités fondées sur les risques.',
      etapes=['Menu **Programme d’audit** → **Créer un programme**.',
              'Ajoutez les missions prévues : thème, entité auditée, trimestre, charge estimée.',
              'Priorisez selon la cartographie des risques (les risques critiques d’abord).',
              'Faites approuver le programme ; chaque mission se lance ensuite depuis le programme.'],
      mots=['programme', 'plan', 'annuel', 'pluriannuel', 'audit', 'audits', 'planning', 'planifier', 'missions'],
      liens=[('Programme d’audit', 'liste_programmes_audit')],
      perms=['can_manage_audit_program']),

    A('audit_lancer', 'audit', 'Lancer une mission d’audit',
      'Mission d’audit → Nouvel audit : titre, type, périmètre, objectifs, dates, chef de mission et équipe.',
      etapes=['Menu **Mission d’audit** → **Nouvel audit**.',
              'Titre, type (conformité, opérationnel, financier, SI…), entité auditée, objectifs et périmètre.',
              'Dates prévues, chef de mission et **équipe d’audit** (les membres de l’équipe peuvent travailler sur la mission).',
              'Préparez la lettre de mission et le programme de travail.',
              'Pendant la mission : feuilles de travail, constatations, recommandations.'],
      mots=['audit', 'audits', 'mission', 'missions', 'lancer', 'creer', 'nouveau', 'nouvel', 'demarrer', 'equipe', 'lettre'],
      liens=[('Nouvel audit', 'nouvel_audit'), ('Missions', 'liste_audits')],
      perms=['can_manage_audit']),

    A('constatation', 'audit', 'Saisir une constatation et ses recommandations',
      'Dans la mission → onglet Constatations → Ajouter : fait constaté, critère, cause, conséquence, gravité ; '
      'puis une ou plusieurs recommandations avec responsable et échéance.',
      etapes=['Ouvrez la mission → **Constatations** → **Ajouter**.',
              'Décrivez : **fait** (ce qui a été observé), **critère** (la règle attendue), **cause**, **conséquence**, **gravité**.',
              'Ajoutez les **recommandations** : action attendue, responsable audité, échéance.',
              'L’audité répond (accord, plan d’action proposé) ; le suivi se fait dans les plans d’action.'],
      mots=['constatation', 'constatations', 'constat', 'constats', 'observation', 'finding', 'ecart', 'recommandation', 'recommandations', 'reco'],
      liens=[('Missions', 'liste_audits')],
      perms=['can_manage_audit']),

    A('rapport_audit', 'audit', 'Valider et diffuser le rapport d’audit',
      'Circuit : brouillon → en relecture → approuvé (niveau 1) → validé (niveau 2). Le rapport validé est exportable et signable.',
      etapes=['Le chef de mission envoie le rapport **en relecture**.',
              'Le relecteur l’**approuve** (niveau 1) ou le renvoie avec commentaires.',
              'Le directeur de l’audit le **valide** (niveau 2).',
              'Exportez-le (PDF) et, si besoin, faites-le **signer** électroniquement.'],
      mots=['rapport', 'rapports', 'valider', 'validation', 'relecture', 'diffuser', 'pdf', 'final', 'approuver', 'audit'],
      liens=[('Rapports d’audit', 'rapports_audit')],
      perms=['can_manage_audit', 'can_view_reports']),

    A('audit_tableau', 'audit', 'Suivre l’activité d’audit (tableau de bord global)',
      'Le tableau de bord global de l’audit montre l’avancement du programme, les missions en cours, les '
      'constatations par gravité et le taux de mise en œuvre des recommandations.',
      mots=['tableau', 'bord', 'dashboard', 'audit', 'avancement', 'suivi', 'taux', 'recommandations', 'global'],
      liens=[('Tableau de bord audit', 'dashboard_audit_global_complet')],
      perms=['can_manage_audit']),

    # ==================================================================
    # PLANS D'ACTION
    # ==================================================================
    A('plan_creer', 'plans', 'Créer un plan d’action',
      'Un plan d’action se crée depuis l’élément qui le justifie (recommandation d’audit, risque, incident, '
      'non-conformité) ou depuis la liste des plans d’action.',
      etapes=['Depuis la recommandation / le risque / l’incident → **Créer un plan d’action** (le lien est fait automatiquement).',
              'Titre, objectif, responsable, date de début et échéance, priorité.',
              'Découpez-le en **sous-actions** avec leur propre responsable et échéance.'],
      mots=['plan', 'plans', 'action', 'actions', 'creer', 'nouveau', 'ajouter', 'corrective', 'correctif', 'correctives', 'remediation'],
      liens=[('Plans d’action', 'liste_plans_action')],
      perms=['can_manage_action_plans']),

    A('plan_suivi', 'plans', 'Mettre à jour l’avancement d’un plan d’action',
      'Ouvrez le plan et mettez à jour chaque sous-action (avancement, commentaire, preuve). L’avancement global '
      'se calcule à partir des sous-actions ; à 100 % le plan passe « terminé ».',
      notes=['Le responsable d’un plan ou d’une sous-action peut le mettre à jour même sans permission de gestion générale.',
             'Les plans en retard apparaissent en rouge, dans « Ma semaine » et font l’objet de relances.'],
      mots=['avancement', 'suivi', 'suivre', 'mettre', 'jour', 'progression', 'pourcentage', 'terminer', 'cloturer', 'sous', 'action', 'actions', 'plan', 'plans', 'preuve'],
      liens=[('Plans d’action', 'liste_plans_action')]),

    A('plan_retard', 'plans', 'Un plan d’action est en retard : que faire ?',
      'Mettez à jour l’avancement, expliquez le retard en commentaire, et demandez si besoin un report d’échéance '
      'motivé à la personne qui suit le plan.',
      mots=['retard', 'retards', 'depasse', 'echeance', 'report', 'reporter', 'decaler', 'plan', 'action'],
      liens=[('Plans d’action', 'liste_plans_action')],
      questions=['quels plans sont en retard', 'reporter une echeance']),

    # ==================================================================
    # CONFORMITÉ
    # ==================================================================
    A('veille', 'conformite', 'Suivre un texte réglementaire (veille)',
      'Veille réglementaire → Nouvelle veille : référence du texte, dates de publication et d’application, impact, '
      'risques concernés, actions de conformité.',
      etapes=['Menu **Veille réglementaire** → **Nouvelle veille**.',
              'Référence et intitulé du texte, autorité émettrice, date de publication, date d’entrée en application.',
              'Analyse d’impact : quelles activités, quels processus, quels risques.',
              'Circuit : brouillon → en relecture → approuvée (niveau 1) → en vigueur (niveau 2).',
              'Créez les actions de conformité et suivez-les jusqu’à l’échéance.'],
      mots=['veille', 'reglementaire', 'reglementation', 'loi', 'lois', 'decret', 'texte', 'textes', 'circulaire', 'instruction', 'bceao', 'cobac', 'uemoa', 'cemac', 'regulateur', 'conformite'],
      liens=[('Veille réglementaire', 'veille_reglementaire'), ('Nouvelle veille', 'nouvelle_veille')],
      perms=['can_manage_regulatory', 'can_view_veille']),

    A('tiers_creer', 'conformite', 'Enregistrer un tiers et calculer son niveau de vigilance LCB-FT',
      'Conformité → Tiers → Nouveau tiers : identification, pays, PPE, secteur, bénéficiaires effectifs, canal, montant. '
      'Le score LCB-FT (0 à 100) et le niveau de vigilance sont calculés immédiatement.',
      etapes=['Menu **Tiers et LCB-FT** → **Nouveau tiers**.',
              'Type (client, fournisseur, partenaire…), identité, pays de résidence et de nationalité.',
              'Cochez **PPE** (personne politiquement exposée) si c’est le cas ; renseignez secteur, canal (à distance ou non), montant de la relation, bénéficiaires effectifs.',
              'Enregistrez : le score et les facteurs qui l’expliquent sont affichés.',
              'Niveaux : moins de 30 **simplifiée** (revue 36 mois) · moins de 60 **standard** (24 mois) · 60 et plus **renforcée** (12 mois).'],
      notes=['Les pays des listes du GAFI (juin 2026) et les secteurs sensibles comptent dans le score ; vos listes se modifient dans Paramètres → Risques.',
             'Une correspondance confirmée sur une liste de sanctions place le tiers en **refus**.'],
      mots=['tiers', 'kyc', 'client', 'fournisseur', 'partenaire', 'lcb', 'ft', 'lcbft', 'blanchiment', 'terrorisme', 'vigilance', 'ppe', 'beneficiaire', 'effectif', 'score', 'connaissance'],
      liens=[('Tiers', 'tiers.liste')],
      perms=['can_manage_tiers', 'can_view_tiers'],
      questions=['niveau de vigilance', 'lutte contre le blanchiment']),

    A('tiers_criblage', 'conformite', 'Cribler un tiers contre les listes de sanctions',
      'Sur la fiche du tiers → Cribler. Les correspondances proches (noms similaires) sont proposées ; un humain '
      'confirme ou écarte chacune, avec trace.',
      etapes=['Ouvrez le tiers → **Cribler**.',
              'Examinez chaque correspondance (nom, date de naissance, pays, liste source).',
              '**Écarter** si c’est un homonyme, **confirmer** si c’est la même personne (le tiers passe en refus).',
              'Les listes (ONU, UE, OFAC, liste nationale…) sont importées par le super administrateur ; la date de mise à jour est affichée.'],
      mots=['criblage', 'cribler', 'sanction', 'sanctions', 'liste', 'listes', 'onu', 'ofac', 'gel', 'avoirs', 'homonyme', 'correspondance', 'filtrage', 'screening'],
      liens=[('Tiers', 'tiers.liste')],
      perms=['can_manage_tiers']),

    A('fournisseur', 'conformite', 'Évaluer un fournisseur (criticité)',
      'Sur la fiche d’un tiers fournisseur : impact d’un arrêt, dépendance, substituabilité et note d’évaluation '
      'donnent sa criticité ; l’historique des revues est conservé.',
      mots=['fournisseur', 'fournisseurs', 'prestataire', 'sous', 'traitant', 'externalisation', 'criticite', 'evaluation', 'dependance'],
      liens=[('Tiers', 'tiers.liste')],
      perms=['can_manage_tiers']),

    A('alerte_deposer', 'conformite', 'Déposer un signalement (dispositif d’alerte)',
      'Le dispositif d’alerte permet à toute personne de signaler, de façon confidentielle ou anonyme, une fraude, '
      'de la corruption, du harcèlement ou une autre atteinte grave. Le lien public est fourni par votre organisation.',
      etapes=['Ouvrez le lien de signalement communiqué par votre organisation (il se termine par /alerte/ suivi de sa référence).',
              'Décrivez les faits ; restez anonyme si vous le souhaitez.',
              'Choisissez un mot de passe : avec le **code de suivi** affiché à la fin, il vous permet de suivre le dossier et d’échanger avec le référent sans révéler votre identité.',
              'Conservez précieusement le code de suivi : il n’est affiché qu’une fois.'],
      notes=['Le contenu est chiffré ; aucun e-mail ne contient le signalement ; le super administrateur de la plateforme n’y a pas accès.',
             'Délais : accusé de réception sous 7 jours, retour d’information sous 3 mois.'],
      mots=['alerte', 'signalement', 'signaler', 'lanceur', 'whistleblowing', 'ethique', 'anonyme', 'fraude', 'corruption', 'harcelement', 'sapin', 'confidentiel', 'denoncer', 'suivi', 'dossier', 'code'],
      pour='public',
      questions=['faire un signalement anonyme', 'lancer une alerte', 'comment le lanceur d alerte suit son dossier']),

    A('alerte_traiter', 'conformite', 'Traiter les signalements (référent alerte)',
      'Conformité → Dispositif d’alerte : accusez réception, instruisez, échangez avec le lanceur d’alerte, clôturez.',
      etapes=['Menu **Dispositif d’alerte** : les dossiers et leurs délais s’affichent.',
              '**Accusez réception** sous 7 jours.',
              'Instruisez et échangez avec le lanceur d’alerte par messages (il les lit avec son code de suivi).',
              'Donnez un retour d’information sous 3 mois, puis **clôturez** avec la décision.'],
      notes=['Seuls les référents (permission « gérer les alertes ») voient les dossiers.',
             'Le lien public à communiquer à vos équipes est affiché en haut de la page.'],
      mots=['alerte', 'alertes', 'signalement', 'signalements', 'referent', 'traiter', 'instruire', 'cloturer', 'lien', 'public'],
      liens=[('Dispositif d’alerte', 'alertes.liste')],
      perms=['can_manage_alertes'], pour='admin',
      questions=['qui voit les signalements', 'qui traite les alertes']),

    A('signature', 'conformite', 'Signer électroniquement un document',
      'Sur un rapport ou document compatible → Signer : un code à usage unique est envoyé par e-mail (ou le mot de passe '
      'est redemandé), puis la signature est enregistrée avec l’empreinte du document.',
      etapes=['Ouvrez le document → **Signature** → **Recevoir un code**.',
              'Saisissez le code reçu par e-mail et votre qualité (ex. Directeur de l’audit).',
              'La signature enregistre qui, quand, depuis quelle adresse IP, et l’empreinte SHA-256 du document.',
              'Toute modification ultérieure du document est détectée et signalée sur la page.'],
      notes=['C’est une preuve d’approbation interne, pas une signature « qualifiée » eIDAS.',
             'Permission requise : « signer des documents ».'],
      mots=['signature', 'signer', 'signe', 'electronique', 'approbation', 'parapheur', 'valider', 'document', 'empreinte'],
      perms=['can_sign_documents']),

    # ==================================================================
    # CONTINUITÉ, QUALITÉ
    # ==================================================================
    A('pca_creer', 'continuite', 'Créer un plan de continuité d’activité (PCA)',
      'Plans de continuité → Créer un plan PCA : activités critiques, BIA (RTO / RPO), stratégies de secours, cellule de crise, contacts.',
      etapes=['Menu **Plans de continuité (PCA)** → **Créer un plan PCA**.',
              'Listez les **activités critiques** et faites le **BIA** : durée d’arrêt acceptable (RTO), perte de données acceptable (RPO).',
              'Décrivez les **stratégies de continuité** (site de repli, télétravail, fournisseurs alternatifs…).',
              'Composez la **cellule de crise** et l’annuaire d’urgence.',
              'Faites valider le plan, puis planifiez des **exercices**.'],
      mots=['pca', 'bcp', 'continuite', 'activite', 'crise', 'secours', 'repli', 'bia', 'rto', 'rpo', 'reprise', 'pra', 'sinistre', 'cellule'],
      liens=[('Plans de continuité', 'liste_plans_pca')],
      perms=['can_manage_bcp', 'can_view_bcp']),

    A('pca_exercice', 'continuite', 'Tester un PCA (exercices)',
      'Depuis le plan : ajoutez un exercice (type, scénario, date), puis enregistrez les résultats, les écarts et les actions d’amélioration.',
      notes=['Le niveau de maturité du plan (1 à 5) s’affiche sur la liste des plans.'],
      mots=['exercice', 'exercices', 'test', 'tester', 'simulation', 'scenario', 'pca', 'maturite'],
      liens=[('Plans de continuité', 'liste_plans_pca')],
      perms=['can_manage_bcp']),

    A('qualite', 'continuite', 'Plans qualité et actions d’amélioration',
      'Plans Qualité → Créer un plan : objectifs, indicateurs, actions d’amélioration et audits qualité ; suivi des brouillons, plans actifs et archivés.',
      mots=['qualite', 'iso', '9001', 'amelioration', 'continue', 'plan', 'objectifs', 'pdca'],
      liens=[('Plans qualité', 'liste_plans_qualite')],
      perms=['can_manage_quality']),

    # ==================================================================
    # PILOTAGE
    # ==================================================================
    A('dashboard', 'pilotage', 'Tableau de bord',
      'Vue d’ensemble de vos modules : risques par niveau, KRI en alerte, incidents ouverts, plans d’action en retard, audits en cours.',
      mots=['tableau', 'bord', 'dashboard', 'accueil', 'synthese', 'vue', 'ensemble', 'chiffres'],
      liens=[('Tableau de bord', 'dashboard')]),

    A('dashboard_strategique', 'pilotage', 'Tableau de bord stratégique (direction)',
      'Vue consolidée pour la direction : évolution des risques sur 12 mois, comparaison à 90 jours, risques hors appétence, '
      'priorités ; filtres par pays, pôle, direction.',
      mots=['strategique', 'direction', 'comite', 'consolide', 'evolution', 'tendance', 'tableau', 'bord', 'dg'],
      liens=[('Tableau de bord stratégique', 'tableau_de_bord_strategique')],
      perms=['can_view_tableau_bord_strategique']),

    A('rapport_comite', 'pilotage', 'Préparer le rapport au comité d’audit / des risques',
      'Le rapport au comité est généré automatiquement : synthèse rédigée, risques majeurs et hors appétence, incidents, '
      'KRI, audits, plans d’action, décisions attendues. Il s’imprime en PDF A4.',
      etapes=['Menu **Rapport au comité** (s’ouvre dans un nouvel onglet).',
              'Choisissez la période.',
              'Relisez la synthèse et les décisions proposées.',
              'Imprimez ou enregistrez en PDF (Ctrl P → « Enregistrer au format PDF »).'],
      mots=['rapport', 'comite', 'audit', 'risques', 'conseil', 'administration', 'reporting', 'pdf', 'imprimer', 'synthese', 'direction', 'gouvernance'],
      liens=[('Rapport au comité', 'rapport_comite.page')],
      perms=['can_view_rapport_comite']),

    A('export', 'pilotage', 'Exporter mes données (Excel, CSV, PDF)',
      'Les listes ont un bouton d’export ; l’export complet des données de l’organisation se fait dans '
      'Paramètres → Export des données (administrateur, permission d’export).',
      notes=['Chaque export complet est journalisé.', 'Les rapports (audit, comité) s’impriment en PDF depuis le navigateur.'],
      mots=['export', 'exporter', 'excel', 'csv', 'pdf', 'telecharger', 'extraction', 'extraire', 'sauvegarde', 'donnees', 'imprimer'],
      liens=[('Export des données', 'export_donnees.page')],
      perms=['can_export_data']),

    A('imprimer', 'pilotage', 'Imprimer une page ou l’enregistrer en PDF',
      'Utilisez Ctrl P (Cmd P sur Mac) puis « Enregistrer au format PDF ». Les rapports ont une mise en page A4 prévue pour l’impression.',
      mots=['imprimer', 'impression', 'pdf', 'papier', 'a4', 'page'],
      questions=['comment imprimer', 'imprimer en pdf', 'enregistrer une page en pdf']),

    # ==================================================================
    # IA
    # ==================================================================
    A('ia_fonctions', 'ia', 'Que fait l’intelligence artificielle dans Egalyx ?',
      'Quand elle est active, l’IA propose des analyses rédigées (cartographie, KRI, incidents, veille, qualité), '
      'des suggestions de plans d’action et de constatations. Ses propositions sont toujours à relire et valider par un humain.',
      notes=['L’IA peut être désactivée pour toute la plateforme, pour une organisation (module) ou pour une personne (permission « utiliser l’analyse IA »).',
             'IA désactivée : boutons et liens d’IA disparaissent, le reste de l’outil fonctionne normalement, et l’assistant continue de répondre à partir de ce guide et de vos données.'],
      mots=['ia', 'intelligence', 'artificielle', 'ai', 'gpt', 'chatgpt', 'analyse', 'suggestion', 'automatique', 'robot'],
      questions=['a quoi sert l ia', 'pourquoi je ne vois pas les boutons ia']),

    A('ia_absente', 'ia', 'Je ne vois pas les boutons d’IA',
      'L’IA est désactivée soit pour toute la plateforme, soit pour votre organisation, soit pour votre compte. '
      'Demandez à votre administrateur la permission « Utiliser l’analyse IA » ; si le module n’est pas activé, il '
      'doit être activé par le super administrateur.',
      mots=['ia', 'bouton', 'boutons', 'disparu', 'disparus', 'absent', 'voir', 'analyse', 'desactive', 'desactivee', 'manquant'],
      questions=['les boutons ia ont disparu']),

    # ==================================================================
    # ABONNEMENT, API
    # ==================================================================
    A('abonnement', 'abonnement', 'Mon abonnement : formule, échéance, renouvellement',
      'La page Abonnement affiche la formule, les modules inclus, le nombre d’utilisateurs et la date de fin.',
      mots=['abonnement', 'formule', 'licence', 'licences', 'offre', 'renouveler', 'renouvellement', 'echeance', 'expiration', 'expire', 'tarif', 'prix', 'facture', 'proforma', 'combien', 'nombre', 'limite', 'utilisateurs'],
      liens=[('Abonnement', 'paiement.abonnement')],
      pour='admin'),

    A('paiement', 'abonnement', 'Payer en ligne (Mobile Money, carte)',
      'Depuis Abonnement → Payer : Mobile Money et cartes via CinetPay (Afrique francophone) ou carte via Stripe, '
      'selon les moyens activés. L’abonnement est prolongé dès la confirmation du paiement.',
      etapes=['Administration → **Abonnement** → choisissez mensuel ou annuel → **Payer**.',
              'Choisissez le moyen de paiement et suivez les instructions (code Mobile Money, 3-D Secure…).',
              'Au retour, l’état du paiement s’affiche ; la confirmation arrive aussi automatiquement du prestataire.'],
      notes=['Paiement débité mais abonnement non prolongé après 15 minutes : ouvrez un ticket avec la référence du paiement.',
             'Aucun bouton de paiement : le paiement en ligne n’est pas encore activé ; contactez Egalyx pour un paiement par virement.'],
      mots=['payer', 'paye', 'paiement', 'payement', 'mobile', 'money', 'orange', 'mtn', 'moov', 'wave', 'carte', 'visa', 'mastercard', 'cinetpay', 'stripe', 'virement', 'reglement', 'fcfa', 'xof', 'euro', 'debite'],
      liens=[('Abonnement', 'paiement.abonnement')],
      pour='admin',
      questions=['j ai paye mais rien ne se passe', 'paiement debite abonnement pas prolonge']),

    A('api', 'abonnement', 'Connecter Egalyx à un autre logiciel (API, webhooks)',
      'L’API REST /api/v1 (documentation OpenAPI intégrée) permet de lire et d’écrire vos données avec une clé API ; '
      'les webhooks envoient des événements à vos outils.',
      etapes=['Administration → **Clés API** → créez une clé (elle ne s’affiche qu’une fois).',
              'Lisez la **documentation de l’API** : chaque appel envoie la clé dans l’en-tête.',
              'Les **journaux d’appels** montrent l’usage de chaque clé ; révoquez une clé compromise immédiatement.'],
      mots=['api', 'cle', 'cles', 'integration', 'integrations', 'webhook', 'webhooks', 'connecter', 'connecteur', 'interface', 'openapi', 'swagger', 'rest', 'erp', 'si'],
      liens=[('Documentation API', 'api_doc.page'), ('Clés API', 'admin_api_keys'), ('Webhooks', 'admin_webhooks')],
      perms=['can_manage_api'], pour='admin'),

    A('securite_donnees', 'abonnement', 'Où sont mes données et comment sont-elles protégées ?',
      'Chaque organisation est cloisonnée : un utilisateur ne peut ni voir ni modifier les données d’une autre. '
      'Les accès sont contrôlés par module et par permission ; les secrets (2FA, signalements) sont chiffrés ; '
      'les actions sensibles sont journalisées ; des sauvegardes régulières sont faites par l’exploitant.',
      notes=['Pour les questions contractuelles (hébergement, sous-traitants, RGPD / lois locales de protection des données), contactez Egalyx via un ticket.'],
      mots=['securite', 'donnees', 'protection', 'confidentialite', 'rgpd', 'hebergement', 'chiffrement', 'sauvegarde', 'cloisonnement', 'personnelles']),

    # ==================================================================
    # DÉPANNAGE
    # ==================================================================
    A('module_absent', 'depannage', 'Je ne vois pas un module ou un menu',
      'Un module absent n’est pas autorisé pour vous. Trois causes possibles : le module n’est pas activé pour '
      'votre organisation, votre rôle ne l’inclut pas, ou une permission vous manque.',
      etapes=['Demandez à l’administrateur de votre organisation de vérifier vos **permissions** (Utilisateurs → Permissions).',
              'Si même l’administrateur ne voit pas le module, il n’est pas inclus dans votre abonnement : il doit être activé par Egalyx (super administrateur).'],
      mots=['voir', 'vois', 'module', 'modules', 'menu', 'absent', 'manque', 'manquant', 'disparu', 'trouve', 'affiche', 'cache', 'masque', 'onglet'],
      questions=['je ne vois pas le module audit', 'le menu a disparu', 'je ne trouve pas la cartographie', 'la personne ne voit rien', 'mon collegue ne voit pas le module']),

    A('acces_refuse', 'depannage', 'Message « Accès refusé » ou « Permission insuffisante »',
      'Vous pouvez voir l’élément mais pas faire cette action (créer, modifier, valider, supprimer). Demandez la '
      'permission correspondante à votre administrateur, ou faites-vous désigner responsable de l’élément.',
      mots=['acces', 'refuse', 'interdit', 'permission', 'insuffisante', 'autorise', '403', 'droit', 'pas', 'modifier', 'impossible'],
      questions=['pourquoi je ne peux pas modifier', 'acces refuse']),

    A('introuvable', 'depannage', 'Page introuvable (404) en ouvrant un lien',
      'Le lien vise un élément archivé, supprimé ou appartenant à une autre organisation. Retrouvez l’élément avec la recherche (Ctrl K).',
      mots=['404', 'introuvable', 'existe', 'lien', 'casse', 'mort', 'page', 'trouvee', 'erreur'],
      questions=['page introuvable']),

    A('erreur_500', 'depannage', 'Erreur interne (500) ou page blanche',
      'Rechargez la page. Si l’erreur revient, ouvrez un ticket en indiquant la page, l’heure et ce que vous faisiez ; '
      'joignez une capture d’écran.',
      mots=['erreur', '500', 'interne', 'bug', 'bogue', 'plante', 'crash', 'blanche', 'marche', 'fonctionne', 'probleme', 'serveur'],
      questions=['ca ne marche pas', 'j ai une erreur']),

    A('lenteur', 'depannage', 'L’application est lente',
      'Vérifiez votre connexion, fermez les onglets inutiles et utilisez un navigateur à jour (Chrome, Edge, Firefox). '
      'Sur les grandes listes, utilisez les filtres. Si la lenteur persiste, ouvrez un ticket avec la page concernée.',
      mots=['lent', 'lente', 'lenteur', 'lenteurs', 'charge', 'chargement', 'rame', 'temps', 'performance', 'attente']),

    A('enregistrement', 'depannage', 'Mon formulaire ne s’enregistre pas',
      'Regardez les champs en rouge (obligatoires ou mal remplis). Si la page indique un jeton expiré, rechargez-la : '
      'la session avait expiré. Pour un fichier joint, vérifiez la taille et le format.',
      mots=['enregistre', 'enregistrer', 'sauvegarder', 'valider', 'formulaire', 'bouton', 'rien', 'marche', 'obligatoire', 'champ', 'champs', 'fichier', 'joindre', 'piece', 'jointe', 'upload'],
      questions=['le bouton enregistrer ne marche pas']),

    A('email_non_recu', 'depannage', 'Je ne reçois pas les e-mails d’Egalyx',
      'Vérifiez le dossier des indésirables et votre adresse dans Mon profil. Si personne ne reçoit d’e-mail, l’envoi '
      'n’est pas configuré pour votre organisation : les notifications restent visibles dans la cloche.',
      mots=['email', 'mail', 'mails', 'courriel', 'recois', 'recu', 'spam', 'indesirable', 'notification', 'envoi'],
      questions=['je ne recois pas les mails']),

    A('support', 'depannage', 'Signaler un problème ou contacter Egalyx',
      'Un problème dans votre organisation (panne, erreur, incident constaté) : menu **Signaler un incident**. '
      'Une question sur l’utilisation d’Egalyx : posez-la à l’assistant ; s’il ne sait pas répondre, il la transmet aux '
      'gestionnaires de votre organisation. Pour l’abonnement, la facturation ou un problème de la plateforme : écrivez à Egalyx.',
      etapes=['**Signaler un incident** : décrivez ce que vous avez constaté, où et quand ; joignez une capture si utile.',
              'Suivez la suite donnée dans **Mes signalements** (reçu, pris en charge, transformé en incident, traité).',
              'Écrire à Egalyx : bouton « Écrire à Egalyx » du centre d’aide (adresse réglable : EGALYX_EMAIL_SUPPORT).'],
      notes=['Fraude, corruption, harcèlement : utilisez le dispositif d’alerte confidentiel, pas un signalement.',
             'Les gestionnaires des signalements trient et transforment en incident ce qui le mérite ; vous êtes prévenu.'],
      mots=['support', 'ticket', 'tickets', 'signaler', 'signalement', 'signalements', 'contacter', 'contact', 'aide',
            'humain', 'conseiller', 'assistance', 'joindre', 'telephone', 'appeler', 'egalyx', 'panne', 'probleme'],
      liens=[('Signaler un incident', 'signalements.nouveau'), ('Mes signalements', 'signalements.miens')]),

    A('signalements_gerer', 'maitrise', 'Trier les signalements et les transformer en incidents',
      'Menu **Signalements** : les problèmes signalés par les utilisateurs (et par le lien public, s’il est activé). '
      'Triez, puis cochez « Convertir en incident » pour ce qui le mérite : l’incident est créé « à qualifier ».',
      etapes=['Ouvrez **Signalements → Tous les signalements** ; les nouveaux apparaissent aussi dans « Ma semaine ».',
              'Traitez : pris en charge, traité ; ou convertissez en incident (il faut aussi « Gérer les incidents »).',
              'Dans l’incident créé : rattachez le risque (obligatoire avant la résolution) et, si possible, le dispositif.',
              '**Lien public** : à activer pour les personnes sans compte (prestataires, visiteurs) ; régénérez-le s’il circule trop.'],
      notes=['Les badges « Question » signalent les questions transmises par l’assistant, à traiter comme une demande d’aide.',
             'Le déclarant est prévenu quand son signalement est pris en charge, transformé en incident ou classé.'],
      mots=['signalement', 'signalements', 'ticket', 'tickets', 'trier', 'convertir', 'incident', 'lien', 'public', 'anonyme'],
      liens=[('Signalements', 'liste_tickets_support'), ('Lien public', 'signalements.parametres')],
      perms=['can_view_tickets', 'can_manage_tickets']),

    # ==================================================================
    # SUPER ADMINISTRATEUR
    # ==================================================================
    A('sa_client_creer', 'superadmin', 'Créer une organisation cliente et choisir ses modules',
      'Super admin → Clients → Nouveau client ; après l’enregistrement, la page Modules s’ouvre : choisissez un profil '
      '(audit, risques, contrôle interne, conformité, suite complète) puis ajustez module par module.',
      etapes=['**Clients** → **Nouveau client** : nom, référence, pays, formule, nombre d’utilisateurs, administrateur.',
              'Page **Modules** : appliquez un profil (ex. « Cabinet ou service d’audit ») puis cochez / décochez.',
              'Un module désactivé disparaît pour tout le client, administrateur compris, et ses pages sont bloquées.',
              'Le bouton **Modules** reste disponible sur la liste et la fiche du client pour changer plus tard.'],
      mots=['client', 'clients', 'organisation', 'creer', 'nouveau', 'modules', 'profil', 'auditeur', 'cabinet', 'activer', 'desactiver', 'formule'],
      liens=[('Clients', 'super_admin_clients')], pour='super_admin'),

    A('sa_ia', 'superadmin', 'Activer ou désactiver l’IA pour toute la plateforme',
      'Super admin → IA : un interrupteur coupe toutes les fonctions d’IA pour tous les clients (boutons masqués, '
      'adresses bloquées). La variable d’environnement EGALYX_IA=0 force la désactivation.',
      mots=['ia', 'intelligence', 'desactiver', 'activer', 'interrupteur', 'plateforme', 'couper'],
      liens=[('Réglage IA', 'ia.page')], pour='super_admin'),

    A('sa_demo', 'superadmin', 'Créer l’organisation de démonstration',
      'Super admin → Démonstration : crée « Sahel Finance (démonstration) » avec des données réalistes pour présenter l’outil.',
      mots=['demo', 'demonstration', 'presenter', 'exemple', 'donnees', 'test', 'prospect'],
      liens=[('Démonstration', 'demo.page')], pour='super_admin'),

    A('sa_sauvegardes', 'superadmin', 'Sauvegardes de la base de données',
      'Super admin → Sauvegardes : lancer une sauvegarde, voir les dernières. En ligne de commande : flask sauvegarder ; '
      'mise à jour du schéma : flask mettre-a-jour-base.',
      mots=['sauvegarde', 'sauvegardes', 'backup', 'restaurer', 'base', 'donnees', 'schema'],
      liens=[('Sauvegardes', 'sauvegardes.page')], pour='super_admin'),

    A('sa_sanctions', 'superadmin', 'Importer les listes de sanctions',
      'Conformité → Listes de sanctions : importez un fichier CSV (ONU, UE, OFAC, liste nationale) ; la date de mise à jour '
      'est affichée aux clients lors du criblage.',
      mots=['sanctions', 'liste', 'listes', 'importer', 'onu', 'ofac', 'csv', 'gel', 'avoirs'],
      liens=[('Listes de sanctions', 'tiers.sanctions')], pour='super_admin'),
]


# ======================================================================
# Fonctions ajoutées en novembre 2026 : plans par module, règles d'avancement et de clôture,
# heure et devise, lettre de mission, listes paginées, archives KRI, réévaluations.
# ======================================================================
ARTICLES += [
    A('plans_ou_trouver', 'plans', 'Plans d’action d’audit, de risque, de contrôle N2 : où les trouver ?',
      'Chaque plan d’action appartient au module qui l’a fait naître. Les plans d’audit restent dans l’audit, ceux d’un risque '
      'restent dans la cartographie ; la page « Tous les plans d’action » les rassemble pour une vue d’ensemble.',
      etapes=['**Plans d’audit** : menu Audit interne → **Plans d’action**. Cette liste ne montre que les plans nés d’une recommandation d’audit.',
              '**Plans d’un risque** : ouvrez le risque (ou la cartographie) → **Plans d’action**.',
              '**Plans du contrôle N2** : menu Contrôle N2 → **Plans d’action**.',
              '**Plans indépendants** (sans audit ni risque) : Plans d’action → **Indépendants**.',
              '**Tous les plans d’action** : un registre unique, filtrable par origine (audit, risques, indépendant…), par responsable et par échéance.'],
      notes=['Le fil d’Ariane et le bouton **Retour** d’un plan ramènent toujours à son module d’origine : un plan d’audit ne renvoie jamais vers la cartographie, et inversement.',
             'Si vous ouvrez un plan par un lien du mauvais module, Egalyx vous redirige vers la bonne fiche.'],
      mots=['plan', 'plans', 'action', 'actions', 'audit', 'risque', 'risques', 'cartographie', 'c2n', 'independant', 'independants',
            'tous', 'registre', 'ou', 'trouver', 'liste', 'difference', 'origine', 'module', 'retour', 'melange', 'emmele', 'unifie'],
      liens=[('Plans d’action d’audit', 'liste_plans_action'), ('Tous les plans d’action', 'plans_unifies.page'),
             ('Plans indépendants', 'liste_plans_action_independants')],
      questions=['difference plan d action audit et plan d action risque', 'voir tous les plans d action',
                 'ou sont les plans d action des risques', 'ou trouver les plans d action', 'tous les plans d action',
                 'plan d action audit et risque melanges']),

    A('plans_regles', 'plans', 'Avancement et clôture : ce qu’Egalyx fait automatiquement',
      'L’avancement remonte tout seul des sous-actions vers le plan, puis du plan vers la recommandation. Quand tout est terminé, '
      'Egalyx demande la clôture de la recommandation ; il ne la clôture jamais sans validation.',
      etapes=['**Sous-action** : à 0 % elle est « à faire », entre 1 et 99 % « en cours », à 100 % « terminée ». Marquer « terminée » la passe à 100 %.',
              '**Plan** : son avancement est la moyenne de ses sous-actions. S’il en a, le curseur du plan est bloqué : mettez à jour les sous-actions.',
              'Un plan marqué « terminé » passe à 100 %. S’il redescend sous 100 %, il est rouvert automatiquement.',
              '**Recommandation** (audit ou contrôle N2) : son avancement est la moyenne de ses plans.',
              'Quand **tous ses plans sont terminés**, une **demande de clôture** est créée et les gestionnaires sont prévenus. Ils valident ou refusent depuis le registre des recommandations.',
              'Si un plan est rouvert entre-temps, la demande de clôture est retirée.',
              'Une recommandation clôturée passe sa constatation à « close » ; si elle est rouverte, la constatation repasse « en action ».'],
      notes=['Les changements sont enregistrés immédiatement : après actualisation de la page, vous retrouvez la même progression.',
             'Modifier le statut d’une sous-action ou la supprimer demande le droit de modifier le plan (responsable du plan ou gestionnaire des plans d’action).'],
      mots=['avancement', 'progression', 'pourcentage', 'curseur', 'bloque', 'termine', 'terminer', 'cloture', 'cloturer', 'demande',
            'automatique', 'automatiquement', 'recommandation', 'constatation', 'rouvrir', 'rouvert', 'moyenne', 'sous', 'actualiser',
            'enregistre', 'sauvegarde', 'regle', 'regles', 'reaction', 'grise', 'desactive'],
      liens=[('Registre des recommandations', 'recommandations.registre'), ('Tous les plans d’action', 'plans_unifies.page')],
      questions=['mon plan d action est termine mais la recommandation n est pas cloturee', 'demande de cloture recommandation',
                 'la progression du plan ne s enregistre pas', 'pourquoi je ne peux pas bouger le curseur d avancement',
                 'rouvrir un plan termine', 'que se passe t il quand un plan est termine', 'la recommandation ne se cloture pas',
                 'la progression revient a zero apres actualisation']),

    A('plans_statuts', 'plans', 'Les statuts d’un plan d’action et d’une sous-action',
      'Plan : en attente, planifié, en cours, suspendu, retardé, terminé, annulé. Sous-action : à faire, en cours, retardée, terminée, annulée.',
      notes=['Un même statut porte toujours le même nom partout : si un import ou un ancien écran envoie « clôturé » ou « complet », Egalyx l’enregistre comme « terminé ».',
             'Un plan dont l’échéance est passée est signalé **en retard** dans les listes et dans « Ma semaine ».'],
      mots=['statut', 'statuts', 'etat', 'etats', 'planifie', 'suspendu', 'retarde', 'termine', 'annule', 'attente', 'faire', 'sous', 'action', 'plan'],
      liens=[('Tous les plans d’action', 'plans_unifies.page')],
      questions=['statut d une sous action', 'quels sont les statuts d un plan d action']),

    A('lettre_mission', 'audit', 'Préparer et envoyer la lettre de mission',
      'Dans la feuille de travail de la mission, l’onglet **Lettre de mission** génère la lettre avec l’en-tête de votre organisation, '
      'l’affiche en aperçu, l’exporte en PDF et l’envoie par e-mail aux bonnes personnes.',
      etapes=['Ouvrez la mission → **Feuilles de travail** → ouvrez la feuille → onglet **Lettre de mission**.',
              'Choisissez le **modèle d’en-tête** (logo, couleurs, mentions, signature préparés pour votre organisation).',
              '**Générer** pré-remplit la lettre à partir de la mission ; corrigez-la puis **Sauvegarder**.',
              '**Aperçu** et **PDF** montrent la lettre telle qu’elle partira.',
              '**Envoyer** ouvre la liste des destinataires : participants et membres externes en « À », responsable et équipe d’audit en copie ; les observateurs sont proposés mais non cochés. Ajustez puis confirmez.'],
      notes=['L’e-mail reprend l’objet et le message du modèle, joint la lettre en PDF ; les réponses arrivent au chef de mission.',
             'Chaque envoi est gardé dans l’encadré **Envois** (date, destinataires). Si l’envoi d’e-mails n’est pas configuré sur la plateforme, Egalyx le dit au lieu de faire comme si c’était parti.',
             'Les modèles d’en-tête sont créés par l’administrateur Egalyx (super administrateur) pour chaque organisation.'],
      mots=['lettre', 'mission', 'envoyer', 'envoi', 'destinataire', 'destinataires', 'entete', 'modele', 'logo', 'pdf', 'apercu',
            'email', 'audite', 'participants', 'copie', 'signature', 'generer'],
      liens=[('Missions', 'liste_audits')],
      perms=['can_manage_audit'],
      questions=['envoyer la lettre de mission', 'a qui est envoyee la lettre de mission', 'modifier l en tete de la lettre de mission',
                 'modele de lettre de mission', 'imprimer la lettre de mission en pdf', 'la lettre de mission n est pas partie']),

    A('heure_devise', 'admin', 'Régler l’heure et la devise de mon organisation',
      'Menu **Administration → Heure et devise** (aussi dans le menu à votre nom, en haut à droite) : choisissez le fuseau horaire et la monnaie de l’organisation. Toutes les heures '
      'et tous les montants s’affichent ensuite selon ce réglage, pour tous les utilisateurs.',
      etapes=['Menu latéral **Administration → Heure et devise**, ou menu à votre nom (en haut à droite) → **Heure et devise**.',
              'Choisissez le **fuseau horaire** (ex. Abidjan, Dakar, Lomé : UTC+0 ; Cotonou, Douala, Kinshasa : UTC+1 ; Paris).',
              'Choisissez la **devise** : franc CFA (UEMOA ou CEMAC), euro, dollar, dirham, dinar, naira, cedi…',
              'Enregistrez : l’aperçu montre l’heure locale et un exemple de montant.'],
      notes=['Les heures enregistrées sont stockées de façon neutre et converties à l’affichage : changer de fuseau corrige l’affichage sans toucher aux données.',
             'Les heures saisies à la main avant cette fonction (date d’un incident, ouverture d’un questionnaire) restent affichées telles qu’elles ont été saisies.',
             'Le super administrateur peut aussi régler l’heure et la devise de chaque organisation.'],
      mots=['heure', 'heures', 'fuseau', 'horaire', 'devise', 'devises', 'monnaie', 'euro', 'fcfa', 'cfa', 'xof', 'xaf', 'dollar',
            'montant', 'montants', 'decalage', 'fausse', 'faux', 'mauvaise', 'utc', 'gmt', 'locale'],
      liens=[('Heure et devise', 'lettre_mission.heure_devise')],
      pour='admin',
      questions=['comment changer la devise de mon organisation', 'regler le fuseau horaire', 'l heure affichee est fausse',
                 'changer de monnaie fcfa', 'afficher les montants en euros', 'il y a une heure de decalage']),

    A('listes_pages', 'demarrer', 'Listes longues : pages et nombre de lignes',
      'Les grandes listes s’affichent par pages pour rester rapides. En bas de la liste, changez de page ou choisissez 25, 50, 100 ou 200 lignes par page.',
      notes=['Concerné : plans d’action d’audit, Tous les plans d’action, registre des recommandations, demandes de réévaluation.',
             'Les totaux et compteurs en haut de page portent sur toute la liste, pas seulement sur la page affichée.',
             'Les filtres et le tri sont conservés quand vous changez de page.'],
      mots=['liste', 'listes', 'page', 'pages', 'pagination', 'lignes', 'ligne', 'afficher', 'plus', 'suivante', 'precedente',
            'nombre', 'lent', 'longue', 'resultats', 'tout'],
      questions=['afficher plus de lignes dans la liste', 'voir la page suivante', 'la liste n affiche pas tout',
                 'combien de lignes par page']),

    A('kri_archives', 'maitrise', 'Archiver, restaurer ou supprimer des KRI',
      'Un KRI archivé disparaît des tableaux mais reste consultable dans **Archives des KRI**, d’où on peut le restaurer.',
      etapes=['Fiche du KRI → **Archiver**.',
              'Liste des KRI → bouton **Archives** : restaurez un KRI, ou **Restaurer tout** (administrateur).',
              '**Exporter** la liste des archives en fichier.',
              '**Nettoyer** supprime définitivement les KRI archivés depuis plus de 90 jours (administrateur).'],
      mots=['kri', 'kpi', 'indicateur', 'indicateurs', 'archive', 'archives', 'archiver', 'restaurer', 'restaurer', 'nettoyer', 'supprimer', 'exporter'],
      liens=[('Archives des KRI', 'kris_archives')],
      questions=['restaurer des kri archives', 'ou sont les kri archives', 'supprimer definitivement un kri']),

    A('reevaluation', 'risques', 'Demande de réévaluation d’un risque après un audit',
      'Quand un audit montre qu’un risque est mal coté, l’auditeur propose un nouvel impact et une nouvelle probabilité. '
      'La demande est validée ou rejetée par une personne habilitée sur les risques, jamais par son auteur.',
      etapes=['Dans la mission d’audit, sur le risque ou la constatation concerné → **Demander une réévaluation** : impact et probabilité proposés, justification.',
              'Menu Risques → **Demandes de réévaluation** : la demande y attend une décision.',
              '**Valider** crée la nouvelle évaluation du risque ; **Rejeter** demande un commentaire.'],
      mots=['reevaluation', 'reevaluer', 'demande', 'demandes', 'revoir', 'cotation', 'audit', 'auditeur', 'valider', 'rejeter', 'risque'],
      liens=[('Demandes de réévaluation', 'liste_demandes_reevaluation')],
      questions=['demande de reevaluation d un risque', 'l audit demande de reevaluer un risque', 'valider une reevaluation']),

    A('incident_supprimer', 'maitrise', 'Supprimer définitivement un incident',
      'Archivez d’abord l’incident ; seul un administrateur peut ensuite le supprimer définitivement depuis les archives. '
      'La suppression est notée dans le journal d’activité.',
      mots=['incident', 'incidents', 'supprimer', 'definitivement', 'archiver', 'archive', 'effacer'],
      liens=[('Incidents', 'liste_incidents')],
      perms=['can_manage_incidents'],
      questions=['supprimer definitivement un incident', 'effacer un incident']),

    A('sa_reglages_organisation', 'superadmin', 'Heure, devise et modèles de lettre de mission d’une organisation',
      'Super admin → **Heure, devise et lettres de mission** : une ligne par organisation. Ouvrez-la pour régler son fuseau et sa devise, '
      'et préparer ses modèles de lettre de mission.',
      etapes=['Choisissez l’organisation (ou bouton **Réglages** sur la fiche du client).',
              'Réglez le **fuseau horaire** et la **devise**.',
              '**Nouveau modèle** de lettre : logo (celui de l’organisation ou aucun) et sa position, couleur, titre et lignes d’en-tête, mention en haut, pied de page, signature.',
              'Réglez l’**objet** et le **message de l’e-mail** d’envoi. L’aperçu se met à jour pendant la saisie.',
              'Marquez un modèle **par défaut**, **dupliquez**-le pour une variante, désactivez ou supprimez ceux qui ne servent plus.'],
      notes=['Les auditeurs de l’organisation choisissent ensuite le modèle dans l’onglet Lettre de mission ; ils ne peuvent pas modifier l’en-tête.'],
      mots=['heure', 'devise', 'fuseau', 'lettre', 'mission', 'modele', 'modeles', 'entete', 'logo', 'organisation', 'client', 'reglages', 'super', 'admin'],
      liens=[('Heure, devise et lettres de mission', 'lettre_mission.vue_ensemble')], pour='super_admin',
      questions=['heure et devise super admin', 'modele de lettre de mission par client', 'creer un en tete de lettre de mission']),
]

for _a in ARTICLES:
    if _a['id'] == 'plan_suivi':
        _a['resume'] = ('Mettez à jour chaque sous-action (avancement, commentaire, preuve). L’avancement du plan est la moyenne de ses '
                        'sous-actions ; à 100 % il passe « terminé » et la recommandation liée suit.')
        _a['etapes'] = ['Ouvrez le plan depuis son module (audit, risque, contrôle N2) ou depuis **Tous les plans d’action**.',
                        'Pour chaque sous-action : avancement, commentaire, preuve. Sans sous-action, utilisez le curseur du plan.',
                        'L’avancement est enregistré aussitôt ; il est conservé après actualisation.']
        _a['notes'] = ['Le responsable d’un plan ou d’une sous-action peut le mettre à jour même sans permission de gestion générale.',
                       'Les plans en retard apparaissent en rouge, dans « Ma semaine » et font l’objet de relances.',
                       'Ce qui se passe ensuite (plan terminé, demande de clôture de la recommandation) : voir « Avancement et clôture : ce qu’Egalyx fait automatiquement ».']
        _a['liens'] = [('Plans d’action d’audit', 'liste_plans_action'), ('Tous les plans d’action', 'plans_unifies.page')]
    elif _a['id'] in ('plan_creer', 'plan_retard'):
        _a['liens'] = [('Plans d’action d’audit', 'liste_plans_action'), ('Tous les plans d’action', 'plans_unifies.page')]
    elif _a['id'] == 'audit_lancer':
        _a['etapes'][3] = ('Préparez la **lettre de mission** (feuille de travail → onglet Lettre de mission) et le programme de travail.')
    elif _a['id'] == 'registre_recommandations':
        _a['etapes'][3] = ('À 100 %, il **demande la clôture** (une preuve est exigée). Quand tous les plans liés sont terminés, '
                           'Egalyx crée lui-même la demande et prévient les gestionnaires.')
    elif _a['id'] == 'api':
        _a['etapes'].append('Sur chaque clé : **Détails**, **Régénérer** (l’ancienne cesse de marcher) ou **Révoquer**.')
        _a['mots'] += ['regenerer', 'revoquer', 'details']
    elif _a['id'] == 'questionnaires':
        _a['notes'] = list(_a['notes']) + ['**Dupliquer** un questionnaire crée une copie désactivée (avec ses catégories et questions), à adapter puis activer.']
        _a['mots'] += ['dupliquer', 'copier', 'copie']


# ======================================================================
# Couverture complète (19/11/2026) : chaque page de l'outil a sa fiche.
# ======================================================================
ARTICLES += [
    # ------------------------------------------------------------ ADMINISTRATION
    A('operateurs', 'admin', 'Gérer les opérateurs et leurs droits',
      'Les opérateurs sont les collaborateurs des métiers qui évaluent leurs risques, exécutent des campagnes et suivent leurs plans '
      'dans un espace simplifié. L’administrateur choisit pour chacun ce qu’il peut faire et sur quel périmètre.',
      etapes=['Tableau de bord Admin Client → **Opérateurs** (ou **Gérer les opérateurs**).',
              '**Ajouter un opérateur** : choisissez le collaborateur.',
              '**Choisir ses droits** : évaluer les risques, voir ou modifier les évaluations, exécuter ou valider des campagnes, '
              'créer ou exécuter des plans d’action, voir ou évaluer les dispositifs.',
              'Limitez son **périmètre** : directions, services et types de risques autorisés.',
              '**Retirer le rôle** rend au collaborateur son rôle habituel.'],
      notes=['Un opérateur sans aucun droit voit un tableau de bord vide avec un message l’invitant à contacter son administrateur.',
             'Les évaluations des opérateurs peuvent être validées par une personne désignée : voir « Faire valider les évaluations des opérateurs ».'],
      mots=['operateur', 'operateurs', 'metier', 'metiers', 'droits', 'perimetre', 'direction', 'service', 'evaluer', 'espace', 'simplifie'],
      liens=[('Opérateurs', 'admin_operateurs')], pour='admin',
      questions=['ajouter un operateur', 'donner des droits a un operateur', 'limiter un operateur a sa direction',
                 'qu est ce qu un operateur']),

    A('espace_operateur', 'demarrer', 'Mon espace opérateur',
      'Si vous êtes opérateur, Egalyx s’ouvre sur votre **tableau de bord opérationnel** : risques à évaluer, campagnes à réaliser, '
      'plans d’action à suivre et notifications.',
      etapes=['**Risques à évaluer** : ouvrez un risque et saisissez votre évaluation (impact, probabilité, maîtrise).',
              '**Campagnes à réaliser** : exécutez les contrôles qui vous sont confiés.',
              '**Plans d’action à suivre** : mettez à jour l’avancement de vos plans et sous-actions ; les plans en retard sont signalés.',
              '**Mes recommandations** : les recommandations dont vous êtes responsable.',
              '**Mon profil** : photo, coordonnées.'],
      notes=['Vous ne voyez que ce que l’administrateur vous a ouvert, et seulement pour votre périmètre (direction, service).',
             'Si votre tableau de bord est vide avec un message d’avertissement, aucun droit ne vous a encore été donné : contactez votre administrateur.'],
      mots=['operateur', 'espace', 'tableau', 'bord', 'operationnel', 'risques', 'evaluer', 'campagnes', 'realiser', 'plans', 'suivre', 'vide'],
      liens=[('Mon espace', 'operateur_dashboard'), ('Mes recommandations', 'recommandations.miennes')],
      questions=['mon tableau de bord operateur est vide', 'je suis operateur que dois je faire', 'ou evaluer mes risques']),

    A('gestionnaire_utilisateurs', 'admin', 'Déléguer la gestion des utilisateurs (gestionnaire)',
      'Un gestionnaire d’utilisateurs crée, modifie, active ou désactive les comptes à la place de l’administrateur, sans pouvoir toucher à l’administrateur.',
      etapes=['Menu à votre nom → **Créer un gestionnaire**.',
              'Identifiant, e-mail, mot de passe provisoire, département.',
              'Cochez ses pouvoirs : voir la liste, modifier les utilisateurs (sauf l’administrateur), créer des comptes, activer / désactiver.',
              'Le gestionnaire travaille ensuite dans **Gestion des utilisateurs** (filtres, export, statistiques).'],
      notes=['**Désactiver et transférer** : quand une personne part, ses dossiers (risques, plans, recommandations) sont confiés à un autre utilisateur.'],
      mots=['gestionnaire', 'utilisateurs', 'deleguer', 'delegation', 'creer', 'comptes', 'desactiver', 'transferer', 'transfert'],
      liens=[('Créer un gestionnaire', 'client_admin_creer_gestionnaire'), ('Gestion des utilisateurs', 'gestionnaire_utilisateurs')],
      pour='admin',
      questions=['creer un gestionnaire d utilisateurs', 'deleguer la creation des comptes', 'transferer les dossiers d un utilisateur qui part']),

    A('modeles_permissions', 'admin', 'Modèles de permissions',
      'Un modèle regroupe un ensemble de permissions (voir le tableau de bord, gérer les risques, les audits, la veille, exporter…) '
      'à appliquer d’un coup à plusieurs utilisateurs.',
      etapes=['Tableau de bord Admin Client → **Modèles de permissions** → **Nouveau modèle** : nom, rôle associé, description.',
              'Cochez les permissions du modèle.',
              'Sur la fiche d’un utilisateur, **appliquez** le modèle : ses permissions sont remplacées par celles du modèle.'],
      notes=['Modifier un modèle ne change pas les utilisateurs auxquels il a déjà été appliqué : réappliquez-le.'],
      mots=['modele', 'modeles', 'template', 'permissions', 'profil', 'profils', 'appliquer', 'droits', 'role'],
      liens=[('Modèles de permissions', 'admin_templates_permissions')], pour='admin',
      questions=['creer un modele de permissions', 'appliquer les memes droits a plusieurs utilisateurs']),

    A('page_connexion', 'admin', 'Personnaliser la page de connexion de mon organisation',
      'Message d’accueil, contact d’assistance et couleur affichés sur la page de connexion de votre organisation.',
      etapes=['Menu à votre nom → **Identité de l’organisation** → lien « personnaliser la page de connexion ».',
              'Saisissez le **message d’accueil** et le **contact d’assistance** (qui appeler en cas de souci de connexion).',
              'Choisissez la **couleur**, puis **Enregistrer**.'],
      notes=['Le logo et le nom viennent de « Identité de l’organisation ».'],
      mots=['page', 'connexion', 'login', 'accueil', 'message', 'personnaliser', 'couleur', 'contact', 'assistance'],
      liens=[('Page de connexion', 'connexion_client.reglage'), ('Identité de l’organisation', 'identite.page')], pour='admin',
      questions=['personnaliser la page de connexion', 'ajouter un message sur la page de connexion']),

    A('parametres_evaluation', 'admin', 'Paramétrer les échelles d’évaluation (impact, probabilité, maîtrise, couleurs)',
      'Paramétrage → **Paramètres d’évaluation** : le libellé et la description de chaque niveau d’impact, de probabilité et de maîtrise, '
      'le guide d’évaluation affiché aux évaluateurs et les couleurs des niveaux.',
      etapes=['Onglets **Impact**, **Probabilité**, **Maîtrise** : pour chaque niveau, nom court, description longue, couleur, actif, ordre.',
              'Onglet **Guide** : le texte d’aide des trois phases (pré-évaluation, validation, confirmation).',
              'Onglet **Couleurs** : seuils et couleurs Faible, Moyen, Élevé, Revue.',
              '**Enregistrer** chaque onglet ; **Rafraîchir les paramètres** recharge les valeurs.'],
      notes=['Les seuils de cotation et l’appétence se règlent dans « Paramètres des risques ».'],
      mots=['echelle', 'echelles', 'niveaux', 'impact', 'probabilite', 'maitrise', 'libelle', 'description', 'couleur', 'couleurs',
            'guide', 'evaluation', 'parametrer', 'parametres'],
      liens=[('Paramètres d’évaluation', 'admin_parametres_evaluation'), ('Paramètres des risques', 'parametres_risque.page')],
      pour='admin',
      questions=['changer les libelles des niveaux d impact', 'modifier les couleurs de la matrice', 'modifier le guide d evaluation']),

    A('fiches_risque_parametrage', 'admin', 'Adapter la fiche risque : champs personnalisés, listes déroulantes, fichiers',
      'Paramétrage → **Fiches risques** : ajoutez vos propres champs à la fiche d’un risque, créez vos listes de valeurs et réglez les pièces jointes autorisées.',
      etapes=['**Champs personnalisés** : nom affiché, type (texte, nombre, date, liste…), section (général, analyse, évaluation, documentation), '
              'ordre, obligatoire, texte d’aide, valeurs possibles, contrôle de format.',
              '**Listes déroulantes** : valeurs au format « valeur|libellé », sélection multiple ou non, valeurs par défaut.',
              '**Gestion fichiers** : extensions autorisées et taille maximale des pièces jointes.',
              '**Export / Import** : exportez la configuration en fichier JSON pour la reprendre dans une autre organisation.'],
      mots=['champ', 'champs', 'personnalise', 'personnalises', 'liste', 'listes', 'deroulante', 'deroulantes', 'fichier', 'fichiers',
            'extension', 'taille', 'fiche', 'risque', 'parametrage', 'configuration', 'json'],
      liens=[('Fiches risques', 'parametrage_risque'), ('Champs personnalisés', 'parametrage_champs'),
             ('Listes déroulantes', 'parametrage_listes'), ('Gestion fichiers', 'parametrage_fichiers')], pour='admin',
      questions=['ajouter un champ a la fiche risque', 'creer une liste deroulante', 'autoriser un type de fichier',
                 'taille maximale des pieces jointes']),

    A('cloture_campagnes_droit', 'admin', 'Choisir qui peut clôturer une campagne d’évaluation',
      'Paramètres des risques → **Clôture des campagnes** : les gestionnaires des risques et administrateurs (par défaut), '
      'tous les utilisateurs ayant accès à la cartographie (valideurs compris), ou les administrateurs seulement.',
      notes=['Le réglage s’applique au bouton « Clôturer » comme aux liens directs.',
             'Une campagne clôturée ne reçoit plus d’évaluations ; elle reste consultable dans l’historique de la cartographie.'],
      mots=['cloture', 'cloturer', 'campagne', 'campagnes', 'evaluation', 'qui', 'droit', 'autoriser'],
      liens=[('Clôture des campagnes', 'cloture_campagne.page')], pour='admin',
      questions=['qui peut cloturer une campagne', 'empecher de cloturer une campagne']),

    A('usage_limites', 'abonnement', 'Utilisation et limites de mon abonnement',
      'Tableau de bord Admin Client → **Utilisation et limites** : votre formule et ce que vous en consommez (utilisateurs, modules).',
      mots=['utilisation', 'limites', 'limite', 'quota', 'formule', 'consommation', 'nombre', 'utilisateurs', 'licences'],
      liens=[('Utilisation et limites', 'client_admin_usage'), ('Abonnement', 'paiement.abonnement')], pour='admin',
      questions=['combien d utilisateurs puis je creer', 'j ai atteint la limite d utilisateurs']),

    A('sessions_journaux', 'admin', 'Sessions ouvertes et journal système',
      'Tableau de bord Admin Client → boutons **Journal d’activité**, **Sessions**, **Journal système**. **Sessions** montre qui est connecté et depuis quand ; **Journal système** les événements techniques '
      'de votre organisation. Le **journal d’activité** reste la référence pour savoir qui a fait quoi.',
      mots=['sessions', 'session', 'connectes', 'connecte', 'journal', 'systeme', 'logs', 'traces', 'technique'],
      liens=[('Sessions utilisateurs', 'admin_sessions_utilisateurs'), ('Journal système', 'admin_logs_systeme'),
             ('Journal d’activité', 'admin_journal_activite')], pour='admin',
      questions=['qui est connecte en ce moment', 'voir les sessions ouvertes']),

    A('organigramme', 'admin', 'L’organigramme : afficher et personnaliser',
      'Directions & Services → **Organigramme** dessine votre structure (pays, pôles, directions, services). **Configuration** : nom, logo, couleurs.',
      etapes=['Ouvrez l’organigramme ; cherchez une entité ou une personne, zoomez, passez en plein écran.',
              '**Collaborateurs** affiche les personnes sous chaque entité.',
              '**Configuration** : nom de l’entreprise, logo, couleur des directions et des services.',
              '**Imprimer / PDF** pour une page A3.'],
      mots=['organigramme', 'structure', 'directions', 'services', 'poles', 'filiales', 'pays', 'logo', 'couleur', 'imprimer'],
      liens=[('Organigramme', 'admin_organigramme'), ('Configuration', 'configurer_organigramme')], pour='admin',
      questions=['afficher l organigramme', 'changer les couleurs de l organigramme', 'imprimer l organigramme']),

    A('archives_organisation', 'admin', 'Directions archivées',
      'Une direction archivée disparaît des listes mais reste consultable dans **Directions archivées**, d’où on peut la restaurer.',
      mots=['direction', 'directions', 'archivee', 'archivees', 'restaurer', 'archive'],
      liens=[('Directions', 'admin_directions')], pour='admin'),

    # ------------------------------------------------------------ RISQUES
    A('risques_tableau_recherche', 'risques', 'Tableau de bord des risques et recherche avancée',
      'Tous les risques de toutes vos cartographies, filtrables par niveau net (critiques, élevés, moyens, faibles, non évalués), '
      'avec export Excel ou JSON. La recherche avancée filtre par texte, catégorie, niveau et cartographie.',
      etapes=['Depuis le tableau de bord d’accueil → **Tableau de bord des risques**.',
              'Cliquez un niveau (ex. « Critiques actifs ») pour filtrer la liste ; « Critiques N-1 » compare à l’exercice précédent.',
              '**Recherche avancée** : combinez texte, catégorie, niveau et cartographie.',
              '**Exporter Excel** ou **JSON** le résultat.'],
      mots=['tableau', 'bord', 'risques', 'recherche', 'avancee', 'filtrer', 'critiques', 'eleves', 'tous', 'liste', 'exporter', 'json', 'excel', 'trouver'],
      liens=[('Tableau de bord des risques', 'dashboard_risques'), ('Recherche avancée', 'recherche_risques')],
      perms=['can_manage_risks', 'can_view_reports'],
      questions=['voir tous les risques critiques', 'chercher un risque', 'liste de tous les risques', 'exporter les risques en excel']),

    A('archives_risques', 'risques', 'Cartographies et risques archivés',
      'Une cartographie ou un risque archivé quitte les listes mais reste dans les archives : on peut le consulter, le restaurer, '
      'ou nettoyer les archives (suppression définitive).',
      etapes=['Cartographie → **Archives** (cartographies) ou **Risques archivés**.',
              '**Restaurer** remet l’élément en service avec son historique.',
              '**Nettoyage** supprime définitivement les archives choisies : action irréversible.'],
      mots=['archive', 'archives', 'archiver', 'restaurer', 'cartographie', 'cartographies', 'risque', 'risques', 'nettoyer', 'nettoyage', 'definitivement'],
      liens=[('Cartographies archivées', 'cartographies_archives'), ('Risques archivés', 'risques_archives')],
      perms=['can_manage_risks'],
      questions=['restaurer une cartographie archivee', 'restaurer un risque archive', 'ou sont les risques archives']),

    A('comparaison_matrices', 'pilotage', 'Comparer deux matrices de risques',
      'Menu **Comparaison des matrices** (sous le tableau de bord stratégique) : mettez côte à côte deux cartographies ou deux périodes pour voir les risques qui montent ou baissent.',
      mots=['comparer', 'comparaison', 'matrice', 'matrices', 'evolution', 'periode', 'avant', 'apres', 'cartographies'],
      liens=[('Comparaison des matrices', 'rapport_comparaison_matrices')],
      questions=['comparer deux cartographies', 'evolution de la matrice entre deux periodes']),

    A('organismes', 'conformite', 'Organismes régulateurs',
      'La liste des autorités (banque centrale, commission bancaire, autorité de marché…) : code, nom, pays, type, contact et couleur. '
      'Elle sert dans la veille réglementaire et pour l’origine des recommandations externes.',
      mots=['organisme', 'organismes', 'regulateur', 'regulateurs', 'autorite', 'autorites', 'bceao', 'cobac', 'commission', 'superviseur'],
      liens=[('Organismes régulateurs', 'liste_organismes')],
      questions=['ajouter un organisme regulateur', 'liste des regulateurs']),

    # ------------------------------------------------------------ MAÎTRISE
    A('dispositifs_benchmark', 'maitrise', 'Comparer l’efficacité des dispositifs de maîtrise',
      'Depuis le stress test d’un dispositif → **Benchmark** : chaque dispositif avec son type, son efficacité, la réduction du risque obtenue, sa résilience et son stress test. '
      'Exportez en PDF ou imprimez.',
      mots=['benchmark', 'comparer', 'efficacite', 'dispositif', 'dispositifs', 'reduction', 'resilience', 'stress', 'rapport'],
      liens=[('Benchmark des dispositifs', 'benchmark_dispositifs')], perms=['can_manage_risks'],
      questions=['quels dispositifs sont les plus efficaces', 'rapport sur les dispositifs de maitrise']),

    A('dispositifs_archives', 'maitrise', 'Dispositifs archivés',
      'Un dispositif archivé n’est plus compté dans la maîtrise du risque ; il reste dans les **archives des dispositifs**, '
      'd’où on peut le restaurer ou le supprimer définitivement.',
      mots=['dispositif', 'dispositifs', 'archive', 'archives', 'restaurer', 'supprimer', 'definitivement', 'dmr'],
      liens=[('Dispositifs archivés', 'dispositifs_archives')], perms=['can_manage_risks']),

    A('kri_sources', 'maitrise', 'Alimenter un KRI automatiquement (sources de données)',
      'Fiche d’un KRI → **Sources de données** : déclarez d’où viennent les mesures (API, fichier, base de données) pour éviter les saisies manuelles.',
      etapes=['**Nouvelle source** : nom, type (API, fichier, base de données), paramètres de connexion.',
              'Rattachez la source au KRI concerné.',
              'Suivez l’état de chaque source (active ou non) dans la liste.'],
      mots=['source', 'sources', 'donnees', 'automatique', 'automatiquement', 'alimenter', 'api', 'fichier', 'base', 'kri', 'import'],
      liens=[('Sources de données', 'liste_sources_donnees')], perms=['can_manage_kri'],
      questions=['alimenter un kri automatiquement', 'importer les mesures d un kri']),

    A('incidents_tableaux', 'maitrise', 'Tableaux de bord et analyse des incidents',
      'Boutons en haut de la liste des incidents : le **tableau de bord avancé** (par direction, évolution dans le temps, top 10 des coûts, filtres de dates), '
      'l’**analyse** des tendances et récurrences, et la liste des **incidents escaladés** en attente.',
      mots=['incident', 'incidents', 'tableau', 'bord', 'avance', 'analyse', 'tendance', 'tendances', 'recurrence', 'cout', 'couts',
            'direction', 'escalade', 'escalades', 'statistiques'],
      liens=[('Tableau de bord avancé', 'dashboard_incidents_avance'), ('Analyse des incidents', 'dashboard_ia_incidents'),
             ('Incidents escaladés', 'incidents_escalade_attente')],
      perms=['can_manage_incidents', 'can_view_incidents'],
      questions=['statistiques des incidents par direction', 'cout des incidents', 'incidents escalades', 'incidents recurrents']),

    A('incidents_export_archives', 'maitrise', 'Exporter ou archiver des incidents',
      'Depuis la liste des incidents : export **CSV**, **Excel** ou **PDF** de la sélection filtrée. Un incident archivé passe dans '
      '**Incidents archivés**, d’où il peut être restauré.',
      mots=['incident', 'incidents', 'exporter', 'export', 'csv', 'excel', 'pdf', 'archiver', 'archives', 'restaurer'],
      liens=[('Incidents', 'liste_incidents'), ('Incidents archivés', 'incidents_archives')],
      perms=['can_manage_incidents', 'can_view_incidents'],
      questions=['exporter les incidents en excel', 'restaurer un incident archive']),

    # ------------------------------------------------------------ CONTRÔLE
    A('processus_metier', 'controle', 'Processus métier et vue transversale',
      'Déclarez vos processus (nom, code, type, processus parent, propriétaire, directions) ; la **vue transversale** montre pour chaque processus '
      'ses risques et son score.',
      etapes=['Logigrammes → **Processus métier** → **Nouveau processus** : nom, code, type, parent, propriétaire, directions associées.',
              'Rattachez risques, contrôles et logigrammes au processus.',
              'Logigrammes → **Vue transversale** : le classement des processus par score de risque.'],
      mots=['processus', 'metier', 'transversale', 'vue', 'proprietaire', 'parent', 'score', 'cartographie', 'macro'],
      liens=[('Processus métier', 'liste_processus_metier'), ('Vue transversale', 'vue_transversale')], perms=['can_manage_logigram', 'can_manage_processus'],
      questions=['creer un processus', 'quels processus sont les plus risques', 'vue transversale des processus']),

    A('logigrammes_archives', 'controle', 'Logigrammes archivés',
      'Un logigramme archivé reste dans **Logigrammes archivés** : restaurez-le, exportez la liste, ou supprimez-le définitivement.',
      mots=['logigramme', 'logigrammes', 'archive', 'archives', 'restaurer', 'supprimer', 'definitivement'],
      liens=[('Logigrammes archivés', 'archives_logigrammes')]),

    A('c2n_reglages', 'controle', 'Réglages du contrôle interne N2 (seuils, échantillons)',
      'Contrôle interne N2 → **Réglages** : seuils de conclusion (conforme, à améliorer, à corriger, en %) et taille d’échantillon proposée '
      'selon la fréquence du contrôle.',
      mots=['reglages', 'seuil', 'seuils', 'conclusion', 'conforme', 'ameliorer', 'corriger', 'echantillon', 'echantillons', 'taille', 'frequence', 'c2n', 'n2'],
      liens=[('Réglages N2', 'c2n_reglages.page')], perms=['can_manage_controle_interne_n2'],
      questions=['changer les seuils de conformite c2n', 'taille de l echantillon']),

    A('c2n_referentiel', 'controle', 'Construire le référentiel de contrôles N2',
      'Contrôle interne N2 → **Référentiel** → créer : code, nom du contrôle, processus, métier, objectif, fréquence, responsable, '
      'et les risques couverts (chargés depuis une cartographie ou saisis).',
      mots=['referentiel', 'controle', 'controles', 'type', 'types', 'c2n', 'n2', 'frequence', 'objectif', 'risques', 'couverts'],
      liens=[('Référentiel N2', 'c2n_liste_referentiel')], perms=['can_manage_controle_interne_n2'],
      questions=['creer un controle dans le referentiel', 'ajouter un controle type']),

    A('c2n_journal', 'controle', 'Journal d’audit du contrôle N2',
      'Toutes les actions sur le contrôle N2 (création, exécution, soumission, validation), filtrables par utilisateur, action et type d’élément.',
      mots=['journal', 'trace', 'traces', 'historique', 'c2n', 'n2', 'qui', 'action'],
      liens=[('Journal d’audit N2', 'c2n_journal_audit')], perms=['can_manage_controle_interne_n2', 'can_view_controle_interne_n2']),

    A('campagnes_statistiques', 'controle', 'Tableau de bord des campagnes de contrôle',
      'Répartition par statut, volumes contrôlés, taux de réalisation, de conformité et d’anomalie, efficacité.',
      mots=['campagne', 'campagnes', 'statistiques', 'tableau', 'bord', 'taux', 'conformite', 'anomalie', 'volumes'],
      liens=[('Tableau de bord des campagnes', 'statistiques_globales_controle')],
      questions=['statistiques des campagnes de controle', 'taux de conformite des campagnes']),

    A('questionnaires_import', 'controle', 'Importer un questionnaire',
      'Questionnaires → **Importer questionnaire** : chargez un fichier JSON, choisissez d’importer catégories, questions et options, '
      'vérifiez l’aperçu puis importez.',
      mots=['questionnaire', 'questionnaires', 'importer', 'import', 'json', 'fichier', 'modele'],
      liens=[('Importer un questionnaire', 'importer_questionnaire')],
      questions=['importer un questionnaire', 'format du fichier questionnaire']),

    # ------------------------------------------------------------ AUDIT
    A('feuilles_travail', 'audit', 'Feuilles de travail d’une mission',
      'Les feuilles de travail documentent les tests de la mission : objectif, procédés, constats, pièces, et l’onglet **Lettre de mission**.',
      etapes=['Fiche de la mission → **Feuilles de travail** → ouvrir ou créer une feuille (ou menu Audit interne → **Feuilles de travail** pour toutes les missions).',
              'Complétez les onglets (objectifs, tests réalisés, conclusions) et sauvegardez.'],
      mots=['feuille', 'feuilles', 'travail', 'papier', 'papiers', 'test', 'tests', 'documentation', 'mission'],
      liens=[('Feuilles de travail', 'liste_global_feuilles_travail')], perms=['can_manage_audit'],
      questions=['ou sont les feuilles de travail', 'creer une feuille de travail']),

    A('audit_parametres', 'audit', 'Paramètres d’audit : configurations, modèles de constatations, checklists',
      'Pour gagner du temps à chaque mission : des **configurations** par type d’audit (durée standard, seuils de gravité), des **modèles de '
      'constatations** prêts à l’emploi (cause racine, recommandation standard) et des **checklists** par type d’audit.',
      etapes=['Liste des missions d’audit → **Paramètres d’audit** : **Nouvelle configuration** ou **Initialiser les configurations** (jeu de départ).',
              '**Nouveau modèle** de constatation : référence, titre, type, gravité par défaut, processus, cause racine typique, recommandation standard.',
              'Menu Audit interne → **Checklists d’audit** : choisissez un type, appliquez le modèle et personnalisez-le.'],
      notes=['Les **recommandations globales** (Administration) sont des textes types repris dans les rapports d’audit.'],
      mots=['configuration', 'configurations', 'parametres', 'audit', 'modele', 'modeles', 'constatation', 'constatations', 'checklist',
            'checklists', 'liste', 'controle', 'type', 'gravite', 'recommandation', 'globale', 'globales', 'standard'],
      liens=[('Paramètres d’audit', 'configurations_audit'), ('Checklists', 'checklist_audit'),
             ('Recommandations globales', 'admin_recommandations_globales')], perms=['can_manage_audit'],
      questions=['creer un modele de constatation', 'utiliser une checklist d audit', 'recommandations types pour les rapports']),

    A('rapports_audit_fichiers', 'audit', 'Comparer plusieurs missions d’audit',
      'Menu Audit interne → **Comparaison d’audits** : constatations, recommandations, plans d’action, taux de réalisation et score '
      'de chaque mission, côte à côte.',
      mots=['rapport', 'rapports', 'fichier', 'fichiers', 'joint', 'joints', 'televerser', 'comparer', 'comparaison', 'missions', 'audits'],
      liens=[('Comparaison d’audits', 'rapport_comparaison_audits')],
      perms=['can_manage_audit', 'can_view_reports'],
      questions=['joindre un fichier a un audit', 'comparer deux audits']),

    A('developpement_auditeurs', 'audit', 'Développement des auditeurs : compétences et formations',
      'Menu Audit interne → **Développement des auditeurs** : les compétences de l’équipe d’audit et leurs formations.',
      etapes=['**Compétences** : code, nom, catégorie, niveau requis ; activez celles servant aux évaluations.',
              '**Auditeurs** : le niveau de chacun par compétence (évaluation).',
              '**Formations** : titre, type, durée, dates, coût, formateur, objectifs ; inscrivez les auditeurs.'],
      mots=['auditeur', 'auditeurs', 'competence', 'competences', 'formation', 'formations', 'developpement', 'equipe', 'niveau', 'evaluation'],
      liens=[('Développement des auditeurs', 'developpement_auditeurs_index'), ('Compétences', 'gestion_competences'),
             ('Formations', 'liste_formations')], perms=['can_manage_audit'],
      questions=['suivre les competences des auditeurs', 'ajouter une formation', 'inscrire un auditeur a une formation']),

    A('programme_archives', 'audit', 'Programmes d’audit archivés',
      'Un programme archivé (exercice terminé) reste consultable dans **Programmes archivés** et peut être restauré.',
      mots=['programme', 'programmes', 'archive', 'archives', 'restaurer', 'ancien', 'exercice'],
      liens=[('Programmes archivés', 'programmes_archives')], perms=['can_manage_audit_program']),

    # ------------------------------------------------------------ CONFORMITÉ
    A('veille_vues', 'conformite', 'Veille réglementaire : tableau de bord, kanban, calendrier, favoris',
      'Plusieurs vues sur les textes suivis : **tableau de bord**, **kanban** par statut (projets, en vigueur, abrogées, suspendues), '
      '**calendrier** des échéances (exportable vers Outlook ou Google Agenda en .ics), **favoris**, **rapport** par impact et par type.',
      etapes=['Veille → **Kanban** : faites glisser une veille pour changer son statut.',
              '**Calendrier** : dates d’application et actions des 30 prochains jours ; **Exporter (.ics)** pour votre agenda.',
              '**Favoris** : l’étoile sur une veille la met dans « Mes veilles favorites ».',
              '**Rapport** : répartition par impact et par type, actions à faire, en cours, terminées.'],
      mots=['veille', 'kanban', 'calendrier', 'echeance', 'echeances', 'ics', 'agenda', 'outlook', 'favori', 'favoris', 'rapport',
            'dashboard', 'tableau', 'vigueur', 'abrogee', 'projet'],
      liens=[('Tableau de bord veille', 'veille_dashboard'), ('Kanban', 'veille_kanban'), ('Calendrier', 'veille_calendar'),
             ('Rapport', 'rapport_veille')],
      perms=['can_manage_regulatory', 'can_view_veille'],
      questions=['calendrier des echeances reglementaires', 'exporter la veille dans mon agenda', 'vue kanban de la veille',
                 'mes veilles favorites']),

    A('veille_menaces', 'conformite', 'Détection de menaces réglementaires',
      'Veille → **Menaces** : Egalyx repère les textes dont l’échéance approche ou l’impact est fort sans action prévue. '
      '**Relancer** l’analyse ; **Ignorer** une menace (avec une raison).',
      mots=['menace', 'menaces', 'detection', 'detecter', 'risque', 'reglementaire', 'ignorer', 'relancer'],
      liens=[('Menaces', 'veille_menaces')], perms=['can_manage_regulatory', 'can_view_veille']),

    A('veille_archives', 'conformite', 'Archives de la veille et des actions de conformité',
      'Les veilles et actions archivées restent consultables (filtres, recherche) dans les archives de la veille.',
      mots=['veille', 'archives', 'archive', 'action', 'actions', 'conformite', 'restaurer'],
      liens=[('Archives veille', 'veille_archives')], perms=['can_manage_regulatory', 'can_view_veille']),

    A('alerte_suivi', 'conformite', 'Suivre mon signalement (lanceur d’alerte)',
      'Après un signalement, vous recevez un **code de suivi** et choisissez un **mot de passe**. Sur la page **Suivre un signalement**, '
      'ils donnent accès au dossier : réponses du référent, questions, état — sans révéler votre identité.',
      mots=['suivre', 'suivi', 'signalement', 'alerte', 'code', 'anonyme', 'lanceur', 'dossier', 'reponse'],
      liens=[('Suivre un signalement', 'alerte.suivi')], pour='public',
      questions=['suivre mon signalement', 'j ai perdu mon code de suivi', 'le referent m a t il repondu']),

    # ------------------------------------------------------------ CONTINUITÉ / QUALITÉ
    A('pca_tableau_stress', 'continuite', 'Tableau de bord PCA et stress test',
      'Le **tableau de bord PCA** montre les plans par statut et par niveau de maturité. Le **stress test** note chaque plan sur 5 '
      'face à des scénarios de crise.',
      mots=['pca', 'continuite', 'tableau', 'bord', 'maturite', 'stress', 'test', 'crise', 'scenario', 'scenarios', 'resilience'],
      liens=[('Tableau de bord PCA', 'tableau_bord_pca'), ('Stress test', 'pca_stress_test_dedie')],
      perms=['can_manage_bcp', 'can_view_bcp'],
      questions=['niveau de maturite des pca', 'faire un stress test pca']),

    A('qualite_outils', 'continuite', 'Qualité : cartographie des plans, revues, grilles d’audit',
      'Autour des plans qualité : la **cartographie** des plans, les **revues** (en retard, dans les 30 jours), les **grilles d’audit qualité** '
      '(questions par référentiel) et la **cartographie des risques par fonction d’assurance** (niveaux de contrôle 1, 2, 3 et externe).',
      etapes=['Plans qualité → **Grilles d’audit** → **Nouvelle grille** : titre, référentiel, version, type, puis les questions ; **Utiliser** la grille pour un audit.',
              'Plans qualité → **Revues** : les plans dont la revue est en retard ou proche.',
              '**Cartographie des risques par fonction d’assurance** : pour chaque risque, qui contrôle à quel niveau ; export PDF ou Excel.'],
      mots=['qualite', 'grille', 'grilles', 'audit', 'revue', 'revues', 'cartographie', 'assurance', 'fonction', 'fonctions',
            'niveau', 'niveaux', 'lignes', 'defense', 'referentiel', 'iso'],
      liens=[('Plans qualité', 'liste_plans_qualite'), ('Grilles d’audit qualité', 'liste_grilles_audit_qualite'),
             ('Revues', 'alertes_revues_qualite'), ('Cartographie par fonction d’assurance', 'liste_cartographie_risques')],
      perms=['can_manage_quality', 'can_manage_quality_plans', 'can_manage_quality_audits'],
      questions=['creer une grille d audit qualite', 'revues des plans qualite en retard', 'trois lignes de defense']),

    # ------------------------------------------------------------ PLANS
    A('plans_independants', 'plans', 'Créer un plan d’action indépendant',
      'Pour une action qui ne vient ni d’un audit ni d’un risque (projet interne, demande de la direction) : Plans d’action → '
      '**Indépendants** → **Nouveau** : nom, description, responsable, dates.',
      mots=['independant', 'independants', 'plan', 'action', 'libre', 'sans', 'audit', 'risque', 'projet'],
      liens=[('Plans indépendants', 'liste_plans_action_independants')],
      questions=['creer un plan d action sans audit', 'plan d action independant']),

    # ------------------------------------------------------------ PILOTAGE / IA / AIDE
    A('rapports_analyses', 'pilotage', 'Rapports et analyses par direction',
      'Menu **Rapports et analyses** : pour chaque direction, nombre de risques, score moyen et risques critiques ; export PDF.',
      mots=['rapport', 'rapports', 'analyse', 'analyses', 'direction', 'directions', 'score', 'moyen', 'critiques', 'pdf'],
      liens=[('Rapports et analyses', 'rapports')]),

    A('ia_suivi', 'ia', 'Suivre l’utilisation de l’IA',
      'Tableau de bord Admin Client → **Analyses IA** : la liste les analyses faites (par type, audits les plus analysés, analyses récentes).',
      mots=['ia', 'analyses', 'utilisation', 'suivi', 'intelligence', 'artificielle', 'consommation'],
      liens=[('Analyses IA', 'admin_analyses_ia')], pour='admin'),

    A('assistant_ameliorer', 'demarrer', 'Questions non comprises par l’assistant',
      'Tableau de bord Admin Client → **Questions non comprises** (super admin : menu à son nom) : la liste des questions auxquelles l’assistant n’a pas su répondre. '
      'Elle sert à compléter le centre d’aide. Vous pouvez aussi transmettre une question au support depuis l’assistant.',
      mots=['assistant', 'chat', 'chatbot', 'questions', 'comprises', 'repondu', 'reponse', 'ameliorer'],
      liens=[('Questions non comprises', 'assistant_questions_non_comprises')], pour='admin',
      questions=['l assistant ne comprend pas ma question', 'questions non comprises']),

    A('support_page', 'depannage', 'La page Support',
      'Page **Support** (lien « Support » en bas du site public) : parcourir l’aide par catégorie, ouvrir un ticket (sujet, priorité, message) et les autres moyens de contact.',
      mots=['support', 'contact', 'aide', 'ticket', 'telephone', 'email', 'joindre', 'equipe'],
      liens=[('Support', 'support')]),

    # ------------------------------------------------------------ SUPER ADMINISTRATEUR
    A('sa_formules', 'superadmin', 'Formules d’abonnement',
      'Super admin → **Formules d’abonnement** : créez les formules (nom, prix, utilisateurs inclus, modules) proposées aux clients.',
      mots=['formule', 'formules', 'abonnement', 'offre', 'offres', 'prix', 'tarif', 'creer'],
      liens=[('Formules', 'super_admin_formules')], pour='super_admin'),

    A('sa_management', 'superadmin', 'Gérer les super administrateurs',
      'Super admin → **Gestion Super Admins** : liste, création d’un nouveau super administrateur, réinitialisation de mot de passe.',
      mots=['super', 'admin', 'administrateur', 'administrateurs', 'creer', 'reinitialiser', 'mot', 'passe', 'gestion'],
      liens=[('Gestion Super Admins', 'super_admin_management')], pour='super_admin'),

    A('sa_vue_client', 'superadmin', 'Voir l’outil comme un client (Vue Client)',
      'Menu **Vue Client** : choisissez une organisation pour travailler avec ses données ; **Ma vue personnelle** pour revenir. '
      'Le **panneau de contrôle** rappelle le mode de vue actuel et les actions système.',
      mots=['vue', 'client', 'clients', 'consulter', 'basculer', 'changer', 'organisation', 'personnelle', 'panneau', 'controle', 'mode'],
      liens=[('Panneau de contrôle', 'super_admin_control_panel')], pour='super_admin',
      questions=['voir les donnees d un client', 'revenir a ma vue', 'aucun client selectionne']),

    A('sa_tous_utilisateurs', 'superadmin', 'Tous les utilisateurs de la plateforme',
      'Super admin → **Tous les utilisateurs** : filtres par client, statistiques globales, détail et export.',
      mots=['utilisateurs', 'tous', 'plateforme', 'clients', 'export', 'statistiques'],
      liens=[('Tous les utilisateurs', 'liste_utilisateurs')], pour='super_admin'),

    A('sa_documents', 'superadmin', 'Documents commerciaux et juridiques',
      'Super admin : **Documents juridiques** (licence, contrat de service, SLA, accord de confidentialité), **Facture pro forma**, '
      '**Contrat de représentation** et **Générateur de conventions** (apporteur d’affaires). Chaque document se génère, se copie, se télécharge ou s’imprime.',
      mots=['contrat', 'contrats', 'licence', 'sla', 'nda', 'confidentialite', 'proforma', 'facture', 'devis', 'representation',
            'convention', 'conventions', 'apporteur', 'juridique', 'juridiques'],
      liens=[('Documents juridiques', 'licence'), ('Facture pro forma', 'proforma'), ('Contrat de représentation', 'representation'),
             ('Générateur de conventions', 'super_admin_generateur_conventions')], pour='super_admin',
      questions=['generer une facture pro forma', 'generer un contrat de licence']),

    A('sa_articles', 'superadmin', 'Articles du blog',
      'Super admin → **Gestion des articles** : écrire, publier ou garder en brouillon, catégories, auteurs, génération assistée par IA.',
      mots=['article', 'articles', 'blog', 'publier', 'brouillon', 'categorie', 'auteur'],
      liens=[('Gestion des articles', 'admin_articles')], pour='super_admin'),

    A('sa_recalcul', 'superadmin', 'Recalculer les cotations des risques',
      'Menu à votre nom → **Recalcul des cotations** : recalcule les scores bruts et nets de tous les risques avec les paramètres actuels '
      '(après un changement de seuils, par exemple).',
      mots=['recalculer', 'recalcul', 'cotation', 'cotations', 'score', 'scores', 'seuils'],
      liens=[('Recalcul des cotations', 'recalculer_cotations_admin')], pour='super_admin'),

    A('sa_apparence', 'superadmin', 'Choisir l’interface d’une organisation (actuelle ou harmonisée)',
      'Menu à votre nom → **Apparence** : pour chaque organisation, l’interface **actuelle** ou l’interface **harmonisée**. '
      'Le changement est immédiat et ne touche pas aux données.',
      mots=['apparence', 'interface', 'design', 'theme', 'harmonisee', 'actuelle', 'classique', 'nouvelle', 'style', 'look'],
      liens=[('Apparence', 'apparence.page')], pour='super_admin',
      questions=['changer l interface d un client', 'activer l interface harmonisee']),
]


GLOSSAIRE = [
    ('Appétence au risque', 'Niveau de risque que la direction accepte de prendre pour atteindre ses objectifs ; au-delà, des mesures sont exigées.'),
    ('BIA', 'Business Impact Analysis : analyse des conséquences d’un arrêt d’activité, qui fixe RTO et RPO.'),
    ('Bénéficiaire effectif', 'Personne physique qui, in fine, possède ou contrôle un client ou un tiers.'),
    ('C2N', 'Contrôle interne de niveau 2 : contrôles réalisés par une fonction indépendante des opérationnels.'),
    ('Campagne de contrôle', 'Test d’un contrôle sur un échantillon de dossiers, qui donne un taux de conformité.'),
    ('Cartographie des risques', 'Ensemble des risques d’un périmètre, évalués et positionnés selon impact et probabilité.'),
    ('Constatation', 'Écart relevé par l’auditeur entre la situation observée et la règle attendue.'),
    ('Criblage', 'Comparaison du nom d’un tiers aux listes de sanctions et de gel des avoirs.'),
    ('Demande de clôture', 'Proposition de clore une recommandation, faite par son responsable ou automatiquement quand tous ses plans sont terminés ; un gestionnaire la valide ou la refuse.'),
    ('Criticité', 'Niveau d’un risque (Faible, Moyen, Élevé, Critique) obtenu à partir de son score.'),
    ('Dispositif de maîtrise (DMR)', 'Contrôle ou mesure qui réduit la probabilité ou l’impact d’un risque.'),
    ('Escalade', 'Remontée automatique d’un incident non traité dans les délais vers un niveau hiérarchique supérieur.'),
    ('Fuseau horaire', 'Heure légale de l’organisation (ex. UTC+0 à Abidjan) ; toutes les heures affichées en dépendent.'),
    ('GAFI', 'Groupe d’action financière : publie les listes de pays à haut risque et sous surveillance en matière de LCB-FT.'),
    ('Impact', 'Gravité des conséquences si le risque survient (1 à 5).'),
    ('KPI', 'Indicateur de performance, comparé à une cible.'),
    ('KRI', 'Indicateur de risque, comparé à un seuil d’alerte et un seuil critique.'),
    ('LCB-FT', 'Lutte contre le blanchiment de capitaux et le financement du terrorisme.'),
    ('Maîtrise (niveau de)', 'Qualité des dispositifs de maîtrise, de 1 Insuffisant à 5 Excellent ; réduit la probabilité nette.'),
    ('Non-conformité', 'Écart constaté lors d’un contrôle, suivi jusqu’à sa correction.'),
    ('PCA', 'Plan de continuité d’activité : organisation pour continuer à fonctionner pendant une crise.'),
    ('PPE', 'Personne politiquement exposée : exerce ou a exercé une fonction publique importante (ou proche d’une telle personne).'),
    ('Probabilité', 'Vraisemblance que le risque survienne (1 à 5).'),
    ('Recommandation', 'Action proposée par l’auditeur pour corriger une constatation.'),
    ('Risque brut', 'Impact × probabilité, avant prise en compte des dispositifs de maîtrise.'),
    ('Risque net (résiduel)', 'Risque restant après les dispositifs de maîtrise ; c’est le niveau de référence.'),
    ('RPO', 'Perte de données maximale acceptable, exprimée en durée.'),
    ('RTO', 'Durée maximale d’interruption acceptable avant reprise.'),
    ('SLA', 'Délai de traitement convenu (par exemple pour un incident).'),
    ('Vigilance (LCB-FT)', 'Intensité des mesures de connaissance d’un tiers : simplifiée, standard ou renforcée.'),
]


# Guide illustré pas à pas (captures d'écran annotées) : catégorie et fiches ajoutées en tête du centre d'aide.
try:
    from egalyx.guide_illustre import installer as _installer_guide
    _installer_guide(ARTICLES, CATEGORIES)
except ImportError:  # pragma: no cover
    pass


def article(id_):
    for a in ARTICLES:
        if a['id'] == id_:
            return a
    return None


# ----------------------------------------------------------------------
# Réglage fin de la recherche (banque de questions recette/banque_questions.py)
# ----------------------------------------------------------------------
_RETIRER_MOTS = {
    'assistant_ameliorer': ['assistant', 'chat', 'chatbot', 'reponse', 'ameliorer'],
    'rapports_audit_fichiers': ['fichier', 'fichiers', 'joint', 'joints', 'televerser', 'rapport', 'rapports'],
    'kri_sources': ['donnees', 'kri'],
    'kri_archives': ['kri', 'kpi', 'indicateur', 'indicateurs'],
    'c2n_referentiel': ['controle', 'controles', 'c2n', 'n2', 'type', 'types'],
    'c2n_reglages': ['c2n', 'n2', 'conforme'],
    'c2n_journal': ['c2n', 'n2', 'qui', 'action', 'historique'],
    'questionnaires_import': ['modele'],
    'audit_parametres': ['audit', 'liste', 'controle', 'type', 'recommandation'],
    'ia_absente': [],
    'ia_suivi': ['ia', 'intelligence', 'artificielle'],
    'cloture_campagnes_droit': ['evaluation', 'campagnes'],
    'espace_operateur': ['campagnes', 'tableau', 'bord', 'risques', 'plans', 'operationnel'],
    'plan_retard': [],
    'gestionnaire_utilisateurs': ['utilisateurs', 'creer', 'comptes'],
    'incidents_export_archives': ['exporter', 'export', 'csv', 'excel', 'pdf'],
    'support_page': ['contact', 'support', 'joindre', 'equipe', 'email', 'telephone'],
    'risques_tableau_recherche': ['exporter', 'json', 'excel'],
}
_AJOUTER = {
    'presentation': (['egalyx', 'quoi', 'outil', 'logiciel', 'sert'], ['c est quoi egalyx', 'a quoi sert egalyx', 'presentation de l outil']),
    'navigation': (['deplacer', 'deplace', 'menu', 'menus', 'naviguer'], ['comment on se deplace dans l outil', 'ou sont les menus']),
    'assistant': ([], ['a quoi sert l assistant', 'comment utiliser l assistant', 'que peut faire l assistant']),
    'notifications': (['trop', 'recois', 'couper', 'desactiver'], ['je recois trop de notifications', 'couper les notifications']),
    'roles': (['difference', 'differences', 'roles'], ['difference entre les roles', 'quels sont les roles']),
    'journal': (['supprime', 'modifie', 'historique', 'qui'], ['qui a supprime ce risque', 'qui a modifie', 'historique des actions des utilisateurs']),
    'import_export_admin': (['utilisateurs'], ['importer des utilisateurs depuis excel', 'importer des utilisateurs']),
    'modeles_permissions': (['type'], ['profil de droits type', 'modele de droits']),
    'fiches_risque_parametrage': (['joindre', 'pieces'], ['quels fichiers on peut joindre', 'types de fichiers autorises']),
    'heure_devise': (['decalee', 'decale'], ['l heure est decalee', 'l heure n est pas la bonne']),
    'guide-campagnes': (['lancer'], ['lancer une campagne d evaluation', 'lancer une campagne']),
    'campagne': (['lancer'], ['lancer une campagne d evaluation', 'lancer une campagne']),
    'kri_fiabilite': (['fiabilite', 'fiable', 'qualite'], ['fiabilite des donnees kri', 'les donnees du kri sont elles fiables']),
    'c2n_principe': (['quoi', 'principe'], ['c est quoi le controle n2', 'c est quoi le c2n', 'controle interne de second niveau']),
    'c2n_planification': (['planifier', 'second', 'niveau'], ['planifier les controles de second niveau', 'planifier les controles n2']),
    'c2n_nc': ([], ['une non conformite c2n', 'traiter une non conformite']),
    'questionnaires': (['creer', 'envoyer', 'agences', 'diffuser', 'sondage', 'enquete'], ['creer un questionnaire', 'nouveau questionnaire']),
    'constatation': (['ajouter', 'cause', 'causes', 'consequence', 'consequences', 'critere'], ['ajouter une constatation', 'saisir une constatation']),
    'rapport_audit': (['rediger', 'ecrire'], ['rediger le rapport d audit', 'ecrire le rapport d audit']),
    'audit_tableau': ([], ['tableau de bord audit', 'tableau de bord de l audit']),
    'ia_fonctions': (['fait', 'peut'], ['que fait l ia', 'a quoi sert l ia']),
    'enregistrement': (['modifications', 'enregistrees'], ['mes modifications ne sont pas enregistrees', 'ca ne s enregistre pas']),
    'dashboard': ([], ['tableau de bord', 'mon tableau de bord', 'page d accueil']),
    'export': ([], ['exporter en excel', 'exporter mes donnees']),
    'support': ([], ['contacter le support', 'ouvrir un ticket']),
    'support_page': ([], ['page support', 'ou est la page support']),
    'alertes_incidents': (['critique', 'critiques', 'grave'], []),
    'dashboard_strategique': (['direction', 'generale', 'dg', 'synthese'], ['indicateurs pour la direction generale']),
    'plans_regles': (['100'], []),
    'dispositif_creer': (['cle', 'reduire', 'mesure', 'attenuer'], []),
    'email_non_recu': (['arrive', 'recu', 'jamais', 'spam'], []),
    'utilisateur_creer': (['ajout'], ['ajout utilisateur', 'ajouter un utilisateur']),
    'guide-kri': (['koi', 'quoi'], ['c est quoi un kri', 'kri c koi', 'kri c est quoi']),
}
for _a in ARTICLES:
    if _a['id'] in _RETIRER_MOTS:
        _a['mots'] = [m for m in _a['mots'] if m not in _RETIRER_MOTS[_a['id']]]
    if _a['id'] in _AJOUTER:
        _m, _q = _AJOUTER[_a['id']]
        _a['mots'] = list(_a['mots']) + [m for m in _m if m not in _a['mots']]
        _a['questions'] = list(_a['questions']) + [q for q in _q if q not in _a['questions']]

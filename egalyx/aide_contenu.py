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


GLOSSAIRE = [
    ('Appétence au risque', 'Niveau de risque que la direction accepte de prendre pour atteindre ses objectifs ; au-delà, des mesures sont exigées.'),
    ('BIA', 'Business Impact Analysis : analyse des conséquences d’un arrêt d’activité, qui fixe RTO et RPO.'),
    ('Bénéficiaire effectif', 'Personne physique qui, in fine, possède ou contrôle un client ou un tiers.'),
    ('C2N', 'Contrôle interne de niveau 2 : contrôles réalisés par une fonction indépendante des opérationnels.'),
    ('Campagne de contrôle', 'Test d’un contrôle sur un échantillon de dossiers, qui donne un taux de conformité.'),
    ('Cartographie des risques', 'Ensemble des risques d’un périmètre, évalués et positionnés selon impact et probabilité.'),
    ('Constatation', 'Écart relevé par l’auditeur entre la situation observée et la règle attendue.'),
    ('Criblage', 'Comparaison du nom d’un tiers aux listes de sanctions et de gel des avoirs.'),
    ('Criticité', 'Niveau d’un risque (Faible, Moyen, Élevé, Critique) obtenu à partir de son score.'),
    ('Dispositif de maîtrise (DMR)', 'Contrôle ou mesure qui réduit la probabilité ou l’impact d’un risque.'),
    ('Escalade', 'Remontée automatique d’un incident non traité dans les délais vers un niveau hiérarchique supérieur.'),
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

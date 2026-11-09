"""
egalyx/modules_client.py — modules activés PAR CLIENT, en un seul endroit.

Principe (simple) : un utilisateur peut faire une chose si
    1) le module correspondant est activé pour SON organisation, ET
    2) il a la permission correspondante (rôle ou réglage individuel).

Le super admin coche les modules d'un client sur une seule page (avec des profils
prêts à l'emploi : « Cabinet d'audit », « Gestion des risques », etc.).
Tant qu'aucun choix n'a été fait pour un client, rien ne change : il garde l'accès
actuel (formule + permissions). Le contrôle se fait dans User.has_permission :
menus, pages, recherche et API internes en tiennent compte automatiquement.
"""
import os
from flask import Blueprint, flash, redirect, render_template, request, url_for

from egalyx.commun import journaliser, super_admin_requis

bp = Blueprint('modules_client', __name__, url_prefix='/super-admin/client')

# (code, nom, description, groupe, permissions contrôlées, clés de module de la formule)
CATALOGUE = [
    ('cartographie', 'Cartographie des risques', 'Risques, évaluations brut / net, matrices, bibliothèque sectorielle',
     'Gestion des risques', ('can_manage_risks', 'can_validate_risks', 'can_confirm_evaluations'), ('cartographie',)),
    ('kri', 'Indicateurs de risque (KRI)', 'Indicateurs, seuils, mesures et alertes',
     'Gestion des risques', ('can_manage_kri',), ('suivi_kri',)),
    ('incidents', 'Incidents', 'Déclaration, escalade, résolution des incidents',
     'Gestion des risques', ('can_manage_incidents', 'can_view_incidents', 'can_escalate_incidents', 'can_resolve_incidents'), ('incidents',)),
    ('pca', 'Continuité d’activité (PCA)', 'Plans de continuité et tests',
     'Gestion des risques', ('can_manage_bcp', 'can_view_bcp', 'can_test_bcp'), ('pca',)),
    ('pilotage', 'Pilotage de la direction', 'Tableau de bord stratégique et rapport au comité d’audit',
     'Gestion des risques', ('can_view_tableau_bord_strategique', 'can_view_rapport_comite'), ()),
    ('processus', 'Processus et logigrammes', 'Processus, organigrammes, contrôles rattachés',
     'Contrôle interne', ('can_manage_logigram',), ('gestion_processus',)),
    ('campagnes', 'Campagnes de contrôle', 'Campagnes et tests de contrôles',
     'Contrôle interne', ('can_manage_campaigns', 'can_view_campaigns', 'can_conduct_campaigns'), ('campagnes_controle',)),
    ('controle_n2', 'Contrôle interne de 2e niveau', 'Référentiel, planification et exécution des contrôles N2',
     'Contrôle interne', ('can_view_controle_interne_n2', 'can_manage_controle_interne_n2'), ()),
    ('qualite', 'Qualité', 'Plans et audits qualité',
     'Contrôle interne', ('can_manage_quality', 'can_manage_quality_plans', 'can_manage_quality_audits'), ('qualite',)),
    ('audit', 'Audit interne', 'Missions, feuilles de travail, constatations, recommandations, rapports',
     'Audit interne', ('can_manage_audit', 'can_view_reports'), ('audit_interne',)),
    ('programme_audit', 'Programme d’audit', 'Planification pluriannuelle des missions',
     'Audit interne', ('can_manage_audit_program',), ('programme_audit',)),
    ('plans_action', 'Plans d’action', 'Suivi des actions correctives',
     'Audit interne', ('can_manage_action_plans', 'can_view_action_plans'), ('plans_action',)),
    ('recommandations', 'Registre des recommandations', 'Recommandations d’audit, du N2 et externes (CAC, régulateur), suivi et clôture',
     'Audit interne', ('can_view_recommandations', 'can_manage_recommandations'), ()),
    ('questionnaires', 'Questionnaires', 'Questionnaires d’autoévaluation et réponses',
     'Audit interne', ('can_manage_questionnaires', 'can_create_questionnaires', 'can_view_responses', 'can_export_responses'),
     ('questionnaires_avances',)),
    ('veille', 'Veille réglementaire', 'Textes, impacts, actions de conformité',
     'Conformité', ('can_manage_regulatory', 'can_view_veille', 'can_create_veille', 'can_edit_veille', 'can_delete_veille',
                    'can_approve_veille'), ('veille_reglementaire',)),
    ('tiers', 'Tiers et LCB-FT', 'KYC, vigilance anti-blanchiment, criblage sanctions, fournisseurs',
     'Conformité', ('can_view_tiers', 'can_manage_tiers'), ()),
    ('alertes', 'Dispositif d’alerte', 'Signalements (Sapin II), lien public et suivi confidentiel',
     'Conformité', ('can_manage_alertes',), ()),
    ('ia', 'Analyse IA', 'Analyses assistées par IA',
     'Outils', ('can_use_ia_analysis',), ('analyse_ia',)),
    ('api', 'API et intégrations', 'Clés API, webhooks, journaux d’appels',
     'Outils', ('can_manage_api', 'can_manage_webhooks', 'can_view_api_logs'), ('api_avancee',)),
    ('support', 'Tickets de support', 'Demandes au support Egalyx',
     'Outils', ('can_view_tickets', 'can_manage_tickets'), ('tickets_support',)),
]
MODULES = {m[0]: m for m in CATALOGUE}
GROUPES = ['Gestion des risques', 'Contrôle interne', 'Audit interne', 'Conformité', 'Outils']
MODULE_DE_PERMISSION = {p: m[0] for m in CATALOGUE for p in m[4]}

PROFILS = {
    'audit': ('Cabinet ou service d’audit', 'Missions d’audit, programme, recommandations et plans d’action',
              ('audit', 'programme_audit', 'plans_action', 'questionnaires', 'pilotage', 'support')),
    'risques': ('Gestion des risques', 'Cartographie, KRI, incidents, plans d’action, pilotage',
                ('cartographie', 'kri', 'incidents', 'plans_action', 'pilotage', 'support')),
    'controle': ('Contrôle interne', 'Risques, processus, campagnes et contrôles de 2e niveau',
                 ('cartographie', 'processus', 'campagnes', 'controle_n2', 'plans_action', 'pilotage', 'support')),
    'conformite': ('Conformité et LCB-FT', 'Veille, tiers, alerte, risques de conformité',
                   ('cartographie', 'veille', 'tiers', 'alertes', 'plans_action', 'pilotage', 'support')),
    'complet': ('Suite complète', 'Tous les modules', tuple(MODULES)),
}


def modules_du_client(client):
    """Ensemble des codes de modules actifs, ou None (= pas de restriction).
    1. Choix explicite du super admin pour ce client (page « Modules » du client) ;
    2. à défaut, les modules de sa formule d'abonnement (avant : la formule était ignorée,
       un client sans un module dans sa formule le voyait quand même) ;
    3. sans formule renseignée : pas de restriction.
    EGALYX_MODULES_PAR_FORMULE=0 rétablit l'ancien comportement (formule ignorée)."""
    if client is None:
        return None
    choix = getattr(client, 'modules_actifs', None)
    if choix:
        return {code for code, actif in choix.items() if actif and code in MODULES}
    if os.environ.get('EGALYX_MODULES_PAR_FORMULE', '1') == '1':
        formule = getattr(client, 'formule', None)
        if formule is not None and getattr(formule, 'modules', None):
            return modules_depuis_formule(formule)
    return None


def permission_autorisee_par_module(user, permission):
    """False seulement si la permission appartient à un module explicitement désactivé pour le client."""
    module = MODULE_DE_PERMISSION.get(permission)
    if module is None:
        return True                      # permission transversale (tableau de bord, utilisateurs, paramètres…)
    try:
        actifs = modules_du_client(getattr(user, 'client', None))
    except Exception:
        return True
    return actifs is None or module in actifs


def modules_depuis_formule(formule):
    """Proposition de départ à partir des modules de la formule d'abonnement."""
    if formule is None or not getattr(formule, 'modules', None):
        return set(MODULES)
    actifs = set()
    for code, _n, _d, _g, _p, cles in CATALOGUE:
        if not cles or any(formule.modules.get(k) for k in cles):
            actifs.add(code)
    return actifs


@bp.route('/<int:client_id>/modules', methods=['GET', 'POST'])
@super_admin_requis
def page(client_id):
    from models import db, Client, User, marquer_json_modifie
    client = db.session.get(Client, client_id)
    if client is None:
        return redirect(url_for('super_admin_clients'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'aucune_restriction':
            client.modules_actifs = None
            message = 'Restriction retirée : le client retrouve tous les modules permis par sa formule et ses permissions.'
        else:
            coches = {c for c in request.form.getlist('modules') if c in MODULES}
            if not coches:
                flash('Cochez au moins un module.', 'warning')
                return redirect(url_for('.page', client_id=client_id))
            avant = modules_du_client(client)
            client.modules_actifs = {c: (c in coches) for c in MODULES}
            nouveaux = coches - (avant if avant is not None else set())
            n_admins = donner_modules_aux_admins(client, nouveaux)
            message = f'{len(coches)} module(s) activé(s) pour {client.nom}. Le changement est immédiat pour tous ses utilisateurs.'
            if n_admins:
                message += f" Les administrateurs de l'organisation ({n_admins}) reçoivent les droits des modules ajoutés."
        marquer_json_modifie(client, 'modules_actifs')
        journaliser('modules_client_modifies', {'modules': sorted(modules_du_client(client) or [])}, client_id=client.id)
        db.session.commit()
        flash(message, 'success')
        return redirect(url_for('.page', client_id=client_id))
    actifs = modules_du_client(client)
    nb_utilisateurs = User.query.filter_by(client_id=client.id, is_active=True).count()
    return render_template('egalyx/modules_client.html', client=client, actifs=actifs,
                           proposition=actifs if actifs is not None else modules_depuis_formule(getattr(client, 'formule', None)),
                           catalogue=CATALOGUE, groupes=GROUPES, profils=PROFILS, nb_utilisateurs=nb_utilisateurs)


# Anciennes clés de module utilisées par les contrôles « formule » d'app.py → code du catalogue.
CLE_FORMULE_VERS_MODULE = {
    'suivi_kri': 'kri', 'kri': 'kri',
    'cartographie': 'cartographie', 'risques': 'cartographie', 'matrices_risque': 'cartographie',
    'audit_interne': 'audit', 'audit': 'audit', 'programme_audit': 'programme_audit',
    'processus': 'processus', 'logigrammes': 'processus', 'gestion_processus': 'processus',
    'veille': 'veille', 'veille_reglementaire': 'veille',
    'campagnes': 'campagnes', 'campagnes_controle': 'campagnes',
    'questionnaires': 'questionnaires', 'questionnaires_avances': 'questionnaires',
    'incidents': 'incidents', 'pca': 'pca', 'qualite': 'qualite', 'plans_action': 'plans_action',
    'analyse_ia': 'ia', 'ia_analyse': 'ia',
}


def _brancher_formule():
    """Les anciens contrôles « module inclus dans la formule ? » d'app.py ignoraient le choix de modules fait
    par le super admin : un module activé pour le client apparaissait dans le menu mais affichait
    « Ce module n'est pas inclus dans votre formule ». Ils suivent désormais la même règle que le menu
    (modules_du_client : choix du super admin, sinon formule)."""
    try:
        from models import FormuleAbonnement
    except ImportError:
        return
    origine = getattr(FormuleAbonnement, 'can_access_module', None)
    if origine is None or getattr(origine, '_egalyx', False):
        return

    def can_access_module(self, module_code):
        code = CLE_FORMULE_VERS_MODULE.get(module_code)
        try:
            from flask import has_request_context
            from flask_login import current_user
            if code and has_request_context() and getattr(current_user, 'is_authenticated', False):
                client = getattr(current_user, 'client', None)
                if client is not None and getattr(client, 'formule', None) is self:
                    actifs = modules_du_client(client)
                    return True if actifs is None else code in actifs
        except Exception:
            pass
        return origine(self, module_code)
    can_access_module._egalyx = True
    FormuleAbonnement.can_access_module = can_access_module


# Permissions de gestion qu'un administrateur d'organisation a d'office (cf. models.User.has_permission).
PERMISSIONS_ADMIN_MODULES = (
    'can_manage_risks', 'can_validate_risks', 'can_confirm_evaluations', 'can_manage_kri',
    'can_manage_audit', 'can_manage_audit_program', 'can_manage_action_plans', 'can_view_action_plans',
    'can_view_controle_interne_n2', 'can_manage_controle_interne_n2', 'can_use_ia_analysis',
    'can_view_tableau_bord_strategique',
)


def permissions_du_module(code):
    for c, _n, _d, _g, perms, _cles in CATALOGUE:
        if c == code:
            return perms
    return ()


def _est_admin_organisation(u):
    return getattr(u, 'role', None) == 'admin' or bool(getattr(u, 'is_client_admin', False))


def donner_modules_aux_admins(client, codes):
    """Un administrateur d'organisation a les droits de tous les modules activés pour son organisation :
    quand le super admin active un module, ses administrateurs en reçoivent les permissions."""
    from models import User
    if not codes:
        return 0
    n = 0
    for u in User.query.filter_by(client_id=client.id, is_active=True).all():
        if not _est_admin_organisation(u) or not hasattr(u, 'permissions'):
            continue
        p = dict(u.permissions or {})
        change = False
        for code in codes:
            for perm in permissions_du_module(code):
                if not p.get(perm):
                    p[perm] = True
                    change = True
        if change:
            u.permissions = p
            n += 1
    return n


def _reparer_permissions_admins(app):
    """Une seule fois : rend aux administrateurs d'organisation les permissions des modules actifs pour leur client
    que l'ancienne correction automatique « selon la formule » leur avait retirées (ex. KRI activé par le super
    admin mais absent de la formule → « Accès non autorisé au module liste_kri »)."""
    from egalyx.ia import reglages, ecrire_reglage
    with app.app_context():
        try:
            if reglages().get('reparation_permissions_admins_modules_v2'):
                return
            from models import db, Client
            n = 0
            for client in Client.query.all():
                actifs = modules_du_client(client)
                n += donner_modules_aux_admins(client, set(actifs) if actifs is not None else set(MODULES))
            db.session.commit()
            ecrire_reglage('reparation_permissions_admins_modules_v2', True)
            if n:
                app.logger.info('Permissions de modules rendues à %s administrateur(s).', n)
        except Exception as e:  # base pas encore à jour : on réessaiera au prochain démarrage
            try:
                from models import db as _db
                _db.session.rollback()
            except Exception:
                pass
            app.logger.warning('Réparation des permissions des administrateurs reportée : %s', e)


def enregistrer(app):
    app.register_blueprint(bp)
    app.before_request(bloquer_modules_inactifs)
    _brancher_formule()
    _reparer_permissions_admins(app)
    app.jinja_env.globals['modules_du_client'] = modules_du_client

    def module_autorise(permission):
        from flask_login import current_user
        if not getattr(current_user, 'is_authenticated', False) or getattr(current_user, 'role', None) == 'super_admin':
            return True
        return permission_autorisee_par_module(current_user, permission)
    app.jinja_env.globals['module_autorise'] = module_autorise


# ====================================================================== blocage par adresse
# Un module désactivé est masqué dans les menus (permissions) ET inaccessible par son adresse.
MODELE_MODULE = {
    'cartographie': ('Risque', 'Cartographie', 'EvaluationRisque', 'CampagneEvaluation', 'DispositifMaitrise',
                     'DemandeReevaluation', 'ActualisationCartographie', 'DocumentDispositif', 'VerificationDispositif'),
    'kri': ('KRI', 'MesureKRI', 'SourceDonnee', 'SourceKRILink', 'CollecteDonnee', 'AlerteCollecte', 'FichierKRI'),
    'incidents': ('Incident', 'IncidentHistorique'),
    'pca': ('PlanContinuiteActivite', 'ActionPCA', 'ExercicePCA', 'DocumentPCA'),
    'processus': ('Processus', 'ProcessusActivite', 'ElementLogigramme', 'LienLogigramme', 'EtapeProcessus',
                  'SousEtapeProcessus', 'ZoneRisqueProcessus', 'ControleProcessus', 'ProcessusMetier',
                  'RisqueElementLogigramme', 'ControleElementLogigramme'),
    'campagnes': ('CampagneControle', 'FichierCampagneControle'),
    'controle_n2': ('ProgrammeControle', 'MissionControle', 'TacheControle', 'ReferentielControle', 'PlanificationControle',
                    'ExecutionControle', 'ValidationControle', 'RecommandationC2N', 'PlanActionC2N', 'SousActionPlanC2N',
                    'NonConformiteC2N'),
    'qualite': ('AuditQualite', 'GrilleAuditQualite', 'ReponseAuditQualite', 'NonConformite', 'ReunionQualite',
                'FormationQualite', 'ActionAmeliorationQualite', 'FichierPlanQualite', 'PlanQualiteFonction'),
    'audit': ('Audit', 'Constatation', 'Recommandation', 'FeuilleTravail', 'MatriceMaturite', 'MissionAudit',
              'TestControleFeuille', 'CommentaireFeuille', 'FichierRapport'),
    'programme_audit': ('ProgrammeAudit', 'PlanPluieAudit'),
    'plans_action': ('PlanAction', 'SousAction', 'EtapePlanAction', 'CommentairePlanAction', 'FichierPlanAction'),
    'questionnaires': ('Questionnaire', 'Question', 'ReponseQuestionnaire'),
    'veille': ('VeilleReglementaire', 'ActionConformite', 'VeilleDocument'),
}
MODULE_DU_MODELE = {m: code for code, modeles in MODELE_MODULE.items() for m in modeles}
# Pages sans identifiant (listes, créations) : début d'adresse -> module
PREFIXES = [
    ('/liste_logigrammes', 'processus'), ('/logigramme', 'processus'), ('/editer_logigramme', 'processus'),
    ('/api/logigramme', 'processus'), ('/api/element/', 'processus'), ('/api/lien/', 'processus'),
    ('/api/processus-metier', 'processus'),
    ('/archives_logigrammes', 'processus'), ('/processus', 'processus'), ('/api/processus', 'processus'),
    ('/audits', 'audit'), ('/audit/', 'audit'), ('/feuille-travail', 'audit'), ('/rapports-audit', 'audit'),
    ('/programme-audit', 'programme_audit'), ('/programmes-audit', 'programme_audit'), ('/mission-audit', 'programme_audit'),
    ('/recommandations', 'recommandations'), ('/logigrammes-suivi', 'processus'), ('/audit-suivi', 'audit'),
    ('/plan-action-independant', 'plans_action'), ('/plan-action-risque', 'plans_action'), ('/sous-action', 'plans_action'),
    ('/campagnes-controle', 'campagnes'), ('/campagne-controle', 'campagnes'),
    ('/incidents', 'incidents'), ('/incident/', 'incidents'), ('/kri', 'kri'), ('/veille', 'veille'),
    ('/questionnaire', 'questionnaires'), ('/pca', 'pca'), ('/c2n', 'controle_n2'), ('/qualite', 'qualite'),
    ('/cartographie', 'cartographie'), ('/risque/', 'cartographie'), ('/risques', 'cartographie'),
    ('/api/plan-action', 'plans_action'), ('/plan-action', 'plans_action'), ('/plans-action', 'plans_action'),
    ('/api/kri', 'kri'), ('/api/incidents', 'incidents'), ('/api/veille', 'veille'), ('/organismes', 'veille'),
    ('/api/pca', 'pca'), ('/api/qualite', 'qualite'), ('/api/questionnaire', 'questionnaires'),
    ('/controle/programme', 'controle_n2'), ('/controle/mission', 'controle_n2'),
    ('/controle/campagne', 'campagnes'), ('/controle/fichier', 'campagnes'), ('/controle/statistiques-globales', 'campagnes'),
    ('/operateur/campagne', 'campagnes'), ('/operateur/fichier-campagne', 'campagnes'),
]


def module_de_la_requete(endpoint, chemin):
    from egalyx.cloisonnement_carte import CARTE
    for nom_modele in (CARTE.get(endpoint) or {}).values():
        if nom_modele in MODULE_DU_MODELE:
            return MODULE_DU_MODELE[nom_modele]
    for prefixe, code in PREFIXES:
        if chemin.startswith(prefixe):
            return code
    return None


def bloquer_modules_inactifs():
    from flask import jsonify, request
    from flask_login import current_user
    if not getattr(current_user, 'is_authenticated', False) or getattr(current_user, 'role', None) == 'super_admin':
        return None
    if not request.endpoint or '.' in request.endpoint:          # modules egalyx : protégés par leurs permissions
        return None
    try:
        actifs = modules_du_client(getattr(current_user, 'client', None))
    except Exception:
        return None
    if actifs is None:
        return None
    module = module_de_la_requete(request.endpoint, request.path)
    if module is None or module in actifs:
        return None
    nom = MODULES[module][1]
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({'success': False, 'error': f'Module « {nom} » non activé pour votre organisation'}), 403
    flash(f"Le module « {nom} » n'est pas activé pour votre organisation.", 'warning')
    return redirect(url_for('dashboard'))

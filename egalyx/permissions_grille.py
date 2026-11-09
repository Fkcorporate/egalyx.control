"""
egalyx/permissions_grille.py — une seule liste de permissions, cohérente avec les modules.

- La grille des permissions (page « Permissions » d'un utilisateur) est construite à partir du catalogue des
  modules (egalyx/modules_client.CATALOGUE) : chaque module apparaît avec TOUTES ses permissions, plus les
  permissions transversales (tableau de bord, directions, utilisateurs, administration, intégrations).
- Un module non souscrit par l'organisation apparaît grisé : ses cases ne peuvent pas être cochées.
- À l'enregistrement (quel que soit l'écran : admin client, super admin, import…), les permissions d'un module
  non souscrit sont remises à « non » ; « gérer » entraîne « voir » quand les deux existent.
"""
from egalyx.modules_client import CATALOGUE, MODULES, MODULE_DE_PERMISSION, modules_du_client

LIBELLES = {
    # transversal
    'can_view_dashboard': 'Voir le tableau de bord', 'can_export_data': 'Exporter des données',
    'can_view_departments': 'Voir les directions et services', 'can_manage_departments': 'Gérer les directions et services',
    'can_access_all_departments': 'Accès à toutes les directions', 'can_archive_data': 'Archiver des données',
    'can_delete_data': 'Supprimer des données', 'can_sign_documents': 'Signer les documents',
    'can_view_users_list': 'Voir la liste des utilisateurs', 'can_create_users': 'Créer des utilisateurs',
    'can_edit_users': 'Modifier des utilisateurs', 'can_deactivate_users': 'Désactiver des utilisateurs',
    'can_delete_users': 'Supprimer des utilisateurs', 'can_manage_users': 'Gérer les utilisateurs',
    'can_manage_permissions': 'Gérer les permissions', 'can_block_users': 'Bloquer des utilisateurs',
    'can_manage_settings': 'Gérer les paramètres généraux', 'can_manage_lists': 'Gérer les listes déroulantes',
    'can_manage_fields': 'Gérer les champs personnalisés', 'can_manage_files': 'Gérer les fichiers',
    'can_manage_templates': 'Gérer les modèles de permissions', 'can_manage_import_export': 'Gérer les imports et exports',
    # modules
    'can_manage_risks': 'Gérer les risques (cartographie)', 'can_validate_risks': 'Valider les risques',
    'can_confirm_evaluations': 'Confirmer les évaluations', 'can_manage_kri': 'Gérer les indicateurs KRI',
    'can_manage_incidents': 'Gérer les incidents', 'can_view_incidents': 'Voir les incidents',
    'can_escalate_incidents': 'Escalader les incidents', 'can_resolve_incidents': 'Résoudre les incidents',
    'can_manage_bcp': 'Gérer les plans de continuité', 'can_view_bcp': 'Voir les plans de continuité',
    'can_test_bcp': 'Tester les plans de continuité', 'can_view_tableau_bord_strategique': 'Tableau de bord stratégique',
    'can_view_rapport_comite': "Rapport au comité d'audit", 'can_manage_logigram': 'Gérer les logigrammes et processus',
    'can_manage_campaigns': 'Gérer les campagnes de contrôle', 'can_view_campaigns': 'Voir les campagnes de contrôle',
    'can_conduct_campaigns': 'Réaliser les campagnes de contrôle',
    'can_view_controle_interne_n2': 'Voir le contrôle interne N2', 'can_manage_controle_interne_n2': 'Gérer le contrôle interne N2',
    'can_manage_quality': 'Gérer la qualité', 'can_manage_quality_plans': 'Gérer les plans qualité',
    'can_manage_quality_audits': 'Gérer les audits qualité', 'can_manage_audit': 'Gérer les audits',
    'can_view_reports': "Voir les rapports d'audit", 'can_manage_audit_program': "Gérer le programme d'audit",
    'can_manage_action_plans': "Gérer les plans d'action", 'can_view_action_plans': "Voir les plans d'action",
    'can_view_recommandations': 'Voir le registre des recommandations',
    'can_manage_recommandations': 'Gérer les recommandations (externes, clôtures)',
    'can_manage_questionnaires': 'Gérer les questionnaires', 'can_create_questionnaires': 'Créer des questionnaires',
    'can_view_responses': 'Voir les réponses', 'can_export_responses': 'Exporter les réponses',
    'can_manage_regulatory': 'Gérer la veille réglementaire', 'can_view_veille': 'Voir la veille',
    'can_create_veille': 'Créer des veilles', 'can_edit_veille': 'Modifier des veilles', 'can_delete_veille': 'Supprimer des veilles',
    'can_approve_veille': 'Approuver les veilles', 'can_view_tiers': 'Voir les tiers (LCB-FT)', 'can_manage_tiers': 'Gérer les tiers',
    'can_manage_alertes': "Référent du dispositif d'alerte", 'can_use_ia_analysis': "Utiliser l'analyse IA",
    'can_manage_api': 'Gérer les clés API', 'can_manage_webhooks': 'Gérer les webhooks', 'can_view_api_logs': 'Consulter les journaux API',
    'can_view_tickets': 'Voir les tickets de support', 'can_manage_tickets': 'Gérer les tickets de support',
}

TRANSVERSAL = [
    ('general', 'Général', 'fa-sliders', ('can_view_dashboard', 'can_export_data', 'can_view_departments', 'can_manage_departments',
                                          'can_access_all_departments', 'can_archive_data', 'can_delete_data', 'can_sign_documents')),
    ('utilisateurs', 'Utilisateurs et administration', 'fa-users-gear',
     ('can_view_users_list', 'can_create_users', 'can_edit_users', 'can_deactivate_users', 'can_delete_users', 'can_manage_users',
      'can_manage_permissions', 'can_block_users', 'can_manage_settings', 'can_manage_lists', 'can_manage_fields',
      'can_manage_files', 'can_manage_templates', 'can_manage_import_export')),
]
ICONES = {'cartographie': 'fa-map', 'kri': 'fa-gauge-high', 'incidents': 'fa-triangle-exclamation', 'pca': 'fa-life-ring',
          'pilotage': 'fa-chart-line', 'processus': 'fa-project-diagram', 'campagnes': 'fa-clipboard-list',
          'controle_n2': 'fa-user-check', 'qualite': 'fa-medal', 'audit': 'fa-magnifying-glass', 'programme_audit': 'fa-calendar-days',
          'plans_action': 'fa-list-check', 'recommandations': 'fa-clipboard-check', 'questionnaires': 'fa-square-poll-vertical',
          'veille': 'fa-scale-balanced', 'tiers': 'fa-handshake', 'alertes': 'fa-bullhorn', 'ia': 'fa-robot', 'api': 'fa-plug',
          'support': 'fa-ticket'}
# « gérer » donne « voir »
IMPLIQUE = {'can_manage_recommandations': 'can_view_recommandations', 'can_manage_controle_interne_n2': 'can_view_controle_interne_n2',
            'can_manage_campaigns': 'can_view_campaigns', 'can_conduct_campaigns': 'can_view_campaigns',
            'can_manage_incidents': 'can_view_incidents', 'can_manage_bcp': 'can_view_bcp', 'can_manage_tickets': 'can_view_tickets',
            'can_manage_tiers': 'can_view_tiers', 'can_manage_action_plans': 'can_view_action_plans',
            'can_manage_regulatory': 'can_view_veille', 'can_manage_users': 'can_view_users_list'}


def libelle(code):
    return LIBELLES.get(code, code.replace('can_', '').replace('_', ' ').capitalize())


def toutes():
    """Toutes les permissions gérables, sans doublon, dans l'ordre d'affichage."""
    vues, out = set(), []
    for _c, _t, _i, perms in TRANSVERSAL[:1]:
        for p in perms:
            if p not in vues:
                vues.add(p); out.append(p)
    for code, *_r in CATALOGUE:
        for p in MODULES[code][4]:
            if p not in vues:
                vues.add(p); out.append(p)
    for _c, _t, _i, perms in TRANSVERSAL[1:]:
        for p in perms:
            if p not in vues:
                vues.add(p); out.append(p)
    return out


def liste_plate():
    return [(p, libelle(p)) for p in toutes()]


def grille(user, client):
    """Sections pour l'affichage : [{'code', 'titre', 'icone', 'groupe', 'actif', 'perms': [(code, libelle, coche)]}]."""
    actifs = modules_du_client(client)
    def coche(p):
        try:
            return bool(user.has_permission(p))
        except Exception:
            return False
    sections = []
    code, titre, icone, perms = TRANSVERSAL[0]
    sections.append({'code': code, 'titre': titre, 'icone': icone, 'groupe': None, 'actif': True,
                     'perms': [(p, libelle(p), coche(p)) for p in perms]})
    vus = set(perms)
    for mcode, nom, _desc, groupe, perms_m, _cles in CATALOGUE:
        perms_m = [p for p in perms_m if p not in vus]
        vus.update(perms_m)
        if not perms_m:
            continue
        actif = actifs is None or mcode in actifs
        sections.append({'code': mcode, 'titre': nom, 'icone': ICONES.get(mcode, 'fa-cube'), 'groupe': groupe, 'actif': actif,
                         'perms': [(p, libelle(p), coche(p) and actif) for p in perms_m]})
    code, titre, icone, perms = TRANSVERSAL[1]
    sections.append({'code': code, 'titre': titre, 'icone': icone, 'groupe': None, 'actif': True,
                     'perms': [(p, libelle(p), coche(p)) for p in perms if p not in vus]})
    return sections


def normaliser(permissions, client, anciennes=None):
    """« Gérer » => « voir ». Modules non activés pour l'organisation : la valeur ne peut pas être changée
    (on garde l'ancienne) mais n'est plus effacée : si le super admin réactive le module, l'utilisateur retrouve
    ses droits. Tant que le module est inactif, models.User.has_permission répond « non » quoi qu'il arrive."""
    p = dict(permissions or {})
    actifs = modules_du_client(client)
    if actifs is not None:
        avant = dict(anciennes or {})
        for code in list(p.keys()):
            module = MODULE_DE_PERMISSION.get(code)
            if module and module not in actifs:
                if code in avant:
                    p[code] = avant[code]
                else:
                    p.pop(code, None)
    for fort, faible in IMPLIQUE.items():
        if p.get(fort):
            module = MODULE_DE_PERMISSION.get(fort)
            if actifs is None or module is None or module in actifs:
                p[faible] = True
    return p


def _avant_flush(session, _ctx, _inst):
    """Seule règle appliquée à l'enregistrement : « gérer » => « voir ». Les droits des modules inactifs ne sont
    plus effacés : ils restent sans effet tant que le module est désactivé."""
    import models as m
    for u in list(session.new) + list(session.dirty):
        if not isinstance(u, m.User) or getattr(u, 'role', None) == 'super_admin' or not u.client_id:
            continue
        p = dict(u.permissions or {})
        nouveau = dict(p)
        for fort, faible in IMPLIQUE.items():
            if nouveau.get(fort):
                nouveau[faible] = True
        if nouveau != p:
            u.permissions = nouveau


def enregistrer(app):
    import models as m
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    if not getattr(m, '_egalyx_perm_flush', False):
        event.listen(Session, 'before_flush', _avant_flush)
        m._egalyx_perm_flush = True
    app.jinja_env.globals['grille_permissions'] = grille

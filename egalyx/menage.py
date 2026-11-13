"""
egalyx/menage.py — fonctions retirées de la navigation, sans rien supprimer en base.

1. Ancien module « programmes / missions / tâches de contrôle » (/controle/programme…, /controle/mission…,
   /controle/tache…) : remplacé par le contrôle interne N2 (référentiel → planification → exécution → validation)
   et les campagnes de contrôle. Ses adresses renvoient vers la planification N2, avec un message ; les données
   existantes restent en base (tables programmes_controle, missions_controle, taches_controle).
2. Pages de test (/test-…) : réservées au super admin, introuvables (404) pour tous les autres.
3. Routes de réparation et de mise au point (/fix…, /debug…, /test-…, /emergency…, /force-fix…) : introuvables (404)
   pour TOUT LE MONDE, super admin compris. Beaucoup modifiaient des données en masse sur un simple lien (GET).
   Le blocage se fait par la forme de l'adresse : une route de ce type ajoutée plus tard est bloquée d'office.
   Seules restent ouvertes, au super admin uniquement, celles qu'un bouton de l'espace super admin utilise
   (OUTILS_SUPER_ADMIN). Réouverture d'urgence, le temps d'une intervention : EGALYX_ROUTES_REPARATION=1.
"""
import os
import re

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user

ANCIEN_MODULE = {'liste_programmes', 'nouveau_programme', 'detail_programme', 'modifier_programme', 'activer_programme',
                 'archiver_programme', 'planning_programme', 'detail_mission_controle', 'soumettre_mission',
                 'valider_mission', 'nouvelle_tache', 'nouvelle_mission', 'realiser_tache', 'creer_mission_campagne'}


REPARATION = re.compile(r'/(fix[-_]|debug|test[-_]|emergency|force-fix|migrate-permissions)', re.I)
# Outils réellement utilisés par des boutons de l'espace super admin : super admin seulement
OUTILS_SUPER_ADMIN = {'fix_client_subdomain', 'super_admin_debug_filter', 'super_admin_fix_data_filter',
                      'fix_all_modules_mapping', 'fix_module_inconsistency', 'debug_module_state',
                      'debug_formule_modules', 'fix_plans_action_specific'}


def est_reparation(regle):
    return bool(REPARATION.search(regle or ''))


def _garde():
    ep = request.endpoint or ''
    regle = request.url_rule.rule if request.url_rule is not None else ''
    if est_reparation(regle) and os.environ.get('EGALYX_ROUTES_REPARATION') != '1':
        if ep not in OUTILS_SUPER_ADMIN or getattr(current_user, 'role', None) != 'super_admin':
            abort(404)
    if ep in ANCIEN_MODULE:
        flash("Les programmes et missions de contrôle sont remplacés par le contrôle interne N2 : référentiel des "
              "contrôles, planification, exécution et validation (et les campagnes de contrôle pour le terrain).", 'info')
        return redirect(url_for('c2n_liste_planifications'))
    if request.path.startswith('/test-') or request.path.startswith('/test_'):
        if getattr(current_user, 'role', None) != 'super_admin':
            abort(404)
    return None


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    # le nom de l'ancienne route « créer une mission depuis une campagne » varie selon les versions
    for r in app.url_map.iter_rules():
        if r.rule.startswith('/controle/campagne/') and r.rule.endswith('/creer_mission'):
            ANCIEN_MODULE.add(r.endpoint)
    app.before_request_funcs.setdefault(None, []).insert(0, _garde)
    exempter_controle_ancien(app, set(ANCIEN_MODULE))

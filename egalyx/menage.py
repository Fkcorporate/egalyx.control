"""
egalyx/menage.py — fonctions retirées de la navigation, sans rien supprimer en base.

1. Ancien module « programmes / missions / tâches de contrôle » (/controle/programme…, /controle/mission…,
   /controle/tache…) : remplacé par le contrôle interne N2 (référentiel → planification → exécution → validation)
   et les campagnes de contrôle. Ses adresses renvoient vers la planification N2, avec un message ; les données
   existantes restent en base (tables programmes_controle, missions_controle, taches_controle).
2. Pages de test (/test-…) : réservées au super admin, introuvables (404) pour tous les autres.
"""
from flask import abort, flash, redirect, request, url_for
from flask_login import current_user

ANCIEN_MODULE = {'liste_programmes', 'nouveau_programme', 'detail_programme', 'modifier_programme', 'activer_programme',
                 'archiver_programme', 'planning_programme', 'detail_mission_controle', 'soumettre_mission',
                 'valider_mission', 'nouvelle_tache', 'nouvelle_mission', 'realiser_tache', 'creer_mission_campagne'}


def _garde():
    ep = request.endpoint or ''
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

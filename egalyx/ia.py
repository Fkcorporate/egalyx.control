"""
egalyx/ia.py — interrupteur unique de toutes les fonctions d'intelligence artificielle.

L'IA est utilisable par un utilisateur si, et seulement si :
  1. elle est activée pour la PLATEFORME (super admin : Administration > Intelligence artificielle) ;
  2. le module « Analyse IA » est activé pour SON ORGANISATION (page Modules du client) ;
  3. il a la permission « Utiliser l'analyse IA » (can_use_ia_analysis).

Quand l'une des conditions manque, l'IA DISPARAÎT :
  - les pages et API dédiées à l'IA (52 adresses) sont bloquées ;
  - les analyses IA automatiques déclenchées par d'autres actions (création d'incident, synchronisation
    de la veille, assistant…) ne sont plus appelées : ces actions continuent sans IA ;
  - les boutons et liens d'IA sont retirés des pages ; l'assistant reste disponible mais répond
    uniquement à partir du centre d'aide et des données (sa partie ChatGPT est coupée).
Le réglage plateforme est enregistré dans instance/egalyx_reglages.json (pris en compte immédiatement,
par tous les processus du serveur).
"""
import functools
import json
import logging
import os
import sys

from flask import Blueprint, current_app, flash, has_request_context, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from egalyx.commun import journaliser, super_admin_requis

journal = logging.getLogger('egalyx.ia')
bp = Blueprint('ia', __name__, url_prefix='/super-admin/ia')


class IADesactivee(RuntimeError):
    """Levée par les services d'IA neutralisés : les appelants existants l'attrapent et continuent sans IA."""


# ------------------------------------------------------------------ réglage plateforme (fichier partagé)
_cache = {'mtime': None, 'valeurs': {}}


def _chemin():
    try:
        return os.path.join(current_app.instance_path, 'egalyx_reglages.json')
    except RuntimeError:
        return os.path.join(os.getcwd(), 'instance', 'egalyx_reglages.json')


def reglages():
    p = _chemin()
    try:
        m = os.path.getmtime(p)
    except OSError:
        return {}
    if _cache['mtime'] != m:
        try:
            with open(p, encoding='utf-8') as f:
                _cache['valeurs'] = json.load(f)
        except (OSError, ValueError):
            _cache['valeurs'] = {}
        _cache['mtime'] = m
    return _cache['valeurs']


def ecrire_reglage(cle, valeur):
    p = _chemin()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    v = dict(reglages())
    v[cle] = valeur
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(v, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)                      # écriture atomique : jamais de fichier à moitié écrit
    _cache['mtime'] = None


def ia_plateforme_active():
    if os.environ.get('EGALYX_IA', '1') == '0':          # coupure par variable d'environnement, prioritaire
        return False
    return bool(reglages().get('ia_active', True))


def ia_autorisee(u=None):
    """Les trois conditions (plateforme, organisation, permission) pour l'utilisateur courant."""
    if not ia_plateforme_active():
        return False
    if u is None:
        if not has_request_context():
            return True                     # tâche de fond : seul l'interrupteur plateforme s'applique
        u = current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    if getattr(u, 'role', None) == 'super_admin':
        return True
    verifier = getattr(u, 'has_permission', None)
    return bool(callable(verifier) and verifier('can_use_ia_analysis'))   # inclut le module « ia » du client


# ------------------------------------------------------------------ adresses dédiées à l'IA
ENDPOINTS_IA = {
    'analyse_ia_dashboard', 'generer_kris_ia', 'appliquer_suggestion_kri_ia', 'suggestions_kris_fallback',
    'ajuster_suggestion_kri_ia', 'creer_kri_ia_depuis_risque', 'analyse_ia_incident', 'dashboard_ia_incidents',
    'detecter_menaces_veille', 'analyser_veille_ia', 'api_suggerer_action_pca', 'api_suggerer_exercice_pca',
    'api_pca_suggestions_actions', 'api_pca_suggestions_exercices', 'analyse_ia_ultra', 'export_analyse_ia',
    'analyse_ia_cartographie', 'api_ia_rafraichir', 'api_ia_ignorer_suggestion', 'api_generer_objectifs_smart',
    'api_suggerer_description_plan', 'api_generer_objectifs', 'api_generer_indicateurs', 'api_suggerer_maturite',
    'api_generer_amelioration', 'api_generer_plan_complet', 'api_suggerer_assurance', 'analyse_ia_audit',
    'resultat_analyse_ia', 'appliquer_recommandation_ia', 'liste_analyses_ia', 'c2n_generer_recommandations_ia',
    'api_suggestions_bibliotheque', 'api_generer_lettre_mission', 'api_generer_plan_action',
    'api_creer_plan_action_depuis_ia', 'supprimer_analyse_ia', 'supprimer_toutes_analyses_ia', 'admin_analyses_ia',
    'api_creer_constat_depuis_ia', 'veille_menaces', 'api_analyser_plan_qualite',
}
# Repères d'adresse utilisés pour masquer les boutons et liens dans les pages
MOTIFS_ADRESSES = ['analyse-ia', 'analyses-ia', 'ia-ultra', '/ia/', '/kri/ia', 'kris-ia', 'kris/suggestions', '/kri/ia',
                   'dashboard-ia', 'analyser-ia', 'detecter-menaces', 'veille/menaces', 'suggerer-',
                   'suggestions/actions', 'suggestions/exercices', 'generer-objectifs', 'generer-indicateurs',
                   'generer-amelioration', 'generer-plan-complet', 'generer-lettre-mission', 'generer-ia',
                   'creer-depuis-ia', 'generer-plan-action', 'bibliotheque-risques/suggestions', 'admin/analyses-ia',
                   'analyser-plan']


def bloquer():
    if request.endpoint not in ENDPOINTS_IA or ia_autorisee():
        return None
    message = ("L'intelligence artificielle est désactivée." if not ia_plateforme_active()
               else "L'analyse IA n'est pas disponible pour votre compte (module ou permission « Utiliser l'analyse IA »).")
    if request.path.startswith('/api/') or request.path.startswith('/assistant/') or request.is_json \
            or 'application/json' in (request.headers.get('Accept') or ''):
        return jsonify({'success': False, 'error': message, 'ia_desactivee': True}), 403
    flash(message, 'info')
    retour = request.referrer if request.referrer and request.referrer != request.url else url_for('dashboard')
    return redirect(retour)


# ------------------------------------------------------------------ analyses automatiques (dans d'autres actions)
SERVICES = [('services.incident_ia_service', 'IncidentIAService'), ('services.analyse_ia', 'ServiceAnalyseIA'),
            ('services.ia_veille_service', 'IAVeilleService'), ('services.ia_qualite_service', 'IAQualiteService'),
            ('services.analyse_hybride', 'AnalyseHybrideService'), ('services.kri_ia_service', 'kri_ia_service'),
            ('services.detection_menace_service', 'DetectionMenaceService')]
FONCTIONS_APP = ('appel_ia_generer_plan_action', 'appel_ia_generer_constats', '_assistant_client_openai')


def _garder(f, nom):
    if getattr(f, '_egalyx_ia', False):
        return f

    @functools.wraps(f)
    def enveloppe(*a, **k):
        if not ia_autorisee():
            journal.info("IA désactivée : appel %s ignoré", nom)
            raise IADesactivee(f"IA désactivée ({nom})")
        return f(*a, **k)
    enveloppe._egalyx_ia = True
    return enveloppe


def neutraliser_services(module_app=None):
    """Enveloppe les méthodes publiques des services d'IA et les fonctions d'appel de app.py."""
    import importlib
    faits = []
    for module, nom in SERVICES:
        try:
            cible = getattr(importlib.import_module(module), nom)
        except Exception:
            continue                         # service absent de cette installation
        for attr in dir(cible):
            if attr.startswith('_'):
                continue
            brut = getattr(cible, attr, None)
            if not callable(brut):
                continue
            try:
                if isinstance(cible, type):
                    statique = isinstance(cible.__dict__.get(attr), staticmethod)
                    classe = isinstance(cible.__dict__.get(attr), classmethod)
                    if attr not in cible.__dict__:
                        continue
                    f = cible.__dict__[attr].__func__ if (statique or classe) else cible.__dict__[attr]
                    g = _garder(f, f'{nom}.{attr}')
                    setattr(cible, attr, staticmethod(g) if statique else classmethod(g) if classe else g)
                else:                        # instance (ex. kri_ia_service)
                    setattr(cible, attr, _garder(brut, f'{nom}.{attr}'))
                faits.append(f'{nom}.{attr}')
            except (TypeError, AttributeError):
                continue
    if module_app is not None:
        for nom in FONCTIONS_APP:
            f = getattr(module_app, nom, None)
            if callable(f):
                setattr(module_app, nom, _garder(f, nom))
                faits.append(nom)
    return faits


# ------------------------------------------------------------------ page super admin
@bp.route('/', methods=['GET', 'POST'])
@super_admin_requis
def page():
    from models import Client
    if request.method == 'POST':
        active = request.form.get('ia_active') == '1'
        ecrire_reglage('ia_active', active)
        journaliser('ia_plateforme_' + ('activee' if active else 'desactivee'), {}, client_id=None)
        flash("Intelligence artificielle " + ("activée" if active else "désactivée sur toute la plateforme : "
              "boutons et analyses d'IA ont disparu pour tous les clients (l'assistant répond depuis le centre d'aide)."), 'success')
        return redirect(url_for('.page'))
    from egalyx.modules_client import modules_du_client
    clients = Client.query.order_by(Client.nom).all()
    sans_ia = [c for c in clients if (modules_du_client(c) is not None and 'ia' not in modules_du_client(c))]
    return render_template('egalyx/ia_reglage.html', active=ia_plateforme_active(),
                           force_env=os.environ.get('EGALYX_IA', '1') == '0', clients=clients, sans_ia=sans_ia,
                           nb_adresses=len(ENDPOINTS_IA), cle_openai=bool(os.environ.get('OPENAI_API_KEY')))


def enregistrer(app):
    app.register_blueprint(bp)
    app.before_request(bloquer)
    app.jinja_env.globals['ia_active'] = ia_autorisee
    app.jinja_env.globals['ia_motifs_adresses'] = MOTIFS_ADRESSES
    faits = neutraliser_services(sys.modules.get(app.import_name))
    if faits:
        print(f"✅ IA : {len(faits)} fonction(s) d'analyse soumises à l'interrupteur IA")

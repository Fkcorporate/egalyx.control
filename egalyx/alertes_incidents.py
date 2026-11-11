"""
egalyx/alertes_incidents.py — e-mails d'alerte des incidents, réglés par organisation.

Les notifications dans l'application ne changent pas. La copie par e-mail se règle sur la page
« Incidents → Alertes e-mail » (administrateur de l'organisation ou gestionnaire des incidents) :
  - activée ou non (désactivée par défaut : rien ne part tant que l'organisation ne l'a pas décidé) ;
  - quels événements : délai de traitement dépassé, escalade ;
  - qui : responsable de résolution, superviseur, gestionnaires des incidents, adresses supplémentaires
    (boîte du risk manager, astreinte…) ;
  - chacun peut se désabonner pour lui-même (lien en bas de chaque e-mail).
Stockage : ClientConfiguration.preferences['alertes_incidents'] (aucune nouvelle table).
EGALYX_INCIDENTS_EMAIL=0 reste l'interrupteur général du serveur.
"""
import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from egalyx.commun import a_permission, client_id_courant, client_requis, est_admin_client, journaliser

bp = Blueprint('alertes_incidents', __name__, url_prefix='/incidents/alertes')

CLE = 'alertes_incidents'
EVENEMENTS = [('delai', 'Délai de traitement dépassé', "L'incident n'est pas résolu dans le délai prévu pour sa gravité."),
              ('escalade', 'Escalade', "L'incident passe au niveau supérieur (superviseur, direction).")]
ROLES = [('responsable', 'Responsable de la résolution'), ('superviseur', 'Superviseur / direction'),
         ('gestionnaire', 'Gestionnaires des incidents')]
DEFAUT = {'actif': False, 'evenements': ['delai', 'escalade'], 'roles': ['responsable', 'superviseur'],
          'adresses': [], 'desabonnes': []}
RE_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _m():
    import models
    return models


def reglages(client_id, session_=None):
    """Réglages complets (valeurs par défaut comprises). Ne lève jamais d'exception."""
    r = dict(DEFAUT)
    if not client_id:
        return r
    try:
        m = _m()
        s = session_ or m.db.session
        conf = s.query(m.ClientConfiguration).filter_by(client_id=client_id).first()
        sauves = ((conf.preferences or {}).get(CLE) if conf else None) or {}
        for k in DEFAUT:
            if k in sauves:
                r[k] = sauves[k]
    except Exception:  # noqa: BLE001
        pass
    return r


def _enregistrer(client_id, valeurs):
    m = _m()
    conf = m.ClientConfiguration.query.filter_by(client_id=client_id).first()
    if conf is None:
        conf = m.ClientConfiguration(client_id=client_id, couleurs={}, preferences={})
        m.db.session.add(conf)
    prefs = dict(conf.preferences or {})
    prefs[CLE] = valeurs
    conf.preferences = prefs          # nouvelle valeur : le changement du JSON est bien détecté


def peut_regler(u=None):
    u = u or current_user
    return est_admin_client(u) or a_permission('can_manage_incidents', u=u)


@bp.route('/', methods=['GET', 'POST'])
@client_requis
def page():
    if not peut_regler():
        abort(403)
    cid = client_id_courant()
    r = reglages(cid)
    if request.method == 'POST':
        adresses, refusees = [], []
        for a in re.split(r'[\s,;]+', request.form.get('adresses', '')):
            a = a.strip().lower()
            if a:
                (adresses if RE_EMAIL.match(a) else refusees).append(a)
        valeurs = {'actif': request.form.get('actif') == '1',
                   'evenements': [c for c, _l, _a in EVENEMENTS if request.form.get('ev_' + c) == '1'],
                   'roles': [c for c, *_x in ROLES if request.form.get('role_' + c) == '1'],
                   'adresses': sorted(set(adresses))[:20],
                   'desabonnes': r.get('desabonnes') or []}
        _enregistrer(cid, valeurs)
        journaliser('incidents_alertes_reglages', {k: v for k, v in valeurs.items() if k != 'desabonnes'})
        _m().db.session.commit()
        if refusees:
            flash('Adresse(s) ignorée(s), format invalide : ' + ', '.join(refusees[:5]), 'warning')
        flash('E-mails d\'alerte ' + ('activés.' if valeurs['actif'] else 'désactivés : seules les notifications dans '
                                       'l\'application restent.'), 'success')
        return redirect(url_for('.page'))
    m = _m()
    desabonnes = m.User.query.filter(m.User.id.in_(r.get('desabonnes') or [-1])).all()
    try:
        from egalyx import courriel
        smtp = courriel.est_configure()
    except Exception:  # noqa: BLE001
        smtp = False
    return render_template('egalyx/alertes_incidents.html', r=r, evenements=EVENEMENTS, roles=ROLES,
                           desabonnes=desabonnes, smtp=smtp, moi_desabonne=current_user.id in (r.get('desabonnes') or []))


@bp.route('/me-desabonner', methods=['GET', 'POST'])
@client_requis
def desabonner():
    """Lien présent dans chaque e-mail : la personne connectée arrête (ou reprend) les e-mails pour elle-même."""
    cid = client_id_courant()
    r = reglages(cid)
    liste = set(r.get('desabonnes') or [])
    if request.method == 'POST':
        reprendre = request.form.get('reprendre') == '1'
        (liste.discard if reprendre else liste.add)(current_user.id)
        r['desabonnes'] = sorted(liste)
        _enregistrer(cid, r)
        journaliser('incidents_alertes_' + ('reabonnement' if reprendre else 'desabonnement'), {})
        _m().db.session.commit()
        flash('Vous recevrez de nouveau les e-mails d\'alerte des incidents.' if reprendre else
              'Vous ne recevrez plus les e-mails d\'alerte des incidents. Les notifications dans l\'application '
              'restent affichées.', 'success')
        return redirect(url_for('.page') if peut_regler() else url_for('dashboard'))
    return render_template('egalyx/alertes_incidents_moi.html', desabonne=current_user.id in liste)


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'alertes_incidents.page', 'alertes_incidents.desabonner'})
    app.jinja_env.globals['incidents_alertes_reglables'] = peut_regler

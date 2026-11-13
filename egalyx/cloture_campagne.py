"""
egalyx/cloture_campagne.py — qui peut clôturer une campagne d'évaluation des risques (réglage par organisation).

Par défaut, rien ne change : tout utilisateur qui a accès à la cartographie peut clôturer la campagne
(bouton « Clôturer » ou lien direct), y compris un valideur.
L'administrateur peut restreindre dans Paramètres des risques → « Clôture des campagnes d'évaluation » :
  - « tous »            : comportement actuel ;
  - « gestionnaires »   : seulement la permission « Gérer les risques » et les administrateurs ;
  - « administrateurs » : seulement les administrateurs de l'organisation.
Le réglage s'applique au bouton (masqué) ET aux liens directs (refusés avec un message).
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from egalyx.commun import client_id_courant, journaliser, permission_requise

bp = Blueprint('cloture_campagne', __name__, url_prefix='/parametres/risques/campagnes')
CLE = 'cloture_campagne_evaluation'
CHOIX = {
    'tous': ("Tous les utilisateurs ayant accès à la cartographie",
             "Comportement actuel : y compris les valideurs et les gestionnaires sans droit de paramétrage."),
    'gestionnaires': ("Les gestionnaires des risques et les administrateurs",
                      "Permission « Gérer les risques » requise. Les valideurs sans cette permission ne peuvent plus clôturer."),
    'administrateurs': ("Les administrateurs de l'organisation uniquement",
                        "Le plus strict : seule l'administration de l'organisation clôture les campagnes."),
}
DEFAUT = 'tous'
ENDPOINTS = ('cloturer_campagne_specifique', 'cloturer_campagne_cartographie')


def _conf(client_id, creer=False):
    import models as M
    conf = M.ClientConfiguration.query.filter_by(client_id=client_id).first()
    if conf is None and creer:
        conf = M.ClientConfiguration(client_id=client_id, couleurs={}, preferences={})
        M.db.session.add(conf)
    return conf


def reglage(client_id):
    if not client_id:
        return DEFAUT
    try:
        conf = _conf(client_id)
        v = ((conf.preferences or {}).get(CLE) if conf else None) or DEFAUT
        return v if v in CHOIX else DEFAUT
    except Exception:  # noqa: BLE001
        return DEFAUT


def _est_admin(u):
    return u.role in ('super_admin', 'admin') or bool(getattr(u, 'is_client_admin', False))


def peut_cloturer_campagne(u=None):
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return False
    if u.role == 'super_admin':
        return True
    r = reglage(getattr(u, 'client_id', None))
    if r == 'administrateurs':
        return _est_admin(u)
    if r == 'gestionnaires':
        return _est_admin(u) or u.has_permission('can_manage_risks')
    return True


def _controle():
    if request.endpoint not in ENDPOINTS or not getattr(current_user, 'is_authenticated', False):
        return None
    if peut_cloturer_campagne():
        return None
    qui = CHOIX[reglage(current_user.client_id)][0].lower()
    flash(f"Clôture refusée : dans votre organisation, seuls {qui} peuvent clôturer une campagne d'évaluation.", 'warning')
    cid = (request.view_args or {}).get('cartographie_id')
    return redirect(url_for('detail_cartographie', id=cid) if cid else url_for('liste_cartographies'))


@bp.route('/', methods=['GET', 'POST'])
@permission_requise('can_manage_settings')
def page():
    from models import db
    cid = client_id_courant()
    actuel = reglage(cid)
    if request.method == 'POST':
        choix = request.form.get('cloture')
        if choix not in CHOIX:
            flash('Choix invalide.', 'danger')
            return redirect(url_for('.page'))
        conf = _conf(cid, creer=True)
        prefs = dict(conf.preferences or {})
        prefs[CLE] = choix
        conf.preferences = prefs
        try:
            journaliser('reglage_cloture_campagne', {'avant': actuel, 'apres': choix})
        except Exception:  # noqa: BLE001
            pass
        db.session.commit()
        flash(f"Enregistré : {CHOIX[choix][0].lower()} peuvent clôturer une campagne d'évaluation.", 'success')
        return redirect(url_for('.page'))
    return render_template('egalyx/cloture_campagne.html', choix=CHOIX, actuel=actuel, defaut=DEFAUT)


def enregistrer(app):
    app.register_blueprint(bp)
    app.before_request(_controle)
    app.jinja_env.globals['peut_cloturer_campagne'] = peut_cloturer_campagne
    return True

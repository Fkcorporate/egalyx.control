"""
egalyx/apparence.py — PAQUET OPTIONNEL « nouvelle apparence » : classique ou nouvelle, au choix.

Sans ce fichier (et sans templates/egalyx/_apparence.html), Egalyx garde exactement son apparence actuelle.
Avec lui, SEUL LE SUPER-ADMIN décide (menu du compte → « Apparence ») : classique ou nouvelle pour
chaque client. Les utilisateurs et les administrateurs des clients ne voient pas ce réglage.
EGALYX_APPARENCE=nouvelle|classique fixe la valeur des clients non réglés (classique si absent).
La nouvelle apparence est une feuille de style ajoutée par-dessus les pages existantes (rien n'est réécrit) :
tableau de bord sobre (cartes blanches, couleur réservée aux statuts, suppression des barres « Taux » vides),
en-tête et menu à plat, cartes à bordure fine. Revenir à « classique » rétablit tout immédiatement.
Stockage : client_configurations.preferences['apparence'].
"""
import os

from flask import abort, Blueprint, flash, g, redirect, render_template, request, url_for
from flask_login import current_user

bp = Blueprint('apparence', __name__, url_prefix='/compte/apparence')

CHOIX = ('classique', 'nouvelle')


def _m():
    import models
    return models


def defaut_serveur():
    v = (os.environ.get('EGALYX_APPARENCE') or 'classique').strip().lower()
    return v if v in CHOIX else 'classique'


def defaut_organisation(client_id):
    if not client_id:
        return None
    try:
        m = _m()
        conf = m.ClientConfiguration.query.filter_by(client_id=client_id).first()
        v = (conf.preferences or {}).get('apparence') if conf else None
        return v if v in CHOIX else None
    except Exception:  # noqa: BLE001
        return None


def apparence_effective(u=None):
    """Seul le super-admin décide : apparence fixée pour le client, sinon défaut du serveur."""
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return defaut_serveur()
    return defaut_organisation(getattr(u, 'client_id', None)) or defaut_serveur()


def apparence_nouvelle():
    try:
        if 'egalyx_apparence' not in g:
            g.egalyx_apparence = apparence_effective()
        return g.egalyx_apparence == 'nouvelle'
    except Exception:  # noqa: BLE001
        return False


def _est_super_admin():
    return bool(getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'is_super_admin', False))


@bp.route('/', methods=['GET', 'POST'])
def page():
    from egalyx.commun import journaliser
    m = _m()
    if not getattr(current_user, 'is_authenticated', False):
        abort(401)
    if not _est_super_admin():
        abort(404)
    if request.method == 'POST':
        try:
            cid = int(request.form.get('client_id') or 0)
        except ValueError:
            abort(400)
        client = m.db.session.get(m.Client, cid) if cid else None
        if client is None:
            abort(404)
        v = request.form.get('apparence')
        conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
        if conf is None:
            conf = m.ClientConfiguration(client_id=cid, couleurs={}, preferences={})
            m.db.session.add(conf)
        prefs = dict(conf.preferences or {})
        if v in CHOIX:
            prefs['apparence'] = v
        else:
            prefs.pop('apparence', None)
        conf.preferences = prefs
        journaliser('apparence_client', {'apparence': v or 'serveur'}, client_id=cid)
        m.db.session.commit()
        flash(f"Apparence de « {client.nom} » : {v or 'celle du serveur (' + defaut_serveur() + ')'}.", 'success')
        return redirect(url_for('.page'))
    clients = m.Client.query.order_by(m.Client.nom).all()
    reglages = {c.id: defaut_organisation(c.id) for c in clients}
    return render_template('egalyx/apparence.html', clients=clients, reglages=reglages, serveur=defaut_serveur())


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'apparence.page'})
    app.jinja_env.globals['apparence_nouvelle'] = apparence_nouvelle

    # L'entrée « Apparence » du menu du compte (base.html : url_exists('apparence.page')) n'apparaît
    # que pour le super-admin : les utilisateurs et les admins clients ne voient pas ce réglage.
    @app.context_processor
    def _menu_apparence():
        def url_exists(endpoint):
            if endpoint == 'apparence.page':
                return _est_super_admin()
            return endpoint in app.view_functions
        return {'url_exists': url_exists}

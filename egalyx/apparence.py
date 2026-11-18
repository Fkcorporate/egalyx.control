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
import sys

from flask import abort, Blueprint, flash, g, redirect, render_template, request, url_for
from flask_login import current_user

bp = Blueprint('apparence', __name__, url_prefix='/compte/apparence')

CHOIX = ('classique', 'nouvelle')


def journal(message):
    """Journal de diagnostic (console / logs Render) : coupé par défaut (une ligne par page remplissait les journaux).
    EGALYX_APPARENCE_LOG=1 (ou EGALYX_TRACES=1) pour le rallumer."""
    if (os.environ.get('EGALYX_APPARENCE_LOG') or '').strip() != '1' and os.environ.get('EGALYX_TRACES') != '1':
        return
    try:
        print(f'🎨 [APPARENCE] {message}', file=sys.stdout, flush=True)
    except Exception:  # noqa: BLE001
        pass


def _m():
    import models
    return models


def defaut_serveur():
    v = (os.environ.get('EGALYX_APPARENCE') or 'classique').strip().lower()
    return v if v in CHOIX else 'classique'


def reglage_brut(client_id):
    """(valeur enregistrée, explication) — pour le journal."""
    if not client_id:
        return None, 'aucun client'
    try:
        m = _m()
        conf = m.ClientConfiguration.query.filter_by(client_id=client_id).first()
        if conf is None:
            return None, 'pas de configuration pour ce client'
        prefs = conf.preferences
        if not isinstance(prefs, dict):
            return None, f'preferences illisibles ({type(prefs).__name__})'
        return prefs.get('apparence'), 'ok'
    except Exception as e:  # noqa: BLE001
        return None, f'erreur lecture : {e!r}'


def defaut_organisation(client_id):
    v, _ = reglage_brut(client_id)
    return v if v in CHOIX else None


def apparence_effective(u=None):
    """Seul le super-admin décide : apparence fixée pour le client, sinon défaut du serveur."""
    u = u or current_user
    if not getattr(u, 'is_authenticated', False):
        return defaut_serveur()
    cid = getattr(u, 'client_id', None)
    if u is current_user or getattr(u, 'id', None) == getattr(current_user, 'id', None):
        try:                      # super-admin en « Voir comme ce client » : apparence du client consulté
            from egalyx.commun import client_id_courant
            cid = client_id_courant() or cid
        except Exception:  # noqa: BLE001
            pass
    return defaut_organisation(cid) or defaut_serveur()


def _journal_page(resultat):
    """Une ligne par page affichée : qui, quel client, quel réglage, quel résultat."""
    try:
        from flask import session
        u = current_user
        if not getattr(u, 'is_authenticated', False):
            journal(f'{request.path} · non connecté → {resultat} (défaut serveur {defaut_serveur()})')
            return
        cid = getattr(u, 'client_id', None)
        vue = session.get('viewing_client_id')
        try:
            from egalyx.commun import client_id_courant
            courant = client_id_courant()
        except Exception:  # noqa: BLE001
            courant = cid
        brut, info = reglage_brut(courant or cid)
        journal(f'{request.path} · {getattr(u, "username", "?")} (rôle {getattr(u, "role", "?")}, client {cid}'
                f'{", consulte le client " + str(vue) if vue else ""}) · client utilisé {courant or cid} · '
                f'réglage enregistré={brut!r} ({info}) · défaut serveur={defaut_serveur()} → {resultat.upper()}')
    except Exception as e:  # noqa: BLE001
        journal(f'journal impossible : {e!r}')


def apparence_nouvelle():
    try:
        if 'egalyx_apparence' not in g:
            g.egalyx_apparence = apparence_effective()
            _journal_page(g.egalyx_apparence)
        return g.egalyx_apparence == 'nouvelle'
    except Exception as e:  # noqa: BLE001
        journal(f'erreur, apparence classique utilisée : {e!r}')
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
        avant = defaut_organisation(cid)
        journaliser('apparence_client', {'apparence': v or 'serveur'}, client_id=cid)
        m.db.session.commit()
        relu, info = reglage_brut(cid)
        journal(f'ENREGISTREMENT par {current_user.username} · client {cid} « {client.nom} » : {avant!r} → {v!r} · '
                f'relu en base : {relu!r} ({info})' + ('' if (relu or None) == (v if v in CHOIX else None)
                                                        else ' ⚠️ LA BASE NE CONTIENT PAS LA VALEUR ATTENDUE'))
        flash(f"Apparence de « {client.nom} » : {v or 'celle du serveur (' + defaut_serveur() + ')'}.", 'success')
        return redirect(url_for('.page'))
    clients = m.Client.query.order_by(m.Client.nom).all()
    reglages = {c.id: defaut_organisation(c.id) for c in clients}
    return render_template('egalyx/apparence.html', clients=clients, reglages=reglages, serveur=defaut_serveur())


def _diagnostic_demarrage(app):
    """Au démarrage : les fichiers nécessaires sont-ils là, et base.html charge-t-il la feuille de style ?"""
    racine = os.path.join(app.root_path, 'templates')
    feuille = os.path.exists(os.path.join(racine, 'egalyx', '_apparence.html'))
    page = os.path.exists(os.path.join(racine, 'egalyx', 'apparence.html'))
    try:
        with open(os.path.join(racine, 'base.html'), encoding='utf-8') as f:
            crochet = 'egalyx/_apparence.html' in f.read()
    except OSError:
        crochet = False
    journal(f'démarrage · templates/egalyx/_apparence.html {"présent" if feuille else "ABSENT"} · '
            f'templates/egalyx/apparence.html {"présent" if page else "ABSENT"} · '
            f'base.html {"charge" if crochet else "NE CHARGE PAS"} la nouvelle apparence · '
            f'EGALYX_APPARENCE={os.environ.get("EGALYX_APPARENCE") or "(absente → classique)"}')
    if not feuille or not crochet:
        journal('⚠️ la nouvelle apparence ne PEUT PAS s\'afficher : '
                + ('templates/egalyx/_apparence.html manque. ' if not feuille else '')
                + ('templates/base.html ne contient pas {% include "egalyx/_apparence.html" ignore missing %} '
                   '(base.html remplacé ou modifié : réinstallez le paquet complet).' if not crochet else ''))


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'apparence.page'})
    app.jinja_env.globals['apparence_nouvelle'] = apparence_nouvelle
    _diagnostic_demarrage(app)
    try:                                    # tableau de bord mis en page comme la maquette (apparence « Nouvelle »)
        from egalyx import apparence_tableau
        apparence_tableau.enregistrer(app)
    except ImportError:
        journal('egalyx/apparence_tableau.py absent : tableau de bord d\'origine, même en apparence « Nouvelle »')

    # L'entrée « Apparence » du menu du compte (base.html : url_exists('apparence.page')) n'apparaît
    # que pour le super-admin : les utilisateurs et les admins clients ne voient pas ce réglage.
    @app.context_processor
    def _menu_apparence():
        def url_exists(endpoint):
            if endpoint == 'apparence.page':
                return _est_super_admin()
            return endpoint in app.view_functions
        return {'url_exists': url_exists}

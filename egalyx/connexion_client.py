"""
egalyx/connexion_client.py — page de connexion aux couleurs de chaque client (https://<client>.egalyx.com).

Sur l'adresse d'un client (g.current_client, posé par la reconnaissance du sous-domaine) :
  - la page de connexion montre le logo, le nom et la couleur de l'organisation, un message d'accueil et un contact
    d'assistance choisis par l'administrateur du client, le rappel de la double authentification, les boutons
    Microsoft / Google s'ils sont activés, « propulsé par Egalyx » ;
  - seuls les comptes de CE client (et le super-admin) peuvent s'y connecter ; un compte d'un autre client reçoit le
    même message qu'un mauvais mot de passe (on ne révèle pas quels clients existent) ;
  - la page n'est pas indexée par les moteurs de recherche.
Sur egalyx.com ou une adresse inconnue : page de connexion Egalyx habituelle, inchangée.
Essai en local : http://127.0.0.1:5005/auth/login_fullscreen?espace=<sous-domaine>
Réglages (administrateur du client) : /organisation/page-connexion
"""
import re

from flask import (Blueprint, abort, flash, g, get_flashed_messages, redirect, render_template, request, session,
                   url_for)
from flask_login import current_user, logout_user

bp = Blueprint('connexion_client', __name__, url_prefix='/organisation/page-connexion')
CLE = 'page_connexion'
MESSAGE_GENERIQUE = 'Nom d\'utilisateur ou mot de passe incorrect'
COULEUR_DEFAUT = '#13294B'


def _m():
    import models
    return models


def _local():
    return request.host.split(':')[0].lower() in ('localhost', '127.0.0.1', '0.0.0.0')


def client_de_la_page():
    """Client de l'adresse (sous-domaine), ou, en local seulement, celui de ?espace=<sous-domaine>."""
    client = getattr(g, 'current_client', None)
    if client is None and _local():
        espace = (request.args.get('espace') or session.get('essai_espace') or '').strip().lower()
        if espace and re.fullmatch(r'[a-z0-9-]{1,63}', espace):
            from egalyx.gestion_clients import client_par_hote, domaine_principal
            client = client_par_hote(f'{espace}.{domaine_principal()}')
            if client is not None:
                session['essai_espace'] = espace
    return client


def reglages(cid):
    m = _m()
    try:
        conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
        r = ((conf.preferences or {}).get(CLE) if conf else None) or {}
    except Exception:  # noqa: BLE001
        r = {}
    couleur = r.get('couleur') if re.fullmatch(r'#[0-9A-Fa-f]{6}', r.get('couleur') or '') else COULEUR_DEFAUT
    return {'message': (r.get('message') or '').strip(), 'contact': (r.get('contact') or '').strip(), 'couleur': couleur}


def _contexte(client):
    from egalyx.identite import identite
    ident = identite(client.id) or {'nom': client.nom, 'nom_court': client.nom, 'logo_url': None}
    try:
        from egalyx.sso import fournisseurs_actifs
        sso = fournisseurs_actifs()
    except Exception:  # noqa: BLE001
        sso = []
    r = reglages(client.id)
    return {'client': client, 'ident': ident, 'reglages': r, 'sso': sso,
            'initiales': ''.join(w[0] for w in (ident.get('nom_court') or client.nom).split()[:2]).upper(),
            'actif': getattr(client, 'is_active', True) is not False,
            'messages': get_flashed_messages(with_categories=True)}


def page(client, statut=200, nom_saisi='', apercu=False):
    ctx = _contexte(client)
    rep = render_template('auth/connexion_client.html', nom_saisi=nom_saisi, apercu=apercu, **ctx)
    from flask import make_response
    rep = make_response(rep, statut)
    rep.headers['X-Robots-Tag'] = 'noindex, nofollow'
    rep.headers['Cache-Control'] = 'no-store'
    return rep


def _compte_d_un_autre_client(nom, client):
    if not nom:
        return False
    u = _m().User.query.filter_by(username=nom).first()
    if u is None:
        return False
    if getattr(u, 'role', '') == 'super_admin' or getattr(u, 'is_super_admin', False):
        return False
    return getattr(u, 'client_id', None) != client.id


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'connexion_client.reglage'})

    origine = app.view_functions.get('login_fullscreen')
    if origine is not None:
        def connexion_selon_adresse(*a, **k):
            if _local() and 'espace' in request.args and not request.args.get('espace'):
                session.pop('essai_espace', None)    # ?espace= vide : retour à la page Egalyx en local
            client = client_de_la_page()
            if client is None:
                return origine(*a, **k)
            connecte = getattr(current_user, 'is_authenticated', False)
            if request.method == 'GET' and connecte:
                # aperçu pour l'administrateur de ce client (ou le super-admin), sinon comportement habituel
                if request.args.get('apercu') and (getattr(current_user, 'role', '') == 'super_admin'
                                                   or getattr(current_user, 'client_id', None) == client.id):
                    return page(client, apercu=True)
                return origine(*a, **k)
            if getattr(client, 'is_active', True) is False:
                return page(client, 403)
            if request.method == 'POST':
                nom = (request.form.get('username') or '').strip()
                mdp = request.form.get('password') or ''
                u = _m().User.query.filter_by(username=nom).first() if nom else None
                valide = u is not None and mdp and u.check_password(mdp) and getattr(u, 'is_active', True)
                if not valide or _compte_d_un_autre_client(nom, client):
                    if valide:
                        app.logger.warning('Connexion refusée sur l\'espace %s : compte d\'une autre organisation (%s)',
                                           client.id, nom)
                    flash(MESSAGE_GENERIQUE, 'error')     # même message dans tous les cas
                    return page(client, 200, nom)
                return origine(*a, **k)               # connexion et redirection habituelles (selon le rôle)
            return page(client)
        connexion_selon_adresse.__name__ = origine.__name__
        connexion_selon_adresse.__doc__ = origine.__doc__
        app.view_functions['login_fullscreen'] = connexion_selon_adresse

    # Connexion Microsoft / Google sur l'adresse d'un client : même contrôle d'organisation
    retour_sso = app.view_functions.get('sso.retour')
    if retour_sso is not None:
        def retour_sso_controle(*a, **k):
            client = client_de_la_page()
            rep = retour_sso(*a, **k)
            if client is not None and getattr(current_user, 'is_authenticated', False) \
                    and getattr(current_user, 'role', '') != 'super_admin' \
                    and getattr(current_user, 'client_id', None) != client.id:
                logout_user()
                session.clear()
                flash('Ce compte n\'a pas accès à cet espace.', 'error')
                return redirect(url_for('login_fullscreen'))
            return rep
        retour_sso_controle.__name__ = retour_sso.__name__
        app.view_functions['sso.retour'] = retour_sso_controle


@bp.route('/', methods=['GET', 'POST'])
def reglage():
    """Réglages de la page de connexion de l'organisation (administrateur du client)."""
    from egalyx.commun import client_id_courant, journaliser
    from egalyx.identite import peut_regler
    if not getattr(current_user, 'is_authenticated', False):
        return redirect(url_for('login_fullscreen', next=request.path))
    if not peut_regler():
        abort(403)
    cid = client_id_courant()
    if not cid:
        abort(404)
    m = _m()
    if request.method == 'POST':
        message = (request.form.get('message') or '').strip()[:220]
        contact = (request.form.get('contact') or '').strip()[:120]
        couleur = (request.form.get('couleur') or '').strip()
        if not re.fullmatch(r'#[0-9A-Fa-f]{6}', couleur):
            couleur = COULEUR_DEFAUT
        conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
        if conf is None:
            conf = m.ClientConfiguration(client_id=cid, couleurs={}, preferences={})
            m.db.session.add(conf)
        prefs = dict(conf.preferences or {})
        prefs[CLE] = {'message': message, 'contact': contact, 'couleur': couleur}
        conf.preferences = prefs
        journaliser('page_connexion', {'message': bool(message), 'contact': bool(contact), 'couleur': couleur}, client_id=cid)
        m.db.session.commit()
        flash('Page de connexion enregistrée.', 'success')
        return redirect(url_for('.reglage'))
    from egalyx.gestion_clients import url_client
    client = m.db.session.get(m.Client, cid)
    adresse = url_client(client)
    apercu = adresse + '/auth/login_fullscreen' if adresse else None
    if apercu:
        apercu += '?apercu=1'
    if _local() and client is not None:
        from egalyx.gestion_clients import sous_domaine_du_client
        sd = sous_domaine_du_client(client)
        apercu = url_for('login_fullscreen', espace=sd, apercu=1) if sd else None
    return render_template('egalyx/page_connexion.html', r=reglages(cid), adresse=adresse, apercu=apercu,
                           defaut=COULEUR_DEFAUT)

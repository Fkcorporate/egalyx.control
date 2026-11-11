"""
egalyx/identite.py — le nom et le logo de chaque organisation dans l'outil.

  - Nom affiché (court, 30 caractères) : en haut de l'outil, dans l'objet des e-mails d'alerte, sur les rapports.
    Par défaut : le nom du client (raccourci s'il est long).
  - Logo (PNG, JPEG ou WebP, 1 Mo au plus) : réencodé en PNG (≤ 400 × 160 px) pour écarter tout contenu
    malveillant, rangé dans instance/logos/client_<id>.png, servi uniquement aux utilisateurs de l'organisation
    (et au super admin) ; jamais de SVG (risque de script).
  - Réglable par l'administrateur de l'organisation (« Identité de l'organisation ») et par le super admin, dès la
    création du client.
  - « Egalyx » reste visible : marque en haut à gauche et mention « Réalisé avec Egalyx » sur les rapports.
Stockage : Client.logo (nom du fichier) et ClientConfiguration.preferences['identite'] — aucune nouvelle table.
"""
import base64
import io
import os

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, url_for
from flask_login import current_user

from egalyx.commun import client_id_courant, client_requis, est_admin_client, est_super_admin, journaliser

bp = Blueprint('identite', __name__, url_prefix='/organisation/identite')

CLE = 'identite'
NOM_MAX = 30
TAILLE_MAX = 1024 * 1024
DIMENSIONS = (400, 160)
SIGNATURES = {b'\x89PNG\r\n\x1a\n': 'png', b'\xff\xd8\xff': 'jpg', b'RIFF': 'webp'}


def _m():
    import models
    return models


def _dossier():
    d = os.path.join(current_app.instance_path, 'logos')
    os.makedirs(d, exist_ok=True)
    return d


def _chemin_logo(cid):
    return os.path.join(_dossier(), f'client_{int(cid)}.png')


def nom_par_defaut(nom):
    nom = (nom or '').strip()
    if len(nom) <= NOM_MAX:
        return nom
    return nom[:NOM_MAX - 1].rstrip() + '…'


def _preferences(cid):
    m = _m()
    try:
        conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
        return ((conf.preferences or {}).get(CLE) if conf else None) or {}
    except Exception:  # noqa: BLE001
        return {}


def identite(cid=None):
    """{'nom', 'nom_court', 'logo_url', 'a_logo'} de l'organisation (celle consultée par défaut). Mis en cache par requête."""
    cid = cid if cid is not None else client_id_courant()
    if not cid:
        return None
    cache = g.setdefault('_egalyx_identite', {}) if _contexte_requete() else {}
    if cid in cache:
        return cache[cid]
    m = _m()
    client = m.db.session.get(m.Client, cid)
    if client is None:
        return None
    prefs = _preferences(cid)
    chemin = _chemin_logo(cid)
    a_logo = bool(client.logo) and os.path.exists(chemin)
    res = {'id': cid, 'nom': client.nom, 'nom_court': prefs.get('nom_court') or nom_par_defaut(client.nom),
           'a_logo': a_logo,
           'logo_url': url_for('identite.logo', cid=cid, v=int(os.path.getmtime(chemin))) if a_logo else None}
    cache[cid] = res
    return res


def _contexte_requete():
    from flask import has_request_context
    return has_request_context()


def nom_affiche(cid):
    """Nom court sans contexte de requête (e-mails envoyés en arrière-plan, CLI)."""
    m = _m()
    try:
        client = m.db.session.get(m.Client, cid)
    except Exception:  # noqa: BLE001
        return None
    if client is None:
        return None
    return _preferences(cid).get('nom_court') or nom_par_defaut(client.nom)


def logo_data_uri(cid):
    """Logo en data URI pour les PDF (WeasyPrint) et les pages imprimables."""
    try:
        p = _chemin_logo(cid)
        if os.path.exists(p):
            with open(p, 'rb') as f:
                return 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
    except Exception:  # noqa: BLE001
        pass
    return None


# ---------------------------------------------------------------- enregistrement
def preparer_logo(contenu):
    """Contrôle et réencode le logo. Renvoie les octets PNG, ou lève ValueError avec un message clair."""
    if not contenu:
        raise ValueError('Fichier vide.')
    if len(contenu) > TAILLE_MAX:
        raise ValueError('Logo trop lourd : 1 Mo au maximum.')
    fmt = next((f for sig, f in SIGNATURES.items() if contenu.startswith(sig)), None)
    if fmt == 'webp' and contenu[8:12] != b'WEBP':
        fmt = None
    if fmt is None:
        raise ValueError('Format non accepté : PNG, JPEG ou WebP (le SVG n\'est pas accepté).')
    try:
        from PIL import Image
    except ImportError:
        if fmt != 'png':
            raise ValueError('Ce serveur n\'accepte que les logos PNG (bibliothèque Pillow absente).')
        return contenu
    try:
        img = Image.open(io.BytesIO(contenu))
        img.load()
    except Exception:  # noqa: BLE001
        raise ValueError('Image illisible.')
    if img.width * img.height > 25_000_000:
        raise ValueError('Image trop grande.')
    img = img.convert('RGBA')
    img.thumbnail(DIMENSIONS)
    sortie = io.BytesIO()
    img.save(sortie, 'PNG', optimize=True)
    return sortie.getvalue()


def appliquer(cid, nom_court=None, logo=None, retirer_logo=False):
    """Enregistre le nom affiché et/ou le logo (sans commit). logo : octets bruts du fichier envoyé."""
    m = _m()
    client = m.db.session.get(m.Client, cid)
    if client is None:
        raise ValueError('Organisation introuvable.')
    if nom_court is not None:
        conf = m.ClientConfiguration.query.filter_by(client_id=cid).first()
        if conf is None:
            conf = m.ClientConfiguration(client_id=cid, couleurs={}, preferences={})
            m.db.session.add(conf)
        prefs = dict(conf.preferences or {})
        ident = dict(prefs.get(CLE) or {})
        ident['nom_court'] = ' '.join(nom_court.split())[:NOM_MAX] or None
        prefs[CLE] = ident
        conf.preferences = prefs
    if logo:
        donnees = preparer_logo(logo)
        with open(_chemin_logo(cid), 'wb') as f:
            f.write(donnees)
        client.logo = os.path.basename(_chemin_logo(cid))
    elif retirer_logo:
        try:
            os.remove(_chemin_logo(cid))
        except OSError:
            pass
        client.logo = None
    if _contexte_requete():
        g.pop('_egalyx_identite', None)


# ---------------------------------------------------------------- pages
def peut_regler():
    return est_admin_client() or est_super_admin()


@bp.route('/', methods=['GET', 'POST'])
@client_requis
def page():
    if not peut_regler():
        abort(403)
    cid = client_id_courant()
    if request.method == 'POST':
        f = request.files.get('logo')
        try:
            appliquer(cid, nom_court=request.form.get('nom_court', ''),
                      logo=f.read(TAILLE_MAX + 1) if f and f.filename else None,
                      retirer_logo=request.form.get('retirer_logo') == '1')
        except ValueError as e:
            flash(str(e), 'warning')
            return redirect(url_for('.page', client_id=cid if est_super_admin() else None))
        journaliser('identite_organisation', {'nom_court': request.form.get('nom_court', '')[:NOM_MAX],
                                              'logo': bool(f and f.filename),
                                              'retrait_logo': request.form.get('retirer_logo') == '1'}, client_id=cid)
        _m().db.session.commit()
        flash('Identité de l\'organisation enregistrée.', 'success')
        return redirect(url_for('.page', client_id=cid if est_super_admin() else None))
    return render_template('egalyx/identite.html', ident=identite(cid), nom_max=NOM_MAX)


@bp.route('/logo/<int:cid>')
def logo(cid):
    """Logo servi aux seuls utilisateurs de l'organisation et au super admin."""
    if not getattr(current_user, 'is_authenticated', False):
        abort(404)
    if not (est_super_admin() or getattr(current_user, 'client_id', None) == cid):
        abort(404)
    p = _chemin_logo(cid)
    if not os.path.exists(p):
        abort(404)
    r = send_file(p, mimetype='image/png', max_age=86400)
    r.headers['X-Content-Type-Options'] = 'nosniff'
    return r


# ---------------------------------------------------------------- création du client (super admin)
def _brancher_creation(app):
    """Le formulaire de création du client propose « Nom affiché » et « Logo » : appliqués après la création."""
    nom_vue = 'super_admin_nouveau_client'
    vue = app.view_functions.get(nom_vue)
    if vue is None or getattr(vue, '_egalyx_identite', False):
        return

    def enveloppe(*a, **k):
        reponse = vue(*a, **k)
        if request.method == 'POST' and getattr(reponse, 'status_code', 200) in (301, 302, 303):
            ref = (request.form.get('reference') or '').strip()
            nom_court = (request.form.get('identite_nom_court') or '').strip()
            f = request.files.get('identite_logo')
            if ref and (nom_court or (f and f.filename)):
                m = _m()
                client = m.Client.query.filter_by(reference=ref).first()
                if client is not None:
                    try:
                        appliquer(client.id, nom_court=nom_court or None,
                                  logo=f.read(TAILLE_MAX + 1) if f and f.filename else None)
                        m.db.session.commit()
                    except ValueError as e:
                        m.db.session.rollback()
                        flash(f'Client créé, mais le logo n\'a pas été enregistré : {e} Ajoutez-le depuis la fiche du client.',
                              'warning')
        return reponse
    enveloppe.__name__ = vue.__name__
    enveloppe._egalyx_identite = True
    app.view_functions[nom_vue] = enveloppe


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'identite.page', 'identite.logo'})
    _brancher_creation(app)
    app.jinja_env.globals['identite_client'] = identite
    app.jinja_env.globals['identite_reglable'] = peut_regler
    app.jinja_env.globals['logo_client_data'] = logo_data_uri

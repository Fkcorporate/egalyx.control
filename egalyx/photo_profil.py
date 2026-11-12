"""
egalyx/photo_profil.py — photo de profil de chaque utilisateur.

  - Chacun dépose ou retire sa photo depuis « Mon profil » (PNG, JPEG ou WebP, 2 Mo au plus).
  - L'image est recadrée en carré et réencodée en PNG 256 × 256 (Pillow) : aucun contenu malveillant ne passe,
    les métadonnées (position GPS de la photo…) sont supprimées. SVG refusé.
  - Rangée dans instance/avatars/user_<id>.png ; servie seulement aux utilisateurs de la même organisation et
    au super admin.
  - Affichée dans l'en-tête, le menu mobile et le profil ; ailleurs, initiales sur fond coloré.
Aucune nouvelle colonne en base : la présence du fichier suffit.
"""
import io
import os

from flask import Blueprint, abort, current_app, flash, redirect, request, send_file, url_for
from flask_login import current_user

from egalyx.commun import est_super_admin, journaliser

bp = Blueprint('photo_profil', __name__, url_prefix='/compte/photo')

TAILLE_MAX = 2 * 1024 * 1024
COTE = 256
SIGNATURES = {b'\x89PNG\r\n\x1a\n': 'png', b'\xff\xd8\xff': 'jpg', b'RIFF': 'webp'}


def _dossier():
    d = os.path.join(current_app.instance_path, 'avatars')
    os.makedirs(d, exist_ok=True)
    return d


def _chemin(uid):
    return os.path.join(_dossier(), f'user_{int(uid)}.png')


def preparer(contenu):
    if not contenu:
        raise ValueError('Fichier vide.')
    if len(contenu) > TAILLE_MAX:
        raise ValueError('Photo trop lourde : 2 Mo au maximum.')
    fmt = next((f for sig, f in SIGNATURES.items() if contenu.startswith(sig)), None)
    if fmt == 'webp' and contenu[8:12] != b'WEBP':
        fmt = None
    if fmt is None:
        raise ValueError('Format non accepté : PNG, JPEG ou WebP.')
    try:
        from PIL import Image, ImageOps
    except ImportError:
        if fmt != 'png':
            raise ValueError('Ce serveur n\'accepte que les photos PNG (bibliothèque Pillow absente).')
        return contenu
    try:
        img = Image.open(io.BytesIO(contenu))
        img.load()
    except Exception:  # noqa: BLE001
        raise ValueError('Image illisible.')
    if img.width * img.height > 40_000_000:
        raise ValueError('Image trop grande.')
    img = ImageOps.exif_transpose(img)            # photo de téléphone : bonne orientation
    img = ImageOps.fit(img.convert('RGB'), (COTE, COTE), method=Image.LANCZOS)
    sortie = io.BytesIO()
    img.save(sortie, 'PNG', optimize=True)
    return sortie.getvalue()


def photo_url(u):
    """URL de la photo (avec version pour le cache) ou None."""
    try:
        uid = getattr(u, 'id', None)
        if not uid:
            return None
        p = _chemin(uid)
        if os.path.exists(p):
            return url_for('photo_profil.voir', uid=uid, v=int(os.path.getmtime(p)))
    except Exception:  # noqa: BLE001
        pass
    return None


def initiales(u):
    nom = ' '.join(x for x in (getattr(u, 'prenom', None), getattr(u, 'nom', None)) if x) or getattr(u, 'username', '') or '?'
    morceaux = [m for m in nom.replace('.', ' ').replace('_', ' ').split() if m]
    return ''.join(m[0] for m in morceaux[:2]).upper() or '?'


@bp.route('/', methods=['POST'])
def deposer():
    if not getattr(current_user, 'is_authenticated', False):
        abort(401)
    retour = request.form.get('retour') or request.referrer or url_for('profil_utilisateur')
    if request.form.get('retirer') == '1':
        try:
            os.remove(_chemin(current_user.id))
        except OSError:
            pass
        journaliser('photo_profil_retiree', {})
        _commit()
        flash('Photo de profil retirée.', 'info')
        return redirect(retour)
    f = request.files.get('photo')
    if not f or not f.filename:
        flash('Choisissez une photo.', 'warning')
        return redirect(retour)
    try:
        donnees = preparer(f.read(TAILLE_MAX + 1))
    except ValueError as e:
        flash(str(e), 'warning')
        return redirect(retour)
    with open(_chemin(current_user.id), 'wb') as sortie:
        sortie.write(donnees)
    journaliser('photo_profil_modifiee', {})
    _commit()
    flash('Photo de profil enregistrée.', 'success')
    return redirect(retour)


def _commit():
    try:
        from models import db
        db.session.commit()
    except Exception:  # noqa: BLE001
        pass


@bp.route('/<int:uid>')
def voir(uid):
    if not getattr(current_user, 'is_authenticated', False):
        abort(404)
    if uid != current_user.id and not est_super_admin():
        from models import db, User
        cible = db.session.get(User, uid)
        if cible is None or cible.client_id != getattr(current_user, 'client_id', None):
            abort(404)
    p = _chemin(uid)
    if not os.path.exists(p):
        abort(404)
    r = send_file(p, mimetype='image/png', max_age=86400)
    r.headers['X-Content-Type-Options'] = 'nosniff'
    return r


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'photo_profil.deposer', 'photo_profil.voir'})
    app.jinja_env.globals['photo_url'] = photo_url
    app.jinja_env.globals['initiales'] = initiales

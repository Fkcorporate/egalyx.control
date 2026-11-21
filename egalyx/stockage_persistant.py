"""
egalyx/stockage_persistant.py — garder les fichiers déposés d'un déploiement à l'autre (Render).

Sur Render, tout ce qui est écrit dans le dossier du projet est effacé à chaque déploiement : logos, photos de
profil, preuves, pièces jointes, lettres de mission, documents PCA… Seul un « disque persistant » est conservé.

Au démarrage, si un dossier de données est défini, les trois dossiers où l'application écrit ses fichiers
deviennent des liens vers ce disque :
    instance/        → <données>/instance        (logos, avatars, preuves, lettres de mission, PCA, réglages…)
    uploads/         → <données>/uploads
    static/uploads/  → <données>/static_uploads
Le contenu déjà présent (par exemple livré avec le dépôt) est d'abord copié sur le disque, sans jamais écraser
un fichier qui s'y trouve déjà. Aucune autre partie du code ne change : les chemins restent les mêmes.

Dossier de données :
  - variable d'environnement EGALYX_DONNEES (ex. /var/data) ;
  - sinon, sur Render, /var/data s'il s'agit d'un disque monté ;
  - sinon rien n'est fait (poste local, tests).
Plusieurs processus (gunicorn) peuvent démarrer en même temps : un verrou sur le disque évite les conflits.
"""
import logging
import os
import shutil

log = logging.getLogger('egalyx.stockage')

DOSSIERS = (('instance', None), ('uploads', 'uploads'), ('static_uploads', os.path.join('static', 'uploads')))
DEFAUT_RENDER = '/var/data'


def dossier_donnees():
    d = (os.environ.get('EGALYX_DONNEES') or '').strip()
    if d:
        return d
    if 'RENDER' in os.environ and os.path.ismount(DEFAUT_RENDER):
        return DEFAUT_RENDER
    return None


def _copier_sans_ecraser(source, cible):
    """Copie l'arborescence source dans cible ; un fichier déjà présent dans cible est conservé tel quel."""
    n = 0
    for racine, dossiers, fichiers in os.walk(source):
        rel = os.path.relpath(racine, source)
        dest = os.path.join(cible, rel) if rel != '.' else cible
        os.makedirs(dest, exist_ok=True)
        for f in fichiers:
            s, d = os.path.join(racine, f), os.path.join(dest, f)
            if not os.path.lexists(d):
                shutil.copy2(s, d)
                n += 1
    return n


def _relier(local, cible):
    """Fait de `local` un lien vers `cible` (après copie de son contenu). Rend un texte pour le journal."""
    os.makedirs(cible, exist_ok=True)
    if os.path.islink(local):
        if os.path.realpath(local) == os.path.realpath(cible):
            return f'{local} → {cible} (déjà relié)'
        os.unlink(local)
    elif os.path.isdir(local):
        n = _copier_sans_ecraser(local, cible)
        shutil.rmtree(local)
        os.symlink(cible, local)
        return f'{local} → {cible} ({n} fichier(s) recopié(s))'
    elif os.path.exists(local):
        raise RuntimeError(f'{local} existe mais n\'est pas un dossier')
    os.makedirs(os.path.dirname(local) or '.', exist_ok=True)
    os.symlink(cible, local)
    return f'{local} → {cible}'


def preparer(app, donnees=None):
    """Relie les dossiers de fichiers au disque persistant. Rend la liste des opérations (vide si rien à faire)."""
    donnees = donnees or dossier_donnees()
    if not donnees:
        return []
    os.makedirs(donnees, exist_ok=True)
    faits = []
    verrou = open(os.path.join(donnees, '.egalyx_verrou'), 'w')
    try:
        try:
            import fcntl
            fcntl.flock(verrou, fcntl.LOCK_EX)
        except ImportError:  # pragma: no cover (Windows)
            pass
        for nom, relatif in DOSSIERS:
            local = app.instance_path if relatif is None else os.path.join(app.root_path, relatif)
            try:
                faits.append(_relier(local, os.path.join(donnees, nom)))
            except Exception as e:  # ne jamais empêcher le démarrage ; le signaler clairement
                faits.append(f'⚠️ {local} : {e}')
                log.error('Stockage persistant impossible pour %s : %s', local, e)
    finally:
        verrou.close()
    app.config['EGALYX_DONNEES'] = donnees
    for f in faits:
        log.warning('Stockage persistant : %s', f)
        print(f'[egalyx] Stockage persistant : {f}', flush=True)
    return faits


def enregistrer(app):
    return preparer(app)

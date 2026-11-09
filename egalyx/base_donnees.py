"""
egalyx/base_donnees.py — mise à jour du schéma et sauvegardes.

1. Colonnes manquantes : db.create_all() crée les nouvelles tables mais n'ajoute
   jamais de colonne à une table existante. completer_schema() compare models.py à
   la base et ajoute les colonnes absentes (ALTER TABLE … ADD COLUMN, sans NOT NULL,
   avec la valeur par défaut simple du modèle). Rien n'est jamais supprimé ni modifié.
     - au démarrage (désactivable : EGALYX_MAJ_SCHEMA_AUTO=0)
     - à la demande : flask mettre-a-jour-base [--simulation]

2. Sauvegardes : SQLite (API de sauvegarde en ligne), PostgreSQL (pg_dump -Fc),
   MySQL (mysqldump), compressées, avec rétention.
     EGALYX_DOSSIER_SAUVEGARDES       (défaut <instance>/sauvegardes)
     EGALYX_SAUVEGARDE_RETENTION_JOURS (défaut 30)
     EGALYX_SAUVEGARDE_AUTO=1          sauvegarde quotidienne (heure : EGALYX_SAUVEGARDE_HEURE, défaut 2)
     flask sauvegarder
   Une sauvegarde sur le même serveur que la base ne protège pas d'une perte du
   serveur : copiez le dossier ailleurs (stockage objet, autre machine).
"""
import gzip
import logging
import os
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote

journal = logging.getLogger('egalyx.base')


# =========================================================== schéma
def _defaut_litteral(colonne, dialecte):
    """Valeur par défaut SQL d'une colonne si elle est un scalaire simple (bool, nombre, texte)."""
    d = colonne.default
    if d is None or not getattr(d, 'is_scalar', False):
        return None
    v = d.arg
    if isinstance(v, bool):
        return ('TRUE' if v else 'FALSE') if dialecte == 'postgresql' else ('1' if v else '0')
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str) and len(v) < 200:
        return "'" + v.replace("'", "''") + "'"
    return None


def colonnes_manquantes(db):
    """Liste de (table, colonne, instruction SQL) à appliquer."""
    from sqlalchemy import inspect
    moteur = db.engine
    inspecteur = inspect(moteur)
    tables_existantes = set(inspecteur.get_table_names())
    prepare = moteur.dialect.identifier_preparer
    dialecte = moteur.dialect.name
    a_faire = []
    # metadata.tables (et non sorted_tables) : pas de résolution des clés étrangères,
    # donc un modèle mal déclaré ailleurs ne bloque pas l'ajout des colonnes.
    for table in db.metadata.tables.values():
        if table.name not in tables_existantes:
            continue                      # create_all() s'en charge
        try:
            presentes = {c['name'] for c in inspecteur.get_columns(table.name)}
        except Exception as e:
            journal.warning("Table %s illisible : %s", table.name, e)
            continue
        for col in table.columns:
            if col.name in presentes:
                continue
            try:
                type_sql = col.type.compile(dialect=moteur.dialect)
            except Exception as e:
                journal.warning("Type non traduisible %s.%s : %s", table.name, col.name, e)
                continue
            sql = f"ALTER TABLE {prepare.quote(table.name)} ADD COLUMN {prepare.quote(col.name)} {type_sql}"
            defaut = _defaut_litteral(col, dialecte)
            if defaut is not None:
                sql += f" DEFAULT {defaut}"
            a_faire.append((table.name, col.name, sql))
    return a_faire


def completer_schema(db, simulation=False):
    """Ajoute les colonnes manquantes. Retourne la liste des instructions (appliquées ou non)."""
    from sqlalchemy import text
    instructions = colonnes_manquantes(db)
    if simulation or not instructions:
        return instructions
    appliquees = []
    for table, colonne, sql in instructions:
        try:
            with db.engine.begin() as cnx:
                cnx.execute(text(sql))
            appliquees.append((table, colonne, sql))
            journal.info("Colonne ajoutée : %s.%s", table, colonne)
        except Exception as e:     # une autre instance l'a peut-être ajoutée entre-temps
            journal.warning("Colonne %s.%s non ajoutée : %s", table, colonne, e)
    return appliquees


# =========================================================== sauvegardes
def dossier_sauvegardes(app):
    d = os.environ.get('EGALYX_DOSSIER_SAUVEGARDES') or os.path.join(app.instance_path, 'sauvegardes')
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def _chemin_sqlite(url, app):
    chemin = url.split(':///', 1)[1] if ':///' in url else ''
    if not chemin or chemin == ':memory:':
        return None
    if not os.path.isabs(chemin):
        for base in (app.instance_path, app.root_path, os.getcwd()):
            if os.path.exists(os.path.join(base, chemin)):
                return os.path.join(base, chemin)
        return os.path.join(app.instance_path, chemin)
    return chemin


def _compresser(source, cible):
    with open(source, 'rb') as e, gzip.open(cible, 'wb', compresslevel=6) as s:
        shutil.copyfileobj(e, s)
    os.remove(source)
    os.chmod(cible, 0o600)


def sauvegarder(app, url=None):
    """Crée une sauvegarde compressée. Retourne le chemin du fichier. Lève une exception en cas d'échec."""
    url = url or app.config.get('SQLALCHEMY_DATABASE_URI') or ''
    dossier = dossier_sauvegardes(app)
    horodatage = datetime.now().strftime('%Y%m%d-%H%M%S')
    verrou = os.path.join(dossier, '.en_cours')
    # Évite deux sauvegardes simultanées (plusieurs workers) : verrou de 1 h maximum
    if os.path.exists(verrou) and time.time() - os.path.getmtime(verrou) < 3600:
        raise RuntimeError("Une sauvegarde est déjà en cours.")
    open(verrou, 'w').close()
    try:
        if url.startswith('sqlite'):
            chemin = _chemin_sqlite(url, app)
            if not chemin or not os.path.exists(chemin):
                raise RuntimeError(f"Fichier SQLite introuvable ({chemin}).")
            brut = os.path.join(dossier, f'egalyx-{horodatage}.sqlite')
            src = sqlite3.connect(chemin)
            dst = sqlite3.connect(brut)
            with dst:
                src.backup(dst)      # copie cohérente même si l'application écrit
            src.close(); dst.close()
        elif url.startswith(('postgresql', 'postgres')):
            u = urlparse(url.replace('+psycopg2', '').replace('+pg8000', ''))
            brut = os.path.join(dossier, f'egalyx-{horodatage}.dump')
            env = dict(os.environ, PGPASSWORD=unquote(u.password or ''))
            cmd = ['pg_dump', '-Fc', '--no-owner', '-h', u.hostname or 'localhost', '-p', str(u.port or 5432),
                   '-U', unquote(u.username or ''), '-f', brut, u.path.lstrip('/')]
            subprocess.run(cmd, env=env, check=True, capture_output=True, timeout=3600)
        elif url.startswith('mysql'):
            u = urlparse(url.split('?')[0].replace('+pymysql', '').replace('+mysqldb', ''))
            brut = os.path.join(dossier, f'egalyx-{horodatage}.sql')
            env = dict(os.environ, MYSQL_PWD=unquote(u.password or ''))
            with open(brut, 'wb') as sortie:
                subprocess.run(['mysqldump', '--single-transaction', '--routines', '-h', u.hostname or 'localhost',
                                '-P', str(u.port or 3306), '-u', unquote(u.username or ''), u.path.lstrip('/')],
                               env=env, check=True, stdout=sortie, stderr=subprocess.PIPE, timeout=3600)
        else:
            raise RuntimeError("Type de base non pris en charge pour la sauvegarde automatique.")
        cible = brut + '.gz'
        _compresser(brut, cible)
        purger(app)
        journal.info("Sauvegarde créée : %s", cible)
        return cible
    finally:
        try:
            os.remove(verrou)
        except OSError:
            pass


def purger(app, jours=None):
    jours = jours or int(os.environ.get('EGALYX_SAUVEGARDE_RETENTION_JOURS') or 30)
    limite = time.time() - jours * 86400
    dossier = dossier_sauvegardes(app)
    supprimes = 0
    for nom in os.listdir(dossier):
        p = os.path.join(dossier, nom)
        if nom.startswith('egalyx-') and nom.endswith('.gz') and os.path.getmtime(p) < limite:
            os.remove(p)
            supprimes += 1
    return supprimes


def lister(app):
    dossier = dossier_sauvegardes(app)
    fichiers = []
    for nom in sorted(os.listdir(dossier), reverse=True):
        if nom.startswith('egalyx-') and nom.endswith('.gz'):
            p = os.path.join(dossier, nom)
            fichiers.append({'nom': nom, 'taille': os.path.getsize(p),
                             'date': datetime.fromtimestamp(os.path.getmtime(p))})
    return fichiers


def etat(app):
    """Résumé pour la page super admin et le contrôle de santé."""
    f = lister(app)
    derniere = f[0]['date'] if f else None
    return {'nombre': len(f), 'derniere': derniere, 'fichiers': f[:60],
            'en_retard': (derniere is None) or (datetime.now() - derniere > timedelta(hours=36)),
            'auto': os.environ.get('EGALYX_SAUVEGARDE_AUTO', '1') == '1',
            'dossier': dossier_sauvegardes(app),
            'retention': int(os.environ.get('EGALYX_SAUVEGARDE_RETENTION_JOURS') or 30)}


# =========================================================== branchement
def enregistrer(app, db):
    import click
    app.register_blueprint(_blueprint(app))

    @app.cli.command('mettre-a-jour-base')
    @click.option('--simulation', is_flag=True, help="Affiche les instructions sans les appliquer.")
    def _cli_maj(simulation):
        """Ajoute à la base les colonnes définies dans models.py et absentes des tables."""
        if not simulation:
            try:
                db.create_all()
            except Exception as e:
                print(f"⚠️ Création des nouvelles tables incomplète : {e}")
        res = completer_schema(db, simulation=simulation)
        if not res:
            print("✅ Schéma à jour : aucune colonne manquante.")
        for _t, _c, sql in res:
            print(("[simulation] " if simulation else "✅ ") + sql)

    @app.cli.command('sauvegarder')
    def _cli_sauvegarder():
        """Crée une sauvegarde compressée de la base."""
        print("✅ Sauvegarde :", sauvegarder(app))

    if os.environ.get('EGALYX_MAJ_SCHEMA_AUTO', '1') == '1':
        with app.app_context():
            try:
                db.create_all()
            except Exception as e:
                print(f"⚠️ Création des nouvelles tables incomplète : {e}")
            try:
                res = completer_schema(db)
                if res:
                    print(f"✅ Schéma complété : {len(res)} colonne(s) ajoutée(s).")
            except Exception as e:
                print(f"⚠️ Ajout des colonnes manquantes impossible : {e} — lancez « flask mettre-a-jour-base ».")

    # Sauvegarde quotidienne. Avec le rechargeur de Flask, seul le processus enfant planifie.
    if os.environ.get('EGALYX_SAUVEGARDE_AUTO', '1') == '1' and \
            (not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            heure = int(os.environ.get('EGALYX_SAUVEGARDE_HEURE') or 2)
            planif = BackgroundScheduler(daemon=True)

            def _tache():
                try:
                    with app.app_context():
                        sauvegarder(app)
                except Exception as e:
                    journal.error("Sauvegarde quotidienne échouée : %s", e)
            planif.add_job(_tache, 'cron', hour=heure, minute=17, id='egalyx_sauvegarde', replace_existing=True,
                           misfire_grace_time=3600, coalesce=True)
            planif.start()
            app.extensions['egalyx_planificateur'] = planif
        except Exception as e:
            print(f"⚠️ Sauvegarde automatique non planifiée : {e}")


# =========================================================== page super admin
def _blueprint(app):
    from flask import Blueprint, flash, redirect, render_template, url_for
    from egalyx.commun import super_admin_requis
    bp = Blueprint('sauvegardes', __name__, url_prefix='/super-admin/sauvegardes')

    @bp.route('/', methods=['GET', 'POST'])
    @super_admin_requis
    def page():
        from flask import request
        if request.method == 'POST':
            try:
                chemin = sauvegarder(app)
                flash(f'Sauvegarde créée : {os.path.basename(chemin)}', 'success')
            except Exception as e:
                flash(f'Sauvegarde impossible : {e}', 'danger')
            return redirect(url_for('.page'))
        from models import db
        try:
            manquantes = colonnes_manquantes(db)
        except Exception:
            manquantes = []
        return render_template('egalyx/sauvegardes.html', e=etat(app), manquantes=manquantes)
    return bp

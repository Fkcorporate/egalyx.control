"""Recette : migrations Alembic / Flask-Migrate (révision de référence egalyx_0001_reference).

Sur une base à part (EGALYX_BASE_TEST) :
  A. base vidée -> upgrade : toutes les tables du modèle, révision enregistrée
  B. base « ancienne » (une table et des colonnes manquantes, sans suivi Alembic) -> upgrade : tout est complété,
     les données existantes sont intactes
  C. upgrade une 2e fois : rien ne change
  D. une seule tête de révision ; la référence ne se défait pas (downgrade refusé)
  E. le schéma complet se génère pour PostgreSQL (base de production)
"""
import os
import sys
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
os.environ['EGALYX_MAJ_SCHEMA_AUTO'] = '0'
os.environ['EGALYX_BASE_TEST'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recette_migrations.db')
if os.path.exists(os.environ['EGALYX_BASE_TEST']):
    os.remove(os.environ['EGALYX_BASE_TEST'])
import socle  # noqa: E402
from socle import Muet  # noqa: E402

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A = socle.charger(reinitialiser=False)
app = A.app
from models import db  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
import flask_migrate  # noqa: E402

DOSSIER = os.path.join(app.root_path, 'migrations')
TETE = 'egalyx_0005_satisfaction_audit'   # dernière révision (0001 : référence ; 0002 : heure, devise, lettres ; 0003 : statuts ;
                                           # 0004 : dossier de mission figé ; 0005 : satisfaction des audités)


def tables():
    return set(inspect(db.engine).get_table_names())


def version():
    with db.engine.connect() as c:
        try:
            return [r[0] for r in c.execute(text('SELECT version_num FROM alembic_version'))]
        except Exception:  # noqa: BLE001
            return None


def upgrade():
    with Muet():
        flask_migrate.upgrade(directory=DOSSIER)


modele = set(db.metadata.tables)
with app.app_context():
    print('--- A. Base vide')
    with db.engine.begin() as c:
        c.execute(text('PRAGMA foreign_keys=OFF'))
        for t in tables():
            c.execute(text(f'DROP TABLE IF EXISTS "{t}"'))
    verif('base réellement vide au départ', not tables())
    upgrade()
    manquantes = modele - tables()
    verif(f'upgrade : les {len(modele)} tables du modèle sont créées', not manquantes, str(sorted(manquantes)[:5]))
    verif('révision de référence enregistrée', version() == [TETE], str(version()))

    print('--- B. Base ancienne (table et colonnes manquantes, sans suivi des migrations)')
    from models import User
    with Muet():
        socle.peupler(A)
    referencees = {fk.column.table.name for t in db.metadata.tables.values() for fk in t.foreign_keys}
    feuille = sorted(t for t in modele if t not in referencees and t != 'alembic_version')[0]
    with db.engine.begin() as c:
        c.execute(text('PRAGMA foreign_keys=OFF'))
        c.execute(text(f'DROP TABLE "{feuille}"'))
        for col in ('fonction', 'prenom'):
            c.execute(text(f'ALTER TABLE "user" DROP COLUMN {col}'))
        c.execute(text('DROP TABLE alembic_version'))
    cols = {x['name'] for x in inspect(db.engine).get_columns('user')}
    verif(f'préparation : table « {feuille} » et colonnes user.fonction / user.prenom retirées',
          feuille not in tables() and 'fonction' not in cols and 'prenom' not in cols)
    def compter():
        with db.engine.connect() as c:
            return (c.execute(text('SELECT COUNT(*) FROM clients')).scalar(),
                    c.execute(text('SELECT COUNT(*) FROM "user"')).scalar())
    nb_clients = compter()
    upgrade()
    cols = {x['name'] for x in inspect(db.engine).get_columns('user')}
    verif('upgrade : la table manquante est recréée', feuille in tables())
    verif('upgrade : les colonnes manquantes sont ajoutées', {'fonction', 'prenom'} <= cols)
    verif('upgrade : données existantes intactes', compter() == nb_clients and nb_clients[1] >= 7, str(nb_clients))
    verif('base désormais suivie (révision de référence)', version() == [TETE], str(version()))

    print('--- C. Deuxième passage')
    avant = {t: sorted(x['name'] for x in inspect(db.engine).get_columns(t)) for t in tables()}
    upgrade()
    apres = {t: sorted(x['name'] for x in inspect(db.engine).get_columns(t)) for t in tables()}
    verif('upgrade une 2e fois : rien ne change', avant == apres and version() == [TETE])

    print('--- C2. Base marquée par une ancienne révision disparue')
    with db.engine.begin() as c:
        c.execute(text("UPDATE alembic_version SET version_num = 'add_password_security'"))
        c.execute(text('ALTER TABLE "user" DROP COLUMN fonction'))
    upgrade()
    cols = {x['name'] for x in inspect(db.engine).get_columns('user')}
    verif('révision inconnue oubliée, référence appliquée, colonne rétablie', version() == [TETE] and 'fonction' in cols, str(version()))

    print('--- C3. Révision 0002 sur une base restée en 0001')
    with db.engine.begin() as c:
        c.execute(text('DROP TABLE modeles_lettre_mission'))
        c.execute(text('ALTER TABLE clients DROP COLUMN devise'))
        c.execute(text("UPDATE alembic_version SET version_num = 'egalyx_0001_reference'"))
    upgrade()
    verif('0002 : colonne clients.devise et table des modèles de lettre ajoutées',
          'devise' in {x['name'] for x in inspect(db.engine).get_columns('clients')} and 'modeles_lettre_mission' in tables() and version() == [TETE], str(version()))

    print('--- D. Chaîne de révisions')
    from alembic.script import ScriptDirectory
    from alembic.config import Config
    cfg = Config(os.path.join(DOSSIER, 'alembic.ini')); cfg.set_main_option('script_location', DOSSIER)
    sd = ScriptDirectory.from_config(cfg)
    verif('une seule tête de révision', sd.get_heads() == [TETE], str(sd.get_heads()))
    verif('chaîne propre : 0001 -> 0002 -> 0003 -> 0004 -> 0005', [r.revision for r in sd.walk_revisions()] == [
        TETE, 'egalyx_0004_dossier_fige', 'egalyx_0003_statuts', 'egalyx_0002_localisation_lettres', 'egalyx_0001_reference'])
    try:
        with Muet():
            flask_migrate.downgrade(directory=DOSSIER, revision='base')
        refuse = False
    except BaseException as e:  # noqa: BLE001
        refuse = True
    verif('la référence ne se défait pas (protection contre une perte de données)', refuse and modele <= tables() | {'alembic_version'})

print('--- E. PostgreSQL')
from sqlalchemy import create_mock_engine  # noqa: E402
ddl = []
moteur = create_mock_engine('postgresql+psycopg2://', lambda sql, *a, **k: ddl.append(str(sql.compile(dialect=moteur.dialect))))
try:
    db.metadata.create_all(moteur, checkfirst=False)
    ok = True
except Exception as e:  # noqa: BLE001
    ok = False; print('   ', e)
verif(f'schéma complet généré pour PostgreSQL ({sum(1 for x in ddl if x.strip().startswith("CREATE TABLE"))} tables)', ok and sum(1 for x in ddl if x.strip().startswith('CREATE TABLE')) == len(modele))

try:
    os.remove(os.environ['EGALYX_BASE_TEST'])
except OSError:
    pass
print(f'\n{sum(res)}/{len(res)} vérifications réussies')

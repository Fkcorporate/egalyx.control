"""Recette : sources de données KRI — plus de lecture de la base Egalyx, des fichiers du serveur ou du réseau interne."""
import datetime as dt
import socle
from socle import Muet
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import objets
import models as M
from models import db
from sqlalchemy import text
from egalyx import kri_sources_securite as S
with Muet():
    try: objets.peupler_objets(A, ids)
    except TypeError: objets.peupler_objets(A)
A.app.config['WTF_CSRF_ENABLED'] = False
fichier_base = A.app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
ATTAQUE = {'nom': 'x', 'type_source': 'base_donnees', 'frequence_rafraichissement': 86400, 'bdd_type': 'sqlite',
           'bdd_nom': fichier_base, 'bdd_requete': 'select username, client_id from user', 'auth_type': '',
           'api_method': 'GET', 'fichier_format': 'csv'}


def nb_sources():
    with A.app.app_context():
        return M.SourceDonnee.query.count()


# 1. réservé au super-administrateur
for role in ('admin_a', 'gestionnaire', 'operateur', 'lecteur'):
    c = socle.navigateur(A, ids[role]); n = nb_sources()
    r1 = c.get('/kri/sources'); r2 = c.post('/kri/sources/nouvelle', data=ATTAQUE)
    verif(f'{role} : sources interdites (liste {r1.status_code}, création {r2.status_code})',
          r1.status_code in (302, 403) and r2.status_code in (302, 403) and nb_sources() == n)
    r = c.get('/api/kri/sources/disponibles')
    verif(f'{role} : API des sources interdite', r.status_code in (302, 403), str(r.status_code))

# 2. même le super-admin ne peut plus créer de source dangereuse
sa = socle.navigateur(A, ids['superadmin'])
r = sa.get('/kri/sources'); verif('super-admin : liste des sources accessible', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
for nom, d in (('SQLite (base Egalyx)', ATTAQUE),
               ('fichier du serveur', dict(ATTAQUE, type_source='fichier', fichier_chemin='/etc/passwd')),
               ('API en http', dict(ATTAQUE, type_source='api', api_url='http://8.8.8.8/x')),
               ('API locale', dict(ATTAQUE, type_source='api', api_url='https://127.0.0.1/x')),
               ('API métadonnées cloud', dict(ATTAQUE, type_source='api', api_url='https://169.254.169.254/latest')),
               ('API réseau privé', dict(ATTAQUE, type_source='api', api_url='https://10.0.0.5/x')),
               ('PostgreSQL interne', dict(ATTAQUE, bdd_type='postgresql', bdd_host='127.0.0.1', bdd_port=5432))):
    n = nb_sources(); r = sa.post('/kri/sources/nouvelle', data=d, follow_redirects=True)
    t = r.get_data(as_text=True)
    verif(f'super-admin : {nom} refusé', nb_sources() == n and r.status_code == 200 and 'Source refusée' in t,
          f'{r.status_code} {socle.cause(A)}')
n = nb_sources()
sa.post('/kri/sources/nouvelle', data=dict(ATTAQUE, type_source='api', api_url='https://8.8.8.8/indicateurs'))
verif('super-admin : API https publique acceptée', nb_sources() == n + 1)

# 3. une ancienne source dangereuse déjà en base ne lit plus rien
with A.app.app_context():
    cid = db.session.get(M.User, ids['gestionnaire']).client_id
    db.session.execute(text("INSERT INTO sources_donnees (nom, type_source, config_connexion, statut, client_id, frequence_rafraichissement) "
                            "VALUES ('ancienne', 'base_donnees', :c, 'actif', :cid, 86400)"),
                       {'c': '{"type": "sqlite", "database": "%s", "requete": "select username from user"}' % fichier_base, 'cid': cid})
    db.session.commit()
    sid = db.session.execute(text("select max(id) from sources_donnees")).scalar()
    k = M.KRI.query.filter_by(client_id=cid).first()
    if k is None:
        k = M.KRI(nom='KRI recette', client_id=cid, type_indicateur='kri', seuil_alerte=10, seuil_critique=20); db.session.add(k); db.session.commit()
    db.session.execute(text("INSERT INTO source_kri_links (source_id, kri_id, est_actif) VALUES (:s, :k, 1)"), {'s': sid, 'k': k.id})
    db.session.commit()
    from collecte_engine import CollecteEngine
    nm = M.MesureKRI.query.count()
    out = CollecteEngine(A.app, db).collecter_source(sid, force=True)
    db.session.rollback()
    texte = str(out)
    verif('ancienne source SQLite : collecte refusée, aucune donnée', M.MesureKRI.query.count() == nm and 'username' not in texte
          and 'recette' not in texte.lower() and out.get('erreurs'), texte[:160])
    try:
        CollecteEngine(A.app, db)._recuperer_depuis_fichier({'chemin': '/etc/passwd'}); ok = False
    except S.SourceRefusee:
        ok = True
    verif('lecture de fichier du serveur impossible', ok)
    cle = 'nom_de_la_cle'
    verif('erreurs techniques masquées', 'could not' not in S._message_public("could not convert string to float: 'SECRET'")
          and 'SECRET' not in S._message_public("could not convert string to float: 'SECRET'"))

# 4. formules sans eval
verif('formule : moyenne', S.calculer('sum(donnees) / len(donnees)', {'donnees': [2, 4, 6]}) == 4)
for f in ("().__class__.__bases__", "__import__('os')", "donnees.__class__", "open('/etc/passwd')", "9**9**9"):
    try:
        S.calculer(f, {'donnees': [1]}); ok = False
    except Exception:
        ok = True
    verif(f'formule refusée : {f}', ok)

# 5. statistiques par date, routes en double, page détail
with A.app.app_context():
    k = M.KRI.query.filter_by(client_id=cid).first(); kid = k.id
    for m in list(k.mesures): db.session.delete(m)
    db.session.add(M.MesureKRI(kri_id=kid, valeur=99, date_mesure=dt.datetime(2026, 10, 1), client_id=cid))
    db.session.add(M.MesureKRI(kri_id=kid, valeur=11, date_mesure=dt.datetime(2026, 11, 1), client_id=cid))
    db.session.add(M.MesureKRI(kri_id=kid, valeur=55, date_mesure=dt.datetime(2026, 9, 1), client_id=cid))  # saisie en retard
    db.session.commit()
    verif('statistiques : dernière valeur = la plus récente par date', db.session.get(M.KRI, kid).get_statistiques()['derniere_valeur'] == 11)
g = socle.navigateur(A, ids['gestionnaire'])
r = g.get(f'/kri/{kid}/modifier'); verif('modifier un KRI : page OK', r.status_code == 200, f'{r.status_code} {socle.cause(A)}')
for qui, cl, attendu in (('gestionnaire', g, False), ('super-admin', sa, True)):
    r = cl.get(f'/kri/{kid}'); t = r.get_data(as_text=True)
    if r.status_code in (301, 302):
        r = cl.get(r.headers['Location']); t = r.get_data(as_text=True)
    verif(f'fiche KRI ({qui}) : bouton « Gérer les sources » {"visible" if attendu else "masqué"}',
          r.status_code == 200 and (('Gérer les sources' in t) == attendu), f'{r.status_code} {socle.cause(A)}')
print(f'\n{sum(res)}/{len(res)}')

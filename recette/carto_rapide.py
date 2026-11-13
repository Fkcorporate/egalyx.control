"""Recette : fiche cartographie rapide (requêtes, matrices en cache, compression) + réglage de clôture des campagnes."""
import gzip
import os
import random
import re
import sys
import time
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel, creer
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import objets
import models as M
from models import db
from sqlalchemy import event
with Muet():
    O = objets.peupler_objets(A, ids)
N = 60
random.seed(3)
with A.app.app_context():
    d = creer(M.Direction, nom='Direction perf', client_id=1)
    carto = creer(M.Cartographie, nom='Carto perf', client_id=1, direction_id=d.id, created_by=ids['admin_a'])
    camp = creer(M.CampagneEvaluation, cartographie_id=carto.id, nom='Campagne 2026', statut='en_cours', client_id=1)
    for i in range(N):
        r = creer(M.Risque, reference=f'R-{i:03d}', intitule=f'Risque {i}', cartographie_id=carto.id, client_id=1, created_by=ids['admin_a'])
        for j in range(2 if i % 5 else 0):
            creer(M.DispositifMaitrise, reference=f'DM-{i:03d}-{j}', nom=f'Contrôle {i}.{j}', risque_id=r.id, client_id=1, statut='actif',
                  efficacite_reelle=random.randint(1, 5), created_by=ids['admin_a'])
        if i % 7:
            creer(M.EvaluationRisque, risque_id=r.id, campagne_id=camp.id, client_id=1, impact_pre=random.randint(1, 5),
                  probabilite_pre=random.randint(1, 5), niveau_maitrise_pre=random.randint(1, 5))
    db.session.commit(); CID, CAMP = carto.id, camp.id
compte, ecritures = [0], [0]
with A.app.app_context():
    def _compter(conn, cur, stmt, *a):
        compte[0] += 1
        if stmt.lstrip().upper().startswith(('UPDATE', 'INSERT', 'DELETE')):
            ecritures[0] += 1
    event.listen(db.engine, 'before_cursor_execute', _compter)


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore') if r.headers.get('Content-Encoding') != 'gzip' else '', socle.cause(A)


print('--- Fiche cartographie')
c = socle.navigateur(A, ids['admin_a'])
with Muet():
    c.get(f'/cartographie/{CID}')
compte[0] = ecritures[0] = 0; t = time.perf_counter()
with Muet():
    r = c.get(f'/cartographie/{CID}')
duree = time.perf_counter() - t
html = r.data.decode()
verif('page affichée', r.status_code == 200, socle.cause(A))
verif(f'peu de requêtes SQL ({compte[0]} pour {N} risques ; avant : ~12 par risque)', compte[0] < 60, str(compte[0]))
verif('aucune écriture en base quand rien ne change', ecritures[0] == 0, str(ecritures[0]))
verif(f'rapide ({duree:.2f} s)', duree < 1.0)
verif('matrices plus intégrées en base64 dans la page', 'data:image/png;base64,' not in html)
urls = [u.replace('&amp;', '&') for u in re.findall(r'src="(/cartographie/\d+/matrice/[^"]+)"', html)]
verif('4 matrices en images séparées', len(urls) == 4, str(urls))

print('--- Même contenu que l\'ancienne fiche')
from flask_login import login_user
ancien = sys.modules[A.app.import_name].detail_cartographie
from egalyx import carto_rapide
jeton = lambda h: re.sub(r'I[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{10,}', 'J', re.sub(
    r'src="[^"]*matrice[^"]*"|src="data:image/png;base64,[^"]*"', 'src="M"', h))
sortie = {}
for nom, f in (('ancien', ancien), ('nouveau', carto_rapide.detail_cartographie)):
    with A.app.test_request_context(f'/cartographie/{CID}'):
        login_user(db.session.get(M.User, ids['admin_a']))
        with Muet():
            sortie[nom] = jeton(f(CID))
verif('HTML identique à l\'ancienne version (hors images)', sortie['ancien'] == sortie['nouveau'],
      f"{len(sortie['ancien'])} / {len(sortie['nouveau'])}")

print('--- Images des matrices')
res_img = []
for u in urls:
    x = c.get(u)
    res_img.append((x.status_code, x.mimetype, len(x.data)))
verif('images PNG valides', all(s == 200 and m == 'image/png' and n > 5000 for s, m, n in res_img), str(res_img))
dossier = os.path.join(A.app.instance_path, 'cache_matrices')
def _couleurs(octets):
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(octets)).convert('RGB'); im.thumbnail((200, 200))
    return len(set(im.getdata()))
coul = [_couleurs(c.get(u).data) for u in urls]
verif('images NON vides (vraie matrice dessinée)', all(n > 20 for n in coul), str(coul))
verif('mises en cache sur disque', os.path.isdir(dossier) and len([f for f in os.listdir(dossier) if f.endswith('.png')]) >= 4)
x = c.get(urls[0]); etag = x.headers.get('ETag')
x2 = c.get(urls[0], headers={'If-None-Match': etag})
verif('navigateur : 304 « non modifié » avec l\'ETag', x2.status_code == 304, str(x2.status_code))
with A.app.app_context():
    e = M.EvaluationRisque.query.filter_by(campagne_id=CAMP).first()
    e.impact_pre = 6 - (e.impact_pre or 1) if (e.impact_pre or 1) != 3 else 5; db.session.commit()
with Muet():
    html2 = c.get(f'/cartographie/{CID}').data.decode()
urls2 = [u.replace('&amp;', '&') for u in re.findall(r'src="(/cartographie/\d+/matrice/[^"]+)"', html2)]
verif('cotation modifiée : nouvelle image (le cache ne sert pas une matrice périmée)', urls2 and urls2[0] != urls[0])
r, _, _ = go('admin_b', 'get', urls[0])
verif('autre organisation : image refusée', r.status_code in (403, 404), str(r.status_code))
r, _, _ = go('lecteur', 'get', urls[0])
verif('sans « Gérer les risques » : image refusée', r.status_code in (302, 403, 404), str(r.status_code))
r, _, _ = go('admin_a', 'get', f'/cartographie/{CID}/matrice/inconnu.png')
verif('type de matrice inconnu : 404', r.status_code == 404)
import shutil, threading
shutil.rmtree(dossier, ignore_errors=True)
paral = {}
# 4 demandes simultanées (comme le navigateur) sur un vrai serveur multi-fils
from werkzeug.serving import make_server
srv = make_server('127.0.0.1', 0, A.app, threaded=True); port = srv.server_port
th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
import requests as _rq
sess_http = _rq.Session()
nom_ck = A.app.config.get('SESSION_COOKIE_NAME', 'session')
ck = c.get_cookie(nom_ck)
sess_http.cookies.set(nom_ck, ck.value if ck else '', domain='127.0.0.1')
with Muet():
    html3 = sess_http.get(f'http://127.0.0.1:{port}/cartographie/{CID}').text
urls3 = [u.replace('&amp;', '&') for u in re.findall(r'src="(/cartographie/\d+/matrice/[^"]+)"', html3)]
def _get(u):
    x = sess_http.get(f'http://127.0.0.1:{port}{u}')
    paral[u] = (x.status_code, _couleurs(x.content) if x.status_code == 200 else 0)
with Muet():
    fils = [threading.Thread(target=_get, args=(u,)) for u in urls3]
    [f.start() for f in fils]; [f.join() for f in fils]
srv.shutdown()
verif('4 matrices demandées en même temps : toutes dessinées', len(urls3) == 4 and all(v and v[0] == 200 and v[1] > 20 for v in paral.values()), str(paral))

print('--- Compression')
z = c.get(f'/cartographie/{CID}', headers={'Accept-Encoding': 'gzip, deflate, br'})
brut = len(html2.encode())
verif(f'page compressée ({brut // 1024} Ko → {len(z.data) // 1024} Ko)', z.headers.get('Content-Encoding') == 'gzip'
      and len(z.data) < brut / 5 and 'Accept-Encoding' in z.headers.get('Vary', ''))
with Muet():
    normal = c.get(f'/cartographie/{CID}').data.decode()
verif('contenu décompressé identique', jeton(gzip.decompress(z.data).decode()) == jeton(normal))
z = c.get(urls[0], headers={'Accept-Encoding': 'gzip'})
verif('images non recompressées', z.headers.get('Content-Encoding') is None and z.mimetype == 'image/png')
z = c.get(f'/cartographie/{CID}')
verif('navigateur sans gzip : page normale', z.headers.get('Content-Encoding') is None and z.status_code == 200)
z = c.get('/manifest.webmanifest', headers={'Accept-Encoding': 'gzip'})
verif('petite réponse (< 2 Ko) : non compressée', z.headers.get('Content-Encoding') is None)

print('--- Réglage : clôture des campagnes d\'évaluation')
from egalyx import cloture_campagne as cc


def jeton_csrf(role):
    cl = socle.navigateur(A, ids[role])
    with Muet():
        t = cl.get('/dashboard').data.decode('utf-8', 'ignore')
    m = re.search(r'name="csrf-token" content="([^"]+)"', t)
    return cl, (m.group(1) if m else '')


def nouvelle_campagne():
    with A.app.app_context():
        for x in M.CampagneEvaluation.query.filter_by(cartographie_id=O['a']['carto'], statut='en_cours'):
            x.statut = 'terminee'
        x = creer(M.CampagneEvaluation, cartographie_id=O['a']['carto'], nom='À clôturer', statut='en_cours', client_id=1)
        db.session.commit(); return x.id


def cloturer(role):
    cid = nouvelle_campagne()
    cl, j = jeton_csrf(role)
    with Muet():
        cl.get(f"/cartographie/{O['a']['carto']}/cloturer-campagne/{cid}?csrf_token={j}")
    with A.app.app_context():
        return db.session.get(M.CampagneEvaluation, cid).statut == 'terminee'


def regler(choix, role='admin_a'):
    cl, j = jeton_csrf(role)
    with Muet():
        return cl.post('/parametres/risques/campagnes/', data={'cloture': choix, 'csrf_token': j})


with A.app.app_context():
    verif('par défaut : « tous » (comportement actuel inchangé)', cc.reglage(1) == 'tous')
verif('par défaut : le valideur peut toujours clôturer (inchangé)', cloturer('validateur'))
r, t, e = go('admin_a', 'get', '/parametres/risques/campagnes/')
verif('page de réglage : 3 choix, « Par défaut » signalé', r.status_code == 200 and t.count('name="cloture"') == 3 and 'Par défaut' in t, f'{r.status_code} {e}')
r, t, _ = go('admin_a', 'get', '/parametres/risques/')
verif('lien depuis « Paramètres des risques »', 'Clôture des campagnes d' in t)
r, _, _ = go('lecteur', 'get', '/parametres/risques/campagnes/')
verif('sans droit de paramétrage : page refusée', r.status_code == 302, str(r.status_code))
r = regler('gestionnaires', 'lecteur')
with A.app.app_context():
    verif('sans droit de paramétrage : enregistrement refusé', cc.reglage(1) == 'tous')
regler('n_importe_quoi')
with A.app.app_context():
    verif('choix invalide : refusé', cc.reglage(1) == 'tous')

regler('gestionnaires')
with A.app.app_context():
    verif('réglage « gestionnaires » enregistré', cc.reglage(1) == 'gestionnaires')
    verif('autre organisation non touchée', cc.reglage(2) == 'tous')
verif('« gestionnaires » : le valideur ne peut plus clôturer (lien direct)', not cloturer('validateur'))
verif('« gestionnaires » : le gestionnaire des risques peut', cloturer('gestionnaire'))
verif('« gestionnaires » : l\'administrateur peut', cloturer('admin_a'))
nouvelle_campagne()
r, t, _ = go('validateur', 'get', f"/cartographie/{O['a']['carto']}/campagnes")
r2, t2, _ = go('gestionnaire', 'get', f"/cartographie/{O['a']['carto']}/campagnes")
verif('bouton « Clôturer la campagne » masqué pour le valideur, visible pour le gestionnaire',
      (r.status_code != 200 or 'Clôturer la campagne</a>' not in t.replace('\n', '').replace('  ', '')) and
      (r2.status_code != 200 or 'Clôturer la campagne' in t2), f'{r.status_code} {r2.status_code}')
regler('administrateurs')
verif('« administrateurs » : le gestionnaire ne peut plus', not cloturer('gestionnaire'))
verif('« administrateurs » : l\'administrateur peut', cloturer('admin_a'))
regler('tous')
verif('retour à « tous » : le valideur peut de nouveau', cloturer('validateur'))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')

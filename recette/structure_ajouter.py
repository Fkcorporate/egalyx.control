"""Recette : « Ajouter » depuis l'arborescence (Structure de l'organisation) — pays, pôle, direction, service
s'enregistrent SANS responsable (« À pourvoir ») et reviennent sur l'arborescence."""
import os
import re
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
import models as M

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


admin, lect = socle.navigateur(A, ids['admin_a']), socle.navigateur(A, ids['lecteur'])


def envoyer(c, url, data):
    h = appel(c, 'get', url).data.decode(errors='ignore')
    t = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', h) or re.search(r'value="([^"]+)"[^>]*name="csrf_token"', h)
    return appel(c, 'post', url, data={'csrf_token': t.group(1) if t else '', **data})


r = appel(admin, 'get', '/admin/directions')
liens = set(re.findall(r'href="(/admin/(?:pays|pole|direction|service)/[^"]*nouve[^"]*)"', r.data.decode()))
verif('arborescence : menu « Ajouter » et boutons « + » présents', r.status_code == 200 and len(liens) >= 3, len(liens))
R = '?retour=/admin/directions'
r = envoyer(admin, '/admin/pays/nouveau' + R, {'nom': 'Côte d’Ivoire', 'code': 'CI', 'ordre': '0'})
verif('pays : créé, retour sur l’arborescence', r.status_code == 302 and r.headers.get('Location') == '/admin/directions', r.status_code)
r = envoyer(admin, '/admin/pole/nouveau' + R, {'nom': 'Pôle Finance', 'ordre': '0', 'pays_id': '0', 'couleur': '#3b82f6',
                                               'type_responsable': 'utilisateur', 'responsable_id': '0'})
verif('pôle sans responsable : créé (avant : « Veuillez sélectionner un responsable »)', r.status_code == 302
      and r.headers.get('Location') == '/admin/directions', r.status_code)
with A.app.app_context():
    pole = M.Pole.query.filter_by(client_id=1, nom='Pôle Finance').first()
    PID = pole.id if pole else 0
    verif('… sans responsable en base', pole is not None and pole.responsable_id is None)
r = envoyer(admin, f'/admin/direction/nouvelle?pole_id={PID}&retour=/admin/directions',
            {'nom': 'Direction des crédits', 'pole_id': str(PID), 'type_responsable': 'utilisateur', 'responsable_id': '0'})
with A.app.app_context():
    d = M.Direction.query.filter_by(client_id=1, nom='Direction des crédits').first()
    DID = d.id if d else 0
    verif('direction sans responsable : créée dans son pôle, retour sur l’arborescence', r.status_code == 302 and d is not None
          and d.pole_id == PID and d.responsable_id is None, r.status_code)
r = envoyer(admin, f'/admin/service/nouveau/{DID}' + R, {'nom': 'Service recouvrement', 'direction_id': str(DID),
                                                         'type_responsable': 'utilisateur', 'responsable_id': '0'})
with A.app.app_context():
    s = M.Service.query.filter_by(client_id=1, nom='Service recouvrement').first()
    verif('service sans responsable : créé sous sa direction', r.status_code == 302 and s is not None and s.direction_id == DID, r.status_code)
r = envoyer(admin, '/admin/pole/nouveau' + R, {'nom': 'Pôle RH', 'ordre': '0', 'pays_id': '0', 'couleur': '#3b82f6',
                                               'type_responsable': 'utilisateur', 'responsable_id': str(ids['gestionnaire'])})
with A.app.app_context():
    verif('pôle avec responsable : toujours possible', (M.Pole.query.filter_by(client_id=1, nom='Pôle RH').first() or M.Pole()).responsable_id == ids['gestionnaire'])
r = appel(admin, 'get', '/admin/directions')
verif('arborescence : nouvelles entités affichées, « À pourvoir »', all(x in r.data.decode() for x in ('Pôle Finance', 'Direction des crédits', 'Service recouvrement', 'À pourvoir')))
r = envoyer(lect, '/admin/direction/nouvelle' + R, {'nom': 'Intrus', 'pole_id': '0'})
with A.app.app_context():
    verif('simple utilisateur : création refusée', M.Direction.query.filter_by(nom='Intrus').first() is None)
r = envoyer(admin, '/admin/direction/nouvelle' + R, {'nom': 'Redirection', 'pole_id': '0', 'responsable_id': '0'})
r2 = appel(admin, 'post', '/admin/direction/nouvelle?retour=https://exemple.com/', data={'nom': 'X'})
verif('retour limité aux pages de l’outil (pas de redirection vers un autre site)', 'exemple.com' not in (r2.headers.get('Location') or ''))
print(f'\n{sum(res)}/{len(res)} vérifications réussies')

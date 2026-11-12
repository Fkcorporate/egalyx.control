"""Recette : page de connexion aux couleurs du client (https://<client>.egalyx.com)."""
import socle
from socle import Muet, appel
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
from egalyx import gestion_clients
with A.app.app_context():
    ua = db.session.get(M.User, ids['gestionnaire']); ub = db.session.get(M.User, ids['admin_b'])
    ca = db.session.get(M.Client, ua.client_id); cb = db.session.get(M.Client, ub.client_id)
    ca.sous_domaine, cb.sous_domaine = 'banquea', 'banqueb'
    nom_a, nom_b, user_a, user_b, cid_a = ca.nom, cb.nom, ua.username, ub.username, ca.id
    db.session.commit()
gestion_clients.vider_cache_hotes()
HA, HB, HP = 'https://banquea.egalyx.com', 'https://banqueb.egalyx.com', 'https://www.egalyx.com'


def client(base):
    return A.app.test_client()


c = A.app.test_client()
r = c.get('/auth/login_fullscreen', base_url=HA); t = r.get_data(as_text=True)
verif('banquea.egalyx.com : page aux couleurs du client', r.status_code == 200 and nom_a in t and 'Propulsé par Egalyx' in t,
      f'{r.status_code} {socle.cause(A)}')
verif('… non indexée (balise + en-tête)', 'noindex' in t and 'noindex' in (r.headers.get('X-Robots-Tag') or ''))
verif('… rappel double authentification', 'FreeOTP' in t)
r = c.get('/auth/login_fullscreen', base_url=HP); t = r.get_data(as_text=True)
verif('www.egalyx.com : page Egalyx habituelle', r.status_code == 200 and 'Propulsé par Egalyx' not in t)

c = A.app.test_client()
r = c.post('/auth/login_fullscreen', base_url=HA, data={'username': user_b, 'password': socle.MDP})
t = r.get_data(as_text=True)
verif('Compte d\'un AUTRE client sur banquea : refusé, message identique à un mauvais mot de passe',
      r.status_code == 200 and 'mot de passe incorrect' in t and nom_b not in t, str(r.status_code))
with c.session_transaction(base_url=HA) as s:
    verif('… et pas de session ouverte', '_user_id' not in s)
c = A.app.test_client()
r = c.post('/auth/login_fullscreen', base_url=HA, data={'username': user_a, 'password': 'mauvais'})
verif('Mauvais mot de passe : même message, sur la page du client', 'mot de passe incorrect' in r.get_data(as_text=True)
      and 'Propulsé par Egalyx' in r.get_data(as_text=True))
c = A.app.test_client()
r = c.post('/auth/login_fullscreen', base_url=HA, data={'username': user_a, 'password': socle.MDP})
verif('Compte du client sur son adresse : connecté (redirection habituelle)', r.status_code in (302, 303), f'{r.status_code} {socle.cause(A)}')
c = A.app.test_client()
r = c.post('/auth/login_fullscreen', base_url=HB, data={'username': user_b, 'password': socle.MDP})
verif('Client B sur son adresse : connecté', r.status_code in (302, 303))
c = A.app.test_client()
r = c.post('/auth/login_fullscreen', base_url=HP, data={'username': user_b, 'password': socle.MDP})
verif('Adresse principale : connexion habituelle inchangée', r.status_code in (302, 303))

# réglages par l'administrateur du client
adm = socle.navigateur(A, ids['admin_a'])
r = appel(adm, 'get', '/organisation/page-connexion/')
verif('Admin client : page de réglage', r.status_code == 200 and 'Message d' in r.get_data(as_text=True), f'{r.status_code} {socle.cause(A)}')
r = appel(adm, 'post', '/organisation/page-connexion/', data={'message': 'Bienvenue sur l\'espace contrôle interne de la DR.',
                                                               'contact': 'risques@banquea.ci', 'couleur': '#0B5D3B'})
c = A.app.test_client()
t = c.get('/auth/login_fullscreen', base_url=HA).get_data(as_text=True)
verif('Message, contact et couleur affichés', 'espace contrôle interne de la DR' in t and 'risques@banquea.ci' in t and '#0B5D3B' in t)
t = c.get('/auth/login_fullscreen', base_url=HB).get_data(as_text=True)
verif('… pas chez l\'autre client', 'risques@banquea.ci' not in t and '#0B5D3B' not in t)
r = appel(adm, 'post', '/organisation/page-connexion/', data={'message': '<script>alert(1)</script>', 'contact': '', 'couleur': 'red;}'})
t = c.get('/auth/login_fullscreen', base_url=HA).get_data(as_text=True)
verif('Saisies protégées (pas de script, couleur invalide refusée)', '<script>alert(1)</script>' not in t and 'red;}' not in t)
r = appel(socle.navigateur(A, ids['gestionnaire']), 'get', '/organisation/page-connexion/')
verif('Utilisateur simple : réglage interdit', r.status_code == 403, str(r.status_code))
ap = A.app.test_client()
with A.app.app_context():
    nom_adm = db.session.get(M.User, ids['admin_a']).username
ap.post('/auth/login_fullscreen', base_url=HA, data={'username': nom_adm, 'password': socle.MDP})
r = ap.get('/auth/login_fullscreen?apercu=1', base_url=HA)
verif('Aperçu pour l\'admin connecté', r.status_code == 200 and 'Aperçu de votre page' in r.get_data(as_text=True))
c = A.app.test_client()
r = c.get('/auth/login_fullscreen?espace=banquea', base_url='http://127.0.0.1:5005')
verif('Essai en local : ?espace=<sous-domaine>', r.status_code == 200 and 'Propulsé par Egalyx' in r.get_data(as_text=True))
r = c.get('/auth/login_fullscreen?espace=', base_url='http://127.0.0.1:5005')
verif('… ?espace= vide : retour à la page Egalyx', 'Propulsé par Egalyx' not in r.get_data(as_text=True))
with A.app.app_context():
    db.session.get(M.Client, cid_a).is_active = False; db.session.commit()
c = A.app.test_client()
r = c.post('/auth/login_fullscreen', base_url=HA, data={'username': user_a, 'password': socle.MDP})
verif('Client suspendu : connexion impossible, message clair', r.status_code == 403 and 'indisponible' in r.get_data(as_text=True))
print(f'\n{sum(res)}/{len(res)} vérifications réussies')

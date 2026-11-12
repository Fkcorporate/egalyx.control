"""Recette : toutes les pages d'accès (templates/auth) s'affichent proprement, sur www et sur l'adresse d'un client."""
import re
import socle
from socle import Muet
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
from flask import render_template
from egalyx import gestion_clients
with A.app.app_context():
    ua = db.session.get(M.User, ids['gestionnaire'])
    ca = db.session.get(M.Client, ua.client_id)
    ca.sous_domaine = 'banquea'; db.session.commit()
    jeton = ua.generate_reset_token() if hasattr(ua, 'generate_reset_token') else None
    ref, nom_a, uid = ca.reference, ca.nom, ua.id
gestion_clients.vider_cache_hotes()
HA, HP = 'https://banquea.egalyx.com', 'https://www.egalyx.com'


def propre(t):
    return 'auth-page' in t and '{{' not in t and '{%' not in t


c = A.app.test_client()
for url, base, attendu in (('/auth/login_fullscreen', HP, ['name="remember_me"', 'name="username"', 'Mot de passe oublié']),
                           ('/auth/login_fullscreen', HA, [nom_a, 'name="remember_me"']),
                           ('/forgot-password', HP, ['name="email"', 'Retour à la connexion']),
                           ('/forgot-password', HA, [nom_a, 'name="email"']),
                           (f'/client-login/{ref}', HP, [nom_a, 'name="remember_me"'])):
    r = c.get(url, base_url=base); t = r.get_data(as_text=True)
    verif(f'{base.split("//")[1]}{url}', r.status_code == 200 and propre(t) and all(a in t for a in attendu),
          f'{r.status_code} {[a for a in attendu if a not in t]} {socle.cause(A)}')
if jeton:
    r = c.get(f'/reset-password/{jeton}', base_url=HP); t = r.get_data(as_text=True)
    verif('lien de réinitialisation', r.status_code == 200 and propre(t) and 'name="confirm_password"' in t and 'class="regles"' in t, f'{r.status_code}')
r = c.post('/forgot-password', base_url=HP, data={'email': 'inconnu@exemple.fr'}, follow_redirects=True)
verif('demande de lien : retour propre', r.status_code == 200 and propre(r.get_data(as_text=True)), str(r.status_code))
# « Rester connecté » : le champ remember_me pose désormais le cookie de session longue
c2 = A.app.test_client()
r = c2.get('/auth/login_fullscreen', base_url=HP)
tok = re.search(r'name="csrf_token" value="([^"]+)"', r.get_data(as_text=True))
with A.app.app_context():
    u = db.session.get(M.User, uid); nom = u.username
r = c2.post('/auth/login_fullscreen', base_url=HP, data={'csrf_token': tok.group(1) if tok else '', 'username': nom,
                                                          'password': socle.MDP, 'remember_me': 'y'})
cook = ' '.join(r.headers.getlist('Set-Cookie'))
verif('« Rester connecté » pose le cookie remember_token', 'remember_token' in cook, str(r.status_code))

with A.app.test_request_context('/', base_url=HP):
    with A.app.app_context():
        cl = db.session.get(M.Client, ca.id) if False else M.Client.query.filter_by(reference=ref).first()
        for gab, ctx in (('auth/email_sent.html', {'email': 'a@b.fr'}), ('auth/client_inactive.html', {'client': cl}),
                         ('auth/login.html', {}), ('auth/force_change_password.html', {}), ('auth/change_password.html', {})):
            try:
                t = render_template(gab, **ctx); verif(f'gabarit {gab}', propre(t))
            except Exception as e:
                verif(f'gabarit {gab}', False, repr(e)[:200])
print(f'\n{sum(res)}/{len(res)}')

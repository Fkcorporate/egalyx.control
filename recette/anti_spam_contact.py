"""Recette : anti-spam du formulaire de contact (/api/contact) — question, champ piège, délai, jeton unique, limite IP."""
import re, time
import socle
from socle import Muet
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
from egalyx import anti_spam_contact as AS
envois = []
A.email_service.send_contact_confirmation = lambda **k: envois.append(k) or True
c = A.app.test_client()
BASE = {'nom_complet': 'Awa Koné', 'email': 'awa@exemple.ci', 'societe': 'Banque Horizon', 'sujet': 'Démo', 'message': 'Bonjour, une démo SVP.'}

def defi():
    d = c.get('/api/contact/defi').get_json()
    q = d['question']; mots = q.split()
    a, op, b = AS.NOMBRES.index(mots[2]), mots[3], AS.NOMBRES.index(mots[4])
    return d, (a + b if op == 'plus' else a - b)

def poster(ip='10.0.0.1', **x):
    return c.post('/api/contact', data={**BASE, **x}, headers={'X-Forwarded-For': ip})

r = c.get('/api/contact/defi'); d = r.get_json()
verif('Question anti-spam disponible sans connexion', r.status_code == 200 and d['question'].startswith('Combien font') and d['jeton'], str(d))
verif('Question jamais mise en cache', r.headers.get('Cache-Control') == 'no-store')

r = poster(); verif('Sans réponse : refusé, rien envoyé', r.status_code == 400 and not envois, r.get_data(as_text=True)[:120])
d, rep = defi(); r = poster(defi_jeton=d['jeton'], defi_reponse=str(rep))
verif('Envoi instantané (< 3 s, robot) : refusé', r.status_code == 400 and 'trop rapide' in r.get_json()['message'] and not envois)
time.sleep(3.1)
r = poster(defi_jeton=d['jeton'], defi_reponse=str(rep + 1))
verif('Mauvaise réponse : refusée', r.status_code == 400 and 'incorrecte' in r.get_json()['message'] and not envois)
r = poster(defi_jeton=d['jeton'] + 'x', defi_reponse=str(rep))
verif('Jeton falsifié : refusé', r.status_code == 400 and not envois)
r = poster(defi_jeton=d['jeton'], defi_reponse=str(rep))
verif('Bonne réponse après quelques secondes : message envoyé', r.status_code == 200 and r.get_json().get('success') and len(envois) == 1,
      r.get_data(as_text=True)[:160])
r = poster(defi_jeton=d['jeton'], defi_reponse=str(rep))
verif('Même question réutilisée : refusée (usage unique)', r.status_code == 400 and 'déjà servi' in r.get_json()['message'] and len(envois) == 1)

d, rep = defi(); time.sleep(3.1)
r = poster(defi_jeton=d['jeton'], defi_reponse=str(rep), site_web='http://spam.example')
verif('Champ piège rempli (robot) : faux succès, RIEN envoyé', r.status_code == 200 and r.get_json().get('success') and len(envois) == 1)

AS._envois.clear()
ok = 0
for i in range(6):
    d, rep = defi()
    jetons = (d, rep)
    if i == 0: time.sleep(3.1)
    else:
        # jeton daté de plus de 3 s sans attendre : on recule l'horloge du module
        pass
    AS.DELAI_MIN = 0
    r = poster(ip='10.9.9.9', defi_jeton=d['jeton'], defi_reponse=str(rep))
    ok += r.status_code == 200
AS.DELAI_MIN = 3
verif('Limite : 5 messages par heure et par adresse IP (6e refusé)', ok == 5 and r.status_code == 429, f'{ok} acceptés, dernier {r.status_code}')
d, rep = defi(); AS.DELAI_MIN = 0
r = poster(ip='10.1.2.3', defi_jeton=d['jeton'], defi_reponse=str(rep)); AS.DELAI_MIN = 3
verif('… une autre adresse IP n\'est pas bloquée', r.status_code == 200)

import os
os.environ['EGALYX_ANTI_SPAM_CONTACT'] = '0'
r = c.get('/api/contact/defi'); r2 = poster(ip='10.5.5.5')
verif('Coupure d\'urgence EGALYX_ANTI_SPAM_CONTACT=0 : formulaire sans question', r.get_json()['question'] is None and r2.status_code == 200)
os.environ.pop('EGALYX_ANTI_SPAM_CONTACT')
print(f'\n{sum(res)}/{len(res)} vérifications réussies')

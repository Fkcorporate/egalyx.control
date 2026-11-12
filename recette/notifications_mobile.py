"""Mes notifications (application / e-mail immédiat / résumé quotidien, règles imposées par l'organisation),
application installable (manifeste, icônes, service worker, hors ligne), « À traiter » sur le tableau de bord,
indicateurs de la liste des clients."""
import datetime as dt
import io
import json
import sys
import time

import socle
import objets
from socle import Muet, appel, creer

with Muet():
    A, ids = socle.preparer()
    O = objets.peupler_objets(A, ids)
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore')


from egalyx import courriel
envoyes = []
courriel.est_configure = lambda: True
courriel.envoyer = lambda dest, sujet, texte, **k: envoyes.append((dest[0], sujet, texte)) or True

with A.app.app_context():
    mail_g = db.session.get(M.User, ids['gestionnaire']).email


def notifier(uid, type_, titre, **k):
    with A.app.app_context():
        db.session.add(M.Notification(destinataire_id=uid, type_notification=type_, titre=titre, message=titre + ' (détail)',
                                      client_id=1, **k))
        db.session.commit()
    time.sleep(0.4)


print('--- Mes notifications')
r, t = go('gestionnaire', 'get', '/notifications/preferences')
verif('Page « Mes notifications » (ancienne adresse conservée)', r.status_code == 200 and 'E-mail immédiat' in t
      and 'Résumé quotidien' in t and mail_g in t, f'{r.status_code} {socle.cause(A)}')
verif('Utilisateur simple : pas de section « Pour toute l\'organisation »', 'Pour toute l' not in t)
notifier(ids['gestionnaire'], 'evaluation_a_valider', 'Évaluation à valider : R-001')
verif('Par défaut : aucun e-mail (application seulement)', not envoyes, str(envoyes))
go('gestionnaire', 'post', '/notifications/preferences', data={'email_a_valider': '1', 'resume_echeance': '1',
                                                               'resume_a_valider': '1', 'heure_resume': '8'})
with A.app.app_context():
    from egalyx.notifications_prefs import reglages
    rg = reglages(db.session.get(M.User, ids['gestionnaire']))
verif('Préférences enregistrées', rg['evenements']['a_valider']['email'] and rg['evenements']['echeance']['resume']
      and rg['heure_resume'] == 8, str(rg['evenements']['a_valider']))
envoyes.clear()
notifier(ids['gestionnaire'], 'evaluation_a_valider', 'Évaluation à valider : R-002')
verif('E-mail immédiat choisi : envoyé, avec le nom de l\'organisation et un lien', len(envoyes) == 1 and envoyes[0][0] == mail_g
      and envoyes[0][1].startswith('[') and '/notifications/notification/' in envoyes[0][2], str(envoyes))
envoyes.clear()
notifier(ids['gestionnaire'], 'kri_alerte', 'KRI en alerte')
verif('Type non coché : pas d\'e-mail', not envoyes, str(envoyes))
envoyes.clear()
notifier(ids['gestionnaire'], 'incident', 'Délai dépassé : INC-9', entite_type='incident', entite_id=999)
verif('Alerte de délai d\'incident : pas de doublon (réglée par l\'organisation)', not envoyes, str(envoyes))

r, t = go('admin_a', 'get', '/notifications/preferences')
verif('Admin du client : section « Pour toute l\'organisation »', 'Pour toute l' in t)
go('admin_a', 'post', '/notifications/preferences', data={'action': 'organisation', 'imp_email_signalement': '1'})
r, t = go('lecteur', 'get', '/notifications/preferences')
verif('Règle imposée : verrouillée chez chacun', 'Imposé par votre organisation' in t, '')
envoyes.clear()
with A.app.app_context():
    mail_l = db.session.get(M.User, ids['lecteur']).email
notifier(ids['lecteur'], 'signalement', 'Nouveau signalement')
verif('E-mail imposé : envoyé même sans choix personnel', any(e[0] == mail_l for e in envoyes), str(envoyes))
r, _ = go('lecteur', 'post', '/notifications/preferences', data={'action': 'organisation', 'imp_email_kri': '1'})
verif('Utilisateur simple : ne peut pas imposer', r.status_code == 403, str(r.status_code))
with A.app.app_context():
    from egalyx.notifications_prefs import imposes
    verif('… et rien n\'a changé', 'kri' not in imposes(1))
r, _ = go('admin_b', 'get', '/notifications/preferences')
with A.app.app_context():
    verif('Autre organisation : règles de A non appliquées', not imposes(2))

print('--- Résumé quotidien')
with A.app.app_context():
    pa = creer(M.PlanAction, reference='PA-RES-1', nom='Plan en retard pour le résumé', client_id=1, created_by=ids['admin_a'],
               statut='en_cours', responsable_id=ids['gestionnaire'], date_fin_prevue=dt.date.today() - dt.timedelta(days=2))
    db.session.commit()
notifier(ids['gestionnaire'], 'echeance_proche', 'Échéance proche : plan PA-77')
envoyes.clear()
with A.app.test_request_context():
    from egalyx.notifications_prefs import envoyer_resumes
    n1 = envoyer_resumes(forcer=True)
time.sleep(0.5)
resume = [e for e in envoyes if e[0] == mail_g]
verif('Résumé envoyé : « Ma semaine » et nouvelles notifications', n1 >= 1 and resume and 'Ma semaine' in resume[0][2]
      and 'Échéance proche : plan PA-77' in resume[0][2], str(resume)[:300])
verif('Notification d\'un type non retenu absente du résumé', resume and 'KRI en alerte' not in resume[0][2])
envoyes.clear()
with A.app.test_request_context():
    n2 = envoyer_resumes()
verif('Un seul résumé par jour', not [e for e in envoyes if e[0] == mail_g], str(n2))

print('--- Application installable')
anon = A.app.test_client()
r = anon.get('/manifest.webmanifest')
m = json.loads(r.data) if r.status_code == 200 else {}
verif('Manifeste public (nom, plein écran, départ « Ma semaine », icônes)', m.get('display') == 'standalone'
      and m.get('start_url', '').startswith('/ma-semaine') and len(m.get('icons', [])) == 2, f'{r.status_code} {str(m)[:120]}')
from PIL import Image
for taille in (192, 512):
    r = anon.get(f'/application/icone-{taille}.png')
    img = Image.open(io.BytesIO(r.data)) if r.status_code == 200 else None
    verif(f'Icône {taille} × {taille}', img is not None and img.size == (taille, taille), str(r.status_code))
r = anon.get('/sw.js')
verif('Service worker servi à la racine, sans mise en cache des pages de données', r.status_code == 200
      and b"mode !== 'navigate'" in r.data and b'onLine === false' in r.data and 'javascript' in r.content_type, str(r.status_code))
r = anon.get('/hors-ligne')
verif('Page hors ligne publique', r.status_code == 200 and 'Pas de connexion'.encode() in r.data, str(r.status_code))
r, t = go('gestionnaire', 'get', '/dashboard')
verif('Pages : manifeste, icône iPhone, bouton « Installer l\'application »', 'href="/manifest.webmanifest"' in t
      and '/application/icone-180.png' in t and 'btnInstallerApp' in t)
verif('« Installer l\'application » toujours visible dans le menu, avec la page d\'aide en secours',
      '<li id="liInstallerApp">' in t and 'data-aide="/aide/fiche/application_telephone"' in t)
r2, t2 = go('lecteur', 'get', '/aide/fiche/application_telephone')
verif('Page d\'aide « Installer Egalyx sur mon téléphone » (iPhone, Android, ordinateur, Mac)', r2.status_code == 200
      and 'Sur l’écran d’accueil' in t2 and 'Ajouter au Dock' in t2, str(r2.status_code))

print('--- Tableau de bord : plus de bloc « À traiter » (retiré à la demande)')
verif('Tableau de bord sans « À traiter »', r.status_code == 200 and 'id="aTraiter"' not in t, f'{r.status_code} {socle.cause(A)}')

print('--- Liste des clients (super admin)')
r, t = go('superadmin', 'get', '/super-admin/clients')
verif('Liste des clients : utilisateurs réels, double authentification, mise en route', r.status_code == 200
      and 'double auth.' in t and 'Mise en route' in t, f'{r.status_code} {socle.cause(A)}')
verif('Client sans connexion récente signalé « À surveiller »', 'À surveiller' in t)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)

"""Recette : deux interfaces (actuelle / harmonisée), réglées par le super admin pour chaque organisation."""
import os
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import sys
import socle
from socle import Muet, navigateur
res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with Muet():
    A, ids = socle.preparer()
import models as M
app = A.app
with app.app_context():
    cid_a = A.db.session.get(M.User, ids['admin_a']).client_id
    cid_b = A.db.session.get(M.User, ids['admin_b']).client_id


def regler(cid, valeur):
    with app.app_context():
        conf = M.ClientConfiguration.query.filter_by(client_id=cid).first()
        if conf is None:
            conf = M.ClientConfiguration(client_id=cid, couleurs={}, preferences={}); A.db.session.add(conf)
        p = dict(conf.preferences or {})
        if valeur:
            p['apparence'] = valeur
        else:
            p.pop('apparence', None)
        conf.preferences = p; A.db.session.commit()


def harmonisee(c, url='/dashboard'):
    with Muet():
        h = c.get(url, follow_redirects=True).get_data(as_text=True)
    return 'egalyx-harmonise.css' in h and "classList.add('ui-h')" in h


print('--- Réglage par organisation')
regler(cid_a, None); regler(cid_b, None)
ca, cb = navigateur(A, ids['admin_a']), navigateur(A, ids['admin_b'])
verif('par défaut : interface actuelle (rien de chargé)', not harmonisee(ca))
regler(cid_a, 'harmonisee')
verif('organisation A en harmonisée : feuille de style et script chargés', harmonisee(ca))
verif('organisation B non touchée', not harmonisee(cb))
regler(cid_a, 'nouvelle')
verif('ancien réglage « nouvelle » = interface harmonisée', harmonisee(ca))
regler(cid_a, 'classique')
verif('« classique » = interface actuelle', not harmonisee(ca))

print('--- Toutes les familles de pages')
regler(cid_a, 'harmonisee')
co = navigateur(A, ids['operateur'])
verif('espace opérateur (gabarit à part) : harmonisé', harmonisee(co, '/operateur/dashboard'))
verif('page Support (gabarit à part) : harmonisée', harmonisee(ca, '/support'))
verif('centre d’aide : harmonisé', harmonisee(ca, '/aide/'))

print('--- Page de réglage et aperçu (super admin seulement)')
cs = navigateur(A, ids['superadmin'])
with Muet():
    r = cs.get('/compte/apparence/')
h = r.get_data(as_text=True)
verif('super admin : page « Interface des clients »', r.status_code == 200 and 'Interface harmonisée' in h and 'Interface actuelle' in h)
verif('… avec « Comparer les deux versions »', 'Comparer les deux versions' in h)
with Muet():
    r1 = ca.get('/compte/apparence/'); r2 = ca.post('/compte/apparence/apercu/harmonisee')
verif('administrateur client : ni la page ni l’aperçu', r1.status_code == 404 and r2.status_code == 404, (r1.status_code, r2.status_code))
with Muet():
    cs.post('/compte/apparence/apercu/harmonisee')
verif('aperçu du super admin : il voit l’interface harmonisée', harmonisee(cs, '/super-admin/dashboard'))
regler(cid_a, 'classique')
verif('… sans changer celle des clients', not harmonisee(ca))
with Muet():
    cs.post('/compte/apparence/apercu/aucun')
verif('aperçu arrêté', not harmonisee(cs, '/super-admin/dashboard'))
with Muet():
    r = cs.post('/compte/apparence/apercu/harmonisee', data={'suivant': '//pirate.example/'})
verif('aperçu : pas de redirection vers un autre site', 'pirate.example' not in (r.headers.get('Location') or ''), r.headers.get('Location'))
with Muet():
    r = cs.post('/compte/apparence/', data={'client_id': cid_b, 'apparence': 'harmonisee'})
regler_b = None
with app.app_context():
    regler_b = (M.ClientConfiguration.query.filter_by(client_id=cid_b).first().preferences or {}).get('apparence')
verif('super admin enregistre « harmonisée » pour B', regler_b == 'harmonisee', regler_b)

print('--- Images du guide selon l’interface')
import egalyx
dossier = os.path.join(app.static_folder, 'aide', 'guide')
images = [f for f in os.listdir(dossier) if f.endswith('.webp')]
variantes = os.path.join(dossier, 'harmonisee')
verif('captures de l’interface harmonisée présentes', os.path.isdir(variantes) and len(os.listdir(variantes)) >= 80,
      len(os.listdir(variantes)) if os.path.isdir(variantes) else 0)
regler(cid_a, 'harmonisee')
with Muet():
    h = ca.get('/aide/fiche/guide-plans-action').get_data(as_text=True)
verif('organisation harmonisée : le guide montre les captures harmonisées', 'aide/guide/harmonisee/plans_audit.webp' in h)
regler(cid_a, 'classique')
with Muet():
    h = ca.get('/aide/fiche/guide-plans-action').get_data(as_text=True)
verif('organisation en interface actuelle : captures actuelles', 'aide/guide/plans_audit.webp' in h and 'harmonisee/plans_audit' not in h)
for f in ('css/egalyx-harmonise.css', 'js/egalyx-harmonise.js'):
    verif(f'fichier {f} présent', os.path.exists(os.path.join(app.static_folder, f)))

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)

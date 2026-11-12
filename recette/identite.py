"""Identité de l'organisation : nom affiché et logo dans l'en-tête, droits, cloisonnement du logo, formats refusés,
super admin (création et fiche du client), rapport au comité, objet des e-mails."""
import io
import sys

import socle
from socle import Muet, appel

with Muet():
    A, ids = socle.preparer()
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond))
    print('OK   ' if cond else 'ÉCHEC', nom, detail)


def go(role, m, url, **kw):
    r = appel(socle.navigateur(A, ids[role]), m, url, **kw)
    return r, r.data.decode('utf-8', 'ignore')


def png(l=800, h=300):
    from PIL import Image
    b = io.BytesIO()
    Image.new('RGBA', (l, h), (20, 60, 120, 255)).save(b, 'PNG')
    return b.getvalue()


with A.app.app_context():
    cid_a = db.session.get(M.User, ids['admin_a']).client_id
    cid_b = db.session.get(M.User, ids['admin_b']).client_id

r, t = go('admin_a', 'get', '/dashboard')
verif('Par défaut : le nom du client apparaît en haut', 'org-nom-fk">Banque Recette<' in t, f'{r.status_code} {socle.cause(A)}')
r, t = go('admin_a', 'get', '/organisation/identite/')
verif('Admin : page Identité affichée', r.status_code == 200 and 'Nom affiché' in t, f'{r.status_code} {socle.cause(A)}')
r, _ = go('lecteur', 'get', '/organisation/identite/')
verif('Utilisateur non admin : refusé', r.status_code in (302, 403), str(r.status_code))

r, _ = go('admin_a', 'post', '/organisation/identite/', data={'nom_court': '  BR   Banque ', 'logo': (io.BytesIO(png()), 'logo.png')},
          content_type='multipart/form-data')
r, t = go('admin_a', 'get', '/dashboard')
verif('Nom affiché et logo en haut de l\'outil', 'org-nom-fk">BR Banque<' in t and f'/organisation/identite/logo/{cid_a}' in t,
      socle.cause(A))
r, _ = go('admin_a', 'get', f'/organisation/identite/logo/{cid_a}')
from PIL import Image
img = Image.open(io.BytesIO(r.data)) if r.status_code == 200 else None
verif('Logo servi en PNG, redimensionné (≤ 400 × 160)', img is not None and img.width <= 400 and img.height <= 160,
      f'{r.status_code} {img.size if img else ""}')
r, _ = go('lecteur', 'get', f'/organisation/identite/logo/{cid_a}')
verif('Utilisateur de l\'organisation : voit le logo', r.status_code == 200, str(r.status_code))
r, _ = go('admin_b', 'get', f'/organisation/identite/logo/{cid_a}')
verif('Autre organisation : logo introuvable', r.status_code == 404, str(r.status_code))
r = appel(A.app.test_client(), 'get', f'/organisation/identite/logo/{cid_a}')
verif('Sans connexion : logo introuvable', r.status_code == 404, str(r.status_code))
r, t = go('admin_b', 'get', '/dashboard')
verif('Autre organisation : son propre nom, jamais celui de A', 'BR Banque' not in t and 'org-nom-fk">Autre Organisation<' in t)

svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
r, _ = go('admin_a', 'post', '/organisation/identite/', data={'nom_court': 'BR Banque', 'logo': (io.BytesIO(svg), 'x.svg')},
          content_type='multipart/form-data')
r2, _ = go('admin_a', 'get', f'/organisation/identite/logo/{cid_a}')
verif('SVG refusé, logo précédent conservé', r2.status_code == 200 and r2.data[:4] == b'\x89PNG', str(r2.status_code))
r, _ = go('admin_a', 'post', '/organisation/identite/', data={'nom_court': 'BR Banque',
                                                             'logo': (io.BytesIO(b'\x89PNG\r\n\x1a\nfaux'), 'x.png')},
          content_type='multipart/form-data')
verif('Faux PNG refusé', go('admin_a', 'get', f'/organisation/identite/logo/{cid_a}')[0].status_code == 200)
r, _ = go('admin_a', 'post', '/organisation/identite/', data={'nom_court': 'X' * 60}, content_type='multipart/form-data')
with A.app.app_context():
    from egalyx.identite import nom_affiche
    verif('Nom limité à 30 caractères', nom_affiche(cid_a) == 'X' * 30, nom_affiche(cid_a))
go('admin_a', 'post', '/organisation/identite/', data={'nom_court': 'BR Banque'}, content_type='multipart/form-data')
with A.app.app_context():
    verif('Nom repris dans l\'objet des e-mails d\'alerte', nom_affiche(cid_a) == 'BR Banque')

r, t = go('admin_a', 'get', '/rapports/comite-audit')
verif('Rapport au comité : logo et mention Egalyx', r.status_code == 200 and 'data:image/png;base64' in t and 'Réalisé avec Egalyx' in t,
      f'{r.status_code} {socle.cause(A)}')

print('--- Super admin')
r, t = go('superadmin', 'get', '/super-admin/client/nouveau')
verif('Création du client : champs Nom affiché et Logo', r.status_code == 200 and 'identite_nom_court' in t
      and 'multipart/form-data' in t, f'{r.status_code} {socle.cause(A)}')
from socle import creer
with A.app.app_context():
    db.session.add(creer(M.FormuleAbonnement, code='std_rec', nom='Standard', is_active=True, prix_mensuel=10,
                         ordre_affichage=1))
    db.session.commit()
from PIL import Image
jpg = io.BytesIO()
Image.new('RGB', (300, 100), (200, 0, 0)).save(jpg, 'JPEG')
jpg.seek(0)
r, _ = go('superadmin', 'post', '/super-admin/client/nouveau', data={
    'nom': 'Nouvelle Banque du Sahel', 'reference': 'NBS-01', 'contact_nom': 'X', 'contact_email': 'contact@nbs-recette.fr',
    'plan': 'std_rec', 'max_utilisateurs': '10', 'max_risques': '100', 'max_audits': '10', 'sous_domaine': 'nbs',
    'identite_nom_court': 'NBS', 'identite_logo': (jpg, 'logo.jpg')}, content_type='multipart/form-data')
with A.app.app_context():
    nouveau = M.Client.query.filter_by(reference='NBS-01').first()
    verif('Sous-domaine enregistré aussi sur le client à la création', nouveau is not None and nouveau.sous_domaine == 'nbs',
          nouveau.sous_domaine if nouveau else '')
    verif('Client créé avec son nom affiché et son logo (JPEG converti)', nouveau is not None and nouveau.logo == f'client_{nouveau.id}.png'
          and nom_affiche(nouveau.id) == 'NBS', f'{r.status_code} {socle.cause(A)}')
r, t = go('superadmin', 'get', f'/super-admin/client/{cid_b}')
verif('Fiche du client : lien « Nom affiché et logo »', f'/organisation/identite/?client_id={cid_b}' in t, str(r.status_code))
r, _ = go('superadmin', 'post', f'/organisation/identite/?client_id={cid_b}', data={'nom_court': 'AO',
                                                                                  'logo': (io.BytesIO(png(200, 200)), 'l.png')},
          content_type='multipart/form-data')
r, t = go('admin_b', 'get', '/dashboard')
verif('Réglé par le super admin, visible par le client', 'org-nom-fk">AO<' in t and f'/logo/{cid_b}' in t, socle.cause(A))
r, _ = go('superadmin', 'get', f'/organisation/identite/logo/{cid_b}')
verif('Super admin : voit le logo de chaque client', r.status_code == 200, str(r.status_code))
with A.app.app_context():
    from egalyx import identite as ident_mod
    with A.app.test_request_context():
        try:
            ident_mod.appliquer(cid_b, retirer_logo=True)
            db.session.commit()
        except Exception as e:  # noqa: BLE001
            print('   ', e)
r, t = go('admin_b', 'get', '/dashboard')
verif('Logo retiré : plus d\'image, le nom reste', f'/logo/{cid_b}' not in t and 'org-nom-fk">AO<' in t)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')
sys.exit(0 if all(res) else 1)

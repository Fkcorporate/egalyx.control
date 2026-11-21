"""Recette : présentation des rapports aux couleurs de chaque organisation (Identité de l'organisation)."""
import io
import os
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
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

with app.app_context():
    kri_a = socle.creer(M.KRI, nom='Taux de virements rejetés', client_id=cid_a).id
    kri_b = socle.creer(M.KRI, nom='Indicateur B', client_id=cid_b).id
    A.db.session.commit()
admin = navigateur(A, ids['admin_a'])
admin_b = navigateur(A, ids['admin_b'])
lecteur = navigateur(A, ids['lecteur'])
RAPPORTS = {'rapport au comité': '/rapports/comite-audit', 'rapport KRI': f'/kri/{kri_a}/rapport-pdf?html=1'}
with app.test_request_context():
    from flask import url_for
    RAPPORTS['rapport KRI'] = url_for('telecharger_rapport_kri_pdf', kri_id=kri_a, html=1)
    URL_KRI_B = url_for('telecharger_rapport_kri_pdf', kri_id=kri_b, html=1)


def page(c, url):
    r = socle.appel(c, 'get', url)
    return r.status_code, r.data.decode('utf-8', 'replace')


def jeton(c):
    _, h = page(c, '/organisation/identite/')
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', h)
    return m.group(1) if m else ''


def regler(c, **champs):
    donnees = {'csrf_token': jeton(c), 'nom_court': '', 'rapports': '1', 'rp_logo': '1'}
    donnees.update(champs)
    return socle.appel(c, 'post', '/organisation/identite/', data=donnees, content_type='multipart/form-data')


print('--- Sans réglage : rapports inchangés')
avant = {}
for nom, url in RAPPORTS.items():
    st, h = page(admin, url)
    avant[nom] = h
    verif(f'{nom} : s\'affiche', st == 200, st)
    verif(f'{nom} : pas de bandeau ni de mention', 'rp-marque' not in h and 'Confidentiel — usage interne' not in h)

print('--- Page de réglage')
st, h = page(admin, '/organisation/identite/')
verif('administrateur : section « Présentation des rapports »', st == 200 and 'Présentation des rapports' in h and 'rp_couleur' in h)
st, _ = page(lecteur, '/organisation/identite/')
verif('simple utilisateur : pas d\'accès au réglage', st == 403, st)

print('--- Contrôles')
r = regler(admin, rp_couleur_active='1', rp_couleur='vert', rp_mention='', rp_pied='')
with app.app_context():
    from egalyx import identite
    verif('couleur invalide refusée', identite.reglages_rapports(cid_a)['couleur'] is None)
r = regler(admin, rp_couleur_active='1', rp_couleur='#F5E9A0', rp_mention='', rp_pied='')
with app.app_context():
    verif('couleur trop claire refusée (illisible sur blanc)', identite.reglages_rapports(cid_a)['couleur'] is None)

print('--- Réglage complet')
PIED = 'Banque Recette S.A. — Direction de l\'audit interne\nAbidjan "Plateau"'
r = regler(admin, rp_couleur_active='1', rp_couleur='#0e6b4f', rp_mention='Confidentiel — usage interne', rp_pied=PIED)
verif('enregistrement', r.status_code in (302, 303), r.status_code)
with app.app_context():
    rg = identite.reglages_rapports(cid_a)
    verif('couleur enregistrée', rg['couleur'] == '#0E6B4F', rg['couleur'])
    verif('mention et pied enregistrés', rg['mention'] == 'Confidentiel — usage interne' and 'Abidjan' in rg['pied'], rg)
    j = M.JournalActiviteClient.query.filter_by(action='identite_organisation').count()
    verif('réglage journalisé', j >= 1, j)

for nom, url in RAPPORTS.items():
    st, h = page(admin, url)
    verif(f'{nom} : couleur du client', '#0E6B4F' in h, st)
    verif(f'{nom} : mention de confidentialité', 'Confidentiel — usage interne' in h)
    verif(f'{nom} : pied de page', 'Direction de l' in h and 'Abidjan' in h)
st, h = page(admin, RAPPORTS['rapport KRI'])
verif('pied de page sûr dans le CSS (guillemets échappés)', 'Abidjan \\"Plateau\\"' in h)

print('--- Injection')
regler(admin, rp_couleur_active='0', rp_mention='</style><script>alert(1)</script>', rp_pied='"; } body { display:none } @x { content: "')
for nom, url in RAPPORTS.items():
    st, h = page(admin, url)
    verif(f'{nom} : aucun script ni CSS injecté', '<script>alert(1)' not in h and '"; } body' not in h.replace('\\"', 'X'), st)

print('--- Logo')
from PIL import Image
im = Image.new('RGB', (200, 80), (14, 107, 79)); b = io.BytesIO(); im.save(b, 'PNG')
with app.app_context():
    identite.appliquer(cid_a, logo=b.getvalue()); A.db.session.commit()
regler(admin, rp_couleur_active='0', rp_mention='', rp_pied='')
st, h = page(admin, RAPPORTS['rapport KRI'])
verif('logo affiché par défaut', 'data:image/png;base64,' in h and 'rp-marque' in h)
regler(admin, rp_couleur_active='0', rp_mention='', rp_pied='', rp_logo='0')
st, h = page(admin, RAPPORTS['rapport KRI'])
verif('logo masqué si décoché', 'data:image/png;base64,' not in h)

print('--- Cloisonnement')
regler(admin, rp_couleur_active='1', rp_couleur='#0E6B4F', rp_mention='Diffusion restreinte A', rp_pied='Pied A')
st, h = page(admin_b, URL_KRI_B)
verif('autre organisation : ne voit pas la présentation de A', 'Diffusion restreinte A' not in h and '#0E6B4F' not in h and 'Pied A' not in h, st)

print('--- Retour à l\'origine')
regler(admin, rp_couleur_active='0', rp_mention='', rp_pied='', rp_logo='0')
for nom, url in RAPPORTS.items():
    st, h = page(admin, url)
    verif(f'{nom} : de nouveau sans bandeau ni couleur', 'rp-marque' not in h and '#0E6B4F' not in h)

print('--- Rapports branchés')
GABARITS = ['audit/rapport_pdf.html', 'audit/rapport_complet.html', 'egalyx/rapport_comite.html', 'rapports/cartographie_pdf.html',
            'kri/rapport_pdf.html', 'incidents/export_pdf.html', 'c2n/plan_action_export_pdf.html', 'rapport_dispositifs.html',
            'logigramme/export_logigramme_pdf.html', 'admin/organigramme_pdf.html', 'audit/feuille_travail_pdf.html',
            'qualite/audits/rapport.html']
manque = [g for g in GABARITS if 'presentation_rapport()' not in open(os.path.join(app.template_folder, g), encoding='utf-8').read()]
verif(f'{len(GABARITS)} rapports suivent la présentation du client', not manque, manque)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')

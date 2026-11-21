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

print('--- Contenu des rapports (niveau 2)')
from werkzeug.datastructures import MultiDict
st, h = page(admin, '/organisation/rapports/audit')
verif('page « Contenu des rapports » : administrateur', st == 200 and 'Sections affichées' in h and 'Signataires' in h, st)
st, _ = page(lecteur, '/organisation/rapports/comite')
verif('page « Contenu des rapports » : refusée au simple utilisateur', st == 403, st)
st, _ = page(admin, '/organisation/rapports/inconnu')
verif('rapport inconnu : 404', st == 404, st)
st, h = page(admin, '/organisation/identite/')
verif('lien depuis Identité de l\'organisation', '/organisation/rapports/' in h)

def regler_contenu(c, rapport, champs):
    donnees = MultiDict([('csrf_token', jeton(c))] + champs)
    return socle.appel(c, 'post', f'/organisation/rapports/{rapport}', data=donnees)

r = regler_contenu(admin, 'comite', [('titre', 'Rapport trimestriel au comité des risques'),
    ('sections', 'chiffres'), ('sections', 'audit'),
    ('introduction', 'Situation de {organisation} au {date}. {inconnu} reste tel quel.'),
    ('conclusion', 'Le comité est invité à prendre acte.'),
    ('sig_regles', '1'), ('sig_fonction', 'Président du comité'), ('sig_nom', ''), ('sig_fonction', 'Directeur de l\'audit interne'), ('sig_nom', 'Awa Koné')])
verif('contenu du rapport au comité enregistré', r.status_code in (302, 303), r.status_code)
st, h = page(admin, RAPPORTS['rapport au comité'])
verif('comité : titre choisi', 'Rapport trimestriel au comité des risques' in h and '<h1 style="margin-top: 1rem;">Rapport au comité' not in h)
verif('comité : synthèse toujours affichée (obligatoire)', 'Synthèse</h2>' in h)
verif('comité : sections masquées absentes', 'Profil de risque' not in h and 'Méthode</h2>' not in h and 'Conformité</h2>' not in h)
verif('comité : numérotation recalculée', '<span class="num">1.</span>Introduction' in h and '<span class="num">2.</span>Synthèse' in h
      and '<span class="num">3.</span>Chiffres clés' in h and '<span class="num">4.</span>Audit interne' in h and '<span class="num">5.</span>Conclusion' in h)
verif('introduction : champs remplis, champ inconnu laissé tel quel', 'Situation de Banque' in h and '{organisation}' not in h and '{inconnu} reste tel quel' in h)
verif('comité : signataires', 'Président du comité' in h and 'Awa Koné' in h and 'class="ct-signature"' in h)
st, h2 = page(admin_b, RAPPORTS['rapport au comité'])
verif('autre organisation : contenu d\'origine', 'Rapport trimestriel' not in h2 and 'Profil de risque' in h2 and 'class="ct-signature"' not in h2)

r = regler_contenu(admin, 'comite', [('sig_regles', '1'), ('sig_fonction', ''), ('sig_nom', 'Sans fonction')])
with app.app_context():
    from egalyx import rapport_contenu
    verif('signataire sans fonction refusé', rapport_contenu.reglages(cid_a, 'comite')['titre'] == 'Rapport trimestriel au comité des risques')
r = regler_contenu(admin, 'comite', [('introduction', 'x' * 1600)])
with app.app_context():
    verif('texte trop long refusé', len(rapport_contenu.reglages(cid_a, 'comite')['introduction']) < 1600)
regler_contenu(admin, 'comite', [('introduction', '<script>alert(2)</script>'), ('sections', 'chiffres')])
st, h = page(admin, RAPPORTS['rapport au comité'])
verif('texte type : HTML échappé', '<script>alert(2)' not in h and '&lt;script&gt;alert(2)' in h)
with app.app_context():
    n = M.JournalActiviteClient.query.filter_by(action='contenu_rapport').count()
verif('réglages du contenu journalisés', n >= 2, n)

with app.app_context():
    ct = rapport_contenu.Contenu('audit', {'titre': '', 'masquees': ['tests', 'sommaire'], 'introduction': 'Intro {reference}',
                                           'conclusion': 'Fin', 'signataires': [], 'signataires_regles': False},
                                 {'reference': 'AUD-1', 'organisation': 'X', 'date': '01/01/2026', 'mission': 'M'})
    verif('rapport d\'audit : numérotation (intro, résumé, constatations…, conclusion avant validation)',
          [ct.numero(k) for k in ('introduction', 'resume', 'tests', 'constatations', 'conclusion', 'validation')] == [1, 2, '', 3, 6, 7]
          and ct.introduction == 'Intro AUD-1' and not ct.montre('sommaire'), ct.sommaire())
    verif("rapport d'audit : titre d'origine sans réglage", ct.titre == "Rapport d'Audit")
r = regler_contenu(admin, 'comite', [('action', 'reinitialiser')])
st, h = page(admin, RAPPORTS['rapport au comité'])
verif('« Rétablir le contenu d\'origine »', 'Rapport trimestriel' not in h and 'Profil de risque' in h and 'class="ct-signature"' not in h)
GABARITS_CONTENU = ['audit/rapport_pdf.html', 'egalyx/rapport_comite.html']
verif('rapport d\'audit et rapport au comité suivent le contenu choisi',
      all("contenu_rapport('" in open(os.path.join(app.template_folder, g), encoding='utf-8').read() for g in GABARITS_CONTENU))

print('--- Exports PDF sans WeasyPrint')
for u in ('/incidents/export/pdf', '/dispositifs/rapport'):
    r = socle.appel(admin, 'get', u)
    with admin.session_transaction() as ss:
        fl = ss.get('_flashes') or []
    verif(f'{u} : version imprimable (et plus de message d\'erreur)', r.status_code == 200 and b'eg-pdf-secours' in r.data
          and not any('WeasyPrint' in m for _, m in fl), r.status_code)

print('--- Rapports branchés')
GABARITS = ['audit/rapport_pdf.html', 'audit/rapport_complet.html', 'egalyx/rapport_comite.html', 'rapports/cartographie_pdf.html',
            'kri/rapport_pdf.html', 'incidents/export_pdf.html', 'c2n/plan_action_export_pdf.html', 'rapport_dispositifs.html',
            'logigramme/export_logigramme_pdf.html', 'admin/organigramme_pdf.html', 'audit/feuille_travail_pdf.html',
            'qualite/audits/rapport.html']
manque = [g for g in GABARITS if 'presentation_rapport()' not in open(os.path.join(app.template_folder, g), encoding='utf-8').read()]
verif(f'{len(GABARITS)} rapports suivent la présentation du client', not manque, manque)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')

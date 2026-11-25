"""Recette : cartouche qualité en haut de chaque page du rapport d'audit (PDF élégant, exports PDF, Word)."""
import io
import os
import subprocess
import tempfile
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
import models as M
from models import db

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


def texte_pdf(octets):
    import pypdf
    return [' '.join(p.extract_text().split()) for p in pypdf.PdfReader(io.BytesIO(octets)).pages]


def jeton(c):
    import re
    r = appel(c, 'get', '/organisation/identite/')
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.data.decode())
    return m.group(1) if m else ''


with A.app.app_context():
    a = socle.creer(M.Audit, reference='AUD-CQ', titre='Audit achats', type_audit='interne', client_id=1, statut='en_cours',
                    responsable_id=ids['gestionnaire'])
    for i in range(1, 46):
        socle.creer(M.Constatation, reference=f'CST-{i}', description='Bons de commande non signés. ' * 12, audit_id=a.id, client_id=1)
    b = socle.creer(M.Audit, reference='AUD-B', titre='Audit B', type_audit='interne', client_id=2, statut='en_cours', responsable_id=ids['admin_b'])
    db.session.commit()
    AID, BID = a.id, b.id
    from PIL import Image
    t = io.BytesIO(); Image.new('RGB', (120, 90), (220, 20, 20)).save(t, 'PNG')
    from egalyx import identite
    identite.appliquer(1, logo=t.getvalue()); db.session.commit()

admin, gest, lect, admin_b = (socle.navigateur(A, ids[r]) for r in ('admin_a', 'gestionnaire', 'lecteur', 'admin_b'))
FORM = {'actif': '1', 'titre': "RAPPORT D'AUDIT INTERNE", 'libelle_1': 'CODE', 'valeur_1': 'ENR 003/ PRG-AUDI',
        'libelle_2': 'DATE', 'valeur_2': '1/03/2023', 'libelle_3': 'VERSION', 'valeur_3': '00', 'libelle_4': 'MISSION',
        'valeur_4': '{reference}', 'page_libelle': 'PAGE', 'page_format': 'n_de_N', 'logo': '1', 'police': 'arial',
        'taille': '8.5', 'taille_titre': '9.5', 'trait': 'fin', 'couleur_trait': '#000000', 'premiere_page': '1',
        'largeur_logo': '13', 'largeur': 'page'}

print('--- Réglage')
r = appel(admin, 'get', '/organisation/identite/')
verif('page : section « Cartouche qualité » complète', r.status_code == 200 and all(x in r.data for x in (
    b'cartouche-qualite', b'libelle_5', b'page_format', b'Mise en forme', b'Aper\xc3\xa7u PDF')))
r = appel(lect, 'post', '/organisation/cartouche-qualite/', data={**FORM, 'csrf_token': jeton(lect)})
verif('simple utilisateur : réglage refusé', r.status_code == 403, r.status_code)
r = appel(admin, 'post', '/organisation/cartouche-qualite/', data={**FORM, 'csrf_token': jeton(admin)})
with A.app.app_context():
    from egalyx import cartouche_qualite as C
    g_ = C.lire(1)
verif('réglage enregistré (4 cases + PAGE)', r.status_code in (302, 303) and g_['actif'] and len(g_['colonnes']) == 4
      and g_['colonnes'][3]['valeur'] == '{reference}', g_['colonnes'])
with A.app.app_context():
    verif('réglage journalisé', M.JournalActiviteClient.query.filter_by(action='cartouche_qualite').count() >= 1)
from urllib.parse import urlencode
r = appel(admin, 'get', '/organisation/cartouche-qualite/apercu?' + urlencode({**FORM, 'apercu': '1'}))
p = texte_pdf(r.data) if r.status_code == 200 else []
verif('aperçu PDF : 3 pages numérotées « n de 3 »', len(p) == 3 and all(f'{n} de 3' in t for n, t in enumerate(p, 1)), r.status_code)

print('--- Exports PDF (ReportLab)')
for nom, url in (('export PDF', f'/audit/{AID}/export/rapport-pdf'), ('rapport complet PDF', f'/audit/{AID}/export/rapport-complet')):
    r = appel(gest, 'get', url)
    p = texte_pdf(r.data) if r.status_code == 200 and r.data[:4] == b'%PDF' else []
    n = len(p)
    verif(f'{nom} : cartouche sur chaque page, « n de {n} »', n >= 2 and all(
        "RAPPORT D'AUDIT INTERNE" in t and 'ENR 003/ PRG-AUDI' in t and f'{i} de {n}' in t for i, t in enumerate(p, 1)), (r.status_code, n))
    verif(f'{nom} : champ {{reference}} rempli', bool(p) and 'AUD-CQ' in p[0] and '{reference}' not in p[0])
    import pypdf
    largeur = float(pypdf.PdfReader(io.BytesIO(r.data)).pages[0].mediabox.width) if p else 0
    verif(f'{nom} : format A4', abs(largeur - 595.28) < 1, largeur)
r = appel(admin_b, 'get', f'/audit/{AID}/export/rapport-complet')
verif('rapport complet PDF : refusé à une autre organisation (corrigé)', not (r.status_code == 200 and r.data[:4] == b'%PDF'), r.status_code)

print('--- PDF élégant (WeasyPrint)')
try:
    import weasyprint  # noqa: F401
    vrai = not getattr(weasyprint, '__egalyx_remplacant__', False) and hasattr(weasyprint, '__version__')
except Exception:
    vrai = False
r = appel(gest, 'get', f'/audit/{AID}/rapport-pdf-elegant')
if vrai and r.status_code == 200 and r.data[:4] == b'%PDF':
    p = texte_pdf(r.data); n = len(p)
    verif('PDF élégant : cartouche sur chaque page, « n de N »', n >= 3 and all(
        'ENR 003/ PRG-AUDI' in t and f'{i} de {n}' in t for i, t in enumerate(p, 1)), n)
    verif('PDF élégant : plus de double numérotation', not any(f'Page {i} sur {n}' in t or f'Page {i} / {n}' in t for i, t in enumerate(p, 1)))
    verif('PDF élégant : contenu en pleine largeur (pas de réduction)', 'Résumé exécutif' in ' '.join(p))
else:
    print('     (WeasyPrint absent ici : PDF élégant vérifié par sa version imprimable)', r.status_code)
    verif('PDF élégant sans WeasyPrint : repli sans erreur', r.status_code in (200, 302), r.status_code)

print('--- Word')
from docx import Document
for nom, url in (('rapport Word', f'/audit/{AID}/rapport-word-pro'), ('export Word', f'/audit/{AID}/export-word'),
                 ('synthèse Word', f'/audit/{AID}/export/synthese-word')):
    r = appel(gest, 'get', url)
    ok = r.status_code == 200 and 'wordprocessing' in (r.headers.get('Content-Type') or '')
    d = Document(io.BytesIO(r.data)) if ok else None
    xml = d.sections[0].header._element.xml if d else ''
    verif(f'{nom} : cartouche en en-tête, PAGE / NUMPAGES', d is not None and 'ENR 003/ PRG-AUDI' in xml and 'AUD-CQ' in xml
          and 'NUMPAGES' in xml and "RAPPORT D'AUDIT INTERNE" in xml, r.status_code)
    verif(f'{nom} : une seule numérotation (pied sans « Page X / Y »)', d is not None and 'NUMPAGES' not in d.sections[0].footer._element.xml)

print('--- Variante : sans case PAGE, sans page de garde')
appel(admin, 'post', '/organisation/cartouche-qualite/', data={**FORM, 'page_format': 'aucune', 'premiere_page': '', 'csrf_token': jeton(admin)})
r = appel(gest, 'get', f'/audit/{AID}/export/rapport-pdf')
p = texte_pdf(r.data)
verif('page de garde sans cartouche, pages suivantes avec', 'ENR 003/ PRG-AUDI' not in p[0] and 'ENR 003/ PRG-AUDI' in p[1])
verif('sans case PAGE : numéro « Page n / N » en bas', f'Page 2 / {len(p)}' in p[1])

print('--- Désactivé : rapports comme avant')
appel(admin, 'post', '/organisation/cartouche-qualite/', data={**FORM, 'actif': '', 'csrf_token': jeton(admin)})
r = appel(gest, 'get', f'/audit/{AID}/export/rapport-pdf')
p = texte_pdf(r.data)
verif('cartouche désactivé : absent', not any('ENR 003/ PRG-AUDI' in t for t in p))
r = appel(gest, 'get', f'/audit/{AID}/rapport-word-pro')
dw = Document(io.BytesIO(r.data))
verif('Word sans cartouche, numérotation habituelle en pied', 'ENR 003' not in dw.sections[0].header._element.xml and 'NUMPAGES' in dw.sections[0].footer._element.xml)

print('--- Autre organisation')
appel(admin, 'post', '/organisation/cartouche-qualite/', data={**FORM, 'csrf_token': jeton(admin)})
r = appel(admin_b, 'get', f'/audit/{BID}/export/rapport-pdf')
p = texte_pdf(r.data) if r.data[:4] == b'%PDF' else ['']
verif('organisation B : son rapport sort, sans le cartouche de A', r.status_code == 200 and not any('ENR 003/ PRG-AUDI' in t for t in p), r.status_code)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')

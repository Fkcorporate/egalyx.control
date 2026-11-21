"""Recette : le rapport d'audit Word suit la présentation et le contenu choisis par l'organisation."""
import datetime as dt
import io
import os
os.environ['EGALYX_COLLECTE_AUTO'] = '0'
import socle
from socle import Muet, appel
with Muet():
    A, ids = socle.preparer()
import models as M
from models import db
from docx import Document
from werkzeug.datastructures import MultiDict

res = []


def verif(nom, cond, detail=''):
    res.append(bool(cond)); print('OK   ' if cond else 'ÉCHEC', nom, detail)


with A.app.app_context():
    a = socle.creer(M.Audit, reference='AUD-W', titre='Audit des achats', type_audit='interne', client_id=1, statut='en_cours',
                    responsable_id=ids['gestionnaire'])
    socle.creer(M.Constatation, reference='CST-W', description='Bons de commande non signés', audit_id=a.id, client_id=1)
    socle.creer(M.Recommandation, reference='REC-W', description='Signer les bons', type_recommandation='corrective',
                urgence=3, impact_operationnel=3, audit_id=a.id, client_id=1)
    db.session.commit()
    AID = a.id
c = socle.navigateur(A, ids['gestionnaire'])


def rapport():
    r = appel(c, 'get', f'/audit/{AID}/rapport-word-pro')
    if r.status_code != 200 or 'wordprocessingml' not in (r.headers.get('Content-Type') or ''):
        return None, r.status_code
    d = Document(io.BytesIO(r.data))
    corps = '\n'.join(p.text for p in d.paragraphs)
    tables = '\n'.join(cell.text for t in d.tables for row in t.rows for cell in row.cells)
    entete = '\n'.join(p.text for p in d.sections[0].header.paragraphs)
    pied = '\n'.join(p.text for p in d.sections[0].footer.paragraphs)
    pied_xml = d.sections[0].footer._element.xml
    titres = [p.text for p in d.paragraphs if p.style.name.startswith('Heading')]
    return {'doc': d, 'corps': corps, 'tables': tables, 'entete': entete, 'pied': pied, 'pied_xml': pied_xml, 'titres': titres}, 200


print('--- Sans réglage')
w, st = rapport()
verif('rapport Word généré', w is not None, st)
verif('titre et sections habituels', "RAPPORT D'AUDIT" in w['titres'] and all(t in w['titres'] for t in
      ('RÉSUMÉ EXÉCUTIF', 'TESTS DE CONTRÔLE', 'CONSTATATIONS DÉTAILLÉES', 'RECOMMANDATIONS', "PLANS D'ACTION", 'VALIDATION')), w['titres'])
verif('signataires habituels', 'Auditeur principal' in w['tables'] and 'Responsable Qualité' in w['tables'])
verif('pas d\'introduction ni de conclusion', 'INTRODUCTION' not in w['titres'] and 'CONCLUSION' not in w['titres'])
verif('numéro de page « Page X / Y »', 'PAGE' in w['pied_xml'] and 'NUMPAGES' in w['pied_xml'])
verif('mention habituelle « Egalyx Control » en pied', 'Egalyx Control - Rapport généré le' in w['pied'])

print('--- Avec la présentation et le contenu du client')
with A.app.app_context():
    from egalyx import identite, rapport_contenu
    from PIL import Image
    b = io.BytesIO(); Image.new('RGB', (200, 80), (14, 107, 79)).save(b, 'PNG')
    identite.appliquer(1, logo=b.getvalue())
    identite.appliquer_rapports(1, couleur='#0E6B4F', mention='Confidentiel — usage interne',
                                pied="Banque Recette S.A. — Direction de l'audit interne", logo=True)
    rapport_contenu.appliquer(1, 'audit', MultiDict([
        ('titre', "Rapport de mission d'audit interne"),
        ('sections', 'resume'), ('sections', 'constatations'), ('sections', 'recommandations'), ('sections', 'validation'),
        ('introduction', 'Mission {reference} — {mission}.\nConduite par la Direction de l\'audit interne de {organisation}.'),
        ('conclusion', 'Nous remercions les équipes.'),
        ('sig_regles', '1'), ('sig_fonction', "Directeur de l'audit interne"), ('sig_nom', 'Awa Koné'),
        ('sig_fonction', 'Directeur général'), ('sig_nom', '')]))
    db.session.commit()
w, st = rapport()
verif('rapport Word généré', w is not None, st)
verif('titre choisi', "RAPPORT DE MISSION D'AUDIT INTERNE" in w['titres'], w['titres'][:2])
verif('sections masquées absentes (tests, plans)', 'TESTS DE CONTRÔLE' not in w['titres'] and "PLANS D'ACTION" not in w['titres'], w['titres'])
verif('introduction, champs remplis', 'INTRODUCTION' in w['titres'] and 'Mission AUD-W — Audit des achats.' in w['corps']
      and '{organisation}' not in w['corps'])
verif('conclusion avant la validation', w['titres'].index('CONCLUSION') < w['titres'].index('VALIDATION'))
verif('signataires choisis', "Directeur de l'audit interne" in w['tables'] and 'Awa Koné' in w['tables'] and 'Directeur général' in w['tables']
      and 'Responsable Qualité' not in w['tables'])
verif('en-tête : nom de l\'organisation et mention', 'CONFIDENTIEL — USAGE INTERNE' in w['entete'])
verif('en-tête : logo', 'graphic' in w['doc'].sections[0].header._element.xml)
verif('pied : texte de l\'organisation + numéro de page', "Direction de l'audit interne" in w['pied'] and 'NUMPAGES' in w['pied_xml'])
h1 = w['doc'].styles['Heading 2'].font.color.rgb
verif('titres à la couleur du client', str(h1) == '0E6B4F', h1)
verif('en-têtes de tableaux à la couleur du client', '0E6B4F' in w['doc'].tables[-1]._element.xml)

print('--- Autres exports Word de l\'audit')
for u in (f'/audit/{AID}/export-word', f'/audit/{AID}/export/synthese-word'):
    r = appel(c, 'get', u)
    ok = r.status_code == 200 and 'wordprocessing' in (r.headers.get('Content-Type') or '')
    d = Document(io.BytesIO(r.data)) if ok else None
    verif(f'{u} : en-tête et pied du client', d is not None and 'CONFIDENTIEL' in '\n'.join(p.text for p in d.sections[0].header.paragraphs)
          and "Direction de l'audit interne" in '\n'.join(p.text for p in d.sections[0].footer.paragraphs), r.status_code)

print('--- Autre organisation')
with A.app.app_context():
    b2 = socle.creer(M.Audit, reference='AUD-WB', titre='Audit B', type_audit='interne', client_id=2, statut='en_cours')
    db.session.commit(); BID = b2.id
cb = socle.navigateur(A, ids['admin_b'])
r = appel(cb, 'get', f'/audit/{BID}/rapport-word-pro')
d = Document(io.BytesIO(r.data)) if r.status_code == 200 else None
verif('autre organisation : sa propre présentation (pas celle de A)', d is not None and "RAPPORT D'AUDIT" in [p.text for p in d.paragraphs]
      and 'CONFIDENTIEL' not in '\n'.join(p.text for p in d.sections[0].header.paragraphs), r.status_code)
r = appel(cb, 'get', f'/audit/{AID}/rapport-word-pro')
verif('autre organisation : pas le rapport de A', r.status_code != 200 or 'wordprocessingml' not in (r.headers.get('Content-Type') or ''), r.status_code)

print(f'\n{sum(res)}/{len(res)} vérifications réussies')

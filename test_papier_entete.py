"""Papier à en-tête PDF du client (egalyx/papier_entete.py) : dépôt par le super admin, détection de la zone libre,
pose des rapports d'audit sur le papier, numérotation « n de N », lettre de mission mise en page dans la zone libre,
cloisonnement entre organisations, retrait."""
import io
import logging
import re  # noqa: F401

import pytest
from flask import Response

from test_v4_parcours import contexte  # noqa: F401,E402  (fixture ; place aussi les doubles de models en tête)

pypdf = pytest.importorskip('pypdf')
logging.getLogger('pypdf').setLevel(logging.ERROR)


def faux_papier():
    """Papier d'essai : cartouche en haut avec « 1 de 1 », pied de page avec une adresse (aucune donnée réelle)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    t = io.BytesIO(); c = canvas.Canvas(t, pagesize=A4); W, H = A4
    c.rect(30, H - 80, W - 60, 50)
    c.setFont('Helvetica', 9); c.drawString(60, H - 60, 'RAPPORT D AUDIT TEST')
    c.setFont('Helvetica-Bold', 8); c.drawString(W - 80, H - 70, '1')
    c.setFont('Helvetica', 8); c.drawString(W - 72, H - 70, 'de ')
    c.setFont('Helvetica-Bold', 8); c.drawString(W - 60, H - 70, '1')
    c.line(40, 70, W - 40, 70); c.drawCentredString(W / 2, 50, 'ORGANISATION TEST - 1 rue Exemple')
    c.showPage(); c.save()
    return t.getvalue()


def rapport(pages=2):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate
    from reportlab.lib.styles import getSampleStyleSheet
    t = io.BytesIO(); st = getSampleStyleSheet()
    el = []
    for i in range(pages):
        el += [Paragraph(f'Constat numero {i + 1}', st['Heading1']), Paragraph('Texte du rapport. ' * 40, st['BodyText'])]
        if i < pages - 1:
            el.append(PageBreak())
    SimpleDocTemplate(t, pagesize=letter).build(el)
    return t.getvalue()


@pytest.fixture()
def app_papier(contexte, tmp_path, monkeypatch):  # noqa: F811
    app, c, d = contexte
    monkeypatch.setenv('EGALYX_DONNEES', str(tmp_path))
    monkeypatch.setenv('EGALYX_2FA_OBLIGATOIRE_ADMINS', '0')          # la double authentification est testée ailleurs
    from egalyx import papier_entete, lettre_mission
    if 'lettre_mission' not in app.blueprints:
        app.register_blueprint(lettre_mission.bp)          # page de réglages (retour après dépôt)
    papier_entete.enregistrer(app)
    # une route du nom de l'export du rapport d'audit (sections/audit.py) renvoyant un PDF de 2 pages
    app.add_url_rule('/essai/rapport', 'export_rapport_audit_pdf',
                     lambda: Response(rapport(), mimetype='application/pdf'))
    return app, c, d


def _deposer(c, cid, type_='rapport_audit', octets=None):
    return c.post(f'/super-admin/client/{cid}/papier-entete/{type_}',
                  data={'fichier': (io.BytesIO(octets or faux_papier()), 'papier.pdf')}, content_type='multipart/form-data')


def test_depot_reserve_au_super_admin_et_pdf_obligatoire(app_papier):
    app, c, d = app_papier
    cid = d['acme'].id
    c.get(f"/_connexion/{d['admin'].id}")
    assert _deposer(c, cid).status_code == 404                         # administrateur client : pas d'accès
    c.get(f"/_connexion/{d['conf'].id}")
    assert _deposer(c, cid).status_code == 404
    c.get(f"/_connexion/{d['sa'].id}")
    r = c.post(f'/super-admin/client/{cid}/papier-entete/rapport_audit',
               data={'fichier': (io.BytesIO(b'pas un pdf'), 'x.pdf')}, content_type='multipart/form-data')
    assert r.status_code == 302
    from egalyx.papier_entete import tous
    with app.test_request_context():
        assert tous(cid) == {}
    assert _deposer(c, cid).status_code == 302
    with app.test_request_context():
        reg = tous(cid)['rapport_audit']
    assert reg['numero'] is not None                                   # « 1 de 1 » repéré dans le cartouche
    assert 25 <= reg['haut'] <= 45 and 25 <= reg['bas'] <= 40          # zone libre sous le cartouche, au-dessus du pied


def test_rapport_pose_sur_le_papier_et_numerote(app_papier):
    app, c, d = app_papier
    c.get(f"/_connexion/{d['sa'].id}"); _deposer(c, d['acme'].id)
    c.get(f"/_connexion/{d['conf'].id}")                               # utilisateur de l'organisation
    r = c.get('/essai/rapport')
    lu = pypdf.PdfReader(io.BytesIO(r.data))
    assert len(lu.pages) == 2
    textes = [p.extract_text() for p in lu.pages]
    assert all('RAPPORT D AUDIT TEST' in t and 'ORGANISATION TEST' in t for t in textes)
    import re
    assert re.search(r'1\s*de\s*2', textes[0]) and re.search(r'2\s*de\s*2', textes[1])   # « 1 de 1 » réécrit
    assert 'Constat numero 2' in textes[1]
    assert abs(float(lu.pages[0].mediabox[3]) - 841.9) < 1             # le papier impose sa taille (A4)
    # une autre organisation, sans papier : rapport inchangé
    c.get(f"/_connexion/{d['conf_autre'].id}")
    brut = c.get('/essai/rapport').data
    assert 'RAPPORT D AUDIT TEST' not in pypdf.PdfReader(io.BytesIO(brut)).pages[0].extract_text()


def test_reglage_pause_et_retrait(app_papier):
    app, c, d = app_papier
    cid = d['acme'].id
    c.get(f"/_connexion/{d['sa'].id}"); _deposer(c, cid)
    c.post(f'/super-admin/client/{cid}/papier-entete/rapport_audit', data={'haut': '50', 'bas': '30', 'gauche': '20', 'droite': '20'})
    from egalyx.papier_entete import tous, reglage
    with app.test_request_context():
        reg = tous(cid)['rapport_audit']
        assert reg['haut'] == 50 and reg['actif'] is False and reglage(cid, 'rapport_audit') is None   # case décochée : en pause
    c.get(f"/_connexion/{d['conf'].id}")
    assert 'RAPPORT D AUDIT TEST' not in pypdf.PdfReader(io.BytesIO(c.get('/essai/rapport').data)).pages[0].extract_text()
    c.get(f"/_connexion/{d['sa'].id}")
    c.post(f'/super-admin/client/{cid}/papier-entete/rapport_audit', data={'haut': '50', 'bas': '30', 'actif': '1'})
    ap = c.get(f'/super-admin/client/{cid}/papier-entete/rapport_audit/apercu')
    assert ap.status_code == 200 and ap.mimetype == 'application/pdf'
    assert c.post(f'/super-admin/client/{cid}/papier-entete/rapport_audit/supprimer').status_code == 302
    with app.test_request_context():
        assert tous(cid) == {}


def test_lettre_mission_dans_la_zone_libre_sans_reduction(app_papier):
    app, c, d = app_papier
    cid = d['acme'].id
    c.get(f"/_connexion/{d['sa'].id}"); _deposer(c, cid, 'lettre_mission')
    from egalyx.papier_entete import page_exemple, poser, reglage
    with app.test_request_context():
        r = reglage(cid, 'lettre_mission')
        pdf = poser(page_exemple('Lettre', natif=True, r=r), cid, 'lettre_mission', natif=True)
    p = pypdf.PdfReader(io.BytesIO(pdf)).pages[0]
    t = p.extract_text()
    assert 'ORGANISATION TEST' in t and 'Lettre' in t

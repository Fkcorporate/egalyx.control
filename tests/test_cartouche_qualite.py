"""egalyx/cartouche_qualite.py + papier_entete.poser : cartouche qualité numéroté « n de N » sur chaque page."""
import pytest

pytest.importorskip('reportlab')
pypdf = pytest.importorskip('pypdf')


def test_cartouche_sur_chaque_page_et_numerote():
    import io
    from egalyx import cartouche_qualite as C, papier_entete as P
    r = dict(C.DEFAUT, actif=True, code='ENR 003/ PRG-AUDI', date='1/03/2023', version='00')
    octets, reglage = C.pdf_papier(r)
    reglage.update(octets=octets, chemin=None)
    pdf = P.poser(P.page_exemple("Rapport d'audit"), 1, 'rapport_audit', reglage_force=reglage)
    pages = pypdf.PdfReader(io.BytesIO(pdf)).pages
    assert len(pages) >= 2
    for n, page in enumerate(pages, start=1):
        texte = ' '.join(page.extract_text().split())
        assert "RAPPORT D'AUDIT INTERNE" in texte and 'ENR 003/ PRG-AUDI' in texte and 'VERSION' in texte
        assert f'{n} de {len(pages)}' in texte

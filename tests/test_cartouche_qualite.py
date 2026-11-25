"""egalyx/cartouche_qualite.py : cartouche qualité dessiné directement sur chaque page (PDF ReportLab, HTML), numéroté."""
import io

import pytest

pytest.importorskip('reportlab')
pypdf = pytest.importorskip('pypdf')


def _pdf(reglage, pages=3):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph
    from egalyx import cartouche_qualite as C
    tampon = io.BytesIO()
    doc = C.document_pdf(tampon, None, None, reglage=dict(C.normaliser(reglage), actif=True))
    st = getSampleStyleSheet()
    story = []
    for n in range(pages):
        story.append(Paragraph(f'Contenu {n + 1}', st['Normal']))
        if n < pages - 1:
            story.append(PageBreak())
    doc.build(story)
    return pypdf.PdfReader(io.BytesIO(tampon.getvalue())).pages


def test_cartouche_sur_chaque_page_et_numerote():
    pages = _pdf({'colonnes': [{'libelle': 'CODE', 'valeur': 'ENR 003/ PRG-AUDI'}, {'libelle': 'DATE', 'valeur': '1/03/2023'},
                               {'libelle': 'VERSION', 'valeur': '00'}], 'logo': False})
    assert len(pages) == 3
    for n, page in enumerate(pages, start=1):
        texte = ' '.join(page.extract_text().split())
        assert "RAPPORT D'AUDIT INTERNE" in texte and 'ENR 003/ PRG-AUDI' in texte and 'VERSION' in texte
        assert f'{n} de 3' in texte
        assert f'Contenu {n}' in texte                          # le contenu est bien là, sous le cartouche
        assert float(page.mediabox.width) == pytest.approx(595.28, abs=0.5)   # A4


def test_formats_de_page_et_page_de_garde():
    pages = _pdf({'page_format': 'page_n_sur_N', 'page_libelle': 'PAGINATION', 'premiere_page': False, 'logo': False})
    assert 'PAGINATION' not in pages[0].extract_text()
    assert 'Page 2 sur 3' in ' '.join(pages[1].extract_text().split())


def test_ancien_reglage_repris():
    from egalyx import cartouche_qualite as C
    r = C.normaliser({'actif': True, 'titre': 'RAPPORT', 'code': 'ENR 003', 'date': '1/03/2023', 'version': '00'})
    assert [c['libelle'] for c in r['colonnes']] == ['CODE', 'DATE', 'VERSION']
    assert r['colonnes'][0]['valeur'] == 'ENR 003'


def test_html_echappe_et_compteurs():
    from egalyx import cartouche_qualite as C
    r = C.normaliser({'titre': '<script>x</script>', 'colonnes': [{'libelle': 'CODE', 'valeur': '"><b>'}], 'logo': False})
    h = str(C.html(r))
    assert '<script>' not in h and '&lt;script&gt;' in h and '"><b>' not in h
    assert 'cq-n' in h and 'cq-total' in h
    assert 'counter(pages)' in str(C.css(r))


def test_largeurs_selon_le_contenu():
    from egalyx import cartouche_qualite as C
    r = C.normaliser({'colonnes': [{'libelle': 'CODE', 'valeur': 'ENR 003/ PRG-AUDI'}, {'libelle': 'VERSION', 'valeur': '00'}]})
    lg, lt, lc = C.largeurs(r, True)
    assert abs(lg + lt + sum(lc) - 100) < 0.01
    assert lc[0] > lc[1]                                         # la case CODE, plus remplie, est plus large

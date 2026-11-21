"""
egalyx/rapport_word.py — présentation de l'organisation dans les rapports Word (python-docx).

Même réglage que les rapports PDF (egalyx/identite.presentation_rapport) :
  - en-tête de page : logo, nom de l'organisation, mention de confidentialité ;
  - couleur du client sur les titres et les en-têtes de tableaux ;
  - pied de page : texte de l'organisation et numéro de page « Page X / Y ».
Sans réglage, seuls le nom (et le logo s'il existe) apparaissent en en-tête ; les couleurs restent celles de Word.
"""
import base64
import io
import re

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROUGE_MENTION = RGBColor(0xB4, 0x23, 0x18)
GRIS = RGBColor(0x6B, 0x72, 0x80)


def _rgb(hexa):
    hexa = (hexa or '').lstrip('#')
    return RGBColor(int(hexa[0:2], 16), int(hexa[2:4], 16), int(hexa[4:6], 16)) if re.fullmatch(r'[0-9A-Fa-f]{6}', hexa) else None


def _image(data_uri):
    m = re.match(r'data:image/[a-z+]+;base64,(.+)$', data_uri or '', re.S)
    if not m:
        return None
    try:
        return io.BytesIO(base64.b64decode(m.group(1)))
    except Exception:
        return None


def _champ(paragraphe, instruction):
    """Insère un champ Word (PAGE, NUMPAGES…) mis à jour à l'ouverture."""
    run = paragraphe.add_run()
    debut = OxmlElement('w:fldChar'); debut.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText'); instr.set(qn('xml:space'), 'preserve'); instr.text = instruction
    sep = OxmlElement('w:fldChar'); sep.set(qn('w:fldCharType'), 'separate')
    texte = OxmlElement('w:t'); texte.text = '1'
    fin = OxmlElement('w:fldChar'); fin.set(qn('w:fldCharType'), 'end')
    for el in (debut, instr, sep, texte, fin):
        run._r.append(el)
    return run


def ombrer(cellule, hexa):
    """Fond d'une cellule de tableau."""
    tc = cellule._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), hexa.lstrip('#'))
    tc.append(shd)


def entete_tableau(table, rp):
    """En-tête de tableau aux couleurs du client (texte blanc sur la couleur) ; rien sans couleur réglée."""
    if not rp or not rp.get('couleur_client'):
        return
    for cellule in table.rows[0].cells:
        ombrer(cellule, rp['couleur_client'])
        for p in cellule.paragraphs:
            for r in p.runs:
                r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                r.bold = True


def preparer_document(doc, rp):
    """Applique la présentation de l'organisation au document (en-tête, pied, couleur des titres)."""
    if not rp:
        return
    couleur = _rgb(rp.get('couleur_client'))
    if couleur:
        for nom in ('Title', 'Heading 1', 'Heading 2', 'Heading 3', 'Heading 4'):
            try:
                doc.styles[nom].font.color.rgb = couleur
            except KeyError:
                pass
    section = doc.sections[0]
    # En-tête : logo, nom, mention
    if rp.get('logo') or rp.get('nom') or rp.get('mention'):
        entete = section.header
        p = entete.paragraphs[0]
        p.text = ''
        img = _image(rp.get('logo'))
        if img is not None:
            try:
                p.add_run().add_picture(img, height=Cm(1.1))
                p.add_run('   ')
            except Exception:
                pass
        if rp.get('nom'):
            r = p.add_run(rp['nom'])
            r.bold = True
            r.font.size = Pt(10)
            if couleur:
                r.font.color.rgb = couleur
        if rp.get('mention'):
            r = p.add_run('\t\t' + rp['mention'].upper())
            r.bold = True
            r.font.size = Pt(8)
            r.font.color.rgb = ROUGE_MENTION
    # Pied : texte de l'organisation, puis « Page X / Y »
    pied = section.footer
    p = pied.paragraphs[0]
    p.text = ''
    if rp.get('pied'):
        r = p.add_run(rp['pied'])
        r.font.size = Pt(8)
        r.font.color.rgb = GRIS
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p = pied.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for morceau in ('Page ', 'PAGE', ' / ', 'NUMPAGES'):
        run = _champ(p, morceau) if morceau in ('PAGE', 'NUMPAGES') else p.add_run(morceau)
        run.font.size = Pt(8)
        run.font.color.rgb = GRIS
    return p


def texte_libre(doc, texte):
    """Texte saisi par l'organisation (introduction, conclusion) : un paragraphe par ligne non vide."""
    for ligne in (texte or '').split('\n'):
        if ligne.strip():
            par = doc.add_paragraph(ligne.strip())
            par.paragraph_format.space_after = Pt(6)

"""
egalyx/pdf_tableaux.py — tableaux ReportLab lisibles pour les exports PDF.

Table() de ReportLab n'enroule pas le texte : une description longue déborde sur les cases voisines.
tableau_pdf() met chaque texte dans un Paragraph (retour à la ligne automatique) et ajuste les largeurs de
colonnes à la largeur utile de la page, en gardant leurs proportions.
"""
from xml.sax.saxutils import escape

LARGEUR_A4_UTILE = 595.28 - 2 * 15 * 72 / 25.4      # A4, marges de 15 mm


def tableau_pdf(data, colWidths=None, largeur=LARGEUR_A4_UTILE, taille=8, entete=True, **kw):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph, Table
    normal = ParagraphStyle('cellule', fontName='Helvetica', fontSize=taille, leading=taille * 1.25)
    gras = ParagraphStyle('cellule_entete', parent=normal, fontName='Helvetica-Bold')

    def cellule(v, ligne):
        if v is None:
            v = ''
        if isinstance(v, (str, int, float)):
            return Paragraph(escape(str(v)).replace('\n', '<br/>'), gras if (entete and ligne == 0) else normal)
        return v
    lignes = [[cellule(v, i) for v in row] for i, row in enumerate(data)]
    if colWidths:
        total = float(sum(colWidths))
        colWidths = [w * largeur / total for w in colWidths]
        # une colonne ne coupe jamais un mot (référence « REC-01 », « 15/11/2026 ») : largeur mini = son plus long mot
        from reportlab.pdfbase.pdfmetrics import stringWidth
        minis = []
        for j in range(len(colWidths)):
            mots = [m for row in data if j < len(row) and isinstance(row[j], (str, int, float)) for m in str(row[j]).split()]
            minis.append(min(max((stringWidth(m, 'Helvetica-Bold', taille) for m in mots), default=0) + 14, largeur * 0.4))   # + marges intérieures des cases (2 x 6 pt)
        manque = sum(max(0, mn - w) for mn, w in zip(minis, colWidths))
        if manque:
            souples = sum(w - mn for mn, w in zip(minis, colWidths) if w > mn) or 1
            colWidths = [mn if w <= mn else w - (w - mn) * manque / souples for mn, w in zip(minis, colWidths)]
    kw.setdefault('repeatRows', 1 if entete else 0)
    t = Table(lignes, colWidths=colWidths, **kw)
    t.setStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)])
    return t

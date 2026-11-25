"""
egalyx/appreciation_reco.py — appréciation de l'auditeur sur chaque recommandation d'audit.

Niveau (satisfaisant, partiellement satisfaisant, insatisfaisant, non évalué) + commentaire libre.
Saisie dans la fenêtre « Modifier » d'une recommandation (fiche audit) ; affichée dans la fiche audit,
le registre des recommandations, la fiche recommandation et les rapports d'audit.
Colonnes : Recommandation.appreciation, appreciation_commentaire, appreciation_le, appreciation_par_id.
"""
from datetime import datetime

from markupsafe import Markup, escape

NIVEAUX = {
    'satisfaisant': {'libelle': 'Satisfaisant', 'couleur': '#067647', 'fond': '#DCFAE6'},
    'partiel': {'libelle': 'Partiellement satisfaisant', 'couleur': '#B54708', 'fond': '#FEF0C7'},
    'insatisfaisant': {'libelle': 'Insatisfaisant', 'couleur': '#B42318', 'fond': '#FEE4E2'},
    'non_evalue': {'libelle': 'Non évalué', 'couleur': '#475467', 'fond': '#F2F4F7'},
}
COMMENTAIRE_MAX = 2000


def libelle(code):
    return NIVEAUX.get(code or '', {}).get('libelle', '')


def badge(reco, vide='—'):
    """Pastille colorée (styles en ligne : fonctionne à l'écran, à l'impression et en PDF)."""
    code = getattr(reco, 'appreciation', None) if not isinstance(reco, str) else reco
    n = NIVEAUX.get(code or '')
    if not n:
        return Markup(f'<span style="color:#98A2B3">{escape(vide)}</span>') if vide else Markup('')
    return Markup(f'<span class="egx-appreciation" style="display:inline-block;padding:2px 9px;border-radius:999px;'
                  f'font-size:.8em;font-weight:600;white-space:nowrap;color:{n["couleur"]};background:{n["fond"]}">'
                  f'{escape(n["libelle"])}</span>')


def enregistrer_formulaire(reco, form, user_id=None):
    """Lit les champs appreciation / appreciation_commentaire d'un formulaire, s'ils sont présents."""
    if 'appreciation' not in form and 'appreciation_commentaire' not in form:
        return False
    code = (form.get('appreciation') or '').strip()
    code = code if code in NIVEAUX else None
    commentaire = (form.get('appreciation_commentaire') or '').strip()[:COMMENTAIRE_MAX] or None
    if code == reco.appreciation and commentaire == reco.appreciation_commentaire:
        return False
    reco.appreciation, reco.appreciation_commentaire = code, commentaire
    reco.appreciation_le = datetime.utcnow() if (code or commentaire) else None
    reco.appreciation_par_id = user_id if (code or commentaire) else None
    return True


def enregistrer(app):
    app.jinja_env.globals.update(APPRECIATIONS=NIVEAUX, appreciation_badge=badge, appreciation_libelle=libelle)

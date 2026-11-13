"""
egalyx/questionnaire_stats.py — des statistiques de questionnaire vraies.

Avant : le graphique « Réponses par mois » affichait 12, 19, 15, 25, 22, 30 et chaque question à note affichait 5, 10,
15, 20, 25, quelles que soient les réponses ; la page ne vérifiait pas non plus que le questionnaire appartient au client.
Maintenant :
  - évolution = nombre réel de réponses par mois sur les 6 derniers mois ;
  - questions à note (« rating ») et à échelle (« range ») = répartition réelle des notes sur l'échelle de la question,
    avec la moyenne ;
  - accès limité au questionnaire du client (super-admin : tous) ; pour un modèle commun, seules les réponses du client
    sont comptées.
"""
from collections import Counter
from datetime import datetime

from flask import abort, render_template
from flask_login import current_user, login_required

TYPES = {'text': 'Texte court', 'textarea': 'Texte long', 'radio': 'Choix unique', 'checkbox': 'Choix multiple',
         'select': 'Liste déroulante', 'date': 'Date', 'email': 'Email', 'number': 'Nombre', 'range': 'Échelle',
         'rating': 'Évaluation', 'yesno': 'Oui/Non'}
MOIS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']


def _note(rep):
    if rep.valeur_numerique is not None:
        return rep.valeur_numerique
    try:
        return float(str(rep.valeur_texte).replace(',', '.'))
    except (TypeError, ValueError):
        return None


def six_derniers_mois(dates, maintenant=None):
    maintenant = maintenant or datetime.utcnow()
    mois = []
    a, m = maintenant.year, maintenant.month
    for _ in range(6):
        mois.append((a, m))
        a, m = (a - 1, 12) if m == 1 else (a, m - 1)
    mois.reverse()
    compte = Counter((d.year, d.month) for d in dates if d)
    return {'labels': [f"{MOIS[m - 1]} {str(a)[2:]}" for a, m in mois], 'valeurs': [compte.get(k, 0) for k in mois]}


def repartition_notes(notes, mini=1, maxi=5):
    mini = int(mini if mini is not None else 1)
    maxi = int(maxi if maxi is not None else 5)
    if maxi < mini or maxi - mini > 20:
        mini, maxi = 1, 5
    arrondies = Counter(int(round(n)) for n in notes if n is not None)
    labels = list(range(mini, maxi + 1))
    valides = [n for n in notes if n is not None]
    return {'labels': [str(x) for x in labels], 'valeurs': [arrondies.get(x, 0) for x in labels],
            'moyenne': round(sum(valides) / len(valides), 2) if valides else None, 'nb': len(valides)}


def statistiques_questionnaire(id):
    import models as M
    from models import db
    q = db.session.get(M.Questionnaire, id)
    if q is None:
        abort(404)
    super_admin = getattr(current_user, 'role', '') == 'super_admin'
    if not super_admin and q.client_id is not None and q.client_id != current_user.client_id:
        abort(404)

    base = M.ReponseQuestionnaire.query.filter_by(questionnaire_id=id)
    if not super_admin and q.client_id is None:                 # modèle commun : seulement les réponses du client
        base = base.filter(M.ReponseQuestionnaire.client_id == current_user.client_id)
    reponses = base.all()
    ids = [r.id for r in reponses]
    total = len(reponses)
    completes = sum(1 for r in reponses if r.statut == 'complet')
    stats = {'total_reponses': total, 'reponses_completes': completes,
             'taux_completion': (completes / total * 100) if total else 0}

    par_question = {}
    if ids:
        for rq in M.ReponseQuestion.query.filter(M.ReponseQuestion.reponse_questionnaire_id.in_(ids)).all():
            par_question.setdefault(rq.question_id, []).append(rq)

    questions_stats = []
    for categorie in q.categories:
        for question in categorie.questions:
            reps = par_question.get(question.id, [])
            details, notes = None, None
            if reps:
                if question.type in ('radio', 'select', 'checkbox', 'yesno'):
                    details = dict(Counter(r.valeur_texte for r in reps if r.valeur_texte))
                elif question.type == 'number':
                    v = sorted(r.valeur_numerique for r in reps if r.valeur_numerique is not None)
                    if v:
                        details = {'moyenne': sum(v) / len(v), 'min': v[0], 'max': v[-1], 'median': v[len(v) // 2]}
                elif question.type in ('rating', 'range'):
                    notes = repartition_notes([_note(r) for r in reps], question.echelle_min, question.echelle_max)
            questions_stats.append({
                'question': question.texte[:100] + ('...' if len(question.texte) > 100 else ''),
                'type': 'rating' if question.type == 'range' and notes else question.type,
                'type_display': TYPES.get(question.type, question.type),
                'total_reponses': len(reps), 'details': details, 'notes': notes,
            })

    return render_template('questionnaire/stats.html', questionnaire=q, stats=stats, questions_stats=questions_stats,
                           evolution=six_derniers_mois([r.date_debut for r in reponses]))


def enregistrer(app):
    if 'statistiques_questionnaire' in app.view_functions:
        app.view_functions['statistiques_questionnaire'] = login_required(statistiques_questionnaire)
        return True
    return False

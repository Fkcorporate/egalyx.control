"""
egalyx/satisfaction_audit.py — questionnaire de satisfaction des audités en fin de mission (pratique IIA :
recueillir l'avis des audités pour améliorer la fonction d'audit interne).

  - Quand le rapport définitif est émis, les audités (participants de l'audit et responsables des
    recommandations) reçoivent une notification avec le lien du questionnaire : 6 affirmations notées de 1 à 5
    (ou « sans avis ») et un commentaire libre. Une seule réponse par personne et par mission, modifiable
    pendant 30 jours.
  - Les membres de l'équipe d'audit ne répondent pas (ils ne s'évaluent pas eux-mêmes).
  - Résultats sans nom. Une mission n'affiche ses moyennes qu'à partir de 2 réponses (une réponse unique
    serait reconnaissable) ; les commentaires sont présentés sans nom, dans le désordre de leur arrivée.
  - Synthèse par année pour les gestionnaires de l'audit : moyenne par question, taux de réponse, missions.
"""
from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import client_id_courant, entier, journaliser

bp = Blueprint('satisfaction_audit', __name__, url_prefix='/audit-suivi')

QUESTIONS = [
    ('preparation', 'La mission a été bien préparée et son objectif clairement expliqué (lettre de mission, réunion d’ouverture).'),
    ('professionnalisme', 'Les auditeurs ont été professionnels, à l’écoute et respectueux de votre activité.'),
    ('organisation', 'Les demandes d’information et le calendrier de la mission ont été raisonnables.'),
    ('constats', 'Les constats sont exacts, étayés et compréhensibles.'),
    ('recommandations', 'Les recommandations sont pertinentes et réalisables.'),
    ('valeur', 'La mission apporte une valeur ajoutée à votre activité.'),
]
ECHELLE = [(1, 'Pas du tout d’accord'), (2, 'Plutôt pas d’accord'), (3, 'Mitigé'), (4, 'Plutôt d’accord'), (5, 'Tout à fait d’accord')]
SEUIL_ANONYMAT = 2
DELAI_MODIFICATION = timedelta(days=30)
COMMENTAIRE_MAX = 2000


def _m():
    import models
    return models


def _ap():
    from egalyx import audit_plus
    return audit_plus


def invites(audit):
    """Audités appelés à répondre : participants et responsables des recommandations, hors équipe d'audit."""
    ap = _ap()
    return ap.audites(audit) - ap.equipe(audit)


def peut_repondre(audit, u=None):
    u = u or current_user
    return audit.etat_rapport == 'definitif' and u.id in invites(audit)


def reponse_de(audit, u=None):
    u = u or current_user
    return _m().SatisfactionAudit.query.filter_by(audit_id=audit.id, user_id=u.id).first()


def resultats(reponses):
    """Moyennes par question et globale (sur les notes données), nombre de réponses, commentaires."""
    par_q = {}
    for code, _ in QUESTIONS:
        notes = [int(r.notes[code]) for r in reponses if r.notes and str(r.notes.get(code, '')).isdigit()]
        par_q[code] = {'moyenne': round(sum(notes) / len(notes), 1) if notes else None, 'nb': len(notes)}
    toutes = [int(v) for r in reponses for v in (r.notes or {}).values() if str(v).isdigit()]
    return {'nb': len(reponses), 'questions': par_q,
            'moyenne': round(sum(toutes) / len(toutes), 1) if toutes else None,
            'commentaires': sorted((r.commentaire for r in reponses if (r.commentaire or '').strip()), key=lambda c: c.lower())}


def resume_audit(audit):
    """Pour la page « Constats et réponses » (gestionnaires) : rien de lisible sous le seuil d'anonymat."""
    m = _m()
    reps = m.SatisfactionAudit.query.filter_by(audit_id=audit.id).all()
    nb_invites = len(invites(audit))
    res = resultats(reps)
    res['invites'] = nb_invites
    res['visible'] = len(reps) >= SEUIL_ANONYMAT
    if not res['visible']:
        res['questions'] = {}
        res['moyenne'] = None
        res['commentaires'] = []
    return res


def notifier_invites(audit):
    """Appelé à l'émission du rapport définitif (sans commit : l'appelant valide)."""
    m = _m()
    for uid in invites(audit):
        if uid == current_user.id:
            continue
        m.db.session.add(m.Notification(
            destinataire_id=uid, type_notification='audit_satisfaction', client_id=audit.client_id,
            titre=f'Votre avis sur l’audit {audit.reference}'[:200],
            message=(f"L'audit « {audit.titre} » est terminé. Deux minutes pour donner votre avis sur la mission ? "
                     "Vos réponses sont présentées sans votre nom.")[:500],
            entite_type='audit_satisfaction', entite_id=audit.id))


# ---------------------------------------------------------------- pages
@bp.route('/<int:audit_id>/satisfaction', methods=['GET', 'POST'])
@login_required
def questionnaire(audit_id):
    m = _m()
    a = _ap().charger_audit(audit_id)
    if a.etat_rapport != 'definitif':
        flash('Le questionnaire de satisfaction s’ouvre quand le rapport définitif est émis.', 'info')
        return redirect(url_for('detail_audit', id=a.id))
    if not peut_repondre(a):
        abort(403)
    existante = reponse_de(a)
    modifiable = existante is None or datetime.utcnow() - (existante.repondu_le or datetime.utcnow()) <= DELAI_MODIFICATION
    if request.method == 'POST':
        if not modifiable:
            flash('Votre réponse ne peut plus être modifiée (30 jours après l’envoi).', 'warning')
            return redirect(url_for('.questionnaire', audit_id=a.id))
        notes = {}
        for code, _ in QUESTIONS:
            v = entier(request.form.get(code))
            if v is not None and 1 <= v <= 5:
                notes[code] = v
        commentaire = (request.form.get('commentaire') or '').strip()[:COMMENTAIRE_MAX] or None
        if not notes and not commentaire:
            flash('Répondez à au moins une question, ou laissez un commentaire.', 'warning')
            return redirect(url_for('.questionnaire', audit_id=a.id))
        if existante is None:
            existante = m.SatisfactionAudit(client_id=a.client_id, audit_id=a.id, user_id=current_user.id)
            m.db.session.add(existante)
        existante.notes, existante.commentaire, existante.repondu_le = notes, commentaire, datetime.utcnow()
        journaliser('audit_satisfaction', {'audit_id': a.id, 'questions': len(notes)})   # sans les notes : anonymat
        m.db.session.commit()
        flash('Merci : votre avis est enregistré. Il sera présenté sans votre nom.', 'success')
        return redirect(url_for('.questionnaire', audit_id=a.id))
    return render_template('egalyx/audit_satisfaction.html', a=a, questions=QUESTIONS, echelle=ECHELLE,
                           r=existante, modifiable=modifiable, commentaire_max=COMMENTAIRE_MAX)


@bp.route('/satisfaction')
@login_required
def synthese():
    m = _m()
    ap = _ap()
    if not ap.module_audit_actif() or not ap.est_gestionnaire_audit():
        abort(403)
    cid = client_id_courant()
    annees = sorted({r.repondu_le.year for r in m.SatisfactionAudit.query.filter_by(client_id=cid).all() if r.repondu_le},
                    reverse=True)
    annee = entier(request.args.get('annee')) or (annees[0] if annees else datetime.utcnow().year)
    reps = [r for r in m.SatisfactionAudit.query.filter_by(client_id=cid).all() if r.repondu_le and r.repondu_le.year == annee]
    par_audit = {}
    for r in reps:
        par_audit.setdefault(r.audit_id, []).append(r)
    missions = []
    for aid, rs in par_audit.items():
        a = m.db.session.get(m.Audit, aid)
        if a is None:
            continue
        res = resultats(rs)
        missions.append({'audit': a, 'nb': res['nb'], 'invites': len(invites(a)),
                         'moyenne': res['moyenne'] if res['nb'] >= SEUIL_ANONYMAT else None})
    missions.sort(key=lambda x: (x['moyenne'] is None, x['moyenne'] or 0))
    total = resultats(reps)
    if total['nb'] < SEUIL_ANONYMAT:
        total.update({'questions': {}, 'moyenne': None, 'commentaires': []})
    total['commentaires'] = []   # les commentaires se lisent mission par mission
    return render_template('egalyx/audit_satisfaction_synthese.html', missions=missions, total=total, questions=QUESTIONS,
                           annee=annee, annees=annees or [annee], seuil=SEUIL_ANONYMAT)


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'satisfaction_audit.questionnaire'})
    app.jinja_env.globals['satisfaction_audit'] = resume_audit
    app.jinja_env.globals['satisfaction_peut_repondre'] = lambda a: _peut(a)
    app.jinja_env.globals['sat_questions'] = QUESTIONS


def _peut(a):
    try:
        return peut_repondre(a)
    except Exception:
        return False

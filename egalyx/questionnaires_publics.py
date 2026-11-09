"""
egalyx/questionnaires_publics.py — garde unique devant les adresses de réponse aux questionnaires.

Ces adresses sont accessibles sans connexion (répondants externes). Avant, seule la page d'accueil
du questionnaire vérifiait qu'il était public, actif et dans ses dates : les adresses d'envoi
acceptaient n'importe quel numéro, donc des réponses à des questionnaires internes de n'importe
quel client. Désormais, chaque envoi ou lecture exige un questionnaire :
  - existant et actif, dans sa période d'ouverture ;
  - public, OU l'utilisateur connecté appartient à l'organisation propriétaire.
"""
import re
from datetime import datetime

from flask import jsonify, request
from flask_login import current_user

REGLES = {
    '/api/questionnaire/<int:id>/repondre', '/api/questionnaire/<int:id>/reponse', '/api/questionnaire/<int:id>/repondant',
    '/api/questionnaire/<int:id>/reponses/<session_id>', '/api/questionnaire/<int:id>/reponses/<session_id>/statut',
    '/questionnaires/<int:id>/repondre', '/api/questionnaire/submit',
}


def identifiant_questionnaire():
    if request.view_args and isinstance(request.view_args.get('id'), int):
        return request.view_args['id']
    donnees = request.get_json(silent=True) or {}
    qid = donnees.get('questionnaire_id') or request.form.get('questionnaire_id')
    if not qid:
        m = re.search(r'/questionnaires/(\d+)/', request.headers.get('Referer', ''))
        qid = m.group(1) if m else None
    try:
        return int(qid) if qid else None
    except (TypeError, ValueError):
        return None


def autorise(q, utilisateur, maintenant=None):
    """Règle pure (testée) : le questionnaire peut-il recevoir / restituer des réponses pour cet utilisateur ?"""
    maintenant = maintenant or datetime.utcnow()
    if q is None or not getattr(q, 'est_actif', False):
        return False
    if q.date_debut and maintenant < q.date_debut:
        return False
    if q.date_fin and maintenant > q.date_fin:
        return False
    if getattr(q, 'est_public', False):
        return True
    if not getattr(utilisateur, 'is_authenticated', False):
        return False
    return getattr(utilisateur, 'role', None) == 'super_admin' or (
        q.client_id is not None and getattr(utilisateur, 'client_id', None) == q.client_id)


def controler():
    if request.method == 'OPTIONS' or request.url_rule is None or request.url_rule.rule not in REGLES:
        return None
    from models import db, Questionnaire
    qid = identifiant_questionnaire()
    q = db.session.get(Questionnaire, qid) if qid else None
    if not autorise(q, current_user):
        return jsonify({'success': False, 'error': 'Questionnaire indisponible'}), 404
    return None


def enregistrer(app):
    app.before_request(controler)

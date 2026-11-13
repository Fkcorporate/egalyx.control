"""
egalyx/demande_offre.py — la demande de changement d'offre part vraiment.

Avant : l'écran affichait « Demande envoyée au support » mais rien n'était transmis (une ligne de journal).
Maintenant :
  1. un ticket de support est créé (source « changement_offre ») : l'équipe Egalyx le voit dans son espace support ;
  2. si le serveur d'e-mail est configuré (SMTP_*), un e-mail part à EGALYX_EMAIL_CONTACT (ou à l'expéditeur par défaut) ;
  3. le message affiché dit exactement ce qui a été fait (référence du ticket, e-mail envoyé ou non) ;
  4. une même demande encore ouverte n'est pas dupliquée.
L'adresse /api/client/upgrade-request, appelée par la page « Utilisation » mais qui n'existait pas, est créée.
"""
import logging
import os
import sys

from flask import current_app, flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

journal = logging.getLogger('egalyx.demande_offre')
SOURCE = 'changement_offre'
OUVERTS = ('nouveau', 'en_cours', 'ouvert', 'en_attente')


def _est_admin_client():
    return bool(getattr(current_user, 'is_client_admin', False) or getattr(current_user, 'role', '') == 'admin')


def creer_demande(formule_id):
    """Crée (ou retrouve) la demande. Renvoie (ok, message, reference)."""
    import models as M
    from models import db
    try:
        formule = db.session.get(M.FormuleAbonnement, int(formule_id))
    except (TypeError, ValueError):
        formule = None
    if formule is None:
        return False, "Formule introuvable.", None
    client = current_user.client
    actuelle = client.formule.nom if getattr(client, 'formule', None) else 'Aucune'
    if getattr(client, 'formule', None) is not None and client.formule.id == formule.id:
        return False, f"Vous êtes déjà sur la formule {formule.nom}.", None

    sujet = f"Changement d'offre : {actuelle} → {formule.nom}"[:200]
    existant = (M.TicketSupport.query
                .filter(M.TicketSupport.client_id == client.id, M.TicketSupport.source == SOURCE,
                        M.TicketSupport.sujet == sujet, M.TicketSupport.statut.in_(OUVERTS)).first())
    if existant:
        return True, (f"Votre demande de passage à la formule {formule.nom} est déjà enregistrée "
                      f"(ticket {existant.reference}) : l'équipe Egalyx va vous recontacter."), existant.reference

    description = (f"Le client « {client.nom} » demande à changer d'offre.\n\n"
                   f"Formule actuelle : {actuelle}\nFormule demandée : {formule.nom}\n"
                   f"Demandé par : {current_user.username} ({current_user.email})\n\n"
                   "Merci de recontacter le client pour confirmer les conditions et procéder au changement.")
    ticket = M.TicketSupport(client_id=client.id, client_nom=current_user.username, client_email=current_user.email,
                             client_societe=client.nom, sujet=sujet, description=description, source=SOURCE,
                             statut='nouveau', priorite_client='haute', declarant_id=current_user.id,
                             ip_address=(request.remote_addr or '')[:45], user_agent=(request.user_agent.string or '')[:500])
    ticket.reference = ticket.generer_reference()
    db.session.add(ticket)
    db.session.commit()

    courriel_envoye = False
    try:
        from egalyx import courriel
        cfg = courriel.configuration()
        if cfg.get('mot_de_passe'):
            courriel_envoye = bool(courriel.envoyer(os.environ.get('EGALYX_EMAIL_CONTACT') or cfg['expediteur'],
                                                    f"[Egalyx] {sujet} — {client.nom} ({ticket.reference})", description))
    except Exception as e:
        journal.warning("E-mail de demande d'offre non envoyé : %s", e)

    try:
        app_mod = sys.modules[current_app.import_name]
        app_mod.log_activity(current_user.id, 'upgrade_request', f"{sujet} (ticket {ticket.reference})", 'client', client.id)
    except Exception:
        pass

    message = (f"Demande de passage à la formule {formule.nom} enregistrée (ticket {ticket.reference}). "
               "L'équipe Egalyx la reçoit dans son espace support"
               + (" et par e-mail" if courriel_envoye else "") + " et vous recontactera.")
    return True, message, ticket.reference


def client_request_upgrade():
    if not _est_admin_client():
        flash("Seuls les administrateurs client peuvent demander un changement d'offre.", 'error')
        return redirect(url_for('dashboard'))
    try:
        ok, message, _ref = creer_demande(request.form.get('formule_id'))
    except Exception as e:
        journal.exception("demande d'offre")
        ok, message = False, f"La demande n'a pas pu être enregistrée ({e}). Contactez-nous via la page Support."
    flash(message, 'success' if ok else 'error')
    return redirect(url_for('client_admin_usage'))


def api_client_upgrade_request():
    if not _est_admin_client():
        return jsonify({'success': False, 'error': "Seuls les administrateurs client peuvent demander un changement d'offre."}), 403
    data = request.get_json(silent=True) or {}
    try:
        ok, message, ref = creer_demande(data.get('formule_id'))
    except Exception as e:
        journal.exception("demande d'offre (API)")
        return jsonify({'success': False, 'error': f"La demande n'a pas pu être enregistrée : {e}"}), 500
    return jsonify({'success': ok, 'message': message, 'reference': ref, 'error': None if ok else message}), (200 if ok else 400)


def enregistrer(app):
    if 'client_request_upgrade' in app.view_functions:
        app.view_functions['client_request_upgrade'] = login_required(client_request_upgrade)
    if 'api_client_upgrade_request' not in app.view_functions:
        app.add_url_rule('/api/client/upgrade-request', 'api_client_upgrade_request',
                         login_required(api_client_upgrade_request), methods=['POST'])
    return True

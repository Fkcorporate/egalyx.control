"""
egalyx/signalements.py — « Signalements » (ex-tickets de support) : le canal de détection des incidents de chaque client.

Circuit : un utilisateur (ou une personne extérieure par le lien public) signale → les gestionnaires des
signalements trient → ce qui le mérite est converti en incident (qualifié ensuite : risque, dispositif, escalade).

1. Signaler : tout utilisateur connecté d'une organisation, opérateurs compris (« Signaler un incident », menu et
   espace opérateur). Le signalement est toujours rattaché à SA propre organisation (avant : l'adresse de la page
   choisissait l'organisation ; sans adresse, on tombait sur le formulaire du premier client avec sa liste de
   directions et services). Le déclarant est enregistré et suit ses signalements (« Mes signalements »).
2. Lien public (personnes extérieures) : désactivé par défaut ; l'administrateur ou un gestionnaire des
   signalements l'active et obtient un lien secret, régénérable. Protections : champ piège anti-robot, délai
   minimal de saisie, 5 envois par heure et par connexion.
3. Droits : voir tous les signalements = « Voir » ou « Gérer les tickets » ; traiter, archiver, supprimer = « Gérer » ;
   convertir en incident = « Gérer les tickets » + « Gérer les incidents ». Le détail d'un signalement (nom, e-mail,
   téléphone du déclarant) n'est plus lisible par n'importe quel membre de l'organisation.
4. Notifications : nouveau signalement → gestionnaires ; pris en charge, converti, classé → déclarant.
5. Orientation : le formulaire rappelle que les alertes éthiques (fraude, corruption, harcèlement) passent par le
   dispositif d'alerte confidentiel, quand ce module est actif.
"""
import secrets
import time
from collections import defaultdict, deque

from flask import (Blueprint, abort, current_app, flash, has_request_context, redirect, render_template, request,
                   session, url_for)
from flask_login import current_user, login_required
from werkzeug.datastructures import ImmutableMultiDict

from egalyx.commun import a_permission, est_admin_client, journaliser

bp = Blueprint('signalements', __name__, url_prefix='/signalements')

VOIR = ('can_view_tickets', 'can_manage_tickets')
GERER = ('can_manage_tickets',)
STATUTS_FINIS = ('traite', 'resolu', 'ferme', 'archive', 'converti')
_ENVOIS = defaultdict(deque)
DELAI_MINI_S = 3


def _m():
    import models
    return models


def peut(niveau, u=None):
    u = u or current_user
    if getattr(u, 'role', None) == 'super_admin':
        return True
    return a_permission(*(VOIR if niveau == 'voir' else GERER), u=u)


def peut_convertir(u=None):
    u = u or current_user
    return peut('gerer', u) and (getattr(u, 'role', None) == 'super_admin' or a_permission('can_manage_incidents', u=u))


def peut_parametrer(u=None):
    u = u or current_user
    return est_admin_client(u) or peut('gerer', u)


def module_actif(client=None):
    from egalyx.modules_client import modules_du_client
    client = client or getattr(current_user, 'client', None)
    actifs = modules_du_client(client) if client is not None else None
    return actifs is None or 'support' in actifs


def lien_alerte(client):
    """Lien du dispositif d'alerte (signalements éthiques confidentiels) si ce module est actif pour le client."""
    from egalyx.modules_client import modules_du_client
    if client is None:
        return None
    actifs = modules_du_client(client)
    if actifs is not None and 'alertes' not in actifs:
        return None
    try:
        return url_for('alerte.deposer', reference=client.reference)
    except Exception:  # noqa: BLE001
        return None


def _appeler_formulaire(client):
    """Réutilise le formulaire existant (directions, services, pièces jointes) en imposant l'organisation."""
    request.args = ImmutableMultiDict({'client': str(client.id)})
    return current_app.view_functions['nouveau_ticket_support']()


# ---------------------------------------------------------------- pages
@bp.route('/nouveau', methods=['GET', 'POST'])
@login_required
def nouveau():
    m = _m()
    if not current_user.client_id:
        flash("Le super admin n'appartient à aucune organisation : ouvrez l'espace d'un client pour signaler.", 'info')
        return redirect(url_for('liste_tickets_support'))
    client = m.db.session.get(m.Client, current_user.client_id)
    if not module_actif(client):
        abort(404)
    return _appeler_formulaire(client)


@bp.route('/public/<jeton>', methods=['GET', 'POST'])
def public(jeton):
    m = _m()
    client = m.Client.query.filter_by(signalement_jeton=jeton).first() if jeton and len(jeton) >= 20 else None
    if client is None or not client.signalement_public or not client.is_active or not module_actif(client):
        return render_template('egalyx/signalement_lien_invalide.html'), 404
    if getattr(current_user, 'is_authenticated', False) and current_user.client_id == client.id:
        return redirect(url_for('.nouveau'))
    cle = f'signalement_ouvert_{client.id}'
    if request.method == 'GET':
        session[cle] = time.time()
        return _appeler_formulaire(client)
    # Protections anti-robot et anti-saturation (formulaire anonyme)
    if request.form.get('site_web'):
        return redirect(url_for('.public', jeton=jeton))
    ouvert = session.get(cle)
    if not ouvert or time.time() - float(ouvert) < DELAI_MINI_S:
        flash("Merci de vérifier votre saisie puis d'envoyer à nouveau.", 'warning')
        session[cle] = time.time()
        return redirect(url_for('.public', jeton=jeton))
    from egalyx.commun import adresse_ip
    maintenant = time.time()
    file = _ENVOIS[(client.id, adresse_ip())]
    while file and maintenant - file[0] > 3600:
        file.popleft()
    if len(file) >= 5:
        flash('Trop de signalements envoyés depuis cette connexion. Réessayez dans une heure.', 'danger')
        return redirect(url_for('.public', jeton=jeton))
    file.append(maintenant)
    return _appeler_formulaire(client)


@bp.route('/mes-signalements')
@login_required
def miens():
    m = _m()
    T = m.TicketSupport
    q = T.query.filter(T.client_id == current_user.client_id)
    email = (getattr(current_user, 'email', '') or '').lower()
    q = q.filter((T.declarant_id == current_user.id) | ((T.declarant_id.is_(None)) & (T.client_email == email)))
    tickets = q.order_by(T.created_at.desc()).all()
    incidents = {i.id: i for i in m.Incident.query.filter(
        m.Incident.id.in_([t.incident_id for t in tickets if t.incident_id] or [-1])).all()}
    gabarit = 'operateur/base_operateur.html' if getattr(current_user, 'is_operateur', False) else 'base.html'
    return render_template('egalyx/signalements_miens.html', tickets=tickets, incidents=incidents, gabarit=gabarit)


@bp.route('/parametres', methods=['GET', 'POST'])
@login_required
def parametres():
    m = _m()
    if not peut_parametrer() or not current_user.client_id:
        abort(403)
    client = m.db.session.get(m.Client, current_user.client_id)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'activer':
            client.signalement_public = True
            if not client.signalement_jeton:
                client.signalement_jeton = secrets.token_urlsafe(24)
            flash('Lien public de signalement activé.', 'success')
        elif action == 'desactiver':
            client.signalement_public = False
            flash('Lien public désactivé : il ne fonctionne plus.', 'info')
        elif action == 'regenerer':
            client.signalement_jeton = secrets.token_urlsafe(24)
            flash("Nouveau lien créé : l'ancien ne fonctionne plus.", 'success')
        journaliser(f'signalement_lien_{action}', {})
        m.db.session.commit()
        return redirect(url_for('.parametres'))
    lien = url_for('.public', jeton=client.signalement_jeton, _external=True) \
        if client.signalement_public and client.signalement_jeton else None
    return render_template('egalyx/signalements_parametres.html', client=client, lien=lien,
                           lien_alerte=lien_alerte(client))


# ---------------------------------------------------------------- anciennes pages : mêmes règles
DROITS = {'liste_tickets_support': 'voir', 'details_ticket': 'detail', 'archiver_ticket': 'gerer',
          'restaurer_ticket': 'gerer', 'supprimer_definitivement_ticket': 'gerer', 'traiter_ticket': 'traiter',
          'convertir_ticket_en_incident': 'convertir'}


def _ticket_requete():
    m = _m()
    va = request.view_args or {}
    tid = va.get('ticket_id', va.get('id'))
    return m.db.session.get(m.TicketSupport, tid) if isinstance(tid, int) else None


def droit_ticket(endpoint=None):
    endpoint = endpoint or request.endpoint
    niveau = DROITS.get(endpoint, 'voir')
    if niveau == 'detail':
        t = _ticket_requete()
        return peut('voir') or (t is not None and t.declarant_id == getattr(current_user, 'id', None))
    if niveau == 'convertir' or (niveau == 'traiter' and request.form.get('convertir_incident') == 'on'):
        return peut_convertir()
    return peut('gerer' if niveau in ('gerer', 'traiter') else 'voir')


def _garde():
    ep = request.endpoint or ''
    if ep == 'nouveau_ticket_support':
        # L'ancienne adresse : connecté → sa propre organisation ; anonyme → seulement par le lien public
        if getattr(current_user, 'is_authenticated', False) and getattr(current_user, 'role', None) != 'super_admin':
            return redirect(url_for('signalements.nouveau'))
        if not getattr(current_user, 'is_authenticated', False):
            jeton = request.args.get('jeton')
            if jeton:
                return redirect(url_for('signalements.public', jeton=jeton))
            return render_template('egalyx/signalement_lien_invalide.html'), 404
        return None
    if ep not in DROITS:
        return None
    if not getattr(current_user, 'is_authenticated', False) or getattr(current_user, 'role', None) == 'super_admin':
        return None
    if droit_ticket(ep):
        return None
    from flask import jsonify
    message = ("Il faut « Gérer les tickets » et « Gérer les incidents » pour convertir un signalement en incident."
               if DROITS[ep] in ('convertir',) or request.form.get('convertir_incident') == 'on'
               else "Vous n'avez pas la permission nécessaire pour les signalements.")
    if request.method != 'GET' and (request.is_json or 'json' in (request.headers.get('Accept') or '')
                                    or ep in ('archiver_ticket', 'restaurer_ticket', 'supprimer_definitivement_ticket',
                                              'convertir_ticket_en_incident', 'details_ticket')):
        return jsonify({'success': False, 'error': message}), 403
    if ep == 'details_ticket':
        return jsonify({'success': False, 'error': message}), 403
    flash(message, 'warning')
    return redirect(url_for('signalements.miens') if ep == 'liste_tickets_support' else
                    (url_for('liste_tickets_support') if peut('voir') else url_for('dashboard')))


# ---------------------------------------------------------------- enregistrement : déclarant, organisation, avis
def _avant_flush(session_, _ctx, _inst):
    m = _m()
    if not has_request_context():
        return
    u = current_user if getattr(current_user, 'is_authenticated', False) else None
    for t in list(session_.new):
        if not isinstance(t, m.TicketSupport):
            continue
        if u is not None and getattr(u, 'role', None) != 'super_admin' and u.client_id:
            t.client_id = u.client_id                 # jamais dans une autre organisation
            if not t.declarant_id:
                t.declarant_id = u.id
        t._egalyx_nouveau = True
        session_.info.setdefault('egalyx_tickets', set()).add(t)
    for t in list(session_.dirty):
        if isinstance(t, m.TicketSupport):
            from sqlalchemy import inspect as sa_inspect
            insp = sa_inspect(t)
            h_statut, h_inc = insp.attrs.statut.history, insp.attrs.incident_id.history
            if (h_statut.added and h_statut.deleted and h_statut.added[0] != h_statut.deleted[0]) or \
                    (h_inc.added and h_inc.added[0] and not (h_inc.deleted and h_inc.deleted[0])):
                t._egalyx_change = True
                session_.info.setdefault('egalyx_tickets', set()).add(t)


def _apres_flush(session_, _ctx):
    m = _m()
    a_traiter = session_.info.pop('egalyx_tickets', None)
    if not a_traiter:
        return
    for t in a_traiter:
        if getattr(t, '_egalyx_nouveau', False):
            t._egalyx_nouveau = False
            for u in m.User.query.filter_by(client_id=t.client_id, is_active=True).all():
                if u.id != t.declarant_id and u.has_permission('can_manage_tickets'):
                    session_.add(m.Notification(destinataire_id=u.id, type_notification='signalement',
                                                titre=f'Nouveau signalement : {t.reference}'[:200],
                                                message=f'« {t.sujet} » — {t.client_nom}', entite_type='ticket',
                                                entite_id=t.id, client_id=t.client_id))
        if getattr(t, '_egalyx_change', False):
            t._egalyx_change = False
            if t.declarant_id and t.declarant_id != getattr(current_user, 'id', None):
                if t.incident_id:
                    texte = 'a été transformé en incident et est pris en charge.'
                elif t.statut == 'archive':
                    texte = 'a été classé.'
                elif t.statut in STATUTS_FINIS:
                    texte = 'a été traité.'
                else:
                    texte = 'est pris en charge.'
                session_.add(m.Notification(destinataire_id=t.declarant_id, type_notification='signalement',
                                            titre=f'Votre signalement {t.reference}'[:200],
                                            message=f'Votre signalement « {t.sujet} » {texte}', entite_type='ticket',
                                            entite_id=t.id, client_id=t.client_id))


# ---------------------------------------------------------------- « Ma semaine »
def taches(u, ajout, horizon, aujourd_hui, lien):
    m = _m()
    if not u.client_id or not peut('gerer', u):
        return
    for t in m.TicketSupport.query.filter(m.TicketSupport.client_id == u.client_id,
                                          m.TicketSupport.statut.in_(('nouveau', 'en_cours'))).all():
        question = t.source == 'assistant'
        ajout(('Question à traiter' if question else 'Signalement à trier') if t.statut == 'nouveau'
              else ('Question en cours' if question else 'Signalement en cours'), t.sujet,
              f'{t.reference} · {t.client_nom}', t.created_at, lien('liste_tickets_support'),
              1 if t.statut == 'nouveau' else 2)


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    exempter_controle_ancien(app, set(DROITS) | {'nouveau_ticket_support'})
    import models as m
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    app.register_blueprint(bp)
    app.before_request(_garde)
    if not getattr(m, '_egalyx_signalements_flush', False):
        event.listen(Session, 'before_flush', _avant_flush)
        event.listen(Session, 'after_flush_postexec', _apres_flush)
        m._egalyx_signalements_flush = True
    import os
    app.jinja_env.globals['egalyx_email_support'] = os.environ.get('EGALYX_EMAIL_SUPPORT') or 'contact@egalyx.com'
    app.jinja_env.globals.update(signalement_peut_voir=lambda: peut('voir'),
                                 signalement_peut_parametrer=peut_parametrer,
                                 signalement_peut_convertir=peut_convertir,
                                 signalement_module_actif=module_actif,
                                 signalement_lien_alerte=lien_alerte)

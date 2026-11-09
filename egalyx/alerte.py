"""
egalyx/alerte.py — dispositif d'alerte interne (loi Sapin II modifiée par la loi Waserman,
directive UE 2019/1937 ; utilisable aussi comme canal d'éthique en Afrique francophone).

Côté lanceur d'alerte (public, sans compte) :
    /alerte/<reference_organisation>   dépôt, anonyme ou non
    /alerte/suivi                      suivi avec code + mot de passe, échanges avec le référent
Côté organisation (référents) :
    /conformite/alertes                liste, instruction, échanges, clôture

Confidentialité : contenu, personnes visées et identité chiffrés en base ; aucun e-mail ne
contient le contenu du signalement ; le super administrateur de la plateforme n'y a pas accès.
Délais suivis : accusé de réception sous 7 jours, retour d'information sous 3 mois.
"""
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from werkzeug.security import check_password_hash, generate_password_hash

from egalyx.commun import adresse_ip, client_requis, envoyer_courriel, journaliser

bp_public = Blueprint('alerte', __name__)
bp = Blueprint('alertes', __name__, url_prefix='/conformite/alertes')

ROLES_REFERENT = ('compliance', 'conformite', 'referent_alerte', 'deontologue')
_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
_DEPOTS = defaultdict(deque)          # limitation simple par adresse IP (par processus)
_ESSAIS_SUIVI = defaultdict(deque)
DUREE_SESSION_SUIVI = 1800


def _limite(registre, cle, maxi, fenetre_s):
    maintenant = time.time()
    file = registre[cle]
    while file and maintenant - file[0] > fenetre_s:
        file.popleft()
    if len(file) >= maxi:
        return False
    file.append(maintenant)
    return True


def nouveau_code_suivi():
    bloc = lambda: ''.join(secrets.choice(_ALPHABET) for _ in range(4))
    return f'ALR-{bloc()}-{bloc()}'


def est_referent(u=None):
    u = u or current_user
    if not getattr(u, 'is_authenticated', False) or getattr(u, 'role', None) == 'super_admin':
        return False                      # confidentialité : l'opérateur de la plateforme n'y a pas accès
    verifier = getattr(u, 'has_permission', None)
    if callable(verifier):
        return bool(verifier('can_manage_alertes'))
    return getattr(u, 'role', None) in ('admin',) + ROLES_REFERENT or bool(getattr(u, 'is_client_admin', False))


def _organisation(reference):
    from models import Client
    c = Client.query.filter_by(reference=reference).first()
    if not c or not c.is_active:
        abort(404)
    return c


def _referents(client_id):
    from models import User
    return [u for u in User.query.filter_by(client_id=client_id, is_active=True).all()
            if est_referent(u) and not getattr(u, 'is_blocked', False) and not getattr(u, 'deleted_at', None)]


# =================================================================== public
@bp_public.route('/alerte/<reference>', methods=['GET', 'POST'])
def deposer(reference):
    from models import db, Signalement, MessageSignalement
    org = _organisation(reference)
    if request.method == 'POST':
        if request.form.get('site_web'):           # champ piège invisible : robot
            return redirect(url_for('.deposer', reference=reference))
        if not _limite(_DEPOTS, adresse_ip(), 5, 3600):
            flash('Trop de signalements envoyés depuis cette connexion. Réessayez dans une heure.', 'danger')
            return render_template('egalyx/alerte_depot.html', org=org, f=request.form, categories=Signalement.CATEGORIES), 429
        f = request.form
        erreurs = []
        description = (f.get('description') or '').strip()
        mdp = f.get('mot_de_passe') or ''
        if f.get('categorie') not in Signalement.CATEGORIES:
            erreurs.append('Choisissez une catégorie.')
        if len(description) < 30:
            erreurs.append('Décrivez les faits (au moins 30 caractères).')
        if len(mdp) < 8 or mdp != f.get('mot_de_passe2'):
            erreurs.append('Le mot de passe de suivi doit faire au moins 8 caractères et être confirmé.')
        if not f.get('bonne_foi'):
            erreurs.append('Vous devez confirmer agir de bonne foi.')
        anonyme = f.get('anonyme') == '1'
        if not anonyme and not (f.get('nom') or '').strip():
            erreurs.append('Indiquez votre nom, ou choisissez le signalement anonyme.')
        if erreurs:
            for e in erreurs:
                flash(e, 'danger')
            return render_template('egalyx/alerte_depot.html', org=org, f=f, categories=Signalement.CATEGORIES)

        code = nouveau_code_suivi()
        while Signalement.query.filter_by(code_suivi=code).first():
            code = nouveau_code_suivi()
        s = Signalement(client_id=org.id, code_suivi=code, mot_de_passe_hash=generate_password_hash(mdp),
                        categorie=f['categorie'], date_faits=(f.get('date_faits') or '')[:100] or None,
                        lieu=(f.get('lieu') or '')[:200] or None, anonyme=anonyme)
        s.description = description[:20000]
        s.personnes_impliquees = (f.get('personnes') or '').strip()[:5000] or None
        if not anonyme:
            s.identite = {'nom': f.get('nom', '').strip()[:200], 'fonction': f.get('fonction', '').strip()[:200],
                          'contact': f.get('contact', '').strip()[:200]}
        db.session.add(s)
        db.session.flush()
        m = MessageSignalement(signalement_id=s.id, auteur='systeme')
        m.contenu = 'Signalement déposé.'
        db.session.add(m)
        db.session.commit()
        for r in _referents(org.id):
            envoyer_courriel(r.email, 'Nouveau signalement reçu — Egalyx Control',
                             f"Un nouveau signalement a été déposé dans le dispositif d'alerte de {org.nom}.\n"
                             f"Accusé de réception à envoyer avant le {s.echeance_accuse:%d/%m/%Y}.\n\n"
                             f"Consultez-le dans Egalyx Control (Conformité > Alertes). Par confidentialité, "
                             f"ce message ne contient aucun détail.")
        session['alerte_code_affiche'] = code
        return redirect(url_for('.depot_confirme', reference=reference))
    return render_template('egalyx/alerte_depot.html', org=org, f={}, categories=Signalement.CATEGORIES)


@bp_public.route('/alerte/<reference>/confirmation')
def depot_confirme(reference):
    org = _organisation(reference)
    code = session.pop('alerte_code_affiche', None)
    if not code:
        return redirect(url_for('.suivi'))
    return render_template('egalyx/alerte_confirmation.html', org=org, code=code)


def _signalement_suivi():
    from models import db, Signalement
    info = session.get('alerte_suivi') or {}
    if not info or time.time() - info.get('t', 0) > DUREE_SESSION_SUIVI:
        session.pop('alerte_suivi', None)
        return None
    return db.session.get(Signalement, info.get('id'))


@bp_public.route('/alerte/suivi', methods=['GET', 'POST'])
def suivi():
    from models import db, Signalement, MessageSignalement
    if request.method == 'POST' and request.form.get('action') == 'connexion':
        if not _limite(_ESSAIS_SUIVI, adresse_ip(), 10, 900):
            flash('Trop de tentatives. Réessayez dans 15 minutes.', 'danger')
            return render_template('egalyx/alerte_suivi.html', s=None), 429
        code = (request.form.get('code') or '').strip().upper()
        s = Signalement.query.filter_by(code_suivi=code).first()
        if not s or not check_password_hash(s.mot_de_passe_hash, request.form.get('mot_de_passe') or ''):
            flash('Code de suivi ou mot de passe incorrect.', 'danger')
            return render_template('egalyx/alerte_suivi.html', s=None)
        session['alerte_suivi'] = {'id': s.id, 't': time.time()}
        return redirect(url_for('.suivi'))

    s = _signalement_suivi()
    if request.method == 'POST' and request.form.get('action') == 'message':
        if not s:
            return redirect(url_for('.suivi'))
        texte = (request.form.get('message') or '').strip()
        if texte and not s.est_cloture:
            m = MessageSignalement(signalement_id=s.id, auteur='lanceur')
            m.contenu = texte[:10000]
            db.session.add(m)
            db.session.commit()
            for r in _referents(s.client_id):
                envoyer_courriel(r.email, 'Nouveau message sur un signalement — Egalyx Control',
                                 "Le lanceur d'alerte a ajouté un message à un signalement. "
                                 "Consultez-le dans Egalyx Control (Conformité > Alertes).")
            flash('Message transmis au référent.', 'success')
        return redirect(url_for('.suivi'))
    if request.args.get('quitter'):
        session.pop('alerte_suivi', None)
        return redirect(url_for('.suivi'))
    return render_template('egalyx/alerte_suivi.html', s=s)


# =================================================================== référents
def _referent_requis():
    if not est_referent():
        flash("Accès réservé aux référents du dispositif d'alerte (permission « Référent du dispositif d'alerte »).", 'danger')
        return redirect(url_for('dashboard'))
    return None


@bp.route('/')
@client_requis
def liste():
    from models import Signalement, Client
    refus = _referent_requis()
    if refus:
        return refus
    statut = request.args.get('statut') or ''
    q = Signalement.query.filter_by(client_id=current_user.client_id)
    if statut == 'ouverts':
        q = q.filter(Signalement.statut.in_(['recu', 'recevable', 'en_instruction']))
    elif statut:
        q = q.filter_by(statut=statut)
    signalements = q.order_by(Signalement.created_at.desc()).all()
    tous = Signalement.query.filter_by(client_id=current_user.client_id).all()
    maintenant = datetime.utcnow()
    indicateurs = {
        'ouverts': sum(1 for s in tous if not s.est_cloture),
        'accuse_retard': sum(1 for s in tous if not s.date_accuse_reception and s.echeance_accuse < maintenant),
        'retour_retard': sum(1 for s in tous if not s.est_cloture and not s.date_retour_information
                             and s.echeance_retour and s.echeance_retour < maintenant),
        'total': len(tous),
    }
    org = Client.query.get(current_user.client_id)
    lien = url_for('alerte.deposer', reference=org.reference, _external=True) if org else None
    return render_template('egalyx/alertes_liste.html', signalements=signalements, ind=indicateurs,
                           statut=statut, lien_public=lien, maintenant=maintenant, Signalement=Signalement)


def _charger(sid):
    from models import Signalement
    s = Signalement.query.filter_by(id=sid, client_id=current_user.client_id).first()
    if not s:
        abort(404)
    return s


@bp.route('/<int:sid>')
@client_requis
def detail(sid):
    from models import db
    refus = _referent_requis()
    if refus:
        return refus
    s = _charger(sid)
    journaliser('signalement_consulte', {'signalement': s.id})
    db.session.commit()
    return render_template('egalyx/alerte_detail.html', s=s, referents=_referents(s.client_id),
                           maintenant=datetime.utcnow())


@bp.route('/<int:sid>/action', methods=['POST'])
@client_requis
def action(sid):
    from models import db, MessageSignalement
    refus = _referent_requis()
    if refus:
        return refus
    s = _charger(sid)
    a = request.form.get('action')
    texte = (request.form.get('message') or '').strip()

    def message(auteur, contenu, interne=False):
        m = MessageSignalement(signalement_id=s.id, auteur=auteur, interne=interne,
                               referent_id=current_user.id if auteur == 'referent' else None)
        m.contenu = contenu[:10000]
        db.session.add(m)

    if a == 'accuser':
        if not s.date_accuse_reception:
            s.date_accuse_reception = datetime.utcnow()
            message('referent', texte or "Votre signalement a bien été reçu. Il sera examiné par un référent "
                                         "habilité, dans le respect de la confidentialité.")
            if not s.referent_id:
                s.referent_id = current_user.id
    elif a == 'recevabilite':
        if request.form.get('recevable') == '1':
            s.recevable, s.statut = True, 'en_instruction'
            message('referent', texte or 'Votre signalement est recevable et fait l\'objet d\'une instruction.')
        else:
            if not texte:
                flash("Motivez l'irrecevabilité : le lanceur d'alerte doit en être informé.", 'danger')
                return redirect(url_for('.detail', sid=sid))
            s.recevable, s.statut, s.motif_cloture = False, 'irrecevable', texte
            message('referent', texte)
    elif a == 'message' and texte:
        message('referent', texte)
        if s.date_accuse_reception and not s.date_retour_information and request.form.get('retour') == '1':
            s.date_retour_information = datetime.utcnow()
    elif a == 'note' and texte:
        message('referent', texte, interne=True)
    elif a == 'attribuer':
        rid = request.form.get('referent_id', type=int)
        if rid in {r.id for r in _referents(s.client_id)}:
            s.referent_id = rid
    elif a == 'cloturer':
        issue = request.form.get('issue')
        if issue not in ('cloture_fonde', 'cloture_non_fonde') or not texte:
            flash("Indiquez l'issue et la conclusion transmise au lanceur d'alerte.", 'danger')
            return redirect(url_for('.detail', sid=sid))
        s.statut, s.motif_cloture = issue, texte
        if not s.date_retour_information:
            s.date_retour_information = datetime.utcnow()
        message('referent', texte)
    else:
        flash('Action incomplète.', 'warning')
        return redirect(url_for('.detail', sid=sid))
    journaliser('signalement_' + a, {'signalement': s.id})
    db.session.commit()
    flash('Signalement mis à jour.', 'success')
    return redirect(url_for('.detail', sid=sid))


def enregistrer(app, csrf=None):
    app.register_blueprint(bp_public)
    app.register_blueprint(bp)
    app.jinja_env.globals['est_referent_alerte'] = est_referent

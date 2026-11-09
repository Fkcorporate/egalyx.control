"""
egalyx/signature.py — signature électronique interne (validation tracée).

Ce que c'est : une preuve d'approbation à usage interne. Le signataire, authentifié,
confirme par un code à usage unique envoyé sur son adresse e-mail (ou, si l'envoi
d'e-mails n'est pas configuré, en ressaisissant son mot de passe). On enregistre
qui, quand, depuis quelle adresse IP, en quelle qualité, et l'empreinte SHA-256 du
document à cet instant. Toute modification ultérieure du document est détectée.

Ce que ce n'est pas : une signature électronique « avancée » ou « qualifiée » au sens du
règlement eIDAS (pas de certificat individuel ni de prestataire de confiance).
"""
import time

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from werkzeug.security import check_password_hash, generate_password_hash

from egalyx import calculs, courriel
from egalyx.commun import a_permission, adresse_ip, client_id_courant, client_requis, est_admin_client, journaliser

bp = Blueprint('signature', __name__, url_prefix='/signature')

ROLES = {'auteur': 'Auteur', 'valideur': 'Valideur (revue)', 'approbateur': 'Approbateur'}
DUREE_CODE = 600
MAX_ESSAIS = 5


# Champs de suivi qui évoluent normalement après signature (statut, avancement, archivage) :
# ils ne font pas partie du contenu signé.
EXCLUS = {'statut', 'sous_statut', 'pourcentage_realisation', 'pourcentage', 'avancement', 'date_fin_reelle',
          'date_realisation', 'efficacite', 'score_efficacite', 'commentaire_evaluation', 'is_archived',
          'archived_at', 'archived_by', 'archive_reason', 'espace_travail_actif'}


def _colonnes(obj):
    return {c.name: getattr(obj, c.name, None) for c in obj.__table__.columns if c.name not in EXCLUS}


def _enfants(obj, *relations):
    sortie = {}
    for r in relations:
        valeur = getattr(obj, r, None)
        if valeur is None:
            continue
        if hasattr(valeur, 'all') and callable(valeur.all):
            valeur = valeur.all()
        sortie[r] = sorted((_colonnes(e) for e in valeur), key=lambda x: x.get('id') or 0)
    return sortie


def _types():
    from models import Audit, PlanAction
    return {
        'audit': {'modele': Audit, 'libelle': "Rapport d'audit", 'enfants': ('constatations', 'recommandations'),
                  'voir': ('can_manage_audit', 'can_manage_audit_program', 'can_view_reports'),
                  'titre': lambda o: o.titre, 'lien': lambda o: url_for('detail_audit', id=o.id)},
        'plan_action': {'modele': PlanAction, 'libelle': "Plan d'action", 'enfants': ('sous_actions',),
                        'voir': ('can_manage_action_plans', 'can_view_action_plans'),
                        'titre': lambda o: o.nom, 'lien': lambda o: url_for('detail_plan_action', plan_id=o.id)},
    }


def document(type_doc, doc_id):
    """(définition, objet) du document, limité à l'organisation courante ; 404 sinon."""
    d = _types().get(type_doc)
    if not d:
        abort(404)
    if not a_permission(*d['voir']):
        abort(403)
    o = d['modele'].query.filter_by(id=doc_id, client_id=client_id_courant()).first()
    if not o:
        abort(404)
    return d, o


def empreinte_document(d, o):
    contenu = _colonnes(o)
    contenu.update(_enfants(o, *d['enfants']))
    return calculs.empreinte(contenu)


def signatures(type_doc, doc_id, empreinte_actuelle=None):
    from models import SignatureDocument
    lst = (SignatureDocument.query.filter_by(type_document=type_doc, document_id=doc_id)
           .order_by(SignatureDocument.created_at).all())
    for s in lst:
        s.valide = (not s.revoquee) and (empreinte_actuelle is None or s.empreinte == empreinte_actuelle)
    return lst


def resume_signatures(type_doc, doc_id):
    """Pour les pages de détail : {'total', 'valides', 'modifie'} (global Jinja)."""
    try:
        from models import SignatureDocument
        lst = SignatureDocument.query.filter_by(type_document=type_doc, document_id=doc_id, revoquee=False).all()
        if not lst:
            return {'total': 0, 'valides': 0, 'modifie': False}
        d, o = document(type_doc, doc_id)
        e = empreinte_document(d, o)
        valides = sum(1 for s in lst if s.empreinte == e)
        return {'total': len(lst), 'valides': valides, 'modifie': valides < len(lst)}
    except Exception:
        return {'total': 0, 'valides': 0, 'modifie': False}


@bp.route('/<type_doc>/<int:doc_id>')
@client_requis
def page(type_doc, doc_id):
    d, o = document(type_doc, doc_id)
    e = empreinte_document(d, o)
    attente = session.get('signature_attente') or {}
    code_envoye = attente.get('doc') == [type_doc, doc_id] and time.time() - attente.get('t', 0) < DUREE_CODE
    return render_template('egalyx/signature.html', d=d, o=o, type_doc=type_doc, empreinte=e,
                           peut_signer=a_permission('can_sign_documents'),
                           signatures=signatures(type_doc, doc_id, e), ROLES=ROLES,
                           code_envoye=code_envoye, par_email=courriel.est_configure(),
                           deja_signe=any(s.signataire_id == current_user.id and s.valide
                                          for s in signatures(type_doc, doc_id, e)))


@bp.route('/<type_doc>/<int:doc_id>/code', methods=['POST'])
@client_requis
def envoyer_code(type_doc, doc_id):
    d, o = document(type_doc, doc_id)
    if not a_permission('can_sign_documents'):
        abort(403)
    if not courriel.est_configure():
        return redirect(url_for('.page', type_doc=type_doc, doc_id=doc_id))
    code = calculs.code_numerique(6)
    session['signature_attente'] = {'doc': [type_doc, doc_id], 'h': generate_password_hash(code),
                                    'e': empreinte_document(d, o), 't': time.time(), 'n': 0}
    ok = courriel.envoyer(current_user.email, 'Code de signature — Egalyx Control',
                          f"Votre code pour signer « {d['libelle']} {getattr(o, 'reference', '')} » : {code}\n"
                          f"Il expire dans 10 minutes. Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.")
    flash('Code envoyé à ' + current_user.email + '.' if ok else "L'e-mail n'a pas pu être envoyé. Réessayez.",
          'info' if ok else 'danger')
    return redirect(url_for('.page', type_doc=type_doc, doc_id=doc_id))


@bp.route('/<type_doc>/<int:doc_id>/signer', methods=['POST'])
@client_requis
def signer(type_doc, doc_id):
    from models import db, SignatureDocument
    d, o = document(type_doc, doc_id)
    if not a_permission('can_sign_documents'):
        abort(403)
    e = empreinte_document(d, o)
    role = request.form.get('role') if request.form.get('role') in ROLES else 'valideur'
    retour = redirect(url_for('.page', type_doc=type_doc, doc_id=doc_id))
    if courriel.est_configure():
        att = session.get('signature_attente') or {}
        if att.get('doc') != [type_doc, doc_id] or time.time() - att.get('t', 0) > DUREE_CODE:
            flash('Code expiré : demandez-en un nouveau.', 'warning')
            return retour
        if att.get('e') != e:
            session.pop('signature_attente', None)
            flash('Le document a été modifié depuis l\'envoi du code. Relisez-le puis demandez un nouveau code.', 'warning')
            return retour
        if not check_password_hash(att['h'], (request.form.get('code') or '').strip()):
            att['n'] = att.get('n', 0) + 1
            if att['n'] >= MAX_ESSAIS:
                session.pop('signature_attente', None)
                flash('Trop d\'erreurs : demandez un nouveau code.', 'danger')
            else:
                session['signature_attente'] = att
                flash('Code incorrect.', 'danger')
            return retour
        methode = 'code_email'
        session.pop('signature_attente', None)
    else:
        if not current_user.check_password(request.form.get('mot_de_passe') or ''):
            flash('Mot de passe incorrect.', 'danger')
            return retour
        methode = 'mot_de_passe'
    s = SignatureDocument(client_id=o.client_id, type_document=type_doc, document_id=o.id,
                          reference_document=getattr(o, 'reference', None), empreinte=e,
                          signataire_id=current_user.id, role_signataire=role,
                          commentaire=(request.form.get('commentaire') or '').strip()[:2000] or None,
                          methode=methode, adresse_ip=adresse_ip()[:45],
                          navigateur=(request.user_agent.string or '')[:300])
    db.session.add(s)
    journaliser('document_signe', {'type': type_doc, 'document': o.id, 'empreinte': e, 'role': role})
    db.session.commit()
    flash(f'Document signé en qualité de {ROLES[role].lower()}.', 'success')
    return retour


@bp.route('/revoquer/<int:sig_id>', methods=['POST'])
@client_requis
def revoquer(sig_id):
    from models import db, SignatureDocument
    s = SignatureDocument.query.filter_by(id=sig_id, client_id=client_id_courant()).first_or_404()
    if s.signataire_id != current_user.id and not est_admin_client():
        abort(403)
    s.revoquee = True
    journaliser('signature_revoquee', {'signature': s.id})
    db.session.commit()
    flash('Signature révoquée.', 'info')
    return redirect(url_for('.page', type_doc=s.type_document, doc_id=s.document_id))


def enregistrer(app):
    app.register_blueprint(bp)
    app.jinja_env.globals['resume_signatures'] = resume_signatures

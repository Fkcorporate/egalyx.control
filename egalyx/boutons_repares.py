"""
egalyx/boutons_repares.py — boutons qui appelaient une adresse inexistante (« ne fait rien »).

Recensement du 19/11/2026 (outil : appels fetch / liens des gabarits comparés aux adresses de l'application).
Chaque adresse ajoutée ici vérifie l'organisation (cloisonnement) et le droit nécessaire.

  Clés API (administrateur)          détail, régénération, révocation
  Modèles de permissions             « Appliquer à tous les utilisateurs du rôle » (+ liste limitée à l'organisation)
  Incidents                          suppression définitive d'un incident archivé
  KRI archivés                       tout restaurer, nettoyer (> 90 jours), exporter
  KRI (modifier)                     suggestions d'optimisation
  Contrôle N2                        suppression d'un plan d'action N2, export du tableau de bord
  Opérateurs                         réintégrer une anomalie écartée
  Qualité                            générer / vérifier une référence d'action
  Questionnaires                     dupliquer
  Réévaluations                      statistiques et liste (actualisation sans rechargement)
  PCA                                analyse d'un plan en cours de saisie
  Feuille de travail                 actualiser le contexte GRC
  Super admin                        recharger les gabarits, vider le cache, santé du système, export des journaux
  Documentation publique             pages « Guide d'utilisation », « Documentation complète », « API », « Tutoriels »
  Sous-action d'un plan indépendant  page de modification
"""
import csv
import io
import logging
import os
import re
import time
from datetime import datetime, timedelta

from flask import Response, abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import a_permission, client_id_courant, est_admin_client, est_super_admin, journaliser

journal = logging.getLogger('egalyx.boutons_repares')
DEMARRAGE = time.time()


def _m():
    import models as M
    return M


def _json_refus(message='Permission refusée', code=403):
    return jsonify({'success': False, 'error': message}), code


def _de_mon_organisation(obj):
    if obj is None:
        return False
    if est_super_admin():
        return True
    return getattr(obj, 'client_id', None) == getattr(current_user, 'client_id', None)


def _obtenir(modele, ident):
    obj = _m().db.session.get(modele, ident)
    if not _de_mon_organisation(obj):
        abort(404)
    return obj


def _csv(nom, entetes, lignes):
    tampon = io.StringIO()
    tampon.write('﻿')
    w = csv.writer(tampon, delimiter=';')
    w.writerow(entetes)
    for l in lignes:
        w.writerow(['' if v is None else v for v in l])
    return Response(tampon.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{nom}"'})


# ------------------------------------------------------------------ clés API
def _admin_org():
    return est_admin_client() or est_super_admin()


def cle_api_details(key_id):
    if not _admin_org():
        return _json_refus()
    k = _obtenir(_m().ApiKey, key_id)
    return jsonify({'success': True, 'api_key': k.api_key, 'name': k.name, 'total_requests': k.total_requests or 0,
                    'last_request_at': k.last_request_at.strftime('%d/%m/%Y %H:%M') if k.last_request_at else None,
                    'is_active': bool(k.is_active and not k.is_revoked)})


def cle_api_regenerer(key_id):
    if not _admin_org():
        return _json_refus()
    M = _m()
    k = _obtenir(M.ApiKey, key_id)
    if k.is_revoked:
        return _json_refus('Clé révoquée : créez-en une nouvelle.', 400)
    k.generate_keys()
    journaliser('cle_api_regeneree', {'cle': k.name}, client_id=k.client_id)
    M.db.session.commit()
    return jsonify({'success': True, 'api_key': k.api_key, 'api_secret': k.api_secret})


def cle_api_revoquer(key_id):
    if not _admin_org():
        return _json_refus()
    M = _m()
    k = _obtenir(M.ApiKey, key_id)
    k.revoke(current_user.id, (request.get_json(silent=True) or {}).get('raison') or 'Révoquée par un administrateur')
    journaliser('cle_api_revoquee', {'cle': k.name}, client_id=k.client_id)
    M.db.session.commit()
    return jsonify({'success': True})


# ------------------------------------------------------------------ modèles de permissions
def _modeles_visibles():
    M = _m()
    q = M.PermissionTemplate.query
    if not est_super_admin():
        q = q.filter((M.PermissionTemplate.client_id == current_user.client_id) | (M.PermissionTemplate.client_id.is_(None)))
    return q


def modeles_permissions_liste():
    """Remplace la liste : elle montrait les modèles de TOUTES les organisations."""
    return render_template('admin/templates_permissions.html',
                           templates=_modeles_visibles().order_by(_m().PermissionTemplate.name).all())


def modele_permissions_appliquer(id):
    M = _m()
    if not _admin_org():
        return _json_refus()
    t = _modeles_visibles().filter(M.PermissionTemplate.id == id).first()
    if t is None:
        return _json_refus('Modèle introuvable', 404)
    cid = client_id_courant()
    cibles = M.User.query.filter(M.User.client_id == cid, M.User.role == (t.role or 'utilisateur'),
                                 M.User.role.notin_(('admin', 'super_admin'))).all()
    cibles = [u for u in cibles if not getattr(u, 'is_client_admin', False)]
    for u in cibles:
        u.permissions = dict(t.permissions or {})
    journaliser('modele_permissions_applique', {'modele': t.name, 'role': t.role, 'utilisateurs': len(cibles)}, client_id=cid)
    M.db.session.commit()
    return jsonify({'success': True, 'count': len(cibles),
                    'message': f'Modèle appliqué à {len(cibles)} utilisateur(s) du rôle « {t.role} » (administrateurs exclus).'})


# ------------------------------------------------------------------ incidents
def incident_supprimer_definitivement(incident_id):
    M = _m()
    inc = _obtenir(M.Incident, incident_id)
    if not inc.peut_supprimer_definitivement(current_user):
        return _json_refus('Seuls les administrateurs peuvent supprimer définitivement un incident.')
    if not inc.is_archived:
        return _json_refus('Archivez d\'abord l\'incident.', 400)
    ref = inc.reference
    try:
        M.IncidentHistorique.query.filter_by(incident_id=inc.id).delete(synchronize_session=False)
        for modele in ('TicketSupport', 'DispositifHistoriqueEfficacite'):
            if hasattr(M, modele):
                getattr(M, modele).query.filter_by(incident_id=inc.id).update({'incident_id': None}, synchronize_session=False)
        M.db.session.delete(inc)
        journaliser('incident_supprime_definitivement', {'reference': ref}, client_id=inc.client_id)
        M.db.session.commit()
    except Exception as e:  # noqa: BLE001
        M.db.session.rollback()
        journal.warning('Suppression de l\'incident %s impossible : %s', ref, e)
        return _json_refus('Cet incident est encore lié à d\'autres éléments : il reste archivé.', 409)
    return jsonify({'success': True, 'message': f'Incident {ref} supprimé définitivement.'})


# ------------------------------------------------------------------ KRI archivés
def _kri_archives():
    M = _m()
    q = M.KRI.query.filter(M.KRI.est_actif.is_(False))
    if not est_super_admin():
        q = q.filter(M.KRI.client_id == current_user.client_id)
    return q


def kri_restaurer_tous():
    if getattr(current_user, 'role', None) not in ('admin', 'super_admin'):
        return _json_refus()
    M = _m()
    n = 0
    for k in _kri_archives().all():
        k.est_actif, k.archived_at, k.archived_by, k.updated_at = True, None, None, datetime.utcnow()
        n += 1
    journaliser('kri_restaures_tous', {'nombre': n})
    M.db.session.commit()
    return jsonify({'success': True, 'count': n})


def kri_nettoyer_anciens():
    """Supprime définitivement les KRI archivés depuis plus de 90 jours (comme annoncé sur la page)."""
    if getattr(current_user, 'role', None) not in ('admin', 'super_admin'):
        return _json_refus()
    M = _m()
    limite = datetime.utcnow() - timedelta(days=90)
    n, gardes = 0, 0
    for k in _kri_archives().filter(M.KRI.archived_at.isnot(None), M.KRI.archived_at < limite).all():
        try:
            with M.db.session.begin_nested():
                M.MesureKRI.query.filter_by(kri_id=k.id).delete(synchronize_session=False)
                M.db.session.delete(k)
            n += 1
        except Exception:  # noqa: BLE001
            gardes += 1
    journaliser('kri_nettoyage', {'supprimes': n, 'gardes': gardes})
    M.db.session.commit()
    return jsonify({'success': True, 'count': n, 'gardes': gardes})


def kri_archives_export():
    if not current_user.is_authenticated:
        abort(401)
    kris = _kri_archives().order_by(_m().KRI.archived_at.desc()).all()
    return _csv(f'kri_archives_{datetime.utcnow():%Y%m%d}.csv', ['Code', 'Nom', 'Unité', 'Seuil alerte', 'Seuil critique', 'Archivé le'],
                [(getattr(k, 'code', '') or '', k.nom, getattr(k, 'unite_mesure', ''), getattr(k, 'seuil_alerte', ''),
                  getattr(k, 'seuil_critique', ''), k.archived_at.strftime('%d/%m/%Y') if k.archived_at else '') for k in kris])


def kri_optimiser(kri_id):
    """Suggestions d'optimisation : celles du risque du KRI (même service que la création d'un KRI)."""
    M = _m()
    k = _obtenir(M.KRI, kri_id)
    risque_id = request.args.get('risque_id', type=int) or getattr(k, 'risque_id', None)
    if not risque_id:
        return jsonify({'success': False, 'error': 'Associez d\'abord ce KRI à un risque.'}), 400
    vue = current_app.view_functions.get('generer_kris_ia') or current_app.view_functions.get('suggestions_kris_fallback')
    if vue is None:
        return jsonify({'success': False, 'error': 'Service de suggestions indisponible.'}), 503
    return vue(risque_id=risque_id)


# ------------------------------------------------------------------ contrôle N2
def _droit_n2():
    return est_super_admin() or a_permission('can_manage_controle_interne_n2')


def c2n_plan_supprimer(plan_id):
    M = _m()
    p = _obtenir(M.PlanActionC2N, plan_id)
    if not _droit_n2():
        return _json_refus()
    ref = p.reference
    try:
        with M.db.session.begin_nested():
            sa_ids = [s.id for s in M.SousActionPlanC2N.query.filter_by(plan_action_id=p.id).all()] \
                if hasattr(M.SousActionPlanC2N, 'plan_action_id') else []
            if sa_ids and hasattr(M, 'CommentaireSousActionC2N'):
                M.CommentaireSousActionC2N.query.filter(M.CommentaireSousActionC2N.sous_action_id.in_(sa_ids)).delete(synchronize_session=False)
            if sa_ids:
                M.SousActionPlanC2N.query.filter(M.SousActionPlanC2N.id.in_(sa_ids)).delete(synchronize_session=False)
            if hasattr(M, 'CommentairePlanActionC2N'):
                M.CommentairePlanActionC2N.query.filter_by(plan_action_id=p.id).delete(synchronize_session=False)
            M.RecommandationC2N.query.filter_by(plan_action_id=p.id).update({'plan_action_id': None}, synchronize_session=False)
            M.db.session.delete(p)
        journaliser('plan_action_n2_supprime', {'reference': ref})
        M.db.session.commit()
    except Exception as e:  # noqa: BLE001
        M.db.session.rollback()
        journal.warning('Suppression du plan N2 %s impossible : %s', ref, e)
        return _json_refus('Ce plan est encore lié à d\'autres éléments : archivez-le plutôt.', 409)
    return jsonify({'success': True, 'message': f'Plan {ref} supprimé.'})


def c2n_dashboard_export():
    M = _m()
    if not (est_super_admin() or a_permission('can_manage_controle_interne_n2', 'can_view_controle_interne_n2')):
        abort(403)
    q = M.PlanificationControle.query
    if not est_super_admin():
        q = q.filter(M.PlanificationControle.client_id == current_user.client_id)
    annee = request.args.get('annee', type=int)
    if annee:
        q = q.filter(M.PlanificationControle.annee == annee)
    statut = request.args.get('statut')
    if statut:
        q = q.filter(M.PlanificationControle.statut == statut)
    lignes = []
    for p in q.order_by(M.PlanificationControle.date_prevue.desc()).limit(5000).all():
        ref = getattr(p, 'referentiel', None)
        ctrl = getattr(p, 'controleur', None)
        lignes.append((p.reference, getattr(ref, 'code_controle', ''), getattr(ref, 'nom', ''), p.annee,
                       p.date_prevue.strftime('%d/%m/%Y') if p.date_prevue else '', p.statut,
                       (getattr(ctrl, 'nom_affiche', None) or getattr(ctrl, 'username', '')) if ctrl else ''))
    return _csv(f'controle_n2_{datetime.utcnow():%Y%m%d}.csv',
                ['Référence', 'Code contrôle', 'Contrôle', 'Année', 'Date prévue', 'Statut', 'Contrôleur'], lignes)


# ------------------------------------------------------------------ opérateurs
def operateur_reintegrer_anomalie(anomalie_id):
    M = _m()
    if not getattr(current_user, 'is_operateur', False):
        return _json_refus('Accès non autorisé')
    a = M.AnomalieDetectee.query.filter_by(id=anomalie_id, client_id=current_user.client_id).first()
    if a is None:
        abort(404)
    if not a.campagne.peut_etre_modifiee_par(current_user):
        return _json_refus('Non autorisé')
    if a.statut != 'ecartee':
        return _json_refus('Seule une anomalie écartée peut être réintégrée.', 400)
    if hasattr(a, 'reinitialiser'):
        ok, msg = a.reinitialiser()
        if not ok:
            return _json_refus(msg, 400)
    else:
        a.statut = 'a_traiter'
    M.db.session.commit()
    return jsonify({'success': True, 'message': 'Anomalie réintégrée.'})


# ------------------------------------------------------------------ qualité
def _plan_qualite(plan_id):
    return _obtenir(_m().PlanQualiteFonction, plan_id)


def qualite_generer_reference(plan_id):
    M = _m()
    plan = _plan_qualite(plan_id)
    prises = {r for (r,) in M.db.session.query(M.ActionAmeliorationQualite.reference)
              .filter(M.ActionAmeliorationQualite.client_id == plan.client_id).all()}
    n = M.ActionAmeliorationQualite.query.filter_by(plan_qualite_id=plan.id).count() + 1
    while f'AQ-{plan.reference}-{n:03d}' in prises:
        n += 1
    return jsonify({'success': True, 'reference': f'AQ-{plan.reference}-{n:03d}'})


def qualite_verifier_reference(plan_id):
    M = _m()
    plan = _plan_qualite(plan_id)
    ref = (request.args.get('reference') or '').strip()
    q = M.ActionAmeliorationQualite.query.filter_by(client_id=plan.client_id, reference=ref)
    exclure = request.args.get('action_id', type=int)
    if exclure:
        q = q.filter(M.ActionAmeliorationQualite.id != exclure)
    return jsonify({'success': True, 'exists': bool(ref) and q.first() is not None})


# ------------------------------------------------------------------ questionnaires
def questionnaire_dupliquer(id):
    M = _m()
    src = _obtenir(M.Questionnaire, id)
    if not (est_super_admin() or est_admin_client() or a_permission('can_manage_questionnaires', 'can_manage_audit')
            or src.created_by == current_user.id):
        return _json_refus()
    cols = [c.key for c in M.Questionnaire.__mapper__.column_attrs if c.key not in ('id', 'code', 'date_creation', 'date_modification')]
    copie = M.Questionnaire(**{c: getattr(src, c) for c in cols})
    copie.titre = (src.titre + ' (copie)')[:200]
    base = re.sub(r'-COPIE\d*$', '', src.code or 'Q')[:40]
    n = 1
    while M.Questionnaire.query.filter_by(code=f'{base}-COPIE{n}').first():
        n += 1
    copie.code, copie.est_actif, copie.created_by = f'{base}-COPIE{n}', False, current_user.id
    M.db.session.add(copie)
    M.db.session.flush()
    correspondance = {}
    for cat in sorted(src.categories, key=lambda x: x.ordre or 0):
        nc = M.QuestionnaireCategorie(questionnaire_id=copie.id, titre=cat.titre, description=cat.description,
                                      client_id=cat.client_id, ordre=cat.ordre)
        M.db.session.add(nc); M.db.session.flush()
        for q in cat.questions:
            qcols = [c.key for c in M.Question.__mapper__.column_attrs if c.key not in ('id', 'categorie_id')]
            nq = M.Question(categorie_id=nc.id, **{c: getattr(q, c) for c in qcols})
            M.db.session.add(nq); M.db.session.flush()
            correspondance[q.id] = nq.id
            for o in q.options:
                ocols = [c.key for c in M.OptionQuestion.__mapper__.column_attrs if c.key not in ('id', 'question_id')]
                M.db.session.add(M.OptionQuestion(question_id=nq.id, **{c: getattr(o, c) for c in ocols}))
    if hasattr(M, 'ConditionQuestion') and correspondance:
        for cnd in M.ConditionQuestion.query.filter(M.ConditionQuestion.question_id.in_(list(correspondance))).all():
            if cnd.question_parent_id in correspondance:
                M.db.session.add(M.ConditionQuestion(question_id=correspondance[cnd.question_id],
                                                     question_parent_id=correspondance[cnd.question_parent_id],
                                                     operateur=cnd.operateur, valeur=cnd.valeur))
    M.db.session.commit()
    return jsonify({'success': True, 'id': copie.id, 'message': f'Questionnaire dupliqué (inactif) : {copie.titre}'})


# ------------------------------------------------------------------ réévaluations
def _demandes():
    M = _m()
    if not a_permission('can_manage_risks') and not est_super_admin():
        abort(403)
    q = M.DemandeReevaluation.query.filter_by(client_id=client_id_courant())
    statut, recherche = request.args.get('statut', ''), (request.args.get('recherche') or '').strip()
    if statut:
        q = q.filter_by(statut=statut)
    if recherche:
        motif = f'%{recherche}%'
        q = q.filter(M.DemandeReevaluation.titre.ilike(motif) | M.DemandeReevaluation.reference.ilike(motif)
                     | M.DemandeReevaluation.justification.ilike(motif))
    return q


def reevaluations_stats():
    q = _demandes()
    traitees = [d for d in q.filter(_m().DemandeReevaluation.statut.in_(('validee', 'rejetee'))).all() if d.date_validation and d.date_demande]
    moy = round(sum((d.date_validation - d.date_demande).total_seconds() / 3600 for d in traitees) / len(traitees), 1) if traitees else 0
    compte = lambda s: q.filter_by(statut=s).count()  # noqa: E731
    return jsonify({'success': True, 'stats': {'total': q.count(), 'en_attente': compte('en_attente'), 'validees': compte('validee'),
                                               'rejetees': compte('rejetee'), 'annulees': compte('annulee'), 'temps_moyen': moy}})


def reevaluations_liste():
    M = _m()
    peut = getattr(current_user, 'role', None) in ('admin', 'responsable_risques', 'manager')
    out = []
    for d in _demandes().order_by(M.DemandeReevaluation.date_demande.desc()).limit(500).all():
        out.append({'id': d.id, 'reference': d.reference, 'titre': d.titre or '', 'statut': d.statut,
                    'statut_label': d.get_statut_label() if hasattr(d, 'get_statut_label') else d.statut,
                    'statut_css': d.get_statut_css() if hasattr(d, 'get_statut_css') else 'secondary',
                    'risque_reference': d.risque.reference if getattr(d, 'risque', None) else 'N/A',
                    'impact_propose': d.impact_propose, 'probabilite_propose': d.probabilite_propose,
                    'niveau_maitrise_propose': d.niveau_maitrise_propose,
                    'demandeur': d.demandeur.username if getattr(d, 'demandeur', None) else 'N/A',
                    'date_demande': d.date_demande.strftime('%d/%m/%Y %H:%M') if d.date_demande else '',
                    'peut_valider': peut and d.statut == 'en_attente'})
    return jsonify({'success': True, 'demandes': out})


# ------------------------------------------------------------------ PCA, feuille de travail
def pca_analyser_saisie():
    d = (request.get_json(silent=True) or {}).get('plan_data') or {}
    try:
        from services.ia_pca_service import IAPcaService
        return jsonify({'success': True, 'analyse': IAPcaService.analyser_plan_complet(d)})
    except Exception as e:  # noqa: BLE001
        journal.warning('Analyse PCA impossible : %s', e)
        return jsonify({'success': False, 'error': 'Analyse indisponible pour le moment.'}), 503


def feuille_contexte_grc(feuille_id):
    """Le contexte GRC (risques, contrôles, KRI) est recalculé à l'affichage : on vérifie l'accès et on recharge."""
    _obtenir(_m().FeuilleTravail, feuille_id)
    return jsonify({'success': True})


# ------------------------------------------------------------------ super admin
def _super():
    if not est_super_admin():
        abort(404)


def systeme_recharger_gabarits():
    _super()
    current_app.jinja_env.cache.clear() if current_app.jinja_env.cache is not None else None
    return jsonify({'success': True})


def systeme_vider_cache():
    _super()
    vides = 0
    try:
        from egalyx import cache as _cache  # module de cache éventuel
        if hasattr(_cache, 'vider'):
            _cache.vider(); vides += 1
    except Exception:  # noqa: BLE001
        pass
    if current_app.jinja_env.cache is not None:
        current_app.jinja_env.cache.clear(); vides += 1
    return jsonify({'success': True, 'vides': vides})


def systeme_sante():
    _super()
    M = _m()
    try:
        M.db.session.execute(M.db.text('SELECT 1'))
        base = True
    except Exception:  # noqa: BLE001
        base = False
    try:
        dossier = current_app.instance_path
        os.makedirs(dossier, exist_ok=True)
        p = os.path.join(dossier, '.sante')
        with open(p, 'w') as f:
            f.write('ok')
        os.remove(p)
        fichiers = True
    except OSError:
        fichiers = False
    s = int(time.time() - DEMARRAGE)
    return jsonify({'database': base, 'cache': True, 'filesystem': fichiers,
                    'uptime': f'{s // 86400} j {s % 86400 // 3600} h {s % 3600 // 60} min'})


def systeme_export_journaux():
    _super()
    M = _m()
    lignes = M.SystemLog.query.order_by(M.SystemLog.created_at.desc()).limit(10000).all()
    return _csv(f'journaux_systeme_{datetime.utcnow():%Y%m%d}.csv', ['Date (UTC)', 'Niveau', 'Module', 'Message', 'Organisation', 'IP'],
                [(l.created_at.strftime('%d/%m/%Y %H:%M:%S') if l.created_at else '', l.level, l.module, l.message, l.client_id, l.ip_address)
                 for l in lignes])


# ------------------------------------------------------------------ documentation publique, sous-action indépendante
def docs_page(page):
    gabarits = {'guide-utilisation': 'docs/guide-utilisation.html', 'completes': 'docs/completes.html'}
    if page in gabarits:
        return render_template(gabarits[page])
    if page == 'api':
        return redirect(url_for('api_doc.page') if 'api_doc.page' in current_app.view_functions else '/docs')
    if page == 'tutoriels':
        return redirect(url_for('aide.accueil') if 'aide.accueil' in current_app.view_functions else '/docs')
    abort(404)


def sous_action_independant_modifier(sous_action_id):
    """Même formulaire que pour les autres plans ; après enregistrement, retour à la fiche du plan indépendant
    (aiguillage egalyx/plans_nature.py)."""
    vue = current_app.view_functions.get('modifier_sous_action_risque')
    if vue is None:
        abort(404)
    return vue(sous_action_id=sous_action_id)


ROUTES = [
    ('/admin/api-keys/<int:key_id>/details', 'egalyx_cle_api_details', cle_api_details, ['GET']),
    ('/admin/api-keys/<int:key_id>/regenerer', 'egalyx_cle_api_regenerer', cle_api_regenerer, ['POST']),
    ('/admin/api-keys/<int:key_id>/revoke', 'egalyx_cle_api_revoquer', cle_api_revoquer, ['POST']),
    ('/admin/template/<int:id>/appliquer', 'egalyx_modele_permissions_appliquer', modele_permissions_appliquer, ['POST']),
    ('/api/incident/<int:incident_id>/supprimer-definitivement', 'egalyx_incident_supprimer_definitivement', incident_supprimer_definitivement, ['DELETE', 'POST']),
    ('/kri/restaurer-tous', 'egalyx_kri_restaurer_tous', kri_restaurer_tous, ['POST']),
    ('/kri/nettoyer-anciens', 'egalyx_kri_nettoyer_anciens', kri_nettoyer_anciens, ['POST']),
    ('/api/kris/archives/export', 'egalyx_kri_archives_export', kri_archives_export, ['GET']),
    ('/api/kri/<int:kri_id>/optimiser-ia', 'egalyx_kri_optimiser', kri_optimiser, ['GET', 'POST']),
    ('/c2n/plan-action/<int:plan_id>/supprimer', 'egalyx_c2n_plan_supprimer', c2n_plan_supprimer, ['DELETE', 'POST']),
    ('/c2n/dashboard/export', 'egalyx_c2n_dashboard_export', c2n_dashboard_export, ['GET']),
    ('/operateur/anomalie/<int:anomalie_id>/reintegrer', 'operateur_reintegrer_anomalie', operateur_reintegrer_anomalie, ['POST']),
    ('/api/qualite/generer-reference-action/<int:plan_id>', 'egalyx_qualite_generer_reference', qualite_generer_reference, ['POST']),
    ('/api/qualite/verifier-reference-action/<int:plan_id>', 'egalyx_qualite_verifier_reference', qualite_verifier_reference, ['GET']),
    ('/questionnaires/<int:id>/dupliquer', 'egalyx_questionnaire_dupliquer', questionnaire_dupliquer, ['POST']),
    ('/api/demandes-reevaluation/stats', 'egalyx_reevaluations_stats', reevaluations_stats, ['GET']),
    ('/api/demandes-reevaluation/liste', 'egalyx_reevaluations_liste', reevaluations_liste, ['GET']),
    ('/api/pca/analyser-plan-complet', 'egalyx_pca_analyser_saisie', pca_analyser_saisie, ['POST']),
    ('/api/feuille-travail/<int:feuille_id>/contexte-grc', 'egalyx_feuille_contexte_grc', feuille_contexte_grc, ['GET']),
    ('/api/system/reload-templates', 'egalyx_systeme_recharger_gabarits', systeme_recharger_gabarits, ['POST']),
    ('/api/system/clear-cache', 'egalyx_systeme_vider_cache', systeme_vider_cache, ['POST']),
    ('/api/system/health', 'egalyx_systeme_sante', systeme_sante, ['GET']),
    ('/api/system/export-logs', 'egalyx_systeme_export_journaux', systeme_export_journaux, ['GET']),
    ('/sous-action-independant/<int:sous_action_id>/modifier', 'egalyx_sous_action_independant_modifier', sous_action_independant_modifier, ['GET', 'POST']),
]
PUBLIQUES = [('/docs/<page>', 'egalyx_docs_page', docs_page, ['GET'])]


def enregistrer(app):
    for regle, endpoint, vue, methodes in ROUTES:
        if endpoint not in app.view_functions:
            app.add_url_rule(regle, endpoint, login_required(vue), methods=methodes)
    for regle, endpoint, vue, methodes in PUBLIQUES:
        if endpoint not in app.view_functions:
            app.add_url_rule(regle, endpoint, vue, methods=methodes)
    if 'admin_templates_permissions' in app.view_functions:
        app.view_functions['admin_templates_permissions'] = login_required(modeles_permissions_liste)

"""
egalyx/pca.py — refonte du module « Plans de continuité d'activité » (PCA).

1. Droits cohérents sur tout le module (une seule grille, appliquée avant chaque page) :
   voir = « Voir », « Tester » ou « Gérer les PCA » ; tester (exercices, résultats) = « Tester » ou « Gérer » ;
   gérer (plans, actions, documents, liens) = « Gérer les PCA ». Le responsable d'une action peut la mettre à jour.
   Avant : la plupart des pages demandaient « Gérer les audits », le tableau de bord et le stress test étaient
   ouverts à tous, et la personne nommée valideur pouvait modifier tout le plan.
2. Circuit de validation : en rédaction → en relecture (soumis) → validé par le valideur désigné (ou, sans valideur,
   par un gestionnaire des PCA ; EGALYX_PCA_DOUBLE_REGARD=1 interdit de valider ce qu'on a soumis).
   Le statut « Validé » ne peut plus être choisi dans le formulaire. Modifier un plan validé le repasse en rédaction.
   À la validation : version +0.1 et date de fin de validité à un an si elle n'est pas renseignée.
3. Exercices : saisie du résultat (réalisé / reporté / annulé, durée réelle de reprise, note, points forts, axes
   d'amélioration). Un exercice réalisé met à jour les dates du dernier et du prochain test ; chaque axe peut devenir
   une action du PCA. La durée de reprise est comparée au RTO.
4. RTO / RPO : le texte (« 4 h », « 2 jours », « 30 min ») est converti en heures pour pouvoir comparer.
5. Activations réelles du PCA (incident majeur…) avec durée constatée comparée au RTO.
6. Liens avec la cartographie (risques) et les processus métier ; documents joints.
7. Alertes : plan expiré ou bientôt expiré, test en retard, plan à valider, actions confiées (« Ma semaine »).
"""
import os
import re
import uuid
from datetime import date, datetime, timedelta

from flask import (Blueprint, abort, current_app, flash, g, has_request_context, redirect, render_template, request,
                   send_file, url_for)
from flask_login import current_user, login_required

from egalyx.commun import a_permission, entier, est_admin_client, journaliser

bp = Blueprint('pca', __name__, url_prefix='/pca-suivi')

VOIR = ('can_view_bcp', 'can_test_bcp', 'can_manage_bcp')
TESTER = ('can_test_bcp', 'can_manage_bcp')
GERER = ('can_manage_bcp',)
STATUTS = {'en_redaction': 'En rédaction', 'en_relecture': 'En relecture', 'valide': 'Validé',
           'obsolète': 'Obsolète', 'archive': 'Archivé'}
MOIS_PERIODICITE = {'mensuelle': 1, 'trimestrielle': 3, 'semestrielle': 6, 'annuelle': 12, 'biennale': 24}
CHAMPS_CONTENU = ('titre', 'description', 'processus_critiques', 'delai_arret_max', 'perte_donnees_max', 'strategies',
                  'sites_secours', 'procedures_urgence', 'procedures_reprise', 'procedures_retour_normal',
                  'ressources_critiques', 'duree_critique', 'bia_realisee', 'pole_id', 'direction_id', 'service_id')
EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'txt', 'csv', 'png', 'jpg', 'jpeg', 'zip'}
TAILLE_MAX = 20 * 1024 * 1024

# Pages existantes : niveau de droit exigé. Une page /pca non listée : lecture = voir, écriture = gérer.
DROITS = {
    'liste_plans_pca': 'voir', 'detail_plan_pca': 'plan', 'tableau_bord_pca': 'voir', 'export_plan_pca_pdf': 'voir',
    'pca_stress_test_dedie': 'voir', 'pca_stress_test_modal': 'voir', 'pca_stress_test_analyse': 'voir',
    'pca_stress_test_ajax': 'voir', 'api_analyser_plan_pca': 'voir',
    'api_pca_suggestions_actions': 'gerer', 'api_pca_suggestions_exercices': 'tester',
    'nouveau_plan_pca': 'gerer', 'modifier_plan_pca': 'gerer', 'archiver_plan_pca': 'gerer', 'restaurer_plan_pca': 'gerer',
    'nouvelle_action_pca': 'gerer', 'supprimer_action_pca': 'gerer', 'api_suggerer_action_pca': 'gerer',
    'modifier_action_pca': 'action',
    'nouvel_exercice_pca': 'tester', 'modifier_exercice_pca': 'tester', 'supprimer_exercice_pca': 'gerer',
    'api_suggerer_exercice_pca': 'tester',
}
NIVEAUX = {'voir': VOIR, 'tester': TESTER, 'gerer': GERER}


def _m():
    import models
    return models


# ---------------------------------------------------------------- droits
def peut(niveau, u=None):
    return a_permission(*NIVEAUX[niveau], u=u or current_user)


def droit(endpoint=None):
    """Utilisé par les pages d'app.py à la place de l'ancien contrôle « Gérer les audits »."""
    endpoint = endpoint or (request.endpoint if has_request_context() else None)
    niveau = DROITS.get(endpoint) or ('voir' if request.method in ('GET', 'HEAD') else 'gerer')
    if niveau == 'action':
        return peut('gerer') or _responsable_action()
    if niveau == 'plan':          # la fiche : droit « Voir », ou valideur / responsable de ce plan
        return peut('voir') or _nomme_sur_le_plan()
    return peut(niveau)


def _nomme_sur_le_plan():
    m = _m()
    pid = (request.view_args or {}).get('plan_id')
    p = m.db.session.get(m.PlanContinuiteActivite, pid) if pid else None
    uid = getattr(current_user, 'id', None)
    return bool(p and p.client_id == current_user.client_id and uid in (p.valideur_id, p.responsable_id))


def _responsable_action():
    m = _m()
    aid = (request.view_args or {}).get('action_id')
    a = m.db.session.get(m.ActionPCA, aid) if aid else None
    return bool(a and a.responsable_id == getattr(current_user, 'id', None) and a.client_id == current_user.client_id)


def _garde():
    """Avant chaque page du module PCA : même grille de droits partout."""
    ep = request.endpoint or ''
    if not (request.path.startswith('/pca') or request.path.startswith('/api/pca')) or ep.startswith('pca.'):
        return None
    if not getattr(current_user, 'is_authenticated', False) or getattr(current_user, 'role', None) == 'super_admin':
        return None
    if droit(ep):
        return None
    if request.path.startswith('/api/') or request.is_json:
        from flask import jsonify
        return jsonify({'success': False, 'error': 'permission_insuffisante'}), 403
    flash("Vous n'avez pas la permission nécessaire pour cette page des plans de continuité.", 'warning')
    return redirect(url_for('liste_plans_pca') if peut('voir') and ep != 'liste_plans_pca' else url_for('dashboard'))


def charger_plan(plan_id):
    m = _m()
    p = m.db.session.get(m.PlanContinuiteActivite, plan_id)
    if p is None or (getattr(current_user, 'role', None) != 'super_admin' and p.client_id != current_user.client_id):
        abort(404)
    return p


def _utilisateur(uid):
    m = _m()
    return m.db.session.get(m.User, uid) if uid else None


def peut_valider(p, u=None):
    u = u or current_user
    if (p.statut or '') != 'en_relecture':
        return False
    if p.valideur_id:
        return p.valideur_id == u.id
    if not (peut('gerer', u) or est_admin_client(u)):
        return False
    if os.environ.get('EGALYX_PCA_DOUBLE_REGARD') == '1' and p.soumis_par_id == u.id:
        return False
    return True


# ---------------------------------------------------------------- outils
def heures(texte):
    """« 4h », « 4 heures », « 2 jours », « 30 min », « 1 semaine », « 0,5 j » → heures (None si illisible)."""
    if texte is None:
        return None
    t = str(texte).strip().lower().replace(',', '.')
    if not t:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)\s*([a-zéû]*)', t)
    if not m:
        return None
    n, unite = float(m.group(1)), m.group(2)
    if unite.startswith(('min', 'mn')):
        return round(n / 60.0, 2)
    if unite.startswith(('j', 'd')):
        return n * 24
    if unite.startswith(('sem', 'w')):
        return n * 24 * 7
    if unite.startswith('mois'):
        return n * 24 * 30
    return n                        # « h », « heure(s) » ou nombre seul : heures


def _plus_mois(d, n):
    a, mo = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
    import calendar
    return date(a, mo, min(d.day, calendar.monthrange(a, mo)[1]))


def mois_periodicite(p):
    return MOIS_PERIODICITE.get((p.periodicite_test or 'annuelle').strip().lower(), 12)


def _lignes(texte):
    return [x.strip(' -•\t') for x in (texte or '').splitlines() if x.strip(' -•\t')]


def _notifier(ids, titre, message, p, type_='pca'):
    m = _m()
    for uid in {i for i in ids if i and i != getattr(current_user, 'id', None)}:
        m.db.session.add(m.Notification(destinataire_id=uid, type_notification=type_, titre=titre[:200], message=message,
                                        entite_type='pca', entite_id=p.id, client_id=p.client_id))


def _gestionnaires(cid):
    m = _m()
    return [u.id for u in m.User.query.filter_by(client_id=cid, is_active=True).all()
            if a_permission(*GERER, u=u) or est_admin_client(u)]


def _version_suivante(v):
    try:
        maj, _, mineur = str(v or '1.0').partition('.')
        return f"{int(maj)}.{int(mineur or 0) + 1}"
    except ValueError:
        return '1.1'


# ---------------------------------------------------------------- informations pour la fiche
def alertes(p, aujourd_hui=None):
    a = []
    j = aujourd_hui or date.today()
    if p.statut == 'valide' and p.date_validite:
        if p.date_validite < j:
            a.append(('danger', f"Plan expiré depuis le {p.date_validite.strftime('%d/%m/%Y')} : à revoir et revalider."))
        elif p.date_validite <= j + timedelta(days=60):
            a.append(('warning', f"Fin de validité le {p.date_validite.strftime('%d/%m/%Y')}."))
    if p.date_prochain_test and p.date_prochain_test < j:
        a.append(('danger', f"Test en retard : prévu le {p.date_prochain_test.strftime('%d/%m/%Y')}."))
    if not p.date_dernier_test:
        a.append(('warning', "Ce plan n'a jamais été testé."))
    if not p.bia_realisee:
        a.append(('secondary', "Analyse d'impact (BIA) non réalisée."))
    if p.delai_arret_max and p.rto_heures is None:
        a.append(('secondary', f"RTO « {p.delai_arret_max} » illisible : écrivez par exemple « 4 h » ou « 2 jours »."))
    if p.statut == 'en_redaction' and p.motif_renvoi:
        a.append(('warning', f"Renvoyé en rédaction : {p.motif_renvoi}"))
    return a


def suivi(p):
    """Tout ce que la barre de suivi de la fiche affiche."""
    m = _m()
    cid = p.client_id
    risques = m.Risque.query.filter(m.Risque.id.in_(p.risque_ids or [-1]), m.Risque.client_id == cid).all()
    processus = m.ProcessusMetier.query.filter(m.ProcessusMetier.id.in_(p.processus_ids or [-1]),
                                                m.ProcessusMetier.client_id == cid).all()
    exercices = m.ExercicePCA.query.filter_by(plan_id=p.id).order_by(m.ExercicePCA.date_exercice.desc()).all()
    activations = m.ActivationPCA.query.filter_by(plan_id=p.id).order_by(m.ActivationPCA.debut.desc()).all()
    documents = m.DocumentPCA.query.filter_by(plan_id=p.id).order_by(m.DocumentPCA.uploaded_at.desc()).all()
    gerer = peut('gerer')
    choix = {}
    if gerer:
        choix['risques'] = m.Risque.query.filter_by(client_id=cid, is_archived=False).order_by(m.Risque.reference).all()
        choix['processus'] = m.ProcessusMetier.query.filter_by(client_id=cid).order_by(m.ProcessusMetier.nom).all()
        choix['incidents'] = m.Incident.query.filter_by(client_id=cid).order_by(m.Incident.id.desc()).limit(50).all()
    en_cours = next((x for x in activations if not x.fin), None)
    derniers = [e for e in exercices if e.statut == 'realise' and e.duree_reprise_heures is not None]
    return {
        'statut': p.statut or 'en_redaction', 'libelle': STATUTS.get(p.statut or 'en_redaction', p.statut),
        'valideur': _utilisateur(p.valideur_id), 'soumis_par': _utilisateur(p.soumis_par_id),
        'valide_par': _utilisateur(p.valide_par_id), 'alertes': alertes(p),
        'gerer': gerer, 'tester': peut('tester'), 'peut_valider': peut_valider(p),
        'peut_activer': gerer or p.responsable_id == current_user.id,
        'risques': risques, 'processus': processus, 'exercices': exercices, 'activations': activations,
        'activation_en_cours': en_cours, 'documents': documents, 'choix': choix,
        'rto': p.rto_heures, 'rpo': p.rpo_heures,
        'dernier_resultat': derniers[0] if derniers else None,
    }


# ---------------------------------------------------------------- circuit de validation
def _circuit():
    g.egalyx_pca_circuit = True


@bp.route('/<int:plan_id>/soumettre', methods=['POST'])
@login_required
def soumettre(plan_id):
    p = charger_plan(plan_id)
    if not peut('gerer'):
        abort(403)
    if p.statut not in ('en_redaction', None, ''):
        flash('Seul un plan en rédaction peut être soumis.', 'warning')
        return redirect(url_for('detail_plan_pca', plan_id=p.id))
    manque = [n for n, ok in (('responsable', p.responsable_id), ('processus critiques', p.processus_critiques),
                              ('RTO', p.delai_arret_max), ("procédures d'urgence", p.procedures_urgence)) if not ok]
    if manque:
        flash('Avant de soumettre, complétez : ' + ', '.join(manque) + '.', 'warning')
        return redirect(url_for('detail_plan_pca', plan_id=p.id))
    _circuit()
    p.statut, p.soumis_le, p.soumis_par_id, p.motif_renvoi = 'en_relecture', datetime.utcnow(), current_user.id, None
    dest = [p.valideur_id] if p.valideur_id else _gestionnaires(p.client_id)
    _notifier(dest, f'PCA à valider : {p.reference}', f'{current_user.username} soumet le plan « {p.titre} » à validation.',
              p, 'pca_a_valider')
    journaliser('pca_soumis', {'plan_id': p.id})
    _m().db.session.commit()
    flash('Plan soumis à validation.', 'success')
    return redirect(url_for('detail_plan_pca', plan_id=p.id))


@bp.route('/<int:plan_id>/valider', methods=['POST'])
@login_required
def valider(plan_id):
    p = charger_plan(plan_id)
    if not peut_valider(p):
        flash("Vous ne pouvez pas valider ce plan (seul le valideur désigné le peut).", 'warning')
        return redirect(url_for('detail_plan_pca', plan_id=p.id))
    _circuit()
    deja_valide = p.valide_le is not None
    p.statut, p.valide_le, p.valide_par_id, p.motif_renvoi = 'valide', datetime.utcnow(), current_user.id, None
    if deja_valide:
        p.version = _version_suivante(p.version)
    if not p.date_validite or p.date_validite < date.today():
        p.date_validite = _plus_mois(date.today(), 12)
    _notifier([p.soumis_par_id, p.responsable_id, p.redacteur_id], f'PCA validé : {p.reference}',
              f'{current_user.username} a validé le plan « {p.titre} » (version {p.version}).', p, 'pca_valide')
    journaliser('pca_valide', {'plan_id': p.id, 'version': p.version,
                               'auto_validation': p.soumis_par_id == current_user.id})
    _m().db.session.commit()
    flash(f'Plan validé (version {p.version}), valable jusqu\'au {p.date_validite.strftime("%d/%m/%Y")}.', 'success')
    return redirect(url_for('detail_plan_pca', plan_id=p.id))


@bp.route('/<int:plan_id>/renvoyer', methods=['POST'])
@login_required
def renvoyer(plan_id):
    p = charger_plan(plan_id)
    if not peut_valider(p):
        abort(403)
    motif = (request.form.get('motif') or '').strip()
    if not motif:
        flash('Indiquez ce qu\'il faut revoir.', 'warning')
        return redirect(url_for('detail_plan_pca', plan_id=p.id))
    _circuit()
    p.statut, p.motif_renvoi = 'en_redaction', motif
    _notifier([p.soumis_par_id, p.redacteur_id, p.responsable_id], f'PCA à revoir : {p.reference}',
              f'{current_user.username} renvoie le plan « {p.titre} » : {motif}', p, 'pca_a_revoir')
    journaliser('pca_renvoye', {'plan_id': p.id, 'motif': motif})
    _m().db.session.commit()
    flash('Plan renvoyé en rédaction.', 'info')
    return redirect(url_for('detail_plan_pca', plan_id=p.id))


# ---------------------------------------------------------------- liens risques / processus
@bp.route('/<int:plan_id>/liens', methods=['POST'])
@login_required
def liens(plan_id):
    m = _m()
    p = charger_plan(plan_id)
    if not peut('gerer'):
        abort(403)
    rid = {entier(x) for x in request.form.getlist('risque_ids') if entier(x)}
    pid = {entier(x) for x in request.form.getlist('processus_ids') if entier(x)}
    p.risque_ids = sorted(r.id for r in m.Risque.query.filter(m.Risque.id.in_(rid or [-1]),
                                                               m.Risque.client_id == p.client_id).all())
    p.processus_ids = sorted(x.id for x in m.ProcessusMetier.query.filter(m.ProcessusMetier.id.in_(pid or [-1]),
                                                                          m.ProcessusMetier.client_id == p.client_id).all())
    m.db.session.commit()
    flash('Risques et processus couverts enregistrés.', 'success')
    return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')


# ---------------------------------------------------------------- résultat d'exercice
@bp.route('/exercice/<int:exercice_id>/resultat', methods=['GET', 'POST'])
@login_required
def resultat(exercice_id):
    m = _m()
    e = m.db.session.get(m.ExercicePCA, exercice_id)
    if e is None:
        abort(404)
    p = charger_plan(e.plan_id)
    if not peut('tester'):
        abort(403)
    if request.method == 'POST':
        st = request.form.get('statut')
        if st not in ('realise', 'reporte', 'annule', 'planifie'):
            abort(400)
        e.statut = st
        d = request.form.get('date_exercice')
        if d:
            try:
                e.date_exercice = datetime.strptime(d, '%Y-%m-%d')
            except ValueError:
                pass
        e.resultats = (request.form.get('resultats') or '').strip() or None
        note = entier(request.form.get('note'))
        e.note = max(0, min(100, note)) if note is not None else None
        e.duree_reprise_heures = heures(request.form.get('duree_reprise'))
        e.points_forts = _lignes(request.form.get('points_forts'))
        axes = _lignes(request.form.get('axes_amelioration'))
        e.axes_amelioration = axes
        e.resultat_saisi_le, e.resultat_saisi_par_id = datetime.utcnow(), current_user.id
        creees = 0
        if st == 'realise':
            jour = (e.date_exercice.date() if isinstance(e.date_exercice, datetime) else e.date_exercice) or date.today()
            if not p.date_dernier_test or jour >= p.date_dernier_test:
                p.date_dernier_test = jour
                p.dernier_test = datetime.combine(jour, datetime.min.time())
                p.date_prochain_test = _plus_mois(jour, mois_periodicite(p))
                p.prochain_test = datetime.combine(p.date_prochain_test, datetime.min.time())
            historique = list(p.resultats_tests or [])
            historique.append({'exercice_id': e.id, 'date': jour.isoformat(), 'note': e.note,
                               'duree_reprise_heures': e.duree_reprise_heures, 'rto_heures': p.rto_heures})
            p.resultats_tests = historique
            if request.form.get('creer_actions') and axes and peut('gerer'):
                deja = set(e.actions_correctives or [])
                n0 = m.ActionPCA.query.filter_by(plan_id=p.id).count()
                for i, axe in enumerate(a for a in axes if a not in deja):
                    m.db.session.add(m.ActionPCA(
                        reference=f'{p.reference}-A{n0 + i + 1:02d}', plan_id=p.id, intitule=axe[:200],
                        description=f"Axe d'amélioration de l'exercice {e.reference} ({e.nom}).", phase='preparation',
                        priorite='haute' if (e.note or 100) < 50 else 'moyenne', statut='a_faire',
                        date_fin_prevue=_plus_mois(date.today(), 3), created_by=current_user.id, client_id=p.client_id))
                    creees += 1
                e.actions_correctives = sorted(deja | set(axes))
        journaliser('pca_exercice_resultat', {'exercice_id': e.id, 'statut': st, 'actions_creees': creees})
        m.db.session.commit()
        msg = 'Résultat enregistré.'
        if st == 'realise':
            msg += f" Prochain test le {p.date_prochain_test.strftime('%d/%m/%Y')}."
        if creees:
            msg += f' {creees} action(s) créée(s) à partir des axes d\'amélioration.'
        flash(msg, 'success')
        return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')
    return render_template('egalyx/pca_resultat_exercice.html', e=e, p=p)


# ---------------------------------------------------------------- activations réelles
@bp.route('/<int:plan_id>/activer', methods=['POST'])
@login_required
def activer(plan_id):
    m = _m()
    p = charger_plan(plan_id)
    if not (peut('gerer') or p.responsable_id == current_user.id):
        abort(403)
    motif = (request.form.get('motif') or '').strip()
    if not motif:
        flash('Indiquez la raison du déclenchement.', 'warning')
        return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')
    if m.ActivationPCA.query.filter_by(plan_id=p.id, fin=None).first():
        flash('Une activation est déjà en cours pour ce plan.', 'info')
        return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')
    inc = entier(request.form.get('incident_id'))
    if inc:
        i = m.db.session.get(m.Incident, inc)
        inc = i.id if i is not None and i.client_id == p.client_id else None
    a = m.ActivationPCA(plan_id=p.id, client_id=p.client_id, incident_id=inc, motif=motif, debut=datetime.utcnow(),
                        declenche_par_id=current_user.id)
    m.db.session.add(a)
    m.db.session.flush()
    _notifier(set(_gestionnaires(p.client_id)) | {p.responsable_id}, f'PCA déclenché : {p.reference}',
              f'{current_user.username} a déclenché le plan « {p.titre} » : {motif}', p, 'pca_active')
    journaliser('pca_active', {'plan_id': p.id, 'activation_id': a.id, 'incident_id': inc})
    m.db.session.commit()
    flash('PCA déclenché. Pensez à clore l\'activation au retour à la normale.', 'warning')
    return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')


@bp.route('/activation/<int:activation_id>/cloturer', methods=['POST'])
@login_required
def cloturer_activation(activation_id):
    m = _m()
    a = m.db.session.get(m.ActivationPCA, activation_id)
    if a is None:
        abort(404)
    p = charger_plan(a.plan_id)
    if not (peut('gerer') or p.responsable_id == current_user.id):
        abort(403)
    if a.fin:
        return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')
    a.fin, a.cloture_par_id = datetime.utcnow(), current_user.id
    a.bilan = (request.form.get('bilan') or '').strip() or None
    journaliser('pca_activation_close', {'activation_id': a.id, 'duree_heures': a.duree_heures()})
    m.db.session.commit()
    d = a.duree_heures()
    msg = f'Activation close après {d:g} h.'
    if p.rto_heures is not None:
        msg += ' RTO respecté.' if d <= p.rto_heures else f' RTO ({p.rto_heures:g} h) dépassé.'
    flash(msg, 'success' if p.rto_heures is None or d <= p.rto_heures else 'warning')
    return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')


# ---------------------------------------------------------------- documents
def _dossier(client_id):
    d = os.path.join(current_app.instance_path, 'documents_pca', str(client_id))
    os.makedirs(d, exist_ok=True)
    return d


@bp.route('/<int:plan_id>/document', methods=['POST'])
@login_required
def ajouter_document(plan_id):
    m = _m()
    p = charger_plan(plan_id)
    if not peut('gerer'):
        abort(403)
    f = request.files.get('fichier')
    if not f or not f.filename:
        flash('Choisissez un fichier.', 'warning')
        return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')
    from werkzeug.utils import secure_filename
    nom = secure_filename(f.filename) or 'document'
    ext = nom.rsplit('.', 1)[-1].lower() if '.' in nom else ''
    if ext not in EXTENSIONS:
        flash('Type de fichier non accepté.', 'warning')
        return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')
    contenu = f.read()
    if len(contenu) > TAILLE_MAX:
        flash('Fichier trop volumineux (20 Mo au plus).', 'warning')
        return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')
    unique = f'{uuid.uuid4().hex}.{ext}'
    chemin = os.path.join(_dossier(p.client_id), unique)
    with open(chemin, 'wb') as out:
        out.write(contenu)
    cat = request.form.get('categorie') if request.form.get('categorie') in ('document', 'procedure', 'schema', 'rapport') else 'document'
    m.db.session.add(m.DocumentPCA(plan_id=p.id, nom_fichier=f.filename[:255], nom_unique=unique, chemin_fichier=chemin,
                                   type_fichier=(f.mimetype or ext)[:255], taille=len(contenu), categorie=cat,
                                   description=(request.form.get('description') or '')[:500] or None,
                                   uploaded_by=current_user.id, client_id=p.client_id))
    m.db.session.commit()
    flash('Document ajouté.', 'success')
    return redirect(url_for('detail_plan_pca', plan_id=p.id) + '#pca-suivi')


def _document(document_id):
    m = _m()
    d = m.db.session.get(m.DocumentPCA, document_id)
    if d is None:
        abort(404)
    charger_plan(d.plan_id)
    return d


@bp.route('/document/<int:document_id>')
@login_required
def telecharger_document(document_id):
    d = _document(document_id)
    if not peut('voir'):
        abort(403)
    racine = os.path.realpath(os.path.join(current_app.instance_path, 'documents_pca'))
    chemin = os.path.realpath(d.chemin_fichier or '')
    if not chemin.startswith(racine + os.sep) or not os.path.exists(chemin):
        abort(404)
    return send_file(chemin, as_attachment=True, download_name=d.nom_fichier)


@bp.route('/document/<int:document_id>/supprimer', methods=['POST'])
@login_required
def supprimer_document(document_id):
    m = _m()
    d = _document(document_id)
    if not peut('gerer'):
        abort(403)
    plan_id = d.plan_id
    try:
        racine = os.path.realpath(os.path.join(current_app.instance_path, 'documents_pca'))
        chemin = os.path.realpath(d.chemin_fichier or '')
        if chemin.startswith(racine + os.sep) and os.path.exists(chemin):
            os.remove(chemin)
    except OSError:
        pass
    m.db.session.delete(d)
    m.db.session.commit()
    flash('Document supprimé.', 'success')
    return redirect(url_for('detail_plan_pca', plan_id=plan_id) + '#pca-suivi')


# ---------------------------------------------------------------- règles à l'enregistrement
def _avant_flush(session, _ctx, _inst):
    m = _m()
    from sqlalchemy import inspect as sa_inspect
    circuit = False
    try:
        circuit = bool(getattr(g, 'egalyx_pca_circuit', False))
    except RuntimeError:
        circuit = True                 # hors requête (scripts, tâches) : pas de contrôle
    for p in list(session.new) + list(session.dirty):
        if not isinstance(p, m.PlanContinuiteActivite):
            continue
        p.rto_heures = heures(p.delai_arret_max)
        p.rpo_heures = heures(p.perte_donnees_max)
        if circuit:
            continue
        if p in session.new:
            if p.statut in ('valide', 'en_relecture'):
                p.statut = 'en_redaction'
                _signaler("Un nouveau plan commence « en rédaction » : soumettez-le ensuite à validation.")
            continue
        insp = sa_inspect(p)
        h = insp.attrs.statut.history
        ancien = h.deleted[0] if h.deleted else p.statut
        if h.added and h.added[0] in ('valide', 'en_relecture') and ancien != h.added[0]:
            p.statut = ancien
            _signaler("Le statut « Validé » ou « En relecture » se donne par le circuit de validation (boutons de la fiche).")
            ancien_effectif = ancien
        else:
            ancien_effectif = p.statut
        if ancien_effectif == 'valide':
            change = any(insp.attrs[c].history.has_changes() and
                         (insp.attrs[c].history.deleted or [None])[0] != (insp.attrs[c].history.added or [None])[0]
                         for c in CHAMPS_CONTENU if c in insp.attrs)
            if change:
                p.statut = 'en_redaction'
                _signaler('Plan modifié après validation : il repasse en rédaction et doit être revalidé.')


def _signaler(message):
    try:
        flash(message, 'info')
    except RuntimeError:
        pass


# ---------------------------------------------------------------- « Ma semaine »
def taches(u, ajout, horizon, aujourd_hui, lien):
    m = _m()
    if not u.client_id:
        return
    gerer = a_permission(*GERER, u=u)
    for p in m.PlanContinuiteActivite.query.filter_by(client_id=u.client_id, is_archived=False).all():
        url = lien('detail_plan_pca', plan_id=p.id)
        if p.statut == 'en_relecture' and peut_valider(p, u):     # le valideur désigné, même sans droit PCA
            ajout('PCA à valider', p.titre, f'{p.reference} · soumis', p.soumis_le, url, 1)
        concerne = gerer or p.responsable_id == u.id
        if not concerne:
            continue
        if p.statut == 'valide' and p.date_validite and p.date_validite <= horizon + timedelta(days=46):
            ajout('PCA à revoir', p.titre, f'{p.reference} · fin de validité', p.date_validite, url)
        if p.date_prochain_test and p.date_prochain_test <= horizon:
            ajout('Test de PCA', p.titre, f'{p.reference} · test prévu', p.date_prochain_test, url)
    for a in m.ActionPCA.query.filter(m.ActionPCA.responsable_id == u.id, m.ActionPCA.statut != 'termine').all():
        ajout('Action de PCA', a.intitule, a.reference, a.date_fin_prevue, lien('modifier_action_pca', action_id=a.id))


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    exempter_controle_ancien(app, DROITS)
    import models as m
    from sqlalchemy import event
    from sqlalchemy.orm import Session
    app.register_blueprint(bp)
    app.before_request(_garde)
    if not getattr(m, '_egalyx_pca_flush', False):
        event.listen(Session, 'before_flush', _avant_flush)
        m._egalyx_pca_flush = True
    app.jinja_env.globals['pca_suivi'] = suivi
    app.jinja_env.globals['pca_statuts'] = STATUTS

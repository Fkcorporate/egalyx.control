"""
egalyx/carto_rapide.py — fiche d'une cartographie rapide.

Mesure avant (80 risques, 2 dispositifs chacun) : ~2,3 s, ~980 requêtes SQL, 2,7 Mo de HTML.
Causes :
  1. les 4 matrices étaient dessinées avec matplotlib à CHAQUE affichage (~1,4 s) puis collées dans la page
     en base64 (d'où les 2,7 Mo) ;
  2. 3 à 4 requêtes par risque (évaluation, dispositifs, puis encore campagne + évaluation pour les anomalies) ;
  3. une écriture en base à chaque visite, même sans changement, qui obligeait à recharger tous les objets.
Correctifs (affichage et données identiques) :
  1. matrices servies comme images séparées (/cartographie/<id>/matrice/<type>.png), mises en cache sur disque
     (instance/cache_matrices) tant que les cotations ne changent pas : le navigateur les charge en parallèle ;
  2. évaluations et dispositifs chargés en 2 requêtes pour toute la cartographie ; anomalies calculées sur place ;
  3. écriture en base seulement si une cotation a réellement changé.
"""
import hashlib
import logging
import os
import sys
from datetime import datetime

from flask import abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

journal = logging.getLogger('egalyx.carto_rapide')
VERSION = 'm1'
TYPES = ('classique', 'criticite', 'priorisation', 'surbrillance')


def _app():
    return sys.modules[current_app.import_name]


def _cotations(evaluation):
    impact = evaluation.impact_conf or evaluation.impact_val or evaluation.impact_pre
    proba = evaluation.probabilite_conf or evaluation.probabilite_val or evaluation.probabilite_pre
    maitrise = evaluation.niveau_maitrise_conf or evaluation.niveau_maitrise_val or evaluation.niveau_maitrise_pre
    return impact, proba, maitrise


def _anomalies(evaluation, nb_dispositifs):
    """Mêmes règles que utils.detecter_anomalies_risque, sans requête supplémentaire."""
    anomalies = []
    if evaluation is None:
        return anomalies
    phase = 'phase1'
    if evaluation.date_confirmation:
        phase = 'termine'
    elif evaluation.statut_validation == 'a_revoir':
        phase = 'a_revoir'
    elif evaluation.date_validation:
        phase = 'phase2'
    if phase == 'phase2':
        anomalies.append({'niveau': 'warning', 'message': "Évaluation validée mais non confirmée (Phase 2 → 3 requise).",
                          'action': None, 'label': "Confirmer"})
    elif phase == 'a_revoir':
        anomalies.append({'niveau': 'danger', 'message': "Évaluation renvoyée à l'opérateur — en attente de correction.",
                          'action': None, 'label': "Voir"})
    niveau = evaluation.niveau_risque_net or evaluation.niveau_risque
    if niveau in ('Critique', 'Élevé') and nb_dispositifs == 0:
        anomalies.append({'niveau': 'warning', 'message': f"Risque {niveau} sans aucun dispositif de maîtrise.",
                          'action': None, 'label': "Créer un dispositif"})
    return anomalies


def _donnees(cartographie, campagne, relations=True):
    """Risques visibles, dernière évaluation de la campagne et dispositifs : 2 requêtes au total."""
    a = _app()
    import models as M
    from sqlalchemy.orm import selectinload
    # risques + relations lues par la page (évaluations, KRI, dispositifs) : 4 requêtes au lieu d'une par risque
    q = M.Risque.query.filter(M.Risque.cartographie_id == cartographie.id).order_by(M.Risque.id)
    if relations:
        q = q.options(selectinload(M.Risque.evaluations), selectinload(M.Risque.kri), selectinload(M.Risque.dispositifs_maitrise))
    tous = q.all()
    risques = [r for r in tous if not getattr(r, 'is_archived', False) and a.check_client_access(r)]
    ids = [r.id for r in risques]
    evals, dispositifs = {}, {i: [] for i in ids}
    if ids:
        for e in (a.get_client_filter(M.EvaluationRisque)
                  .filter(M.EvaluationRisque.risque_id.in_(ids), M.EvaluationRisque.campagne_id == campagne.id)
                  .order_by(M.EvaluationRisque.created_at.desc())):
            evals.setdefault(e.risque_id, e)                       # la plus récente
        for d in (a.get_client_filter(M.DispositifMaitrise)
                  .filter(M.DispositifMaitrise.risque_id.in_(ids), M.DispositifMaitrise.is_archived.is_(False))
                  .order_by(M.DispositifMaitrise.reference.asc())):
            dispositifs[d.risque_id].append(d)
    return risques, evals, dispositifs


def _evaluations_valides(risques, evals, dispositifs, synchroniser=True):
    """Calcule les cotations ISO (comme la vue d'origine) ; renvoie {risque_id: dict} et la liste des évaluations valides."""
    from utils import calculer_maitrise_depuis_dmr, calculer_scores_risque
    res, valides = {}, []
    for r in risques:
        e = evals.get(r.id)
        info = dict(est_evalue=False, impact=None, probabilite=None, niveau_maitrise=None, score_net=0.0, score_brut=0.0,
                    niveau_net=None, niveau_brut=None, taux_reduction=0.0, probabilite_ajustee=None,
                    niveau_maitrise_dmr=None, ecart_maitrise=None)
        if e is not None:
            impact, proba, maitrise = _cotations(e)
            info.update(impact=impact, probabilite=proba, niveau_maitrise=maitrise)
            if impact and proba and impact > 0 and proba > 0:
                s = calculer_scores_risque(impact, proba, maitrise)
                dmr = ecart = None
                try:
                    dmr = calculer_maitrise_depuis_dmr(dispositifs.get(r.id, []))
                    if dmr is not None and maitrise:
                        ecart = abs(float(maitrise) - float(dmr))
                except Exception:  # noqa: BLE001
                    dmr = ecart = None
                info.update(est_evalue=True, score_brut=s['score_brut'], niveau_brut=s['niveau_brut'], score_net=s['score_net'],
                            niveau_net=s['niveau_net'], probabilite_ajustee=s['probabilite_ajustee'],
                            taux_reduction=s['taux_reduction'], niveau_maitrise_dmr=dmr, ecart_maitrise=ecart)
                if synchroniser:
                    for champ, v in (('score_risque_brut', s['score_brut']), ('niveau_risque_brut', s['niveau_brut']),
                                     ('score_risque_net', s['score_net']), ('niveau_risque_net', s['niveau_net']),
                                     ('probabilite_ajustee', s['probabilite_ajustee']),
                                     ('taux_reduction_maitrise', s['taux_reduction']), ('niveau_maitrise_dmr', dmr),
                                     ('ecart_maitrise', ecart), ('score_risque', s['score_net']), ('niveau_risque', s['niveau_net'])):
                        if getattr(e, champ, None) != v:            # n'écrit que ce qui change réellement
                            setattr(e, champ, v)
                valides.append(e)
        res[r.id] = info
    return res, valides


def _risque_surbrillance(risques, infos):
    """Le risque NET le plus critique (même règle que la vue d'origine)."""
    for niveau in ('Critique', 'Élevé'):
        candidats = [r for r in risques if infos[r.id]['est_evalue'] and infos[r.id]['niveau_net'] == niveau]
        if candidats:
            return sorted(candidats, key=lambda r: infos[r.id]['score_net'], reverse=True)[0]
    return None


def _signature(type_, valides, surbrillance_id=None):
    h = hashlib.sha1(f'{VERSION}|{type_}|{surbrillance_id}'.encode())
    for e in sorted(valides, key=lambda x: x.id):
        r = e.risque
        h.update(repr((e.id, e.risque_id, getattr(r, 'reference', None), getattr(r, 'intitule', None), _cotations(e),
                       e.score_risque_brut, e.score_risque_net, e.niveau_risque_net, e.niveau_risque_brut,
                       e.probabilite_ajustee, e.taux_reduction_maitrise, e.niveau_maitrise_dmr)).encode())
    return h.hexdigest()[:20]


def _url_matrice(carto_id, type_, valides, surbrillance=None):
    sid = surbrillance.id if surbrillance is not None else None
    return url_for('carto_rapide_matrice', id=carto_id, type_=type_, v=_signature(type_, valides, sid),
                   **({'r': sid} if sid else {}))


# ------------------------------------------------------------------ fiche
def detail_cartographie(id):
    a = _app()
    import models as M
    from models import db
    cartographie = db.session.get(M.Cartographie, id) or abort(404)
    if not a.check_client_access(cartographie):
        flash('Accès non autorisé à cette cartographie', 'error')
        return redirect(url_for('liste_cartographies'))

    campagne_active = a.get_client_filter(M.CampagneEvaluation).filter_by(cartographie_id=id, statut='en_cours').first()
    if not campagne_active:
        annee = datetime.now().year
        campagne_active = M.CampagneEvaluation(cartographie_id=id, nom=f"Campagne {annee}", description=f"Évaluation annuelle {annee}",
                                               date_debut=datetime.now().date(), statut='en_cours', created_by=current_user.id)
        campagne_active.client_id = cartographie.client_id if current_user.role == 'super_admin' else current_user.client_id
        db.session.add(campagne_active)
        db.session.commit()
    campagnes = (a.get_client_filter(M.CampagneEvaluation).filter_by(cartographie_id=id)
                 .order_by(M.CampagneEvaluation.created_at.desc()).all())

    risques, evals, dispositifs_par_risque = _donnees(cartographie, campagne_active)
    infos, evaluations_campagne = _evaluations_valides(risques, evals, dispositifs_par_risque)
    if db.session.dirty and any(db.session.is_modified(o) for o in db.session.dirty):
        try:
            db.session.commit()                                      # uniquement si une cotation a changé
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            journal.warning("Synchronisation des cotations : %s", e)

    risques_avec_evaluation, total_dispositifs = [], 0
    for r in risques:
        disp = dispositifs_par_risque.get(r.id, [])
        total_dispositifs += len(disp)
        r.dispositifs_maitrise_list = disp
        i = infos[r.id]
        e = evals.get(r.id)
        risques_avec_evaluation.append({
            'risque': r, 'evaluation': e, 'est_evalue': i['est_evalue'],
            'score': i['score_net'], 'niveau': i['niveau_net'], 'score_brut': i['score_brut'], 'niveau_brut': i['niveau_brut'],
            'score_net': i['score_net'], 'niveau_net': i['niveau_net'], 'taux_reduction': i['taux_reduction'],
            'probabilite_ajustee': i['probabilite_ajustee'], 'impact': i['impact'], 'probabilite': i['probabilite'],
            'niveau_maitrise': i['niveau_maitrise'], 'niveau_maitrise_dmr': i['niveau_maitrise_dmr'],
            'ecart_maitrise': i['ecart_maitrise'], 'dispositifs': disp, 'nb_dispositifs': len(disp),
            'anomalies': _anomalies(e, len(disp)) if i['est_evalue'] else [],
        })

    tableau_bordeaux = {'actions_prioritaires': [], 'surveillance_renforcee': [], 'surveillance_courante': [], 'actions_limitees': []}
    for it in risques_avec_evaluation:
        if not it['est_evalue'] or not it['niveau_net']:
            continue
        d = {'risque': it['risque'], 'evaluation': it['evaluation'], 'score': it['score_net'], 'score_brut': it['score_brut'],
             'niveau': it['niveau_net'], 'niveau_brut': it['niveau_brut'], 'taux_reduction': it['taux_reduction'],
             'nb_dispositifs': it['nb_dispositifs']}
        cle = {'Critique': 'actions_prioritaires', 'Élevé': 'surveillance_renforcee', 'Moyen': 'surveillance_courante'}
        tableau_bordeaux[cle.get(it['niveau_net'], 'actions_limitees')].append(d)
    for cat in tableau_bordeaux:
        tableau_bordeaux[cat].sort(key=lambda x: x['score'], reverse=True)

    matrices = dict.fromkeys(TYPES)
    if evaluations_campagne:
        for t in ('classique', 'criticite', 'priorisation'):
            matrices[t] = _url_matrice(id, t, evaluations_campagne)
        sb = (tableau_bordeaux['actions_prioritaires'] or tableau_bordeaux['surveillance_renforcee'] or [None])[0]
        if sb:
            matrices['surbrillance'] = _url_matrice(id, 'surbrillance', evaluations_campagne, sb['risque'])

    nb_risques_total = len(risques)
    nb_risques_evalues = sum(1 for x in risques_avec_evaluation if x['est_evalue'])
    progression_campagne = int(nb_risques_evalues / nb_risques_total * 100) if nb_risques_total else 0

    risque_ids = [r.id for r in risques]
    demandes_reevaluation = []
    if risque_ids:
        demandes_reevaluation = (a.get_client_filter(M.DemandeReevaluation).filter(M.DemandeReevaluation.risque_id.in_(risque_ids))
                                 .order_by(M.DemandeReevaluation.date_demande.desc()).all())
    compte = lambda s: sum(1 for d in demandes_reevaluation if d.statut == s)  # noqa: E731

    stats_dispositifs = {'total': total_dispositifs, 'par_type': {}, 'efficaces': 0, 'a_verifier': 0, 'non_evalues': 0, 'par_risque': {}}
    aujourdhui = datetime.now().date()
    for rid, disp in dispositifs_par_risque.items():
        stats_dispositifs['par_risque'][rid] = len(disp)
        for d in disp:
            if d.type_dispositif:
                stats_dispositifs['par_type'][d.type_dispositif] = stats_dispositifs['par_type'].get(d.type_dispositif, 0) + 1
            if d.efficacite_reelle and d.efficacite_reelle >= 4:
                stats_dispositifs['efficaces'] += 1
            if d.efficacite_reelle is None:
                stats_dispositifs['non_evalues'] += 1
            if not d.prochaine_verification or d.prochaine_verification <= aujourdhui:
                stats_dispositifs['a_verifier'] += 1

    analyse_couverture = []
    for it in risques_avec_evaluation:
        disp = dispositifs_par_risque.get(it['risque'].id, [])
        eff = [d.efficacite_reelle for d in disp if d.efficacite_reelle is not None]
        analyse_couverture.append({'risque_id': it['risque'].id, 'reference': it['risque'].reference, 'nb_dispositifs': len(disp),
                                   'efficacite_moyenne': (sum(eff) / len(eff)) if eff else None, 'niveau_risque': it['niveau_net'],
                                   'niveau_brut': it['niveau_brut'], 'score': it['score_net'], 'score_brut': it['score_brut']})

    constats_audit = []
    if risque_ids:
        constats_audit = (a.get_client_filter(M.Constatation).join(M.Constatation.risque)
                          .filter(M.Risque.cartographie_id == id, M.Constatation.statut != 'clos').all())

    tries = sorted(risques_avec_evaluation, key=lambda x: (x['score_net'] or 0, x['risque'].reference), reverse=True)
    ordre = {'danger': 0, 'warning': 1, 'info': 2}
    anomalies_globales = sorted(({'risque': it['risque'], 'niveau': an['niveau'], 'message': an['message'],
                                  'label': an.get('label', ''), 'action': an.get('action')}
                                 for it in risques_avec_evaluation for an in it['anomalies']),
                                key=lambda x: ordre.get(x['niveau'], 3))

    return render_template(
        'cartographie/detail.html', cartographie=cartographie, campagne_active=campagne_active, campagnes=campagnes,
        risques_avec_evaluation=tries, nb_risques_total=nb_risques_total, nb_risques_evalues=nb_risques_evalues,
        progression_campagne=progression_campagne,
        matrice_classique=matrices['classique'], matrice_criticite=matrices['criticite'],
        matrice_priorisation=matrices['priorisation'], matrice_surbrillance=matrices['surbrillance'],
        tableau_bordeaux=tableau_bordeaux, total_dispositifs=total_dispositifs, dispositifs_par_risque=dispositifs_par_risque,
        stats_dispositifs=stats_dispositifs, analyse_couverture=analyse_couverture,
        demandes_reevaluation=demandes_reevaluation, nb_demandes_attente=compte('en_attente'),
        nb_demandes_validees=compte('validee'), nb_demandes_rejetees=compte('rejetee'),
        constats_audit=constats_audit, nb_constats_ouverts=len(constats_audit), anomalies_globales=anomalies_globales,
        now=datetime.now, current_user=current_user)


# ------------------------------------------------------------------ images des matrices (mises en cache)
def matrice(id, type_):
    a = _app()
    import models as M
    from models import db
    if type_ not in TYPES:
        abort(404)
    cartographie = db.session.get(M.Cartographie, id)
    if cartographie is None or not a.check_client_access(cartographie):
        abort(404)
    if not (current_user.role == 'super_admin' or current_user.has_permission('can_manage_risks')):
        abort(403)
    campagne = a.get_client_filter(M.CampagneEvaluation).filter_by(cartographie_id=id, statut='en_cours').first()
    if campagne is None:
        abort(404)
    risques, evals, disp = _donnees(cartographie, campagne, relations=False)
    _infos, valides = _evaluations_valides(risques, evals, disp, synchroniser=True)
    db.session.rollback()                                       # aucune écriture depuis une image
    if not valides:
        abort(404)
    surbrillance = None
    if type_ == 'surbrillance':
        rid = request.args.get('r', type=int)
        surbrillance = next((r for r in risques if r.id == rid), None)
        if surbrillance is None:
            abort(404)
    sig = _signature(type_, valides, surbrillance.id if surbrillance else None)
    dossier = os.path.join(current_app.instance_path, 'cache_matrices')
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, f'{sig}.png')
    if not os.path.exists(chemin):
        import base64
        import utils
        if type_ == 'surbrillance':
            b64 = utils.generer_matrice_risque_specifique(valides, surbrillance)
        else:
            b64 = utils.generer_matrice_risques(valides, type_)
        if not b64:
            abort(404)
        temporaire = chemin + f'.{os.getpid()}.tmp'
        with open(temporaire, 'wb') as f:
            f.write(base64.b64decode(b64))
        os.replace(temporaire, chemin)
        _nettoyer(dossier)
    rep = send_file(chemin, mimetype='image/png', max_age=86400, etag=True, conditional=True)
    rep.headers['Cache-Control'] = 'private, max-age=86400'
    return rep


def _nettoyer(dossier, garder=400):
    """Garde les 400 images les plus récentes (anciennes cotations)."""
    try:
        f = sorted((os.path.join(dossier, n) for n in os.listdir(dossier) if n.endswith('.png')), key=os.path.getmtime)
        for x in f[:-garder]:
            os.remove(x)
    except OSError:
        pass


def enregistrer(app):
    if 'detail_cartographie' in app.view_functions:
        app.view_functions['detail_cartographie'] = login_required(detail_cartographie)
    app.add_url_rule('/cartographie/<int:id>/matrice/<type_>.png', 'carto_rapide_matrice', login_required(matrice))
    try:
        from egalyx.cloisonnement_carte import CARTE
        CARTE['carto_rapide_matrice'] = {'id': 'Cartographie'}
    except ImportError:
        pass
    return True

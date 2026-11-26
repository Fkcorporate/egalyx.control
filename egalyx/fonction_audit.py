"""
egalyx/fonction_audit.py — pilotage de la fonction d'audit interne (Normes internationales d'audit interne, IIA 2024).

1. Univers d'audit (/fonction-audit/univers) : ce que l'audit interne peut auditer (processus, directions, filiales,
   systèmes, projets…), avec un niveau de risque, un cycle d'audit (1, 2 ou 3 ans selon le risque, modifiable),
   la date du dernier audit (audits rattachés à l'entité ou à son processus, ou date saisie pour un audit
   antérieur à l'outil) et l'échéance du prochain. Création rapide depuis les processus et les directions.
2. Qualité de la fonction (/fonction-audit/qualite) : évaluation interne (périodique, au moins annuelle) et
   externe (au moins tous les 5 ans) de la conformité aux 15 principes des Normes ; à côté de chaque principe,
   les indicateurs que l'outil calcule déjà (indépendance, programme, délai du rapport, suivi des
   recommandations, satisfaction des audités, charte…).
3. Charte d'audit (/fonction-audit/charte) : versions successives, modèle de départ, approbation par le Conseil,
   revue annuelle. Une seule version en vigueur.
Droits : les gestionnaires de l'audit (egalyx/audit_plus.est_gestionnaire_audit) ; module Audit interne actif.
"""
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import client_id_courant, entier, journaliser

bp = Blueprint('fonction_audit', __name__, url_prefix='/fonction-audit')

TYPES = {'processus': 'Processus', 'direction': 'Direction', 'filiale': 'Filiale / entité juridique',
         'systeme': "Système d'information", 'projet': 'Projet', 'autre': 'Autre'}
NIVEAUX = {'eleve': 'Élevé', 'moyen': 'Moyen', 'faible': 'Faible'}
CYCLE_DEFAUT = {'eleve': 1, 'moyen': 2, 'faible': 3}
INSTANCES = ("Conseil d'administration", "Comité d'audit", 'Conseil de surveillance', 'Direction générale')
EXTERNE_ANS = 5
REVUE_CHARTE_MOIS = 12

# Normes internationales d'audit interne (IIA, 2024) : domaines et principes (intitulés officiels en français)
DOMAINES = [
    ('II', 'Éthique et professionnalisme', [(1, "Faire preuve d'intégrité"), (2, "Faire preuve d'objectivité"),
                                            (3, 'Faire preuve de compétence'), (4, 'Pratiquer avec conscience professionnelle'),
                                            (5, 'Préserver la confidentialité')]),
    ('III', "Gouvernance de la fonction d'audit interne", [(6, 'Autorité conférée par le Conseil'), (7, 'Indépendance'),
                                                          (8, 'Surveillance du Conseil')]),
    ('IV', "Gestion de la fonction d'audit interne", [(9, 'Planifier de manière stratégique'), (10, 'Gérer les ressources'),
                                                     (11, 'Communiquer avec efficacité'), (12, 'Améliorer la qualité')]),
    ('V', "Réalisation des activités d'audit interne", [(13, 'Planifier les missions avec efficacité'),
                                                       (14, 'Réaliser les travaux de la mission'),
                                                       (15, "Communiquer les résultats de la mission et suivre les plans d'action")]),
]
PRINCIPES = {n: t for _, _, ps in DOMAINES for n, t in ps}
NIVEAUX_CONFORMITE = {'conforme': 'Conforme', 'partiel': 'Partiellement conforme', 'non_conforme': 'Non conforme',
                      'na': 'Sans objet'}
CONCLUSIONS = {'conforme': 'Conforme aux Normes', 'partiel': 'Partiellement conforme', 'non_conforme': 'Non conforme'}

MODELE_CHARTE = """1. Mission et mandat
L'audit interne de {organisation} a pour mission de renforcer la capacité de l'organisation à créer, préserver et maintenir de la valeur, en fournissant au Conseil et à la Direction générale une assurance, des conseils, des analyses et une vision prospective, indépendants, objectifs et fondés sur une approche par les risques.

2. Référentiel
L'audit interne respecte les Normes internationales d'audit interne de l'IIA (2024), ainsi que les lois et réglementations applicables.

3. Positionnement et indépendance
Le responsable de l'audit interne est rattaché fonctionnellement au Conseil (comité d'audit) et administrativement à la Direction générale. Le Conseil approuve sa nomination, sa révocation, sa rémunération, le plan d'audit et le budget de la fonction.

4. Accès
L'audit interne a un accès complet, libre et sans restriction à l'ensemble des fonctions, données, documents, biens et personnes de l'organisation nécessaires à ses travaux, dans le respect de la confidentialité.

5. Champ d'intervention
Missions d'assurance et de conseil portant sur la gouvernance, la gestion des risques et le contrôle interne de toutes les activités de {organisation}.

6. Responsabilités
Le responsable de l'audit interne élabore un plan d'audit fondé sur les risques, conduit les missions, communique les résultats, suit la mise en œuvre des plans d'action et rend compte au Conseil au moins une fois par an.

7. Qualité
L'audit interne met en œuvre un programme d'assurance et d'amélioration qualité : évaluations internes périodiques et évaluation externe au moins tous les cinq ans, dont les résultats sont communiqués au Conseil.

8. Approbation et revue
La présente charte est approuvée par le Conseil et revue au moins une fois par an."""


def _m():
    import models
    return models


def _ap():
    from egalyx import audit_plus
    return audit_plus


def _garde():
    ap = _ap()
    if getattr(current_user, 'role', None) != 'super_admin' and not ap.module_audit_actif():
        abort(404)
    if not ap.est_gestionnaire_audit():
        abort(403)
    cid = client_id_courant()
    if not cid:
        abort(404)
    return cid


def _date(v):
    try:
        return datetime.strptime((v or '').strip(), '%Y-%m-%d').date() if v else None
    except ValueError:
        return None


def _ajouter_ans(d, n):
    try:
        return d.replace(year=d.year + n)
    except ValueError:            # 29 février
        return d.replace(year=d.year + n, day=28)


def _aujourdhui():
    try:
        from egalyx.localisation import aujourdhui
        return aujourdhui()
    except Exception:
        return date.today()


# ---------------------------------------------------------------- univers d'audit
def _date_audit(a):
    if a.rapport_definitif_le:
        return a.rapport_definitif_le.date()
    if (a.statut or '') in ('termine', 'realise', 'clos'):
        return a.date_fin_reelle or a.date_fin_prevue
    return None


def situation(e, audits, auj=None):
    """Dernier audit, audit en cours, cycle, échéance et état d'une entité de l'univers."""
    auj = auj or _aujourdhui()
    lies = [a for a in audits if a.entite_auditable_id == e.id or (e.processus_id and a.processus_id == e.processus_id)]
    dates = [d for d in (_date_audit(a) for a in lies) if d]
    if e.dernier_audit_manuel:
        dates.append(e.dernier_audit_manuel)
    dernier = max(dates) if dates else None
    en_cours = [a for a in lies if _date_audit(a) is None and (a.statut or '') not in ('annule', 'archive') and not a.is_archived]
    cycle = e.cycle_annees or CYCLE_DEFAUT.get(e.niveau_risque or 'moyen', 2)
    echeance = _ajouter_ans(dernier, cycle) if dernier else None
    if en_cours:
        etat, libelle = 'en_cours', 'Audit en cours'
    elif echeance is None:
        etat, libelle = 'retard', 'Jamais audité'
    elif echeance < auj:
        etat, libelle = 'retard', f'À auditer (échéance dépassée de {(auj - echeance).days} j)'
    elif echeance <= auj + timedelta(days=365):
        etat, libelle = 'bientot', 'À prévoir dans les 12 mois'
    else:
        etat, libelle = 'ok', 'Couvert'
    return {'dernier': dernier, 'cycle': cycle, 'echeance': echeance, 'etat': etat, 'libelle': libelle,
            'audits': sorted(lies, key=lambda a: a.id, reverse=True), 'en_cours': en_cours}


def univers(cid):
    m = _m()
    entites = m.EntiteAuditable.query.filter_by(client_id=cid).order_by(m.EntiteAuditable.nom).all()
    audits = m.Audit.query.filter_by(client_id=cid).all()
    auj = _aujourdhui()
    lignes = [{'e': e, **situation(e, audits, auj)} for e in entites]
    ordre = {'retard': 0, 'bientot': 1, 'en_cours': 2, 'ok': 3}
    risque = {'eleve': 0, 'moyen': 1, 'faible': 2}
    actives = [x for x in lignes if x['e'].actif is not False]
    actives.sort(key=lambda x: (ordre[x['etat']], risque.get(x['e'].niveau_risque, 1), x['echeance'] or date.min))
    inactives = [x for x in lignes if x['e'].actif is False]
    couvertes = [x for x in actives if x['etat'] in ('ok', 'bientot', 'en_cours')]
    return {'lignes': actives, 'inactives': inactives, 'audits': audits,
            'couverture': round(100 * len(couvertes) / len(actives)) if actives else None,
            'retard': sum(1 for x in actives if x['etat'] == 'retard'),
            'eleve_retard': sum(1 for x in actives if x['etat'] == 'retard' and x['e'].niveau_risque == 'eleve')}


def _lire_entite(e, f):
    nom = ' '.join((f.get('nom') or '').split())[:200]
    if not nom:
        raise ValueError("Indiquez le nom de l'entité.")
    e.nom = nom
    e.type_entite = f.get('type_entite') if f.get('type_entite') in TYPES else 'autre'
    e.niveau_risque = f.get('niveau_risque') if f.get('niveau_risque') in NIVEAUX else 'moyen'
    c = entier(f.get('cycle_annees'))
    if c is not None and not 1 <= c <= 10:
        raise ValueError("Le cycle d'audit va de 1 à 10 ans.")
    e.cycle_annees = c
    d = _date(f.get('dernier_audit_manuel'))
    if d and d > _aujourdhui():
        raise ValueError("La date du dernier audit ne peut pas être dans le futur.")
    e.dernier_audit_manuel = d
    e.responsable = ' '.join((f.get('responsable') or '').split())[:150] or None
    e.commentaire = (f.get('commentaire') or '').strip()[:2000] or None


@bp.route('/univers', methods=['GET', 'POST'])
@login_required
def page_univers():
    cid = _garde()
    m = _m()
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'ajouter':
                e = m.EntiteAuditable(client_id=cid, actif=True)
                _lire_entite(e, request.form)
                m.db.session.add(e)
                m.db.session.flush()
                journaliser('univers_entite_ajoutee', {'id': e.id, 'nom': e.nom})
                flash(f"« {e.nom} » ajouté à l'univers d'audit.", 'success')
            elif action in ('modifier', 'activer', 'retirer', 'rattacher'):
                e = m.db.session.get(m.EntiteAuditable, entier(request.form.get('entite_id')))
                if e is None or e.client_id != cid:
                    abort(404)
                if action == 'modifier':
                    _lire_entite(e, request.form)
                    flash('Entité mise à jour.', 'success')
                elif action == 'retirer':
                    e.actif = False
                    flash(f"« {e.nom} » retiré de l'univers (conservé dans la liste des entités retirées).", 'info')
                elif action == 'activer':
                    e.actif = True
                    flash(f"« {e.nom} » remis dans l'univers.", 'success')
                else:
                    a = m.db.session.get(m.Audit, entier(request.form.get('audit_id')))
                    if a is None or a.client_id != cid:
                        abort(404)
                    a.entite_auditable_id = e.id
                    flash(f"Audit {a.reference} rattaché à « {e.nom} ».", 'success')
                journaliser('univers_entite_' + action, {'id': e.id})
            elif action == 'importer':
                n = importer(cid, request.form.getlist('source'))
                journaliser('univers_import', {'ajoutees': n})
                flash(f"{n} entité(s) ajoutée(s) depuis vos processus et directions." if n
                      else 'Rien de nouveau à ajouter : ces processus et directions sont déjà dans l’univers.', 'success' if n else 'info')
            else:
                abort(400)
            m.db.session.commit()
        except ValueError as ex:
            m.db.session.rollback()
            flash(str(ex), 'warning')
        return redirect(url_for('.page_univers'))
    u = univers(cid)
    return render_template('egalyx/fonction_audit_univers.html', u=u, types=TYPES, niveaux=NIVEAUX, cycle_defaut=CYCLE_DEFAUT,
                           aujourdhui=_aujourdhui())


def importer(cid, sources):
    """Crée une entité par processus (logigramme) et par direction qui n'en a pas encore. Rend le nombre créé."""
    m = _m()
    existants = m.EntiteAuditable.query.filter_by(client_id=cid).all()
    deja_p = {e.processus_id for e in existants if e.processus_id}
    deja_d = {e.direction_id for e in existants if e.direction_id}
    noms = {(e.nom or '').strip().lower() for e in existants}
    n = 0
    if 'processus' in sources:
        q = m.ProcessusActivite.query
        if 'client_id' in m.ProcessusActivite.__table__.columns:
            q = q.filter_by(client_id=cid)
        for p in q.all():
            if p.is_archived or p.id in deja_p or (p.nom or '').strip().lower() in noms:
                continue
            m.db.session.add(m.EntiteAuditable(client_id=cid, nom=p.nom[:200], type_entite='processus', processus_id=p.id,
                                               direction_id=p.direction_id, niveau_risque='moyen', actif=True))
            noms.add((p.nom or '').strip().lower())
            n += 1
    if 'direction' in sources:
        q = m.Direction.query
        if 'client_id' in m.Direction.__table__.columns:
            q = q.filter_by(client_id=cid)
        for d in q.all():
            if d.id in deja_d and any(e.type_entite == 'direction' and e.direction_id == d.id for e in existants):
                continue
            if (d.nom or '').strip().lower() in noms:
                continue
            m.db.session.add(m.EntiteAuditable(client_id=cid, nom=d.nom[:200], type_entite='direction', direction_id=d.id,
                                               niveau_risque='moyen', actif=True))
            noms.add((d.nom or '').strip().lower())
            n += 1
    return n


# ---------------------------------------------------------------- indicateurs
def indicateurs(cid, annee):
    """Indicateurs de la fonction d'audit pour une année, calculés à partir des données de l'outil."""
    m = _m()
    ap = _ap()
    auj = _aujourdhui()
    audits = m.Audit.query.filter_by(client_id=cid).all()
    definitifs = [a for a in audits if a.rapport_definitif_le and a.rapport_definitif_le.year == annee]
    ind = {}
    # Programme de l'année : missions prévues / réalisées
    prog_ids = [p.id for p in m.ProgrammeAudit.query.filter_by(client_id=cid).all()]
    missions = (m.MissionAudit.query.filter(m.MissionAudit.programme_id.in_(prog_ids), m.MissionAudit.annee_prevue == annee).all()
                if prog_ids else [])
    def realisee(mi):
        a = m.db.session.get(m.Audit, mi.audit_id) if mi.audit_id else None
        return (mi.statut or '') in ('termine', 'realise', 'realisee', 'clos') or (a is not None and a.etat_rapport == 'definitif')
    ind['programme'] = {'prevues': len(missions), 'realisees': sum(1 for x in missions if realisee(x)),
                        'approuve': any((p.statut or '') == 'actif' and p.annee_debut <= annee <= p.annee_fin
                                        for p in m.ProgrammeAudit.query.filter_by(client_id=cid).all())}
    ind['programme']['taux'] = (round(100 * ind['programme']['realisees'] / ind['programme']['prevues'])
                                if ind['programme']['prevues'] else None)
    # Rapports définitifs et délai fin des travaux -> rapport définitif
    delais = [(a.rapport_definitif_le.date() - a.date_fin_reelle).days for a in definitifs if a.date_fin_reelle]
    ind['rapports'] = {'nb': len(definitifs), 'delai_moyen': round(sum(delais) / len(delais)) if delais else None}
    # Indépendance : missions de l'année dont toute l'équipe a signé
    completes = [a for a in definitifs if not ap.etat_independance(a)['manquantes']]
    ind['independance'] = {'nb': len(definitifs), 'completes': len(completes),
                           'taux': round(100 * len(completes) / len(definitifs)) if definitifs else None,
                           'conflits': sum(len(ap.etat_independance(a)['conflits']) for a in definitifs)}
    # Recommandations échues dans l'année : mises en œuvre
    recos = [r for r in m.Recommandation.query.filter_by(client_id=cid).all()
             if r.date_echeance and r.date_echeance.year == annee and r.date_echeance <= auj
             and (r.statut or '') not in ('annule', 'rejetee') and not getattr(r, 'is_archived', False)]
    faites = [r for r in recos if (r.statut or '') == 'termine']
    ind['recommandations'] = {'echues': len(recos), 'mises_en_oeuvre': len(faites),
                              'taux': round(100 * len(faites) / len(recos)) if recos else None}
    # Satisfaction des audités
    try:
        from egalyx.satisfaction_audit import resultats, SEUIL_ANONYMAT
        reps = [r for r in m.SatisfactionAudit.query.filter_by(client_id=cid).all() if r.repondu_le and r.repondu_le.year == annee]
        res = resultats(reps)
        ind['satisfaction'] = {'nb': res['nb'], 'moyenne': res['moyenne'] if res['nb'] >= SEUIL_ANONYMAT else None}
    except Exception:
        ind['satisfaction'] = {'nb': 0, 'moyenne': None}
    # Temps passé (heures saisies sur les missions de l'année)
    try:
        heures = sum(t.heures or 0 for t in m.TempsAudit.query.filter_by(client_id=cid).all() if t.date and t.date.year == annee)
    except Exception:
        heures = None
    ind['temps'] = {'heures': round(heures, 1) if heures is not None else None}
    # Charte, univers, évaluations
    ch = charte_en_vigueur(cid)
    ind['charte'] = {'en_vigueur': ch, 'revue_depassee': bool(ch and ch.revue_prevue and ch.revue_prevue < auj)}
    u = univers(cid)
    ind['univers'] = {'nb': len(u['lignes']), 'couverture': u['couverture'], 'retard': u['retard'], 'eleve_retard': u['eleve_retard']}
    ind['dossiers_figes'] = sum(1 for a in definitifs if a.dossier_rouvert_le is None)
    return ind


def preuves_principes(ind):
    """Indicateurs rattachés à chaque principe (aide à l'évaluation, pas une note automatique)."""
    def pct(x):
        return f'{x} %' if x is not None else '—'
    p = {}
    if ind['independance']['taux'] is None:
        p[2] = ["Déclarations d'indépendance : aucune mission avec rapport définitif sur l'année"]
    else:
        p[2] = [f"Déclarations d'indépendance complètes : {ind['independance']['taux']} % des missions "
                f"({ind['independance']['completes']} / {ind['independance']['nb']})",
                f"Conflits d'intérêts déclarés : {ind['independance']['conflits']}"]
    p[6] = ['Charte en vigueur : ' + (f"version {ind['charte']['en_vigueur'].version}, approuvée le "
                                      f"{ind['charte']['en_vigueur'].approuvee_le.strftime('%d/%m/%Y')}"
                                      if ind['charte']['en_vigueur'] and ind['charte']['en_vigueur'].approuvee_le else 'aucune')]
    if ind['charte']['revue_depassee']:
        p[6].append('Revue annuelle de la charte dépassée')
    p[7] = p[2][:1]
    p[9] = [f"Programme d'audit approuvé pour l'année : {'oui' if ind['programme']['approuve'] else 'non'}",
            f"Univers d'audit couvert dans les cycles : {pct(ind['univers']['couverture'])}"
            + (f" ({ind['univers']['eleve_retard']} entité(s) à risque élevé en retard)" if ind['univers']['eleve_retard'] else '')]
    p[10] = [(f"Missions réalisées / prévues : {ind['programme']['realisees']} / {ind['programme']['prevues']} ({pct(ind['programme']['taux'])})"
              if ind['programme']['prevues'] else "Aucune mission prévue au programme pour l'année"),
             f"Temps saisi : {ind['temps']['heures'] if ind['temps']['heures'] is not None else '—'} h"]
    p[11] = [f"Satisfaction des audités : {str(ind['satisfaction']['moyenne']) + ' / 5' if ind['satisfaction']['moyenne'] else '—'}"
             f" ({ind['satisfaction']['nb']} réponse(s))"]
    p[14] = [f"Rapports définitifs émis : {ind['rapports']['nb']} ; dossiers figés : {ind['dossiers_figes']}"]
    p[15] = [f"Délai moyen fin des travaux → rapport définitif : {str(ind['rapports']['delai_moyen']) + ' j' if ind['rapports']['delai_moyen'] is not None else '—'}",
             f"Recommandations échues mises en œuvre : {ind['recommandations']['mises_en_oeuvre']} / {ind['recommandations']['echues']} ({pct(ind['recommandations']['taux'])})"]
    return p


# ---------------------------------------------------------------- qualité de la fonction
def etat_evaluations(cid):
    m = _m()
    auj = _aujourdhui()
    evals = m.EvaluationQualiteAudit.query.filter_by(client_id=cid).order_by(m.EvaluationQualiteAudit.annee.desc(),
                                                                             m.EvaluationQualiteAudit.id.desc()).all()
    ext = [e for e in evals if e.type_evaluation == 'externe' and e.statut == 'valide' and e.date_evaluation]
    derniere_ext = max(ext, key=lambda e: e.date_evaluation) if ext else None
    prochaine_ext = _ajouter_ans(derniere_ext.date_evaluation, EXTERNE_ANS) if derniere_ext else None
    internes = [e for e in evals if e.type_evaluation == 'interne' and e.statut == 'valide']
    return {'evaluations': evals, 'derniere_externe': derniere_ext, 'prochaine_externe': prochaine_ext,
            'externe_en_retard': prochaine_ext is None or prochaine_ext < auj,
            'interne_annee': any(e.annee == auj.year for e in internes),
            'derniere_interne': internes[0] if internes else None}


@bp.route('/qualite')
@login_required
def page_qualite():
    cid = _garde()
    annee = entier(request.args.get('annee')) or _aujourdhui().year
    ind = indicateurs(cid, annee)
    return render_template('egalyx/fonction_audit_qualite.html', ind=ind, preuves=preuves_principes(ind), annee=annee,
                           etat=etat_evaluations(cid), domaines=DOMAINES, conclusions=CONCLUSIONS, externe_ans=EXTERNE_ANS)


@bp.route('/qualite/evaluation/nouvelle', methods=['POST'])
@login_required
def nouvelle_evaluation():
    cid = _garde()
    m = _m()
    t = request.form.get('type_evaluation')
    if t not in ('interne', 'externe'):
        abort(400)
    annee = entier(request.form.get('annee')) or _aujourdhui().year
    e = m.EvaluationQualiteAudit(client_id=cid, type_evaluation=t, annee=annee, statut='brouillon', reponses={},
                                 date_evaluation=_aujourdhui() if t == 'interne' else None, created_by=current_user.id)
    m.db.session.add(e)
    m.db.session.flush()
    journaliser('qualite_audit_evaluation_creee', {'id': e.id, 'type': t, 'annee': annee})
    m.db.session.commit()
    return redirect(url_for('.evaluation', eval_id=e.id))


@bp.route('/qualite/evaluation/<int:eval_id>', methods=['GET', 'POST'])
@login_required
def evaluation(eval_id):
    cid = _garde()
    m = _m()
    e = m.db.session.get(m.EvaluationQualiteAudit, eval_id)
    if e is None or e.client_id != cid:
        abort(404)
    if request.method == 'POST':
        if e.statut == 'valide':
            flash('Évaluation validée : elle ne se modifie plus.', 'warning')
            return redirect(url_for('.evaluation', eval_id=e.id))
        rep = {}
        for n in PRINCIPES:
            niveau = request.form.get(f'p{n}_niveau')
            rep[str(n)] = {'niveau': niveau if niveau in NIVEAUX_CONFORMITE else None,
                           'commentaire': (request.form.get(f'p{n}_commentaire') or '').strip()[:2000] or None,
                           'action': (request.form.get(f'p{n}_action') or '').strip()[:1000] or None}
        e.reponses = rep
        e.evaluateur = ' '.join((request.form.get('evaluateur') or '').split())[:200] or None
        e.date_evaluation = _date(request.form.get('date_evaluation')) or e.date_evaluation
        e.conclusion = request.form.get('conclusion') if request.form.get('conclusion') in CONCLUSIONS else None
        e.synthese = (request.form.get('synthese') or '').strip()[:5000] or None
        if request.form.get('action') == 'valider':
            manquants = [n for n in PRINCIPES if not rep[str(n)]['niveau']]
            if manquants:
                flash(f"Évaluez chaque principe avant de valider (manquants : {', '.join(map(str, manquants))}).", 'warning')
            elif not e.conclusion or not e.date_evaluation:
                flash('Indiquez la date et la conclusion générale avant de valider.', 'warning')
            elif e.type_evaluation == 'externe' and not e.evaluateur:
                flash("Indiquez l'évaluateur externe (cabinet ou personne) avant de valider.", 'warning')
            else:
                e.statut, e.valide_le, e.valide_par_id = 'valide', datetime.utcnow(), current_user.id
                journaliser('qualite_audit_evaluation_validee', {'id': e.id, 'type': e.type_evaluation, 'conclusion': e.conclusion})
                m.db.session.commit()
                flash('Évaluation validée.', 'success')
                return redirect(url_for('.page_qualite', annee=e.annee))
        else:
            flash('Évaluation enregistrée (brouillon).', 'success')
        m.db.session.commit()
        return redirect(url_for('.evaluation', eval_id=e.id))
    ind = indicateurs(cid, e.annee)
    return render_template('egalyx/fonction_audit_evaluation.html', e=e, domaines=DOMAINES, niveaux=NIVEAUX_CONFORMITE,
                           conclusions=CONCLUSIONS, preuves=preuves_principes(ind), rep=e.reponses or {})


# ---------------------------------------------------------------- charte
def charte_en_vigueur(cid):
    m = _m()
    return (m.CharteAudit.query.filter_by(client_id=cid, statut='approuvee')
            .order_by(m.CharteAudit.version.desc()).first())


@bp.route('/charte', methods=['GET', 'POST'])
@login_required
def page_charte():
    cid = _garde()
    m = _m()
    versions = m.CharteAudit.query.filter_by(client_id=cid).order_by(m.CharteAudit.version.desc()).all()
    brouillon = next((v for v in versions if v.statut == 'brouillon'), None)
    vigueur = charte_en_vigueur(cid)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'nouvelle':
            if brouillon is None:
                from egalyx.identite import nom_affiche
                base = vigueur.texte if vigueur else MODELE_CHARTE.replace('{organisation}', nom_affiche(cid) or 'l’organisation')
                brouillon = m.CharteAudit(client_id=cid, version=(versions[0].version + 1) if versions else 1, texte=base,
                                          statut='brouillon', created_by=current_user.id)
                m.db.session.add(brouillon)
                m.db.session.flush()
                journaliser('charte_audit_brouillon', {'version': brouillon.version})
                m.db.session.commit()
            return redirect(url_for('.page_charte') + '#brouillon')
        if brouillon is None:
            abort(400)
        texte = (request.form.get('texte') or '').strip()
        if len(texte) > 30000:
            flash('Texte trop long (30 000 caractères au maximum).', 'warning')
            return redirect(url_for('.page_charte'))
        brouillon.texte = texte
        if action == 'approuver':
            d = _date(request.form.get('approuvee_le'))
            par = ' '.join((request.form.get('approuvee_par') or '').split())[:200]
            if len(texte) < 200:
                flash('La charte paraît incomplète (moins de 200 caractères).', 'warning')
            elif not d or d > _aujourdhui() or not par:
                flash("Indiquez la date d'approbation (pas dans le futur) et l'instance qui l'a approuvée.", 'warning')
            else:
                for v in versions:
                    if v.statut == 'approuvee':
                        v.statut = 'remplacee'
                brouillon.statut, brouillon.approuvee_le, brouillon.approuvee_par = 'approuvee', d, par
                brouillon.revue_prevue = _ajouter_ans(d, 1)
                journaliser('charte_audit_approuvee', {'version': brouillon.version, 'par': par, 'le': d.isoformat()})
                m.db.session.commit()
                flash(f'Charte version {brouillon.version} en vigueur. Prochaine revue : {brouillon.revue_prevue.strftime("%d/%m/%Y")}.', 'success')
                return redirect(url_for('.page_charte'))
        elif action == 'abandonner':
            m.db.session.delete(brouillon)
            journaliser('charte_audit_brouillon_abandonne', {'version': brouillon.version})
            m.db.session.commit()
            flash('Brouillon abandonné.', 'info')
            return redirect(url_for('.page_charte'))
        else:
            flash('Brouillon enregistré.', 'success')
        m.db.session.commit()
        return redirect(url_for('.page_charte') + '#brouillon')
    return render_template('egalyx/fonction_audit_charte.html', versions=versions, brouillon=brouillon, vigueur=vigueur,
                           instances=INSTANCES, aujourdhui=_aujourdhui())


def enregistrer(app):
    from egalyx.commun import exempter_controle_ancien
    app.register_blueprint(bp)
    exempter_controle_ancien(app, {'fonction_audit.page_univers', 'fonction_audit.nouvelle_evaluation',
                                   'fonction_audit.evaluation', 'fonction_audit.page_charte'})

"""
egalyx/ia_audit.py — l'IA au cœur du travail de l'auditeur (étape 1).

1. Rédaction des constats : l'auditeur saisit ses notes brutes dans « Nouvelle constatation » ; l'IA propose le
   constat structuré selon les 5 C (fait, critère, cause, conséquence, recommandation), la gravité et le type,
   plus les points à vérifier. Rien n'est enregistré tant que l'auditeur n'a pas relu et cliqué « Créer ».
2. Premier jet du rapport : à partir des constats, recommandations, tests et plans de la mission, l'IA propose
   le résumé exécutif et la conclusion ; l'auditeur corrige, enregistre, puis valide. Seul un texte validé
   figure dans les rapports PDF et Word (egalyx/rapport_contenu.redaction_validee).

Garde-fous :
  - chaque fonction a son interrupteur chez le super admin (egalyx/ia.FONCTIONS), en plus de l'interrupteur
    général, du module « Analyse IA » de l'organisation et de la permission « Utiliser l'analyse IA » ;
  - données masquées avant l'envoi et fournisseur choisi par le super admin (egalyx/ia_passerelle.py) ;
  - sans IA : proposition automatique honnête (règles prédéfinies), annoncée comme telle ;
  - l'IA n'invente ni chiffre, ni nom, ni date : ce qui manque est signalé « À compléter » ;
  - accès : équipe de la mission ou gestionnaires de l'audit, organisation de l'utilisateur ; dossier figé
    après le rapport définitif (egalyx/dossier_fige.py) : plus de modification.
"""
import re
from datetime import datetime

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from egalyx.commun import journaliser, nom_personne

bp = Blueprint('ia_audit', __name__, url_prefix='/audit-ia')

NOTES_MAX = 6000
TEXTE_MAX = 8000
GRAVITES = ('mineure', 'moyenne', 'majeure', 'critique')
TYPES = ('non_conformite', 'observation', 'conformite', 'recommandation')


def _m():
    import models
    return models


def _ap():
    from egalyx import audit_plus
    return audit_plus


def _moteur():
    from egalyx import ia_moteur
    return ia_moteur


def fonction_active(code):
    from egalyx.ia import fonction_active as f
    return f(code)


def peut_travailler(audit, u=None):
    u = u or current_user
    ap = _ap()
    return ap.est_gestionnaire_audit(u) or getattr(u, 'id', None) in ap.equipe(audit)


def _audit(audit_id):
    a = _ap().charger_audit(audit_id)            # organisation + module Audit interne, sinon 404
    if not peut_travailler(a):
        abort(403)
    return a


def _fige(audit):
    try:
        from egalyx.dossier_fige import est_fige
        return est_fige(audit)
    except Exception:  # noqa: BLE001
        return False


def _t(v, n):
    return re.sub(r'[ \t]+', ' ', str(v or '')).strip()[:n]


def _choix(v, permis, defaut):
    v = _t(v, 30).lower().replace('é', 'e').replace('è', 'e').replace('-', '_').replace(' ', '_')
    v = {'non_conforme': 'non_conformite', 'nonconformite': 'non_conformite', 'elevee': 'majeure', 'haute': 'majeure',
         'faible': 'mineure', 'moderee': 'moyenne', 'critique': 'critique'}.get(v, v)
    return v if v in permis else defaut


# ====================================================================== 1. constats
CONSIGNES_CONSTAT = """Tu es auditeur interne senior et tu appliques les Normes internationales d'audit interne (IIA 2024).
À partir des notes brutes d'un auditeur, rédige UN constat d'audit en français, selon la méthode des 5 C :
- "titre" : intitulé court du constat (10 mots maximum) ;
- "fait" : ce qui a été observé, de façon factuelle, précise et neutre, avec l'échantillon et les chiffres présents dans les notes ;
- "critere" : la règle attendue (procédure, politique, norme, réglementation). Si les notes ne la citent pas, propose la règle usuelle et commence par « À confirmer : » ;
- "cause" : la cause probable de l'écart (si les notes ne permettent pas de la connaître, écris « À compléter : … ») ;
- "consequence" : le risque ou l'impact pour l'organisation ;
- "recommandation" : action corrective concrète, réalisable, avec le responsable type (sans inventer de nom) ;
- "gravite" : une valeur parmi mineure, moyenne, majeure, critique ;
- "type" : une valeur parmi non_conformite, observation, conformite ;
- "points_a_verifier" : liste (3 au plus) de ce que l'auditeur doit confirmer avant de valider.
Règles : n'invente aucun chiffre, aucun nom, aucune date absents des notes ; style professionnel, phrases courtes ;
pas de jugement sur les personnes. Réponds uniquement par un objet JSON avec exactement ces clés."""


def proposer_constat(audit, notes, risque=None):
    """Proposition de constat : (dict, origine). Ne lève jamais d'erreur."""
    mo = _moteur()
    donnees = {'notes_de_l_auditeur': notes,
               'mission': {'titre': audit.titre, 'objectifs': _t(audit.objectifs, 800), 'criteres_de_la_mission': _t(audit.criteres, 800),
                           'processus': audit.processus_audite_display if hasattr(audit, 'processus_audite_display') else ''},
               'risque_associe': risque}
    try:
        r = mo.demander_json(CONSIGNES_CONSTAT, donnees, max_tokens=1200, temperature=0.2)
        c = {'titre': _t(r.get('titre'), 150), 'fait': _t(r.get('fait'), 3000), 'critere': _t(r.get('critere'), 1500),
             'cause': _t(r.get('cause'), 1500), 'consequence': _t(r.get('consequence'), 1500),
             'recommandation': _t(r.get('recommandation'), 1500),
             'gravite': _choix(r.get('gravite'), GRAVITES, 'moyenne'), 'type': _choix(r.get('type'), TYPES, 'non_conformite'),
             'points_a_verifier': mo.liste_textes(r.get('points_a_verifier'), 3, 300)}
        if not c['fait']:
            raise mo.IndisponibleIA('réponse vide')
        return c, mo.IA
    except mo.IndisponibleIA:
        mo.marquer(mo.AUTO)
        return constat_automatique(notes), mo.AUTO


def constat_automatique(notes):
    """Sans IA : les notes deviennent le fait ; les autres rubriques sont signalées à compléter."""
    texte = _t(notes, 3000)
    gravite = 'majeure' if re.search(r'\b(fraude|détournement|detournement|absence totale|aucun contrôle|aucun controle)\b', texte, re.I) else 'moyenne'
    return {'titre': '', 'fait': texte, 'critere': '', 'cause': '', 'consequence': '', 'recommandation': '',
            'gravite': gravite, 'type': 'non_conformite',
            'points_a_verifier': ['Préciser le critère (procédure ou règle non respectée).',
                                  'Identifier la cause et la conséquence de l’écart.',
                                  'Formuler la recommandation.']}


@bp.route('/audit/<int:audit_id>/constat/proposer', methods=['POST'])
@login_required
def constat_proposer(audit_id):
    a = _audit(audit_id)
    if not fonction_active('redaction_constats'):
        return jsonify({'success': False, 'error': "La rédaction des constats par l'IA n'est pas activée."}), 403
    corps = request.get_json(silent=True) or request.form
    notes = _t(corps.get('notes'), NOTES_MAX)
    if len(notes) < 15:
        return jsonify({'success': False, 'error': 'Saisissez vos notes (au moins une phrase).'}), 400
    risque = None
    if corps.get('risque_id'):
        m = _m()
        try:
            rq = m.Risque.query.filter_by(id=int(corps.get('risque_id')), client_id=a.client_id).first()
        except (TypeError, ValueError):
            rq = None
        risque = {'reference': rq.reference, 'intitule': rq.intitule} if rq else None
    constat, origine = proposer_constat(a, notes, risque)
    journaliser('ia_constat_propose', {'audit': a.id, 'origine': origine}, client_id=a.client_id, valider=True)
    return jsonify({'success': True, 'constat': constat, 'origine': origine, 'origine_libelle': _moteur().libelle(origine)})


# ====================================================================== 2. premier jet du rapport
CONSIGNES_RAPPORT = """Tu es directeur de l'audit interne (Normes IIA 2024). Rédige en français, à partir des données de la mission
(constats, recommandations, tests, plans d'action, réponses des audités), deux textes pour le rapport d'audit :
- "resume" : le résumé exécutif destiné à la direction générale (10 à 18 lignes) : objectif et périmètre de la mission,
  appréciation d'ensemble, principaux constats par ordre de gravité (avec leur référence), priorités d'action ;
- "conclusion" : la conclusion de la mission (5 à 10 lignes), avec une opinion globale motivée parmi
  « satisfaisant », « à améliorer », « insatisfaisant », et les engagements pris par les audités s'il y en a ;
- "opinion" : une valeur parmi satisfaisant, a_ameliorer, insatisfaisant.
Règles : appuie-toi uniquement sur les données fournies ; reprends les chiffres exacts ; n'invente ni chiffre, ni nom,
ni date ; si une information manque, écris « À compléter : … » ; ton professionnel, factuel, sans jargon inutile.
Réponds uniquement par un objet JSON avec exactement ces clés."""
OPINIONS = {'satisfaisant': 'satisfaisant', 'a_ameliorer': 'à améliorer', 'insatisfaisant': 'insatisfaisant'}
CLOS = {'termine', 'terminee', 'clos', 'close', 'cloture', 'cloturee', 'realise', 'realisee'}


def _donnees_mission(audit):
    m = _m()
    constats = m.Constatation.query.filter_by(audit_id=audit.id).filter(m.Constatation.is_archived.isnot(True)).all()
    recos = m.Recommandation.query.filter_by(audit_id=audit.id).all()
    plans = m.PlanAction.query.filter_by(audit_id=audit.id).all() if hasattr(m.PlanAction, 'audit_id') else []
    ordre = {g: i for i, g in enumerate(('critique', 'majeure', 'moyenne', 'mineure'))}
    constats.sort(key=lambda c: (ordre.get((c.gravite or '').lower(), 9), c.reference or ''))
    tests = {'total': 0, 'conformes': 0, 'non_conformes': 0}
    try:
        feuilles = m.FeuilleTravail.query.filter_by(audit_id=audit.id).all()
        if feuilles:
            for t in m.TestControleFeuille.query.filter(m.TestControleFeuille.feuille_travail_id.in_([f.id for f in feuilles])).all():
                tests['total'] += 1
                if (t.resultat or '') == 'conforme':
                    tests['conformes'] += 1
                elif (t.resultat or '') == 'non_conforme':
                    tests['non_conformes'] += 1
    except Exception:  # noqa: BLE001
        pass
    return {
        'mission': {'reference': audit.reference, 'titre': audit.titre, 'type': audit.type_audit,
                    'objectifs': _t(audit.objectifs, 1200), 'perimetre': _t(audit.portee, 1200), 'criteres': _t(audit.criteres, 800),
                    'processus': getattr(audit, 'processus_audite_display', '') or '',
                    'debut': str(audit.date_debut_reelle or audit.date_debut_prevue or ''),
                    'fin': str(audit.date_fin_reelle or audit.date_fin_prevue or '')},
        'constats': [{'reference': c.reference, 'gravite': c.gravite, 'fait': _t(c.description, 900), 'critere': _t(c.critere, 300),
                      'cause': _t(c.cause_racine, 300), 'consequence': _t(c.consequence, 300),
                      'reponse_audite': _t(c.reponse_audite, 400), 'position_audite': c.position_audite} for c in constats[:40]],
        'recommandations': [{'reference': r.reference, 'description': _t(r.description, 500), 'statut': r.statut,
                             'echeance': str(r.date_echeance or '') if hasattr(r, 'date_echeance') else ''} for r in recos[:40]],
        'tests': tests,
        'plans_action': [{'nom': _t(getattr(p, 'nom', ''), 200), 'statut': getattr(p, 'statut', '')} for p in plans[:20]],
        'chiffres': {'constats': len(constats), 'par_gravite': {g: sum(1 for c in constats if (c.gravite or '').lower() == g) for g in ordre},
                     'recommandations': len(recos), 'recommandations_closes': sum(1 for r in recos if (r.statut or '') in CLOS)},
    }


def rapport_automatique(d):
    """Sans IA : résumé et conclusion composés à partir des chiffres de la mission (règles prédéfinies)."""
    mi, ch = d['mission'], d['chiffres']
    pg = ch['par_gravite']
    graves = pg.get('critique', 0) + pg.get('majeure', 0)
    lignes = [f"La mission {mi['reference']} « {mi['titre']} » "
              + (f"avait pour objectif : {mi['objectifs'].rstrip('.')}." if mi['objectifs'] else "— objectif : À compléter.")]
    if mi['perimetre']:
        lignes.append(f"Périmètre : {mi['perimetre'].rstrip('.')}.")
    if d['tests']['total']:
        lignes.append(f"{d['tests']['total']} test(s) de contrôle ont été réalisés, dont {d['tests']['non_conformes']} non conforme(s).")
    lignes.append(f"{ch['constats']} constat(s) ont été relevés : {pg.get('critique', 0)} critique(s), {pg.get('majeure', 0)} majeur(s), "
                  f"{pg.get('moyenne', 0)} moyen(s) et {pg.get('mineure', 0)} mineur(s).")
    principaux = [c for c in d['constats'] if (c['gravite'] or '').lower() in ('critique', 'majeure')][:3] or d['constats'][:3]
    for c in principaux:
        lignes.append(f"- {c['reference']} ({c['gravite'] or 'gravité à préciser'}) : {_t(c['fait'], 220)}")
    lignes.append(f"{ch['recommandations']} recommandation(s) ont été formulées.")
    opinion = 'insatisfaisant' if pg.get('critique', 0) else ('a_ameliorer' if graves or ch['constats'] else 'satisfaisant')
    conclusion = (f"Au vu des travaux réalisés, le dispositif audité est jugé {OPINIONS[opinion]}"
                  + (f", compte tenu de {graves} constat(s) critique(s) ou majeur(s)." if graves else ".")
                  + " La mise en œuvre des recommandations fera l'objet d'un suivi par l'audit interne. À compléter : engagements des audités.")
    return {'resume': '\n'.join(lignes), 'conclusion': conclusion, 'opinion': opinion}


def proposer_rapport(audit):
    mo = _moteur()
    d = _donnees_mission(audit)
    try:
        r = mo.demander_json(CONSIGNES_RAPPORT, d, max_tokens=1800, temperature=0.2)
        res = {'resume': _t(r.get('resume'), TEXTE_MAX).replace('\\n', '\n'), 'conclusion': _t(r.get('conclusion'), TEXTE_MAX).replace('\\n', '\n'),
               'opinion': _choix(r.get('opinion'), tuple(OPINIONS), '')}
        if not res['resume'] or not res['conclusion']:
            raise mo.IndisponibleIA('réponse incomplète')
        return res, mo.IA
    except mo.IndisponibleIA:
        mo.marquer(mo.AUTO)
        return rapport_automatique(d), mo.AUTO


def _redaction(audit):
    r = audit.redaction_rapport if isinstance(audit.redaction_rapport, dict) else {}
    return {'resume': r.get('resume', ''), 'conclusion': r.get('conclusion', ''), 'etat': r.get('etat', 'vide' if not r else 'brouillon'),
            'ia': bool(r.get('ia')), 'origine': r.get('origine', ''), 'par': r.get('par'), 'le': r.get('le'),
            'valide_par': r.get('valide_par'), 'valide_le': r.get('valide_le')}


def _nom(uid):
    if not uid:
        return ''
    u = _m().db.session.get(_m().User, uid)
    from egalyx.commun import nom_personne
    return nom_personne(u)


@bp.route('/audit/<int:audit_id>/redaction', methods=['GET'])
@login_required
def redaction(audit_id):
    a = _audit(audit_id)
    r = _redaction(a)
    return render_template('egalyx/ia_redaction_rapport.html', audit=a, r=r, fige=_fige(a),
                           ia_ok=fonction_active('premier_jet_rapport'), nom_par=_nom(r['par']), nom_valide=_nom(r['valide_par']),
                           opinions=OPINIONS)


@bp.route('/audit/<int:audit_id>/redaction/proposer', methods=['POST'])
@login_required
def redaction_proposer(audit_id):
    a = _audit(audit_id)
    if not fonction_active('premier_jet_rapport'):
        return jsonify({'success': False, 'error': "Le premier jet du rapport par l'IA n'est pas activé."}), 403
    res, origine = proposer_rapport(a)
    journaliser('ia_rapport_propose', {'audit': a.id, 'origine': origine}, client_id=a.client_id, valider=True)
    return jsonify({'success': True, **res, 'origine': origine, 'origine_libelle': _moteur().libelle(origine)})


@bp.route('/audit/<int:audit_id>/redaction', methods=['POST'])
@login_required
def redaction_enregistrer(audit_id):
    a = _audit(audit_id)
    m = _m()
    f = request.form
    action = f.get('action', 'brouillon')
    avant = _redaction(a)
    resume, conclusion = (f.get('resume') or '').strip()[:TEXTE_MAX], (f.get('conclusion') or '').strip()[:TEXTE_MAX]
    if action == 'retirer':
        nouveau = dict(a.redaction_rapport or {}, etat='brouillon', valide_par=None, valide_le=None)
        message = 'Validation retirée : le texte ne figure plus dans le rapport (brouillon conservé).'
    else:
        if action == 'valider' and not (resume and conclusion):
            flash('Pour valider, le résumé exécutif et la conclusion doivent être remplis.', 'warning')
            return redirect(url_for('.redaction', audit_id=a.id))
        maintenant = datetime.utcnow().isoformat(timespec='seconds')
        nouveau = {'resume': resume, 'conclusion': conclusion, 'ia': f.get('ia') == '1' or (avant['ia'] and resume == avant['resume']),
                   'origine': f.get('origine') or avant['origine'], 'par': current_user.id, 'le': maintenant,
                   'etat': 'valide' if action == 'valider' else 'brouillon',
                   'valide_par': current_user.id if action == 'valider' else None, 'valide_le': maintenant if action == 'valider' else None}
        message = ('Rédaction validée : elle figure désormais dans les rapports PDF et Word.' if action == 'valider'
                   else 'Brouillon enregistré (il ne figure pas encore dans le rapport).')
    a.redaction_rapport = nouveau
    try:
        from models import marquer_json_modifie
        marquer_json_modifie(a, 'redaction_rapport')
    except Exception:  # noqa: BLE001
        pass
    journaliser('rapport_redaction_' + ('validee' if nouveau.get('etat') == 'valide' else 'brouillon' if action != 'retirer' else 'retiree'),
                {'audit': a.id, 'ia': nouveau.get('ia', False)}, client_id=a.client_id)
    m.db.session.commit()
    flash(message, 'success')
    return redirect(url_for('.redaction', audit_id=a.id))


def enregistrer(app):
    if 'ia_audit' not in app.blueprints:
        app.register_blueprint(bp)
    app.jinja_env.globals['ia_audit_peut'] = lambda audit: peut_travailler(audit)


# ====================================================================== 3. préparation de la mission (étape 2)
# Taille d'échantillon usuelle selon la fréquence du contrôle (pratique courante en audit des contrôles).
ECHANTILLONS = [(('plusieurs fois par jour', 'multiple', 'continu', 'transaction', 'automatique'), 25),
                (('quotid', 'journal', 'jour'), 25), (('hebdo', 'semaine'), 10), (('mensu', 'mois'), 3),
                (('trimest',), 2), (('semest',), 2), (('annu', 'an'), 1)]
METHODES = ('aleatoire', 'systematique', 'jugement', 'exhaustif')
CRITICITES = ('critique', 'eleve', 'moyen', 'faible')
TESTS_MAX = 25

CONSIGNES_PREPARATION = """Tu es chef de mission d'audit interne (Normes IIA 2024). Prépare le programme de travail de la mission décrite,
à partir de ses objectifs, des risques du processus, des contrôles en place et des audits précédents. Réponds en français, en JSON :
- "objectifs" : 3 à 5 objectifs détaillés de la mission (une phrase chacun) ;
- "tests" : 6 à 15 tests d'audit, chacun avec :
    "titre" (court), "risque_ref" (référence du risque couvert, ou ""), "controle_ref" (référence du contrôle testé, ou ""),
    "objectif" (ce que le test démontre), "procedure" (étapes numérotées 1., 2., 3. …, concrètes),
    "criteres_acceptation" (ce qui rend le test conforme), "echantillon" (population et façon de sélectionner),
    "taille_echantillon" (entier), "methode" (aleatoire, systematique, jugement ou exhaustif), "periode" (période couverte),
    "pieces" (liste des pièces à obtenir), "criticite" (critique, eleve, moyen ou faible), "jours" (charge estimée en jours, nombre) ;
- "documents_a_demander" : liste des documents à demander aux audités avant le terrain ;
- "points_attention" : 2 à 5 points d'attention tirés des audits précédents et des risques les plus élevés.
Règles : un test au moins pour chaque risque élevé ou critique ; tester en priorité les contrôles clés ; reprendre les
recommandations encore ouvertes des audits précédents (test de suivi) ; tailles d'échantillon cohérentes avec la fréquence
du contrôle (quotidien ou plusieurs fois par jour : 25 ; hebdomadaire : 10 ; mensuel : 3 ; trimestriel : 2 ; annuel : 1) ;
n'invente ni référence de risque ou de contrôle, ni chiffre, ni nom absents des données ; ce qui manque : « À compléter »."""


def taille_selon_frequence(frequence, defaut=25):
    f = (frequence or '').lower()
    for mots, taille in ECHANTILLONS:
        if any(m in f for m in mots):
            return taille
    return defaut


def _rang(niveau):
    from egalyx.carto_processus import rang_niveau
    return rang_niveau(niveau)


def contexte_mission(audit):
    """Ce que l'IA (ou la proposition automatique) reçoit pour préparer la mission."""
    m = _m()
    from egalyx.carto_processus import _sans_accents as sa
    cid = audit.client_id
    processus = (getattr(audit, 'processus_audite_display', '') or '').strip()
    risques = {}
    for ar in m.AuditRisque.query.filter_by(audit_id=audit.id).all():
        r = m.db.session.get(m.Risque, ar.risque_id)
        if r is not None and r.client_id == cid and not r.is_archived:
            risques[r.id] = r
    pm_ids = set()
    if processus or audit.processus_id:
        for p in m.ProcessusMetier.query.filter_by(client_id=cid, is_archived=False).all():
            if (audit.processus_id and p.logigramme_id == audit.processus_id) or (processus and sa(p.nom) == sa(processus)):
                pm_ids.add(p.id)
                pm_ids.update(e.id for e in m.ProcessusMetier.query.filter_by(parent_id=p.id, client_id=cid).all())
    for r in m.Risque.query.filter_by(client_id=cid, is_archived=False).all():
        if r.id in risques:
            continue
        if getattr(r, 'processus_metier_associe_id', None) in pm_ids or (processus and sa(r.processus_concerne) == sa(processus)):
            risques[r.id] = r
    liste = sorted(risques.values(), key=lambda r: (-_rang(getattr(r, 'dernier_niveau_risque', None)), r.reference or ''))[:15]
    ids = [r.id for r in liste]
    controles = []
    if ids:
        for c in m.ControleProcessus.query.filter(m.ControleProcessus.risque_id.in_(ids), m.ControleProcessus.client_id == cid).all():
            if not c.is_archived:
                controles.append({'reference': c.reference, 'nom': c.nom, 'description': _t(c.description, 300), 'type': c.type_controle,
                                  'frequence': c.frequence, 'risque_id': c.risque_id, 'source': 'controle'})
        for d in m.DispositifMaitrise.query.filter(m.DispositifMaitrise.risque_id.in_(ids)).all():
            r = risques.get(d.risque_id)
            if r is not None and not getattr(d, 'is_archived', False):
                controles.append({'reference': d.reference, 'nom': d.nom, 'description': _t(d.description, 300), 'type': d.type_dispositif,
                                  'frequence': d.frequence, 'risque_id': d.risque_id, 'source': 'dispositif'})
    ref_risque = {r.id: r.reference for r in liste}
    controles = controles[:25]
    anterieurs = []
    if processus or audit.processus_id:
        q = m.Audit.query.filter(m.Audit.client_id == cid, m.Audit.id != audit.id)
        for a in q.all():
            if (audit.processus_id and a.processus_id == audit.processus_id) or (processus and sa(a.processus_concerne) == sa(processus)):
                anterieurs.append(a)
    from datetime import date as _date
    anterieurs = sorted(anterieurs, key=lambda a: a.date_fin_reelle or a.date_fin_prevue or (a.created_at.date() if a.created_at else _date.min),
                        reverse=True)[:3]
    passes = []
    for a in anterieurs:
        cs = m.Constatation.query.filter_by(audit_id=a.id).all()
        rs = [r for r in m.Recommandation.query.filter_by(audit_id=a.id).all() if (r.statut or '') not in CLOS]
        passes.append({'reference': a.reference, 'titre': a.titre, 'fin': str(a.date_fin_reelle or a.date_fin_prevue or ''),
                       'constats': [{'reference': c.reference, 'gravite': c.gravite, 'fait': _t(c.description, 250)} for c in cs[:8]],
                       'recommandations_ouvertes': [{'reference': r.reference, 'description': _t(r.description, 250), 'statut': r.statut} for r in rs[:8]]})
    entite = None
    try:
        e = m.EntiteAuditable.query.filter_by(client_id=cid, actif=True).filter(
            (m.EntiteAuditable.processus_id == audit.processus_id) if audit.processus_id else (m.EntiteAuditable.nom == processus)).first()
        if e:
            entite = {'nom': e.nom, 'niveau_risque': e.niveau_risque, 'commentaire': _t(e.commentaire, 300)}
    except Exception:  # noqa: BLE001
        pass
    return {
        'mission': {'reference': audit.reference, 'titre': audit.titre, 'type': audit.type_audit, 'processus': processus,
                    'objectifs': _t(audit.objectifs, 1200), 'perimetre': _t(audit.portee, 1200), 'criteres': _t(audit.criteres, 800),
                    'debut': str(audit.date_debut_prevue or ''), 'fin': str(audit.date_fin_prevue or '')},
        'risques': [{'reference': r.reference, 'intitule': _t(r.intitule, 200), 'niveau': getattr(r, 'dernier_niveau_risque', None) or 'non évalué',
                     'description': _t(getattr(r, 'description', ''), 300)} for r in liste],
        'controles': [{**{k: v for k, v in c.items() if k != 'risque_id'}, 'risque_ref': ref_risque.get(c['risque_id'], '')} for c in controles],
        'audits_precedents': passes,
        'univers_audit': entite,
    }


def programme_automatique(ctx):
    """Sans IA : un test par contrôle, un test d'existence pour chaque risque sans contrôle, un test de suivi par recommandation ouverte."""
    tests = []
    niv = {r['reference']: _rang(r['niveau']) for r in ctx['risques']}
    crit = {4: 'critique', 3: 'eleve', 2: 'moyen', 1: 'faible', 0: 'moyen'}
    for c in ctx['controles']:
        n = taille_selon_frequence(c['frequence'])
        tests.append({'titre': f"Efficacité du contrôle « {c['nom'][:120]} »", 'risque_ref': c['risque_ref'], 'controle_ref': c['reference'],
                      'objectif': f"S'assurer que le contrôle est exécuté comme prévu ({c['frequence'] or 'fréquence à préciser'}) et qu'il couvre le risque {c['risque_ref']}.",
                      'procedure': "1. Obtenir la description du contrôle et la liste des occurrences de la période.\n"
                                   f"2. Sélectionner un échantillon de {n} occurrence(s).\n"
                                   "3. Pour chacune, vérifier la preuve d'exécution (visa, date, auteur habilité) et le traitement des anomalies.\n"
                                   "4. Documenter les écarts et en apprécier la cause.",
                      'criteres_acceptation': 'Contrôle exécuté, tracé et revu pour chaque élément de l’échantillon.',
                      'echantillon': 'Occurrences du contrôle sur la période auditée', 'taille_echantillon': n,
                      'methode': 'exhaustif' if n == 1 else 'aleatoire', 'periode': 'À compléter', 'pieces': ['Preuves d’exécution du contrôle'],
                      'criticite': crit[niv.get(c['risque_ref'], 0)], 'jours': 1 if n <= 5 else 2})
    couverts = {c['risque_ref'] for c in ctx['controles']}
    for r in ctx['risques']:
        if r['reference'] not in couverts:
            tests.append({'titre': f"Dispositif de maîtrise du risque {r['reference']}", 'risque_ref': r['reference'], 'controle_ref': '',
                          'objectif': f"Vérifier qu'un dispositif de maîtrise existe et fonctionne pour le risque « {r['intitule']} ».",
                          'procedure': "1. Interroger le responsable du processus sur les contrôles en place.\n"
                                       "2. Obtenir la documentation (procédure, délégations, paramétrages).\n"
                                       "3. Réaliser un test de cheminement sur une opération.\n4. Conclure sur la conception du dispositif.",
                          'criteres_acceptation': 'Dispositif documenté, adapté au risque et appliqué.', 'echantillon': 'Test de cheminement',
                          'taille_echantillon': 1, 'methode': 'jugement', 'periode': 'À compléter', 'pieces': ['Procédure', 'Organigramme et délégations'],
                          'criticite': crit[niv.get(r['reference'], 0)], 'jours': 1})
    for a in ctx['audits_precedents']:
        for rec in a['recommandations_ouvertes']:
            tests.append({'titre': f"Suivi de la recommandation {rec['reference']}", 'risque_ref': '', 'controle_ref': '',
                          'objectif': f"Vérifier la mise en œuvre de la recommandation de l'audit {a['reference']}.",
                          'procedure': "1. Obtenir les justificatifs de mise en œuvre.\n2. Vérifier leur effectivité sur un échantillon.\n3. Conclure : mise en œuvre, partielle ou non.",
                          'criteres_acceptation': 'Recommandation mise en œuvre et efficace.', 'echantillon': 'Justificatifs de mise en œuvre',
                          'taille_echantillon': 3, 'methode': 'jugement', 'periode': 'Depuis la recommandation', 'pieces': ['Justificatifs de mise en œuvre'],
                          'criticite': 'moyen', 'jours': 0.5})
    return {'objectifs': [o for o in [ctx['mission']['objectifs']] if o] or ['À compléter : objectifs de la mission.'],
            'tests': tests[:TESTS_MAX],
            'documents_a_demander': ['Procédures du processus en vigueur', 'Organigramme et matrice des délégations',
                                     'Liste des opérations de la période auditée', 'Rapports de contrôle de la période'],
            'points_attention': [f"Risque {r['reference']} ({r['niveau']}) : {r['intitule']}" for r in ctx['risques'] if _rang(r['niveau']) >= 3][:4]}


def _nettoyer_test(t, refs_risques, refs_controles):
    mo = _moteur()
    try:
        taille = max(0, min(500, int(float(t.get('taille_echantillon') or 0))))
    except (TypeError, ValueError):
        taille = 0
    try:
        jours = max(0.0, min(30.0, float(str(t.get('jours') or 0).replace(',', '.'))))
    except (TypeError, ValueError):
        jours = 0.0
    rr, rc = _t(t.get('risque_ref'), 50), _t(t.get('controle_ref'), 50)
    return {'titre': _t(t.get('titre'), 190) or 'Test', 'risque_ref': rr if rr in refs_risques else '',
            'controle_ref': rc if rc in refs_controles else '', 'objectif': _t(t.get('objectif'), 1000),
            'procedure': str(t.get('procedure') or '').strip()[:3000], 'criteres_acceptation': _t(t.get('criteres_acceptation'), 1000),
            'echantillon': _t(t.get('echantillon'), 500), 'taille_echantillon': taille,
            'methode': _choix(t.get('methode'), METHODES, 'aleatoire'), 'periode': _t(t.get('periode'), 190),
            'pieces': mo.liste_textes(t.get('pieces'), 8, 200), 'criticite': _choix(t.get('criticite'), CRITICITES, 'moyen'),
            'jours': round(jours, 1)}


def proposer_programme(audit):
    mo = _moteur()
    ctx = contexte_mission(audit)
    refs_r = {r['reference'] for r in ctx['risques']}
    refs_c = {c['reference'] for c in ctx['controles']}
    try:
        r = mo.demander_json(CONSIGNES_PREPARATION, ctx, max_tokens=4000, temperature=0.2)
        tests = [_nettoyer_test(t, refs_r, refs_c) for t in (r.get('tests') or [])[:TESTS_MAX] if isinstance(t, dict)]
        if not tests:
            raise mo.IndisponibleIA('aucun test proposé')
        prog = {'objectifs': mo.liste_textes(r.get('objectifs'), 6, 400), 'tests': tests,
                'documents_a_demander': mo.liste_textes(r.get('documents_a_demander'), 15, 200),
                'points_attention': mo.liste_textes(r.get('points_attention'), 6, 400)}
        origine = mo.IA
    except mo.IndisponibleIA:
        mo.marquer(mo.AUTO)
        prog = programme_automatique(ctx)
        prog['tests'] = [_nettoyer_test(t, refs_r, refs_c) for t in prog['tests']]
        origine = mo.AUTO
    prog['contexte'] = {'risques': len(ctx['risques']), 'controles': len(ctx['controles']), 'audits_precedents': len(ctx['audits_precedents']),
                        'recommandations_ouvertes': sum(len(a['recommandations_ouvertes']) for a in ctx['audits_precedents'])}
    return prog, origine


@bp.route('/audit/<int:audit_id>/preparation', methods=['GET'])
@login_required
def preparation(audit_id):
    a = _audit(audit_id)
    ctx = contexte_mission(a)
    m = _m()
    nb_feuilles = m.FeuilleTravail.query.filter_by(audit_id=a.id).filter(m.FeuilleTravail.is_archived.isnot(True)).count()
    return render_template('egalyx/ia_preparation_mission.html', audit=a, ctx=ctx, fige=_fige(a), nb_feuilles=nb_feuilles,
                           ia_ok=fonction_active('preparation_mission'))


@bp.route('/audit/<int:audit_id>/preparation/proposer', methods=['POST'])
@login_required
def preparation_proposer(audit_id):
    a = _audit(audit_id)
    if fonction_active('preparation_mission'):
        prog, origine = proposer_programme(a)
    else:                                         # IA coupée : programme type à partir des contrôles, sans IA
        ctx = contexte_mission(a)
        prog = programme_automatique(ctx)
        refs_r, refs_c = {r['reference'] for r in ctx['risques']}, {c['reference'] for c in ctx['controles']}
        prog['tests'] = [_nettoyer_test(t, refs_r, refs_c) for t in prog['tests']]
        prog['contexte'] = {'risques': len(ctx['risques']), 'controles': len(ctx['controles']),
                            'audits_precedents': len(ctx['audits_precedents']), 'recommandations_ouvertes': 0}
        origine = _moteur().AUTO
        _moteur().marquer(origine)
    journaliser('ia_preparation_proposee', {'audit': a.id, 'origine': origine, 'tests': len(prog['tests'])}, client_id=a.client_id, valider=True)
    return jsonify({'success': True, **prog, 'origine': origine, 'origine_libelle': _moteur().libelle(origine)})


def _reference_feuille(cid):
    m = _m()
    annee = datetime.now().year
    n = m.FeuilleTravail.query.filter(m.FeuilleTravail.reference.like(f'FT-{annee}-%'), m.FeuilleTravail.client_id == cid).count() + 1
    while m.FeuilleTravail.query.filter_by(client_id=cid, reference=f'FT-{annee}-{n:04d}').first():
        n += 1
    return f'FT-{annee}-{n:04d}'


@bp.route('/audit/<int:audit_id>/preparation/creer', methods=['POST'])
@login_required
def preparation_creer(audit_id):
    """Crée les feuilles de travail (une par risque couvert, plus « tests transverses ») et leurs tests."""
    a = _audit(audit_id)
    m = _m()
    corps = request.get_json(silent=True) or {}
    ctx = contexte_mission(a)
    refs_r = {r['reference'] for r in ctx['risques']}
    refs_c = {c['reference'] for c in ctx['controles']}
    tests = [_nettoyer_test(t, refs_r, refs_c) for t in (corps.get('tests') or [])[:TESTS_MAX] if isinstance(t, dict)]
    if not tests:
        return jsonify({'success': False, 'error': 'Cochez au moins un test.'}), 400
    risques = {r.reference: r for r in m.Risque.query.filter(m.Risque.client_id == a.client_id, m.Risque.reference.in_(refs_r)).all()} if refs_r else {}
    controles = {c.reference: c for c in m.ControleProcessus.query.filter(m.ControleProcessus.client_id == a.client_id,
                                                                          m.ControleProcessus.reference.in_(refs_c)).all()} if refs_c else {}
    groupes = {}
    for t in tests:
        groupes.setdefault(t['risque_ref'], []).append(t)
    origine = _t(corps.get('origine'), 20)
    feuilles = []
    for ref, lst in sorted(groupes.items(), key=lambda x: (x[0] == '', x[0])):
        r = risques.get(ref)
        f = m.FeuilleTravail(reference=_reference_feuille(a.client_id), audit_id=a.id, client_id=a.client_id, type_feuille='test',
                             statut='brouillon', titre=(f'Risque {ref} — {r.intitule}' if r else 'Tests transverses et suivi des recommandations')[:200],
                             description=('Programme de travail préparé ' + ('avec l’IA' if origine == 'ia' else 'automatiquement')
                                          + ' puis retenu par ' + nom_personne(current_user) + '.'),
                             risque_id=r.id if r else None, preparee_par_id=current_user.id, created_by=current_user.id,
                             contenu={'preparation': {'origine': origine or 'manuel', 'le': datetime.utcnow().isoformat(timespec='seconds')}})
        m.db.session.add(f)
        m.db.session.flush()
        for i, t in enumerate(lst):
            c = controles.get(t['controle_ref'])
            if c is not None and f.controle_id is None and len(lst) == 1:
                f.controle_id = c.id
            pieces = ('\n\nPièces à obtenir :\n- ' + '\n- '.join(t['pieces'])) if t['pieces'] else ''
            test = m.TestControleFeuille(
                feuille_travail_id=f.id, objet_test=t['titre'], objectif_controle=t['objectif'],
                reference_norme=(t['controle_ref'] or None), procedure=t['procedure'] + pieces,
                criteres_acceptation=t['criteres_acceptation'], echantillon=t['echantillon'],
                methode_echantillonnage=t['methode'], taille_echantillon=t['taille_echantillon'] or None,
                periode_couverte=t['periode'] or None, niveau_criticite=t['criticite'],
                temps_passe_minutes=None, ordre=i)
            if r is not None and hasattr(test, 'risques_associes'):
                test.risques_associes.append(r)          # la criticité du test suit alors celle du risque (règle de l'outil)
            m.db.session.add(test)
        feuilles.append(f)
    docs = [d for d in (corps.get('documents') or []) if isinstance(d, str) and d.strip()][:20]
    if docs:
        f = m.FeuilleTravail(reference=_reference_feuille(a.client_id), audit_id=a.id, client_id=a.client_id, type_feuille='checklist',
                             statut='brouillon', titre='Documents à demander aux audités',
                             description='\n'.join('- ' + _t(d, 200) for d in docs), preparee_par_id=current_user.id, created_by=current_user.id,
                             contenu={'checklist': [{'libelle': _t(d, 200), 'fait': False} for d in docs]})
        m.db.session.add(f)
        feuilles.append(f)
    journaliser('ia_preparation_creee', {'audit': a.id, 'feuilles': len(feuilles), 'tests': len(tests), 'origine': origine}, client_id=a.client_id)
    m.db.session.commit()
    flash(f'{len(feuilles)} feuille(s) de travail créée(s) avec {len(tests)} test(s). Complétez-les puis réalisez les tests.', 'success')
    return jsonify({'success': True, 'feuilles': [f.reference for f in feuilles], 'retour': url_for('detail_audit', id=a.id)})

"""
egalyx/ia_honnete.py — l'« IA » dit la vérité.

  - les contenus de secours (modèles types, règles) des services existants sont signalés comme « automatiques » :
    les réponses JSON portent « origine » et l'écran l'affiche (templates/egalyx/_ia_origine.html) ;
  - l'analyse d'un incident et les recommandations du contrôle de niveau 2 (C2N) appellent réellement l'IA,
    et retombent sur des règles annoncées comme telles quand l'IA n'est pas disponible ;
  - plus de « score de confiance » inventé.
"""
import functools
import json
import logging
import sys

from flask import current_app, flash, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

from egalyx import ia_moteur as moteur

journal = logging.getLogger('egalyx.ia_honnete')


# ------------------------------------------------------------------ signaler les contenus de secours
def _auto(f):
    if getattr(f, '_egalyx_auto', False):
        return f

    @functools.wraps(f)
    def enveloppe(*a, **k):
        moteur.marquer(moteur.AUTO)
        return f(*a, **k)
    enveloppe._egalyx_auto = True
    return enveloppe


def _envelopper_methodes(module, classe, noms):
    try:
        cls = getattr(__import__(module, fromlist=[classe]), classe)
    except Exception:
        return 0
    n = 0
    for nom in noms:
        brut = cls.__dict__.get(nom)
        if brut is None:
            continue
        if isinstance(brut, classmethod):
            setattr(cls, nom, classmethod(_auto(brut.__func__)))
        elif isinstance(brut, staticmethod):
            setattr(cls, nom, staticmethod(_auto(brut.__func__)))
        else:
            setattr(cls, nom, _auto(brut))
        n += 1
    return n


def _envelopper_vue(app, endpoint):
    vue = app.view_functions.get(endpoint)
    if vue is not None:
        app.view_functions[endpoint] = _auto(vue)
        return 1
    return 0


# ------------------------------------------------------------------ incidents
def analyse_ia_incident(id):
    import models as M
    from models import db
    from services.incident_ia_service import IncidentIAService
    app_mod = sys.modules[current_app.import_name]
    incident = app_mod.get_client_object_or_404(M.Incident, id)
    try:
        analyse = IncidentIAService.analyser_incident(incident)
        db.session.add(M.IncidentHistorique(incident_id=id, action='analyse_ia', utilisateur_id=current_user.id,
                                            details=json.dumps({'origine': analyse.get('origine'), 'modele': analyse.get('modele')})))
        db.session.commit()
        if analyse.get('origine') == 'ia':
            flash("Analyse rédigée par l'IA : vérifiez les pistes proposées avant de les retenir.", 'success')
        else:
            flash("L'IA n'est pas disponible : une analyse automatique simple (sans IA) a été produite.", 'info')
    except Exception as e:
        db.session.rollback()
        journal.exception("analyse incident %s", id)
        flash(f"Analyse impossible : {e}", 'error')
    return redirect(url_for('detail_incident', id=id))


# ------------------------------------------------------------------ contrôle de niveau 2 : recommandations
CONSIGNES_C2N = """Tu es un expert du contrôle interne de niveau 2. On te donne un contrôle planifié et le résultat de son exécution.
Propose des recommandations concrètes et propres À CE CONTRÔLE, fondées uniquement sur les données (taux de conformité,
anomalies, volumes, commentaires, conclusion). N'invente aucun chiffre. Pas de recommandation générique (« former les équipes »,
« automatiser ») sauf si les données la justifient explicitement. Français professionnel.
Réponds {"recommandations": [{"titre": "...", "description": "1 à 2 phrases", "priorite": "haute|moyenne|basse",
"categorie": "processus|technique|formation|organisation|documentation"}]} : 1 à 4 recommandations, la plus urgente d'abord.
Si l'exécution montre un contrôle conforme sans anomalie, renvoie une liste vide."""
CATEGORIES_C2N = {'processus', 'technique', 'formation', 'organisation', 'documentation'}


def _recos_c2n_regles(p):
    e = p.execution
    recos = []
    if e is None:
        return recos
    if e.taux_conformite is not None and e.taux_conformite < 70:
        recos.append({'titre': 'Analyser les causes de non-conformité', 'priorite': 'haute', 'categorie': 'processus',
                      'description': f"Le taux de conformité de {e.taux_conformite:g} % est inférieur au seuil de 70 % : "
                                     "analysez les causes des anomalies et renforcez le contrôle."})
    if (e.volume_previsionnel or 0) and (e.volume_controle or 0) < e.volume_previsionnel:
        recos.append({'titre': "Compléter l'échantillon", 'priorite': 'moyenne', 'categorie': 'processus',
                      'description': f"Seulement {e.volume_controle}/{e.volume_previsionnel} éléments contrôlés : "
                                     "étendez l'échantillon pour fiabiliser la conclusion."})
    if (e.nb_anomalies or 0) > 0 and not (e.conclusion or '').strip():
        recos.append({'titre': 'Documenter la conclusion du contrôle', 'priorite': 'moyenne', 'categorie': 'documentation',
                      'description': f"{e.nb_anomalies} anomalie(s) relevée(s) sans conclusion écrite."})
    return recos


def c2n_generer_recommandations_ia():
    import models as M
    from models import db
    app_mod = sys.modules[current_app.import_name]
    data = request.get_json(silent=True) or {}
    try:
        p = app_mod.get_client_object_or_404(M.PlanificationControle, int(data.get('planification_id') or 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'planification_id requis'}), 400
    try:
        e, ref = p.execution, getattr(p, 'referentiel', None)
        donnees = {
            'controle': {'code': getattr(ref, 'code_controle', None), 'nom': getattr(ref, 'nom', None),
                         'objectif': moteur.texte(getattr(ref, 'objectif', None), 800),
                         'risques_couverts': moteur.texte(getattr(ref, 'risques_couverts', None), 600),
                         'processus': getattr(ref, 'processus', None)},
            'planification': {'reference': p.reference, 'perimetre': p.perimetre, 'type_test': p.type_test, 'statut': p.statut},
            'execution': None if e is None else {
                'taux_conformite': e.taux_conformite, 'volume_previsionnel': e.volume_previsionnel,
                'volume_controle': e.volume_controle, 'nb_conformes': e.nb_conformes, 'nb_anomalies': e.nb_anomalies,
                'gravite_deficience': e.gravite_deficience, 'resultats': moteur.texte(e.resultats, 1500),
                'commentaires': moteur.texte(e.commentaires, 1000), 'conclusion': moteur.texte(e.conclusion, 800)},
        }
        recos, source = None, 'ia'
        try:
            r = moteur.demander_json(CONSIGNES_C2N, donnees, max_tokens=900)
            recos = []
            for x in (r.get('recommandations') or [])[:4]:
                if isinstance(x, dict) and moteur.texte(x.get('titre')):
                    cat = moteur.texte(x.get('categorie'), 30).lower()
                    recos.append({'titre': moteur.texte(x.get('titre'), 200), 'description': moteur.texte(x.get('description'), 800),
                                  'priorite': moteur.priorite(x.get('priorite')),
                                  'categorie': cat if cat in CATEGORIES_C2N else 'processus'})
        except moteur.IndisponibleIA:
            moteur.marquer(moteur.AUTO)
            recos, source = _recos_c2n_regles(p), 'automatique'

        existantes = {(r.titre or '').strip().lower() for r in
                      M.RecommandationC2N.query.filter_by(planification_id=p.id, client_id=current_user.client_id)}
        nouvelles = []
        for d in recos:
            if d['titre'].strip().lower() in existantes:
                continue
            reco = M.RecommandationC2N(planification_id=p.id, titre=d['titre'], description=d['description'],
                                       priorite=d['priorite'], categorie=d['categorie'], source=source, statut='proposee',
                                       created_by=current_user.id, client_id=current_user.client_id)
            db.session.add(reco)
            nouvelles.append(reco)
        db.session.commit()
        try:
            app_mod.log_activity(current_user.id, 'c2n_generate_ia_recommandations',
                                 f"{len(nouvelles)} recommandation(s) ({source}) pour la planification {p.reference}",
                                 'c2n_planification', p.id)
        except Exception:
            pass
        if source == 'ia':
            msg = (f"{len(nouvelles)} recommandation(s) rédigée(s) par l'IA à partir des résultats du contrôle."
                   if nouvelles else "L'IA ne propose pas de nouvelle recommandation pour ce contrôle.")
        else:
            msg = (f"IA indisponible : {len(nouvelles)} recommandation(s) proposée(s) par les règles automatiques."
                   if nouvelles else "IA indisponible, et les règles automatiques ne relèvent aucun écart à traiter.")
        return jsonify({'success': True, 'message': msg, 'source': source,
                        'recommandations': [r.to_dict() for r in nouvelles]})
    except Exception as e:
        db.session.rollback()
        journal.exception("recommandations C2N")
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------ KRI : modèles types (sans IA)
def suggestions_kris_fallback(risque_id):
    """Modèles d'indicateurs types pour un risque, présentés comme tels (plus de « score de confiance 85 % » inventé ;
    corrige aussi l'erreur quand la catégorie du risque est vide)."""
    import models as M
    from datetime import datetime
    app_mod = sys.modules[current_app.import_name]
    risque = app_mod.get_client_object_or_404(M.Risque, risque_id)
    moteur.marquer(moteur.AUTO)
    ref, intitule = risque.reference or f"R-{risque.id}", risque.intitule or "ce risque"
    s = [
        {"nom": f"Taux d'occurrence - {ref}", "description": f"Fréquence d'apparition du risque : {intitule}",
         "formule_calcul": "(Nombre d'occurrences / Période) × 100", "unite_mesure": "%", "categorie": "operationnel",
         "seuil_alerte": 5.0, "seuil_critique": 10.0, "sens_evaluation_seuil": "superieur", "frequence_mesure": "mensuel",
         "justification": "Indicateur de base pour surveiller la fréquence du risque"},
        {"nom": f"Impact moyen - {ref}", "description": f"Impact financier moyen du risque {intitule}",
         "formule_calcul": "Somme des impacts / Nombre d'occurrences", "unite_mesure": "€", "categorie": "financier",
         "seuil_alerte": 5000.0, "seuil_critique": 10000.0, "sens_evaluation_seuil": "superieur",
         "frequence_mesure": "trimestriel", "justification": "Mesure l'impact financier du risque"},
    ]
    categorie = str(getattr(risque, 'categorie', '') or '').lower()
    if 'securite' in categorie or 'sécurité' in categorie or 'conformite' in categorie or 'conformité' in categorie:
        s.append({"nom": f"Taux de conformité - {ref}", "description": "Pourcentage de conformité aux exigences",
                  "formule_calcul": "(Nombre de contrôles conformes / Total des contrôles) × 100", "unite_mesure": "%",
                  "categorie": "conformite", "seuil_alerte": 90.0, "seuil_critique": 80.0, "sens_evaluation_seuil": "inferieur",
                  "frequence_mesure": "trimestriel", "justification": "Surveille le niveau de conformité"})
    for x in s:
        x['_metadata'] = {'generated_at': datetime.utcnow().isoformat(), 'mode': 'modele_type'}
    return jsonify({'success': True, 'risque_id': risque.id, 'risque_reference': risque.reference, 'suggestions': s,
                    'count': len(s), 'metadata': {'generated_at': datetime.utcnow().isoformat(), 'mode': 'fallback',
                                                  'note': "Modèles types (sans IA) : à adapter à votre risque."}})


# ------------------------------------------------------------------ enregistrement
def enregistrer(app):
    moteur.enregistrer(app)
    n = 0
    n += _envelopper_methodes('services.analyse_ia', 'ServiceAnalyseIA',
                              ['_simuler_analyse_detaille', '_simulation_par_defaut', '_simuler_lettre_mission'])
    n += _envelopper_methodes('services.kri_ia_service', 'KRIIAService', ['_simuler_generation_kri'])
    n += _envelopper_methodes('services.ia_veille_service', 'MoteurSuggestionLocal', ['analyser'])
    module_app = sys.modules.get(app.import_name)
    for nom in ('simuler_plan_action', 'simuler_reponse_ia_constats'):
        f = getattr(module_app, nom, None)
        if callable(f):
            setattr(module_app, nom, _auto(f))
            n += 1
    for endpoint, vue in (('analyse_ia_incident', analyse_ia_incident),
                          ('c2n_generer_recommandations_ia', c2n_generer_recommandations_ia),
                          ('suggestions_kris_fallback', suggestions_kris_fallback)):
        if endpoint in app.view_functions:
            app.view_functions[endpoint] = login_required(vue)
            n += 1
    journal.info("IA honnête : %s point(s) branché(s)", n)
    return n

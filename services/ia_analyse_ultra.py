# services/ia_analyse_ultra.py
import os
import json
from datetime import datetime, timedelta
from openai import OpenAI
from flask import current_app, session
import re

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = None

if OPENAI_API_KEY and OPENAI_API_KEY != "mode-simulation" and OPENAI_API_KEY.startswith("sk-") and len(OPENAI_API_KEY) >= 30:  # toutes les clés OpenAI actuelles (sk-proj-…, sk-svcacct-…)
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI client initialisé pour Analyse Ultra")
    except Exception as e:
        print(f"⚠️ Erreur initialisation OpenAI: {e}")
        client = None


class IAAnalyseUltraService:
    """
    Service d'analyse IA ULTRA complet
    Analyse TOUTES les données disponibles
    """

    @staticmethod
    def _is_ia_available():
        return client is not None

    @staticmethod
    def analyser_complet(cartographie, risques, evaluations, dispositifs, incidents, 
                         demandes_reevaluation, constats_audit, plans_action, 
                         commentaires, historique_modifications):
        """
        ANALYSE COMPLÈTE ULTRA - Prend en compte TOUTES les données
        
        Args:
            cartographie: Objet Cartographie
            risques: Liste des risques
            evaluations: Liste des évaluations
            dispositifs: Liste des dispositifs
            incidents: Liste des incidents
            demandes_reevaluation: Liste des demandes de réévaluation
            constats_audit: Liste des constats d'audit
            plans_action: Liste des plans d'action
            commentaires: Liste des commentaires (toutes sources)
            historique_modifications: Historique des modifications
        """
        
        # 1. Collecter et structurer TOUTES les données
        donnees = IAAnalyseUltraService._collecter_donnees(
            cartographie, risques, evaluations, dispositifs, incidents,
            demandes_reevaluation, constats_audit, plans_action,
            commentaires, historique_modifications
        )
        
        # 2. Analyser avec IA si disponible
        if IAAnalyseUltraService._is_ia_available():
            try:
                resultat_ia = IAAnalyseUltraService._analyser_avec_ia(donnees)
                return resultat_ia
            except Exception as e:
                print(f"❌ Erreur IA: {e}")
                # Fallback vers analyse locale
                return IAAnalyseUltraService._analyser_local(donnees)
        
        # 3. Analyse locale (fallback)
        return IAAnalyseUltraService._analyser_local(donnees)

    # ============================================================
    # COLLECTE DES DONNÉES - TOUT
    # ============================================================
    @staticmethod
    def _collecter_donnees(cartographie, risques, evaluations, dispositifs, incidents,
                           demandes_reevaluation, constats_audit, plans_action,
                           commentaires, historique_modifications):
        """Collecte et structure TOUTES les données"""
        
        maintenant = datetime.now()
        date_limite = maintenant - timedelta(days=365)
        
        donnees = {
            'cartographie': {
                'nom': cartographie.nom,
                'description': cartographie.description,
                'date_creation': cartographie.created_at.isoformat() if cartographie.created_at else None,
                'statut': 'active'
            },
            'risques': [],
            'evaluations': [],
            'dispositifs': [],
            'incidents': [],
            'demandes_reevaluation': [],
            'constats_audit': [],
            'plans_action': [],
            'commentaires': [],
            'historique': [],
            'statistiques': {},
            'analyses_textuelles': {
                'commentaires_risques': [],
                'commentaires_evaluations': [],
                'commentaires_validation': [],
                'commentaires_confirmation': [],
                'justifications': [],
                'observations': []
            }
        }
        
        # 1. Risques
        for r in risques:
            donnees['risques'].append({
                'id': r.id,
                'reference': r.reference,
                'intitule': r.intitule,
                'description': r.description,
                'categorie': r.categorie,
                'type_risque': r.type_risque,
                'processus_concerne': r.processus_concerne,
                'cause_racine': r.cause_racine,
                'consequences': r.consequences,
                'date_creation': r.created_at.isoformat() if r.created_at else None,
                'is_archived': r.is_archived
            })
        
        # 2. Évaluations - AVEC TOUS LES COMMENTAIRES
        for e in evaluations:
            # Récupérer les valeurs finales
            impact = e.impact_conf or e.impact_val or e.impact_pre
            probabilite = e.probabilite_conf or e.probabilite_val or e.probabilite_pre
            niveau_maitrise = e.niveau_maitrise_conf or e.niveau_maitrise_val or e.niveau_maitrise_pre
            
            donnees['evaluations'].append({
                'id': e.id,
                'risque_id': e.risque_id,
                'campagne_nom': e.campagne_nom,
                'date_pre_evaluation': e.date_pre_evaluation.isoformat() if e.date_pre_evaluation else None,
                'date_validation': e.date_validation.isoformat() if e.date_validation else None,
                'date_confirmation': e.date_confirmation.isoformat() if e.date_confirmation else None,
                'impact_pre': e.impact_pre,
                'probabilite_pre': e.probabilite_pre,
                'niveau_maitrise_pre': e.niveau_maitrise_pre,
                'impact_val': e.impact_val,
                'probabilite_val': e.probabilite_val,
                'niveau_maitrise_val': e.niveau_maitrise_val,
                'impact_conf': e.impact_conf,
                'probabilite_conf': e.probabilite_conf,
                'niveau_maitrise_conf': e.niveau_maitrise_conf,
                'score_risque': e.score_risque,
                'niveau_risque': e.niveau_risque,
                'statut_validation': e.statut_validation,
                # ✅ TOUS LES COMMENTAIRES
                'commentaire_pre_evaluation': e.commentaire_pre_evaluation,
                'commentaire_validation': e.commentaire_validation,
                'commentaire_confirmation': e.commentaire_confirmation,
                # Métadonnées
                'metadonnees': e.metadonnees,
                'origine': e.origine,
                'audit_id': e.audit_id,
                'constat_id': e.constat_id
            })
            
            # Collecter les commentaires textuels
            if e.commentaire_pre_evaluation:
                donnees['analyses_textuelles']['commentaires_risques'].append({
                    'evaluation_id': e.id,
                    'phase': 'pre_evaluation',
                    'texte': e.commentaire_pre_evaluation
                })
            if e.commentaire_validation:
                donnees['analyses_textuelles']['commentaires_evaluations'].append({
                    'evaluation_id': e.id,
                    'phase': 'validation',
                    'texte': e.commentaire_validation
                })
            if e.commentaire_confirmation:
                donnees['analyses_textuelles']['commentaires_confirmation'].append({
                    'evaluation_id': e.id,
                    'phase': 'confirmation',
                    'texte': e.commentaire_confirmation
                })
        
        # 3. Dispositifs
        for d in dispositifs:
            donnees['dispositifs'].append({
                'id': d.id,
                'reference': d.reference,
                'nom': d.nom,
                'type_dispositif': d.type_dispositif,
                'efficacite_attendue': d.efficacite_attendue,
                'efficacite_reelle': d.efficacite_reelle,
                'couverture': d.couverture,
                'statut': d.statut,
                'date_derniere_verification': d.date_derniere_verification.isoformat() if d.date_derniere_verification else None,
                'commentaire_evaluation': d.commentaire_evaluation,
                'risque_id': d.risque_id
            })
        
        # 4. Incidents
        for i in incidents:
            donnees['incidents'].append({
                'id': i.id,
                'reference': i.reference,
                'titre': i.titre,
                'description': i.description,
                'gravite': i.gravite,
                'date_occurrence': i.date_occurrence.isoformat() if i.date_occurrence else None,
                'risque_id': i.risque_id,
                'dispositif_id': i.dispositif_id,
                'cause_racine': i.cause_racine,
                'actions_correctives': i.actions_correctives,
                'statut': i.statut
            })
        
        # 5. Demandes de réévaluation
        for d in demandes_reevaluation:
            donnees['demandes_reevaluation'].append({
                'id': d.id,
                'reference': d.reference,
                'justification': d.justification,
                'statut': d.statut,
                'date_demande': d.date_demande.isoformat() if d.date_demande else None,
                'impact_propose': d.impact_propose,
                'probabilite_propose': d.probabilite_propose,
                'score_propose': d.score_propose,
                'niveau_risque_propose': d.niveau_risque_propose,
                'risque_id': d.risque_id
            })
        
        # 6. Constats d'audit
        for c in constats_audit:
            donnees['constats_audit'].append({
                'id': c.id,
                'reference': c.reference,
                'description': c.description,
                'statut': c.statut,
                'gravite': c.gravite,
                'risque_id': c.risque_id,
                'date_creation': c.created_at.isoformat() if c.created_at else None
            })
        
        # 7. Plans d'action
        for p in plans_action:
            donnees['plans_action'].append({
                'id': p.id,
                'reference': p.reference,
                'nom': p.nom,
                'description': p.description,
                'statut': p.statut,
                'pourcentage_realisation': p.pourcentage_realisation,
                'date_debut': p.date_debut.isoformat() if p.date_debut else None,
                'date_fin_prevue': p.date_fin_prevue.isoformat() if p.date_fin_prevue else None,
                'risque_id': p.risque_id,
                'responsable': p.responsable.username if p.responsable else None
            })
        
        # 8. Commentaires généraux
        for c in commentaires:
            donnees['commentaires'].append({
                'id': c.id,
                'contenu': c.contenu,
                'date': c.created_at.isoformat() if c.created_at else None,
                'utilisateur': c.utilisateur.username if c.utilisateur else None,
                'source': c.source_type
            })
        
        # 9. Statistiques
        donnees['statistiques'] = {
            'total_risques': len(risques),
            'total_evaluations': len(evaluations),
            'total_dispositifs': len(dispositifs),
            'total_incidents': len(incidents),
            'total_demandes_reevaluation': len(demandes_reevaluation),
            'total_constats_audit': len(constats_audit),
            'total_plans_action': len(plans_action),
            'total_commentaires': len(commentaires),
            'evaluations_confirmees': len([e for e in evaluations if e.date_confirmation]),
            'evaluations_validees': len([e for e in evaluations if e.date_validation and not e.date_confirmation]),
            'dispositifs_efficaces': len([d for d in dispositifs if d.efficacite_reelle and d.efficacite_reelle >= 4]),
            'incidents_recents': len([i for i in incidents if i.date_occurrence >= date_limite]),
            'taux_evaluation': round((len([e for e in evaluations if e.date_confirmation]) / len(risques) * 100), 1) if risques else 0
        }
        
        return donnees

    # ============================================================
    # ANALYSE AVEC IA - ULTRA PRÉCISE
    # ============================================================
    @staticmethod
    def _analyser_avec_ia(donnees):
        """Analyse avec OpenAI - Ultra précise"""
        
        try:
            # Construire le prompt ULTRA COMPLET
            prompt = IAAnalyseUltraService._construire_prompt_ultra(donnees)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """Tu es un expert en gestion des risques, audit et contrôle interne.
                    Tu analyses des cartographies des risques avec une précision exceptionnelle.
                    Tu prends en compte TOUTES les données : commentaires, évaluations, dispositifs, incidents, etc.
                    
                    RÈGLES D'ANALYSE :
                    1. Analyse SÉMANTIQUE des commentaires (sentiment, pertinence, profondeur)
                    2. Détecte les INCOHÉRENCES entre les évaluations et les commentaires
                    3. Identifie les TENDANCES et les CORRÉLATIONS
                    4. Évalue la QUALITÉ des évaluations
                    5. Propose des RECOMMANDATIONS STRATÉGIQUES
                    6. Identifie les RISQUES ÉMERGENTS
                    7. Évalue la MATURITÉ de la gestion des risques
                    
                    Réponds au format JSON avec les clés suivantes :
                    - score_global: nombre (0-100)
                    - niveau_maturite: string (excellent/bon/moyen/faible/critique)
                    - synthese: string (résumé en langage naturel)
                    - analyse_detailee: objet avec sections
                    - forces: liste des points forts
                    - faiblesses: liste des points faibles
                    - opportunites: liste des opportunités
                    - menaces: liste des menaces
                    - recommandations: liste d'objets avec titre, description, priorite, actions
                    - alertes: liste des alertes avec niveau et message
                    - tendances: liste des tendances identifiées
                    - risques_emergents: liste des risques émergents
                    - plan_action: liste des actions recommandées"""},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            
            resultat = json.loads(response.choices[0].message.content)
            
            # Ajouter les métadonnées
            resultat['source'] = 'ia'
            resultat['date_analyse'] = datetime.now().isoformat()
            resultat['version'] = '2.0'
            resultat['analyse_textuelle'] = IAAnalyseUltraService._analyser_textes_commentaires(donnees)
            
            return resultat
            
        except Exception as e:
            print(f"❌ Erreur IA: {e}")
            import traceback
            traceback.print_exc()
            return IAAnalyseUltraService._analyser_local(donnees)

    # ============================================================
    # PROMPT ULTRA COMPLET
    # ============================================================
    @staticmethod
    def _construire_prompt_ultra(donnees):
        """Construit un prompt ULTRA complet pour l'IA"""
        
        return f"""
        ANALYSE COMPLÈTE DE LA CARTOGRAPHIE DES RISQUES
        ================================================
        
        📋 INFORMATIONS GÉNÉRALES
        Nom: {donnees['cartographie']['nom']}
        Description: {donnees['cartographie']['description']}
        Date création: {donnees['cartographie']['date_creation']}
        
        📊 STATISTIQUES CLÉS
        {json.dumps(donnees['statistiques'], indent=2, ensure_ascii=False)}
        
        📝 RISQUES ({len(donnees['risques'])})
        {json.dumps([{
            'reference': r['reference'],
            'intitule': r['intitule'],
            'categorie': r['categorie'],
            'type': r['type_risque'],
            'cause_racine': r['cause_racine']
        } for r in donnees['risques']], indent=2, ensure_ascii=False)}
        
        📋 ÉVALUATIONS ({len(donnees['evaluations'])})
        {json.dumps([{
            'campagne': e['campagne_nom'],
            'impact': e['impact_pre'],
            'probabilite': e['probabilite_pre'],
            'score': e['score_risque'],
            'niveau': e['niveau_risque'],
            'statut': e['statut_validation']
        } for e in donnees['evaluations']], indent=2, ensure_ascii=False)}
        
        💬 COMMENTAIRES DES ÉVALUATIONS
        {json.dumps(donnees['analyses_textuelles'], indent=2, ensure_ascii=False)}
        
        🛡️ DISPOSITIFS ({len(donnees['dispositifs'])})
        {json.dumps([{
            'reference': d['reference'],
            'type': d['type_dispositif'],
            'efficacite': d['efficacite_reelle'],
            'statut': d['statut']
        } for d in donnees['dispositifs']], indent=2, ensure_ascii=False)}
        
        ⚠️ INCIDENTS ({len(donnees['incidents'])})
        {json.dumps([{
            'reference': i['reference'],
            'gravite': i['gravite'],
            'statut': i['statut']
        } for i in donnees['incidents']], indent=2, ensure_ascii=False)}
        
        📋 DEMANDES DE RÉÉVALUATION ({len(donnees['demandes_reevaluation'])})
        {json.dumps([{
            'reference': d['reference'],
            'statut': d['statut']
        } for d in donnees['demandes_reevaluation']], indent=2, ensure_ascii=False)}
        
        📋 CONSTATS D'AUDIT ({len(donnees['constats_audit'])})
        {json.dumps([{
            'reference': c['reference'],
            'gravite': c['gravite'],
            'statut': c['statut']
        } for c in donnees['constats_audit']], indent=2, ensure_ascii=False)}
        
        📋 PLANS D'ACTION ({len(donnees['plans_action'])})
        {json.dumps([{
            'reference': p['reference'],
            'statut': p['statut'],
            'progression': p['pourcentage_realisation']
        } for p in donnees['plans_action']], indent=2, ensure_ascii=False)}
        
        📝 COMMENTAIRES GÉNÉRAUX ({len(donnees['commentaires'])})
        {json.dumps([c['contenu'] for c in donnees['commentaires'][:10]], indent=2, ensure_ascii=False)}
        
        TÂCHES D'ANALYSE :
        
        1. ANALYSE SÉMANTIQUE DES COMMENTAIRES
           - Qualité et profondeur des commentaires
           - Sentiment général (positif/négatif/neutre)
           - Cohérence entre commentaires et évaluations
           - Thèmes récurrents
        
        2. ANALYSE DES ÉVALUATIONS
           - Qualité des évaluations
           - Cohérence des notations
           - Écarts entre les phases (pré-éval vs validation vs confirmation)
           - Tendances dans le temps
        
        3. ANALYSE DES DISPOSITIFS
           - Efficacité globale
           - Adéquation avec les risques
           - Lacunes et redondances
        
        4. ANALYSE DES INCIDENTS
           - Causes racines
           - Corrélation avec dispositifs inefficaces
           - Gravité et impact
        
        5. ANALYSE SWOT COMPLÈTE
           - Forces (atouts, points forts)
           - Faiblesses (lacunes, points faibles)
           - Opportunités (axes d'amélioration)
           - Menaces (risques externes, tendances)
        
        6. RECOMMANDATIONS STRATÉGIQUES
           - Court terme (urgence)
           - Moyen terme (planification)
           - Long terme (stratégique)
        
        7. ALERTES ET RISQUES ÉMERGENTS
           - Alerte rouge : critique/urgent
           - Alerte orange : important
           - Alerte jaune : à surveiller
           - Risques émergents à anticiper
        
        FORMAT DE RÉPONSE : JSON
        """

    # ============================================================
    # ANALYSE TEXTUELLE DES COMMENTAIRES
    # ============================================================
    @staticmethod
    def _analyser_textes_commentaires(donnees):
        """Analyse sémantique des commentaires"""
        
        analyse = {
            'commentaires_risques': {
                'total': 0,
                'mots_cles': {},
                'sentiments': {'positif': 0, 'negatif': 0, 'neutre': 0},
                'profondeur_moyenne': 0
            },
            'commentaires_evaluations': {
                'total': 0,
                'themes': {},
                'qualite_moyenne': 0
            }
        }
        
        # Analyse des commentaires de risques
        textes = []
        for c in donnees['analyses_textuelles']['commentaires_risques']:
            texte = c['texte']
            if texte:
                textes.append(texte)
                analyse['commentaires_risques']['total'] += 1
                
                # Mots clés
                mots = re.findall(r'\b[a-zA-Z]{3,}\b', texte.lower())
                for mot in mots:
                    if len(mot) > 3:
                        analyse['commentaires_risques']['mots_cles'][mot] = \
                            analyse['commentaires_risques']['mots_cles'].get(mot, 0) + 1
        
        if textes:
            analyse['commentaires_risques']['profondeur_moyenne'] = round(
                sum(len(t.split()) for t in textes) / len(textes), 1
            )
        
        # Top mots clés
        mots_cles = analyse['commentaires_risques']['mots_cles']
        analyse['commentaires_risques']['top_mots'] = sorted(
            mots_cles.items(), key=lambda x: x[1], reverse=True
        )[:10]
        
        return analyse

    # ============================================================
    # ANALYSE LOCALE (FALLBACK)
    # ============================================================
    @staticmethod
    def _analyser_local(donnees):
        """Analyse locale de fallback"""
        
        stats = donnees['statistiques']
        
        # Score global
        score = 0
        if stats['taux_evaluation'] >= 70:
            score += 30
        elif stats['taux_evaluation'] >= 50:
            score += 20
        elif stats['taux_evaluation'] >= 30:
            score += 10
        
        if stats['total_dispositifs'] > 0:
            score += min((stats['total_dispositifs'] / stats['total_risques']) * 25, 25)
        
        score += min(stats['total_plans_action'] * 2, 15)
        
        if stats['incidents_recents'] == 0:
            score += 15
        elif stats['incidents_recents'] <= 3:
            score += 10
        else:
            score += max(0, 15 - stats['incidents_recents'] * 2)
        
        score = min(100, int(score))
        
        if score >= 80:
            niveau = 'excellent'
            label = 'Excellent'
            synthese = "Cartographie très mature et bien gérée"
        elif score >= 60:
            niveau = 'bon'
            label = 'Bon'
            synthese = "Cartographie satisfaisante avec des axes d'amélioration"
        elif score >= 40:
            niveau = 'moyen'
            label = 'Moyen'
            synthese = "Cartographie perfectible - Des actions sont nécessaires"
        else:
            niveau = 'faible'
            label = 'Faible'
            synthese = "Cartographie immature - Une refonte est recommandée"
        
        return {
            'score_global': score,
            'niveau_maturite': niveau,
            'synthese': synthese,
            'source': 'local',
            'date_analyse': datetime.now().isoformat(),
            'version': '2.0',
            'analyse_detailee': {
                'evaluations': f"Taux d'évaluation: {stats['taux_evaluation']}%",
                'dispositifs': f"Total: {stats['total_dispositifs']}",
                'incidents': f"Total: {stats['total_incidents']}, Récents: {stats['incidents_recents']}"
            },
            'forces': [],
            'faiblesses': [],
            'opportunites': [],
            'menaces': [],
            'recommandations': [],
            'alertes': [],
            'tendances': [],
            'risques_emergents': [],
            'plan_action': []
        }


# ============================================================
# SERVICE D'ANALYSE AVEC IA - COMPATIBLE AVEC VOTRE CODE
# ============================================================

class IAAnalyseService:
    """Service d'analyse IA - Version compatible avec votre code existant"""
    
    @staticmethod
    def analyser_cartographie(cartographie, risques, evaluations, dispositifs, incidents,
                              demandes_reevaluation=None, constats_audit=None, 
                              plans_action=None, commentaires=None, historique=None):
        """
        Analyse complète avec IA - Version compatible
        
        Args:
            cartographie: Objet Cartographie
            risques: Liste des risques
            evaluations: Liste des évaluations
            dispositifs: Liste des dispositifs
            incidents: Liste des incidents
            demandes_reevaluation: Liste des demandes de réévaluation
            constats_audit: Liste des constats d'audit
            plans_action: Liste des plans d'action
            commentaires: Liste des commentaires
            historique: Historique des modifications
        """
        
        # Appeler le service ultra avec toutes les données
        return IAAnalyseUltraService.analyser_complet(
            cartographie=cartographie,
            risques=risques,
            evaluations=evaluations,
            dispositifs=dispositifs,
            incidents=incidents,
            demandes_reevaluation=demandes_reevaluation or [],
            constats_audit=constats_audit or [],
            plans_action=plans_action or [],
            commentaires=commentaires or [],
            historique_modifications=historique or []
        )
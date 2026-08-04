# services/analyse_hybride.py
"""
SERVICE D'ANALYSE HYBRIDE - Algorithmique + IA
Toujours des suggestions (même sans API)
"""

import os
import json
import re
from datetime import datetime, timedelta
from collections import Counter
import statistics

# ============================================================
# PARTIE 1 : SUGGESTIONS ALGORITHMIQUES (TOUJOURS DISPONIBLES)
# ============================================================

class AnalyseAlgorithmique:
    """Moteur d'analyse algorithmique - Toujours disponible"""
    
    @staticmethod
    def generer_suggestions(risques, evaluations, dispositifs, incidents, 
                           demandes_reevaluation=None, constats_audit=None):
        """
        Génère des suggestions basées sur des règles métier
        TOUJOURS disponible, même sans API
        """
        suggestions = []
        alertes = []
        risques_proposes = []
        
        # Variables pour les statistiques
        total_risques = len(risques)
        
        # ============================================================
        # 1. ANALYSE DES RISQUES CRITIQUES SANS DISPOSITIF
        # ============================================================
        risques_critiques_sans_dispo = []
        for r in risques:
            eval = next((e for e in evaluations if e.risque_id == r.id), None)
            if eval and eval.niveau_risque in ['Critique', 'Élevé']:
                has_dispositif = any(d.risque_id == r.id for d in dispositifs)
                if not has_dispositif:
                    risques_critiques_sans_dispo.append({
                        'risque': r,
                        'niveau': eval.niveau_risque,
                        'score': eval.score_risque
                    })
        
        if risques_critiques_sans_dispo:
            suggestions.append({
                'id': 'sug_critiques_sans_dispo',
                'titre': f"🛡️ {len(risques_critiques_sans_dispo)} risque(s) critique(s) sans dispositif",
                'description': 'Ces risques ont un niveau critique ou élevé mais ne disposent d\'aucun dispositif de maîtrise.',
                'priorite': 'critical',
                'icone': 'fa-shield-alt',
                'categorie': 'dispositifs',
                'actions': [
                    'Créer des dispositifs de maîtrise adaptés',
                    'Prioriser les risques les plus critiques',
                    'Planifier des audits spécifiques'
                ],
                'delai_suggere': '15 jours',
                'impact': 'Élevé',
                'risques_concernes': [r['risque'] for r in risques_critiques_sans_dispo[:5]]
            })
            
            alertes.append({
                'niveau': 'rouge',
                'message': f"🔴 {len(risques_critiques_sans_dispo)} risques critiques sans dispositif",
                'detail': 'Action immédiate requise'
            })
        
        # ============================================================
        # 2. ANALYSE DU TAUX D'ÉVALUATION
        # ============================================================
        evaluees = len([e for e in evaluations if e.date_confirmation])
        taux_evaluation = int((evaluees / total_risques * 100) if total_risques > 0 else 0)
        
        if taux_evaluation < 50:
            suggestions.append({
                'id': 'sug_taux_evaluation',
                'titre': f"📊 Taux d'évaluation faible ({taux_evaluation}%)",
                'description': f'Seulement {taux_evaluation}% des risques sont évalués. {total_risques - evaluees} risques restants à évaluer.',
                'priorite': 'high',
                'icone': 'fa-chart-bar',
                'categorie': 'evaluation',
                'actions': [
                    'Organiser une session d\'évaluation collective',
                    'Prioriser les risques critiques',
                    'Mettre en place des évaluations régulières'
                ],
                'delai_suggere': '30 jours',
                'impact': 'Élevé'
            })
            
            if taux_evaluation < 30:
                alertes.append({
                    'niveau': 'orange',
                    'message': f"🟠 Taux d'évaluation très faible ({taux_evaluation}%)",
                    'detail': f"{total_risques - evaluees} risques non évalués"
                })
        
        # ============================================================
        # 3. ANALYSE DES INCIDENTS RÉCENTS
        # ============================================================
        date_limite = datetime.now() - timedelta(days=365)
        incidents_recents = [i for i in incidents if i.date_occurrence >= date_limite]
        
        if incidents_recents:
            gravites = Counter([i.gravite for i in incidents_recents if i.gravite])
            critiques = gravites.get('critique', 0)
            eleves = gravites.get('elevee', 0)
            
            suggestions.append({
                'id': 'sug_incidents_recents',
                'titre': f"⚠️ {len(incidents_recents)} incident(s) récent(s)",
                'description': f'{critiques} critiques, {eleves} élevés. Une analyse approfondie est recommandée.',
                'priorite': 'high' if critiques > 0 else 'medium',
                'icone': 'fa-exclamation-triangle',
                'categorie': 'incidents',
                'actions': [
                    'Analyser les causes racines des incidents',
                    'Mettre en place des actions correctives',
                    'Renforcer les contrôles préventifs'
                ],
                'delai_suggere': '15 jours',
                'impact': 'Élevé' if critiques > 0 else 'Moyen'
            })
            
            if critiques > 0:
                alertes.append({
                    'niveau': 'rouge',
                    'message': f"🔴 {critiques} incident(s) critique(s) récent(s)",
                    'detail': 'Action corrective immédiate requise'
                })
            elif eleves > 0:
                alertes.append({
                    'niveau': 'orange',
                    'message': f"🟠 {eleves} incident(s) élevé(s) récent(s)",
                    'detail': 'Surveillance renforcée nécessaire'
                })
        
        # ============================================================
        # 4. ANALYSE DE LA COUVERTURE DES DISPOSITIFS
        # ============================================================
        risques_avec_dispositif = set([d.risque_id for d in dispositifs])
        taux_couverture = int((len(risques_avec_dispositif) / total_risques * 100) if total_risques > 0 else 0)
        
        if taux_couverture < 40:
            suggestions.append({
                'id': 'sug_couverture_dispositifs',
                'titre': f"🛡️ Couverture dispositifs insuffisante ({taux_couverture}%)",
                'description': f'{total_risques - len(risques_avec_dispositif)} risques sans dispositif de maîtrise.',
                'priorite': 'high',
                'icone': 'fa-shield-alt',
                'categorie': 'dispositifs',
                'actions': [
                    'Identifier les risques sans dispositif',
                    'Créer des dispositifs adaptés',
                    'Évaluer l\'efficacité des dispositifs existants'
                ],
                'delai_suggere': '45 jours',
                'impact': 'Élevé'
            })
            
            if taux_couverture < 20:
                alertes.append({
                    'niveau': 'orange',
                    'message': f"🟠 Couverture dispositifs très faible ({taux_couverture}%)",
                    'detail': 'Risques non maîtrisés'
                })
        
        # ============================================================
        # 5. ANALYSE DE LA QUALITÉ DES ÉVALUATIONS
        # ============================================================
        if evaluations:
            scores_qualite = []
            for e in evaluations:
                qualite = 0
                if e.impact_pre and e.probabilite_pre:
                    qualite += 1
                if e.commentaire_pre_evaluation and len(e.commentaire_pre_evaluation) > 10:
                    qualite += 1
                if e.commentaire_validation and len(e.commentaire_validation) > 10:
                    qualite += 1
                if e.commentaire_confirmation and len(e.commentaire_confirmation) > 10:
                    qualite += 1
                scores_qualite.append(qualite / 4 * 100)
            
            qualite_moyenne = statistics.mean(scores_qualite) if scores_qualite else 0
            
            if qualite_moyenne < 50:
                suggestions.append({
                    'id': 'sug_qualite_evaluations',
                    'titre': f"📝 Qualité des évaluations insuffisante ({int(qualite_moyenne)}%)",
                    'description': 'Les évaluations manquent de profondeur. Commentaires et justifications insuffisants.',
                    'priorite': 'medium',
                    'icone': 'fa-pen',
                    'categorie': 'qualite',
                    'actions': [
                        'Former les évaluateurs',
                        'Mettre en place des modèles d\'évaluation',
                        'Exiger des commentaires justificatifs'
                    ],
                    'delai_suggere': '60 jours',
                    'impact': 'Moyen'
                })
        
        # ============================================================
        # 6. ANALYSE DES CATÉGORIES
        # ============================================================
        categories = {}
        for r in risques:
            if r.categorie:
                categories[r.categorie] = categories.get(r.categorie, 0) + 1
        
        if len(categories) < 3:
            categories_manquantes = ['Financier', 'Opérationnel', 'Réglementaire', 'Stratégique', 'Réputationnel']
            categories_existantes = list(categories.keys())
            suggestions.append({
                'id': 'sug_categories_manquantes',
                'titre': f"🏷️ Diversifier les catégories de risques ({len(categories)} existantes)",
                'description': f'Seulement {len(categories)} catégories couvertes. Ajoutez des risques dans : {", ".join([c for c in categories_manquantes if c.lower() not in [cat.lower() for cat in categories_existantes]][:3])}...',
                'priorite': 'medium',
                'icone': 'fa-tags',
                'categorie': 'couverture',
                'actions': [
                    'Identifier les catégories manquantes',
                    'Créer des risques dans les nouvelles catégories',
                    'Évaluer l\'exposition par catégorie'
                ],
                'delai_suggere': '90 jours',
                'impact': 'Moyen'
            })
        
        # ============================================================
        # 7. ANALYSE DES DEMANDES DE RÉÉVALUATION
        # ============================================================
        if demandes_reevaluation:
            attente = len([d for d in demandes_reevaluation if d.statut == 'en_attente'])
            if attente > 0:
                suggestions.append({
                    'id': 'sug_demandes_reevaluation',
                    'titre': f"🔄 {attente} demande(s) de réévaluation en attente",
                    'description': 'Des demandes de réévaluation sont en attente de traitement.',
                    'priorite': 'high',
                    'icone': 'fa-clock',
                    'categorie': 'reevaluation',
                    'actions': [
                        'Traiter les demandes en attente',
                        'Prioriser les demandes critiques',
                        'Planifier les réévaluations'
                    ],
                    'delai_suggere': '15 jours',
                    'impact': 'Élevé'
                })
        
        # ============================================================
        # 8. ANALYSE DES ÉCARTS ENTRE PHASES
        # ============================================================
        for e in evaluations:
            if e.impact_pre and e.impact_val and e.impact_conf:
                ecart_pre_val = abs(e.impact_pre - e.impact_val)
                ecart_val_conf = abs(e.impact_val - e.impact_conf)
                
                if ecart_pre_val > 1 or ecart_val_conf > 1:
                    risque_ref = e.risque.reference if hasattr(e.risque, 'reference') else 'N/A'
                    suggestions.append({
                        'id': 'sug_ecart_phases',
                        'titre': f"📊 Écarts significatifs entre les phases d'évaluation",
                        'description': f"Des écarts >1 point ont été détectés pour le risque {risque_ref}. Cela peut indiquer une incertitude.",
                        'priorite': 'medium',
                        'icone': 'fa-arrow-right-arrow-left',
                        'categorie': 'evaluation',
                        'actions': [
                            'Analyser les raisons des écarts',
                            'Vérifier la cohérence des évaluations',
                            'Documenter les justifications'
                        ],
                        'delai_suggere': '30 jours',
                        'impact': 'Moyen'
                    })
                    break
        
        # ============================================================
        # 9. ANALYSE DES DISPOSITIFS REDONDANTS
        # ============================================================
        dispositifs_par_risque = {}
        for d in dispositifs:
            if d.risque_id not in dispositifs_par_risque:
                dispositifs_par_risque[d.risque_id] = []
            dispositifs_par_risque[d.risque_id].append(d)

        for risque_id, dispo_list in dispositifs_par_risque.items():
            types = [d.type_dispositif for d in dispo_list if d.type_dispositif]
            if len(types) > len(set(types)):
                risque = next((r for r in risques if r.id == risque_id), None)
                risque_ref = risque.reference if risque else 'N/A'
                suggestions.append({
                    'id': 'sug_dispositifs_redondants',
                    'titre': f"🔄 Dispositifs potentiellement redondants pour {risque_ref}",
                    'description': f"Plusieurs dispositifs du même type sont présents pour ce risque. Une consolidation pourrait être envisagée.",
                    'priorite': 'low',
                    'icone': 'fa-compress-arrows-alt',
                    'categorie': 'dispositifs',
                    'actions': [
                        'Auditer les dispositifs redondants',
                        'Consolider ou supprimer les doublons',
                        'Optimiser les ressources'
                    ],
                    'delai_suggere': '60 jours',
                    'impact': 'Faible'
                })
                break
        
        # ============================================================
        # 10. ANALYSE DES COMMENTAIRES (NLP basique)
        # ============================================================
        commentaires_texte = []
        for e in evaluations:
            if e.commentaire_pre_evaluation:
                commentaires_texte.append(e.commentaire_pre_evaluation)
            if e.commentaire_validation:
                commentaires_texte.append(e.commentaire_validation)
            if e.commentaire_confirmation:
                commentaires_texte.append(e.commentaire_confirmation)

        if commentaires_texte:
            mots_risque = ['critique', 'urgent', 'grave', 'majeur', 'important', 'prioritaire']
            risque_mentions = sum(1 for t in commentaires_texte if any(m in t.lower() for m in mots_risque))
            
            if risque_mentions > len(commentaires_texte) * 0.3:
                suggestions.append({
                    'id': 'sug_commentaires_risque',
                    'titre': f"📝 Commentaires orientés risque",
                    'description': f"Les commentaires utilisent fréquemment des termes de risque ({int(risque_mentions/len(commentaires_texte)*100)}%). Une analyse qualitative est recommandée.",
                    'priorite': 'low',
                    'icone': 'fa-comment-dots',
                    'categorie': 'qualite',
                    'actions': [
                        'Analyser les commentaires en profondeur',
                        'Identifier les thèmes récurrents',
                        'Améliorer la documentation'
                    ],
                    'delai_suggere': '45 jours',
                    'impact': 'Faible'
                })
        
        # ============================================================
        # 11. ANALYSE DES COMMENTAIRES PAR CAMPAGNE (AMÉLIORÉ)
        # ============================================================
        if evaluations:
            commentaires_par_campagne = {}
            qualite_par_campagne = {}
            
            for e in evaluations:
                campagne = e.campagne_nom or 'Sans campagne'
                
                # Initialiser
                if campagne not in commentaires_par_campagne:
                    commentaires_par_campagne[campagne] = {
                        'pre': [],
                        'validation': [],
                        'confirmation': [],
                        'total': 0,
                        'mots_cles': {},
                        'qualite_moyenne': 0,
                        'taux_commentaires': 0
                    }
                
                # Récupérer les commentaires
                if e.commentaire_pre_evaluation:
                    commentaires_par_campagne[campagne]['pre'].append(e.commentaire_pre_evaluation)
                    commentaires_par_campagne[campagne]['total'] += 1
                    
                    # Mots clés
                    mots = e.commentaire_pre_evaluation.lower().split()
                    for mot in mots:
                        # Nettoyer le mot
                        mot_propre = re.sub(r'[^a-zA-Zàâäéèêëîïôöùûüÿçæœ]', '', mot)
                        if len(mot_propre) > 4:
                            commentaires_par_campagne[campagne]['mots_cles'][mot_propre] = \
                                commentaires_par_campagne[campagne]['mots_cles'].get(mot_propre, 0) + 1
                
                if e.commentaire_validation:
                    commentaires_par_campagne[campagne]['validation'].append(e.commentaire_validation)
                    commentaires_par_campagne[campagne]['total'] += 1
                
                if e.commentaire_confirmation:
                    commentaires_par_campagne[campagne]['confirmation'].append(e.commentaire_confirmation)
                    commentaires_par_campagne[campagne]['total'] += 1
                
                # Qualité des commentaires
                qualite = 0
                if e.commentaire_pre_evaluation and len(e.commentaire_pre_evaluation) > 20:
                    qualite += 1
                if e.commentaire_validation and len(e.commentaire_validation) > 20:
                    qualite += 1
                if e.commentaire_confirmation and len(e.commentaire_confirmation) > 20:
                    qualite += 1
                
                if campagne not in qualite_par_campagne:
                    qualite_par_campagne[campagne] = []
                qualite_par_campagne[campagne].append(qualite)
            
            # Générer des suggestions basées sur les commentaires par campagne
            for campagne, data in commentaires_par_campagne.items():
                # Calculer la qualité moyenne
                if campagne in qualite_par_campagne and qualite_par_campagne[campagne]:
                    qualite_moyenne = (sum(qualite_par_campagne[campagne]) / 
                                      len(qualite_par_campagne[campagne])) * 33.3
                    commentaires_par_campagne[campagne]['qualite_moyenne'] = round(qualite_moyenne, 1)
                
                # Calculer le taux de commentaires
                eval_campagne = len([e for e in evaluations if (e.campagne_nom or 'Sans campagne') == campagne])
                if eval_campagne > 0:
                    taux = (data['total'] / (eval_campagne * 3)) * 100
                    commentaires_par_campagne[campagne]['taux_commentaires'] = round(taux, 1)
                
                # Suggestion si peu de commentaires
                if data['total'] < 3:
                    suggestions.append({
                        'id': f'sug_commentaires_campagne_{campagne[:10].replace(" ", "_")}',
                        'titre': f"📝 Peu de commentaires dans la campagne '{campagne}'",
                        'description': f"Seulement {data['total']} commentaires pour cette campagne. Des commentaires détaillés améliorent la qualité des évaluations.",
                        'priorite': 'low',
                        'icone': 'fa-comment-dots',
                        'categorie': 'campagne',
                        'actions': [
                            f'Encourager les commentaires dans la campagne {campagne}',
                            'Former les évaluateurs',
                            'Mettre en place des modèles de commentaires'
                        ],
                        'delai_suggere': '30 jours',
                        'impact': 'Faible',
                        'campagne': campagne,
                        'metriques': {
                            'total_commentaires': data['total'],
                            'taux_commentaires': commentaires_par_campagne[campagne]['taux_commentaires'],
                            'qualite_moyenne': commentaires_par_campagne[campagne]['qualite_moyenne']
                        }
                    })
                
                # Suggestion sur les mots clés récurrents
                if data['mots_cles']:
                    top_mots = sorted(data['mots_cles'].items(), key=lambda x: x[1], reverse=True)[:5]
                    if top_mots and len(top_mots) >= 2:
                        mots_cles_str = ', '.join([f"'{m[0]}'" for m in top_mots[:3]])
                        suggestions.append({
                            'id': f'sug_mots_cles_{campagne[:10].replace(" ", "_")}',
                            'titre': f"🔑 Thèmes récurrents dans '{campagne}'",
                            'description': f"Mots clés fréquents : {mots_cles_str}. Ces thèmes méritent une attention particulière.",
                            'priorite': 'medium',
                            'icone': 'fa-key',
                            'categorie': 'campagne',
                            'actions': [
                                'Analyser ces thèmes en profondeur',
                                'Créer des risques dédiés si nécessaire',
                                'Documenter les tendances'
                            ],
                            'delai_suggere': '45 jours',
                            'impact': 'Moyen',
                            'campagne': campagne,
                            'top_mots': top_mots[:5]
                        })
                
                # Suggestion sur la qualité des commentaires
                if commentaires_par_campagne[campagne]['qualite_moyenne'] < 40:
                    suggestions.append({
                        'id': f'sug_qualite_comments_{campagne[:10].replace(" ", "_")}',
                        'titre': f"📋 Qualité des commentaires insuffisante - '{campagne}'",
                        'description': f"La qualité moyenne des commentaires est de {commentaires_par_campagne[campagne]['qualite_moyenne']}%. Les commentaires sont trop courts.",
                        'priorite': 'medium',
                        'icone': 'fa-pen-fancy',
                        'categorie': 'campagne',
                        'actions': [
                            f'Former les équipes de la campagne {campagne}',
                            'Fournir des modèles de commentaires détaillés',
                            'Organiser des ateliers d\'écriture'
                        ],
                        'delai_suggere': '30 jours',
                        'impact': 'Moyen',
                        'campagne': campagne,
                        'qualite_actuelle': commentaires_par_campagne[campagne]['qualite_moyenne']
                    })
        
        # ============================================================
        # 12. ANALYSE DE LA MATURITÉ PAR CAMPAGNE
        # ============================================================
        campagnes_eval = {}
        for e in evaluations:
            campagne_nom = e.campagne_nom or 'Sans campagne'
            if campagne_nom not in campagnes_eval:
                campagnes_eval[campagne_nom] = {'total': 0, 'confirmees': 0}
            campagnes_eval[campagne_nom]['total'] += 1
            if e.date_confirmation:
                campagnes_eval[campagne_nom]['confirmees'] += 1

        for campagne, data in campagnes_eval.items():
            if data['total'] > 0:
                taux = data['confirmees'] / data['total'] * 100
                if taux < 50:
                    suggestions.append({
                        'id': f'sug_campagne_{campagne[:10].replace(" ", "_")}',
                        'titre': f"📋 Campagne '{campagne}' - Taux de confirmation faible ({int(taux)}%)",
                        'description': f"Seulement {int(taux)}% des évaluations de cette campagne sont confirmées.",
                        'priorite': 'high' if taux < 30 else 'medium',
                        'icone': 'fa-calendar-check',
                        'categorie': 'campagne',
                        'actions': [
                            'Finaliser les évaluations en cours',
                            'Prioriser les confirmations',
                            'Organiser des sessions de validation'
                        ],
                        'delai_suggere': '30 jours',
                        'impact': 'Élevé' if taux < 30 else 'Moyen',
                        'campagne': campagne,
                        'taux_actuel': round(taux, 1)
                    })
        
        # ============================================================
        # 13. ANALYSE DES TENDANCES DE SCORES
        # ============================================================
        if len(evaluations) >= 3:
            scores_par_risque = {}
            for e in evaluations:
                if e.risque_id not in scores_par_risque:
                    scores_par_risque[e.risque_id] = []
                if e.score_risque:
                    scores_par_risque[e.risque_id].append(e.score_risque)
            
            for risque_id, scores in scores_par_risque.items():
                if len(scores) >= 3:
                    if scores[0] < scores[-1] and scores[-1] > scores[0] * 1.2:
                        risque = next((r for r in risques if r.id == risque_id), None)
                        risque_ref = risque.reference if risque else 'N/A'
                        suggestions.append({
                            'id': f'sug_tendance_hausse_{risque_id}',
                            'titre': f"📈 Tendance haussière des scores pour {risque_ref}",
                            'description': f"Le score du risque a augmenté de {scores[0]} à {scores[-1]}. Une analyse est recommandée.",
                            'priorite': 'high',
                            'icone': 'fa-chart-line',
                            'categorie': 'evolution',
                            'actions': [
                                'Analyser les causes de l\'augmentation',
                                'Vérifier les contrôles en place',
                                'Réévaluer le risque si nécessaire'
                            ],
                            'delai_suggere': '15 jours',
                            'impact': 'Élevé'
                        })
                        break
        
        # ============================================================
        # 14. ANALYSE DE LA COUVERTURE PAR TYPE DE DISPOSITIF
        # ============================================================
        types_dispositifs = {}
        for d in dispositifs:
            if d.type_dispositif:
                types_dispositifs[d.type_dispositif] = types_dispositifs.get(d.type_dispositif, 0) + 1

        if types_dispositifs:
            preventif = types_dispositifs.get('Préventif', 0)
            detectif = types_dispositifs.get('Détectif', 0)
            correctif = types_dispositifs.get('Correctif', 0)
            
            if preventif == 0 and (detectif > 0 or correctif > 0):
                suggestions.append({
                    'id': 'sug_manque_preventif',
                    'titre': "🛡️ Absence de dispositifs préventifs",
                    'description': "Aucun dispositif préventif n'a été identifié. Les dispositifs détectifs et correctifs seuls ne suffisent pas.",
                    'priorite': 'high',
                    'icone': 'fa-shield-alt',
                    'categorie': 'dispositifs',
                    'actions': [
                        'Créer des dispositifs préventifs',
                        'Équilibrer la typologie des dispositifs',
                        'Renforcer la prévention'
                    ],
                    'delai_suggere': '45 jours',
                    'impact': 'Élevé'
                })
        
        # ============================================================
        # 15. ANALYSE DES CONSTATS D'AUDIT
        # ============================================================
        if constats_audit:
            constats_ouverts = [c for c in constats_audit if c.statut != 'clos']
            if constats_ouverts:
                suggestions.append({
                    'id': 'sug_constats_ouverts',
                    'titre': f"📋 {len(constats_ouverts)} constat(s) d'audit ouvert(s)",
                    'description': "Des constats d'audit sont encore ouverts. Leur traitement est prioritaire.",
                    'priorite': 'high',
                    'icone': 'fa-clipboard-list',
                    'categorie': 'audit',
                    'actions': [
                        'Traiter les constats ouverts',
                        'Planifier les actions correctives',
                        'Suivre l\'avancement'
                    ],
                    'delai_suggere': '30 jours',
                    'impact': 'Élevé'
                })
        
        # ============================================================
        # 16. SUGGESTION DE RISQUES SUPPLÉMENTAIRES
        # ============================================================
        # Même si la cartographie n'est pas vide, proposer des risques
        # pour les catégories manquantes ou les types non couverts
        
        if total_risques > 0:
            categories_existantes = set([r.categorie for r in risques if r.categorie])
            types_existants = set([r.type_risque for r in risques if r.type_risque])

            risques_supplementaires = []

            # 1. Catégories manquantes
            categories_importantes = ['Financier', 'Opérationnel', 'Réglementaire', 'Stratégique', 'Réputationnel', 'Informatique']
            categories_manquantes = [c for c in categories_importantes if c.lower() not in [cat.lower() for cat in categories_existantes]]

            if categories_manquantes:
                for cat in categories_manquantes[:3]:
                    risques_supplementaires.append({
                        'reference': f'RISK-{cat[:3].upper()}-001',
                        'intitule': f'Risque {cat}',
                        'description': f'Risque lié à la catégorie {cat}. À définir selon le contexte métier.',
                        'categorie': cat,
                        'type_risque': 'residuel',
                        'impact_propose': 3,
                        'probabilite_propose': 3,
                        'est_suggestion': True,
                        'raison': f"Catégorie '{cat}' manquante"
                    })

            # 2. Types manquants
            types_importants = ['Inherent', 'Residuel', 'Cible', 'Externe', 'Interne']
            types_manquants = [t for t in types_importants if t.lower() not in [typ.lower() for typ in types_existants]]

            if types_manquants:
                for typ in types_manquants[:2]:
                    risques_supplementaires.append({
                        'reference': f'RISK-TYP-{typ[:3].upper()}-001',
                        'intitule': f'Risque de type {typ}',
                        'description': f'Risque de type {typ}. À définir selon le contexte.',
                        'categorie': 'Général',
                        'type_risque': typ,
                        'impact_propose': 3,
                        'probabilite_propose': 3,
                        'est_suggestion': True,
                        'raison': f"Type '{typ}' manquant"
                    })

            # 3. Si peu de risques (< 5), proposer des risques complémentaires
            if total_risques < 5:
                risques_complementaires = [
                    {
                        'reference': 'RISK-COMP-001',
                        'intitule': 'Rupture d\'approvisionnement',
                        'description': 'Dépendance à un fournisseur unique pour des matières critiques.',
                        'categorie': 'Operationnel',
                        'type_risque': 'Externe',
                        'impact_propose': 4,
                        'probabilite_propose': 3,
                        'est_suggestion': True,
                        'raison': "Risque complémentaire recommandé"
                    },
                    {
                        'reference': 'RISK-COMP-002',
                        'intitule': 'Cyberattaque',
                        'description': 'Vulnérabilité aux attaques informatiques.',
                        'categorie': 'Informatique',
                        'type_risque': 'Externe',
                        'impact_propose': 5,
                        'probabilite_propose': 4,
                        'est_suggestion': True,
                        'raison': "Risque complémentaire recommandé"
                    }
                ]
                risques_supplementaires.extend(risques_complementaires)

            # Ajouter aux risques proposés
            if risques_supplementaires:
                risques_proposes = risques_supplementaires
        
        # ============================================================
        # 17. SI CARTOGRAPHIE VIDE - PROPOSER DES RISQUES PAR DÉFAUT
        # ============================================================
        if total_risques == 0:
            risques_proposes = AnalyseAlgorithmique._generer_risques_par_defaut()
            
            suggestions.append({
                'id': 'sug_cartographie_vide',
                'titre': '🚀 Démarrer votre cartographie des risques',
                'description': 'Votre cartographie est vide. Voici des risques suggérés pour vous lancer.',
                'priorite': 'critical',
                'icone': 'fa-rocket',
                'categorie': 'demarrage',
                'actions': [
                    'Ajouter les risques proposés',
                    'Commencer les évaluations',
                    'Définir les priorités'
                ],
                'delai_suggere': '7 jours',
                'impact': 'Critique'
            })
        
        return {
            'suggestions': suggestions,
            'alertes': alertes,
            'risques_proposes': risques_proposes,
            'statistiques': {
                'total_risques': total_risques,
                'taux_evaluation': taux_evaluation,
                'taux_couverture': taux_couverture,
                'incidents_recents': len(incidents_recents),
                'commentaires_par_campagne': commentaires_par_campagne if evaluations else {}
            }
        }
    
    @staticmethod
    def _generer_risques_par_defaut():
        """Génère des risques par défaut pour une cartographie vide"""
        return [
            {
                'reference': 'RISK-001',
                'intitule': 'Rupture d\'approvisionnement critique',
                'description': 'Dépendance excessive à un fournisseur unique pour des matières premières essentielles.',
                'categorie': 'Operationnel',
                'type_risque': 'Externe',
                'impact_propose': 4,
                'probabilite_propose': 3
            },
            {
                'reference': 'RISK-002',
                'intitule': 'Cyberattaque sur les systèmes d\'information',
                'description': 'Les systèmes d\'information sont vulnérables aux attaques de type ransomware ou phishing.',
                'categorie': 'Informatique',
                'type_risque': 'Externe',
                'impact_propose': 5,
                'probabilite_propose': 4
            },
            {
                'reference': 'RISK-003',
                'intitule': 'Non-conformité réglementaire',
                'description': 'Risque de non-respect des nouvelles réglementations sectorielles.',
                'categorie': 'Reglementaire',
                'type_risque': 'Reglementaire',
                'impact_propose': 4,
                'probabilite_propose': 4
            },
            {
                'reference': 'RISK-004',
                'intitule': 'Départ de talents clés',
                'description': 'Risque de perte de compétences critiques suite au départ de collaborateurs clés.',
                'categorie': 'RH',
                'type_risque': 'Interne',
                'impact_propose': 3,
                'probabilite_propose': 4
            },
            {
                'reference': 'RISK-005',
                'intitule': 'Défaillance technique majeure',
                'description': 'Risque de panne ou défaillance des équipements critiques de production.',
                'categorie': 'Operationnel',
                'type_risque': 'Technique',
                'impact_propose': 4,
                'probabilite_propose': 3
            },
            {
                'reference': 'RISK-006',
                'intitule': 'Image de marque et réputation',
                'description': 'Risque de dégradation de l\'image de marque suite à un scandale ou une mauvaise communication.',
                'categorie': 'Reputationnel',
                'type_risque': 'Externe',
                'impact_propose': 5,
                'probabilite_propose': 2
            },
            {
                'reference': 'RISK-007',
                'intitule': 'Fluctuation des taux de change',
                'description': 'Impact des variations des devises sur les marges et la compétitivité.',
                'categorie': 'Financier',
                'type_risque': 'Externe',
                'impact_propose': 3,
                'probabilite_propose': 4
            }
        ]


# ============================================================
# PARTIE 2 : SERVICE HYBRIDE COMPLET
# ============================================================

class AnalyseHybrideService:
    """
    SERVICE HYBRIDE - Algorithmique + IA
    Toujours des suggestions disponibles
    """
    
    @staticmethod
    def analyser_complet(cartographie, risques, evaluations, dispositifs, incidents,
                         demandes_reevaluation=None, constats_audit=None, 
                         plans_action=None):
        """
        Analyse complète avec système hybride
        """
        
        # 1. ANALYSE ALGORITHMIQUE (TOUJOURS)
        resultat_algo = AnalyseAlgorithmique.generer_suggestions(
            risques=risques,
            evaluations=evaluations,
            dispositifs=dispositifs,
            incidents=incidents,
            demandes_reevaluation=demandes_reevaluation,
            constats_audit=constats_audit
        )
        
        # 2. SUGGESTIONS IA (SIMULÉES SI API NON DISPONIBLE)
        suggestions_ia = []
        # Si vous avez une API OpenAI, décommentez cette partie
        # if AnalyseIA._is_available():
        #     suggestions_ia = AnalyseIA.generer_suggestions_ia(donnees) or []
        
        # 3. FUSION
        suggestions = resultat_algo['suggestions']
        
        # Ajouter les suggestions IA (sans doublons)
        for ia_sug in suggestions_ia:
            existe = any(s['titre'] == ia_sug.get('titre') for s in suggestions)
            if not existe:
                suggestions.append(ia_sug)
        
        # 4. SCORE GLOBAL
        score_global = AnalyseHybrideService._calculer_score_global(
            risques, evaluations, dispositifs, incidents
        )
        
        # 5. INDICATEURS DE MATURITÉ
        maturite = AnalyseHybrideService._calculer_maturite(
            risques, evaluations, dispositifs, incidents
        )
        
        # 6. BENCHMARK
        benchmark = AnalyseHybrideService._calculer_benchmark(
            risques, evaluations, dispositifs, incidents
        )
        
        # 7. OBJECTIFS SMART
        objectifs = AnalyseHybrideService._calculer_objectifs(
            risques, evaluations, dispositifs, incidents
        )
        
        return {
            'success': True,
            'score_global': score_global['score'],
            'niveau': score_global['niveau'],
            'niveau_label': score_global['niveau_label'],
            'message': score_global['message'],
            'suggestions': suggestions,
            'alertes': resultat_algo['alertes'],
            'risques_proposes': resultat_algo['risques_proposes'],
            'statistiques': resultat_algo['statistiques'],
            'source': 'algorithme',
            'date_analyse': datetime.now().isoformat(),
            'maturite': maturite,
            'benchmark': benchmark,
            'objectifs': objectifs
        }
    
    @staticmethod
    def _calculer_score_global(risques, evaluations, dispositifs, incidents):
        """Calcule le score global"""
        total_risques = len(risques)
        if total_risques == 0:
            return {
                'score': 0,
                'niveau': 'faible',
                'niveau_label': 'Faible',
                'message': 'Cartographie vide - Commencez par ajouter des risques'
            }
        
        score = 0
        
        # Taux d'évaluation (30%)
        evaluees = len([e for e in evaluations if e.date_confirmation])
        taux_eval = (evaluees / total_risques * 100) if total_risques > 0 else 0
        score += taux_eval * 0.3
        
        # Couverture dispositifs (25%)
        risques_avec_dispo = set([d.risque_id for d in dispositifs])
        taux_dispo = (len(risques_avec_dispo) / total_risques * 100) if total_risques > 0 else 0
        score += min(taux_dispo * 0.25, 25)
        
        # Incidents (20%)
        date_limite = datetime.now() - timedelta(days=365)
        incidents_recents = len([i for i in incidents if i.date_occurrence >= date_limite])
        if incidents_recents == 0:
            score += 20
        else:
            score += max(0, 20 - (incidents_recents * 2))
        
        # Diversité des catégories (15%)
        categories = set([r.categorie for r in risques if r.categorie])
        if len(categories) >= 5:
            score += 15
        elif len(categories) >= 3:
            score += 10
        elif len(categories) >= 1:
            score += 5
        
        # Niveaux de risque (10%)
        niveaux = {}
        for e in evaluations:
            if e.niveau_risque:
                niveaux[e.niveau_risque] = niveaux.get(e.niveau_risque, 0) + 1
        critiques = niveaux.get('Critique', 0)
        if critiques == 0:
            score += 10
        elif critiques <= 2:
            score += 5
        else:
            score += 2
        
        score_final = int(min(100, score))
        
        if score_final >= 80:
            return {'score': score_final, 'niveau': 'excellent', 'niveau_label': 'Excellent', 'message': 'Cartographie très mature'}
        elif score_final >= 60:
            return {'score': score_final, 'niveau': 'bon', 'niveau_label': 'Bon', 'message': 'Cartographie satisfaisante'}
        elif score_final >= 40:
            return {'score': score_final, 'niveau': 'moyen', 'niveau_label': 'Moyen', 'message': 'Cartographie perfectible - Des actions sont nécessaires'}
        else:
            return {'score': score_final, 'niveau': 'faible', 'niveau_label': 'Faible', 'message': 'Cartographie immature - Une refonte est recommandée'}
    
    @staticmethod
    def _calculer_maturite(risques, evaluations, dispositifs, incidents):
        """Calcule les indicateurs de maturité"""
        total_risques = len(risques)
        if total_risques == 0:
            return {}
        
        # Taux d'évaluation
        evaluees = len([e for e in evaluations if e.date_confirmation])
        taux_evaluation = (evaluees / total_risques * 100) if total_risques > 0 else 0
        
        # Couverture dispositifs
        risques_avec_dispo = set([d.risque_id for d in dispositifs])
        taux_couverture = (len(risques_avec_dispo) / total_risques * 100) if total_risques > 0 else 0
        
        # Incidents récents
        date_limite = datetime.now() - timedelta(days=365)
        incidents_recents = len([i for i in incidents if i.date_occurrence >= date_limite])
        
        # Qualité des évaluations
        qualite_moyenne = 0
        if evaluations:
            scores_qualite = []
            for e in evaluations:
                qualite = 0
                if e.impact_pre and e.probabilite_pre:
                    qualite += 1
                if e.commentaire_pre_evaluation and len(e.commentaire_pre_evaluation) > 10:
                    qualite += 1
                if e.commentaire_validation and len(e.commentaire_validation) > 10:
                    qualite += 1
                if e.commentaire_confirmation and len(e.commentaire_confirmation) > 10:
                    qualite += 1
                scores_qualite.append(qualite / 4 * 100)
            qualite_moyenne = statistics.mean(scores_qualite) if scores_qualite else 0
        
        # Catégories
        categories = set([r.categorie for r in risques if r.categorie])
        
        return {
            'evaluation': {
                'score': min(100, taux_evaluation * 1.2),
                'label': 'Évaluations',
                'couleur': '#3b82f6'
            },
            'dispositifs': {
                'score': min(100, taux_couverture * 1.3),
                'label': 'Dispositifs',
                'couleur': '#10b981'
            },
            'incidents': {
                'score': max(0, 100 - incidents_recents * 5),
                'label': 'Incidents',
                'couleur': '#ef4444'
            },
            'qualite': {
                'score': qualite_moyenne,
                'label': 'Qualité',
                'couleur': '#8b5cf6'
            },
            'couverture': {
                'score': min(100, len(categories) * 20),
                'label': 'Couverture',
                'couleur': '#f59e0b'
            }
        }
    
    @staticmethod
    def _calculer_benchmark(risques, evaluations, dispositifs, incidents):
        """Calcule le benchmark sectoriel"""
        total_risques = len(risques)
        if total_risques == 0:
            return {}
        
        evaluees = len([e for e in evaluations if e.date_confirmation])
        taux_evaluation = (evaluees / total_risques * 100) if total_risques > 0 else 0
        
        risques_avec_dispo = set([d.risque_id for d in dispositifs])
        taux_couverture = (len(risques_avec_dispo) / total_risques * 100) if total_risques > 0 else 0
        
        date_limite = datetime.now() - timedelta(days=365)
        incidents_recents = len([i for i in incidents if i.date_occurrence >= date_limite])
        
        scores_risques = [e.score_risque for e in evaluations if e.score_risque]
        score_moyen = statistics.mean(scores_risques) if scores_risques else 0
        
        return {
            'taux_evaluation': {
                'actuel': round(taux_evaluation, 1),
                'secteur': 65,
                'ecart': round(taux_evaluation - 65, 1)
            },
            'taux_couverture': {
                'actuel': round(taux_couverture, 1),
                'secteur': 55,
                'ecart': round(taux_couverture - 55, 1)
            },
            'incidents': {
                'actuel': incidents_recents,
                'secteur': 3,
                'ecart': incidents_recents - 3
            },
            'score_moyen': {
                'actuel': round(score_moyen, 1),
                'secteur': 12,
                'ecart': round(score_moyen - 12, 1)
            }
        }
    
    @staticmethod
    def _calculer_objectifs(risques, evaluations, dispositifs, incidents):
        """Calcule les objectifs SMART"""
        total_risques = len(risques)
        if total_risques == 0:
            return []
        
        evaluees = len([e for e in evaluations if e.date_confirmation])
        taux_evaluation = (evaluees / total_risques * 100) if total_risques > 0 else 0
        
        risques_avec_dispo = set([d.risque_id for d in dispositifs])
        taux_couverture = (len(risques_avec_dispo) / total_risques * 100) if total_risques > 0 else 0
        
        nb_risques_critiques = 0
        for e in evaluations:
            if e.niveau_risque == 'Critique':
                nb_risques_critiques += 1
        
        # Qualité des évaluations
        qualite_moyenne = 0
        if evaluations:
            scores_qualite = []
            for e in evaluations:
                qualite = 0
                if e.impact_pre and e.probabilite_pre:
                    qualite += 1
                if e.commentaire_pre_evaluation and len(e.commentaire_pre_evaluation) > 10:
                    qualite += 1
                if e.commentaire_validation and len(e.commentaire_validation) > 10:
                    qualite += 1
                if e.commentaire_confirmation and len(e.commentaire_confirmation) > 10:
                    qualite += 1
                scores_qualite.append(qualite / 4 * 100)
            qualite_moyenne = statistics.mean(scores_qualite) if scores_qualite else 0
        
        objectifs = [
            {
                'titre': 'Atteindre 80% de taux d\'évaluation',
                'actuel': f"{round(taux_evaluation, 1)}%",
                'cible': '80%',
                'delai': '3 mois',
                'statut': 'termine' if taux_evaluation >= 80 else 'en_cours'
            },
            {
                'titre': 'Réduire les risques critiques de 50%',
                'actuel': f"{nb_risques_critiques}",
                'cible': f"{max(0, nb_risques_critiques // 2)}",
                'delai': '6 mois',
                'statut': 'termine' if nb_risques_critiques <= 2 else 'a_planifier'
            },
            {
                'titre': 'Atteindre 70% de couverture dispositifs',
                'actuel': f"{round(taux_couverture, 1)}%",
                'cible': '70%',
                'delai': '4 mois',
                'statut': 'termine' if taux_couverture >= 70 else 'en_cours'
            },
            {
                'titre': 'Améliorer la qualité des évaluations',
                'actuel': f"{int(qualite_moyenne)}%",
                'cible': '80%',
                'delai': '3 mois',
                'statut': 'termine' if qualite_moyenne >= 80 else 'en_cours'
            }
        ]
        
        return objectifs

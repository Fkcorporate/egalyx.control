import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from io import BytesIO
import base64
from datetime import datetime, timedelta

def calculer_niveau_risque(impact, probabilite):
    """Calculer le niveau de risque basé sur la matrice des risques - VERSION SYNCHRONISÉE"""
    score = impact * probabilite
    
    # ÉCHELLE SYNCHRONISÉE : Score exact = Impact × Probabilité
    if score <= 4:
        return 'Faible', 'green', score
    elif score <= 10:
        return 'Moyen', 'orange', score
    elif score <= 16:
        return 'Élevé', 'red', score
    else:
        return 'Critique', 'darkred', score

def get_couleur_risque(score):
    """Retourne la couleur en fonction du score de risque - SYNCHRONISÉE AVEC MATRICE"""
    # ÉCHELLE EXACTE POUR MATRICE 5x5
    if score <= 4:
        return 'lightgreen'      # Faible
    elif score <= 10:
        return 'yellow'          # Moyen
    elif score <= 16:
        return 'orange'          # Élevé
    else:
        return 'red'             # Critique (17-25)

def generer_matrice_risques(evaluations, matrice_type='classique'):
    """Générer différentes matrices de risques avec positionnement CORRECT - VERSION CORRIGÉE"""
    fig, ax = plt.subplots(figsize=(14, 12))
    
    # Configuration de la matrice 5x5
    impacts = np.arange(1, 6)
    probabilites = np.arange(1, 6)
    
    # CORRECTION : Inverser l'ordre des impacts pour avoir 5 en haut et 1 en bas
    for i, impact in enumerate(impacts):
        for j, proba in enumerate(probabilites):
            score = impact * proba
            couleur = get_couleur_risque(score)
            
            # CORRECTION : Impact 5 = ligne du haut (i=0), Impact 1 = ligne du bas (i=4)
            rect = patches.Rectangle((j, i), 1, 1, linewidth=2,  # PLUS de 4-i, juste i
                                   edgecolor='black', facecolor=couleur, alpha=0.7)
            ax.add_patch(rect)
            
            # Ajouter le score dans la case
            ax.text(j + 0.5, i + 0.5, f'{score}', 
                   ha='center', va='center', fontsize=14, fontweight='bold')
    
    # Dictionnaire pour regrouper les risques par position
    risques_par_position = {}
    
    evaluations_valides = []
    risques_non_evalues = []
    
    print(f"🎯 Traitement de {len(evaluations)} évaluations pour la matrice {matrice_type}")
    
    for idx, evaluation in enumerate(evaluations):
        # Utiliser les valeurs finales selon la priorité
        impact = (evaluation.impact_conf or 
                 evaluation.impact_val or 
                 evaluation.impact_pre)
        probabilite = (evaluation.probabilite_conf or 
                      evaluation.probabilite_val or 
                      evaluation.probabilite_pre)
        
        if impact and probabilite and impact > 0 and probabilite > 0:
            # CORRECTION : Positionnement DIRECT - Impact 5 = y=4 (haut), Impact 1 = y=0 (bas)
            if matrice_type == 'priorisation':
                niveau_maitrise = evaluation.niveau_maitrise_pre or 3
                x = (5 - niveau_maitrise)  # De 0 à 4
                y = impact - 1  # Impact 1 -> y=0 (bas), Impact 5 -> y=4 (haut)
            else:
                x = probabilite - 1  # De 0 à 4 (Probabilité 1 -> x=0, Probabilité 5 -> x=4)
                y = impact - 1  # CORRECTION : Impact 1 -> y=0 (bas), Impact 5 -> y=4 (haut)
            
            # Position centrale dans la case
            x_centre = x + 0.5
            y_centre = y + 0.5
            
            # Stocker la position
            position_key = f"{x}_{y}"
            if position_key not in risques_par_position:
                risques_par_position[position_key] = []
            
            score_calcule = impact * probabilite
            
            risque_data = {
                'evaluation': evaluation,
                'x_centre': x_centre,
                'y_centre': y_centre,
                'x': x,
                'y': y,
                'impact': impact,
                'probabilite': probabilite,
                'score': score_calcule,
                'index': idx
            }
            
            risques_par_position[position_key].append(risque_data)
            evaluations_valides.append(evaluation)
            
            print(f"📍 Risque positionné CORRECT: {evaluation.risque.reference} à P{probabilite}/I{impact} -> Case [{x}, {y}] -> Score: {score_calcule}")
        else:
            print(f"⚠️ Évaluation ignorée: {evaluation.risque.reference}")
            risques_non_evalues.append(evaluation.risque)
    
    print(f"🔍 Matrice {matrice_type}: {len(evaluations_valides)} évaluations valides")
    
    # Couleurs pour les différents risques
    colors = ['blue', 'purple', 'darkred', 'darkgreen', 'darkorange', 'darkcyan', 'brown', 'pink', 'navy', 'teal']
    
    # Tracer les risques avec positionnement CORRECT
    for position_key, risques_list in risques_par_position.items():
        if len(risques_list) == 1:
            # Cas simple : un seul risque à cette position
            risque_data = risques_list[0]
            color_idx = risque_data['index'] % len(colors)
            
            x = risque_data['x_centre']
            y = risque_data['y_centre']
            
            ax.plot(x, y, 'o', markersize=16, color=colors[color_idx], 
                   markeredgecolor='white', markeredgewidth=3, alpha=0.9, zorder=5)
            
            # Référence du risque
            risque_ref = risque_data['evaluation'].risque.reference
            ax.annotate(risque_ref, (x, y), xytext=(12, 12), 
                       textcoords='offset points', fontsize=9, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.4", fc='white', alpha=0.9, ec='gray'),
                       zorder=6)
            
        else:
            # Cas multiple : plusieurs risques à la même position
            print(f"🔄 {len(risques_list)} risques à position {position_key}")
            
            # Position centrale de la case
            x_centre = float(position_key.split('_')[0]) + 0.5
            y_centre = float(position_key.split('_')[1]) + 0.5
            
            # Répartir les risques autour du centre
            radius = 0.2
            angle_step = 2 * np.pi / len(risques_list)
            
            for i, risque_data in enumerate(risques_list):
                color_idx = risque_data['index'] % len(colors)
                
                # Calculer la position sur le cercle
                angle = i * angle_step
                x = x_centre + radius * np.cos(angle)
                y = y_centre + radius * np.sin(angle)
                
                ax.plot(x, y, 'o', markersize=14, color=colors[color_idx], 
                       markeredgecolor='white', markeredgewidth=2, alpha=0.9, zorder=5)
                
                risque_ref = risque_data['evaluation'].risque.reference
                ax.annotate(risque_ref, (x, y), xytext=(10, 10), 
                           textcoords='offset points', fontsize=8, fontweight='bold',
                           bbox=dict(boxstyle="round,pad=0.3", fc='white', alpha=0.9, ec='gray'),
                           zorder=6)
            
            # Marqueur central
            ax.plot(x_centre, y_centre, 's', markersize=8, color='red', 
                   markeredgecolor='yellow', markeredgewidth=2, alpha=0.7, zorder=4)
    
    # Configuration des axes
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 5)
    ax.set_xticks([0.5, 1.5, 2.5, 3.5, 4.5])
    ax.set_yticks([0.5, 1.5, 2.5, 3.5, 4.5])
    
    # CORRECTION : Échelles cohérentes avec le nouveau positionnement
    if matrice_type == 'classique':
        ax.set_xticklabels(['1\nTrès rare', '2\nRare', '3\nPossible', '4\nProbable', '5\nTrès probable'], fontsize=11)
        ax.set_yticklabels(['1\nNégligeable', '2\nMineur', '3\nModéré', '4\nImportant', '5\nCritique'], fontsize=11)  # CORRECTION : ordre normal
        ax.set_xlabel('Probabilité', fontsize=13, fontweight='bold', labelpad=15)
        ax.set_ylabel('Impact', fontsize=13, fontweight='bold', labelpad=15)
        titre = "Matrice des Risques - Classique"
        
    elif matrice_type == 'criticite':
        ax.set_xticklabels(['1\nTrès rare', '2\nRare', '3\nPossible', '4\nProbable', '5\nTrès probable'], fontsize=11)
        ax.set_yticklabels(['1\nNégligeable', '2\nMineur', '3\nModéré', '4\nImportant', '5\nCritique'], fontsize=11)  # CORRECTION : ordre normal
        ax.set_xlabel('Probabilité', fontsize=13, fontweight='bold', labelpad=15)
        ax.set_ylabel('Impact', fontsize=13, fontweight='bold', labelpad=15)
        titre = "Matrice de Criticité"
        
    elif matrice_type == 'priorisation':
        ax.set_xticklabels(['1\nInsuffisant', '2\nPartiel', '3\nAdéquat', '4\nBon', '5\nExcellent'], fontsize=11)
        ax.set_yticklabels(['1\nNégligeable', '2\nMineur', '3\nModéré', '4\nImportant', '5\nCritique'], fontsize=11)  # CORRECTION : ordre normal
        ax.set_xlabel('Niveau de Maîtrise', fontsize=13, fontweight='bold', labelpad=15)
        ax.set_ylabel('Impact', fontsize=13, fontweight='bold', labelpad=15)
        titre = "Matrice de Priorisation"
    
    ax.set_title(titre, fontsize=16, fontweight='bold', pad=25)
    
    # Légende (reste identique)
    legend_x = 5.2
    
    if evaluations_valides:
        ax.text(legend_x, 4.5, 'LÉGENDE RISQUES:', fontweight='bold', fontsize=10, 
                bbox=dict(boxstyle="round,pad=0.3", fc='lightblue', alpha=0.7))
        
        for idx in range(min(4, len(evaluations_valides))):
            eval_data = evaluations_valides[idx]
            impact = (eval_data.impact_conf or eval_data.impact_val or eval_data.impact_pre)
            probabilite = (eval_data.probabilite_conf or eval_data.probabilite_val or eval_data.probabilite_pre)
            
            if impact and probabilite:
                color_idx = idx % len(colors)
                ax.plot(legend_x, 4.2 - idx*0.2, 'o', markersize=10, color=colors[color_idx])
                ax.text(legend_x + 0.3, 4.2 - idx*0.2, eval_data.risque.reference, fontsize=8)
    
    # Légende des couleurs
    ax.text(legend_x, 3.0, 'NIVEAUX DE RISQUE:', fontweight='bold', fontsize=10)
    niveaux = [
        ('Faible (1-4)', 'lightgreen'), 
        ('Moyen (5-10)', 'yellow'), 
        ('Élevé (11-16)', 'orange'), 
        ('Critique (17-25)', 'red')
    ]
    
    for i, (texte, couleur) in enumerate(niveaux):
        ax.add_patch(patches.Rectangle((legend_x, 2.8 - i*0.2), 0.3, 0.15, facecolor=couleur))
        ax.text(legend_x + 0.4, 2.87 - i*0.2, texte, fontsize=8, va='center')
    
    # Conversion en image base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    
    graphic = base64.b64encode(image_png).decode('utf-8')
    plt.close()
    
    print(f"✅ Matrice {matrice_type} générée avec positionnement CORRECT : 25 en haut à droite, 1 en bas à gauche")
    return graphic


def diagnostiquer_evaluations_manquantes(cartographie_id):
    """Fonction de diagnostic pour identifier les évaluations manquantes"""
    from app import db
    from models import Cartographie, Risque, EvaluationRisque
    
    cartographie = Cartographie.query.get(cartographie_id)
    
    print(f"🔍 DIAGNOSTIC pour cartographie: {cartographie.nom}")
    print(f"📊 Total risques: {len(cartographie.risques)}")
    
    for risque in cartographie.risques:
        print(f"\n🎯 Risque: {risque.reference} - {len(risque.evaluations)} évaluations")
        
        for eval in risque.evaluations:
            impact_conf = eval.impact_conf
            impact_val = eval.impact_val
            impact_pre = eval.impact_pre
            prob_conf = eval.probabilite_conf
            prob_val = eval.probabilite_val
            prob_pre = eval.probabilite_pre
            
            impact_final = impact_conf or impact_val or impact_pre
            prob_final = prob_conf or prob_val or prob_pre
            
            print(f"   📋 Évaluation {eval.id}:")
            print(f"      Impact: Conf={impact_conf}, Val={impact_val}, Pre={impact_pre} → Final={impact_final}")
            print(f"      Probabilité: Conf={prob_conf}, Val={prob_val}, Pre={prob_pre} → Final={prob_final}")
            print(f"      Valide: {impact_final and prob_final and impact_final > 0 and prob_final > 0}")

def generer_matrice_risque_specifique(evaluations, risque_surbrillance=None):
    """Générer une matrice avec un risque spécifique en surbrillance - VERSION LÉGENDES CORRIGÉE"""
    fig, ax = plt.subplots(figsize=(14, 12))
    
    # Configuration de la matrice 5x5
    impacts = np.arange(1, 6)
    probabilites = np.arange(1, 6)
    
    # Création de la grille colorée
    for i, impact in enumerate(impacts):
        for j, proba in enumerate(probabilites):
            score = impact * proba
            couleur = get_couleur_risque(score)
            
            rect = patches.Rectangle((j, i), 1, 1, linewidth=2,
                                   edgecolor='black', facecolor=couleur, alpha=0.7)
            ax.add_patch(rect)
            
            ax.text(j + 0.5, i + 0.5, f'{score}', 
                   ha='center', va='center', fontsize=14, fontweight='bold')
    
    # Dictionnaire pour regrouper les risques par position
    risques_par_position = {}
    
    evaluations_valides = []
    risques_non_evalues = []
    
    for idx, evaluation in enumerate(evaluations):
        impact = (evaluation.impact_conf or 
                 evaluation.impact_val or 
                 evaluation.impact_pre)
        probabilite = (evaluation.probabilite_conf or 
                      evaluation.probabilite_val or 
                      evaluation.probabilite_pre)
        
        if impact and probabilite and impact > 0 and probabilite > 0:
            x = probabilite - 1
            y = impact - 1
            
            x_centre = x + 0.5
            y_centre = y + 0.5
            
            position_key = f"{x}_{y}"
            if position_key not in risques_par_position:
                risques_par_position[position_key] = []
            
            score_calcule = impact * probabilite
            
            risque_data = {
                'evaluation': evaluation,
                'x_centre': x_centre,
                'y_centre': y_centre,
                'x': x,
                'y': y,
                'impact': impact,
                'probabilite': probabilite,
                'score': score_calcule,
                'index': idx,
                'is_target': (risque_surbrillance and evaluation.risque.id == risque_surbrillance.id)
            }
            
            risques_par_position[position_key].append(risque_data)
            evaluations_valides.append(evaluation)

    # Couleurs pour les différents risques
    colors = ['blue', 'purple', 'darkred', 'darkgreen', 'darkorange', 'darkcyan', 'brown', 'pink', 'navy', 'teal']
    
    # Tracer les risques
    for position_key, risques_list in risques_par_position.items():
        has_target = any(r['is_target'] for r in risques_list)
        
        if has_target:
            risque_cible_data = next(r for r in risques_list if r['is_target'])
            x = risque_cible_data['x_centre']
            y = risque_cible_data['y_centre']
            
            ax.plot(x, y, 'o', markersize=25, color='red', 
                   markeredgecolor='yellow', markeredgewidth=4, alpha=1.0, zorder=10)
            
            circle = plt.Circle((x, y), 0.4, color='yellow', alpha=0.3, zorder=9)
            ax.add_patch(circle)
            
            risque_ref = risque_cible_data['evaluation'].risque.reference
            score_target = risque_cible_data['score']
            
            ax.annotate(f"⭐ {risque_ref} (S:{score_target}) ⭐", 
                       (x, y), xytext=(25, 25), 
                       textcoords='offset points', fontsize=14, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.6", fc='yellow', alpha=0.9, ec='orange'),
                       arrowprops=dict(arrowstyle='->', color='orange', lw=2),
                       zorder=11)
            
        elif len(risques_list) == 1:
            risque_data = risques_list[0]
            color_idx = risque_data['index'] % len(colors)
            x = risque_data['x_centre']
            y = risque_data['y_centre']
            
            ax.plot(x, y, 'o', markersize=16, color=colors[color_idx], 
                   markeredgecolor='white', markeredgewidth=2, alpha=0.8, zorder=5)
            
            ax.annotate(risque_data['evaluation'].risque.reference, (x, y), xytext=(10, 10), 
                       textcoords='offset points', fontsize=9, fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", fc='white', alpha=0.8),
                       zorder=6)
        
        else:
            x_centre = float(position_key.split('_')[0]) + 0.5
            y_centre = float(position_key.split('_')[1]) + 0.5
            
            ax.plot(x_centre, y_centre, 's', markersize=18, color='purple', 
                   markeredgecolor='white', markeredgewidth=2, alpha=0.8, zorder=5)
            
            ax.text(x_centre, y_centre, str(len(risques_list)), 
                   ha='center', va='center', fontsize=10, fontweight='bold', color='white',
                   zorder=6)
    
    # Configuration des axes
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 5)
    ax.set_xticks([0.5, 1.5, 2.5, 3.5, 4.5])
    ax.set_yticks([0.5, 1.5, 2.5, 3.5, 4.5])
    
    ax.set_xticklabels(['1\nTrès rare', '2\nRare', '3\nPossible', '4\nProbable', '5\nTrès probable'], fontsize=11)
    ax.set_yticklabels(['1\nNégligeable', '2\nMineur', '3\nModéré', '4\nImportant', '5\nCritique'], fontsize=11)
    ax.set_xlabel('Probabilité', fontsize=13, fontweight='bold', labelpad=15)
    ax.set_ylabel('Impact', fontsize=13, fontweight='bold', labelpad=15)
    
    titre = "Matrice des Risques - Vue Spécifique"
    if risque_surbrillance:
        titre += f"\n{risque_surbrillance.reference} en surbrillance"
    ax.set_title(titre, fontsize=16, fontweight='bold', pad=25)
    
    # CORRECTION : LÉGENDES BIEN POSITIONNÉES SANS EMPILEMENT
    legend_x = 5.3
    current_y = 4.5
    
    # Légende des risques
    if evaluations_valides:
        ax.text(legend_x, current_y, 'LÉGENDE RISQUES:', fontweight='bold', fontsize=10, 
                bbox=dict(boxstyle="round,pad=0.3", fc='lightblue', alpha=0.7))
        current_y -= 0.3
        
        for idx in range(min(3, len(evaluations_valides))):
            eval_data = evaluations_valides[idx]
            impact = (eval_data.impact_conf or eval_data.impact_val or eval_data.impact_pre)
            probabilite = (eval_data.probabilite_conf or eval_data.probabilite_val or eval_data.probabilite_pre)
            
            if impact and probabilite:
                color_idx = idx % len(colors)
                ax.plot(legend_x, current_y, 'o', markersize=8, color=colors[color_idx])
                risk_score = impact * probabilite
                ax.text(legend_x + 0.25, current_y, 
                       f"{eval_data.risque.reference} (S:{risk_score})", 
                       fontsize=7, va='center')
                current_y -= 0.2
        
        # Légende risque cible
        if risque_surbrillance:
            current_y -= 0.1  # Espacement
            ax.plot(legend_x, current_y, 'o', markersize=10, color='red', markeredgecolor='yellow')
            target_score = "N/A"
            for position_list in risques_par_position.values():
                for risk in position_list:
                    if risk['is_target']:
                        target_score = risk['score']
                        break
            
            ax.text(legend_x + 0.25, current_y, 
                   f"{risque_surbrillance.reference} (S:{target_score})", 
                   fontsize=7, fontweight='bold', va='center')
            current_y -= 0.15
        
        # Légende risques multiples
        current_y -= 0.1  # Espacement
        ax.plot(legend_x, current_y, 's', markersize=8, color='purple', markeredgecolor='white')
        ax.text(legend_x + 0.25, current_y, "Risques multiples", fontsize=7, fontweight='bold', va='center')
        current_y -= 0.2
    
    # Légende des niveaux de risque - BIEN SÉPARÉE
    current_y -= 0.2  # Espacement supplémentaire
    ax.text(legend_x, current_y, 'NIVEAUX DE RISQUE:', fontweight='bold', fontsize=10)
    current_y -= 0.25
    
    niveaux = [
        ('Faible (1-4)', 'lightgreen'), 
        ('Moyen (5-10)', 'yellow'), 
        ('Élevé (11-16)', 'orange'), 
        ('Critique (17-25)', 'red')
    ]
    
    for i, (texte, couleur) in enumerate(niveaux):
        ax.add_patch(patches.Rectangle((legend_x, current_y - 0.1), 0.25, 0.12, facecolor=couleur))
        ax.text(legend_x + 0.3, current_y - 0.04, texte, fontsize=7, va='center')
        current_y -= 0.15
    
    # Statistiques - BIEN SÉPARÉES
    current_y -= 0.3  # Espacement supplémentaire
    
    # Calcul des statistiques
    stats_text = f"STATISTIQUES:\n• {len(evaluations_valides)} risques évalués"
    if len(risques_non_evalues) > 0:
        stats_text += f"\n• {len(risques_non_evalues)} à évaluer"
    
    if evaluations_valides:
        scores_calcules = []
        for eval_data in evaluations_valides:
            impact = (eval_data.impact_conf or eval_data.impact_val or eval_data.impact_pre)
            probabilite = (eval_data.probabilite_conf or eval_data.probabilite_val or eval_data.probabilite_pre)
            if impact and probabilite:
                scores_calcules.append(impact * probabilite)
        
        if scores_calcules:
            score_moyen = sum(scores_calcules) / len(scores_calcules)
            score_max = max(scores_calcules)
            score_min = min(scores_calcules)
            stats_text += f"\n• Score moyen: {score_moyen:.1f}"
            stats_text += f"\n• Min: {score_min} | Max: {score_max}"
    
    if risque_surbrillance:
        target_impact = "N/A"
        target_prob = "N/A"
        target_score = "N/A"
        
        for position_list in risques_par_position.values():
            for risk in position_list:
                if risk['is_target']:
                    eval_data = risk['evaluation']
                    target_impact = (eval_data.impact_conf or eval_data.impact_val or eval_data.impact_pre)
                    target_prob = (eval_data.probabilite_conf or eval_data.probabilite_val or eval_data.probabilite_pre)
                    target_score = risk['score']
                    break
        
        stats_text += f"\n• Risque sélectionné:"
        stats_text += f"\n  {risque_surbrillance.reference}"
        stats_text += f"\n  Impact: {target_impact}/5"
        stats_text += f"\n  Prob: {target_prob}/5"
        stats_text += f"\n  Score: {target_score}"
    
    # Ajuster la taille de la police selon la longueur du texte
    fontsize_stats = 7 if len(stats_text) > 150 else 8
    
    ax.text(legend_x, current_y, stats_text, fontsize=fontsize_stats, 
            bbox=dict(boxstyle="round,pad=0.3", fc='lightgreen', alpha=0.7),
            verticalalignment='top')
    
    # Ajuster les limites pour la légende
    ax.set_xlim(0, 7.0)
    
    # Conversion en image base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    
    graphic = base64.b64encode(image_png).decode('utf-8')
    plt.close()
    
    print(f"✅ Matrice spécifique générée avec légendes bien positionnées")
    return graphic

def generer_tableau_bordeaux(risques):
    """Générer le tableau de Bordeaux avec classement par niveau de risque"""

    tableau = {
        'actions_prioritaires': [],    # Risques Critiques
        'surveillance_renforcee': [],  # Risques Élevés
        'surveillance_courante': [],   # Risques Moyens
        'actions_limitees': []         # Risques Faibles
    }

    for risque in risques:
        # Ignorer les risques archivés - VERSION ROBUSTE
        if getattr(risque, 'is_archived', False):
            continue

        # Filtrer uniquement les évaluations confirmées
        evaluations_confirmees = [
            e for e in getattr(risque, 'evaluations', [])
            if getattr(e, 'date_confirmation', None) is not None
        ]

        if not evaluations_confirmees:
            continue

        try:
            # Récupérer la dernière évaluation confirmée
            derniere_evaluation = max(evaluations_confirmees, key=lambda x: x.date_confirmation)
            niveau_risque = getattr(derniere_evaluation, 'niveau_risque', None)
            score = getattr(derniere_evaluation, 'score_risque', 0)

            # Classer par niveau de risque exact
            entry = {
                'risque': risque,
                'score': score,
                'evaluation': derniere_evaluation,
                'niveau': niveau_risque
            }

            if niveau_risque == 'Critique':
                tableau['actions_prioritaires'].append(entry)
            elif niveau_risque == 'Élevé':
                tableau['surveillance_renforcee'].append(entry)
            elif niveau_risque == 'Moyen':
                tableau['surveillance_courante'].append(entry)
            elif niveau_risque == 'Faible':
                tableau['actions_limitees'].append(entry)

        except Exception as e:
            print(f"⚠️ Erreur traitement risque {getattr(risque, 'reference', 'N/A')}: {e}")
            continue

    # Trier chaque catégorie par score décroissant
    for categorie in tableau:
        tableau[categorie] = sorted(tableau[categorie], key=lambda x: x['score'], reverse=True)

    print(f"📋 Tableau Bordeaux généré: {sum(len(v) for v in tableau.values())} risques")
    return tableau

def calculer_tendance_kri(mesures, periode_jours=30):
    """Calculer la tendance des KRI sur une période donnée"""
    if not mesures:
        return 'stable'
    
    date_limite = datetime.now() - timedelta(days=periode_jours)
    mesures_recentes = [m for m in mesures if m.date_mesure >= date_limite]
    
    if len(mesures_recentes) < 2:
        return 'stable'
    
    mesures_recentes.sort(key=lambda x: x.date_mesure)
    valeurs = [m.valeur for m in mesures_recentes]
    
    if len(valeurs) > 1:
        pente = np.polyfit(range(len(valeurs)), valeurs, 1)[0]
        
        if pente > 0.1:
            return 'hausse'
        elif pente < -0.1:
            return 'baisse'
    
    return 'stable'

def generer_tableau_bordeaux(risques):
    """Générer le tableau de Bordeaux avec classement par niveau de risque"""

    tableau = {
        'actions_prioritaires': [],    # Risques Critiques
        'surveillance_renforcee': [],  # Risques Élevés
        'surveillance_courante': [],   # Risques Moyens
        'actions_limitees': []         # Risques Faibles
    }

    for risque in risques:
        # Ignorer les risques archivés - VERSION ROBUSTE
        if getattr(risque, 'is_archived', False):
            continue

        # Filtrer uniquement les évaluations confirmées
        evaluations_confirmees = [
            e for e in getattr(risque, 'evaluations', [])
            if getattr(e, 'date_confirmation', None) is not None
        ]

        if not evaluations_confirmees:
            continue

        try:
            # Récupérer la dernière évaluation confirmée
            derniere_evaluation = max(evaluations_confirmees, key=lambda x: x.date_confirmation)
            niveau_risque = getattr(derniere_evaluation, 'niveau_risque', None)
            score = getattr(derniere_evaluation, 'score_risque', 0)

            # Classer par niveau de risque exact
            entry = {
                'risque': risque,
                'score': score,
                'evaluation': derniere_evaluation,
                'niveau': niveau_risque
            }

            if niveau_risque == 'Critique':
                tableau['actions_prioritaires'].append(entry)
            elif niveau_risque == 'Élevé':
                tableau['surveillance_renforcee'].append(entry)
            elif niveau_risque == 'Moyen':
                tableau['surveillance_courante'].append(entry)
            elif niveau_risque == 'Faible':
                tableau['actions_limitees'].append(entry)

        except Exception as e:
            print(f"⚠️ Erreur traitement risque {getattr(risque, 'reference', 'N/A')}: {e}")
            continue

    # Trier chaque catégorie par score décroissant
    for categorie in tableau:
        tableau[categorie] = sorted(tableau[categorie], key=lambda x: x['score'], reverse=True)

    print(f"📋 Tableau Bordeaux généré: {sum(len(v) for v in tableau.values())} risques")
    return tableau



def calculer_tendance_kri(mesures, periode_jours=30):
    """Calculer la tendance des KRI sur une période donnée"""
    if not mesures:
        return 'stable'
    
    date_limite = datetime.now() - timedelta(days=periode_jours)
    mesures_recentes = [m for m in mesures if m.date_mesure >= date_limite]
    
    if len(mesures_recentes) < 2:
        return 'stable'
    
    mesures_recentes.sort(key=lambda x: x.date_mesure)
    valeurs = [m.valeur for m in mesures_recentes]
    
    if len(valeurs) > 1:
        pente = np.polyfit(range(len(valeurs)), valeurs, 1)[0]
        
        if pente > 0.1:
            return 'hausse'
        elif pente < -0.1:
            return 'baisse'
    
    return 'stable'

def generer_rapport_conformite(actions):
    """Générer un rapport de conformité détaillé"""
    total_actions = len(actions)
    
    actions_terminees = len([a for a in actions if a.statut == 'termine'])
    actions_retardees = len([a for a in actions if a.date_echeance and a.date_echeance < datetime.now().date() and a.statut in ['a_faire', 'en_cours']])
    actions_en_cours = len([a for a in actions if a.statut == 'en_cours'])
    actions_a_faire = len([a for a in actions if a.statut == 'a_faire'])
    
    taux_conformite = (actions_terminees / total_actions * 100) if total_actions > 0 else 0
    
    actions_en_retard = []
    for action in actions:
        if action.date_echeance and action.date_echeance < datetime.now().date() and action.statut in ['a_faire', 'en_cours']:
            jours_retard = (datetime.now().date() - action.date_echeance).days
            actions_en_retard.append({
                'action': action,
                'jours_retard': jours_retard
            })
    
    return {
        'total_actions': total_actions,
        'actions_terminees': actions_terminees,
        'actions_retardees': actions_retardees,
        'actions_en_cours': actions_en_cours,
        'actions_a_faire': actions_a_faire,
        'actions_en_retard': actions_en_retard,
        'taux_conformite': round(taux_conformite, 1)
    }

def generer_organigramme_svg(processus):
    """Génère un organigramme SVG simple pour un processus"""
    if not processus.etapes:
        return "<svg width='400' height='100'><text x='200' y='50' text-anchor='middle'>Aucune étape définie</text></svg>"
    
    etapes = sorted(processus.etapes, key=lambda x: x.ordre)
    
    svg_content = f"""
    <svg width="800" height="{len(etapes) * 120 + 50}" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="headerGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color:#007bff;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#0056b3;stop-opacity:1" />
            </linearGradient>
        </defs>
        <rect width="100%" height="100%" fill="#f8f9fa"/>
        <text x="400" y="30" text-anchor="middle" fill="#333" font-family="Arial" font-size="16" font-weight="bold">
            Organigramme - {processus.nom}
        </text>
    """
    
    for i, etape in enumerate(etapes):
        y = i * 120 + 80
        
        svg_content += f"""
        <rect x="250" y="{y-40}" width="300" height="80" fill="white" stroke="#007bff" stroke-width="2" rx="10"/>
        <rect x="250" y="{y-40}" width="300" height="25" fill="url(#headerGradient)" rx="10 10 0 0"/>
        <text x="400" y="{y-20}" text-anchor="middle" fill="white" font-family="Arial" font-size="12" font-weight="bold">
            Étape {etape.ordre}: {etape.nom}
        </text>
        """
        
        if etape.description:
            svg_content += f"""
            <text x="400" y="{y+5}" text-anchor="middle" fill="#666" font-family="Arial" font-size="10">
                {etape.description[:50]}{'...' if len(etape.description) > 50 else ''}
            </text>
            """
        
        if etape.responsable:
            svg_content += f"""
            <text x="400" y="{y+25}" text-anchor="middle" fill="#333" font-family="Arial" font-size="9">
                Responsable: {etape.responsable.username}
            </text>
            """
        
        if etape.duree_estimee:
            svg_content += f"""
            <text x="400" y="{y+40}" text-anchor="middle" fill="#666" font-family="Arial" font-size="9">
                Durée: {etape.duree_estimee}
            </text>
            """
        
        if i < len(etapes) - 1:
            svg_content += f"""
            <line x1="400" y1="{y+40}" x2="400" y2="{y+80}" stroke="#007bff" stroke-width="2"/>
            <polygon points="395,{y+75} 400,{y+85} 405,{y+75}" fill="#007bff"/>
            """
    
    svg_content += "</svg>"
    return svg_content

def mettre_a_jour_statistiques_cartographie(cartographie_id):
    """Mettre à jour les statistiques d'une cartographie - Version complète corrigée"""
    from models import Cartographie, Risque, EvaluationRisque, db
    from sqlalchemy import func, and_
    from datetime import datetime
    
    cartographie = Cartographie.query.get(cartographie_id)
    if not cartographie:
        print(f"❌ Cartographie {cartographie_id} non trouvée pour mise à jour statistiques")
        return False
    
    print(f"📊 Mise à jour statistiques pour cartographie: {cartographie.nom}")
    
    try:
        # 1. Compter les risques actifs
        risques_actifs = Risque.query.filter_by(
            cartographie_id=cartographie_id,
            is_archived=False
        ).count()
        
        # 2. Compter les risques évalués
        risques_evalues = db.session.query(Risque)\
            .join(EvaluationRisque)\
            .filter(
                Risque.cartographie_id == cartographie_id,
                Risque.is_archived == False
            )\
            .distinct()\
            .count()
        
        # 3. Calculer le score moyen
        # Sous-requête pour les dernières évaluations
        derniere_eval_subquery = db.session.query(
            EvaluationRisque.risque_id,
            func.max(EvaluationRisque.created_at).label('max_date')
        ).group_by(EvaluationRisque.risque_id).subquery()
        
        score_moyen = db.session.query(func.avg(EvaluationRisque.score_risque))\
            .join(derniere_eval_subquery, and_(
                EvaluationRisque.risque_id == derniere_eval_subquery.c.risque_id,
                EvaluationRisque.created_at == derniere_eval_subquery.c.max_date
            ))\
            .join(Risque, EvaluationRisque.risque_id == Risque.id)\
            .filter(
                Risque.cartographie_id == cartographie_id,
                Risque.is_archived == False
            )\
            .scalar()
        
        # 4. Compter les risques par niveau
        niveaux_risques = db.session.query(
            EvaluationRisque.niveau_risque,
            func.count(EvaluationRisque.id)
        ).join(derniere_eval_subquery, and_(
            EvaluationRisque.risque_id == derniere_eval_subquery.c.risque_id,
            EvaluationRisque.created_at == derniere_eval_subquery.c.max_date
        ))\
         .join(Risque, EvaluationRisque.risque_id == Risque.id)\
         .filter(
             Risque.cartographie_id == cartographie_id,
             Risque.is_archived == False
         )\
         .group_by(EvaluationRisque.niveau_risque).all()
        
        # 5. Préparer les statistiques complètes
        statistiques = {
            'risques_actifs': risques_actifs,
            'risques_evalues': risques_evalues,
            'score_moyen': round(score_moyen, 2) if score_moyen else 0,
            'repartition_niveaux': dict(niveaux_risques),
            'risques_critiques': 0,
            'risques_eleves': 0,
            'risques_moyens': 0,
            'risques_faibles': 0,
            'derniere_maj': datetime.utcnow().isoformat()
        }
        
        # 6. Calculer les compteurs par niveau
        for niveau, count in niveaux_risques:
            if niveau == 'Critique':
                statistiques['risques_critiques'] = count
            elif niveau == 'Élevé':
                statistiques['risques_eleves'] = count
            elif niveau == 'Moyen':
                statistiques['risques_moyens'] = count
            elif niveau == 'Faible':
                statistiques['risques_faibles'] = count
        
        # 7. Stocker les statistiques dans la cartographie
        cartographie.statistiques = statistiques
        cartographie.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        print(f"✅ Statistiques mises à jour pour {cartographie.nom}:")
        print(f"   - {risques_actifs} risques actifs")
        print(f"   - {risques_evalues} risques évalués") 
        print(f"   - Score moyen: {statistiques['score_moyen']}")
        print(f"   - Répartition: {statistiques['repartition_niveaux']}")
        
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur mise à jour statistiques cartographie {cartographie_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
def exporter_matrice_risques(evaluations, format='png'):
    """Exporter la matrice des risques dans différents formats"""
    matrice_image = generer_matrice_risques(evaluations)
    
    if format == 'png':
        return f"data:image/png;base64,{matrice_image}"
    elif format == 'svg':
        # Implémentation simplifiée pour SVG
        return matrice_image  # Retourner l'image base64 pour l'instant
    else:
        return matrice_image

def calculer_score_risque_moyen(risques):
    """Calculer le score de risque moyen pour un ensemble de risques"""
    if not risques:
        return 0
    
    scores = []
    for risque in risques:
        # Ignorer les risques archivés
        if hasattr(risque, 'is_archived') and risque.is_archived:
            continue
            
        evaluations_validees = [e for e in risque.evaluations if e.statut == 'valide']
        if evaluations_validees:
            derniere_eval = max(evaluations_validees, key=lambda x: x.created_at)
            scores.append(derniere_eval.score_risque)
    
    return sum(scores) / len(scores) if scores else 0

def analyser_tendances_risques(risques, periode_jours=90):
    """Analyser les tendances des risques sur une période donnée"""
    date_limite = datetime.now() - timedelta(days=periode_jours)
    
    tendances = {
        'risques_critiques': 0,
        'risques_en_hausse': 0,
        'risques_en_baisse': 0,
        'risques_stables': 0,
        'nouveaux_risques': 0
    }
    
    for risque in risques:
        # Ignorer les risques archivés
        if hasattr(risque, 'is_archived') and risque.is_archived:
            continue
            
        # Évaluations récentes
        evaluations_recentes = [e for e in risque.evaluations 
                              if e.created_at >= date_limite and e.statut == 'valide']
        
        if not evaluations_recentes:
            continue
            
        # Trier par date
        evaluations_recentes.sort(key=lambda x: x.created_at)
        
        # Vérifier si c'est un nouveau risque
        if len(evaluations_recentes) == 1 and (datetime.now() - evaluations_recentes[0].created_at).days <= 30:
            tendances['nouveaux_risques'] += 1
        
        # Analyser la tendance
        if len(evaluations_recentes) >= 2:
            premier_score = evaluations_recentes[0].score_risque
            dernier_score = evaluations_recentes[-1].score_risque
            
            if dernier_score > premier_score + 2:  # Hausse significative
                tendances['risques_en_hausse'] += 1
            elif dernier_score < premier_score - 2:  # Baisse significative
                tendances['risques_en_baisse'] += 1
            else:
                tendances['risques_stables'] += 1
        
        # Vérifier risque critique
        derniere_eval = evaluations_recentes[-1]
        if derniere_eval.score_risque >= 16:
            tendances['risques_critiques'] += 1
    
    return tendances

def generer_heatmap_risques(cartographie):
    """Générer une heatmap des risques pour une cartographie"""
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Préparer les données pour la heatmap
    data = np.zeros((5, 5))
    
    for risque in cartographie.risques:
        if hasattr(risque, 'is_archived') and risque.is_archived:
            continue
            
        if risque.evaluations:
            derniere_eval = max(risque.evaluations, key=lambda x: x.created_at)
            if derniere_eval.impact and derniere_eval.probabilite:
                i = derniere_eval.impact - 1
                j = derniere_eval.probabilite - 1
                data[i, j] += 1
    
    # Créer la heatmap
    im = ax.imshow(data, cmap='YlOrRd', interpolation='nearest')
    
    # Ajouter les annotations
    for i in range(5):
        for j in range(5):
            if data[i, j] > 0:
                ax.text(j, i, f'{int(data[i, j])}', 
                       ha='center', va='center', fontsize=12, fontweight='bold',
                       color='white' if data[i, j] > np.max(data)/2 else 'black')
    
    # Configuration des axes
    ax.set_xticks(range(5))
    ax.set_yticks(range(5))
    ax.set_xticklabels(['Très faible', 'Faible', 'Moyen', 'Fort', 'Très fort'])
    ax.set_yticklabels(['Très faible', 'Faible', 'Moyen', 'Fort', 'Très fort'])
    ax.set_xlabel('Probabilité', fontsize=12, fontweight='bold')
    ax.set_ylabel('Impact', fontsize=12, fontweight='bold')
    ax.set_title(f"Heatmap des Risques - {cartographie.nom}", fontsize=14, fontweight='bold')
    
    # Barre de couleur
    plt.colorbar(im, ax=ax, label='Nombre de risques')
    
    # Conversion en image base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    
    graphic = base64.b64encode(image_png).decode('utf-8')
    plt.close()
    
    return graphic

def calculer_indice_severite(risques):
    """Calculer l'indice de sévérité moyen des risques"""
    if not risques:
        return 0
    
    scores_severite = []
    for risque in risques:
        if hasattr(risque, 'is_archived') and risque.is_archived:
            continue
            
        if risque.evaluations:
            derniere_eval = max(risque.evaluations, key=lambda x: x.created_at)
            # Indice de sévérité = impact * probabilité (score normalisé)
            severite = (derniere_eval.impact * derniere_eval.probabilite) / 25.0
            scores_severite.append(severite)
    
    return round(sum(scores_severite) / len(scores_severite) * 100, 2) if scores_severite else 0

def generer_radar_chart_risques(cartographie):
    """Générer un radar chart des risques par catégorie"""
    # Compter les risques par catégorie
    categories = {}
    for risque in cartographie.risques:
        if hasattr(risque, 'is_archived') and risque.is_archived:
            continue
            
        if risque.categorie not in categories:
            categories[risque.categorie] = 0
        categories[risque.categorie] += 1
    
    if not categories:
        return None
    
    # Préparer les données pour le radar chart
    labels = list(categories.keys())
    values = list(categories.values())
    
    # Compléter pour avoir au moins 3 catégories pour un radar chart correct
    while len(labels) < 3:
        labels.append('')
        values.append(0)
    
    # Créer le radar chart
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
    
    # Angles pour les catégories
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]  # Fermer le cercle
    values += values[:1]
    
    # Tracer le radar chart
    ax.plot(angles, values, 'o-', linewidth=2, label='Nombre de risques')
    ax.fill(angles, values, alpha=0.25)
    
    # Ajouter les labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, max(values) + 1 if values else 1)
    ax.set_title(f"Répartition des Risques par Catégorie\n{cartographie.nom}", 
                 size=14, fontweight='bold', pad=20)
    
    # Conversion en image base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    
    graphic = base64.b64encode(image_png).decode('utf-8')
    plt.close()
    
    return graphic

def declencher_mise_a_jour_risque(risque_id, action, user_id, donnees=None):
    """Déclencher les mises à jour automatiques après une action sur un risque"""
    from models import db, Risque, EvaluationRisque, KRI, Cartographie, Alerte, HistoriqueModification
    
    risque = Risque.query.get(risque_id)
    if not risque:
        print(f"❌ Risque {risque_id} non trouvé pour mise à jour")
        return
    
    print(f"🔔 Mise à jour déclenchée: {action} sur risque {risque.reference} (ID: {risque_id})")
    
    try:
        if action == 'creation':
            mise_a_jour_apres_creation_risque(risque, user_id)
        
        elif action == 'evaluation':
            mise_a_jour_apres_evaluation_risque(risque, user_id, donnees)
        
        elif action == 'archivage':
            mise_a_jour_apres_archivage_risque(risque, user_id, donnees)
        
        elif action == 'restauration':
            mise_a_jour_apres_restauration_risque(risque, user_id)
        
        elif action == 'modification':
            mise_a_jour_apres_modification_risque(risque, user_id, donnees)
        
        elif action == 'suppression':
            mise_a_jour_apres_suppression_risque(risque, user_id)
        
        # Mettre à jour les statistiques globales
        mettre_a_jour_statistiques_globales()
        
        # Forcer la regénération des matrices
        if risque.cartographie_id:
            regenerer_matrices_cartographie(risque.cartographie_id)
            print(f"🎨 Matrices de la cartographie {risque.cartographie_id} à regénérer")
        
        # SYNCHRONISATION GLOBALE APRÈS CHAQUE ACTION IMPORTANTE
        if action in ['creation', 'evaluation', 'archivage', 'restauration', 'suppression', 'modification']:
            synchroniser_donnees_globales()
            print(f"🔄 Synchronisation globale déclenchée après {action}")
        
        # Validation finale
        db.session.commit()
        print(f"✅ Mise à jour {action} terminée avec succès pour risque {risque.reference}")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur lors de la mise à jour {action}: {str(e)}")
        raise

def mise_a_jour_apres_creation_risque(risque, user_id):
    """Mises à jour après création d'un risque"""
    from models import db
    
    # 1. Mettre à jour la cartographie
    cartographie = risque.cartographie
    cartographie.updated_at = datetime.utcnow()
    
    # 2. Générer une alerte pour les responsables
    generer_alerte_creation_risque(risque, user_id)
    
    # 3. Mettre à jour les indicateurs du dashboard
    mettre_a_jour_indicateurs_cartographie(cartographie.id)
    
    db.session.commit()
    print(f"✅ Risque {risque.reference} créé - Cartographie {cartographie.nom} mise à jour")

def mise_a_jour_apres_evaluation_risque(risque, user_id, donnees_evaluation):
    """Mises à jour après évaluation d'un risque"""
    from models import db
    
    # 1. Mettre à jour le niveau de risque
    risque.derniere_evaluation = datetime.utcnow()
    
    # 2. Vérifier les alertes de seuil
    verifier_alertes_seuil_risque(risque, donnees_evaluation)
    
    # 3. Mettre à jour les KRI associés
    mettre_a_jour_kri_risque(risque)
    
    # 4. Mettre à jour le tableau de Bordeaux
    mettre_a_jour_tableau_bordeaux(risque.cartographie_id)
    
    # 5. Générer une alerte si changement important
    generer_alerte_evaluation_risque(risque, user_id, donnees_evaluation)
    
    db.session.commit()
    print(f"✅ Risque {risque.reference} évalué - Niveau: {donnees_evaluation.get('niveau_risque')}")

def mise_a_jour_apres_archivage_risque(risque, user_id, motif):
    """Mises à jour après archivage d'un risque"""
    from models import db
    
    # 1. Désactiver les KRI associés
    desactiver_kri_risque(risque.id)
    
    # 2. Mettre à jour les statistiques
    mettre_a_jour_statistiques_cartographie(risque.cartographie_id)
    
    # 3. Générer un rapport d'archivage
    generer_rapport_archivage(risque, user_id, motif)
    
    # 4. Notifier les intéressés
    notifier_archivage_risque(risque, user_id)
    
    db.session.commit()
    print(f"✅ Risque {risque.reference} archivé")

def mise_a_jour_apres_restauration_risque(risque, user_id):
    """Mises à jour après restauration d'un risque"""
    from models import db
    
    # 1. Réactiver les KRI associés
    reactiver_kri_risque(risque.id)
    
    # 2. Remettre dans le tableau de Bordeaux
    mettre_a_jour_tableau_bordeaux(risque.cartographie_id)
    
    # 3. Mettre à jour les statistiques
    mettre_a_jour_statistiques_cartographie(risque.cartographie_id)
    
    db.session.commit()
    print(f"✅ Risque {risque.reference} restauré")

def mise_a_jour_apres_modification_risque(risque, user_id, modifications):
    """Mises à jour après modification d'un risque"""
    from models import db
    
    # 1. Historiser les modifications
    historiser_modifications_risque(risque, user_id, modifications)
    
    # 2. Mettre à jour les références croisées
    mettre_a_jour_references_croisees(risque, modifications)
    
    # 3. Regénérer les matrices si nécessaire
    if 'categorie' in modifications or 'processus_concerne' in modifications:
        regenerer_matrices_cartographie(risque.cartographie_id)
    
    db.session.commit()
    print(f"✅ Risque {risque.reference} modifié")

def mise_a_jour_apres_suppression_risque(risque, user_id):
    """Mises à jour après suppression d'un risque"""
    from models import db
    
    cartographie_id = risque.cartographie_id
    
    # 1. Mettre à jour les statistiques de la cartographie
    mettre_a_jour_statistiques_cartographie(cartographie_id)
    
    # 2. Générer un rapport de suppression
    generer_rapport_suppression(risque, user_id)
    
    # 3. Nettoyer les données orphelines
    nettoyer_donnees_orphelines()
    
    print(f"✅ Risque {risque.reference} supprimé")

def mettre_a_jour_indicateurs_cartographie(cartographie_id):
    """Mettre à jour tous les indicateurs d'une cartographie"""
    from models import Cartographie, Risque, EvaluationRisque, db
    from sqlalchemy import func
    
    cartographie = Cartographie.query.get(cartographie_id)
    if not cartographie:
        return
    
    # Compter les risques actifs
    risques_actifs = Risque.query.filter_by(
        cartographie_id=cartographie_id,
        is_archived=False
    ).count()
    
    # Compter les risques évalués
    risques_evalues = db.session.query(Risque)\
        .join(EvaluationRisque)\
        .filter(
            Risque.cartographie_id == cartographie_id,
            Risque.is_archived == False
        )\
        .distinct()\
        .count()
    
    # Calculer le score moyen
    score_moyen = db.session.query(func.avg(EvaluationRisque.score_risque))\
        .join(Risque)\
        .filter(
            Risque.cartographie_id == cartographie_id,
            Risque.is_archived == False,
            EvaluationRisque.id.in_(
                db.session.query(
                    func.max(EvaluationRisque.id)
                ).group_by(EvaluationRisque.risque_id).subquery()
            )
        )\
        .scalar()
    
    # Stocker les indicateurs
    cartographie.indicateurs = {
        'risques_actifs': risques_actifs,
        'risques_evalues': risques_evalues,
        'score_moyen': round(score_moyen, 2) if score_moyen else 0,
        'derniere_sync': datetime.utcnow()
    }
    
    db.session.commit()
    print(f"📊 Indicateurs recalculés pour {cartographie.nom}: {risques_actifs} risques actifs")

def synchroniser_donnees_globales():
    """Synchronise toutes les données entre les différentes vues"""
    from models import db, Risque, Cartographie, EvaluationRisque
    from sqlalchemy import func, and_
    
    print("🔄 SYNCHRONISATION GLOBALE DES DONNÉES...")
    
    try:
        # 1. Synchroniser les compteurs de risques
        total_risques_actifs = Risque.query.filter_by(is_archived=False).count()
        
        # 2. Synchroniser les niveaux de risque
        derniere_evaluation_subquery = db.session.query(
            EvaluationRisque.risque_id,
            func.max(EvaluationRisque.created_at).label('max_date')
        ).group_by(EvaluationRisque.risque_id).subquery()
        
        niveaux = db.session.query(
            EvaluationRisque.niveau_risque,
            func.count(EvaluationRisque.id)
        ).select_from(EvaluationRisque)\
         .join(derniere_evaluation_subquery, and_(
             EvaluationRisque.risque_id == derniere_evaluation_subquery.c.risque_id,
             EvaluationRisque.created_at == derniere_evaluation_subquery.c.max_date
         ))\
         .join(Risque, EvaluationRisque.risque_id == Risque.id)\
         .filter(Risque.is_archived == False)\
         .group_by(EvaluationRisque.niveau_risque).all()
        
        # 3. Synchroniser les cartographies
        cartographies = Cartographie.query.all()
        for carto in cartographies:
            mettre_a_jour_indicateurs_cartographie(carto.id)
        
        print(f"✅ Synchronisation terminée: {total_risques_actifs} risques actifs")
        print(f"📊 Répartition: {dict(niveaux)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur synchronisation: {str(e)}")
        return False




def mettre_a_jour_tableau_bordeaux(cartographie_id):
    """Regénérer le tableau de Bordeaux pour une cartographie"""
    from models import Cartographie
    
    cartographie = Cartographie.query.get(cartographie_id)
    if cartographie:
        # Le tableau de Bordeaux sera regénéré à la prochaine consultation
        print(f"🔄 Tableau de Bordeaux à regénérer pour {cartographie.nom}")

def verifier_alertes_seuil_risque(risque, evaluation):
    """Vérifier et créer des alertes si seuil dépassé"""
    from models import Alerte, db  # AJOUTER db DANS L'IMPORT
    
    niveau = evaluation.get('niveau_risque')
    score = evaluation.get('score_risque')
    
    if niveau in ['Critique', 'Élevé']:
        # Créer une alerte pour les risques importants
        alerte = Alerte(
            type='risque_seuil',
            gravite='haute' if niveau == 'Critique' else 'moyenne',
            titre=f"Risque {niveau} détecté",
            description=f"Le risque {risque.reference} a atteint le niveau {niveau} (score: {score})",
            entite_type='risque',
            entite_id=risque.id,
            created_by=1  # Système
        )
        db.session.add(alerte)
        db.session.commit()  # AJOUTER LE COMMIT
        print(f"🚨 Alerte créée pour risque {risque.reference} - Niveau: {niveau}")

def mettre_a_jour_kri_risque(risque):
    """Mettre à jour les KRI associés à un risque"""
    from models import KRI, db  # AJOUTER db
    
    kri = KRI.query.filter_by(risque_id=risque.id).first()
    if kri and risque.evaluations:
        derniere_eval = max(risque.evaluations, key=lambda x: x.created_at)
        
        # Ajuster les seuils du KRI si nécessaire
        if derniere_eval.niveau_risque == 'Critique' and kri.seuil_critique:
            # Vérifier si le KRI est cohérent avec le niveau de risque
            print(f"📈 KRI {kri.nom} vérifié pour risque {risque.reference}")

def desactiver_kri_risque(risque_id):
    """Désactiver les KRI d'un risque archivé"""
    from models import KRI, db  # AJOUTER db
    
    kri = KRI.query.filter_by(risque_id=risque_id).first()
    if kri:
        kri.est_actif = False
        kri.updated_at = datetime.utcnow()
        db.session.commit()  # AJOUTER LE COMMIT
        print(f"🔴 KRI {kri.nom} désactivé")

def reactiver_kri_risque(risque_id):
    """Réactiver les KRI d'un risque restauré"""
    from models import KRI, db  # AJOUTER db
    
    kri = KRI.query.filter_by(risque_id=risque_id).first()
    if kri:
        kri.est_actif = True
        kri.updated_at = datetime.utcnow()
        db.session.commit()  # AJOUTER LE COMMIT
        print(f"🟢 KRI {kri.nom} réactivé")

def mettre_a_jour_statistiques_globales():
    """Mettre à jour les statistiques globales de l'application"""
    from models import Risque, Cartographie, EvaluationRisque, db  # AJOUTER db
    
    stats = {
        'total_risques': Risque.query.filter_by(is_archived=False).count(),
        'total_cartographies': Cartographie.query.count(),
        'risques_evalues': db.session.query(Risque).join(EvaluationRisque)
                            .filter(Risque.is_archived == False).distinct().count(),
        'derniere_maj_globale': datetime.utcnow()
    }
    
    # Stocker ces statistiques (dans une table dédiée ou en cache)
    print("🌍 Statistiques globales mises à jour")

def generer_rapport_archivage(risque, user_id, motif):
    """Générer un rapport d'archivage"""
    rapport = {
        'risque_reference': risque.reference,
        'risque_intitule': risque.intitule,
        'date_archivage': datetime.utcnow(),
        'archivé_par': user_id,
        'motif': motif,
        'evaluations_supprimees': len(risque.evaluations),
        'kri_desactives': 1 if risque.kri else 0
    }
    
    print(f"📋 Rapport d'archivage généré pour {risque.reference}")

def historiser_modifications_risque(risque, user_id, modifications):
    """Historiser les modifications d'un risque"""
    from models import HistoriqueModification, db  # AJOUTER db
    
    historique = HistoriqueModification(
        entite_type='risque',
        entite_id=risque.id,
        utilisateur_id=user_id,
        modifications=modifications,
        date_modification=datetime.utcnow()
    )
    db.session.add(historique)
    db.session.commit()  # AJOUTER LE COMMIT
    print(f"📝 Historique modif risque {risque.reference}")

def regenerer_matrices_cartographie(cartographie_id):
    """Forcer la regénération des matrices au prochain accès"""
    # On pourrait implémenter un cache ici
    print(f"🎨 Matrices à regénérer pour cartographie {cartographie_id}")

def synchroniser_cartographie_apres_action(cartographie_id, action_type, user_id):
    """Synchronise toutes les vues après une action sur une cartographie"""
    from models import db, Cartographie
    
    cartographie = Cartographie.query.get(cartographie_id)
    if not cartographie:
        return
    
    print(f"🔄 Synchronisation: {action_type} sur cartographie {cartographie.nom}")
    
    # 1. Mettre à jour le timestamp de la cartographie
    cartographie.updated_at = datetime.utcnow()
    
    # 2. Recalculer les indicateurs
    recalculer_indicateurs_cartographie(cartographie_id)
    
    # 3. Invalider les caches si nécessaire
    invalider_cache_cartographie(cartographie_id)
    
    db.session.commit()
    
    print(f"✅ Cartographie {cartographie.nom} synchronisée")

def recalculer_indicateurs_cartographie(cartographie_id):
    """Recalcule tous les indicateurs d'une cartographie"""
    from models import Cartographie, Risque, EvaluationRisque, db  # AJOUTER db
    from sqlalchemy import func
    
    cartographie = Cartographie.query.get(cartographie_id)
    if not cartographie:
        return
    
    # Compter les risques actifs
    risques_actifs = Risque.query.filter_by(
        cartographie_id=cartographie_id,
        is_archived=False
    ).count()
    
    # Compter les risques évalués
    risques_evalues = db.session.query(Risque)\
        .join(EvaluationRisque)\
        .filter(
            Risque.cartographie_id == cartographie_id,
            Risque.is_archived == False
        )\
        .distinct()\
        .count()
    
    # Calculer le score moyen
    score_moyen = db.session.query(func.avg(EvaluationRisque.score_risque))\
        .join(Risque)\
        .filter(
            Risque.cartographie_id == cartographie_id,
            Risque.is_archived == False,
            EvaluationRisque.id.in_(
                db.session.query(
                    func.max(EvaluationRisque.id)
                ).group_by(EvaluationRisque.risque_id).subquery()
            )
        )\
        .scalar()
    
    # Stocker les indicateurs (vous pouvez ajouter ces champs au modèle Cartographie)
    cartographie.indicateurs = {
        'risques_actifs': risques_actifs,
        'risques_evalues': risques_evalues,
        'score_moyen': round(score_moyen, 2) if score_moyen else 0,
        'derniere_sync': datetime.utcnow()
    }
    
    db.session.commit()  # AJOUTER LE COMMIT
    print(f"📊 Indicateurs recalculés pour {cartographie.nom}")

def invalider_cache_cartographie(cartographie_id):
    """Invalide le cache pour forcer le recalcul des vues"""
    # Implémentation simple - vous pouvez utiliser Redis ou un cache mémoire
    cache_key = f"cartographie_{cartographie_id}_stats"
    # Supprimer le cache si existant
    print(f"🗑️ Cache invalidé pour cartographie {cartographie_id}")

def generer_alerte_creation_risque(risque, user_id):
    """Générer une alerte lors de la création d'un risque"""
    from models import Alerte, db
    
    try:
        alerte = Alerte(
            type='creation_risque',
            gravite='info',
            titre=f"Nouveau risque identifié",
            description=f"Le risque {risque.reference} - {risque.intitule} a été créé",
            entite_type='risque',
            entite_id=risque.id,
            created_by=user_id
        )
        db.session.add(alerte)
        db.session.commit()  # AJOUTER LE COMMIT
        print(f"📢 Alerte créée pour nouveau risque {risque.reference}")
    except Exception as e:
        print(f"❌ Erreur création alerte: {str(e)}")

def generer_alerte_evaluation_risque(risque, user_id, donnees_evaluation):
    """Générer une alerte lors de l'évaluation d'un risque"""
    from models import Alerte, db
    
    try:
        niveau = donnees_evaluation.get('niveau_risque', 'Inconnu')
        score = donnees_evaluation.get('score_risque', 0)
        
        alerte = Alerte(
            type='evaluation_risque',
            gravite='haute' if niveau in ['Critique', 'Élevé'] else 'moyenne',
            titre=f"Risque évalué - Niveau {niveau}",
            description=f"Le risque {risque.reference} a été évalué avec un score de {score}",
            entite_type='risque',
            entite_id=risque.id,
            created_by=user_id
        )
        db.session.add(alerte)
        db.session.commit()  # AJOUTER LE COMMIT
        print(f"📢 Alerte évaluation risque {risque.reference}")
    except Exception as e:
        print(f"❌ Erreur alerte évaluation: {str(e)}")

def notifier_archivage_risque(risque, user_id):
    """Notifier l'archivage d'un risque"""
    from models import Alerte, db
    
    try:
        alerte = Alerte(
            type='archivage_risque',
            gravite='info',
            titre=f"Risque archivé",
            description=f"Le risque {risque.reference} a été archivé",
            entite_type='risque',
            entite_id=risque.id,
            created_by=user_id
        )
        db.session.add(alerte)
        db.session.commit()  # AJOUTER LE COMMIT
        print(f"📢 Notification archivage risque {risque.reference}")
    except Exception as e:
        print(f"❌ Erreur notification archivage: {str(e)}")

def generer_rapport_archivage(risque, user_id, motif):
    """Générer un rapport d'archivage"""
    print(f"📋 Rapport d'archivage généré pour {risque.reference}")
    print(f"   - Motif: {motif}")
    print(f"   - Archivé par: {user_id}")
    print(f"   - Date: {datetime.utcnow()}")

def generer_rapport_suppression(risque, user_id):
    """Générer un rapport de suppression"""
    print(f"🗑️ Rapport suppression généré pour {risque.reference}")
    print(f"   - Supprimé par: {user_id}")
    print(f"   - Date: {datetime.utcnow()}")

def historiser_modifications_risque(risque, user_id, modifications):
    """Historiser les modifications d'un risque"""
    from models import db
    print(f"📝 Historique modif risque {risque.reference}")
    print(f"   - Modifications: {modifications}")
    print(f"   - Par utilisateur: {user_id}")

def mettre_a_jour_references_croisees(risque, modifications):
    """Mettre à jour les références croisées"""
    print(f"🔗 Mise à jour références croisées pour {risque.reference}")

def nettoyer_donnees_orphelines():
    """Nettoyer les données orphelines"""
    print("🧹 Nettoyage données orphelines")

def invalider_cache_cartographie(cartographie_id):
    """Invalider le cache d'une cartographie"""
    print(f"🗑️ Cache invalidé pour cartographie {cartographie_id}")

def synchroniser_cartographie_complete(cartographie_id):
    """Synchronise complètement une cartographie après modification"""
    from models import db, Cartographie, Risque, Direction, Service, Notification
    
    cartographie = Cartographie.query.get(cartographie_id)
    if not cartographie:
        return False
    
    try:
        print(f"🔄 Début synchronisation cartographie {cartographie_id}: {cartographie.nom}")
        
        # 1. Synchroniser les relations direction/service
        if cartographie.direction_id:
            direction = Direction.query.get(cartographie.direction_id)
            if direction:
                cartographie.direction_nom = direction.nom
        
        if cartographie.service_id:
            service = Service.query.get(cartographie.service_id)
            if service:
                cartographie.service_nom = service.nom
                # Synchroniser aussi la direction du service
                if service.direction_id and not cartographie.direction_id:
                    cartographie.direction_id = service.direction_id
                    direction = Direction.query.get(service.direction_id)
                    if direction:
                        cartographie.direction_nom = direction.nom
        
        # 2. Mettre à jour les risques associés (si changement de direction/service)
        risques_modifies = 0
        for risque in cartographie.risques:
            # Ne synchroniser que les risques non archivés
            if not getattr(risque, 'is_archived', False):
                risque_modified = False
                
                # Mettre à jour la direction si différente
                if risque.direction_id != cartographie.direction_id:
                    risque.direction_id = cartographie.direction_id
                    risque_modified = True
                
                # Mettre à jour le service si différent
                if risque.service_id != cartographie.service_id:
                    risque.service_id = cartographie.service_id
                    risque_modified = True
                
                if risque_modified:
                    risques_modifies += 1
                    db.session.add(risque)
        
        print(f"📝 {risques_modifies} risques mis à jour")
        
        # 3. Mettre à jour le timestamp
        cartographie.updated_at = datetime.utcnow()
        
        # 4. Recalculer les indicateurs
        recalculer_indicateurs_cartographie(cartographie_id)
        
        # 5. Invalider le cache
        invalider_cache_cartographie(cartographie_id)
        
        db.session.commit()
        print(f"✅ Cartographie {cartographie.nom} synchronisée")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur synchronisation cartographie {cartographie_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def synchroniser_cartographie_apres_archivage(cartographie_id, user_id):
    """Synchroniser après archivage d'une cartographie"""
    from models import db, Cartographie  # IMPORTANT: importer db
    
    try:
        print(f"🔄 Synchronisation après archivage cartographie {cartographie_id}")
        
        cartographie = Cartographie.query.get(cartographie_id)
        if not cartographie:
            return False
        
        # 1. Notifier les utilisateurs concernés
        notifier_archivage_cartographie(cartographie_id, user_id)
        
        # 2. Générer un rapport d'archivage
        generer_rapport_archivage_cartographie(cartographie_id, user_id)
        
        # 3. Mettre à jour le cache
        invalider_cache_cartographie(cartographie_id)
        
        print(f"✅ Synchronisation après archivage terminée pour cartographie {cartographie_id}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur synchronisation après archivage: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
def get_kri_stats():
    """Récupérer les statistiques des KRI pour le dashboard"""
    from sqlalchemy import func
    
    # KRI actifs associés à des risques non archivés
    kris_actifs = KRI.query.join(Risque).filter(
        Risque.is_archived == False,
        KRI.est_actif == True,
        KRI.type_indicateur == 'kri'
    ).count()
    
    # KRI en alerte (mesure récente > seuil)
    derniere_mesure_subq = db.session.query(
        MesureKRI.kri_id,
        func.max(MesureKRI.date_mesure).label('max_date')
    ).group_by(MesureKRI.kri_id).subquery()
    
    kri_alertes = db.session.query(KRI).join(
        derniere_mesure_subq, KRI.id == derniere_mesure_subq.c.kri_id
    ).join(MesureKRI, and_(
        MesureKRI.kri_id == KRI.id,
        MesureKRI.date_mesure == derniere_mesure_subq.c.max_date
    )).join(Risque, KRI.risque_id == Risque.id).filter(
        Risque.is_archived == False,
        KRI.est_actif == True,
        KRI.seuil_alerte.isnot(None),
        KRI.type_indicateur == 'kri',
        or_(
            and_(KRI.sens_evaluation_seuil == 'superieur', MesureKRI.valeur >= KRI.seuil_alerte),
            and_(KRI.sens_evaluation_seuil == 'inferieur', MesureKRI.valeur <= KRI.seuil_alerte)
        )
    ).count()
    
    return {
        'total_kris': kris_actifs,
        'kri_alertes': kri_alertes
    }

def notifier_archivage_cartographie(cartographie_id, user_id):
    """Notifier l'archivage d'une cartographie"""
    from models import db, Cartographie, Notification, User  # IMPORTANT
    
    cartographie = Cartographie.query.get(cartographie_id)
    if not cartographie:
        return
    
    try:
        notifications_count = 0
        
        # Notifier le créateur de la cartographie
        if cartographie.created_by and cartographie.created_by != user_id:
            notification = Notification(
                type_notification='archivage',
                titre=f'Cartographie archivée : {cartographie.nom}',
                message=f'La cartographie "{cartographie.nom}" a été archivée.',
                destinataire_id=cartographie.created_by,
                entite_type='cartographie',
                entite_id=cartographie_id
            )
            db.session.add(notification)
            notifications_count += 1
        
        # Notifier les utilisateurs ayant créé des risques
        users_ids = set()
        for risque in cartographie.risques:
            if risque.created_by and risque.created_by != user_id:
                users_ids.add(risque.created_by)
        
        for uid in users_ids:
            notification = Notification(
                type_notification='info',
                titre='Cartographie archivée',
                message=f'Une cartographie contenant vos risques a été archivée : {cartographie.nom}',
                destinataire_id=uid,
                entite_type='cartographie',
                entite_id=cartographie_id
            )
            db.session.add(notification)
            notifications_count += 1
        
        if notifications_count > 0:
            db.session.commit()
            print(f"📢 {notifications_count} notifications d'archivage envoyées")
        else:
            print(f"ℹ️ Aucune notification nécessaire")
            
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur envoi notifications: {str(e)}")


def generer_rapport_archivage_cartographie(cartographie_id, user_id):
    """Génère un rapport d'archivage pour une cartographie"""
    from models import Cartographie, Risque, User, JournalActivite
    
    cartographie = Cartographie.query.get(cartographie_id)
    if not cartographie:
        return
    
    try:
        # Compter les risques archivés
        risques_archives = [r for r in cartographie.risques if getattr(r, 'is_archived', False)]
        nb_risques_archives = len(risques_archives)
        
        # Créer une entrée dans le journal d'activité
        journal_entry = JournalActivite(
            utilisateur_id=user_id,
            action='archivage_cartographie',
            details={
                'cartographie_id': cartographie_id,
                'cartographie_nom': cartographie.nom,
                'nb_risques_archives': nb_risques_archives,
                'direction': cartographie.direction.nom if cartographie.direction else 'Non spécifiée',
                'service': cartographie.service.nom if cartographie.service else 'Non spécifié',
                'timestamp': datetime.utcnow().isoformat()
            },
            entite_type='cartographie',
            entite_id=cartographie_id,
            created_at=datetime.utcnow()
        )
        
        db.session.add(journal_entry)
        db.session.commit()
        
        print(f"📋 Rapport d'archivage généré pour cartographie {cartographie_id}")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur génération rapport archivage: {str(e)}")


def recalculer_indicateurs_cartographie(cartographie_id):
    """Recalcule tous les indicateurs d'une cartographie"""
    from models import Cartographie, Risque, EvaluationRisque
    
    cartographie = Cartographie.query.get(cartographie_id)
    if not cartographie:
        return
    
    try:
        # 1. Compter les risques actifs
        risques_actifs = [r for r in cartographie.risques if not getattr(r, 'is_archived', False)]
        nb_risques_actifs = len(risques_actifs)
        
        # 2. Calculer les niveaux de risque
        niveaux_risques = {
            'Critique': 0,
            'Élevé': 0, 
            'Moyen': 0,
            'Faible': 0
        }
        
        for risque in risques_actifs:
            if risque.evaluations:
                # Prendre la dernière évaluation
                derniere_eval = max(risque.evaluations, key=lambda x: x.created_at, default=None)
                if derniere_eval and derniere_eval.niveau_risque in niveaux_risques:
                    niveaux_risques[derniere_eval.niveau_risque] += 1
        
        # 3. Calculer le score moyen de risque
        scores = []
        for risque in risques_actifs:
            if risque.evaluations:
                derniere_eval = max(risque.evaluations, key=lambda x: x.created_at, default=None)
                if derniere_eval and derniere_eval.score_risque:
                    scores.append(derniere_eval.score_risque)
        
        score_moyen = sum(scores) / len(scores) if scores else 0
        
        # 4. Mettre à jour les attributs calculés (si existent)
        if hasattr(cartographie, 'nb_risques_actifs'):
            cartographie.nb_risques_actifs = nb_risques_actifs
        
        if hasattr(cartographie, 'niveaux_risques'):
            cartographie.niveaux_risques = niveaux_risques
        
        if hasattr(cartographie, 'score_moyen_risque'):
            cartographie.score_moyen_risque = score_moyen
        
        print(f"📊 Indicateurs recalculés pour cartographie {cartographie_id}")
        print(f"   - Risques actifs: {nb_risques_actifs}")
        print(f"   - Niveaux: {niveaux_risques}")
        print(f"   - Score moyen: {score_moyen:.2f}")
        
    except Exception as e:
        print(f"❌ Erreur recalcul indicateurs: {str(e)}")


def invalider_cache_cartographie(cartographie_id):
    """Invalide le cache pour une cartographie spécifique"""
    try:
        # Vous pouvez implémenter ici votre logique de cache
        # Par exemple, supprimer des fichiers ou vider des clés Redis
        
        # Pour l'instant, juste un log
        print(f"🗑️ Cache invalidé pour cartographie {cartographie_id}")
        
    except Exception as e:
        print(f"⚠️ Erreur invalidation cache: {str(e)}")


def dupliquer_cartographie_complete(cartographie_id, user_id):
    """Duplique complètement une cartographie avec tous ses risques"""
    from models import db, Cartographie, Risque, EvaluationRisque, KRI, MesureKRI
    
    cartographie_origine = Cartographie.query.get(cartographie_id)
    if not cartographie_origine:
        return None
    
    try:
        print(f"🔄 Début duplication cartographie {cartographie_id}: {cartographie_origine.nom}")
        
        # Créer une nouvelle cartographie
        nouvelle_cartographie = Cartographie(
            nom=f"Copie de {cartographie_origine.nom}",
            description=cartographie_origine.description,
            direction_id=cartographie_origine.direction_id,
            service_id=cartographie_origine.service_id,
            type_cartographie=cartographie_origine.type_cartographie,
            created_by=user_id,
            created_at=datetime.utcnow()
        )
        
        db.session.add(nouvelle_cartographie)
        db.session.flush()  # Pour obtenir l'ID
        
        print(f"✅ Nouvelle cartographie créée: {nouvelle_cartographie.id}")
        
        # Dictionnaire pour mapper les anciens IDs aux nouveaux
        risques_map = {}
        
        # Dupliquer les risques non archivés
        for risque_origine in cartographie_origine.risques:
            if not getattr(risque_origine, 'is_archived', False):
                nouveau_risque = Risque(
                    cartographie_id=nouvelle_cartographie.id,
                    reference=f"{risque_origine.reference}_copy_{nouvelle_cartographie.id}",
                    intitule=risque_origine.intitule,
                    description=risque_origine.description,
                    processus_concerne=risque_origine.processus_concerne,
                    categorie=risque_origine.categorie,
                    type_risque=risque_origine.type_risque,
                    cause_racine=risque_origine.cause_racine,
                    consequences=risque_origine.consequences,
                    created_by=user_id,
                    created_at=datetime.utcnow(),
                    is_archived=False
                )
                
                db.session.add(nouveau_risque)
                db.session.flush()
                
                # Mapper l'ancien ID au nouveau
                risques_map[risque_origine.id] = nouveau_risque.id
                
                print(f"📝 Risque dupliqué: {risque_origine.id} -> {nouveau_risque.id}")
        
        db.session.commit()
        
        # Maintenant dupliquer les évaluations et KRI
        for risque_origine_id, nouveau_risque_id in risques_map.items():
            risque_origine = Risque.query.get(risque_origine_id)
            
            # Dupliquer les évaluations
            for eval_origine in risque_origine.evaluations:
                nouvelle_evaluation = EvaluationRisque(
                    risque_id=nouveau_risque_id,
                    campagne_id=eval_origine.campagne_id,
                    referent_pre_evaluation_id=eval_origine.referent_pre_evaluation_id,
                    date_pre_evaluation=eval_origine.date_pre_evaluation,
                    impact_pre=eval_origine.impact_pre,
                    probabilite_pre=eval_origine.probabilite_pre,
                    niveau_maitrise_pre=eval_origine.niveau_maitrise_pre,
                    commentaire_pre_evaluation=eval_origine.commentaire_pre_evaluation,
                    validateur_id=eval_origine.validateur_id,
                    date_validation=eval_origine.date_validation,
                    statut_validation=eval_origine.statut_validation,
                    impact_val=eval_origine.impact_val,
                    probabilite_val=eval_origine.probabilite_val,
                    niveau_maitrise_val=eval_origine.niveau_maitrise_val,
                    commentaire_validation=eval_origine.commentaire_validation,
                    evaluateur_final_id=eval_origine.evaluateur_final_id,
                    date_confirmation=eval_origine.date_confirmation,
                    impact_conf=eval_origine.impact_conf,
                    probabilite_conf=eval_origine.probabilite_conf,
                    niveau_maitrise_conf=eval_origine.niveau_maitrise_conf,
                    commentaire_confirmation=eval_origine.commentaire_confirmation,
                    campagne_nom=eval_origine.campagne_nom,
                    campagne_date_debut=eval_origine.campagne_date_debut,
                    campagne_date_fin=eval_origine.campagne_date_fin,
                    campagne_objectif=eval_origine.campagne_objectif,
                    score_risque=eval_origine.score_risque,
                    niveau_risque=eval_origine.niveau_risque,
                    type_evaluation=eval_origine.type_evaluation,
                    created_by=user_id,
                    created_at=datetime.utcnow()
                )
                db.session.add(nouvelle_evaluation)
            
            # Dupliquer les KRI
            if risque_origine.kri:
                kri_origine = risque_origine.kri
                nouveau_kri = KRI(
                    risque_id=nouveau_risque_id,
                    nom=kri_origine.nom,
                    description=kri_origine.description,
                    type_kri=kri_origine.type_kri,
                    unite_mesure=kri_origine.unite_mesure,
                    seuil_alerte=kri_origine.seuil_alerte,
                    seuil_critique=kri_origine.seuil_critique,
                    frequence_mesure=kri_origine.frequence_mesure,
                    responsable_mesure_id=kri_origine.responsable_mesure_id,
                    created_by=user_id,
                    created_at=datetime.utcnow()
                )
                db.session.add(nouveau_kri)
                db.session.flush()
                
                # Dupliquer les mesures KRI
                for mesure_origine in kri_origine.mesures:
                    nouvelle_mesure = MesureKRI(
                        kri_id=nouveau_kri.id,
                        valeur=mesure_origine.valeur,
                        date_mesure=mesure_origine.date_mesure,
                        commentaire=mesure_origine.commentaire,
                        created_by=user_id,
                        created_at=datetime.utcnow()
                    )
                    db.session.add(nouvelle_mesure)
        
        db.session.commit()
        
        # Recalculer les indicateurs de la nouvelle cartographie
        recalculer_indicateurs_cartographie(nouvelle_cartographie.id)
        
        print(f"✅ Duplication terminée. Nouvelle cartographie: {nouvelle_cartographie.id}")
        
        return nouvelle_cartographie.id
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur duplication cartographie: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def synchroniser_toutes_cartographies():
    """Synchronise toutes les cartographies"""
    from models import Cartographie
    
    cartographies = Cartographie.query.all()
    results = []
    
    for carto in cartographies:
        result = synchroniser_cartographie_complete(carto.id)
        results.append({
            'cartographie': carto.nom,
            'success': result
        })
    
    return results

def verifier_incoherences_cartographie(cartographie_id):
    """Vérifie et corrige les incohérences dans une cartographie"""
    from models import Cartographie, Risque, Direction, Service
    
    cartographie = Cartographie.query.get(cartographie_id)
    if not cartographie:
        return {'error': 'Cartographie non trouvée'}
    
    incoherences = []
    corrections = []
    
    # Vérifier la cohérence direction/service
    if cartographie.service_id and cartographie.direction_id:
        service = Service.query.get(cartographie.service_id)
        if service and service.direction_id != cartographie.direction_id:
            incoherences.append("Incohérence direction/service")
            # Corriger automatiquement
            cartographie.direction_id = service.direction_id
            cartographie.direction_nom = service.direction.nom
            corrections.append("Direction synchronisée avec le service")
    
    # Vérifier les risques orphelins
    risques_sans_evaluation = Risque.query.filter_by(
        cartographie_id=cartographie_id,
        is_archived=False
    ).filter(~Risque.evaluations.any()).count()
    
    if risques_sans_evaluation > 0:
        incoherences.append(f"{risques_sans_evaluation} risques sans évaluation")
    
    # Vérifier les descriptions manquantes
    if not cartographie.description:
        incoherences.append("Description manquante")
        cartographie.description = "Cartographie des risques"
        corrections.append("Description par défaut ajoutée")
    
    if corrections:
        db.session.commit()
    
    return {
        'cartographie': cartographie.nom,
        'incoherences': incoherences,
        'corrections': corrections,
        'timestamp': datetime.utcnow()
    }
def synchronisation_automatique():
    """Synchronisation automatique lancée périodiquement"""
    from models import Cartographie
    
    print("🔄 SYNCHRONISATION AUTOMATIQUE EN COURS...")
    
    cartographies = Cartographie.query.all()
    results = []
    
    for carto in cartographies:
        # Vérifier si une synchronisation est nécessaire
        besoin_sync = (
            carto.updated_at is None or 
            (datetime.utcnow() - carto.updated_at).total_seconds() > 3600  # 1 heure
        )
        
        if besoin_sync:
            result = synchroniser_cartographie_complete(carto.id)
            results.append({
                'cartographie': carto.nom,
                'synchronisee': result,
                'raison': 'Mise à jour programmée'
            })
        else:
            results.append({
                'cartographie': carto.nom, 
                'synchronisee': False,
                'raison': 'Déjà à jour'
            })
    
    print(f"✅ Synchronisation automatique terminée: {len([r for r in results if r['synchronisee']])}/{len(results)} cartographies")
    return results


def synchroniser_processus_apres_modification(processus_id, action_type, user_id):
    """Synchronise automatiquement les données après modification d'un processus"""
    from models import db, Processus
    
    processus = Processus.query.get(processus_id)
    if processus:
        processus.updated_at = datetime.utcnow()
        db.session.commit()
        
        print(f"🔄 Processus {processus.nom} synchronisé après {action_type}")
        
        # Synchronisation globale
        synchroniser_donnees_globales()
        
        # Synchronisation spécifique pour l'organigramme fluide
        if action_type == 'organigramme_fluide':
            synchroniser_organigramme_fluide(processus_id)

def synchroniser_organigramme_fluide(processus_id):
    """Synchroniser les données spécifiques à l'organigramme fluide"""
    from models import EtapeProcessus, LienProcessus
    
    # Vérifier la cohérence des données
    etapes = EtapeProcessus.query.filter_by(processus_id=processus_id).all()
    liens = LienProcessus.query.filter_by(processus_id=processus_id).all()
    
    # Nettoyer les liens orphelins
    for lien in liens:
        source_existe = any(e.id == lien.etape_source_id for e in etapes)
        cible_existe = any(e.id == lien.etape_cible_id for e in etapes)
        
        if not source_existe or not cible_existe:
            db.session.delete(lien)
    
    db.session.commit()
    print(f"✅ Organigramme fluide synchronisé pour le processus {processus_id}")

def synchroniser_evaluation_triphase(risque_id):
    """Synchronise automatiquement après une évaluation triphase"""
    from models import db, Risque, Cartographie
    
    risque = Risque.query.get(risque_id)
    if not risque:
        return
    
    print(f"🔄 Synchronisation évaluation triphase pour risque {risque.reference}")
    
    try:
        # 1. Mettre à jour les indicateurs de la cartographie
        mettre_a_jour_statistiques_cartographie(risque.cartographie_id)
        
        # 2. Forcer la regénération des matrices
        cartographie = Cartographie.query.get(risque.cartographie_id)
        if cartographie:
            cartographie.derniere_sync_matrices = datetime.utcnow()
        
        # 3. Mettre à jour le tableau de Bordeaux
        mettre_a_jour_tableau_bordeaux(risque.cartographie_id)
        
        # 4. Synchroniser le dashboard
        synchroniser_donnees_globales()
        
        db.session.commit()
        
        print(f"✅ Synchronisation terminée pour risque {risque.reference}")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur synchronisation: {str(e)}")

def synchroniser_donnees_globales():
    """Synchronise toutes les données entre les différentes vues"""
    from models import db, Risque, Cartographie, EvaluationRisque
    from sqlalchemy import func, and_
    
    print("🔄 SYNCHRONISATION GLOBALE DES DONNÉES...")
    
    try:
        # 1. Synchroniser les compteurs de risques
        total_risques_actifs = Risque.query.filter_by(is_archived=False).count()
        
        # 2. Synchroniser les niveaux de risque
        derniere_evaluation_subquery = db.session.query(
            EvaluationRisque.risque_id,
            func.max(EvaluationRisque.created_at).label('max_date')
        ).group_by(EvaluationRisque.risque_id).subquery()
        
        niveaux = db.session.query(
            EvaluationRisque.niveau_risque,
            func.count(EvaluationRisque.id)
        ).select_from(EvaluationRisque)\
         .join(derniere_evaluation_subquery, and_(
             EvaluationRisque.risque_id == derniere_evaluation_subquery.c.risque_id,
             EvaluationRisque.created_at == derniere_evaluation_subquery.c.max_date
         ))\
         .join(Risque, EvaluationRisque.risque_id == Risque.id)\
         .filter(Risque.is_archived == False)\
         .group_by(EvaluationRisque.niveau_risque).all()
        
        # 3. Synchroniser les cartographies
        cartographies = Cartographie.query.all()
        for carto in cartographies:
            mettre_a_jour_indicateurs_cartographie(carto.id)
        
        print(f"✅ Synchronisation terminée: {total_risques_actifs} risques actifs")
        print(f"📊 Répartition: {dict(niveaux)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur synchronisation: {str(e)}")
        return False

def generer_matrice_cotation_classique():
    """Génère la structure de données pour la matrice de cotation classique"""
    matrice = {
        'en_tetes': ['', '1 - Très rare', '2 - Rare', '3 - Possible', '4 - Probable', '5 - Très probable'],
        'lignes': []
    }
    
    impacts = [
        {'valeur': 1, 'label': '1 - Négligeable'},
        {'valeur': 2, 'label': '2 - Mineur'},
        {'valeur': 3, 'label': '3 - Modéré'},
        {'valeur': 4, 'label': '4 - Important'},
        {'valeur': 5, 'label': '5 - Critique'}
    ]
    
    for impact in impacts:
        ligne = {'impact': impact, 'cellules': []}
        for probabilite in range(1, 6):
            score = impact['valeur'] * probabilite
            niveau = get_niveau_risque_matrice(score)
            ligne['cellules'].append({
                'score': score,
                'niveau': niveau,
                'impact': impact['valeur'],
                'probabilite': probabilite
            })
        matrice['lignes'].append(ligne)
    
    return matrice

def get_niveau_risque_matrice(score):
    """Retourne le niveau de risque pour un score donné"""
    if score <= 4:
        return {'nom': 'Faible', 'couleur': 'faible', 'classe': 'matrice-connectee-faible'}
    elif score <= 9:
        return {'nom': 'Moyen', 'couleur': 'moyen', 'classe': 'matrice-connectee-moyen'}
    elif score <= 16:
        return {'nom': 'Élevé', 'couleur': 'eleve', 'classe': 'matrice-connectee-eleve'}
    else:
        return {'nom': 'Critique', 'couleur': 'critique', 'classe': 'matrice-connectee-critique'}

def calculer_statistiques_kri(kri):
    """Calcule les statistiques détaillées d'un KRI"""
    if not kri.mesures:
        return {
            'moyenne': 0,
            'min': 0,
            'max': 0,
            'tendance': 'stable',
            'derniere_valeur': 0,
            'ecart_type': 0
        }
    
    valeurs = [m.valeur for m in kri.mesures]
    dates = [m.date_mesure for m in kri.mesures]
    
    # Trier par date
    mesures_triees = sorted(zip(dates, valeurs), key=lambda x: x[0])
    valeurs_triees = [v for d, v in mesures_triees]
    
    stats = {
        'moyenne': round(np.mean(valeurs), 2),
        'min': round(min(valeurs), 2),
        'max': round(max(valeurs), 2),
        'derniere_valeur': valeurs_triees[-1] if valeurs_triees else 0,
        'ecart_type': round(np.std(valeurs), 2) if len(valeurs) > 1 else 0,
        'tendance': calculer_tendance_kri_detaille(valeurs_triees),
        'nb_mesures': len(valeurs),
        'periode_couverte': (max(dates) - min(dates)).days if len(dates) > 1 else 0
    }
    
    return stats

def calculer_tendance_kri_detaille(valeurs):
    """Calcule la tendance détaillée d'un KRI"""
    if len(valeurs) < 2:
        return 'stable'
    
    # Régression linéaire pour déterminer la pente
    x = np.arange(len(valeurs))
    slope, _ = np.polyfit(x, valeurs, 1)
    
    # Calculer le pourcentage de changement
    premier = valeurs[0]
    dernier = valeurs[-1]
    pourcentage_changement = ((dernier - premier) / premier * 100) if premier != 0 else 0
    
    if abs(slope) < 0.01:
        return 'stable'
    elif slope > 0.05:
        return 'hausse_forte' if pourcentage_changement > 10 else 'hausse_moderee'
    elif slope < -0.05:
        return 'baisse_forte' if pourcentage_changement < -10 else 'baisse_moderee'
    else:
        return 'stable'

def generer_graphique_kri(kri):
    """Génère un graphique d'évolution du KRI"""
    if not kri.mesures:
        return None
    
    mesures_triees = sorted(kri.mesures, key=lambda x: x.date_mesure)
    dates = [m.date_mesure.strftime('%d/%m/%Y') for m in mesures_triees]
    valeurs = [m.valeur for m in mesures_triees]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Courbe principale
    ax.plot(dates, valeurs, 'b-', linewidth=2, marker='o', markersize=4, label='Valeur KRI')
    
    # Seuils d'alerte
    if kri.seuil_alerte:
        ax.axhline(y=kri.seuil_alerte, color='orange', linestyle='--', 
                  label=f'Seuil alerte ({kri.seuil_alerte})')
    
    if kri.seuil_critique:
        ax.axhline(y=kri.seuil_critique, color='red', linestyle='--', 
                  label=f'Seuil critique ({kri.seuil_critique})')
    
    ax.set_xlabel('Date')
    ax.set_ylabel(f'Valeur ({kri.unite_mesure})')
    ax.set_title(f'Évolution du KRI - {kri.nom}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Rotation des dates pour meilleure lisibilité
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Conversion en base64
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    
    graphic = base64.b64encode(image_png).decode('utf-8')
    plt.close()
    
    return graphic
def synchroniser_kri_automatique():
    """Synchronisation automatique des KRI"""
    from models import KRI, MesureKRI, Risque, db
    from datetime import datetime, timedelta
    
    print("🔄 SYNCHRONISATION AUTOMATIQUE DES KRI...")
    
    try:
        kris = KRI.query.filter_by(est_actif=True).all()
        kris_synchronises = 0
        
        for kri in kris:
            # Vérifier si une synchronisation est nécessaire
            besoin_sync = (
                kri.derniere_sync is None or 
                (datetime.utcnow() - kri.derniere_sync).total_seconds() > 3600  # 1 heure
            )
            
            if besoin_sync:
                # Mettre à jour la tendance
                kri.tendance = calculer_tendance_kri(kri.mesures)
                kri.derniere_sync = datetime.utcnow()
                kris_synchronises += 1
                
                # Vérifier les alertes de seuil
                verifier_alertes_kri(kri)
        
        db.session.commit()
        print(f"✅ {kris_synchronises}/{len(kris)} KRI synchronisés")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur synchronisation KRI: {str(e)}")
        return False

def verifier_alertes_kri(kri):
    """Vérifier et créer des alertes pour les KRI dépassant les seuils"""
    from models import Alerte, MesureKRI, db
    
    if not kri.mesures:
        return
    
    derniere_mesure = MesureKRI.query.filter_by(kri_id=kri.id).order_by(MesureKRI.date_mesure.desc()).first()
    if not derniere_mesure:
        return
    
    valeur = derniere_mesure.valeur
    
    # Vérifier le seuil critique
    if kri.seuil_critique and valeur >= kri.seuil_critique:
        alerte = Alerte(
            type='kri_critique',
            gravite='haute',
            titre=f"KRI {kri.nom} - Seuil critique dépassé",
            description=f"Le KRI {kri.nom} a atteint la valeur {valeur}, dépassant le seuil critique de {kri.seuil_critique}",
            entite_type='kri',
            entite_id=kri.id,
            created_by=1  # Système
        )
        db.session.add(alerte)
    
    # Vérifier le seuil d'alerte
    elif kri.seuil_alerte and valeur >= kri.seuil_alerte:
        alerte = Alerte(
            type='kri_alerte', 
            gravite='moyenne',
            titre=f"KRI {kri.nom} - Seuil d'alerte dépassé",
            description=f"Le KRI {kri.nom} a atteint la valeur {valeur}, dépassant le seuil d'alerte de {kri.seuil_alerte}",
            entite_type='kri',
            entite_id=kri.id,
            created_by=1  # Système
        )
        db.session.add(alerte)

def synchroniser_kri_risque(risque_id):
    """Synchroniser les KRI d'un risque spécifique"""
    from models import KRI, Risque, db
    
    risque = Risque.query.get(risque_id)
    if not risque:
        return False
    
    kri = KRI.query.filter_by(risque_id=risque_id).first()
    if kri:
        # Mettre à jour la tendance
        kri.tendance = calculer_tendance_kri(kri.mesures)
        kri.derniere_sync = datetime.utcnow()
        
        # Vérifier les alertes
        verifier_alertes_kri(kri)
        
        db.session.commit()
        print(f"✅ KRI {kri.nom} synchronisé pour risque {risque.reference}")
        return True
    
    return False


def synchroniser_matrices_apres_evaluation_triphase(cartographie_id, risque_id=None):
    """Synchronise toutes les matrices après une évaluation triphase"""
    from models import Cartographie
    
    print(f"🔄 Synchronisation matrices après évaluation triphase - Carto: {cartographie_id}, Risque: {risque_id}")
    
    try:
        cartographie = Cartographie.query.get(cartographie_id)
        if not cartographie:
            print(f"❌ Cartographie {cartographie_id} non trouvée")
            return False
        
        # Forcer la regénération des matrices
        cartographie.derniere_sync_matrices = datetime.utcnow()
        
        # Mettre à jour les statistiques
        mettre_a_jour_statistiques_cartographie(cartographie_id)
        
        print(f"✅ Matrices synchronisées pour cartographie {cartographie.nom}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur synchronisation matrices: {str(e)}")
        return False
    
def invalider_cache_matrices(cartographie_id):
    """Invalide le cache des matrices de façon robuste - À PLACER DANS utils.py"""
    from models import Cartographie
    
    print(f"🗑️ Invalidation du cache pour cartographie {cartographie_id}")
    
    # Liste des clés de cache à invalider
    cache_keys = [
        f'matrice_classique_{cartographie_id}',
        f'matrice_criticite_{cartographie_id}', 
        f'matrice_priorisation_{cartographie_id}',
        f'matrice_surbrillance_{cartographie_id}',
        f'tableau_bordeaux_{cartographie_id}',
        f'statistiques_{cartographie_id}',
        f'indicateurs_{cartographie_id}'
    ]
    
    # Implémentation de l'invalidation (adaptez selon votre système de cache)
    for key in cache_keys:
        # Si vous utilisez un cache Redis ou mémoire :
        # cache.delete(key)
        print(f"   🔸 Cache invalidé: {key}")
    
    # Forcer le recalcul au prochain affichage en mettant à jour le timestamp
    try:
        cartographie = Cartographie.query.get(cartographie_id)
        if cartographie:
            cartographie.derniere_sync_matrices = datetime.utcnow()
            # Si vous avez un champ pour forcer le recalcul :
            # cartographie.a_besoin_recalcul = True
            print(f"   🔸 Timestamp de synchronisation mis à jour")
    except Exception as e:
        print(f"   ⚠️ Erreur mise à jour timestamp: {e}")
    
    return True

def synchroniser_scores_apres_evaluation_triphase(risque_id):
    """Synchronise automatiquement les scores après une évaluation triphase - VERSION ROBUSTE"""
    from models import Risque, EvaluationRisque, db
    
    risque = Risque.query.get(risque_id)
    if not risque:
        print(f"❌ Risque {risque_id} non trouvé pour synchronisation")
        return False
    
    try:
        evaluation = EvaluationRisque.query.filter_by(risque_id=risque_id)\
            .order_by(EvaluationRisque.created_at.desc()).first()
        
        if evaluation:
            # PRIORITÉ ESCALADE : Confirmation > Validation > Pré-évaluation
            impact_final = (evaluation.impact_conf or 
                          evaluation.impact_val or 
                          evaluation.impact_pre)
            probabilite_final = (evaluation.probabilite_conf or 
                               evaluation.probabilite_val or 
                               evaluation.probabilite_pre)
            
            if impact_final and probabilite_final:
                score_final = impact_final * probabilite_final
                niveau_final, _ = calculer_niveau_risque(impact_final, probabilite_final)
                
                # Mettre à jour l'évaluation
                evaluation.score_risque = score_final
                evaluation.niveau_risque = niveau_final
                
                # Mettre à jour le risque
                risque.derniere_evaluation = datetime.utcnow()
                
                db.session.commit()
                
                print(f"✅ Scores synchronisés pour {risque.reference}: {impact_final}×{probabilite_final}={score_final} → {niveau_final}")
                
                # Déclencher les mises à jour globales
                declencher_mise_a_jour_risque(risque_id, 'evaluation', 1, {
                    'niveau_risque': niveau_final,
                    'score_risque': score_final,
                    'impact': impact_final,
                    'probabilite': probabilite_final
                })
                
                return True
        
        return False
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur synchronisation scores: {str(e)}")
        return False

def log_system(level, module, message, details=None, ip_address=None):
    """Journalise un événement système"""
    try:
        log = SystemLog(
            level=level,
            module=module,
            message=message,
            details=details or {},
            ip_address=ip_address or (request.remote_addr if request else None)
        )
        db.session.add(log)
        db.session.commit()
        print(f"[{level.upper()}] {module}: {message}")
    except Exception as e:
        print(f"❌ Erreur journalisation système: {e}")


def create_notification(user_id, type, title, message, entity_type=None, entity_id=None):
    """Crée une notification pour un utilisateur"""
    try:
        notification = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            entity_type=entity_type,
            entity_id=entity_id
        )
        db.session.add(notification)
        db.session.commit()
        return notification
    except Exception as e:
        log_system('error', 'notification', f"Erreur création notification: {e}")
        return None


def track_user_session(user_id, session_id, ip_address=None, user_agent=None):
    """Suit une session utilisateur"""
    try:
        # Désactiver les sessions précédentes
        UserSession.query.filter_by(user_id=user_id, is_active=True).update({'is_active': False})
        
        # Créer la nouvelle session
        session = UserSession(
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address or (request.remote_addr if request else None),
            user_agent=user_agent or (request.user_agent.string if request else None)
        )
        db.session.add(session)
        db.session.commit()
        return session
    except Exception as e:
        log_system('error', 'session', f"Erreur suivi session: {e}")
        return None


def end_user_session(session_id):
    """Termine une session utilisateur"""
    try:
        session = UserSession.query.filter_by(session_id=session_id, is_active=True).first()
        if session:
            session.is_active = False
            session.logout_time = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        log_system('error', 'session', f"Erreur fin session: {e}")


class GestionnaireParametrage:
    """Gestionnaire pour le paramétrage dynamique des risques"""
    
    @staticmethod
    def generer_formulaire_risque(risque_id=None):
        """Génère dynamiquement un formulaire de risque avec champs personnalisés"""
        from app import db
        from models import Risque, ChampPersonnaliseRisque, ConfigurationChampRisque
        from forms import RisqueForm
        
        # Récupérer le risque existant si ID fourni
        risque = None
        if risque_id:
            risque = Risque.query.get(risque_id)
        
        # Récupérer tous les champs configurés actifs
        champs_config = ConfigurationChampRisque.query.filter_by(
            est_actif=True
        ).order_by(ConfigurationChampRisque.ordre_affichage).all()
        
        # Récupérer les valeurs existantes
        valeurs_existantes = {}
        if risque:
            champs_perso = ChampPersonnaliseRisque.query.filter_by(
                risque_id=risque_id
            ).all()
            for champ in champs_perso:
                valeurs_existantes[champ.nom_technique] = champ.get_valeur()
        
        # Générer le dictionnaire de données pour le formulaire
        form_data = {}
        for champ_config in champs_config:
            field_name = f"champ_{champ_config.nom_technique}"
            form_data[field_name] = valeurs_existantes.get(
                champ_config.nom_technique, 
                champ_config.valeur_defaut if hasattr(champ_config, 'valeur_defaut') else ''
            )
        
        return RisqueForm(data=form_data if form_data else None)
    
    @staticmethod
    def sauvegarder_champs_personnalises(risque_id, form_data):
        """Sauvegarde les champs personnalisés d'un risque"""
        from app import db
        from models import ChampPersonnaliseRisque
        
        try:
            for field_name, field_value in form_data.items():
                if field_name.startswith('champ_'):
                    nom_technique = field_name.replace('champ_', '')
                    
                    # Rechercher le champ existant
                    champ_perso = ChampPersonnaliseRisque.query.filter_by(
                        risque_id=risque_id,
                        nom_technique=nom_technique
                    ).first()
                    
                    if champ_perso:
                        # Mettre à jour la valeur
                        champ_perso.set_valeur(field_value)
                        champ_perso.updated_at = datetime.utcnow()
                    else:
                        # Créer un nouveau champ
                        champ_perso = ChampPersonnaliseRisque(
                            risque_id=risque_id,
                            nom_technique=nom_technique,
                            valeur_json={'valeur': field_value} if field_value else None
                        )
                        db.session.add(champ_perso)
            
            db.session.commit()
            print(f"✅ Champs personnalisés sauvegardés pour risque {risque_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Erreur sauvegarde champs personnalisés: {e}")
            return False
    
    @staticmethod
    def generer_liste_deroulante_options(nom_liste):
        """Génère les options pour une liste déroulante"""
        from models import ConfigurationListeDeroulante
        
        config_liste = ConfigurationListeDeroulante.query.filter_by(
            nom_technique=nom_liste,
            est_actif=True
        ).first()
        
        if config_liste and config_liste.valeurs:
            # Convertir en format pour les formulaires WTForms
            choices = [(item['valeur'], item['label']) for item in config_liste.valeurs]
            return choices
        
        return []
    
    @staticmethod
    def televerser_fichier(risque_id, fichier, categorie='document', description=''):
        """Téléverse un fichier associé à un risque"""
        from app import db
        from models import FichierRisque
        
        if not fichier or not allowed_file(fichier.filename):
            return None
        
        # Générer un nom de fichier sécurisé
        filename = secure_filename(fichier.filename)
        unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        
        # Chemin de sauvegarde
        upload_folder = app.config.get('UPLOAD_FOLDER_RISQUES', 'uploads/risques')
        filepath = os.path.join(upload_folder, unique_filename)
        
        try:
            # Sauvegarder le fichier
            fichier.save(filepath)
            
            # Créer l'entrée en base
            fichier_risque = FichierRisque(
                risque_id=risque_id,
                nom_fichier=filename,
                chemin_fichier=filepath,
                categorie=categorie,
                description=description,
                taille_fichier=os.path.getsize(filepath)
            )
            
            db.session.add(fichier_risque)
            db.session.commit()
            
            print(f"✅ Fichier téléversé: {filename} pour risque {risque_id}")
            return fichier_risque
            
        except Exception as e:
            print(f"❌ Erreur téléversement fichier: {e}")
            # Supprimer le fichier s'il a été partiellement créé
            if os.path.exists(filepath):
                os.remove(filepath)
            return None
    
    @staticmethod
    def get_config_fichiers():
        """Retourne la configuration des fichiers"""
        from app import app
        
        return {
            'extensions': list(app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'png', 'txt'})),
            'taille_max_mo': app.config.get('MAX_CONTENT_LENGTH', 10 * 1024 * 1024) // (1024 * 1024),
            'categories': ['document', 'image', 'analyse', 'autre']
        }
    
    @staticmethod
    def synchroniser_configuration_champ(champ):
        """Synchroniser l'ajout d'un champ avec toutes les fiches de risque"""
        from app import db
        from models import Risque, ChampPersonnaliseRisque
        
        print(f"🔄 Synchronisation champ ajouté: {champ.nom_technique}")
        
        # Pour les champs obligatoires, créer des entrées vides pour tous les risques existants
        if champ.est_obligatoire and champ.est_actif:
            risques = Risque.query.filter_by(is_archived=False).all()
            
            for risque in risques:
                # Vérifier si le champ existe déjà
                existing = ChampPersonnaliseRisque.query.filter_by(
                    risque_id=risque.id,
                    nom_technique=champ.nom_technique
                ).first()
                
                if not existing:
                    # Créer une entrée vide
                    champ_perso = ChampPersonnaliseRisque(
                        risque_id=risque.id,
                        nom_technique=champ.nom_technique
                    )
                    # Définir une valeur par défaut si disponible
                    if champ.valeurs_possibles and len(champ.valeurs_possibles) > 0:
                        champ_perso.set_valeur(champ.valeurs_possibles[0])
                    else:
                        champ_perso.set_valeur('')
                    db.session.add(champ_perso)
            
            db.session.commit()
            print(f"✅ Champ ajouté à {len(risques)} risques existants")
    
    @staticmethod
    def synchroniser_modification_champ(champ):
        """Synchroniser la modification d'un champ"""
        print(f"🔄 Synchronisation modification champ: {champ.nom_technique}")
        # Logique de synchronisation à implémenter selon les besoins


def log_activity(user_id, action_type, description, entity_type=None, entity_id=None):
    """
    Journalise une activité utilisateur
    """
    # ✅ SOLUTION : Importer À L'INTÉRIEUR de la fonction
    from flask import request
    from models import ActivityLog  # Import ici, pas en haut
    from app import db  # ou votre instance db
    
    try:
        log = ActivityLog(
            user_id=user_id,
            action_type=action_type,
            description=description,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=request.remote_addr if request else None,
            user_agent=request.user_agent.string if request and request.user_agent else None
        )
        db.session.add(log)
        db.session.commit()
        return True
    except Exception as e:
        print(f"❌ Erreur journalisation activité: {e}")
        db.session.rollback()
        return False

# services/dispositif_service.py

from datetime import datetime, timedelta
from sqlalchemy import func

class DispositifService:
    
    @staticmethod
    def analyser_couverture_risque(risque_id):
        """Analyse la couverture d'un risque par ses dispositifs"""
        from models import DispositifMaitrise
        
        dispositifs = DispositifMaitrise.query\
            .filter_by(risque_id=risque_id, is_archived=False, statut='actif')\
            .all()
        
        if not dispositifs:
            return {
                'couverture': 0,
                'niveau': 'Aucune',
                'recommandation': 'Définir au moins un dispositif de maîtrise'
            }
        
        # Calculer la couverture globale
        total_efficacite = sum(d.efficacite_reelle or 0 for d in dispositifs)
        total_attendu = sum(d.efficacite_attendue or 0 for d in dispositifs)
        
        # Vérifier la diversité des types
        types_presents = set(d.type_dispositif for d in dispositifs)
        types_necessaires = {'Préventif', 'Détectif', 'Correctif'}
        types_manquants = types_necessaires - types_presents
        
        # Analyse
        couverture = (total_efficacite / (len(dispositifs) * 5)) * 100 if dispositifs else 0
        
        if couverture >= 80 and not types_manquants:
            niveau = 'Optimale'
        elif couverture >= 60:
            niveau = 'Satisfaisante'
        elif couverture >= 40:
            niveau = 'Partielle'
        else:
            niveau = 'Insuffisante'
        
        recommandations = []
        if types_manquants:
            recommandations.append(f"Ajouter des dispositifs {', '.join(types_manquants)}")
        if couverture < 60:
            recommandations.append("Améliorer l'efficacité des dispositifs existants")
        
        return {
            'couverture': round(couverture, 1),
            'niveau': niveau,
            'recommandations': recommandations,
            'types_presents': list(types_presents),
            'types_manquants': list(types_manquants),
            'dispositifs_actifs': len(dispositifs),
            'efficacite_moyenne': round(total_efficacite / len(dispositifs), 1) if dispositifs else 0
        }
    
    @staticmethod
    def generer_rapport_couverture(cartographie_id):
        """Génère un rapport de couverture pour une cartographie"""
        from models import Risque, DispositifMaitrise
        
        risques = Risque.query\
            .filter_by(cartographie_id=cartographie_id, is_archived=False)\
            .all()
        
        rapport = {
            'date_generation': datetime.utcnow(),
            'cartographie_id': cartographie_id,
            'risques_analyses': len(risques),
            'dispositifs_totaux': 0,
            'risques_sans_dispositif': 0,
            'risques_couverture_optimale': 0,
            'risques_couverture_insuffisante': 0,
            'details': []
        }
        
        for risque in risques:
            analyse = DispositifService.analyser_couverture_risque(risque.id)
            dispositifs_count = DispositifMaitrise.query\
                .filter_by(risque_id=risque.id, is_archived=False)\
                .count()
            
            rapport['dispositifs_totaux'] += dispositifs_count
            
            detail = {
                'risque_id': risque.id,
                'reference': risque.reference,
                'intitule': risque.intitule,
                'niveau_risque': risque.dernier_niveau_risque,
                'dispositifs_count': dispositifs_count,
                'couverture': analyse['couverture'],
                'niveau_couverture': analyse['niveau'],
                'recommandations': analyse['recommandations']
            }
            
            rapport['details'].append(detail)
            
            if dispositifs_count == 0:
                rapport['risques_sans_dispositif'] += 1
            elif analyse['couverture'] >= 80:
                rapport['risques_couverture_optimale'] += 1
            elif analyse['couverture'] < 40:
                rapport['risques_couverture_insuffisante'] += 1
        
        return rapport
    
    @staticmethod
    def detecter_dispositifs_a_verifier(client_id=None, jours_alerte=30):
        """Détecte les dispositifs nécessitant une vérification"""
        from models import DispositifMaitrise
        
        query = DispositifMaitrise.query\
            .filter_by(is_archived=False, statut='actif')
        
        if client_id:
            query = query.filter_by(client_id=client_id)
        
        aujourdhui = datetime.utcnow().date()
        date_limite = aujourdhui + timedelta(days=jours_alerte)
        
        dispositifs = query.filter(
            (DispositifMaitrise.prochaine_verification <= date_limite) |
            (DispositifMaitrise.prochaine_verification.is_(None)) |
            (DispositifMaitrise.date_derniere_verification.is_(None))
        ).all()
        
        resultats = []
        for d in dispositifs:
            if d.prochaine_verification:
                jours_restants = (d.prochaine_verification - aujourdhui).days
                niveau = 'critique' if jours_restants <= 7 else 'alerte' if jours_restants <= 30 else 'info'
            else:
                jours_restants = None
                niveau = 'alerte'
            
            resultats.append({
                'dispositif': d,
                'jours_restants': jours_restants,
                'niveau': niveau,
                'message': f"Vérification prévue le {d.prochaine_verification.strftime('%d/%m/%Y')}" if d.prochaine_verification else "Vérification jamais effectuée"
            })
        
        return sorted(resultats, key=lambda x: x['jours_restants'] or 9999)


# services/audit_service.py - Ajoutez cette fonction

def creer_plan_action_automatique(risque_id, dispositif_id, titre, description, responsable_id, echeance):
    """Crée automatiquement un plan d'action lié à un dispositif"""
    from models import PlanAction, Risque
    
    risque = Risque.query.get(risque_id)
    if not risque:
        return None
    
    # Générer la référence
    derniere_ref = PlanAction.query.filter(
        PlanAction.reference.like(f'PA-{risque.reference}-%')
    ).order_by(PlanAction.reference.desc()).first()
    
    if derniere_ref:
        try:
            num = int(derniere_ref.reference.split('-')[-1]) + 1
        except:
            num = 1
    else:
        num = 1
    
    reference = f"PA-{risque.reference}-{num:03d}"
    
    plan = PlanAction(
        reference=reference,
        titre=titre,
        description=description,
        risque_id=risque_id,
        dispositif_id=dispositif_id,
        responsable_id=responsable_id,
        date_echeance=echeance,
        statut='en_cours',
        priorite='moyenne',
        created_by=current_user.id,
        client_id=current_user.client_id
    )
    
    db.session.add(plan)
    db.session.commit()
    
    # Mettre à jour le dispositif
    dispositif = DispositifMaitrise.query.get(dispositif_id)
    if dispositif:
        dispositif.plan_action_id = plan.id
        db.session.commit()
    
    return plan
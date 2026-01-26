# routes/notifications.py - VERSION SIMPLIFIÉE
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from datetime import datetime
from models import db, Notification

# Créer le blueprint
notifications_bp = Blueprint('notifications', __name__)

# ==================== ROUTES PRINCIPALES ====================

@notifications_bp.route('/notifications')
@login_required
def liste_notifications():
    """Page principale des notifications"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Appliquer les filtres
    type_filter = request.args.get('type')
    urgence_filter = request.args.get('urgence')
    statut_filter = request.args.get('statut')
    
    query = Notification.query.filter_by(destinataire_id=current_user.id)
    
    if type_filter:
        query = query.filter_by(type_notification=type_filter)
    if urgence_filter:
        query = query.filter_by(urgence=urgence_filter)
    if statut_filter == 'non_lue':
        query = query.filter_by(est_lue=False)
    elif statut_filter == 'lue':
        query = query.filter_by(est_lue=True)
    
    notifications = query.order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    # Types disponibles
    types = {
        'nouvelle_constatation': 'Nouvelle constatation',
        'nouvelle_recommandation': 'Nouvelle recommandation',
        'nouveau_plan': 'Nouveau plan d\'action',
        'echeance': 'Échéance',
        'retard': 'Retard',
        'kri_alerte': 'Alerte KRI',
        'veille': 'Veille réglementaire',
        'audit': 'Notification d\'audit',
        'systeme': 'Notification système'
    }
    
    return render_template('notifications/liste.html',
                         notifications=notifications,
                         types=types,
                         page=page)

@notifications_bp.route('/notifications/notification/<int:notification_id>/lire')
@login_required
def lire_notification(notification_id):
    """Lire une notification spécifique"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.destinataire_id != current_user.id:
        abort(403)
    
    # Marquer comme lue
    notification.est_lue = True
    notification.read_at = datetime.utcnow()
    db.session.commit()
    
    # Rediriger vers la page de l'entité si possible
    if notification.entite_type and notification.entite_id:
        urls = {
            'audit': f'/audit/{notification.entite_id}',
            'constatation': f'/audit/constatation/{notification.entite_id}',
            'recommandation': f'/audit/recommandation/{notification.entite_id}',
            'plan_action': f'/audit/plan-action/{notification.entite_id}',
            'risque': f'/risque/{notification.entite_id}',
            'kri': f'/kri/{notification.entite_id}',
            'cartographie': f'/cartographie/{notification.entite_id}',
        }
        if notification.entite_type in urls:
            return redirect(urls[notification.entite_type])
    
    return redirect(url_for('notifications.liste_notifications'))

@notifications_bp.route('/notifications/marquer-toutes-lues', methods=['POST'])
@login_required
def marquer_toutes_lues():
    """Marquer toutes les notifications comme lues"""
    Notification.query.filter_by(
        destinataire_id=current_user.id,
        est_lue=False
    ).update({
        'est_lue': True,
        'read_at': datetime.utcnow()
    })
    
    db.session.commit()
    
    if request.is_json:
        return jsonify({'success': True})
    
    flash('Toutes les notifications ont été marquées comme lues', 'success')
    return redirect(url_for('notifications.liste_notifications'))

@notifications_bp.route('/notifications/notification/<int:notification_id>/supprimer', methods=['DELETE'])
@login_required
def supprimer_notification(notification_id):
    """Supprimer une notification"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.destinataire_id != current_user.id:
        abort(403)
    
    db.session.delete(notification)
    db.session.commit()
    
    return jsonify({'success': True})

@notifications_bp.route('/notifications/supprimer-toutes-lues', methods=['DELETE'])
@login_required
def supprimer_toutes_lues():
    """Supprimer toutes les notifications lues"""
    Notification.query.filter_by(
        destinataire_id=current_user.id,
        est_lue=True
    ).delete()
    
    db.session.commit()
    
    return jsonify({'success': True})

# ==================== ROUTES API ====================

@notifications_bp.route('/api/notifications/count')
@login_required
def api_notifications_count():
    """API pour obtenir le nombre de notifications non lues"""
    count = Notification.query.filter_by(
        destinataire_id=current_user.id,
        est_lue=False
    ).count()
    
    return jsonify({'count': count})

@notifications_bp.route('/api/notifications/recent')
@login_required
def api_notifications_recent():
    """API pour les notifications récentes (pour dropdown)"""
    limit = request.args.get('limit', 5, type=int)
    
    notifications = Notification.query.filter_by(
        destinataire_id=current_user.id
    ).order_by(
        Notification.created_at.desc()
    ).limit(limit).all()
    
    notifications_data = []
    for notif in notifications:
        notifications_data.append({
            'id': notif.id,
            'titre': notif.titre,
            'message': notif.message,
            'est_lue': notif.est_lue,
            'urgence': notif.urgence,
            'created_at': notif.created_at.isoformat() if notif.created_at else None,
            'url': notif.get_url() if hasattr(notif, 'get_url') else '#',
            'icon': notif.get_icon() if hasattr(notif, 'get_icon') else 'bell',
            'color': notif.get_color() if hasattr(notif, 'get_color') else 'primary'
        })
    
    return jsonify({
        'notifications': notifications_data,
        'count': Notification.query.filter_by(
            destinataire_id=current_user.id,
            est_lue=False
        ).count()
    })

@notifications_bp.route('/api/notifications/<int:notification_id>/toggle-lue', methods=['POST'])
@login_required
def api_toggle_notification_lue(notification_id):
    """API pour basculer l'état lu/non lu"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.destinataire_id != current_user.id:
        abort(403)
    
    notification.est_lue = not notification.est_lue
    notification.read_at = datetime.utcnow() if notification.est_lue else None
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'est_lue': notification.est_lue
    })

@notifications_bp.route('/api/notifications/<int:notification_id>/marquer-lue', methods=['POST'])
@login_required
def api_marquer_notification_lue(notification_id):
    """API pour marquer une notification comme lue"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.destinataire_id != current_user.id:
        abort(403)
    
    notification.est_lue = True
    notification.read_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})

# ==================== PRÉFÉRENCES ====================

@notifications_bp.route('/preferences-notifications')
@login_required
def preferences_notifications():
    """Page des préférences de notifications"""
    # Version simplifiée pour commencer
    return render_template('notifications/preferences.html')

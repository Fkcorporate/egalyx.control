# routes/notifications.py - VERSION CORRIGÉE DÉFINITIVE
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from datetime import datetime
from models import db, Notification, User, Audit, Constatation, Recommandation, PlanAction, Risque

# Créer le blueprint
notifications_bp = Blueprint('notifications', __name__)

# ==================== FONCTIONS UTILITAIRES ====================

def format_time_ago(date):
    """Formate une date en texte (ex: 'il y a 5 minutes')"""
    if not date:
        return "Date inconnue"
    
    now = datetime.utcnow()
    diff = now - date
    
    if diff.days > 30:
        return date.strftime('%d/%m/%Y')
    elif diff.days > 0:
        if diff.days == 1:
            return f"Il y a 1 jour"
        return f"Il y a {diff.days} jours"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        if hours == 1:
            return f"Il y a 1 heure"
        return f"Il y a {hours} heures"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        if minutes == 1:
            return f"Il y a 1 minute"
        return f"Il y a {minutes} minutes"
    else:
        return "À l'instant"

def get_notification_icon(notification_type):
    """Retourne l'icône selon le type de notification"""
    icons = {
        'nouvelle_constatation': 'exclamation-circle',
        'nouvelle_recommandation': 'lightbulb',
        'nouveau_plan': 'tasks',
        'echeance': 'calendar-exclamation',
        'retard': 'clock',
        'kri_alerte': 'chart-line',
        'veille': 'balance-scale',
        'audit_demarre': 'play-circle',
        'audit_termine': 'check-circle',
        'risque_evalue': 'exclamation-triangle',
        'systeme': 'cog',
        'info': 'info-circle',
        'success': 'check-circle',
        'warning': 'exclamation-triangle',
        'error': 'times-circle'
    }
    return icons.get(notification_type, 'bell')

def get_notification_color(urgence):
    """Retourne la couleur selon l'urgence"""
    colors = {
        'urgent': 'danger',
        'important': 'warning',
        'normal': 'info'
    }
    return colors.get(urgence, 'secondary')

# ==================== ROUTE PRINCIPALE ====================

@notifications_bp.route('/notifications')
@login_required
def liste_notifications():
    """Page principale des notifications - VERSION CORRIGÉE"""
    try:
        # ========== 1. COMPTER TOUTES LES NOTIFICATIONS ==========
        # Récupérer TOUTES les notifications de l'utilisateur (sans filtre)
        toutes_notifications = Notification.query.filter_by(destinataire_id=current_user.id).all()
        
        print(f"🔔 [DEBUG] Utilisateur {current_user.username}: {len(toutes_notifications)} notifications trouvées")
        
        # Afficher les 5 premières pour debug
        for notif in toutes_notifications[:5]:
            print(f"  - {notif.id}: {notif.titre[:50]} (lue={notif.est_lue})")
        
        # ========== 2. CALCULER LES STATISTIQUES ==========
        stats = {
            'total': len(toutes_notifications),
            'non_lues': len([n for n in toutes_notifications if not n.est_lue]),
            'lues': len([n for n in toutes_notifications if n.est_lue]),
            'urgentes': len([n for n in toutes_notifications if not n.est_lue and n.urgence == 'urgent'])
        }
        
        print(f"📊 STATS: total={stats['total']}, non_lues={stats['non_lues']}")
        
        # ========== 3. RÉCUPÉRER LES FILTRES ==========
        page = request.args.get('page', 1, type=int)
        per_page = 20
        type_filter = request.args.get('type', '')
        urgence_filter = request.args.get('urgence', '')
        statut_filter = request.args.get('statut', '')
        
        # ========== 4. APPLIQUER LES FILTRES ==========
        query = Notification.query.filter_by(destinataire_id=current_user.id)
        
        if type_filter and type_filter != '':
            query = query.filter_by(type_notification=type_filter)
        if urgence_filter and urgence_filter != '':
            query = query.filter_by(urgence=urgence_filter)
        if statut_filter == 'non_lue':
            query = query.filter_by(est_lue=False)
        elif statut_filter == 'lue':
            query = query.filter_by(est_lue=True)
        
        # ========== 5. PAGINATION ==========
        query = query.order_by(Notification.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # ========== 6. PRÉPARER LES DONNÉES POUR LE TEMPLATE ==========
        notifications_data = []
        for notif in pagination.items:
            notifications_data.append({
                'id': notif.id,
                'type': notif.type_notification,
                'titre': notif.titre,
                'message': notif.message,
                'urgence': notif.urgence,
                'est_lue': notif.est_lue,
                'created_at': notif.created_at,
                'time_ago': format_time_ago(notif.created_at),
                'icon': get_notification_icon(notif.type_notification),
                'color': get_notification_color(notif.urgence),
                'entite_type': notif.entite_type,
                'entite_id': notif.entite_id,
                'url': notif.get_url() if hasattr(notif, 'get_url') else None
            })
        
        # ========== 7. TYPES POUR LE FILTRE ==========
        types = {
            'nouvelle_constatation': '📝 Nouvelle constatation',
            'nouvelle_recommandation': '💡 Nouvelle recommandation',
            'nouveau_plan': '📋 Nouveau plan d\'action',
            'echeance': '⏰ Échéance',
            'retard': '⚠️ Retard',
            'kri_alerte': '📊 Alerte KRI',
            'veille': '📚 Veille réglementaire',
            'audit_demarre': '▶️ Audit démarré',
            'audit_termine': '✅ Audit terminé',
            'audit': '📋 Audit',
            'systeme': '⚙️ Système',
            'info': 'ℹ️ Information',
            'success': '✅ Succès',
            'warning': '⚠️ Avertissement',
            'error': '❌ Erreur'
        }
        
        print(f"✅ Rendu template avec {len(notifications_data)} notifications sur cette page")
        
        return render_template(
            'notifications/liste.html',
            notifications=pagination,
            notifications_data=notifications_data,
            types=types,
            stats=stats,
            type_filter=type_filter,
            urgence_filter=urgence_filter,
            statut_filter=statut_filter,
            format_time_ago=format_time_ago
        )
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        
        return render_template(
            'notifications/liste.html',
            notifications=[],
            notifications_data=[],
            types={},
            stats={'total': 0, 'non_lues': 0, 'lues': 0, 'urgentes': 0},
            type_filter='',
            urgence_filter='',
            statut_filter=''
        )


# ==================== AUTRES ROUTES ====================

@notifications_bp.route('/notifications/notification/<int:notification_id>/lire')
@login_required
def lire_notification(notification_id):
    """Lire une notification spécifique"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.destinataire_id != current_user.id:
        abort(403)
    
    notification.est_lue = True
    notification.read_at = datetime.utcnow()
    db.session.commit()
    
    # Rediriger vers la page de l'entité
    if notification.entite_type == 'audit' and notification.entite_id:
        return redirect(url_for('detail_audit', id=notification.entite_id))
    elif notification.entite_type == 'cartographie' and notification.entite_id:
        return redirect(url_for('detail_cartographie', id=notification.entite_id))
    elif notification.entite_type == 'risque' and notification.entite_id:
        return redirect(url_for('detail_risque', id=notification.entite_id))
    
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
    """API pour les notifications récentes"""
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
            'time_ago': format_time_ago(notif.created_at),
            'icon': get_notification_icon(notif.type_notification),
            'color': get_notification_color(notif.urgence),
            'url': notif.get_url() if hasattr(notif, 'get_url') else '#'
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
    
    return jsonify({'success': True, 'est_lue': notification.est_lue})

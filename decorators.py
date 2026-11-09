# decorators.py
from functools import wraps
from flask import flash, redirect, url_for, session, abort
from models import User

def login_required(f):
    """Décorateur pour vérifier que l'utilisateur est connecté"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter pour accéder à cette page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    """Décorateur pour vérifier les permissions d'un utilisateur"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Veuillez vous connecter.', 'warning')
                return redirect(url_for('login'))
            
            user = User.query.get(session['user_id'])
            if not user:
                session.clear()
                flash('Utilisateur non trouvé.', 'danger')
                return redirect(url_for('login'))
            
            # Vérification des permissions
            if not user.has_permission(permission):
                flash('Vous n\'avez pas les droits nécessaires.', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    """Décorateur pour vérifier que l'utilisateur est admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Veuillez vous connecter.', 'warning')
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash('Accès réservé aux administrateurs.', 'danger')
            return redirect(url_for('dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    """Décorateur pour vérifier le rôle de l'utilisateur"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Veuillez vous connecter.', 'warning')
                return redirect(url_for('login'))
            
            user = User.query.get(session['user_id'])
            if not user or user.role not in allowed_roles:
                flash('Vous n\'avez pas les droits nécessaires.', 'danger')
                return redirect(url_for('dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator